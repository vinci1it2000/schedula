# coding: utf-8
from __future__ import annotations

try:
    from tests.utils.server._unittest_guard import ensure_server_test_env
except Exception:
    from _unittest_guard import ensure_server_test_env

ensure_server_test_env()

import datetime as dt
import json
import os
import unittest
import uuid
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Dict, Any, List, Tuple
from unittest.mock import patch
from urllib.parse import urlsplit, urlunsplit

import httpx
import pydash
from flask import Flask
from flask_security.utils import hash_password

from schedula.utils.form.server import basic_app
from schedula.utils.form.server.contracts.engine import register_function
from schedula.utils.form.server.extensions import db as _db
from schedula.utils.form.server.security import User
from schedula.utils.form.server.security.casbin import get_enforcer
from schedula.utils.form.server.security.casbin.bootstrap import (
    bootstrap_user,
    set_system_admin,
)
from schedula.utils.form.server.security.casbin.helpers import ADMIN_DOMAIN, ANON_USER
from schedula.utils.form.server.security.casbin.models import Group
from tests.utils.server.conftest import DummySitemap


def get_riders_order(
        doc: Dict[str, Any], pop_size: int = 200, n_gen: int = 300
) -> Dict[str, Any]:
    """
    GA permutation optimizer for Pickup&Delivery with time windows.

    Included features:
    1) Dropoff uses ONLY a deadline (latest = destination.at + flexibility). No earliest on dropoff.
    2) Precedence (pickup before dropoff) enforced via a REPAIR step (so GA always evaluates precedence-feasible routes).
    3) Start time (start_epoch) is optimized within driver's origin window (origin.at +/- origin.flexibility if present),
       choosing the latest feasible start (reduces waiting) in HARD mode; in SOFT mode uses latest allowed.

    Outputs:
      - "stops": list of stops including "at"
      - "riders": dict keyed by rider_id with pickup/drop_off objects (at, reminder_id, zone, window)
      - "summary": feasibility/mode and stats
    """
    context = doc["context"]
    contract_id = doc["_id"]
    import requests
    import numpy as np
    from schedula.utils.form.server.contracts.schedule import schedule_event_at
    from dateutil.parser import isoparse
    from datetime import datetime, timezone

    # ---------------- helpers ----------------
    def fmt(coords) -> str:
        return "{0},{1}".format(*coords)

    def to_epoch_seconds(s: str) -> float:
        return isoparse(s).timestamp()

    def epoch_to_iso(ts: float) -> str:
        return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone().isoformat()

    # ---------------- read riders ----------------
    riders_items = sorted(context.get("riders", {}).items(), key=lambda kv: kv[0])
    n_riders = len(riders_items)

    # ---------------- driver start window (optional) ----------------
    origin = context["driver_route"]["trip"]["origin"]
    driver_at = to_epoch_seconds(origin["at"])
    driver_f = float(origin.get("flexibility", 0) or 0)
    driver_start_min = driver_at - driver_f
    driver_start_max = driver_at + driver_f

    # ---------------- build ABS time windows (epoch seconds) ----------------
    # Global indexing:
    # 0 = driver start, 1 = driver end,
    # rider j: pickup = 2+2*j, drop = 3+2*j
    tw_abs_earliest: Dict[int, float] = {}  # ONLY pickups (earliest)
    tw_abs_latest: Dict[int, float] = {}  # pickups + drops (latest)

    for j, (_rid, r) in enumerate(riders_items):
        p = 2 + 2 * j
        d = 3 + 2 * j

        # pickup window: [at-flex, at+flex]
        p_at = to_epoch_seconds(r["trip"]["origin"]["at"])
        p_f = float(r["trip"]["origin"].get("flexibility", 0) or 0)
        tw_abs_earliest[p] = p_at - p_f
        tw_abs_latest[p] = p_at + p_f

        # drop: ONLY deadline (latest = at + flex)
        d_at = to_epoch_seconds(r["trip"]["destination"]["at"])
        d_f = float(r["trip"]["destination"].get("flexibility", 0) or 0)
        tw_abs_latest[d] = d_at + d_f

    # ---------------- build coordinates and duration matrix ----------------
    start_coords = origin["location"]["coordinates"]
    end_coords = context["driver_route"]["trip"]["destination"]["location"][
        "coordinates"
    ]

    coords_list = [fmt(start_coords), fmt(end_coords)]
    for _j, (_rid, r) in enumerate(riders_items):
        coords_list.extend(
            [
                fmt(r["trip"]["origin"]["location"]["coordinates"]),
                fmt(r["trip"]["destination"]["location"]["coordinates"]),
            ]
        )
    coordinates = ";".join(coords_list)

    matrix = requests.get(
        f"https://www.consapi.eu/api/table/v1/duration/{coordinates}?api_key=test"
    ).json()["durations"]

    D = np.array(matrix, dtype=float)

    # NOTE: flexibility is seconds (3600 = 1h). Ensure D is seconds.
    # If D is minutes, uncomment:
    # D *= 60.0

    internal = np.arange(2, 2 + 2 * n_riders, dtype=int)
    s = np.zeros(
        D.shape[0], dtype=float
    )  # service times per node (seconds). Fill if you have them.

    # ---------------- precedence repair ----------------
    # Perm genes are in [0..2*n_riders-1] => internal[gene] is a global node index.
    # For rider j:
    #   pickup gene id = 2*j
    #   drop gene id   = 2*j + 1
    def repair_perm(perm: np.ndarray) -> np.ndarray:
        pos = np.empty_like(perm)
        for i, g in enumerate(perm):
            pos[g] = i

        perm = perm.copy()
        for j in range(n_riders):
            gp = 2 * j
            gd = 2 * j + 1
            if pos[gd] < pos[gp]:
                i_d = int(pos[gd])
                i_p = int(pos[gp])
                perm[i_d], perm[i_p] = perm[i_p], perm[i_d]
                pos[gd], pos[gp] = pos[gp], pos[gd]
        return perm

    # ---------------- simulate with a given start epoch ----------------
    def simulate_with_start(start_epoch: float, full: np.ndarray):
        t = float(start_epoch)
        t_service_abs: Dict[int, float] = {0: t}
        lateness: Dict[int, float] = {}
        total_travel = 0.0
        total_wait = 0.0

        for a, b in zip(full[:-1], full[1:]):
            a = int(a)
            b = int(b)

            travel = float(D[a, b])
            total_travel += travel
            t = t + travel

            eb = tw_abs_earliest.get(b)
            if eb is not None and t < eb:
                total_wait += eb - t
                t = eb

            t_service_abs[b] = t

            lb = tw_abs_latest.get(b)
            lateness[b] = max(0.0, t - lb) if lb is not None else 0.0

            t += float(s[b])

        return t_service_abs, lateness, total_travel, total_wait

    def is_feasible_start(start_epoch: float, full: np.ndarray) -> bool:
        _t_service_abs, lateness, _travel, _wait = simulate_with_start(
            start_epoch, full
        )
        return max(lateness.values() or [0.0]) <= 0.0

    # ---------------- GA: hard then soft fallback ----------------
    from pymoo.core.problem import Problem
    from pymoo.operators.sampling.rnd import PermutationRandomSampling
    from pymoo.operators.crossover.ox import OrderCrossover
    from pymoo.operators.mutation.inversion import InversionMutation
    from pymoo.algorithms.soo.nonconvex.ga import GA
    from pymoo.optimize import minimize
    from pymoo.termination import get_termination

    # HARD constraints count:
    # pickups: earliest + latest (2 each) => 2*n_riders
    # drops: latest only (1 each)        => 1*n_riders
    # total: 3*n_riders
    class PDRouteHard(Problem):
        def __init__(self):
            super().__init__(
                n_var=2 * n_riders,
                n_obj=1,
                n_ieq_constr=3 * n_riders,
                xl=0,
                xu=2 * n_riders - 1,
                type_var=int,
            )

        def _evaluate(self, X, out, *args, **kwargs):
            pop = X.shape[0]
            F = np.zeros(pop)
            G = np.zeros((pop, self.n_ieq_constr))

            start_nominal = (
                driver_start_min  # fixed for GA eval; optimized after route chosen
            )

            for i in range(pop):
                perm = repair_perm(X[i])
                route_internal = internal[perm]
                full = np.concatenate(([0], route_internal, [1]))

                t_service_abs, _lateness, travel_cost, _wait = simulate_with_start(
                    start_nominal, full
                )
                F[i] = travel_cost

                c = 0
                for j in range(n_riders):
                    p = 2 + 2 * j
                    d = 3 + 2 * j

                    # pickup earliest: a - t <= 0
                    a_p = tw_abs_earliest[p]
                    t_p = t_service_abs.get(p, 1e30)
                    G[i, c] = a_p - t_p
                    c += 1

                    # pickup latest: t - b <= 0
                    b_p = tw_abs_latest[p]
                    G[i, c] = t_p - b_p
                    c += 1

                    # drop latest: t - b <= 0
                    b_d = tw_abs_latest[d]
                    t_d = t_service_abs.get(d, 1e30)
                    G[i, c] = t_d - b_d
                    c += 1

            out["F"] = F.reshape(-1, 1)
            out["G"] = G

    class PDRouteSoft(Problem):
        def __init__(self):
            super().__init__(
                n_var=2 * n_riders,
                n_obj=1,
                n_ieq_constr=0,
                xl=0,
                xu=2 * n_riders - 1,
                type_var=int,
            )

        def _evaluate(self, X, out, *args, **kwargs):
            pop = X.shape[0]
            F = np.zeros(pop)

            start_nominal = driver_start_min
            PEN_LATE = 2000.0  # lateness penalty weight
            PEN_WAIT = 1.0  # mild wait penalty

            for i in range(pop):
                perm = repair_perm(X[i])
                route_internal = internal[perm]
                full = np.concatenate(([0], route_internal, [1]))

                _t_service_abs, lateness, travel_cost, total_wait = simulate_with_start(
                    start_nominal, full
                )

                late_sum = 0.0
                for node in route_internal:
                    late_sum += float(lateness.get(int(node), 0.0))

                F[i] = travel_cost + PEN_LATE * late_sum + PEN_WAIT * total_wait

            out["F"] = F.reshape(-1, 1)

    def run_ga(problem: Problem):
        algorithm = GA(
            pop_size=pop_size,
            sampling=PermutationRandomSampling(),
            crossover=OrderCrossover(prob=0.9),
            mutation=InversionMutation(prob=0.2),
        )
        res = minimize(
            problem,
            algorithm,
            termination=get_termination("n_gen", n_gen),
            seed=1,
            verbose=False,
        )
        return res

    # Execute
    res_hard = run_ga(PDRouteHard())
    feasible_hard = False
    if hasattr(res_hard, "G") and res_hard.G is not None:
        feasible_hard = float(np.max(res_hard.G)) <= 0.0

    if feasible_hard:
        res = res_hard
        mode = "hard"
    else:
        res = run_ga(PDRouteSoft())
        mode = "soft"

    # Best repaired perm -> route
    best_perm = repair_perm(res.X)
    route_internal = internal[best_perm]
    full = np.concatenate(([0], route_internal, [1]))

    # ---------------- optimize start time within driver window ----------------
    # Choose latest feasible start in hard mode (reduces waiting).
    # In soft mode choose driver_start_max (heuristic).
    if mode == "hard" and is_feasible_start(driver_start_min, full):
        if is_feasible_start(driver_start_max, full):
            start_opt = driver_start_max
        else:
            lo, hi = driver_start_min, driver_start_max
            for _ in range(40):
                mid = (lo + hi) / 2.0
                if is_feasible_start(mid, full):
                    lo = mid
                else:
                    hi = mid
            start_opt = lo
    else:
        start_opt = driver_start_max if mode == "soft" else driver_start_min

    # Final simulation at optimized start
    t_service_abs, lateness_abs, travel_cost, total_wait = simulate_with_start(
        start_opt, full
    )
    lateness_values = [
        float(lateness_abs.get(int(node), 0.0)) for node in route_internal
    ]
    total_lateness = float(np.sum(lateness_values))
    max_lateness = float(np.max(lateness_values)) if lateness_values else 0.0
    feasible_final = (mode == "hard") and (max_lateness <= 0.0)

    summary = {
        "feasible": feasible_final,
        "mode": mode,
        "start_epoch": float(start_opt),
        "start_iso": epoch_to_iso(start_opt),
        "travel_time_sec": float(travel_cost),
        "total_wait_sec": float(total_wait),
        "total_lateness_sec": float(total_lateness),
        "max_lateness_sec": float(max_lateness),
    }
    context["_route_summary"] = summary

    # ---------------- stops output ----------------
    idx_to_stop: Dict[int, Tuple[str, str]] = {}
    for j, (rid, _r) in enumerate(riders_items):
        idx_to_stop[2 + 2 * j] = ("pickup", rid)
        idx_to_stop[3 + 2 * j] = ("drop_off", rid)  # renamed to drop_off

    stops: List[Dict[str, Any]] = []
    for idx in full:
        idx = int(idx)
        if idx == 0:
            stops.append(
                {
                    "type": "origin",
                    "location": context["driver_route"]["trip"]["origin"]["location"],
                    "at": epoch_to_iso(start_opt),
                }
            )
        elif idx == 1:
            stops.append(
                {
                    "type": "destination",
                    "location": context["driver_route"]["trip"]["destination"][
                        "location"
                    ],
                    "at": epoch_to_iso(t_service_abs.get(1, start_opt)),
                }
            )
        else:
            stop_type, rid = idx_to_stop[idx]
            rider = context["riders"][rid]
            if stop_type == "pickup":
                loc = rider["trip"]["origin"]["location"]
            else:
                loc = rider["trip"]["destination"]["location"]

            stop = {
                "type": stop_type,
                "rider_id": rid,
                "location": loc,
                "at": epoch_to_iso(t_service_abs[idx]),
            }
            late = float(lateness_abs.get(idx, 0.0))
            if late > 0:
                stop["lateness_sec"] = late
            stops.append(stop)

    # ---------------- rider-centered output (requested format) ----------------
    # radius: choose >= 200. Use context["zone_radius"] if provided, else 200.
    default_radius = float(context.get("zone_radius", 300))
    if default_radius < 200:
        default_radius = 200.0

    reminder_prefix = str(context.get("reminder_prefix", "rem"))

    riders_out: Dict[str, Any] = {}
    for j, (rid, r) in enumerate(riders_items):
        p_idx = 2 + 2 * j
        d_idx = 3 + 2 * j

        p_loc = r["trip"]["origin"]["location"]
        d_loc = r["trip"]["destination"]["location"]

        # Pickup window ISO
        p_at = to_epoch_seconds(r["trip"]["origin"]["at"])
        p_f = float(r["trip"]["origin"].get("flexibility", 0) or 0)
        p_win_start = epoch_to_iso(p_at - p_f)
        p_win_end = epoch_to_iso(p_at + p_f)

        # Drop window ISO:
        # "drop_off only deadline" => represent window as [destination.at - flex, destination.at + flex] for transparency
        # (even if earliest isn't enforced). If you prefer start == at, tell me.
        d_at = to_epoch_seconds(r["trip"]["destination"]["at"])
        d_f = float(r["trip"]["destination"].get("flexibility", 0) or 0)
        d_win_start = epoch_to_iso(d_at - d_f)
        d_win_end = epoch_to_iso(d_at + d_f)

        riders_out[rid] = {
            "pickup": {
                "reminder_id": schedule_event_at(
                    datetime.fromtimestamp(
                        t_service_abs[p_idx] - 20 * 60, tz=timezone.utc
                    ),
                    {
                        "contract_id": contract_id,
                        "event_name": "RiderPickupReminderTimed",
                        "payload": {"principal": rid},
                        "actor_id": "system:cron",
                    },
                ),
                "at": epoch_to_iso(t_service_abs[p_idx]),
                "zone": {
                    "radius": default_radius,
                    "location": p_loc,
                },
                "window": {
                    "start": p_win_start,
                    "end": p_win_end,
                },
            },
            "drop_off": {
                "reminder_id": schedule_event_at(
                    datetime.fromtimestamp(
                        t_service_abs[d_idx] + 20 * 60, tz=timezone.utc
                    ),
                    {
                        "contract_id": contract_id,
                        "event_name": "RiderDropOffReminderTimed",
                        "payload": {"principal": rid},
                        "actor_id": "system:cron",
                    },
                ),
                "at": epoch_to_iso(t_service_abs[d_idx]),
                "zone": {
                    "radius": default_radius,
                    "location": d_loc,
                },
                "window": {
                    "start": d_win_start,
                    "end": d_win_end,
                },
            },
        }

    return {
        "driver": {
            "stops": stops,
            "start": {
                "at": epoch_to_iso(start_opt),
                "reminder_id": schedule_event_at(
                    datetime.fromtimestamp(start_opt - 60 * 60, tz=timezone.utc),
                    {
                        "contract_id": contract_id,
                        "event_name": "TripDepartureReminderTimed",
                        "actor_id": "system:cron",
                        "payload": {},
                    },
                ),
            },
            "end": {
                "at": epoch_to_iso(t_service_abs[1]),
                "reminder_id": schedule_event_at(
                    datetime.fromtimestamp(
                        t_service_abs[1] + 2 * 60 * 60, tz=timezone.utc
                    ),
                    {
                        "contract_id": contract_id,
                        "event_name": "TripPaymentTimed",
                        "actor_id": "system:cron",
                        "payload": {},
                    },
                ),
            },
        },
        "riders": riders_out,
        "summary": summary,
    }


register_function("get_riders_order", get_riders_order)


@lru_cache(maxsize=1)
def _gherkin_definition_template() -> Dict[str, Any]:
    p = Path(__file__).with_name("data") / "gherkin_definition.json"
    return json.loads(p.read_text(encoding="utf-8"))


def _gherkin_definition() -> Dict[str, Any]:
    return deepcopy(_gherkin_definition_template())


