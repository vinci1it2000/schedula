# coding: utf-8
from __future__ import annotations

import contextlib
import datetime as dt
import json
import os
import unittest
import uuid
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import patch
from urllib.parse import urlsplit, urlunsplit

import httpx
from flask import Flask
from flask_security.utils import hash_password
from schedula.utils.form.server import basic_app
from schedula.utils.form.server.extensions import db as _db
from schedula.utils.form.server.security import User
from schedula.utils.form.server.security.casbin import get_enforcer
from schedula.utils.form.server.security.casbin.bootstrap import (
    bootstrap_user,
    set_system_admin,
)
from schedula.utils.form.server.security.casbin.helpers import ADMIN_DOMAIN, ANON_USER
from schedula.utils.form.server.security.casbin.models import Group
from schedula.utils.form.server.security.casbin.models import ensure_public_group
from tests.utils.server.conftest import DummySitemap


@lru_cache(maxsize=1)
def _gherkin_definition_template() -> Dict[str, Any]:
    p = Path(__file__).with_name("data") / "gherkin_definition.json"
    return json.loads(p.read_text(encoding="utf-8"))


def _gherkin_definition() -> Dict[str, Any]:
    return deepcopy(_gherkin_definition_template())


class ContractsE2ETest(unittest.TestCase):
    _mongo_container: Any = None
    _mongo_base_uri: str = ""

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
        except Exception as ex:  # pragma: no cover - environment dependent
            raise unittest.SkipTest(
                "contracts e2e requires testcontainers[mongodb]"
            ) from ex

        try:
            cls._mongo_container = MongoDbContainer("mongo:7.0")
            cls._mongo_container.start()
            cls._mongo_base_uri = str(cls._mongo_container.get_connection_url())
        except Exception as ex:  # pragma: no cover - environment dependent
            raise unittest.SkipTest(
                "contracts e2e requires Docker with a runnable MongoDB container"
            ) from ex

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            if cls._mongo_container is not None:
                cls._mongo_container.stop()
        finally:
            cls._mongo_container = None
            cls._mongo_base_uri = ""
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
            SQLALCHEMY_DATABASE_URI="sqlite+pysqlite:///:memory:",
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

        self._patchers = [
            patch(
                "schedula.utils.form.server.credits.Lock",
                new=lambda *_args, **_kwargs: contextlib.nullcontext(),
            ),
            patch(
                "schedula.utils.form.server.contracts.engine.create_sadlock",
                new=lambda *_args, **_kwargs: contextlib.nullcontext(),
            ),
            patch(
                "schedula.utils.form.server.contracts.schedule.create_sadlock",
                new=lambda *_args, **_kwargs: contextlib.nullcontext(),
            ),
        ]
        for patcher in self._patchers:
            patcher.start()

        with self.app.app_context():
            _db.create_all()
            ensure_public_group()
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

            from schedula.utils.form.server.credits import get_wallet

            self.route_by_principal: Dict[str, str] = {}
            items_coll = self.app.config["MONGO_DB"]["items"]
            for uid in self.user_ids.values():
                principal = f"u:{uid}"
                route_id = str(uuid.uuid4())
                route_doc = {
                    "cost": 10,
                    "capacity": 3,
                    "user_id": principal,
                    "origin": {
                        "lat": 45.0,
                        "lng": 9.0,
                        "at": "1970-01-01T00:00:00+00:00",
                    },
                    "destination": {"lat": 45.1, "lng": 9.1},
                }
                items_coll.insert_one(
                    {
                        "_id": route_id,
                        "category": "route",
                        "data": route_doc,
                        "created_by": principal,
                        "updated_by": principal,
                        "created_at": dt.datetime.utcnow(),
                        "updated_at": dt.datetime.utcnow(),
                    }
                )
                self.route_by_principal[principal] = route_id

                wallet = get_wallet(uid)
                wallet.charge(product="coin", credits=100)

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
        for patcher in getattr(self, "_patchers", []):
            patcher.stop()
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
        if payload is None and path == "accept-user":
            payload = {
                "seats": 1,
                "origin": {
                    "lat": 45.0,
                    "lng": 9.0,
                    "at": "1970-01-01T00:00:00+00:00",
                },
                "destination": {"lat": 45.1, "lng": 9.1},
            }
        if payload is None and path == "request-join":
            actor_principal = f"u:{self.user_ids[actor]}"
            payload = {
                "route_id": self.route_by_principal[actor_principal],
            }
        if payload is None and path == "driver-accept-start":
            payload = {"rider": f"u:{self.user_ids['p1']}"}
        return self.httpx.post(
            f"/contracts/{contract_id}/{path}",
            json={"payload": payload or {}},
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

    def _user_state(self, contract: Dict[str, Any], user_id: int) -> str:
        return str((contract.get("states") or {}).get(f"u:{user_id}") or "")

    def _count_notifications_for(self, principal: str, event: str) -> int:
        with self.app.app_context():
            coll = self.app.config["MONGO_DB"]["notifications"]
            return int(
                coll.count_documents(
                    {"event": event, f"targets.{principal}": {"$exists": True}}
                )
            )

    def _wallet_balance(self, actor: str, product: str = "coin") -> float:
        with self.app.app_context():
            from schedula.utils.form.server.credits import get_wallet

            wallet = get_wallet(self.user_ids[actor])
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

    def _get_route(self, actor: str, route_id: str) -> Dict[str, Any]:
        resp = self.httpx.get(f"/item/route/{route_id}", headers=self._headers(actor))
        self.assertEqual(resp.status_code, 200, msg=resp.text)
        return resp.json() or {}

    def _create_route(self, actor: str, **updates: Any) -> str:
        principal = f"u:{self.user_ids[actor]}"
        data = {
            "cost": 10,
            "capacity": 3,
            "seats": 1,
            "user_id": principal,
            "origin": {"lat": 45.0, "lng": 9.0, "at": "1970-01-01T00:00:00+00:00"},
            "destination": {"lat": 45.1, "lng": 9.1},
        }
        data.update(updates)
        resp = self.httpx.post(
            "/item/route",
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
            f"/item/route/{route_id}",
            json={"data": data},
            headers=self._headers(actor),
        )
        self.assertEqual(resp.status_code, 200, msg=resp.text)
        return resp.json() or {}

    def _gherkin_context_for(self, driver: str, riders: List[str]) -> Dict[str, Any]:
        driver_principal = f"u:{self.user_ids[driver]}"
        rider_ids = [f"u:{self.user_ids[r]}" for r in riders]
        rider_route_ids = [
            self.route_by_principal[principal] for principal in rider_ids
        ]
        return {
            "driver_trip_id": self.route_by_principal[driver_principal],
            "riders": rider_route_ids,
        }

    def _gherkin_context(self, initial_state: str = "START") -> Dict[str, Any]:
        driver_uid = self.user_ids["d1"]
        p1_uid = self.user_ids["p1"]
        rider_ids = [f"u:{p1_uid}"]
        driver_principal = f"u:{driver_uid}"
        rider_route_ids = [
            self.route_by_principal[principal] for principal in rider_ids
        ]
        return {
            "driver_trip_id": self.route_by_principal[driver_principal],
            "riders": rider_route_ids,
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
        return str(created.json()["id"])

    def _to_recruiting(self, cid: str) -> str:
        self.assertEqual(
            self._post_event(cid, "driver-accept-start", actor="d1").status_code,
            200,
        )
        self.assertEqual(
            self._post_event(cid, "accept-user", actor="p1").status_code, 200
        )
        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
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
        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        self.assertEqual(c["state"], "READY")
        return gid

    def test_start_user_initiated_sets_pending_driver_and_requesting_rider(
        self,
    ) -> None:
        cid = self._create_gherkin_contract(initial_state="START", actor="p1")
        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()

        self.assertEqual(c["state"], "ONBOARDING")
        self.assertEqual(self._user_state(c, self.user_ids["d1"]), "PENDING_DRIVER")
        self.assertEqual(self._user_state(c, self.user_ids["p1"]), "REQUESTING")

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

        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        self.assertEqual(c["state"], "ONBOARDING")
        self.assertEqual(self._user_state(c, self.user_ids["d1"]), "DRIVER")
        self.assertEqual(self._user_state(c, self.user_ids["p1"]), "ACCEPTED")
        self.assertEqual(self._user_state(c, self.user_ids["p4"]), "REQUESTING")

    def test_start_driver_accept_start_sets_accepted_seats_total_from_rider(
        self,
    ) -> None:
        p1_principal = f"u:{self.user_ids['p1']}"
        route_id = self.route_by_principal[p1_principal]
        with self.app.app_context():
            self.app.config["MONGO_DB"]["items"].update_one(
                {"_id": route_id}, {"$set": {"data.seats": 2}}
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

        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        self.assertEqual(c["state"], "ONBOARDING")
        self.assertEqual((c.get("context") or {}).get("accepted_seats_total"), 2)

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

        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
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

        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        self.assertEqual(c["state"], "ONBOARDING")
        self.assertEqual(self._user_state(c, self.user_ids["p1"]), "REJECTED")
        self.assertNotIn(p1_principal, (c.get("context") or {}).get("riders") or {})

    def test_start_driver_cancel_invite_user_clears_pending_state(self) -> None:
        cid = self._create_gherkin_contract(initial_state="START", actor="p1")
        p2_principal = f"u:{self.user_ids['p2']}"
        p2_route_id = self.route_by_principal[p2_principal]

        with self.app.app_context():
            self.app.config["MONGO_DB"]["contracts"].update_one(
                {"_id": cid},
                {
                    "$set": {
                        f"states.{p2_principal}": "PENDING",
                        f"context.riders.{p2_principal}": {
                            "id": p2_route_id,
                            "seats": 1,
                            "trip": {},
                        },
                    }
                },
            )

        cancel = self._post_event(
            cid,
            "driver-cancel-invite-user",
            actor="d1",
            payload={"route_id": p2_route_id},
        )
        self.assertEqual(cancel.status_code, 200)
        self.assertTrue(cancel.json().get("ok"))

        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        self.assertEqual(c["state"], "ONBOARDING")
        self.assertEqual(self._user_state(c, self.user_ids["p2"]), "")

    def test_start_user_accept_invite_moves_to_confirming(self) -> None:
        cid = self._create_gherkin_contract(initial_state="START", actor="p1")
        p2_principal = f"u:{self.user_ids['p2']}"
        p2_route_id = self.route_by_principal[p2_principal]

        with self.app.app_context():
            self.app.config["MONGO_DB"]["contracts"].update_one(
                {"_id": cid},
                {
                    "$set": {
                        f"states.{p2_principal}": "PENDING",
                        f"context.riders.{p2_principal}": {
                            "id": p2_route_id,
                            "seats": 2,
                            "trip": {},
                        },
                    }
                },
            )

        accepted = self._post_event(cid, "accept-user", actor="p2")
        self.assertEqual(accepted.status_code, 200)
        self.assertTrue(accepted.json().get("ok"))

        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        self.assertEqual(c["state"], "ONBOARDING")
        self.assertEqual(self._user_state(c, self.user_ids["p2"]), "ACCEPTED")
        self.assertEqual((c.get("context") or {}).get("accepted_seats_total"), 2)

    def test_start_user_reject_invite_clears_pending_rider(self) -> None:
        cid = self._create_gherkin_contract(initial_state="START", actor="p1")
        p2_principal = f"u:{self.user_ids['p2']}"
        p2_route_id = self.route_by_principal[p2_principal]

        with self.app.app_context():
            self.app.config["MONGO_DB"]["contracts"].update_one(
                {"_id": cid},
                {
                    "$set": {
                        f"states.{p2_principal}": "PENDING",
                        f"context.riders.{p2_principal}": {
                            "id": p2_route_id,
                            "seats": 1,
                            "trip": {},
                        },
                    }
                },
            )

        rejected = self._post_event(cid, "reject-user", actor="p2")
        self.assertEqual(rejected.status_code, 200)
        self.assertTrue(rejected.json().get("ok"))

        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        self.assertEqual(c["state"], "ONBOARDING")
        self.assertEqual(self._user_state(c, self.user_ids["p2"]), "")

    def test_recruiting_driver_reject_user_marks_target_rejected(self) -> None:
        cid = self._create_gherkin_contract(initial_state="START", actor="p1")
        p1_principal = f"u:{self.user_ids['p1']}"

        r = self._post_event(
            cid,
            "driver-reject-user",
            actor="d1",
            payload={"principal": p1_principal},
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json().get("ok"))

        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        self.assertEqual(c["state"], "ONBOARDING")
        self.assertEqual(self._user_state(c, self.user_ids["p1"]), "REJECTED")
        self.assertNotIn(p1_principal, (c.get("context") or {}).get("riders") or {})

    def test_onboarding_driver_reject_trip_cleans_riders_on_rejected(self) -> None:
        cid = self._create_gherkin_contract(initial_state="START", actor="p1")

        r = self._post_event(cid, "driver-reject-trip", actor="d1")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json().get("ok"))

        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        self.assertEqual(c["state"], "REJECTED")
        self.assertEqual((c.get("context") or {}).get("riders") or {}, {})

    def test_recruiting_user_cancel_ride_marks_user_cancelled(self) -> None:
        cid = self._create_gherkin_contract(initial_state="START", actor="p1")

        r = self._post_event(cid, "cancel-user", actor="p1")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json().get("ok"))

        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        self.assertEqual(c["state"], "ONBOARDING")
        self.assertEqual(self._user_state(c, self.user_ids["p1"]), "CANCELLED")

    def test_start_request_join_adds_requesting_user_when_capacity_and_credits_ok(
        self,
    ) -> None:
        driver_principal = f"u:{self.user_ids['d1']}"
        before = self._count_notifications_for(
            driver_principal, "contracts.join_requested"
        )

        cid = self._create_gherkin_contract(initial_state="START")
        r = self._post_event(cid, "request-join", actor="p4")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json().get("ok"))

        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        self.assertEqual(c["state"], "ONBOARDING")
        self.assertEqual(self._user_state(c, self.user_ids["p4"]), "REQUESTING")

        after = self._count_notifications_for(
            driver_principal, "contracts.join_requested"
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

        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        self.assertEqual(self._user_state(c, self.user_ids["p4"]), "")

    def test_start_cancel_join_request_last_user_re_notifies_driver(self) -> None:
        driver_principal = f"u:{self.user_ids['d1']}"
        before = self._count_notifications_for(
            driver_principal, "contracts.request_ride"
        )

        cid = self._create_gherkin_contract(initial_state="START", actor="p1")
        after_create = self._count_notifications_for(
            driver_principal, "contracts.request_ride"
        )
        self.assertEqual(after_create, before + 1)

        self.assertEqual(
            self._post_event(cid, "cancel-join-request", actor="p1").status_code, 200
        )

        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        self.assertEqual(c["state"], "ONBOARDING")
        self.assertIn((c.get("context") or {}).get("riders_map"), ({}, None))

        after_cancel = self._count_notifications_for(
            driver_principal, "contracts.request_ride"
        )
        self.assertEqual(after_cancel, before + 2)

    def test_onboarding_full_journey_all_apis_with_negatives_and_pruning(self) -> None:
        definition = _gherkin_definition()
        template_id = self._create_template(
            definition,
            allowed_initial_states=["START"],
        )

        p1_principal = f"u:{self.user_ids['p1']}"
        p2_principal = f"u:{self.user_ids['p2']}"
        p4_principal = f"u:{self.user_ids['p4']}"
        p2_route_id = self._create_route("p2", cost=10, seats=1)
        p2_route_low_credit = self._create_route("p2", cost=1000, seats=1)
        p2_route_over_seats = self._create_route("p2", cost=10, seats=9)
        p3_route_id = self._create_route("p3", cost=10, seats=1)
        p4_route_id = self._create_route("p4", cost=10, seats=1)
        p4_route_low_credit = self._create_route("p4", cost=1000, seats=1)
        p4_route_over_seats = self._create_route("p4", cost=10, seats=9)
        d1_route_id = self._create_route("d1")

        p2_balance_before = self._wallet_balance("p2")
        p3_balance_before = self._wallet_balance("p3")
        p4_balance_before = self._wallet_balance("p4")

        d1_principal = f"u:{self.user_ids['d1']}"
        p2_invite_before = self._count_notifications_for(
            p2_principal, "contracts.user_invited"
        )
        p3_invite_before = self._count_notifications_for(
            f"u:{self.user_ids['p3']}", "contracts.user_invited"
        )
        p3_cancel_invite_before = self._count_notifications_for(
            f"u:{self.user_ids['p3']}", "contracts.driver_cancelled_invite"
        )
        d1_join_requested_before = self._count_notifications_for(
            d1_principal, "contracts.join_requested"
        )
        d1_user_rejected_before = self._count_notifications_for(
            d1_principal, "contracts.user_rejected"
        )
        d1_user_cancelled_before = self._count_notifications_for(
            d1_principal, "contracts.user_cancelled"
        )
        p2_driver_rejected_before = self._count_notifications_for(
            p2_principal, "contracts.user_rejected_by_driver"
        )

        created_a = self._create_contract(
            template_id,
            self._gherkin_context_for("d1", ["p1"]),
            initial_state="START",
            actor="p1",
        )
        self.assertEqual(created_a.status_code, 201, msg=created_a.text)
        contract_a = str(created_a.json()["id"])

        contract_a_doc = self.httpx.get(
            f"/contracts/{contract_a}", headers=self._headers("owner-1")
        ).json()
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
            payload={"route_id": missing_route_id},
        )
        self.assertEqual(missing_cancel_invite.status_code, 404)

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
            json={"principal": "bad-principal"},
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
            self._gherkin_context_for("d1", ["p1"]),
            initial_state="START",
            actor="p1",
        )
        self.assertEqual(created_req.status_code, 201, msg=created_req.text)
        contract_req = str(created_req.json()["id"])

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
            self._count_notifications_for(d1_principal, "contracts.join_requested"),
            d1_join_requested_before + 2,
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
        self.assertFalse(bad_invite_low_credits.json().get("ok"))
        self.assertEqual(self._wallet_balance("p2"), p2_balance_before)

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
        self.assertEqual(self._wallet_balance("p2"), p2_balance_before - 10)
        p2_route_after_invite = self._get_route("p2", p2_route_id)
        p2_route_data_after_invite = p2_route_after_invite.get("data") or {}
        self.assertEqual(p2_route_data_after_invite.get("reserved_credits"), 10)
        self.assertIn(contract_a, p2_route_data_after_invite.get("contract_ids") or [])
        self.assertEqual(
            self._count_notifications_for(p2_principal, "contracts.user_invited"),
            p2_invite_before + 1,
        )

        invite_p3 = self._post_event(
            contract_a,
            "invite-user",
            actor="d1",
            payload={"route_id": p3_route_id},
        )
        self.assertEqual(invite_p3.status_code, 200)
        self.assertTrue(invite_p3.json().get("ok"))
        self.assertEqual(self._wallet_balance("p3"), p3_balance_before - 10)
        self.assertEqual(
            self._count_notifications_for(
                f"u:{self.user_ids['p3']}", "contracts.user_invited"
            ),
            p3_invite_before + 1,
        )

        cancel_invite_p3 = self._post_event(
            contract_a,
            "driver-cancel-invite-user",
            actor="d1",
            payload={"route_id": p3_route_id},
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
                f"u:{self.user_ids['p3']}", "contracts.driver_cancelled_invite"
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
        self.assertEqual(self._wallet_balance("p3"), p3_balance_before - 10)
        self.assertEqual(
            self._count_notifications_for(
                f"u:{self.user_ids['p3']}", "contracts.user_invited"
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
            self._count_notifications_for(d1_principal, "contracts.user_rejected"),
            d1_user_rejected_before + 1,
        )

        # Competitor contract used to verify pruning after user accept on contract A.
        created_c = self._create_contract(
            template_id,
            {
                "driver_trip_id": self.route_by_principal[f"u:{self.user_ids['p3']}"],
                "riders": [p2_route_id],
            },
            initial_state="START",
            actor="p2",
        )
        self.assertEqual(created_c.status_code, 201, msg=created_c.text)
        contract_c = str(created_c.json()["id"])

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

        contract_c_doc = self.httpx.get(
            f"/contracts/{contract_c}", headers=self._headers("owner-1")
        ).json()
        self.assertEqual(
            self._user_state(contract_c_doc, self.user_ids["p2"]), "REJECTED"
        )
        after_rider_unavailable_c = self._count_notifications_for(
            f"u:{self.user_ids['p3']}", "contracts.rider_unavailable"
        )
        self.assertGreaterEqual(after_rider_unavailable_c, before_rider_unavailable_c)

        # Driver remove accepted user and rider cancel flows.
        driver_remove_p2 = self._post_event(
            contract_a,
            "driver-reject-user",
            actor="d1",
            payload={"principal": p2_principal},
        )
        self.assertEqual(driver_remove_p2.status_code, 200)
        self.assertTrue(driver_remove_p2.json().get("ok"))
        self.assertEqual(self._wallet_balance("p2"), p2_balance_before - 10)
        p2_route_after_driver_reject = self._get_route("p2", p2_route_id)
        p2_route_data_after_driver_reject = (
            p2_route_after_driver_reject.get("data") or {}
        )
        self.assertEqual(
            p2_route_data_after_driver_reject.get("contract_ids") or [], []
        )
        self.assertEqual(p2_route_data_after_driver_reject.get("reserved_credits"), 10)
        self.assertEqual(
            self._count_notifications_for(
                p2_principal, "contracts.user_rejected_by_driver"
            ),
            p2_driver_rejected_before + 1,
        )

        rider_cancel_p1 = self._post_event(contract_a, "cancel-user", actor="p1")
        self.assertEqual(rider_cancel_p1.status_code, 200)
        self.assertTrue(rider_cancel_p1.json().get("ok"))
        self.assertEqual(
            self._count_notifications_for(d1_principal, "contracts.user_cancelled"),
            d1_user_cancelled_before + 1,
        )

        contract_a_doc = self.httpx.get(
            f"/contracts/{contract_a}", headers=self._headers("owner-1")
        ).json()
        self.assertEqual(
            self._user_state(contract_a_doc, self.user_ids["p2"]), "REJECTED"
        )
        self.assertEqual(
            self._user_state(contract_a_doc, self.user_ids["p1"]), "CANCELLED"
        )

        # ONBOARDING terminal events tested in same journey on dedicated contracts.
        created_ready = self._create_contract(
            template_id,
            self._gherkin_context_for("d1", ["p4"]),
            initial_state="START",
            actor="p4",
        )
        self.assertEqual(created_ready.status_code, 201, msg=created_ready.text)
        contract_ready = str(created_ready.json()["id"])
        set_ready = self._post_event(contract_ready, "set-ready", actor="d1")
        self.assertEqual(set_ready.status_code, 200)
        self.assertTrue(set_ready.json().get("ok"))
        ready_doc = self.httpx.get(
            f"/contracts/{contract_ready}", headers=self._headers("owner-1")
        ).json()
        self.assertEqual(ready_doc["state"], "READY")

        created_cancel_trip = self._create_contract(
            template_id,
            self._gherkin_context_for("d1", ["p4"]),
            initial_state="START",
            actor="p4",
        )
        self.assertEqual(
            created_cancel_trip.status_code, 201, msg=created_cancel_trip.text
        )
        contract_cancel_trip = str(created_cancel_trip.json()["id"])
        cancel_trip = self._post_event(
            contract_cancel_trip,
            "driver-reject-trip",
            actor="d1",
        )
        self.assertEqual(cancel_trip.status_code, 200)
        self.assertTrue(cancel_trip.json().get("ok"))
        cancelled_trip_doc = self.httpx.get(
            f"/contracts/{contract_cancel_trip}", headers=self._headers("owner-1")
        ).json()
        self.assertEqual(cancelled_trip_doc["state"], "REJECTED")

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

        got2 = self.httpx.get(f"/contracts/{cid2}", headers=self._headers("owner-1"))
        self.assertEqual(got2.status_code, 200)
        self.assertEqual(
            (got2.json().get("context") or {}).get("bulk_marker"), "propagated"
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

        got2 = self.httpx.get(f"/contracts/{cid2}", headers=self._headers("owner-1"))
        self.assertEqual(got2.status_code, 200)
        self.assertEqual(
            (got2.json().get("context") or {}).get("bulk_marker"), "uniform"
        )