class ContractsE2ETest(unittest.TestCase):
    _mongo_container: Any = None
    _mongo_base_uri: str = ""
    _mysql_container: Any = None
    _sqlalchemy_uri: str = ""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        desktop_sock = os.path.join(
            os.path.expanduser("~"), ".docker", "run", "docker.sock"
        )
        if not os.environ.get("DOCKER_HOST") and os.path.exists(desktop_sock):
            os.environ["DOCKER_HOST"] = f"unix://{desktop_sock}"
        try:
            from testcontainers.mongodb import MongoDbContainer
            from testcontainers.mysql import MySqlContainer
        except Exception as ex:  # pragma: no cover - environment dependent
            raise unittest.SkipTest(
                "contracts e2e requires testcontainers[mongodb,mysql]"
            ) from ex

        try:
            cls._mongo_container = MongoDbContainer("mongo:7.0")
            cls._mongo_container.start()
            cls._mongo_base_uri = str(cls._mongo_container.get_connection_url())
            cls._mysql_container = MySqlContainer("mysql:8.0")
            cls._mysql_container.start()
            mysql_uri = str(cls._mysql_container.get_connection_url())
            if mysql_uri.startswith("mysql://"):
                mysql_uri = "mysql+pymysql://" + mysql_uri[len("mysql://"):]
            cls._sqlalchemy_uri = mysql_uri
        except Exception as ex:  # pragma: no cover - environment dependent
            raise unittest.SkipTest(
                "contracts e2e requires Docker with runnable MongoDB and MySQL containers"
            ) from ex

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            if cls._mongo_container is not None:
                cls._mongo_container.stop()
            if cls._mysql_container is not None:
                cls._mysql_container.stop()
        finally:
            cls._mongo_container = None
            cls._mongo_base_uri = ""
            cls._mysql_container = None
            cls._sqlalchemy_uri = ""
            super().tearDownClass()

    def _test_mongo_uri(self) -> str:
        self.mongo_db_name = f"schedula_contracts_{uuid.uuid4().hex}"
        parts = urlsplit(self.__class__._mongo_base_uri)
        query = parts.query
        if "authSource=" not in query:
            query = f"{query}&authSource=admin" if query else "authSource=admin"
        return urlunsplit(
            (
                parts.scheme,
                parts.netloc,
                f"/{self.mongo_db_name}",
                query,
                parts.fragment,
            )
        )

    def setUp(self) -> None:
        os.environ.pop("MONGO_URI", None)
        self.app = Flask("contracts_test")
        self.mongo_uri = self._test_mongo_uri()
        from pymongo import MongoClient

        self.mongo_client = MongoClient(self.mongo_uri)
        config = dict(
            TESTING=True,
            DEBUG=True,
            PROPAGATE_EXCEPTIONS=True,
            SQLALCHEMY_DATABASE_URI=self.__class__._sqlalchemy_uri,
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            SECURITY_ENABLED=True,
            SECURITY_REGISTERABLE=True,
            SECURITY_SEND_REGISTER_EMAIL=False,
            SECURITY_CONFIRMABLE=True,
            SECURITY_RECOVERABLE=True,
            SECURITY_CHANGEABLE=True,
            CONTRACTS_ENABLED=True,
            SECURITY_LOGIN_AFTER_REGISTER=False,
            SECURITY_URL_PREFIX="/user",
            WTF_CSRF_ENABLED=False,
            SCHEDULA_CSRF_ENABLED=False,
            ITEMS_STORAGE_ENABLED=True,
            FILES_STORAGE_ENABLED=False,
            S3_ITEMS_FILE_STORAGE=False,
            CONTACT_ENABLED=False,
            SCHEDULA_CREDITS_ENABLED=True,
            SCHEDULA_EXPORT_FORM_ENABLED=False,
            SCHEDULA_GDPR_ENABLED=False,
            SCHEDULA_LOCALE_ENABLED=False,
            SCHEDULA_SECRETS_ENABLED=False,
            OPENAPI_ENABLED=False,
            CASBIN_ADMIN_ENABLED=False,
            STRIPE_SECRET_KEY="sk_test_dummy",
            STRIPE_PUBLISHABLE_KEY="pk_test_dummy",
            STRIPE_WEBHOOK_SECRET_KEY="whsec_dummy",
            MONGO_URI=self.mongo_uri,
        )
        sitemap = DummySitemap()
        setattr(sitemap, "stripe_event_handler", staticmethod(lambda _event: None))
        basic_app(sitemap, self.app, config)

        with self.app.app_context():
            _db.create_all()
            owner = self._create_user("owner-1@gmail.com")
            user = self._create_user("u1@gmail.com")
            admin = self._create_user("admin@gmail.com")
            d1 = self._create_user("d1@gmail.com")
            p1 = self._create_user("p1@gmail.com")
            p2 = self._create_user("p2@gmail.com")
            p3 = self._create_user("p3@gmail.com")
            p4 = self._create_user("p4@gmail.com")
            for u in (owner, user, admin, d1, p1, p2, p3, p4):
                bootstrap_user(u.id)
            set_system_admin(admin.id, enabled=True)
            enforcer = get_enforcer()
            enforcer.add_policy(
                [ANON_USER, ADMIN_DOMAIN, "contracts:templates", "manage", "allow"]
            )
            self.user_ids = {
                "owner-1": owner.id,
                "u1": user.id,
                "admin": admin.id,
                "d1": d1.id,
                "p1": p1.id,
                "p2": p2.id,
                "p3": p3.id,
                "p4": p4.id,
            }
            self._locations = {
                "owner-1": {
                    "origin": {
                        "location": {
                            "type": "Point",
                            "coordinates": [7.6869, 45.0703],
                        },  # Torino
                        "at": "2026-02-20T08:00:00+01:00",
                        "flexibility": 3600,
                    },
                    "destination": {
                        "location": {
                            "type": "Point",
                            "coordinates": [9.1900, 45.4642],
                        },  # Milano
                        "at": "2026-02-20T10:04:00+01:00",
                        "flexibility": 3600,
                    },
                },
                "u1": {
                    "origin": {
                        "location": {
                            "type": "Point",
                            "coordinates": [8.8470, 45.4627],
                        },  # Novara
                        "at": "2026-02-20T09:13:00+01:00",
                        "flexibility": 3600,
                    },
                    "destination": {
                        "location": {
                            "type": "Point",
                            "coordinates": [10.2118, 45.5416],
                        },  # Brescia
                        "at": "2026-02-20T11:44:00+01:00",
                        "flexibility": 3600,
                    },
                },
                "admin": {
                    "origin": {
                        "location": {
                            "type": "Point",
                            "coordinates": [9.1900, 45.4642],
                        },  # Milano
                        "at": "2026-02-20T10:04:00+01:00",
                        "flexibility": 3600,
                    },
                    "destination": {
                        "location": {
                            "type": "Point",
                            "coordinates": [10.9916, 45.4384],
                        },  # Verona
                        "at": "2026-02-20T12:43:00+01:00",
                        "flexibility": 3600,
                    },
                },
                "p1": {
                    "origin": {
                        "location": {
                            "type": "Point",
                            "coordinates": [9.6773, 45.6983],
                        },  # Bergamo
                        "at": "2026-02-20T10:56:00+01:00",
                        "flexibility": 3600,
                    },
                    "destination": {
                        "location": {
                            "type": "Point",
                            "coordinates": [11.8768, 45.4064],
                        },  # Padova
                        "at": "2026-02-20T13:48:00+01:00",
                        "flexibility": 3600,
                    },
                },
                "p2": {
                    "origin": {
                        "location": {
                            "type": "Point",
                            "coordinates": [10.2118, 45.5416],
                        },  # Brescia
                        "at": "2026-02-20T11:44:00+01:00",
                        "flexibility": 3600,
                    },
                    "destination": {
                        "location": {
                            "type": "Point",
                            "coordinates": [12.3155, 45.4408],
                        },  # Venezia
                        "at": "2026-02-20T14:30:00+01:00",
                        "flexibility": 3600,
                    },
                },
                "p3": {
                    "origin": {
                        "location": {
                            "type": "Point",
                            "coordinates": [10.9916, 45.4384],
                        },  # Verona
                        "at": "2026-02-20T12:43:00+01:00",
                        "flexibility": 3600,
                    },
                    "destination": {
                        "location": {
                            "type": "Point",
                            "coordinates": [12.3155, 45.4408],
                        },  # Venezia
                        "at": "2026-02-20T14:30:00+01:00",
                        "flexibility": 3600,
                    },
                },
                "p4": {
                    "origin": {
                        "location": {
                            "type": "Point",
                            "coordinates": [11.8768, 45.4064],
                        },  # Padova
                        "at": "2026-02-20T13:48:00+01:00",
                        "flexibility": 3600,
                    },
                    "destination": {
                        "location": {
                            "type": "Point",
                            "coordinates": [12.3155, 45.4408],
                        },  # Venezia
                        "at": "2026-02-20T14:30:00+01:00",
                        "flexibility": 3600,
                    },
                },
                "d1": {
                    "origin": {
                        "location": {
                            "type": "Point",
                            "coordinates": [7.6869, 45.0703],
                        },  # Torino
                        "at": "2026-02-20T08:00:00+01:00",
                        "flexibility": 3600 * 5,
                    },
                    "destination": {
                        "location": {
                            "type": "Point",
                            "coordinates": [12.3155, 45.4408],
                        },  # Venezia
                        "at": "2026-02-20T14:30:00+01:00",
                        "flexibility": 3600 * 5,
                    },
                },
            }

            from schedula.utils.form.server.credits import get_wallet

            self.route_by_principal: Dict[str, str] = {}
            items_coll = self.app.config["MONGO_DB"]["items"]
            self.now = now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
            self.departure = departure = now + dt.timedelta(hours=3)
            self.locations = locations = self.shift_locations(departure)
            for k, uid in self.user_ids.items():
                principal = f"u:{uid}"
                route_id = str(uuid.uuid4())
                loc = locations[k]
                t_start = int(dt.datetime.fromisoformat(loc["origin"]["at"]).timestamp())
                t_end = int(dt.datetime.fromisoformat(loc["destination"]["at"]).timestamp())
                route_doc = {
                    "cost": 10,
                    "available_seats": 3,
                    "from": {
                        "lat": loc["origin"]["location"]["coordinates"][1],
                        "lng": loc["origin"]["location"]["coordinates"][0],
                    },
                    "to": {
                        "lat": loc["destination"]["location"]["coordinates"][1],
                        "lng": loc["destination"]["location"]["coordinates"][0],
                    },
                    "schedule": {
                        "datetime": t_start,
                        "sow_at_start": 0,
                        "sow_at_end": t_end - t_start,
                        "time_type": 'departure',
                        "flexibility": loc["origin"]["flexibility"] / 60
                    },
                }
                items_coll.insert_one(
                    {
                        "_id": route_id,
                        "category": "ride_posts",
                        "data": route_doc,
                        "created_by": principal,
                        "updated_by": principal,
                        "created_at": dt.datetime.utcnow(),
                        "updated_at": dt.datetime.utcnow(),
                    }
                )
                self.route_by_principal[principal] = route_id

                wallet = get_wallet(uid)
                wallet.charge(product="credit", credits=100)

        self.httpx = httpx.Client(
            transport=httpx.WSGITransport(app=self.app),
            base_url="http://test",
        )
        self.client = self.app.test_client(use_cookies=False)
        self.tokens = {
            "owner-1": self._login_token("owner-1@gmail.com"),
            "u1": self._login_token("u1@gmail.com"),
            "admin": self._login_token("admin@gmail.com"),
            "d1": self._login_token("d1@gmail.com"),
            "p1": self._login_token("p1@gmail.com"),
            "p2": self._login_token("p2@gmail.com"),
            "p3": self._login_token("p3@gmail.com"),
            "p4": self._login_token("p4@gmail.com"),
        }

    def tearDown(self) -> None:
        try:
            self.httpx.close()
        except Exception:
            pass
        with self.app.app_context():
            _db.session.remove()
            _db.drop_all()
            try:
                _db.engine.dispose()
            except Exception:
                pass
        try:
            from pymongo import MongoClient

            client = MongoClient(self.mongo_uri)
            client.drop_database(self.mongo_db_name)
            client.close()
        except Exception:
            pass
        try:
            self.mongo_client.close()
        except Exception:
            pass

    def _create_user(self, email: str) -> User:
        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(
                firstname=email.split("@")[0],
                lastname=email.split("@")[1],
                email=email,
                password=hash_password("UserPass123!"),
                active=True,
                fs_uniquifier=str(uuid.uuid4()),
            )
            _db.session.add(user)
        user.confirmed_at = dt.datetime.utcnow()
        _db.session.commit()
        return user

    def _login_token(self, email: str) -> str:
        resp = self.client.post(
            "/user/login", json={"email": email, "password": "UserPass123!"}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json(silent=True) or {}
        token = data.get("response", {}).get("user", {}).get("token")
        self.assertIsNotNone(token)
        return str(token)

    def _headers(self, actor: str) -> Dict[str, str]:
        return {"Authentication-Token": self.tokens[actor]}

    def _create_template(self, definition: Dict[str, Any], **extra: Any) -> str:
        body = {
            "name": f"tpl-{uuid.uuid4()}",
            "definition": definition,
            "is_enabled": True,
        }
        body.update(extra)
        resp = self.httpx.post(
            "/contracts/templates", json=body, headers=self._headers("admin")
        )
        self.assertEqual(resp.status_code, 201, msg=resp.text)
        return str(resp.json()["id"])

    def _create_contract(
            self, template_id: str, context: Dict[str, Any], actor="owner-1", **extra: Any
    ) -> httpx.Response:
        body = {"context": context}
        body.update(extra)
        return self.httpx.post(
            f"/contracts/{template_id}",
            json=body,
            headers=self._headers(actor),
        )

    def _post_event(
            self,
            contract_id: str,
            path: str,
            *,
            actor: str,
            payload: Dict[str, Any] | None = None,
    ) -> httpx.Response:
        if payload is None and path == "request-join":
            actor_principal = f"u:{self.user_ids[actor]}"
            payload = {
                "route_id": self.route_by_principal[actor_principal],
            }
        if payload is None and path == "driver-accept-start":
            payload = {"rider": f"u:{self.user_ids['p1']}"}
        return self.httpx.post(
            f"/contracts/{contract_id}/{path}",
            json=payload or {},
            headers=self._headers(actor),
        )

    def _run_worker_once(self, *, now: dt.datetime | None = None) -> bool:
        from schedula.utils.form.server.contracts.schedule import (
            _func,
            _queue_coll,
            ack_done,
            claim_job,
            nack_retry,
            now_utc,
        )

        now = now or dt.datetime.now(dt.timezone.utc)
        with patch(
                "schedula.utils.form.server.contracts.schedule._claim_job_now",
                return_value=now,
        ):
            with self.app.app_context():
                coll = _queue_coll()
                job = claim_job(coll)
                if not job:
                    return False
                try:
                    resp = _func(**(job.get("payload") or {}))
                    if job.get("kind") == "cron":
                        coll.update_one(
                            {"_id": job["_id"]},
                            {
                                "$set": {
                                    "status": "PENDING",
                                    "run_at": now_utc() + dt.timedelta(seconds=10),
                                    "updated_at": now_utc(),
                                },
                                "$unset": {
                                    "locked_until": "",
                                    "locked_by": "",
                                    "started_at": "",
                                },
                            },
                        )
                    else:
                        ack_done(coll, job["_id"], resp)
                except Exception as ex:
                    nack_retry(coll, job["_id"], ex, delay_s=0)
                    raise
        return True

    def _group_member_ids(self, gid: str) -> set[str]:
        raw_gid = gid[2:] if gid.startswith("g:") else gid
        with self.app.app_context():
            grp = _db.session.get(Group, raw_gid)
            self.assertIsNotNone(grp)
            assert grp is not None
            members = grp.members(models=False)
            out: set[str] = set()
            for m in members:
                if not isinstance(m, dict):
                    continue
                mid = m.get("id")
                if isinstance(mid, str) and mid.startswith("u:"):
                    out.add(mid)
            return out

    def _group_admin_ids(self, gid: str) -> set[str]:
        raw_gid = gid[2:] if gid.startswith("g:") else gid
        with self.app.app_context():
            grp = _db.session.get(Group, raw_gid)
            self.assertIsNotNone(grp)
            assert grp is not None
            members = grp.members(models=False)
            out: set[str] = set()
            for m in members:
                if not isinstance(m, dict):
                    continue
                mid = m.get("id")
                is_admin = bool(m.get("is_admin"))
                if isinstance(mid, str) and mid.startswith("u:") and is_admin:
                    out.add(mid)
            return out

    def _queue_jobs(
            self, *, contract_id: str | None = None, event_name: str | None = None
    ) -> List[Dict[str, Any]]:
        from schedula.utils.form.server.contracts.schedule import _queue_coll

        q: Dict[str, Any] = {}
        if contract_id is not None:
            q["payload.contract_id"] = contract_id
        if event_name is not None:
            q["payload.event_name"] = event_name
        with self.app.app_context():
            return list(_queue_coll().find(q))

    def _user_state(self, contract: Dict[str, Any], user_id: int) -> str:
        return str((contract.get("states") or {}).get(f"u:{user_id}") or "")

    def _rider_pin(self, contract: Dict[str, Any], principal: str) -> str:
        rider = (
                    ((contract.get("context") or {}).get("riders") or {}).get(principal)
                ) or {}
        return str(((rider.get("verification") or {}).get("pin")) or "")

    def _count_notifications_for(self, principal: str, event: str) -> int:
        with self.app.app_context():
            coll = self.app.config["MONGO_DB"]["notifications"]
            return int(
                coll.count_documents(
                    {"event": event, f"targets.{principal}": {"$exists": True}}
                )
            )

    def _wallet_balance(self, actor: str, product: str = "credit") -> float:
        with self.app.app_context():
            from schedula.utils.form.server.credits import get_wallet

            wallet = get_wallet(self.user_ids[actor])
            import time

            time.sleep(1)
            bal = wallet.balance(product=product, session=_db.session)
            if isinstance(bal, dict):
                return float(bal.get(product, 0) or 0)
            return float(bal or 0)

    def _list_notifications(self, actor: str) -> List[Dict[str, Any]]:
        resp = self.httpx.get("/notification", headers=self._headers(actor))
        self.assertEqual(resp.status_code, 200, msg=resp.text)
        data = resp.json() or {}
        return list(data.get("notifications") or [])

    def _count_notification_event_api(self, actor: str, event: str) -> int:
        notes = self._list_notifications(actor)
        return sum(1 for n in notes if n.get("event") == event)

    def _latest_notification_event_api(
            self, actor: str, event: str
    ) -> Dict[str, Any] | None:
        notes = self._list_notifications(actor)
        filtered = [n for n in notes if n.get("event") == event]
        if not filtered:
            return None
        return filtered[0]

    def _latest_notification_doc(
            self, principal: str, event: str
    ) -> Dict[str, Any] | None:
        with self.app.app_context():
            coll = self.app.config["MONGO_DB"]["notifications"]
            return coll.find_one(
                {"event": event, f"targets.{principal}": {"$exists": True}},
                sort=[("_id", -1)],
            )

    def _get_route(self, actor: str, route_id: str) -> Dict[str, Any]:
        resp = self.httpx.get(f"/item/ride_posts/{route_id}", headers=self._headers(actor))
        self.assertEqual(resp.status_code, 200, msg=resp.text)
        return resp.json() or {}

    def _get_contract_doc(self, contract_id: str) -> Dict[str, Any]:
        from schedula.utils.form.server.contracts.engine import _contracts_coll

        with self.app.app_context():
            doc = _contracts_coll().find_one({"_id": contract_id})
        self.assertIsNotNone(doc)
        return doc or {}

    def shift_locations(self, departure: dt.datetime) -> None:
        """
        Shift semplice:
        diff = new_departure - old_d1_departure
        poi somma diff a tutti gli origin.at e destination.at
        """

        # parse old departure di d1
        old_departure = dt.datetime.fromisoformat(self._locations["d1"]["origin"]["at"])

        diff = departure - old_departure
        locations = {}
        for actor, d in self._locations.items():
            locations[actor] = new_d = {}
            for point in ("origin", "destination"):
                new_d[point] = d[point].copy()
                new_d[point]["at"] = (
                        dt.datetime.fromisoformat(d[point]["at"]) + diff
                ).isoformat()
        return locations

    def _create_route(self, actor: str, **updates: Any) -> str:
        loc = self.locations.get(actor, self.locations["p1"])
        t_start = int(dt.datetime.fromisoformat(loc["origin"]["at"]).timestamp())
        t_end = int(dt.datetime.fromisoformat(loc["destination"]["at"]).timestamp())
        data = {
            "cost": 10,
            "available_seats": 3,
            "requested_seats": 1,
            "from": {
                "lat": loc["origin"]["location"]["coordinates"][1],
                "lng": loc["origin"]["location"]["coordinates"][0],
            },
            "to": {
                "lat": loc["destination"]["location"]["coordinates"][1],
                "lng": loc["destination"]["location"]["coordinates"][0],
            },
            "schedule": {
                "datetime": t_start,
                "sow_at_start": 0,
                "sow_at_end": t_end - t_start,
                "time_type": 'departure',
                "flexibility": loc["origin"]["flexibility"] / 60
            },
        }
        data.update(updates)
        resp = self.httpx.post(
            "/item/ride_posts",
            json={"data": data},
            headers=self._headers(actor),
        )
        self.assertEqual(resp.status_code, 201, msg=resp.text)
        body = resp.json() or {}
        return str(body.get("id"))

    def _patch_route_data(
            self, actor: str, route_id: str, **updates: Any
    ) -> Dict[str, Any]:
        current = self._get_route(actor, route_id)
        data = dict(current.get("data") or {})
        data.update(updates)
        resp = self.httpx.patch(
            f"/item/ride_posts/{route_id}",
            json={"data": data},
            headers=self._headers(actor),
        )
        self.assertEqual(resp.status_code, 200, msg=resp.text)
        return resp.json() or {}

    def _gherkin_context_for(self, driver: str) -> Dict[str, Any]:
        driver_principal = f"u:{self.user_ids[driver]}"
        return {
            "driver_trip_id": self.route_by_principal[driver_principal],
        }

    def _gherkin_context(self, initial_state: str = "START") -> Dict[str, Any]:
        driver_uid = self.user_ids["d1"]
        driver_principal = f"u:{driver_uid}"
        return {
            "driver_trip_id": self.route_by_principal[driver_principal],
        }

    def _create_gherkin_contract(self, initial_state: str = "START", actor="p1") -> str:
        definition = _gherkin_definition()
        template_id = self._create_template(
            definition,
            allowed_initial_states=["START"],
        )
        created = self._create_contract(
            template_id,
            self._gherkin_context(initial_state=initial_state),
            initial_state=initial_state,
            actor=actor,
        )
        self.assertEqual(created.status_code, 201)
        cid = str(created.json()["id"])
        if actor in self.user_ids and actor != "d1":
            joined = self._post_event(cid, "request-join", actor=actor)
            self.assertEqual(joined.status_code, 200, msg=joined.text)
            self.assertTrue((joined.json() or {}).get("ok"), msg=joined.text)
        return cid

    def _to_recruiting(self, cid: str) -> str:
        self.assertEqual(
            self._post_event(cid, "driver-accept-start", actor="d1").status_code,
            200,
        )
        self.assertEqual(
            self._post_event(cid, "accept-user", actor="p1").status_code, 200
        )
        c = self._get_contract_doc(cid)
        self.assertEqual(c["state"], "ONBOARDING")
        gid = str((c.get("context") or {}).get("group_id") or "")
        self.assertTrue(gid)
        return gid

    def _to_ready(self, cid: str) -> str:
        gid = self._to_recruiting(cid)
        self.assertEqual(
            self._post_event(
                cid,
                "invite-user",
                actor="d1",
                payload={
                    "route_id": self.route_by_principal[f"u:{self.user_ids['p2']}"]
                },
            ).status_code,
            200,
        )
        self.assertEqual(
            self._post_event(cid, "accept-user", actor="p2").status_code, 200
        )
        self.assertEqual(
            self._post_event(
                cid,
                "invite-user",
                actor="d1",
                payload={
                    "route_id": self.route_by_principal[f"u:{self.user_ids['p3']}"]
                },
            ).status_code,
            200,
        )
        self.assertEqual(
            self._post_event(cid, "accept-user", actor="p3").status_code, 200
        )
        c = self._get_contract_doc(cid)
        self.assertEqual(c["state"], "READY")
        return gid

    def test_list_contracts_filters_by_actor_contract_and_user_state(self) -> None:
        requesting_a_cid = self._create_gherkin_contract(
            initial_state="START", actor="p1"
        )
        requesting_b_cid = self._create_gherkin_contract(
            initial_state="START", actor="p1"
        )

        definition = _gherkin_definition()
        template_id = self._create_template(
            definition, allowed_initial_states=["START"]
        )
        excluded_created = self._create_contract(
            template_id,
            self._gherkin_context_for("d1"),
            initial_state="START",
            actor="p2",
        )
        self.assertEqual(excluded_created.status_code, 201)
        excluded_cid = str(excluded_created.json()["id"])

        joined = self._post_event(excluded_cid, "request-join", actor="p2")
        self.assertEqual(joined.status_code, 200, msg=joined.text)
        self.assertTrue((joined.json() or {}).get("ok"), msg=joined.text)

        listed = self.httpx.get("/contracts/", headers=self._headers("p1"))
        self.assertEqual(listed.status_code, 200, msg=listed.text)
        payload = listed.json() or {}
        ids = {str(i.get("id")) for i in (payload.get("items") or [])}
        self.assertIn(requesting_a_cid, ids)
        self.assertIn(requesting_b_cid, ids)
        self.assertNotIn(excluded_cid, ids)

        filtered = self.httpx.get(
            "/contracts/",
            params={
                "mq": json.dumps(
                    {
                        "state": "ONBOARDING",
                        f"states.u:{self.user_ids['p1']}": "REQUESTING",
                    }
                )
            },
            headers=self._headers("p1"),
        )
        self.assertEqual(filtered.status_code, 200, msg=filtered.text)
        payload = filtered.json() or {}
        ids = [str(i.get("id")) for i in (payload.get("items") or [])]
        self.assertIn(requesting_a_cid, ids)
        self.assertIn(requesting_b_cid, ids)

    def test_list_contracts_supports_date_range_and_sort(self) -> None:
        older_cid = self._create_gherkin_contract(initial_state="START", actor="p1")
        newer_cid = self._create_gherkin_contract(initial_state="START", actor="p1")

        from schedula.utils.form.server.contracts.engine import _contracts_coll

        base = dt.datetime.now(dt.timezone.utc)
        old_ts = base - dt.timedelta(days=2)
        new_ts = base - dt.timedelta(days=1)

        with self.app.app_context():
            _contracts_coll().update_one(
                {"_id": older_cid},
                {
                    "$set": {
                        "created_at": old_ts.isoformat(),
                        "updated_at": old_ts.isoformat(),
                    }
                },
            )
            _contracts_coll().update_one(
                {"_id": newer_cid},
                {
                    "$set": {
                        "created_at": new_ts.isoformat(),
                        "updated_at": new_ts.isoformat(),
                    }
                },
            )

        listed = self.httpx.get(
            "/contracts/",
            params={"sort": "created_at", "limit": 10},
            headers=self._headers("p1"),
        )
        self.assertEqual(listed.status_code, 200, msg=listed.text)
        payload = listed.json() or {}
        ids = [str(i.get("id")) for i in (payload.get("items") or [])]
        self.assertLess(ids.index(older_cid), ids.index(newer_cid))

        ranged = self.httpx.get(
            "/contracts/",
            params={
                "mq": json.dumps(
                    {
                        "created_at": {
                            "$gte": (base - dt.timedelta(days=1, hours=12)).isoformat(),
                            "$lte": base.isoformat(),
                        }
                    }
                ),
            },
            headers=self._headers("p1"),
        )
        self.assertEqual(ranged.status_code, 200, msg=ranged.text)
        payload = ranged.json() or {}
        ids = {str(i.get("id")) for i in (payload.get("items") or [])}
        self.assertIn(newer_cid, ids)
        self.assertNotIn(older_cid, ids)

    def test_list_contracts_uses_aggregate_and_state_aggregate(self) -> None:
        global_definition = _gherkin_definition()
        for state_def in (global_definition.get("states") or {}).values():
            if isinstance(state_def, dict):
                state_def.pop("aggregate", None)
        global_definition["aggregate"] = {
            "source": "global",
            "state": {"$ctx": "doc.state"},
            "user": {"$ctx": "user"},
        }

        global_template_id = self._create_template(
            global_definition,
            allowed_initial_states=["START"],
        )

        created_global = self._create_contract(
            global_template_id,
            self._gherkin_context_for("d1"),
            initial_state="START",
            actor="p1",
        )
        self.assertEqual(created_global.status_code, 201, msg=created_global.text)
        global_cid = str(created_global.json()["id"])

        global_join = self._post_event(global_cid, "request-join", actor="p1")
        self.assertEqual(global_join.status_code, 200, msg=global_join.text)
        self.assertTrue((global_join.json() or {}).get("ok"), msg=global_join.text)

        state_definition = _gherkin_definition()
        for state_def in (state_definition.get("states") or {}).values():
            if isinstance(state_def, dict):
                state_def.pop("aggregate", None)
        state_definition["aggregate"] = {
            "source": "global",
            "state": {"$ctx": "doc.state"},
            "user": {"$ctx": "user"},
        }
        state_definition["states"]["ONBOARDING"]["aggregate"] = {
            "source": "state",
            "state": {"$ctx": "doc.state"},
            "user": {"$ctx": "user"},
        }

        state_template_id = self._create_template(
            state_definition,
            allowed_initial_states=["START"],
        )

        created_state = self._create_contract(
            state_template_id,
            self._gherkin_context_for("d1"),
            initial_state="START",
            actor="p1",
        )
        self.assertEqual(created_state.status_code, 201, msg=created_state.text)
        state_cid = str(created_state.json()["id"])

        state_join = self._post_event(state_cid, "request-join", actor="p1")
        self.assertEqual(state_join.status_code, 200, msg=state_join.text)
        self.assertTrue((state_join.json() or {}).get("ok"), msg=state_join.text)

        listed_rider = self.httpx.get("/contracts/", headers=self._headers("p1"))
        self.assertEqual(listed_rider.status_code, 200, msg=listed_rider.text)
        by_id_rider = {
            str(i.get("id")): i
            for i in (listed_rider.json() or {}).get("items") or []
            if isinstance(i, dict)
        }
        self.assertIn(global_cid, by_id_rider)
        self.assertEqual(
            (by_id_rider[global_cid].get("aggregate_state") or {}).get("source"),
            "global",
        )
        self.assertIn(state_cid, by_id_rider)
        self.assertEqual(
            (by_id_rider[state_cid].get("aggregate_state") or {}).get("source"),
            "state",
        )

    def test_start_user_initiated_sets_pending_driver_and_requesting_rider(
            self,
    ) -> None:
        cid = self._create_gherkin_contract(initial_state="START", actor="p1")
        c = self._get_contract_doc(cid)

        self.assertEqual(c["state"], "ONBOARDING")
        self.assertEqual(self._user_state(c, self.user_ids["d1"]), "PENDING_DRIVER")
        self.assertEqual(self._user_state(c, self.user_ids["p1"]), "REQUESTING")

    def test_driver_accept_start_refunds_excess_reserved_credits(self) -> None:
        p1_principal = f"u:{self.user_ids['p1']}"
        template_id = self._create_template(
            _gherkin_definition(), allowed_initial_states=["START"]
        )
        created = self._create_contract(
            template_id,
            {
                "driver_trip_id": self.route_by_principal[f"u:{self.user_ids['d1']}"],
            },
            initial_state="START",
            actor="p1",
        )
        self.assertEqual(created.status_code, 201, msg=created.text)
        cid = str(created.json()["id"])
        joined = self._post_event(
            cid,
            "request-join",
            actor="p1",
            payload={"route_id": self.route_by_principal[p1_principal]},
        )
        self.assertEqual(joined.status_code, 200, msg=joined.text)
        self.assertTrue((joined.json() or {}).get("ok"), msg=joined.text)

        route_id = self.route_by_principal[p1_principal]
        with self.app.app_context():
            items = self.app.config["MONGO_DB"]["items"]
            route_before = items.find_one({"_id": route_id}) or {}
            self.assertEqual(
                (route_before.get("data") or {}).get("reserved_credits"), 10
            )
            items.update_one({"_id": route_id}, {"$set": {"data.reserved_credits": 25}})
        p1_balance_before_accept = self._wallet_balance("p1")

        accepted = self._post_event(
            cid,
            "driver-accept-start",
            actor="d1",
            payload={"rider": p1_principal},
        )
        self.assertEqual(accepted.status_code, 200)
        self.assertTrue(accepted.json().get("ok"))

        self.assertEqual(self._wallet_balance("p1"), p1_balance_before_accept + 15)
        with self.app.app_context():
            route_after = (
                    self.app.config["MONGO_DB"]["items"].find_one({"_id": route_id}) or {}
            )
        route_data_after = route_after.get("data") or {}
        self.assertEqual(route_data_after.get("reserved_credits"), 10)
        self.assertEqual(route_data_after.get("contract_ids") or [], [cid])

    def test_start_pre_departure_gate_moves_in_progress_when_has_accepted(self) -> None:
        driver_route_id = self._create_route("d1", available_seats=10)
        self.assertEqual(
            (self._get_route("d1", driver_route_id).get("data") or {}).get("available_seats"),
            10,
        )

        p1_principal = f"u:{self.user_ids['p1']}"
        template_id = self._create_template(
            _gherkin_definition(), allowed_initial_states=["START"]
        )
        created = self._create_contract(
            template_id,
            {
                "driver_trip_id": driver_route_id,
            },
            initial_state="START",
            actor="p1",
        )
        self.assertEqual(created.status_code, 201, msg=created.text)
        cid = str(created.json()["id"])
        joined = self._post_event(
            cid,
            "request-join",
            actor="p1",
            payload={"route_id": self.route_by_principal[p1_principal]},
        )
        self.assertEqual(joined.status_code, 200, msg=joined.text)
        self.assertTrue((joined.json() or {}).get("ok"), msg=joined.text)
        created_doc = self._get_contract_doc(cid)
        self.assertEqual(
            ((created_doc.get("context") or {}).get("driver_route") or {}).get(
                "capacity"
            ),
            10,
        )
        c = self._get_contract_doc(cid)
        self.assertIsInstance(
            (c.get("context") or {}).get("pre_departure_check_id"), str
        )

        jobs = self._queue_jobs(contract_id=cid, event_name="PreDepartureGateTimed")
        self.assertEqual(len(jobs), 1)
        run_at = jobs[0].get("run_at")
        self.assertIsInstance(run_at, dt.datetime)
        assert isinstance(run_at, dt.datetime)
        if run_at.tzinfo is None:
            run_at = run_at.replace(tzinfo=dt.timezone.utc)
        self.assertLess(run_at, self.departure)

        p4_principal = f"u:{self.user_ids['p4']}"
        p4_balance_before = self._wallet_balance("p4")
        join_p4 = self._post_event(
            cid,
            "request-join",
            actor="p4",
            payload={"route_id": self.route_by_principal[p4_principal]},
        )
        self.assertEqual(join_p4.status_code, 200)
        self.assertTrue(join_p4.json().get("ok"))
        self.assertEqual(self._wallet_balance("p4"), p4_balance_before - 10)

        accepted = self._post_event(
            cid,
            "driver-accept-start",
            actor="d1",
            payload={"rider": f"u:{self.user_ids['p1']}"},
        )
        self.assertEqual(accepted.status_code, 200)
        self.assertTrue(accepted.json().get("ok"))

        self.assertTrue(self._run_worker_once(now=run_at + dt.timedelta(seconds=1)))

        c = self._get_contract_doc(cid)
        self.assertEqual(c.get("state"), "IN_PROGRESS")
        self.assertEqual(self._user_state(c, self.user_ids["p1"]), "ACCEPTED")
        self.assertEqual(self._user_state(c, self.user_ids["p4"]), "")
        self.assertEqual(self._wallet_balance("p4"), p4_balance_before)
        with self.app.app_context():
            p4_route_after = self.app.config["MONGO_DB"]["items"].find_one(
                {"_id": self.route_by_principal[p4_principal]}
            )
        p4_route_data_after = (p4_route_after or {}).get("data") or {}
        self.assertEqual(p4_route_data_after.get("reserved_credits") or 0, 0)
        self.assertNotIn(cid, p4_route_data_after.get("contract_ids") or [])
        riders_ctx = (c.get("context") or {}).get("riders") or {}
        self.assertIn(p1_principal, riders_ctx)
        self.assertNotIn(p4_principal, riders_ctx)

    def test_start_pre_departure_gate_cleans_all_requesting_riders(self) -> None:
        driver_route_id = self._create_route("d1", available_seats=10)

        p1_principal = f"u:{self.user_ids['p1']}"
        p2_principal = f"u:{self.user_ids['p2']}"
        p4_principal = f"u:{self.user_ids['p4']}"
        template_id = self._create_template(
            _gherkin_definition(), allowed_initial_states=["START"]
        )
        created = self._create_contract(
            template_id,
            {
                "driver_trip_id": driver_route_id,
            },
            initial_state="START",
            actor="p1",
        )
        self.assertEqual(created.status_code, 201, msg=created.text)
        cid = str(created.json()["id"])
        joined = self._post_event(
            cid,
            "request-join",
            actor="p1",
            payload={"route_id": self.route_by_principal[p1_principal]},
        )
        self.assertEqual(joined.status_code, 200, msg=joined.text)
        self.assertTrue((joined.json() or {}).get("ok"), msg=joined.text)

        p2_before = self._wallet_balance("p2")
        p4_before = self._wallet_balance("p4")
        join_p2 = self._post_event(
            cid,
            "request-join",
            actor="p2",
            payload={"route_id": self.route_by_principal[p2_principal]},
        )
        join_p4 = self._post_event(
            cid,
            "request-join",
            actor="p4",
            payload={"route_id": self.route_by_principal[p4_principal]},
        )
        self.assertEqual(join_p2.status_code, 200)
        self.assertEqual(join_p4.status_code, 200)
        self.assertTrue(join_p2.json().get("ok"))
        self.assertTrue(join_p4.json().get("ok"))
        self.assertEqual(self._wallet_balance("p2"), p2_before - 10)
        self.assertEqual(self._wallet_balance("p4"), p4_before - 10)

        accepted = self._post_event(
            cid,
            "driver-accept-start",
            actor="d1",
            payload={"rider": p1_principal},
        )
        self.assertEqual(accepted.status_code, 200)
        self.assertTrue(accepted.json().get("ok"))
        created_second = self._create_contract(
            template_id,
            {
                "driver_trip_id": driver_route_id,
            },
            initial_state="START",
            actor="p4",
        )
        self.assertEqual(created_second.status_code, 201, msg=created.text)
        cid_second = str(created_second.json()["id"])
        joined_second = self._post_event(
            cid_second,
            "request-join",
            actor="p4",
            payload={"route_id": self.route_by_principal[p4_principal]},
        )
        self.assertEqual(joined_second.status_code, 200, msg=joined_second.text)
        self.assertTrue((joined_second.json() or {}).get("ok"), msg=joined_second.text)
        run_at = self._queue_jobs(contract_id=cid, event_name="PreDepartureGateTimed")[
            0
        ]["run_at"]
        if run_at.tzinfo is None:
            run_at = run_at.replace(tzinfo=dt.timezone.utc)
        self.assertTrue(self._run_worker_once(now=run_at + dt.timedelta(seconds=1)))

        c = self._get_contract_doc(cid)
        self.assertEqual(c.get("state"), "IN_PROGRESS")
        self.assertEqual(self._user_state(c, self.user_ids["p1"]), "ACCEPTED")
        self.assertEqual(self._user_state(c, self.user_ids["p2"]), "")
        self.assertEqual(self._user_state(c, self.user_ids["p4"]), "")
        self.assertEqual(self._wallet_balance("p2"), p2_before)
        self.assertEqual(self._wallet_balance("p4"), p4_before - 10)

        with self.app.app_context():
            p2_route_after = self.app.config["MONGO_DB"]["items"].find_one(
                {"_id": self.route_by_principal[p2_principal]}
            )
            p4_route_after = self.app.config["MONGO_DB"]["items"].find_one(
                {"_id": self.route_by_principal[p4_principal]}
            )
        p2_route_data = (p2_route_after or {}).get("data") or {}
        p4_route_data = (p4_route_after or {}).get("data") or {}
        self.assertEqual(p2_route_data.get("reserved_credits") or 0, 0)
        self.assertEqual(p4_route_data.get("reserved_credits") or 0, 10)
        self.assertNotIn(cid, p2_route_data.get("contract_ids") or [])
        self.assertNotIn(cid, p4_route_data.get("contract_ids") or [cid_second])

        riders_ctx = (c.get("context") or {}).get("riders") or {}
        self.assertIn(p1_principal, riders_ctx)
        self.assertNotIn(p2_principal, riders_ctx)
        self.assertNotIn(p4_principal, riders_ctx)

    def test_start_pre_departure_gate_moves_cancelled_when_no_accepted(self) -> None:
        driver_route_id = self._create_route("d1")

        p1_principal = f"u:{self.user_ids['p1']}"
        template_id = self._create_template(
            _gherkin_definition(), allowed_initial_states=["START"]
        )
        created = self._create_contract(
            template_id,
            {
                "driver_trip_id": driver_route_id,
            },
            initial_state="START",
            actor="p1",
        )
        self.assertEqual(created.status_code, 201, msg=created.text)
        cid = str(created.json()["id"])
        joined = self._post_event(
            cid,
            "request-join",
            actor="p1",
            payload={"route_id": self.route_by_principal[p1_principal]},
        )
        self.assertEqual(joined.status_code, 200, msg=joined.text)
        self.assertTrue((joined.json() or {}).get("ok"), msg=joined.text)
        jobs = self._queue_jobs(contract_id=cid, event_name="PreDepartureGateTimed")
        self.assertEqual(len(jobs), 1)
        run_at = jobs[0].get("run_at")
        self.assertIsInstance(run_at, dt.datetime)
        assert isinstance(run_at, dt.datetime)
        if run_at.tzinfo is None:
            run_at = run_at.replace(tzinfo=dt.timezone.utc)

        self.assertTrue(self._run_worker_once(now=run_at + dt.timedelta(seconds=1)))

        c = self._get_contract_doc(cid)
        self.assertEqual(c.get("state"), "CANCELLED")

    def test_in_progress_on_start_generates_pickup_pins_and_notifications(self) -> None:
        driver_route_id = self._create_route("d1")
        template_id = self._create_template(
            _gherkin_definition(), allowed_initial_states=["START"]
        )
        p1_principal = f"u:{self.user_ids['p1']}"
        d1_principal = f"u:{self.user_ids['d1']}"

        created = self._create_contract(
            template_id,
            {
                "driver_trip_id": driver_route_id,
            },
            initial_state="START",
            actor="p1",
        )
        self.assertEqual(created.status_code, 201, msg=created.text)
        cid = str(created.json()["id"])
        joined = self._post_event(
            cid,
            "request-join",
            actor="p1",
            payload={"route_id": self.route_by_principal[p1_principal]},
        )
        self.assertEqual(joined.status_code, 200, msg=joined.text)
        self.assertTrue((joined.json() or {}).get("ok"), msg=joined.text)

        before_rider_pin = self._count_notifications_for(
            p1_principal, "contracts.pickup_pin_created"
        )
        before_driver_hint = self._count_notifications_for(
            d1_principal, "contracts.pickup_pin_hint"
        )

        accept = self._post_event(
            cid,
            "driver-accept-start",
            actor="d1",
            payload={"rider": p1_principal},
        )
        self.assertEqual(accept.status_code, 200)
        self.assertTrue(accept.json().get("ok"))

        run_at = self._queue_jobs(contract_id=cid, event_name="PreDepartureGateTimed")[
            0
        ]["run_at"]
        if run_at.tzinfo is None:
            run_at = run_at.replace(tzinfo=dt.timezone.utc)
        self.assertTrue(self._run_worker_once(now=run_at + dt.timedelta(seconds=1)))

        c = self._get_contract_doc(cid)
        self.assertEqual(c.get("state"), "IN_PROGRESS")
        rider = (((c.get("context") or {}).get("riders") or {}).get(p1_principal)) or {}
        pin = str(pydash.get(rider, "verification.pin") or "")
        self.assertNotEqual(len(set(pin)), 1)
        masked = str(pydash.get(rider, "verification.masked") or "")
        self.assertRegex(pin, r"^\d{6}$")
        self.assertIn("_", masked)
        self.assertRegex(pin, f"^{masked.replace('_', '.')}$")

        after_rider_pin = self._count_notifications_for(
            p1_principal, "contracts.pickup_pin_created"
        )
        after_driver_hint = self._count_notifications_for(
            d1_principal, "contracts.pickup_pin_hint"
        )
        self.assertGreaterEqual(after_rider_pin, before_rider_pin + 1)
        self.assertGreaterEqual(after_driver_hint, before_driver_hint + 1)

    def test_in_progress_confirm_pin_and_payment_timeout_completes(self) -> None:
        driver_route_id = self._create_route("d1")
        template_id = self._create_template(
            _gherkin_definition(), allowed_initial_states=["START"]
        )
        p1_principal = f"u:{self.user_ids['p1']}"
        d1_principal = f"u:{self.user_ids['d1']}"

        created = self._create_contract(
            template_id,
            {
                "driver_trip_id": driver_route_id,
            },
            initial_state="START",
            actor="p1",
        )
        self.assertEqual(created.status_code, 201, msg=created.text)
        cid = str(created.json()["id"])
        joined = self._post_event(
            cid,
            "request-join",
            actor="p1",
            payload={"route_id": self.route_by_principal[p1_principal]},
        )
        self.assertEqual(joined.status_code, 200, msg=joined.text)
        self.assertTrue((joined.json() or {}).get("ok"), msg=joined.text)

        accept = self._post_event(
            cid,
            "driver-accept-start",
            actor="d1",
            payload={"rider": p1_principal},
        )
        self.assertEqual(accept.status_code, 200)
        self.assertTrue(accept.json().get("ok"))

        pre = self._queue_jobs(contract_id=cid, event_name="PreDepartureGateTimed")[0][
            "run_at"
        ]
        if pre.tzinfo is None:
            pre = pre.replace(tzinfo=dt.timezone.utc)
        self.assertTrue(self._run_worker_once(now=pre + dt.timedelta(seconds=1)))

        c = self._get_contract_doc(cid)
        pin = self._rider_pin(c, p1_principal)
        self.assertRegex(pin, r"^\d{6}$")

        before_pickup_confirmed = self._count_notifications_for(
            p1_principal, "contracts.pickup_confirmed"
        )

        confirm = self._post_event(
            cid,
            "driver-confirm-pick-up",
            actor="d1",
            payload={"pins": [pin]},
        )
        self.assertEqual(confirm.status_code, 200)
        self.assertTrue(confirm.json().get("ok"))

        c = self._get_contract_doc(cid)
        self.assertEqual(self._user_state(c, self.user_ids["p1"]), "ONBOARD")
        after_pickup_confirmed = self._count_notifications_for(
            p1_principal, "contracts.pickup_confirmed"
        )
        self.assertGreaterEqual(after_pickup_confirmed, before_pickup_confirmed + 1)

        d1_before = self._wallet_balance("d1")
        d1_coin_before = self._wallet_balance("d1", "coin")
        before_driver_settled = self._count_notifications_for(
            d1_principal, "contracts.payment_settled_driver"
        )
        before_rider_dispute_payment = self._count_notifications_for(
            p1_principal, "contracts.payment_dispute_rider"
        )
        pay_job = self._queue_jobs(contract_id=cid, event_name="TripPaymentTimed")[0][
            "run_at"
        ]
        if pay_job.tzinfo is None:
            pay_job = pay_job.replace(tzinfo=dt.timezone.utc)
        for _ in range(20):
            self._run_worker_once(now=pay_job + dt.timedelta(seconds=1))
            if not self._queue_jobs(contract_id=cid, event_name="TripPaymentTimed"):
                break

        c = self._get_contract_doc(cid)
        self.assertEqual(c.get("state"), "COMPLETED")
        self.assertEqual(self._wallet_balance("d1"), d1_before)
        self.assertEqual(
            self._wallet_balance("d1", "coin"),
            d1_coin_before
            + float(
                (
                        ((c.get("context") or {}).get("driver_route") or {}).get(
                            "compensation"
                        )
                        or 0
                )
            ),
        )
        after_driver_settled = self._count_notifications_for(
            d1_principal, "contracts.payment_settled_driver"
        )
        after_rider_dispute_payment = self._count_notifications_for(
            p1_principal, "contracts.payment_dispute_rider"
        )
        self.assertGreaterEqual(after_driver_settled, before_driver_settled + 1)
        self.assertEqual(after_rider_dispute_payment, before_rider_dispute_payment)

    def test_in_progress_sends_pickup_reminder_20_min_before_window(self) -> None:
        driver_route_id = self._create_route("d1", available_seats=10)

        template_id = self._create_template(
            _gherkin_definition(), allowed_initial_states=["START"]
        )
        p1_principal = f"u:{self.user_ids['p1']}"

        created = self._create_contract(
            template_id,
            {
                "driver_trip_id": driver_route_id,
            },
            initial_state="START",
            actor="p1",
        )
        self.assertEqual(created.status_code, 201, msg=created.text)
        cid = str(created.json()["id"])
        joined = self._post_event(
            cid,
            "request-join",
            actor="p1",
            payload={"route_id": self.route_by_principal[p1_principal]},
        )
        self.assertEqual(joined.status_code, 200, msg=joined.text)
        self.assertTrue((joined.json() or {}).get("ok"), msg=joined.text)

        accept = self._post_event(
            cid,
            "driver-accept-start",
            actor="d1",
            payload={"rider": p1_principal},
        )
        self.assertEqual(accept.status_code, 200)
        self.assertTrue(accept.json().get("ok"))

        pre = self._queue_jobs(contract_id=cid, event_name="PreDepartureGateTimed")[0][
            "run_at"
        ]
        if pre.tzinfo is None:
            pre = pre.replace(tzinfo=dt.timezone.utc)
        self.assertTrue(self._run_worker_once(now=pre + dt.timedelta(seconds=1)))

        jobs = self._queue_jobs(contract_id=cid, event_name="RiderPickupReminderTimed")
        self.assertGreaterEqual(len(jobs), 1)
        run_at = jobs[0]["run_at"]
        if run_at.tzinfo is None:
            run_at = run_at.replace(tzinfo=dt.timezone.utc)
        before = self._count_notifications_for(
            f"u:{self.user_ids['d1']}", "contracts.trip_departure_reminder"
        )
        self.assertTrue(
            self._run_worker_once(now=run_at + dt.timedelta(seconds=1))
        )  # 'TripDepartureReminderTimed'
        after = self._count_notifications_for(
            f"u:{self.user_ids['d1']}", "contracts.trip_departure_reminder"
        )
        self.assertGreaterEqual(after, before + 1)
        before = self._count_notifications_for(
            p1_principal, "contracts.pickup_reminder"
        )
        self.assertTrue(self._run_worker_once(now=run_at + dt.timedelta(seconds=1)))
        after = self._count_notifications_for(p1_principal, "contracts.pickup_reminder")
        self.assertGreaterEqual(after, before + 1)
        latest_reminder = self._latest_notification_doc(
            p1_principal, "contracts.pickup_reminder"
        )
        self.assertIsNotNone(latest_reminder)
        assert latest_reminder is not None
        payload = latest_reminder.get("payload") or {}
        self.assertIn("pickup", payload)

    def test_in_progress_dispute_events_notify_counterpart(self) -> None:
        driver_route_id = self._create_route("d1", available_seats=10)
        template_id = self._create_template(
            _gherkin_definition(), allowed_initial_states=["START"]
        )
        p1_principal = f"u:{self.user_ids['p1']}"
        d1_principal = f"u:{self.user_ids['d1']}"

        created = self._create_contract(
            template_id,
            {
                "driver_trip_id": driver_route_id,
            },
            initial_state="START",
            actor="p1",
        )
        self.assertEqual(created.status_code, 201, msg=created.text)
        cid = str(created.json()["id"])
        joined = self._post_event(
            cid,
            "request-join",
            actor="p1",
            payload={"route_id": self.route_by_principal[p1_principal]},
        )
        self.assertEqual(joined.status_code, 200, msg=joined.text)
        self.assertTrue((joined.json() or {}).get("ok"), msg=joined.text)

        accept = self._post_event(
            cid,
            "driver-accept-start",
            actor="d1",
            payload={"rider": p1_principal},
        )
        self.assertEqual(accept.status_code, 200)
        self.assertTrue(accept.json().get("ok"))

        pre = self._queue_jobs(contract_id=cid, event_name="PreDepartureGateTimed")[0][
            "run_at"
        ]
        if pre.tzinfo is None:
            pre = pre.replace(tzinfo=dt.timezone.utc)
        self.assertTrue(self._run_worker_once(now=pre + dt.timedelta(seconds=1)))

        before_driver_dispute = self._count_notifications_for(
            d1_principal, "contracts.dispute_opened"
        )
        rider_dispute = self._post_event(cid, "driver-did-not-pick-me", actor="p1")
        self.assertEqual(rider_dispute.status_code, 200)
        self.assertTrue(rider_dispute.json().get("ok"))
        after_driver_dispute = self._count_notifications_for(
            d1_principal, "contracts.dispute_opened"
        )
        self.assertGreaterEqual(after_driver_dispute, before_driver_dispute + 1)

        before_rider_dispute = self._count_notifications_for(
            p1_principal, "contracts.dispute_opened"
        )
        driver_dispute = self._post_event(
            cid,
            "rider-not-at-pickup",
            actor="d1",
            payload={"rider": p1_principal},
        )
        self.assertEqual(driver_dispute.status_code, 200)
        self.assertTrue(driver_dispute.json().get("ok"))
        after_rider_dispute = self._count_notifications_for(
            p1_principal, "contracts.dispute_opened"
        )
        self.assertGreaterEqual(after_rider_dispute, before_rider_dispute + 1)

    def test_in_progress_driver_cancel_trip_refunds_only_non_onboard(self) -> None:
        driver_route_id = self._create_route("d1", available_seats=10)
        p1_principal = f"u:{self.user_ids['p1']}"
        p2_principal = f"u:{self.user_ids['p2']}"
        p2_route_id = self._create_route("p2", cost=10, requested_seats=1)
        template_id = self._create_template(
            _gherkin_definition(), allowed_initial_states=["START"]
        )

        created = self._create_contract(
            template_id,
            {
                "driver_trip_id": driver_route_id,
            },
            initial_state="START",
            actor="p1",
        )
        self.assertEqual(created.status_code, 201, msg=created.text)
        cid = str(created.json()["id"])
        join_p1 = self._post_event(
            cid,
            "request-join",
            actor="p1",
            payload={"route_id": self.route_by_principal[p1_principal]},
        )
        self.assertEqual(join_p1.status_code, 200)
        self.assertTrue(join_p1.json().get("ok"))

        join_p2 = self._post_event(
            cid,
            "request-join",
            actor="p2",
            payload={"route_id": p2_route_id},
        )
        self.assertEqual(join_p2.status_code, 200)
        self.assertTrue(join_p2.json().get("ok"))

        for rider in (p1_principal, p2_principal):
            accepted = self._post_event(
                cid,
                "driver-accept-start",
                actor="d1",
                payload={"rider": rider},
            )
            self.assertEqual(accepted.status_code, 200)
            self.assertTrue(accepted.json().get("ok"))

        pre = self._queue_jobs(contract_id=cid, event_name="PreDepartureGateTimed")[0][
            "run_at"
        ]
        if pre.tzinfo is None:
            pre = pre.replace(tzinfo=dt.timezone.utc)
        self.assertTrue(self._run_worker_once(now=pre + dt.timedelta(seconds=1)))

        c = self._get_contract_doc(cid)
        self.assertEqual(c.get("state"), "IN_PROGRESS")
        p1_pin = self._rider_pin(c, p1_principal)
        self.assertRegex(p1_pin, r"^\d{6}$")

        confirm = self._post_event(
            cid,
            "driver-confirm-pick-up",
            actor="d1",
            payload={"pins": [p1_pin]},
        )
        self.assertEqual(confirm.status_code, 200)
        self.assertTrue(confirm.json().get("ok"))

        c = self._get_contract_doc(cid)
        self.assertEqual(self._user_state(c, self.user_ids["p1"]), "ONBOARD")
        self.assertEqual(self._user_state(c, self.user_ids["p2"]), "ACCEPTED")

        p1_balance_before_cancel = self._wallet_balance("p1")
        p2_balance_before_cancel = self._wallet_balance("p2")
        d1_principal = f"u:{self.user_ids['d1']}"

        before_cancel_p1 = self._count_notifications_for(
            p1_principal, "contracts.user_rejected_by_driver"
        )
        before_cancel_p2 = self._count_notifications_for(
            p2_principal, "contracts.user_rejected_by_driver"
        )

        cancel_trip = self._post_event(cid, "driver-cancel-trip", actor="d1")
        self.assertEqual(cancel_trip.status_code, 200)
        self.assertTrue(cancel_trip.json().get("ok"))

        c = self._get_contract_doc(cid)
        self.assertEqual(c.get("state"), "CANCELLED")
        self.assertEqual(self._wallet_balance("p1"), p1_balance_before_cancel)
        self.assertEqual(self._wallet_balance("p2"), p2_balance_before_cancel + 11)

        after_cancel_p1 = self._count_notifications_for(
            p1_principal, "contracts.user_rejected_by_driver"
        )
        after_cancel_p2 = self._count_notifications_for(
            p2_principal, "contracts.user_rejected_by_driver"
        )
        self.assertGreaterEqual(after_cancel_p1, before_cancel_p1)
        self.assertGreaterEqual(after_cancel_p2, before_cancel_p2 + 1)

        group_id = (c.get("context") or {}).get("group_id")
        self.assertIsInstance(group_id, str)
        assert isinstance(group_id, str)
        members = self._group_member_ids(group_id)
        self.assertNotIn(p1_principal, members)
        self.assertNotIn(p2_principal, members)
        self.assertIn(d1_principal, self._group_admin_ids(group_id))

    def test_in_progress_seven_riders_mixed_outcomes_and_disputes(self) -> None:
        for rider in ("p5", "p6", "p7"):
            email = f"{rider}@gmail.com"
            with self.app.app_context():
                from schedula.utils.form.server.credits import get_wallet

                user = self._create_user(email)
                bootstrap_user(user.id)
                wallet = get_wallet(user.id)
                wallet.charge(product="credit", credits=100, session=_db.session)
                _db.session.commit()
                self.user_ids[rider] = user.id
            self.tokens[rider] = self._login_token(email)

        driver_route_id = self._create_route("d1", available_seats=10)

        rider_keys = ["p1", "p2", "p3", "p4", "p5", "p6", "p7"]
        rider_principals = {k: f"u:{self.user_ids[k]}" for k in rider_keys}
        d1_principal = f"u:{self.user_ids['d1']}"
        principal_to_actor = {v: k for k, v in rider_principals.items()}
        rider_route_ids = {
            k: self._create_route(k, cost=10, requested_seats=1) for k in rider_keys
        }

        before_balances = {k: self._wallet_balance(k) for k in ["d1", *rider_keys]}
        before_driver_coin = self._wallet_balance("d1", "coin")
        before_notifications = {
            "d1_dispute_opened": self._count_notifications_for(
                d1_principal, "contracts.dispute_opened"
            ),
            "p3_dispute_opened": self._count_notifications_for(
                rider_principals["p3"], "contracts.dispute_opened"
            ),
            "p3_payment_dispute_rider": self._count_notifications_for(
                rider_principals["p3"], "contracts.payment_dispute_rider"
            ),
            "p4_payment_dispute_rider": self._count_notifications_for(
                rider_principals["p4"], "contracts.payment_dispute_rider"
            ),
            "p5_payment_dispute_rider": self._count_notifications_for(
                rider_principals["p5"], "contracts.payment_dispute_rider"
            ),
            "p6_payment_dispute_rider": self._count_notifications_for(
                rider_principals["p6"], "contracts.payment_dispute_rider"
            ),
            "p7_payment_dispute_rider": self._count_notifications_for(
                rider_principals["p7"], "contracts.payment_dispute_rider"
            ),
            "d1_payment_settled_driver": self._count_notifications_for(
                d1_principal, "contracts.payment_settled_driver"
            ),
        }

        template_id = self._create_template(
            _gherkin_definition(), allowed_initial_states=["START"]
        )
        created = self._create_contract(
            template_id,
            {
                "driver_trip_id": driver_route_id,
            },
            initial_state="START",
            actor="p1",
        )
        self.assertEqual(created.status_code, 201, msg=created.text)
        cid = str(created.json()["id"])
        joined_p1 = self._post_event(
            cid,
            "request-join",
            actor="p1",
            payload={"route_id": rider_route_ids["p1"]},
        )
        self.assertEqual(joined_p1.status_code, 200)
        self.assertTrue(joined_p1.json().get("ok"))

        for rider in ("p2", "p3", "p4", "p5", "p6", "p7"):
            joined = self._post_event(
                cid,
                "request-join",
                actor=rider,
                payload={"route_id": rider_route_ids[rider]},
            )
            self.assertEqual(joined.status_code, 200)
            self.assertTrue(joined.json().get("ok"))

        for rider in rider_keys:
            accepted = self._post_event(
                cid,
                "driver-accept-start",
                actor="d1",
                payload={"rider": rider_principals[rider]},
            )
            self.assertEqual(accepted.status_code, 200)
            self.assertTrue(
                accepted.json().get("ok"), msg=f"{rider}: {accepted.json()}"
            )

        pre_job = self._queue_jobs(contract_id=cid, event_name="PreDepartureGateTimed")[
            0
        ]["run_at"]
        if pre_job.tzinfo is None:
            pre_job = pre_job.replace(tzinfo=dt.timezone.utc)
        for _ in range(20):
            self._run_worker_once(now=pre_job + dt.timedelta(seconds=1))
            if not self._queue_jobs(
                    contract_id=cid, event_name="PreDepartureGateTimed"
            ):
                break

        c = self._get_contract_doc(cid)
        self.assertEqual(c.get("state"), "IN_PROGRESS")

        # 1) rider cancels during IN_PROGRESS.
        cancel_p1 = self._post_event(cid, "cancel-user", actor="p1")
        self.assertEqual(cancel_p1.status_code, 200)
        self.assertTrue(cancel_p1.json().get("ok"))

        # 2) driver cancels another rider during IN_PROGRESS.
        reject_p2 = self._post_event(
            cid,
            "driver-reject-user",
            actor="d1",
            payload={"rider": rider_principals["p2"]},
        )
        self.assertEqual(reject_p2.status_code, 200)
        self.assertTrue(reject_p2.json().get("ok"))

        # 3) rider not present at pickup, driver files claim.
        claim_p3 = self._post_event(
            cid,
            "rider-not-at-pickup",
            actor="d1",
            payload={"rider": rider_principals["p3"]},
        )
        self.assertEqual(claim_p3.status_code, 200)
        self.assertTrue(claim_p3.json().get("ok"))

        # 4) rider present, driver late; rider files claim.
        log_p4 = self._post_event(
            cid,
            "log-location",
            actor="p4",
            payload={
                "locations": [
                    {
                        "lat": 45.0,
                        "lng": 9.0,
                        "at": self.now.isoformat(),
                        "accuracy": 10,
                    }
                ]
            },
        )
        self.assertEqual(log_p4.status_code, 200)
        claim_p4 = self._post_event(cid, "driver-did-not-pick-me", actor="p4")
        self.assertEqual(claim_p4.status_code, 200)
        self.assertTrue(claim_p4.json().get("ok"))

        # 5) rider picked up and PIN confirmed, then tries to claim.
        c = self._get_contract_doc(cid)
        p5_pin = self._rider_pin(c, rider_principals["p5"])
        self.assertRegex(p5_pin, r"^\d{6}$")
        confirm_p5 = self._post_event(
            cid,
            "driver-confirm-pick-up",
            actor="d1",
            payload={"pins": [p5_pin]},
        )
        self.assertEqual(confirm_p5.status_code, 200)
        self.assertTrue(confirm_p5.json().get("ok"))
        claim_p5 = self._post_event(cid, "driver-did-not-pick-me", actor="p5")
        self.assertIn(claim_p5.status_code, (403, 409))

        # 6) rider without PIN confirmation files claim.
        claim_p6 = self._post_event(cid, "driver-did-not-pick-me", actor="p6")
        self.assertEqual(claim_p6.status_code, 200)
        self.assertTrue(claim_p6.json().get("ok"))

        self.assertGreaterEqual(
            self._count_notifications_for(d1_principal, "contracts.dispute_opened"),
            before_notifications["d1_dispute_opened"] + 2,
        )
        self.assertGreaterEqual(
            self._count_notifications_for(
                rider_principals["p3"], "contracts.dispute_opened"
            ),
            before_notifications["p3_dispute_opened"] + 1,
        )

        # 7) rider does not claim and does not send location.

        pay_job = self._queue_jobs(contract_id=cid, event_name="TripPaymentTimed")[0][
            "run_at"
        ]
        if pay_job.tzinfo is None:
            pay_job = pay_job.replace(tzinfo=dt.timezone.utc)
        for _ in range(30):
            self._run_worker_once(now=pay_job + dt.timedelta(seconds=1))
            current = self._get_contract_doc(cid)
            if current.get("state") == "COMPLETED":
                break

        c = self._get_contract_doc(cid)
        self.assertEqual(c.get("state"), "COMPLETED")
        self.assertEqual(self._user_state(c, self.user_ids["p1"]), "CANCELLED")  # 7
        self.assertEqual(self._user_state(c, self.user_ids["p2"]), "REJECTED")  # -1
        self.assertEqual(self._user_state(c, self.user_ids["p3"]), "ACCEPTED")  # -1
        self.assertEqual(self._user_state(c, self.user_ids["p4"]), "ACCEPTED")  # -1
        self.assertEqual(self._user_state(c, self.user_ids["p5"]), "ONBOARD")  # 7
        self.assertEqual(self._user_state(c, self.user_ids["p6"]), "ACCEPTED")  # -1
        self.assertEqual(self._user_state(c, self.user_ids["p7"]), "ACCEPTED")  # 7

        disputed_principals = {
            principal
            for principal, rider in (
                    (c.get("context") or {}).get("riders") or {}
            ).items()
            if bool(((rider or {}).get("dispute") or {}).get("rider"))
               or bool(((rider or {}).get("dispute") or {}).get("driver"))
        }
        self.assertIn(rider_principals["p3"], disputed_principals)
        self.assertIn(rider_principals["p4"], disputed_principals)
        self.assertIn(rider_principals["p6"], disputed_principals)
        self.assertNotIn(rider_principals["p5"], disputed_principals)

        group_id = (c.get("context") or {}).get("group_id")
        self.assertIsInstance(group_id, str)
        assert isinstance(group_id, str)
        members = self._group_member_ids(group_id)
        self.assertNotIn(rider_principals["p1"], members)
        self.assertNotIn(rider_principals["p2"], members)

        self.assertIsInstance(
            ((c.get("context") or {}).get("driver_route") or {}).get("compensation"),
            (int, float),
        )

        riders_ctx = (c.get("context") or {}).get("riders") or {}
        refunded_principals = {
            principal
            for principal, rider in riders_ctx.items()
            if float((((rider or {}).get("dispute") or {}).get("refund") or 0)) > 0
        }

        for principal, rider in riders_ctx.items():
            actor = principal_to_actor[principal]
            state = self._user_state(c, self.user_ids[actor])
            if state in {"ACCEPTED", "ONBOARD"}:
                refund = float(
                    (((rider or {}).get("dispute") or {}).get("refund") or 0)
                )
                expected = float(before_balances[actor] - 10 + refund)
                self.assertEqual(self._wallet_balance(actor), expected)

        after_driver_coin = self._wallet_balance("d1", "coin")
        after_driver_credit = self._wallet_balance("d1", "credit")
        driver_compensation = float(
            (
                    ((c.get("context") or {}).get("driver_route") or {}).get("compensation")
                    or 0
            )
        )
        self.assertEqual(
            (after_driver_coin - before_driver_coin)
            + (after_driver_credit - before_balances["d1"]),
            driver_compensation,
        )

        self.assertEqual(
            self._count_notifications_for(
                d1_principal, "contracts.payment_settled_driver"
            ),
            before_notifications["d1_payment_settled_driver"] + 1,
        )
        self.assertEqual(
            self._count_notifications_for(
                rider_principals["p3"], "contracts.payment_dispute_rider"
            ),
            before_notifications["p3_payment_dispute_rider"]
            + int(rider_principals["p3"] in refunded_principals),
        )
        self.assertEqual(
            self._count_notifications_for(
                rider_principals["p4"], "contracts.payment_dispute_rider"
            ),
            before_notifications["p4_payment_dispute_rider"]
            + int(rider_principals["p4"] in refunded_principals),
        )
        self.assertEqual(
            self._count_notifications_for(
                rider_principals["p5"], "contracts.payment_dispute_rider"
            ),
            before_notifications["p5_payment_dispute_rider"],
        )
        self.assertEqual(
            self._count_notifications_for(
                rider_principals["p6"], "contracts.payment_dispute_rider"
            ),
            before_notifications["p6_payment_dispute_rider"]
            + int(rider_principals["p6"] in refunded_principals),
        )
        self.assertEqual(
            self._count_notifications_for(
                rider_principals["p7"], "contracts.payment_dispute_rider"
            ),
            before_notifications["p7_payment_dispute_rider"],
        )

        self.assertEqual(self._wallet_balance("p1"), before_balances["p1"] - 10)
        self.assertEqual(self._wallet_balance("p2"), before_balances["p2"] + 1)
        self.assertEqual(self._wallet_balance("p3"), before_balances["p3"] + 1)
        self.assertEqual(self._wallet_balance("p4"), before_balances["p4"] + 1)
        self.assertEqual(self._wallet_balance("p5"), before_balances["p5"] - 10)
        self.assertEqual(self._wallet_balance("p6"), before_balances["p6"] + 1)
        self.assertEqual(self._wallet_balance("p7"), before_balances["p7"] - 10)

    def test_start_driver_accept_start_uses_payload_riders_only(self) -> None:
        cid = self._create_gherkin_contract(initial_state="START", actor="p1")

        self.assertEqual(
            self._post_event(cid, "request-join", actor="p4").status_code, 200
        )

        self.assertEqual(
            self._post_event(
                cid,
                "driver-accept-start",
                actor="d1",
                payload={"rider": f"u:{self.user_ids['p1']}"},
            ).status_code,
            200,
        )

        c = self._get_contract_doc(cid)
        self.assertEqual(c["state"], "ONBOARDING")
        self.assertEqual(self._user_state(c, self.user_ids["d1"]), "DRIVER")
        self.assertEqual(self._user_state(c, self.user_ids["p1"]), "ACCEPTED")
        self.assertEqual(self._user_state(c, self.user_ids["p4"]), "REQUESTING")

    def test_start_driver_accept_start_sets_accepted_seats_from_rider(
            self,
    ) -> None:
        p1_principal = f"u:{self.user_ids['p1']}"
        route_id = self.route_by_principal[p1_principal]
        with self.app.app_context():
            self.app.config["MONGO_DB"]["items"].update_one(
                {"_id": route_id}, {"$set": {"data.requested_seats": 2}}
            )

        cid = self._create_gherkin_contract(initial_state="START", actor="p1")
        r = self._post_event(
            cid,
            "driver-accept-start",
            actor="d1",
            payload={"rider": p1_principal},
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json().get("ok"))

        c = self._get_contract_doc(cid)
        self.assertEqual(c["state"], "ONBOARDING")
        self.assertEqual(pydash.get(c, "context.driver_route.accepted_seats"), 2)

    def test_start_driver_accept_start_returns_ok_false_for_non_requesting_rider(
            self,
    ) -> None:
        cid = self._create_gherkin_contract(initial_state="START", actor="p1")
        p4_principal = f"u:{self.user_ids['p4']}"

        r = self._post_event(
            cid,
            "driver-accept-start",
            actor="d1",
            payload={"rider": p4_principal},
        )
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json().get("ok"))

        c = self._get_contract_doc(cid)
        self.assertEqual(c["state"], "ONBOARDING")
        self.assertEqual(self._user_state(c, self.user_ids["d1"]), "PENDING_DRIVER")
        self.assertEqual(self._user_state(c, self.user_ids["p1"]), "REQUESTING")
        self.assertEqual(self._user_state(c, self.user_ids["p4"]), "")

    def test_start_driver_reject_start_sets_rejected_and_cleans_rider(self) -> None:
        cid = self._create_gherkin_contract(initial_state="START", actor="p1")
        p1_principal = f"u:{self.user_ids['p1']}"

        rejected = self._post_event(
            cid,
            "driver-reject-start",
            actor="d1",
            payload={"rider": p1_principal},
        )
        self.assertEqual(rejected.status_code, 200)
        self.assertTrue(rejected.json().get("ok"))

        c = self._get_contract_doc(cid)
        self.assertEqual(c["state"], "ONBOARDING")
        self.assertEqual(self._user_state(c, self.user_ids["p1"]), "REJECTED")
        self.assertNotIn(p1_principal, (c.get("context") or {}).get("riders") or {})

    def test_start_driver_cancel_invite_user_clears_pending_state(self) -> None:
        cid = self._create_gherkin_contract(initial_state="START", actor="p1")
        p2_principal = f"u:{self.user_ids['p2']}"
        p2_route_id = self.route_by_principal[p2_principal]
        p2_trip = {
            "origin": {
                "at": "1970-01-01T00:00:00+00:00",
                "location": {"type": "Point", "coordinates": [45.0, 9.0]},
            },
            "destination": {
                "at": "1970-01-01T00:00:00+00:00",
                "location": {"type": "Point", "coordinates": [45.1, 9.1]},
            },
        }

        with self.app.app_context():
            self.app.config["MONGO_DB"]["contracts"].update_one(
                {"_id": cid},
                {
                    "$set": {
                        f"states.{p2_principal}": "PENDING",
                        f"context.riders.{p2_principal}": {
                            "id": p2_route_id,
                            "cost": 10,
                            "seats": 1,
                            "trip": p2_trip,
                        },
                    }
                },
            )

        cancel = self._post_event(
            cid,
            "driver-cancel-invite-user",
            actor="d1",
            payload={"rider": p2_principal},
        )
        self.assertEqual(cancel.status_code, 200)
        self.assertTrue(cancel.json().get("ok"))

        c = self._get_contract_doc(cid)
        self.assertEqual(c["state"], "ONBOARDING")
        self.assertEqual(self._user_state(c, self.user_ids["p2"]), "")

    def test_start_user_accept_invite_moves_to_confirming(self) -> None:
        cid = self._create_gherkin_contract(initial_state="START", actor="p1")
        p2_principal = f"u:{self.user_ids['p2']}"
        p2_route_id = self.route_by_principal[p2_principal]
        p2_trip = self.locations["p2"]

        with self.app.app_context():
            self.app.config["MONGO_DB"]["contracts"].update_one(
                {"_id": cid},
                {
                    "$set": {
                        f"states.{p2_principal}": "PENDING",
                        f"context.riders.{p2_principal}": {
                            "id": p2_route_id,
                            "actor_name": "p2 use",
                            "cost": 10,
                            "seats": 2,
                            "trip": p2_trip,
                        },
                    }
                },
            )

        accepted = self._post_event(cid, "accept-user", actor="p2")
        self.assertEqual(accepted.status_code, 200)
        self.assertTrue(accepted.json().get("ok"))

        c = self._get_contract_doc(cid)
        self.assertEqual(c["state"], "ONBOARDING")
        self.assertEqual(self._user_state(c, self.user_ids["p2"]), "ACCEPTED")
        self.assertEqual(pydash.get(c, "context.driver_route.accepted_seats"), 2)

    def test_start_user_accept_invite_fails_when_balance_insufficient(self) -> None:
        cid = self._create_gherkin_contract(initial_state="START", actor="p1")
        p2_principal = f"u:{self.user_ids['p2']}"
        low_credit_route_id = self._create_route("p2", cost=1000, requested_seats=1)

        invited = self._post_event(
            cid,
            "invite-user",
            actor="d1",
            payload={"route_id": low_credit_route_id},
        )
        self.assertEqual(invited.status_code, 200)
        self.assertTrue(invited.json().get("ok"))

        balance_before_accept = self._wallet_balance("p2")
        accepted = self._post_event(cid, "accept-user", actor="p2")
        self.assertEqual(accepted.status_code, 200)
        self.assertFalse(accepted.json().get("ok"))

        c = self._get_contract_doc(cid)
        self.assertEqual(c["state"], "ONBOARDING")
        self.assertEqual(self._user_state(c, self.user_ids["p2"]), "PENDING")
        self.assertEqual(self._wallet_balance("p2"), balance_before_accept)
        route_after = self._get_route("p2", low_credit_route_id)
        route_data_after = route_after.get("data") or {}
        self.assertEqual(route_data_after.get("reserved_credits") or 0, 0)
        self.assertNotIn(cid, route_data_after.get("contract_ids") or [])

    def test_start_user_accept_invite_charges_only_missing_delta(self) -> None:
        cid = self._create_gherkin_contract(initial_state="START", actor="p1")
        p2_principal = f"u:{self.user_ids['p2']}"
        route_id = self._create_route("p2", cost=10, requested_seats=1)

        with self.app.app_context():
            self.app.config["MONGO_DB"]["items"].update_one(
                {"_id": route_id},
                {
                    "$set": {
                        "data.reserved_credits": 7,
                        "data.contract_ids": [],
                    }
                },
            )

        invited = self._post_event(
            cid,
            "invite-user",
            actor="d1",
            payload={"route_id": route_id},
        )
        self.assertEqual(invited.status_code, 200)
        self.assertTrue(invited.json().get("ok"))

        balance_before_accept = self._wallet_balance("p2")
        accepted = self._post_event(cid, "accept-user", actor="p2")
        self.assertEqual(accepted.status_code, 200)
        self.assertTrue(accepted.json().get("ok"))
        self.assertEqual(self._wallet_balance("p2"), balance_before_accept - 3)

        route_after = self._get_route("p2", route_id)
        route_data_after = route_after.get("data") or {}
        self.assertEqual(route_data_after.get("reserved_credits"), 10)
        self.assertIn(cid, route_data_after.get("contract_ids") or [])

    def test_start_user_reject_invite_clears_pending_rider(self) -> None:
        cid = self._create_gherkin_contract(initial_state="START", actor="p1")
        p2_principal = f"u:{self.user_ids['p2']}"
        p2_route_id = self.route_by_principal[p2_principal]
        p2_trip = {
            "origin": {
                "at": "1970-01-01T00:00:00+00:00",
                "location": {"type": "Point", "coordinates": [45.0, 9.0]},
            },
            "destination": {
                "at": "1970-01-01T00:00:00+00:00",
                "location": {"type": "Point", "coordinates": [45.1, 9.1]},
            },
        }

        with self.app.app_context():
            self.app.config["MONGO_DB"]["contracts"].update_one(
                {"_id": cid},
                {
                    "$set": {
                        f"states.{p2_principal}": "PENDING",
                        f"context.riders.{p2_principal}": {
                            "id": p2_route_id,
                            "cost": 10,
                            "seats": 1,
                            "trip": p2_trip,
                        },
                    }
                },
            )

        rejected = self._post_event(cid, "reject-user", actor="p2")
        self.assertEqual(rejected.status_code, 200)
        self.assertTrue(rejected.json().get("ok"))

        c = self._get_contract_doc(cid)
        self.assertEqual(c["state"], "ONBOARDING")
        self.assertEqual(self._user_state(c, self.user_ids["p2"]), "REJECTED")

    def test_recruiting_driver_reject_user_marks_target_rejected(self) -> None:
        cid = self._create_gherkin_contract(initial_state="START", actor="p1")
        p1_principal = f"u:{self.user_ids['p1']}"
        p1_route_id = self.route_by_principal[p1_principal]
        p1_balance_before = self._wallet_balance("p1")
        reject_notify_before = self._count_notifications_for(
            p1_principal, "onboarding.user-rejected-by-driver"
        )
        with self.app.app_context():
            route_data_before = (
                                        self.app.config["MONGO_DB"]["items"].find_one({"_id": p1_route_id})
                                        or {}
                                ).get("data") or {}

        r = self._post_event(
            cid,
            "driver-reject-user",
            actor="d1",
            payload={"rider": p1_principal},
        )
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json().get("ok"))

        c = self._get_contract_doc(cid)
        self.assertEqual(c["state"], "ONBOARDING")
        self.assertEqual(self._user_state(c, self.user_ids["p1"]), "REQUESTING")
        self.assertIn(p1_principal, (c.get("context") or {}).get("riders") or {})
        self.assertEqual(self._wallet_balance("p1"), p1_balance_before)
        with self.app.app_context():
            route_data_after = (
                                       self.app.config["MONGO_DB"]["items"].find_one({"_id": p1_route_id}) or {}
                               ).get("data") or {}
        self.assertEqual(route_data_after, route_data_before)
        self.assertEqual(
            self._count_notifications_for(
                p1_principal, "onboarding.user-rejected-by-driver"
            ),
            reject_notify_before,
        )

    def test_onboarding_driver_reject_trip_cleans_riders_on_rejected(self) -> None:
        cid = self._create_gherkin_contract(initial_state="START", actor="p1")

        r = self._post_event(cid, "driver-reject-trip", actor="d1")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json().get("ok"))

        c = self._get_contract_doc(cid)
        self.assertEqual(c["state"], "CANCELLED")
        self.assertEqual((c.get("context") or {}).get("riders") or {}, {})

    def test_recruiting_user_cancel_ride_marks_user_cancelled(self) -> None:
        cid = self._create_gherkin_contract(initial_state="START", actor="p1")
        p1_principal = f"u:{self.user_ids['p1']}"
        p1_route_id = self.route_by_principal[p1_principal]
        p1_balance_before = self._wallet_balance("p1")
        driver_principal = f"u:{self.user_ids['d1']}"
        user_cancelled_before = self._count_notifications_for(
            driver_principal, "onboarding.user-cancelled"
        )
        with self.app.app_context():
            route_data_before = (
                                        self.app.config["MONGO_DB"]["items"].find_one({"_id": p1_route_id})
                                        or {}
                                ).get("data") or {}

        r = self._post_event(cid, "cancel-user", actor="p1")
        self.assertIn(r.status_code, (403, 409))

        c = self._get_contract_doc(cid)
        self.assertEqual(c["state"], "ONBOARDING")
        self.assertEqual(self._user_state(c, self.user_ids["p1"]), "REQUESTING")
        self.assertEqual(self._wallet_balance("p1"), p1_balance_before)
        with self.app.app_context():
            route_data_after = (
                                       self.app.config["MONGO_DB"]["items"].find_one({"_id": p1_route_id})
                                       or {}
                               ).get("data") or {}
        self.assertEqual(route_data_after, route_data_before)
        self.assertEqual(
            self._count_notifications_for(driver_principal, "onboarding.user-cancelled"),
            user_cancelled_before,
        )

    def test_start_request_join_adds_requesting_user_when_capacity_and_credits_ok(
            self,
    ) -> None:
        driver_principal = f"u:{self.user_ids['d1']}"
        p4_principal = f"u:{self.user_ids['p4']}"
        p4_route_id = self.route_by_principal[p4_principal]
        p4_balance_before = self._wallet_balance("p4")
        before = self._count_notifications_for(
            driver_principal, "onboarding.driver-new-join-request"
        )

        cid = self._create_gherkin_contract(initial_state="START", actor="p4")

        c = self._get_contract_doc(cid)
        self.assertEqual(c["state"], "ONBOARDING")
        self.assertEqual(self._user_state(c, self.user_ids["p4"]), "REQUESTING")
        self.assertEqual(self._wallet_balance("p4"), p4_balance_before - 10)
        with self.app.app_context():
            p4_route_data = self.app.config["MONGO_DB"]["items"].find_one({"_id": p4_route_id}) or {}
            p4_route_data = p4_route_data.get("data") or {}

        self.assertEqual(p4_route_data.get("reserved_credits"), 10)
        self.assertIn(cid, p4_route_data.get("contract_ids") or [])

        after = self._count_notifications_for(
            driver_principal, "onboarding.driver-new-join-request"
        )
        self.assertEqual(after, before + 1)

    def test_start_request_join_denies_when_user_has_insufficient_credits(self) -> None:
        cid = self._create_gherkin_contract(initial_state="START")
        p4_principal = f"u:{self.user_ids['p4']}"
        route_id = self.route_by_principal[p4_principal]

        with self.app.app_context():
            self.app.config["MONGO_DB"]["items"].update_one(
                {"_id": route_id}, {"$set": {"data.cost": 1000}}
            )

        r = self._post_event(cid, "request-join", actor="p4")
        self.assertEqual(r.status_code, 200)

        c = self._get_contract_doc(cid)
        self.assertEqual(self._user_state(c, self.user_ids["p4"]), "")

    def test_start_cancel_join_request_last_user_re_notifies_driver(self) -> None:
        driver_principal = f"u:{self.user_ids['d1']}"
        before = self._count_notifications_for(
            driver_principal, "onboarding.driver-new-join-request"
        )
        before_no = self._count_notifications_for(
            driver_principal, "onboarding.no-more-ride-requests"
        )

        cid = self._create_gherkin_contract(initial_state="START", actor="p1")
        after_create = self._count_notifications_for(
            driver_principal, "onboarding.driver-new-join-request"
        )
        self.assertEqual(after_create, before + 1)

        self.assertEqual(
            self._post_event(cid, "cancel-join-request", actor="p1").status_code, 200
        )

        c = self._get_contract_doc(cid)
        self.assertEqual(c["state"], "ONBOARDING")
        self.assertIn((c.get("context") or {}).get("riders_map"), ({}, None))

        after_cancel = self._count_notifications_for(
            driver_principal, "onboarding.no-more-ride-requests"
        )
        self.assertEqual(after_cancel, before_no + 1)

    def test_onboarding_full_journey_all_apis_with_negatives_and_pruning(self) -> None:
        definition = _gherkin_definition()
        template_id = self._create_template(
            definition,
            allowed_initial_states=["START"],
        )

        p1_principal = f"u:{self.user_ids['p1']}"
        p2_principal = f"u:{self.user_ids['p2']}"
        p4_principal = f"u:{self.user_ids['p4']}"
        p2_route_id = self._create_route("p2", cost=10, requested_seats=1)
        p2_route_low_credit = self._create_route("p2", cost=1000, requested_seats=1)
        p2_route_over_seats = self._create_route("p2", cost=10, requested_seats=9)
        p3_route_id = self._create_route("p3", cost=10, requested_seats=1)
        p4_route_id = self._create_route("p4", cost=10, requested_seats=1)
        p4_route_low_credit = self._create_route("p4", cost=1000, requested_seats=1)
        p4_route_over_seats = self._create_route("p4", cost=10, requested_seats=9)
        d1_route_id = self._create_route("d1")
        extra_p2_balance_before = 10
        with self.app.app_context():
            self.app.config["MONGO_DB"]["items"].update_one(
                {"_id": p2_route_id},
                {
                    "$inc": {
                        "data.reserved_credits": extra_p2_balance_before,
                    }
                },
            )

        p2_balance_before = self._wallet_balance("p2")
        p3_balance_before = self._wallet_balance("p3")
        p4_balance_before = self._wallet_balance("p4")

        d1_principal = f"u:{self.user_ids['d1']}"
        p2_invite_before = self._count_notifications_for(
            p2_principal, "onboarding.user-invited"
        )
        p3_invite_before = self._count_notifications_for(
            f"u:{self.user_ids['p3']}", "onboarding.user-invited"
        )
        p3_cancel_invite_before = self._count_notifications_for(
            f"u:{self.user_ids['p3']}", "onboarding.driver-cancelled-invite"
        )
        d1_join_requested_before = self._count_notifications_for(
            d1_principal, "onboarding.driver-new-join-request"
        )
        d1_user_rejected_before = self._count_notifications_for(
            d1_principal, "onboarding.user-rejected"
        )
        d1_user_cancelled_before = self._count_notifications_for(
            d1_principal, "onboarding.user-cancelled"
        )
        p2_driver_rejected_before = self._count_notifications_for(
            p2_principal, "onboarding.user-rejected-by-driver"
        )

        created_a = self._create_contract(
            template_id,
            self._gherkin_context_for("d1"),
            initial_state="START",
            actor="p1",
        )
        self.assertEqual(created_a.status_code, 201, msg=created_a.text)
        contract_a = str(created_a.json()["id"])

        joined = self._post_event(contract_a, "request-join", actor="p1")
        self.assertEqual(joined.status_code, 200, msg=joined.text)
        self.assertTrue((joined.json() or {}).get("ok"), msg=joined.text)

        contract_a_doc = self._get_contract_doc(contract_a)
        self.assertEqual(contract_a_doc["state"], "ONBOARDING")
        self.assertEqual(
            self._user_state(contract_a_doc, self.user_ids["d1"]), "PENDING_DRIVER"
        )
        self.assertEqual(
            self._user_state(contract_a_doc, self.user_ids["p1"]), "REQUESTING"
        )

        # Input and lookup validation errors.
        missing_route_id = str(uuid.uuid4())
        missing_join = self._post_event(
            contract_a,
            "request-join",
            actor="p4",
            payload={"route_id": missing_route_id},
        )
        self.assertEqual(missing_join.status_code, 404)
        self.assertEqual(self._wallet_balance("p4"), p4_balance_before)

        missing_invite = self._post_event(
            contract_a,
            "invite-user",
            actor="d1",
            payload={"route_id": missing_route_id},
        )
        self.assertEqual(missing_invite.status_code, 404)
        self.assertEqual(self._wallet_balance("p2"), p2_balance_before)

        missing_cancel_invite = self._post_event(
            contract_a,
            "driver-cancel-invite-user",
            actor="d1",
            payload={"rider": "u:missing"},
        )
        self.assertEqual(missing_cancel_invite.status_code, 200)
        self.assertFalse(missing_cancel_invite.json().get("ok"))

        bad_invite_payload = self.httpx.post(
            f"/contracts/{contract_a}/event/invite-user",
            json={},
            headers=self._headers("d1"),
        )
        self.assertIn(bad_invite_payload.status_code, (409, 422))

        bad_cancel_invite_payload = self.httpx.post(
            f"/contracts/{contract_a}/event/driver-cancel-invite-user",
            json={},
            headers=self._headers("d1"),
        )
        self.assertIn(bad_cancel_invite_payload.status_code, (409, 422))

        bad_reject_payload = self.httpx.post(
            f"/contracts/{contract_a}/event/driver-reject-user",
            json={"payload": {"rider": "bad-principal"}},
            headers=self._headers("d1"),
        )
        self.assertIn(bad_reject_payload.status_code, (409, 422))

        # State-gated errors for rider actions.
        non_pending_accept = self._post_event(contract_a, "accept-user", actor="p4")
        self.assertIn(non_pending_accept.status_code, (403, 409))
        non_pending_reject = self._post_event(contract_a, "reject-user", actor="p4")
        self.assertIn(non_pending_reject.status_code, (403, 409))

        # Negative: accept-start with non-requesting rider.
        bad_accept = self._post_event(
            contract_a,
            "driver-accept-start",
            actor="d1",
            payload={"rider": p4_principal},
        )
        self.assertEqual(bad_accept.status_code, 200)
        self.assertFalse(bad_accept.json().get("ok"))

        # Negative request-join: driver cannot request join.
        driver_join = self._post_event(
            contract_a,
            "request-join",
            actor="d1",
            payload={"route_id": d1_route_id},
        )
        self.assertEqual(driver_join.status_code, 403)

        # request-join / cancel-join-request exercised on a dedicated contract.
        created_req = self._create_contract(
            template_id,
            self._gherkin_context_for("d1"),
            initial_state="START",
            actor="p1",
        )
        self.assertEqual(created_req.status_code, 201, msg=created_req.text)
        contract_req = str(created_req.json()["id"])

        joined = self._post_event(contract_req, "request-join", actor="p1")
        self.assertEqual(joined.status_code, 200, msg=joined.text)
        self.assertTrue((joined.json() or {}).get("ok"), msg=joined.text)

        good_join = self._post_event(
            contract_req,
            "request-join",
            actor="p4",
            payload={"route_id": p4_route_id},
        )
        self.assertEqual(good_join.status_code, 200)
        self.assertTrue(good_join.json().get("ok"))
        self.assertEqual(self._wallet_balance("p4"), p4_balance_before - 10)
        p4_route_after_join = self._get_route("p4", p4_route_id)
        p4_route_data_after_join = p4_route_after_join.get("data") or {}
        self.assertEqual(p4_route_data_after_join.get("reserved_credits"), 10)
        self.assertIn(contract_req, p4_route_data_after_join.get("contract_ids") or [])

        join_p3 = self._post_event(contract_req, "request-join", actor="p3")
        self.assertEqual(join_p3.status_code, 200)
        self.assertTrue(join_p3.json().get("ok"))
        cancel_p3 = self._post_event(contract_req, "cancel-join-request", actor="p3")
        self.assertEqual(cancel_p3.status_code, 200)
        self.assertTrue(cancel_p3.json().get("ok"))
        p3_route_after_cancel_join = self._get_route("p3", p3_route_id)
        p3_route_data_after_cancel_join = p3_route_after_cancel_join.get("data") or {}
        self.assertEqual(
            p3_route_data_after_cancel_join.get("reserved_credits") or 0, 0
        )
        self.assertEqual(p3_route_data_after_cancel_join.get("contract_ids") or [], [])
        self.assertEqual(
            self._count_notifications_for(
                d1_principal, "onboarding.driver-new-join-request"
            ),
            d1_join_requested_before + 4,
        )

        # invite-user negatives.
        bad_invite_self = self._post_event(
            contract_a,
            "invite-user",
            actor="d1",
            payload={"route_id": d1_route_id},
        )
        self.assertEqual(bad_invite_self.status_code, 200)
        self.assertFalse(bad_invite_self.json().get("ok"))

        bad_invite_low_credits = self._post_event(
            contract_a,
            "invite-user",
            actor="d1",
            payload={"route_id": p2_route_low_credit},
        )
        self.assertEqual(bad_invite_low_credits.status_code, 200)
        self.assertTrue(bad_invite_low_credits.json().get("ok"))
        self.assertEqual(self._wallet_balance("p2"), p2_balance_before)
        clear_low_credit_invite = self._post_event(
            contract_a,
            "driver-cancel-invite-user",
            actor="d1",
            payload={"rider": p2_principal},
        )
        self.assertEqual(clear_low_credit_invite.status_code, 200)
        self.assertTrue(clear_low_credit_invite.json().get("ok"))

        bad_invite_over_seats = self._post_event(
            contract_a,
            "invite-user",
            actor="d1",
            payload={"route_id": p2_route_over_seats},
        )
        self.assertEqual(bad_invite_over_seats.status_code, 200)
        self.assertFalse(bad_invite_over_seats.json().get("ok"))
        self.assertEqual(self._wallet_balance("p2"), p2_balance_before)

        # invite-user positives + driver-cancel-invite-user + reject-user.
        invite_p2 = self._post_event(
            contract_a,
            "invite-user",
            actor="d1",
            payload={"route_id": p2_route_id},
        )
        self.assertEqual(invite_p2.status_code, 200)
        self.assertTrue(invite_p2.json().get("ok"))
        self.assertEqual(self._wallet_balance("p2"), p2_balance_before)
        p2_route_after_invite = self._get_route("p2", p2_route_id)
        p2_route_data_after_invite = p2_route_after_invite.get("data") or {}
        self.assertEqual(p2_route_data_after_invite.get("reserved_credits") or 0, 10)
        self.assertNotIn(
            contract_a, p2_route_data_after_invite.get("contract_ids") or []
        )
        self.assertEqual(
            self._count_notifications_for(p2_principal, "onboarding.user-invited"),
            p2_invite_before + 2,
        )

        invite_p3 = self._post_event(
            contract_a,
            "invite-user",
            actor="d1",
            payload={"route_id": p3_route_id},
        )
        self.assertEqual(invite_p3.status_code, 200)
        self.assertTrue(invite_p3.json().get("ok"))
        self.assertEqual(self._wallet_balance("p3"), p3_balance_before)
        self.assertEqual(
            self._count_notifications_for(
                f"u:{self.user_ids['p3']}", "onboarding.user-invited"
            ),
            p3_invite_before + 1,
        )

        cancel_invite_p3 = self._post_event(
            contract_a,
            "driver-cancel-invite-user",
            actor="d1",
            payload={"rider": f"u:{self.user_ids['p3']}"},
        )
        self.assertEqual(cancel_invite_p3.status_code, 200)
        self.assertTrue(cancel_invite_p3.json().get("ok"))
        self.assertEqual(self._wallet_balance("p3"), p3_balance_before)
        p3_route_after_cancel_invite = self._get_route("p3", p3_route_id)
        p3_route_data_after_cancel_invite = (
                p3_route_after_cancel_invite.get("data") or {}
        )
        self.assertEqual(
            p3_route_data_after_cancel_invite.get("reserved_credits") or 0, 0
        )
        self.assertEqual(
            p3_route_data_after_cancel_invite.get("contract_ids") or [], []
        )
        self.assertEqual(
            self._count_notifications_for(
                f"u:{self.user_ids['p3']}", "onboarding.driver-cancelled-invite"
            ),
            p3_cancel_invite_before + 1,
        )

        invite_p3_again = self._post_event(
            contract_a,
            "invite-user",
            actor="d1",
            payload={"route_id": p3_route_id},
        )
        self.assertEqual(invite_p3_again.status_code, 200)
        self.assertTrue(invite_p3_again.json().get("ok"))
        self.assertEqual(self._wallet_balance("p3"), p3_balance_before)
        self.assertEqual(
            self._count_notifications_for(
                f"u:{self.user_ids['p3']}", "onboarding.user-invited"
            ),
            p3_invite_before + 2,
        )
        reject_invite_p3 = self._post_event(contract_a, "reject-user", actor="p3")
        self.assertEqual(reject_invite_p3.status_code, 200)
        self.assertTrue(reject_invite_p3.json().get("ok"))
        self.assertEqual(self._wallet_balance("p3"), p3_balance_before)
        p3_route_after_reject = self._get_route("p3", p3_route_id)
        p3_route_data_after_reject = p3_route_after_reject.get("data") or {}
        self.assertEqual(p3_route_data_after_reject.get("contract_ids") or [], [])
        self.assertEqual(
            self._count_notifications_for(d1_principal, "onboarding.user-rejected"),
            d1_user_rejected_before + 1,
        )

        # Competitor contract used to verify pruning after user accept on contract A.
        created_c = self._create_contract(
            template_id,
            {
                "driver_trip_id": self.route_by_principal[f"u:{self.user_ids['p3']}"],
            },
            initial_state="START",
            actor="p2",
        )
        self.assertEqual(created_c.status_code, 201, msg=created_c.text)
        contract_c = str(created_c.json()["id"])
        joined_c = self._post_event(
            contract_c,
            "request-join",
            actor="p2",
            payload={"route_id": p2_route_id},
        )
        self.assertEqual(joined_c.status_code, 200, msg=joined_c.text)
        self.assertTrue((joined_c.json() or {}).get("ok"), msg=joined_c.text)

        before_rider_unavailable_c = self._count_notifications_for(
            f"u:{self.user_ids['p3']}", "contracts.rider_unavailable"
        )
        accept_invite_p2 = self._post_event(contract_a, "accept-user", actor="p2")
        self.assertEqual(accept_invite_p2.status_code, 200)
        self.assertTrue(accept_invite_p2.json().get("ok"))
        p2_route_after_accept = self._get_route("p2", p2_route_id)
        p2_route_data_after_accept = p2_route_after_accept.get("data") or {}
        self.assertEqual(p2_route_data_after_accept.get("reserved_credits"), 10)
        self.assertEqual(
            p2_route_data_after_accept.get("contract_ids") or [],
            [contract_a],
        )

        contract_a_after_accept = self._get_contract_doc(contract_a)
        group_id = (contract_a_after_accept.get("context") or {}).get("group_id")
        self.assertIsInstance(group_id, str)
        assert isinstance(group_id, str)
        chat_members = self._group_member_ids(group_id)
        self.assertIn(f"u:{self.user_ids['d1']}", chat_members)
        self.assertIn(p2_principal, chat_members)
        self.assertIn(f"u:{self.user_ids['d1']}", self._group_admin_ids(group_id))

        rider_message = self.httpx.post(
            "/item/message",
            json={
                "data": {
                    "text": "rider ack",
                }
            },
            headers=self._headers("owner-1"),
        )
        self.assertEqual(rider_message.status_code, 201, msg=rider_message.text)
        other_rider_message = self.httpx.post(
            "/item/message",
            json={
                "data": {
                    "text": "other rider msg",
                }
            },
            headers=self._headers("owner-1"),
        )
        self.assertEqual(
            other_rider_message.status_code, 201, msg=other_rider_message.text
        )

        contract_c_doc = self._get_contract_doc(contract_c)
        self.assertEqual(self._user_state(contract_c_doc, self.user_ids["p2"]), "")
        self.assertNotIn(
            p2_principal, ((contract_c_doc.get("context") or {}).get("riders") or {})
        )
        after_rider_unavailable_c = self._count_notifications_for(
            f"u:{self.user_ids['p3']}", "contracts.rider_unavailable"
        )
        self.assertGreaterEqual(after_rider_unavailable_c, before_rider_unavailable_c)
        self._post_event(
            contract_req,
            "request-join",
            actor="p2",
            payload={"route_id": p2_route_id},
        )
        # Driver remove accepted user and rider cancel flows.
        p2_balance_before_driver_reject = self._wallet_balance("p2")
        driver_remove_p2 = self._post_event(
            contract_a,
            "driver-reject-user",
            actor="d1",
            payload={"rider": p2_principal},
        )
        self.assertEqual(driver_remove_p2.status_code, 200)
        self.assertTrue(driver_remove_p2.json().get("ok"))
        self.assertEqual(self._wallet_balance("p2"), p2_balance_before_driver_reject)

        driver_remove_p2 = self._post_event(
            contract_req,
            "driver-reject-start",
            actor="d1",
            payload={"rider": p2_principal},
        )
        self.assertEqual(driver_remove_p2.status_code, 200)
        self.assertTrue(driver_remove_p2.json().get("ok"))
        self.assertEqual(
            self._wallet_balance("p2"), p2_balance_before + extra_p2_balance_before
        )

        p2_route_after_driver_reject = self._get_route("p2", p2_route_id)
        p2_route_data_after_driver_reject = (
                p2_route_after_driver_reject.get("data") or {}
        )
        self.assertEqual(
            p2_route_data_after_driver_reject.get("contract_ids") or [], []
        )
        self.assertEqual(p2_route_data_after_driver_reject.get("reserved_credits"), 0)
        self.assertEqual(
            self._count_notifications_for(
                p2_principal, "onboarding.user-rejected-by-driver"
            ),
            p2_driver_rejected_before + 1,
        )
        chat_members = self._group_member_ids(group_id)
        self.assertEqual(chat_members, {f"u:{self.user_ids['d1']}"})
        self.assertIn(f"u:{self.user_ids['d1']}", self._group_admin_ids(group_id))

        rider_cancel_p1 = self._post_event(contract_a, "cancel-user", actor="p1")
        self.assertIn(rider_cancel_p1.status_code, (403, 409))
        self.assertEqual(
            self._count_notifications_for(d1_principal, "onboarding.user-cancelled"),
            d1_user_cancelled_before,
        )
        chat_members = self._group_member_ids(group_id)
        self.assertEqual(chat_members, {f"u:{self.user_ids['d1']}"})
        self.assertIn(f"u:{self.user_ids['d1']}", self._group_admin_ids(group_id))

        contract_a_doc = self._get_contract_doc(contract_a)
        self.assertEqual(
            self._user_state(contract_a_doc, self.user_ids["p2"]), "REJECTED"
        )
        self.assertNotIn(
            p2_principal,
            ((contract_a_doc.get("context") or {}).get("riders") or {}),
        )
        self.assertEqual(
            self._user_state(contract_a_doc, self.user_ids["p1"]), "REQUESTING"
        )

        # Full positive journey through IN_PROGRESS up to COMPLETED.

        p4_complete_route_id = self._create_route("p4", cost=10, requested_seats=1)
        p4_complete_principal = f"u:{self.user_ids['p4']}"
        d1_route_complete_id = self._create_route("d1")
        created_completed = self._create_contract(
            template_id,
            {
                "driver_trip_id": d1_route_complete_id,
            },
            initial_state="START",
            actor="p4",
        )
        self.assertEqual(created_completed.status_code, 201, msg=created_completed.text)
        contract_completed = str(created_completed.json()["id"])
        joined_completed = self._post_event(
            contract_completed,
            "request-join",
            actor="p4",
            payload={"route_id": p4_complete_route_id},
        )
        self.assertEqual(joined_completed.status_code, 200, msg=joined_completed.text)
        self.assertTrue(
            (joined_completed.json() or {}).get("ok"), msg=joined_completed.text
        )
        p4_balance_after_created_completed = self._wallet_balance("p4")

        accept_start_completed = self._post_event(
            contract_completed,
            "driver-accept-start",
            actor="d1",
            payload={"rider": p4_complete_principal},
        )
        self.assertEqual(accept_start_completed.status_code, 200)
        self.assertTrue(accept_start_completed.json().get("ok"))

        completed_onboarding_doc = self._get_contract_doc(contract_completed)
        self.assertEqual(completed_onboarding_doc.get("state"), "ONBOARDING")
        accepted_count = sum(
            1
            for s in (completed_onboarding_doc.get("states") or {}).values()
            if s == "ACCEPTED"
        )
        self.assertGreaterEqual(accepted_count, 1)

        pre_completed = self._queue_jobs(
            contract_id=contract_completed, event_name="PreDepartureGateTimed"
        )[0]["run_at"]
        if pre_completed.tzinfo is None:
            pre_completed = pre_completed.replace(tzinfo=dt.timezone.utc)
        for _ in range(20):
            self._run_worker_once(now=pre_completed + dt.timedelta(seconds=1))
            if not self._queue_jobs(
                    contract_id=contract_completed, event_name="PreDepartureGateTimed"
            ):
                break

        completed_doc = self._get_contract_doc(contract_completed)
        self.assertEqual(completed_doc.get("state"), "IN_PROGRESS")

        rider_dispute = self._post_event(
            contract_completed,
            "driver-did-not-pick-me",
            actor="p4",
        )
        self.assertEqual(rider_dispute.status_code, 200)
        self.assertTrue(rider_dispute.json().get("ok"))
        completed_doc = self._get_contract_doc(contract_completed)
        riders_ctx = (completed_doc.get("context") or {}).get("riders") or {}
        disputed = bool(
            ((riders_ctx.get(p4_complete_principal) or {}).get("dispute") or {}).get(
                "rider"
            )
        ) or bool(
            ((riders_ctx.get(p4_complete_principal) or {}).get("dispute") or {}).get(
                "driver"
            )
        )
        self.assertTrue(disputed)
        d1_balance_before_completed_payment = self._wallet_balance("d1")
        d1_coin_before_completed_payment = self._wallet_balance("d1", "coin")

        pay_completed = self._queue_jobs(
            contract_id=contract_completed, event_name="TripPaymentTimed"
        )[0]["run_at"]
        if pay_completed.tzinfo is None:
            pay_completed = pay_completed.replace(tzinfo=dt.timezone.utc)
        for _ in range(20):
            self._run_worker_once(now=pay_completed + dt.timedelta(seconds=1))
            current = self._get_contract_doc(contract_completed)
            if current.get("state") == "COMPLETED":
                break

        completed_doc = self._get_contract_doc(contract_completed)
        self.assertEqual(completed_doc.get("state"), "COMPLETED")
        completed_compensation = float(
            (
                    ((completed_doc.get("context") or {}).get("driver_route") or {}).get(
                        "compensation"
                    )
                    or 0
            )
        )
        self.assertEqual(
            round(
                (self._wallet_balance("d1") - d1_balance_before_completed_payment)
                + (
                        self._wallet_balance("d1", "coin")
                        - d1_coin_before_completed_payment
                ),
                6,
            ),
            round(completed_compensation, 6),
        )
        self.assertEqual(
            self._wallet_balance("p4"), p4_balance_after_created_completed + 21
        )

        # ONBOARDING terminal events tested in same journey on dedicated contracts.
        created_ready = self._create_contract(
            template_id,
            self._gherkin_context_for("d1"),
            initial_state="START",
            actor="p4",
        )
        self.assertEqual(created_ready.status_code, 201, msg=created_ready.text)
        contract_ready = str(created_ready.json()["id"])

        joined = self._post_event(contract_ready, "request-join", actor="p4")
        self.assertEqual(joined.status_code, 200, msg=joined.text)
        self.assertTrue((joined.json() or {}).get("ok"), msg=joined.text)

        set_ready = self._post_event(contract_ready, "set-ready", actor="d1")
        self.assertIn(set_ready.status_code, (200, 409))
        if set_ready.status_code == 200:
            self.assertTrue(set_ready.json().get("ok"))
            ready_doc = self._get_contract_doc(contract_ready)
            self.assertIn(ready_doc["state"], ("READY", "IN_PROGRESS"))

        created_cancel_trip = self._create_contract(
            template_id,
            self._gherkin_context_for("d1"),
            initial_state="START",
            actor="p4",
        )
        self.assertEqual(
            created_cancel_trip.status_code, 201, msg=created_cancel_trip.text
        )
        contract_cancel_trip = str(created_cancel_trip.json()["id"])

        joined = self._post_event(contract_cancel_trip, "request-join", actor="p4")
        self.assertEqual(joined.status_code, 200, msg=joined.text)
        self.assertTrue((joined.json() or {}).get("ok"), msg=joined.text)

        cancel_trip = self._post_event(
            contract_cancel_trip,
            "driver-reject-trip",
            actor="d1",
        )
        self.assertEqual(cancel_trip.status_code, 200)
        self.assertTrue(cancel_trip.json().get("ok"))
        cancelled_trip_doc = self._get_contract_doc(contract_cancel_trip)
        self.assertEqual(cancelled_trip_doc["state"], "CANCELLED")

    def test_sync_keeps_driver_admin_across_membership_changes(self) -> None:
        cid = self._create_gherkin_contract(initial_state="START", actor="p1")
        d1_principal = f"u:{self.user_ids['d1']}"

        p2_route_id = self._create_route("p2", cost=10, requested_seats=1)
        invite_p2 = self._post_event(
            cid,
            "invite-user",
            actor="d1",
            payload={"route_id": p2_route_id},
        )
        self.assertEqual(invite_p2.status_code, 200)
        self.assertTrue(invite_p2.json().get("ok"))

        accept_p2 = self._post_event(cid, "accept-user", actor="p2")
        self.assertEqual(accept_p2.status_code, 200)
        self.assertTrue(accept_p2.json().get("ok"))

        c = self._get_contract_doc(cid)
        gid = (c.get("context") or {}).get("group_id")
        self.assertIsInstance(gid, str)
        assert isinstance(gid, str)
        self.assertIn(d1_principal, self._group_admin_ids(gid))

        p3_route_id = self._create_route("p3", cost=10, requested_seats=1)
        invite_p3 = self._post_event(
            cid,
            "invite-user",
            actor="d1",
            payload={"route_id": p3_route_id},
        )
        self.assertEqual(invite_p3.status_code, 200)
        self.assertTrue(invite_p3.json().get("ok"))
        accept_p3 = self._post_event(cid, "accept-user", actor="p3")
        self.assertEqual(accept_p3.status_code, 200)
        self.assertTrue(accept_p3.json().get("ok"))
        self.assertIn(d1_principal, self._group_admin_ids(gid))

        reject_p2 = self._post_event(
            cid,
            "driver-reject-user",
            actor="d1",
            payload={"rider": f"u:{self.user_ids['p2']}"},
        )
        self.assertEqual(reject_p2.status_code, 200)
        self.assertTrue(reject_p2.json().get("ok"))
        self.assertIn(d1_principal, self._group_admin_ids(gid))

        cancel_p1 = self._post_event(cid, "cancel-user", actor="p1")
        self.assertIn(cancel_p1.status_code, (403, 409))
        self.assertIn(d1_principal, self._group_admin_ids(gid))

    def test_onboarding_driver_reject_user_no_refund_when_route_still_linked(
            self,
    ) -> None:
        cid = self._create_gherkin_contract(initial_state="START", actor="p1")
        p2_principal = f"u:{self.user_ids['p2']}"
        p2_route_id = self._create_route("p2", cost=10, requested_seats=1)

        invited = self._post_event(
            cid,
            "invite-user",
            actor="d1",
            payload={"route_id": p2_route_id},
        )
        self.assertEqual(invited.status_code, 200)
        self.assertTrue(invited.json().get("ok"))

        accepted = self._post_event(cid, "accept-user", actor="p2")
        self.assertEqual(accepted.status_code, 200)
        self.assertTrue(accepted.json().get("ok"))

        balance_before_reject = self._wallet_balance("p2")
        with self.app.app_context():
            self.app.config["MONGO_DB"]["items"].update_one(
                {"_id": p2_route_id},
                {
                    "$set": {
                        "data.contract_ids": [cid, "other-contract"],
                        "data.reserved_credits": 10,
                    }
                },
            )

        rejected = self._post_event(
            cid,
            "driver-reject-user",
            actor="d1",
            payload={"rider": p2_principal},
        )
        self.assertEqual(rejected.status_code, 200)
        self.assertTrue(rejected.json().get("ok"))
        self.assertEqual(self._wallet_balance("p2"), balance_before_reject)

        with self.app.app_context():
            route_after = (
                    self.app.config["MONGO_DB"]["items"].find_one({"_id": p2_route_id})
                    or {}
            )
        route_data_after = route_after.get("data") or {}
        self.assertEqual(route_data_after.get("reserved_credits"), 10)
        self.assertEqual(route_data_after.get("contract_ids") or [], ["other-contract"])

        contract_doc = self._get_contract_doc(cid)
        self.assertEqual(
            self._user_state(contract_doc, self.user_ids["p2"]), "REJECTED"
        )

    def test_update_contract_effect_updates_another_contract(self) -> None:
        definition = {
            "id": "contract-bulk-update",
            "version": "1.0",
            "initial_state": "S1",
            "states": {
                "S1": {
                    "events": {
                        "UpdateOthers": {
                            "trigger": [
                                {
                                    "type": "api",
                                    "path": "update-others",
                                    "method": "POST",
                                    "payload_schema": {
                                        "type": "object",
                                        "required": ["target_contract", "value"],
                                        "properties": {
                                            "target_contract": {
                                                "type": "string",
                                                "minLength": 1,
                                            },
                                            "value": {"type": "string", "minLength": 1},
                                        },
                                        "additionalProperties": False,
                                    },
                                }
                            ],
                            "effects": [
                                {
                                    "title": "Bulk Update Contracts",
                                    "description": "Updates target contracts with a propagated marker from the source event.",
                                    "type": "update.contract",
                                    "updates": {
                                        "$$ctx.payload.target_contract": {
                                            "$set": {
                                                "context.bulk_marker": "$$ctx.payload.value"
                                            }
                                        }
                                    },
                                }
                            ],
                        }
                    }
                }
            },
        }

        template_id = self._create_template(definition)
        c1 = self._create_contract(template_id, {"seed": 1})
        c2 = self._create_contract(template_id, {"seed": 2})
        self.assertEqual(c1.status_code, 201)
        self.assertEqual(c2.status_code, 201)

        cid1 = c1.json()["id"]
        cid2 = c2.json()["id"]
        r = self._post_event(
            cid1,
            "update-others",
            actor="u1",
            payload={"target_contract": cid2, "value": "propagated"},
        )
        self.assertEqual(r.status_code, 200)

        got2 = self._get_contract_doc(cid2)
        self.assertEqual(
            (got2.get("context") or {}).get("bulk_marker"), "propagated"
        )

    def test_update_contract_effect_supports_update_pipeline_in_updates(self) -> None:
        definition = {
            "id": "contract-bulk-update-updates",
            "version": "1.0",
            "initial_state": "S1",
            "states": {
                "S1": {
                    "events": {
                        "UpdateBatch": {
                            "trigger": [
                                {
                                    "type": "api",
                                    "path": "update-batch",
                                    "method": "POST",
                                    "payload_schema": {
                                        "type": "object",
                                        "required": ["target_contract", "value"],
                                        "properties": {
                                            "target_contract": {
                                                "type": "string",
                                                "minLength": 1,
                                            },
                                            "value": {"type": "string", "minLength": 1},
                                        },
                                        "additionalProperties": False,
                                    },
                                }
                            ],
                            "effects": [
                                {
                                    "title": "Bulk Update Contracts",
                                    "description": "Updates target contracts with a uniform update list.",
                                    "type": "update.contract",
                                    "updates": {
                                        "$$ctx.payload.target_contract": [
                                            {
                                                "$set": {
                                                    "context.bulk_marker": "$$ctx.payload.value"
                                                }
                                            }
                                        ]
                                    },
                                }
                            ],
                        }
                    }
                }
            },
        }

        template_id = self._create_template(definition)
        c1 = self._create_contract(template_id, {"seed": 1})
        c2 = self._create_contract(template_id, {"seed": 2})
        self.assertEqual(c1.status_code, 201)
        self.assertEqual(c2.status_code, 201)

        cid1 = c1.json()["id"]
        cid2 = c2.json()["id"]
        r = self._post_event(
            cid1,
            "update-batch",
            actor="u1",
            payload={"target_contract": cid2, "value": "uniform"},
        )
        self.assertEqual(r.status_code, 200)

        got2 = self._get_contract_doc(cid2)
        self.assertEqual(
            (got2.get("context") or {}).get("bulk_marker"), "uniform"
        )

    def test_execute_event_effect_fails_fast_when_event_missing_same_contract(
            self,
    ) -> None:
        definition = {
            "id": "contract-execute-event-failfast-local",
            "version": "1.0",
            "initial_state": "S1",
            "states": {
                "S1": {
                    "events": {
                        "Outer": {
                            "trigger": [
                                {
                                    "type": "api",
                                    "path": "outer",
                                    "method": "POST",
                                }
                            ],
                            "effects": [
                                {
                                    "type": "execute.event",
                                    "event_name": "MissingEvent",
                                }
                            ],
                        }
                    }
                }
            },
        }

        template_id = self._create_template(definition)
        created = self._create_contract(template_id, {"seed": 1})
        self.assertEqual(created.status_code, 201)
        cid = created.json()["id"]

        r = self._post_event(cid, "outer", actor="u1")
        self.assertEqual(r.status_code, 409)
        self.assertIn("Event not available in this state", r.text)

        got = self._get_contract_doc(cid)
        self.assertEqual(got.get("state"), "S1")

    def test_execute_event_effect_fails_fast_when_event_missing_other_contract(
            self,
    ) -> None:
        definition = {
            "id": "contract-execute-event-failfast-remote",
            "version": "1.0",
            "initial_state": "S1",
            "states": {
                "S1": {
                    "events": {
                        "Outer": {
                            "trigger": [
                                {
                                    "type": "api",
                                    "path": "outer",
                                    "method": "POST",
                                    "payload_schema": {
                                        "type": "object",
                                        "required": ["target_contract"],
                                        "properties": {
                                            "target_contract": {
                                                "type": "string",
                                                "minLength": 1,
                                            }
                                        },
                                        "additionalProperties": False,
                                    },
                                }
                            ],
                            "effects": [
                                {
                                    "type": "execute.event",
                                    "event_name": "MissingEvent",
                                    "contract_id": "$$ctx.payload.target_contract",
                                }
                            ],
                        }
                    }
                }
            },
        }

        template_id = self._create_template(definition)
        c1 = self._create_contract(template_id, {"seed": 1})
        c2 = self._create_contract(template_id, {"seed": 2})
        self.assertEqual(c1.status_code, 201)
        self.assertEqual(c2.status_code, 201)

        cid1 = c1.json()["id"]
        cid2 = c2.json()["id"]
        r = self._post_event(
            cid1,
            "outer",
            actor="u1",
            payload={"target_contract": cid2},
        )
        self.assertEqual(r.status_code, 409)
        self.assertIn("Event not available in this state", r.text)

        got1 = self._get_contract_doc(cid1)
        got2 = self._get_contract_doc(cid2)
        self.assertEqual((got1.get("context") or {}).get("seed"), 1)
        self.assertEqual((got2.get("context") or {}).get("seed"), 2)

    def test_paydriver_event_positive_compensation_credits_coin_wallet(self) -> None:
        definition = {
            "id": "contract-paydriver-positive",
            "version": "1.0",
            "initial_state": "S1",
            "events": {
                "PayDriver": _gherkin_definition()["events"]["PayDriver"],
            },
            "states": {
                "S1": {
                    "events": {
                        "Settle": {
                            "trigger": [
                                {
                                    "type": "api",
                                    "path": "settle",
                                    "method": "POST",
                                }
                            ],
                            "effects": [
                                {
                                    "type": "execute.event",
                                    "event_name": "PayDriver",
                                }
                            ],
                        }
                    }
                }
            },
        }

        template_id = self._create_template(definition)
        before_coin = self._wallet_balance("d1", "coin")
        before_credit = self._wallet_balance("d1", "credit")
        d1_principal = f"u:{self.user_ids['d1']}"
        before_notif = self._count_notifications_for(
            d1_principal, "contracts.payment_settled_driver"
        )

        created = self._create_contract(
            template_id,
            {
                "driver": d1_principal,
                "driver_route": {"compensation": 4},
            },
            actor="d1",
        )
        self.assertEqual(created.status_code, 201, msg=created.text)
        cid = str(created.json()["id"])

        settled = self._post_event(cid, "settle", actor="d1")
        self.assertEqual(settled.status_code, 200, msg=settled.text)
        self.assertTrue(settled.json().get("ok"))

        self.assertEqual(self._wallet_balance("d1", "coin"), before_coin + 4)
        self.assertEqual(self._wallet_balance("d1", "credit"), before_credit)
        after_notif = self._count_notifications_for(
            d1_principal, "contracts.payment_settled_driver"
        )
        self.assertGreaterEqual(after_notif, before_notif + 1)

    def test_paydriver_event_negative_compensation_splits_coin_and_credit(self) -> None:
        definition = {
            "id": "contract-paydriver-negative",
            "version": "1.0",
            "initial_state": "S1",
            "events": {
                "PayDriver": _gherkin_definition()["events"]["PayDriver"],
            },
            "states": {
                "S1": {
                    "events": {
                        "Settle": {
                            "trigger": [
                                {
                                    "type": "api",
                                    "path": "settle",
                                    "method": "POST",
                                }
                            ],
                            "effects": [
                                {
                                    "type": "execute.event",
                                    "event_name": "PayDriver",
                                }
                            ],
                        }
                    }
                }
            },
        }

        with self.app.app_context():
            from schedula.utils.form.server.credits import get_wallet

            wallet = get_wallet(self.user_ids["d1"])
            wallet.charge(product="coin", credits=2, session=_db.session)
            _db.session.commit()

        before_coin = self._wallet_balance("d1", "coin")
        before_credit = self._wallet_balance("d1", "credit")
        self.assertEqual(before_coin, 2)

        template_id = self._create_template(definition)
        created = self._create_contract(
            template_id,
            {
                "driver": f"u:{self.user_ids['d1']}",
                "driver_route": {"compensation": -5},
            },
            actor="d1",
        )
        self.assertEqual(created.status_code, 201, msg=created.text)
        cid = str(created.json()["id"])

        settled = self._post_event(cid, "settle", actor="d1")
        self.assertEqual(settled.status_code, 200)
        self.assertTrue(settled.json().get("ok"))

        self.assertEqual(self._wallet_balance("d1", "coin"), before_coin - 2)
        self.assertEqual(self._wallet_balance("d1", "credit"), before_credit - 3)

    def test_dispute_events_rider_open_and_undo_notify_driver(self) -> None:
        cid = self._create_gherkin_contract(initial_state="START", actor="p1")
        p1_principal = f"u:{self.user_ids['p1']}"
        d1_principal = f"u:{self.user_ids['d1']}"

        accepted = self._post_event(
            cid,
            "driver-accept-start",
            actor="d1",
            payload={"rider": p1_principal},
        )
        self.assertEqual(accepted.status_code, 200)
        self.assertTrue(accepted.json().get("ok"))

        pre = self._queue_jobs(contract_id=cid, event_name="PreDepartureGateTimed")[0][
            "run_at"
        ]
        if pre.tzinfo is None:
            pre = pre.replace(tzinfo=dt.timezone.utc)
        self.assertTrue(self._run_worker_once(now=pre + dt.timedelta(seconds=1)))

        opened_before = self._count_notifications_for(
            d1_principal, "contracts.dispute_opened"
        )
        canceled_before = self._count_notifications_for(
            d1_principal, "contracts.dispute_canceled"
        )

        open_r = self._post_event(cid, "driver-did-not-pick-me", actor="p1")
        self.assertEqual(open_r.status_code, 200)
        self.assertTrue(open_r.json().get("ok"))
        self.assertGreaterEqual(
            self._count_notifications_for(d1_principal, "contracts.dispute_opened"),
            opened_before + 1,
        )

        undo_r = self._post_event(cid, "driver-did-not-pick-me-undo", actor="p1")
        self.assertEqual(undo_r.status_code, 200)
        c = self._get_contract_doc(cid)
        rider_ctx = ((c.get("context") or {}).get("riders") or {}).get(
            p1_principal
        ) or {}
        if undo_r.json().get("ok"):
            self.assertGreaterEqual(
                self._count_notifications_for(
                    d1_principal, "contracts.dispute_canceled"
                ),
                canceled_before + 1,
            )
            self.assertFalse(bool(((rider_ctx.get("dispute") or {}).get("rider"))))
        else:
            self.assertEqual(
                self._count_notifications_for(
                    d1_principal, "contracts.dispute_canceled"
                ),
                canceled_before,
            )
            self.assertTrue(bool(((rider_ctx.get("dispute") or {}).get("rider"))))

    def test_dispute_events_driver_open_and_undo_notify_rider(self) -> None:
        cid = self._create_gherkin_contract(initial_state="START", actor="p1")
        p1_principal = f"u:{self.user_ids['p1']}"

        accepted = self._post_event(
            cid,
            "driver-accept-start",
            actor="d1",
            payload={"rider": p1_principal},
        )
        self.assertEqual(accepted.status_code, 200)
        self.assertTrue(accepted.json().get("ok"))

        pre = self._queue_jobs(contract_id=cid, event_name="PreDepartureGateTimed")[0][
            "run_at"
        ]
        if pre.tzinfo is None:
            pre = pre.replace(tzinfo=dt.timezone.utc)
        self.assertTrue(self._run_worker_once(now=pre + dt.timedelta(seconds=1)))

        opened_before = self._count_notifications_for(
            p1_principal, "contracts.dispute_opened"
        )
        canceled_before = self._count_notifications_for(
            p1_principal, "contracts.dispute_canceled"
        )

        open_r = self._post_event(
            cid,
            "rider-not-at-pickup",
            actor="d1",
            payload={"rider": p1_principal},
        )
        self.assertEqual(open_r.status_code, 200)
        self.assertTrue(open_r.json().get("ok"))
        self.assertGreaterEqual(
            self._count_notifications_for(p1_principal, "contracts.dispute_opened"),
            opened_before + 1,
        )

        undo_r = self._post_event(
            cid,
            "rider-not-at-pickup-undo",
            actor="d1",
            payload={"rider": p1_principal},
        )
        self.assertEqual(undo_r.status_code, 200)
        self.assertTrue(undo_r.json().get("ok"))
        self.assertGreaterEqual(
            self._count_notifications_for(p1_principal, "contracts.dispute_canceled"),
            canceled_before + 1,
        )

        c = self._get_contract_doc(cid)
        rider_ctx = ((c.get("context") or {}).get("riders") or {}).get(
            p1_principal
        ) or {}
        self.assertFalse(bool(((rider_ctx.get("dispute") or {}).get("driver"))))
