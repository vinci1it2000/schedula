# coding: utf-8
from __future__ import annotations

import datetime as dt
import os
import unittest
import uuid
from typing import Any, Dict, List

import httpx
import mongomock
from flask import Flask

from schedula.utils.form.server import basic_app
from schedula.utils.form.server.contracts.registry import get_registry
from schedula.utils.form.server.extensions import db as _db
from schedula.utils.form.server.security.casbin import get_enforcer
from schedula.utils.form.server.security.casbin.helpers import ADMIN_DOMAIN, ANON_USER
from schedula.utils.form.server.utils import get_mongo, now_utc
from tests.utils.server.conftest import DummySitemap
from tests.utils.server.utils.mongo_validation import ValidatingMongoDatabase


def _iso(ts: dt.datetime) -> str:
    return ts.astimezone(dt.timezone.utc).isoformat()


def _abort_event():
    return {
        "path": "abort",
        "method": "POST",
        "allowedRoles": ["g:anonymous"],
        "payloadSchema": {"type": "object"},
        "effects": [
            {
                "type": "charge_credits",
                "argsMapping": {
                    "ownerId": "${context.ownerId}",
                    "amount": "${context.penaltyCredits}",
                    "reason": "owner_abort",
                },
            },
            {
                "type": "notify",
                "argsMapping": {
                    "kind": "owner_abort",
                    "ownerId": "${context.ownerId}",
                },
            },
        ],
        "defaultTarget": "S_FINAL_OWNER_ABORTED",
    }


def _definition() -> Dict[str, Any]:
    return {
        "id": "contract-e2e",
        "version": "1.0",
        "initialState": "S1_INVITE",
        "states": {
            "S1_INVITE": {
                "onEnter": {
                    "effects": [
                        {
                            "type": "notify",
                            "argsMapping": {
                                "kind": "invite",
                                "invitees": "${context.eligibleResponders}",
                            },
                        }
                    ],
                    "transition": "S2_WAIT_RESPONSES",
                },
                "events": {
                    "AbortByOwner": _abort_event(),
                },
            },
            "S2_WAIT_RESPONSES": {
                "events": {
                    "UserResponse": {
                        "path": "respond",
                        "method": "POST",
                        "payloadSchema": {
                            "type": "object",
                            "properties": {
                                "userId": {"type": "string"},
                                "choice": {
                                    "type": "string",
                                    "enum": ["accept", "reject"],
                                },
                            },
                            "required": ["userId", "choice"],
                        },
                        "allowedRoles": ["g:anonymous"],
                        "allowedActorsContextPath": "eligibleResponders",
                        "dedupKey": "${payload.userId}",
                        "contextUpdate": {
                            "byValue": {
                                "value": "${payload.choice}",
                                "cases": {
                                    "accept": {
                                        "inc": {
                                            "acceptedCount": 1,
                                            "respondedCount": 1,
                                        },
                                        "pushUnique": {
                                            "acceptedUsers": "${payload.userId}",
                                            "respondedUsers": "${payload.userId}",
                                        },
                                    },
                                    "reject": {
                                        "inc": {
                                            "rejectedCount": 1,
                                            "respondedCount": 1,
                                        },
                                        "pushUnique": {
                                            "rejectedUsers": "${payload.userId}",
                                            "respondedUsers": "${payload.userId}",
                                        },
                                    },
                                },
                            }
                        },
                        "effects": [
                            {
                                "type": "notify",
                                "argsMapping": {
                                    "kind": "response",
                                    "userId": "${payload.userId}",
                                    "choice": "${payload.choice}",
                                    "ownerId": "${context.ownerId}",
                                },
                            }
                        ],
                        "transitions": [
                            {
                                "condition": {
                                    "gte": {"var": "$ctx.rejectedCount", "value": 2}
                                },
                                "target": "S_FINAL_REJECTED_QUORUM_STEP2",
                            },
                            {
                                "condition": {
                                    "gte": {"var": "$ctx.acceptedCount", "value": 3}
                                },
                                "target": "S2B_OWNER_VERIFY",
                            },
                            {
                                "condition": {
                                    "gte": {"var": "$ctx.respondedCount", "value": 3}
                                },
                                "target": "S_FINAL_NOT_ENOUGH_ACCEPTS_STEP2",
                            },
                        ],
                    },
                    "RejectByUser": {
                        "path": "reject",
                        "method": "POST",
                        "payloadSchema": {
                            "type": "object",
                            "properties": {
                                "userId": {"type": "string"},
                                "reason": {"type": "string"},
                            },
                            "required": ["userId"],
                        },
                        "allowedRoles": ["g:anonymous"],
                        "allowedActorsContextPath": "eligibleResponders",
                        "dedupKey": "${payload.userId}",
                        "contextUpdate": {
                            "byValue": {
                                "value": "reject",
                                "cases": {
                                    "reject": {
                                        "inc": {
                                            "rejectedCount": 1,
                                            "respondedCount": 1,
                                        },
                                        "pushUnique": {
                                            "rejectedUsers": "${payload.userId}",
                                            "respondedUsers": "${payload.userId}",
                                        },
                                    }
                                },
                            }
                        },
                        "effects": [
                            {
                                "type": "notify",
                                "argsMapping": {
                                    "kind": "reject",
                                    "userId": "${payload.userId}",
                                    "ownerId": "${context.ownerId}",
                                },
                            }
                        ],
                        "defaultTarget": "S_FINAL_REJECTED_QUORUM_STEP2",
                    },
                    "AbortByOwner": _abort_event(),
                },
            },
            "S2B_OWNER_VERIFY": {
                "events": {
                    "OwnerVerify": {
                        "path": "verify",
                        "method": "POST",
                        "payloadSchema": {
                            "type": "object",
                            "properties": {
                                "approvedUsers": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "verifiedCount": {"type": "integer"},
                            },
                            "required": ["approvedUsers", "verifiedCount"],
                        },
                        "allowedRoles": ["g:anonymous"],
                        "contextUpdate": {
                            "set": {
                                "verifiedUsers": "${payload.approvedUsers}",
                                "verifiedCount": "${payload.verifiedCount}",
                            }
                        },
                        "transitions": [
                            {
                                "condition": {
                                    "gte": {"var": "$ctx.verifiedCount", "value": 3}
                                },
                                "target": "S3_CREATE_GROUP",
                            }
                        ],
                    },
                    "OwnerReject": {
                        "path": "owner_reject",
                        "method": "POST",
                        "payloadSchema": {
                            "type": "object",
                            "properties": {"reason": {"type": "string"}},
                        },
                        "allowedRoles": ["g:anonymous"],
                        "effects": [
                            {
                                "type": "notify",
                                "argsMapping": {
                                    "kind": "owner_reject",
                                    "ownerId": "${context.ownerId}",
                                },
                            }
                        ],
                        "defaultTarget": "S_FINAL_OWNER_REJECTED_STEP2B",
                    },
                    "AbortByOwner": _abort_event(),
                }
            },
            "S3_CREATE_GROUP": {
                "onEnter": {
                    "effects": [
                        {
                            "type": "db_create_group",
                            "argsMapping": {
                                "ownerId": "${context.ownerId}",
                                "members": "${context.verifiedUsers}",
                            },
                        }
                    ],
                    "transition": "S4_SCHEDULE_CHECKIN",
                },
                "events": {
                    "AbortByOwner": _abort_event(),
                    "RejectBySystem": {
                        "path": "__system__/reject",
                        "method": "POST",
                        "allowedRoles": ["g:anonymous"],
                        "payloadSchema": {"type": "object"},
                        "defaultTarget": "S_FINAL_SYSTEM_REJECTED_STEP3",
                    },
                },
            },
            "S4_SCHEDULE_CHECKIN": {
                "onEnter": {
                    "effects": [
                        {
                            "type": "timer.schedule",
                            "argsMapping": {
                                "contractId": "${context.contractId}",
                                "name": "checkin",
                                "fireAt": "${context.nextCheckinAt}",
                                "event": "CheckinTimeReached",
                                "path": "/__timer__/checkin",
                                "payload": {},
                            },
                        }
                    ]
                },
                "events": {
                    "CheckinTimeReached": {
                        "path": "__timer__/checkin",
                        "method": "POST",
                        "allowedRoles": ["g:anonymous"],
                        "payloadSchema": {"type": "object"},
                        "defaultTarget": "S4B_SEND_CHECKIN",
                    },
                    "AbortByOwner": _abort_event(),
                    "RejectBySystem": {
                        "path": "__system__/reject",
                        "method": "POST",
                        "allowedRoles": ["g:anonymous"],
                        "payloadSchema": {"type": "object"},
                        "defaultTarget": "S_FINAL_SYSTEM_REJECTED_STEP4",
                    },
                },
            },
            "S4B_SEND_CHECKIN": {
                "onEnter": {
                    "effects": [
                        {
                            "type": "notify",
                            "argsMapping": {
                                "kind": "checkin",
                                "users": "${context.verifiedUsers}",
                            },
                        }
                    ]
                },
                "events": {
                    "UserConfirmation": {
                        "path": "confirm",
                        "method": "POST",
                        "payloadSchema": {
                            "type": "object",
                            "properties": {
                                "userId": {"type": "string"},
                                "answer": {"type": "string", "enum": ["yes", "no"]},
                            },
                            "required": ["userId", "answer"],
                        },
                        "allowedRoles": ["g:anonymous"],
                        "allowedActorsContextPath": "verifiedUsers",
                        "dedupKey": "${payload.userId}",
                        "contextUpdate": {
                            "byValue": {
                                "value": "${payload.answer}",
                                "cases": {
                                    "yes": {
                                        "inc": {"confirmedCount": 1},
                                        "pushUnique": {
                                            "confirmedYes": "${payload.userId}"
                                        },
                                    },
                                    "no": {
                                        "inc": {"confirmedNoCount": 1},
                                        "pushUnique": {
                                            "confirmedNo": "${payload.userId}"
                                        },
                                    },
                                },
                            }
                        },
                        "transitions": [
                            {
                                "condition": {
                                    "gte": {"var": "$ctx.confirmedNoCount", "value": 1}
                                },
                                "target": "S_FINAL_NEGATIVE_CHECKIN",
                            },
                            {
                                "condition": {
                                    "gte": {"var": "$ctx.confirmedCount", "value": 3}
                                },
                                "target": "S_FINAL_POSITIVE_CHECKIN",
                            },
                        ],
                    },
                    "UserReject": {
                        "path": "reject",
                        "method": "POST",
                        "payloadSchema": {
                            "type": "object",
                            "properties": {
                                "userId": {"type": "string"},
                                "reason": {"type": "string"},
                            },
                            "required": ["userId"],
                        },
                        "allowedRoles": ["g:anonymous"],
                        "allowedActorsContextPath": "verifiedUsers",
                        "dedupKey": "${payload.userId}",
                        "effects": [
                            {
                                "type": "notify",
                                "argsMapping": {
                                    "kind": "user_reject",
                                    "userId": "${payload.userId}",
                                },
                            }
                        ],
                        "defaultTarget": "S_FINAL_USER_REJECTED_STEP4B",
                    },
                    "AbortByOwner": _abort_event(),
                },
            },
            "S_FINAL_OWNER_ABORTED": {"final": True},
            "S_FINAL_REJECTED_QUORUM_STEP2": {"final": True},
            "S_FINAL_NOT_ENOUGH_ACCEPTS_STEP2": {"final": True},
            "S_FINAL_OWNER_REJECTED_STEP2B": {"final": True},
            "S_FINAL_SYSTEM_REJECTED_STEP3": {"final": True},
            "S_FINAL_SYSTEM_REJECTED_STEP4": {"final": True},
            "S_FINAL_NEGATIVE_CHECKIN": {"final": True},
            "S_FINAL_POSITIVE_CHECKIN": {"final": True},
            "S_FINAL_USER_REJECTED_STEP4B": {"final": True},
        },
    }


def _base_context() -> Dict[str, Any]:
    return {
        "ownerId": "owner-1",
        "eligibleResponders": ["u1", "u2", "u3"],
        "eligibleCount": 3,
        "acceptedCount": 0,
        "rejectedCount": 0,
        "respondedCount": 0,
        "acceptedUsers": [],
        "rejectedUsers": [],
        "respondedUsers": [],
        "verifiedUsers": [],
        "verifiedCount": 0,
        "confirmedCount": 0,
        "confirmedNoCount": 0,
        "confirmedYes": [],
        "confirmedNo": [],
        "penaltyCredits": 10,
        "nextCheckinAt": _iso(now_utc() + dt.timedelta(hours=1)),
    }


class ContractsE2ETest(unittest.TestCase):
    def setUp(self) -> None:
        os.environ.pop("MONGO_URI", None)
        self.app = Flask("schedula_contracts_test")
        self.mm_client = mongomock.MongoClient()
        mm_db = self.mm_client["schedula_test"]
        vdb = ValidatingMongoDatabase(mm_db)
        config = dict(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI="sqlite+pysqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            SECURITY_ENABLED=False,
            LOGIN_DISABLED=True,
            ITEMS_STORAGE_ENABLED=True,
            FILES_STORAGE_ENABLED=False,
            S3_ITEMS_FILE_STORAGE=False,
            CONTACT_ENABLED=False,
            SCHEDULA_CREDITS_ENABLED=False,
            SCHEDULA_EXPORT_FORM_ENABLED=False,
            SCHEDULA_GDPR_ENABLED=False,
            SCHEDULA_LOCALE_ENABLED=False,
            SCHEDULA_SECRETS_ENABLED=False,
            OPENAPI_ENABLED=False,
            CASBIN_ADMIN_ENABLED=False,
            MONGO_URI="mongodb://mock",
            MONGO_DB=vdb,
            CONTRACTS_DISABLE_IDEMPOTENCY_INDEX=True,
        )
        sitemap = DummySitemap()
        basic_app(sitemap, self.app, config)
        if not hasattr(self.app, "login_manager"):

            class _LM:
                @staticmethod
                def _load_user():
                    return None

            setattr(self.app, "login_manager", _LM())

        from schedula.utils.form.server.contracts import routes as contracts_routes

        self._orig_get_auth_sub = contracts_routes.get_auth_sub
        contracts_routes.get_auth_sub = lambda: "u:owner-1"

        with self.app.app_context():
            _db.create_all()
            self.app.config["CONTRACTS_ACTION_TYPES"] = [
                "notify",
                "db_create_group",
                "timer.schedule",
                "charge_credits",
                "http.request",
            ]
            enforcer = get_enforcer()
            enforcer.add_policy(
                [ANON_USER, ADMIN_DOMAIN, "contracts:templates", "manage", "allow"]
            )
            reg = get_registry()
            reg.register("notify", lambda payload: None, schema={})
            reg.register("db_create_group", lambda payload: None, schema={})
            reg.register("charge_credits", lambda payload: None, schema={})
            reg.register(
                "http.request",
                lambda payload: {"response": {"data": {"status": "ok"}}},
                schema={},
            )

            def _timer_schedule(payload: Dict[str, Any]) -> None:
                timers = get_mongo(collection="contract_timers")
                fire_at_raw = payload.get("fireAt")
                fire_at = None
                if isinstance(fire_at_raw, str):
                    try:
                        fire_at = dt.datetime.fromisoformat(fire_at_raw)
                    except ValueError:
                        fire_at = None
                timers.insert_one(
                    {
                        "_id": str(uuid.uuid4()),
                        "contract_id": payload.get("contractId"),
                        "timer_name": payload.get("name"),
                        "fire_at": fire_at,
                        "event_name": payload.get("event"),
                        "path": payload.get("path"),
                        "payload": payload.get("payload") or {},
                        "status": "SCHEDULED",
                        "created_at": now_utc(),
                    }
                )

            reg.register("timer.schedule", _timer_schedule, schema={})

        self.httpx = httpx.Client(
            transport=httpx.WSGITransport(app=self.app),
            base_url="http://test",
        )

    def tearDown(self) -> None:
        try:
            self.httpx.close()
        except Exception:
            pass
        with self.app.app_context():
            _db.session.remove()
            _db.drop_all()
        try:
            from schedula.utils.form.server.contracts import routes as contracts_routes

            if hasattr(self, "_orig_get_auth_sub"):
                contracts_routes.get_auth_sub = self._orig_get_auth_sub
        except Exception:
            pass
        try:
            self.mm_client.close()
        except Exception:
            pass

    def _post_event(
        self,
        contract_id: str,
        path: str,
        *,
        payload: Dict[str, Any],
        event_id: str | None = None,
        if_match: str | None = None,
        **_ignored: Any,
    ) -> httpx.Response:
        headers: Dict[str, str] = {}
        if if_match:
            headers["If-Match"] = if_match
        body = {"eventId": event_id or str(uuid.uuid4()), "payload": payload}
        return self.httpx.post(
            f"/contracts/{contract_id}/{path}", json=body, headers=headers
        )

    def _outbox_effects(self, contract_id: str) -> List[Dict[str, Any]]:
        with self.app.app_context():
            coll = get_mongo(collection="outbox_effects")
            return list(coll.find({"contract_id": contract_id}))

    def test_success_negative_checkin(self) -> None:
        definition = _definition()
        resp = self.httpx.post("/contracts/validate", json={"definition": definition})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["valid"])

        create = self.httpx.post(
            "/contracts",
            json={
                "definition": definition,
                "context": _base_context(),
                "ownerId": "owner-1",
                "metadata": {"name": "test"},
            },
        )
        self.assertEqual(create.status_code, 201)
        contract = create.json()
        contract_id = contract["id"]
        self.assertEqual(contract["state"], "S2_WAIT_RESPONSES")

        not_allowed = self._post_event(
            contract_id,
            "verify",
            actor_id="owner-1",
            role="owner",
            payload={"approvedUsers": [], "verifiedCount": 0},
        )
        self.assertEqual(not_allowed.status_code, 409)

        not_allowed_confirm = self._post_event(
            contract_id,
            "confirm",
            actor_id="u1",
            role="user",
            payload={"userId": "u1", "answer": "yes"},
        )
        self.assertEqual(not_allowed_confirm.status_code, 409)

        bad_lock = self._post_event(
            contract_id,
            "respond",
            actor_id="u1",
            role="user",
            payload={"userId": "u1", "choice": "accept"},
            if_match="999",
        )
        self.assertEqual(bad_lock.status_code, 409)

        r1 = self._post_event(
            contract_id,
            "respond",
            actor_id="u1",
            role="user",
            payload={"userId": "u1", "choice": "accept"},
        )
        self.assertEqual(r1.status_code, 200)

        dup_same = self._post_event(
            contract_id,
            "respond",
            actor_id="u1",
            role="user",
            payload={"userId": "u1", "choice": "accept"},
        )
        self.assertEqual(dup_same.status_code, 200)

        dup_diff = self._post_event(
            contract_id,
            "respond",
            actor_id="u1",
            role="user",
            payload={"userId": "u1", "choice": "reject"},
        )
        self.assertEqual(dup_diff.status_code, 409)

        r2 = self._post_event(
            contract_id,
            "respond",
            actor_id="u2",
            role="user",
            payload={"userId": "u2", "choice": "accept"},
        )
        self.assertEqual(r2.status_code, 200)
        r3 = self._post_event(
            contract_id,
            "respond",
            actor_id="u3",
            role="user",
            payload={"userId": "u3", "choice": "accept"},
        )
        self.assertEqual(r3.status_code, 200)
        self.assertEqual(r3.json()["state"], "S2B_OWNER_VERIFY")

        effects = self._outbox_effects(contract_id)
        notify_u1_accept = [
            e
            for e in effects
            if e.get("effect_type") == "notify"
            and (e.get("payload") or {}).get("userId") == "u1"
            and (e.get("payload") or {}).get("choice") == "accept"
        ]
        self.assertEqual(len(notify_u1_accept), 1)

        verify = self._post_event(
            contract_id,
            "verify",
            actor_id="owner-1",
            role="owner",
            payload={"approvedUsers": ["u1", "u2", "u3"], "verifiedCount": 3},
        )
        self.assertEqual(verify.status_code, 200)
        self.assertEqual(verify.json()["state"], "S4_SCHEDULE_CHECKIN")

        timers = self.httpx.get(f"/contracts/{contract_id}/timers")
        self.assertEqual(timers.status_code, 200)
        self.assertEqual(timers.json()["timers"][0]["timerName"], "checkin")

        fired = self.httpx.post(f"/contracts/{contract_id}/timers/checkin/fire")
        self.assertEqual(fired.status_code, 200)
        self.assertEqual(fired.json()["event"]["state"], "S4B_SEND_CHECKIN")

        c1 = self._post_event(
            contract_id,
            "confirm",
            actor_id="u1",
            role="user",
            payload={"userId": "u1", "answer": "yes"},
        )
        self.assertEqual(c1.status_code, 200)

        c2 = self._post_event(
            contract_id,
            "confirm",
            actor_id="u2",
            role="user",
            payload={"userId": "u2", "answer": "no"},
        )
        self.assertEqual(c2.status_code, 200)
        self.assertEqual(c2.json()["state"], "S_FINAL_NEGATIVE_CHECKIN")
        self.assertEqual(c2.json()["status"], "DONE")

        history = self.httpx.get(f"/contracts/{contract_id}/history")
        self.assertEqual(history.status_code, 200)
        h = history.json()
        self.assertGreaterEqual(len(h["events"]), 1)
        self.assertGreaterEqual(len(h["transitions"]), 1)
        self.assertGreaterEqual(len(h["effects"]), 1)

    def test_rejected_quorum_step2(self) -> None:
        definition = _definition()
        create = self.httpx.post(
            "/contracts",
            json={
                "definition": definition,
                "context": _base_context(),
                "ownerId": "owner-1",
                "metadata": {"name": "test"},
            },
        )
        contract_id = create.json()["id"]

        r1 = self._post_event(
            contract_id,
            "respond",
            actor_id="u1",
            role="user",
            payload={"userId": "u1", "choice": "reject"},
        )
        self.assertEqual(r1.status_code, 200)
        r2 = self._post_event(
            contract_id,
            "respond",
            actor_id="u2",
            role="user",
            payload={"userId": "u2", "choice": "reject"},
        )
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.json()["state"], "S_FINAL_REJECTED_QUORUM_STEP2")

        dup = self._post_event(
            contract_id,
            "respond",
            actor_id="u1",
            role="user",
            payload={"userId": "u1", "choice": "reject"},
        )
        self.assertEqual(dup.status_code, 200)

        effects = self._outbox_effects(contract_id)
        notify_u1_reject = [
            e
            for e in effects
            if e.get("effect_type") == "notify"
            and (e.get("payload") or {}).get("userId") == "u1"
            and (e.get("payload") or {}).get("choice") == "reject"
        ]
        self.assertEqual(len(notify_u1_reject), 1)

        further = self._post_event(
            contract_id,
            "respond",
            actor_id="u3",
            role="user",
            payload={"userId": "u3", "choice": "accept"},
        )
        self.assertEqual(further.status_code, 410)

    def test_owner_reject_step2b(self) -> None:
        definition = _definition()
        create = self.httpx.post(
            "/contracts",
            json={
                "definition": definition,
                "context": _base_context(),
                "ownerId": "owner-1",
                "metadata": {"name": "test"},
            },
        )
        contract_id = create.json()["id"]

        last_resp = None
        for uid in ("u1", "u2", "u3"):
            last_resp = self._post_event(
                contract_id,
                "respond",
                actor_id=uid,
                role="user",
                payload={"userId": uid, "choice": "accept"},
            )
            self.assertEqual(last_resp.status_code, 200)

        if last_resp is None:
            self.fail("No response captured for step2 accepts")
        self.assertEqual(last_resp.json()["state"], "S2B_OWNER_VERIFY")

        reject = self._post_event(
            contract_id,
            "owner_reject",
            actor_id="owner-1",
            role="owner",
            payload={"reason": "nope"},
        )
        self.assertEqual(reject.status_code, 200)
        self.assertEqual(reject.json()["state"], "S_FINAL_OWNER_REJECTED_STEP2B")

        effects = self._outbox_effects(contract_id)
        owner_reject_notify = [
            e
            for e in effects
            if e.get("effect_type") == "notify"
            and (e.get("payload") or {}).get("kind") == "owner_reject"
        ]
        self.assertGreaterEqual(len(owner_reject_notify), 1)

        further = self._post_event(
            contract_id,
            "respond",
            actor_id="u1",
            role="user",
            payload={"userId": "u1", "choice": "accept"},
        )
        self.assertEqual(further.status_code, 200)

    def test_owner_abort_penalty(self) -> None:
        definition = _definition()

        def _create() -> str:
            resp = self.httpx.post(
                "/contracts",
                json={
                    "definition": definition,
                    "context": _base_context(),
                    "ownerId": "owner-1",
                    "metadata": {"name": "test"},
                },
            )
            return resp.json()["id"]

        contract_id = _create()
        abort1 = self._post_event(
            contract_id,
            "abort",
            actor_id="owner-1",
            role="owner",
            payload={},
        )
        self.assertEqual(abort1.status_code, 200)
        self.assertEqual(abort1.json()["state"], "S_FINAL_OWNER_ABORTED")
        self.assertEqual(abort1.json()["status"], "DONE")

        effects = self._outbox_effects(contract_id)
        charge = [
            e
            for e in effects
            if e.get("effect_type") == "charge_credits"
            and (e.get("payload") or {}).get("ownerId") == "owner-1"
        ]
        self.assertEqual(len(charge), 1)
        self.assertEqual((charge[0].get("payload") or {}).get("amount"), 10)
        self.assertIn("owner_abort", (charge[0].get("payload") or {}).get("reason", ""))

        history = self.httpx.get(f"/contracts/{contract_id}/history")
        self.assertEqual(history.status_code, 200)
        self.assertGreaterEqual(len(history.json()["events"]), 1)
        self.assertGreaterEqual(len(history.json()["effects"]), 1)

        contract_id2 = _create()
        for uid in ("u1", "u2", "u3"):
            resp = self._post_event(
                contract_id2,
                "respond",
                actor_id=uid,
                role="user",
                payload={"userId": uid, "choice": "accept"},
            )
            self.assertEqual(resp.status_code, 200)

        verify = self._post_event(
            contract_id2,
            "verify",
            actor_id="owner-1",
            role="owner",
            payload={"approvedUsers": ["u1", "u2", "u3"], "verifiedCount": 3},
        )
        self.assertEqual(verify.status_code, 200)
        self.assertEqual(verify.json()["state"], "S4_SCHEDULE_CHECKIN")

        abort2 = self._post_event(
            contract_id2,
            "abort",
            actor_id="owner-1",
            role="owner",
            payload={},
        )
        self.assertEqual(abort2.status_code, 200)
        self.assertEqual(abort2.json()["state"], "S_FINAL_OWNER_ABORTED")
        self.assertEqual(abort2.json()["status"], "DONE")

        effects2 = self._outbox_effects(contract_id2)
        charge2 = [
            e
            for e in effects2
            if e.get("effect_type") == "charge_credits"
            and (e.get("payload") or {}).get("ownerId") == "owner-1"
        ]
        self.assertEqual(len(charge2), 1)

    def test_contract_templates_admin_and_available(self) -> None:
        definition = _definition()
        create = self.httpx.post(
            "/contracts/templates",
            json={
                "name": "Template A",
                "description": "Base template",
                "definition": definition,
                "isEnabled": True,
                "isPublic": True,
                "metadata": {"kind": "demo"},
            },
        )
        self.assertEqual(create.status_code, 201)
        tmpl = create.json()
        template_id = tmpl["id"]

        listed = self.httpx.get("/contracts/templates")
        self.assertEqual(listed.status_code, 200)
        ids = [t.get("id") for t in listed.json().get("templates", [])]
        self.assertIn(template_id, ids)

        get_one = self.httpx.get(f"/contracts/templates/{template_id}")
        self.assertEqual(get_one.status_code, 200)
        self.assertEqual(get_one.json().get("id"), template_id)

        available = self.httpx.get("/contracts/templates/available")
        self.assertEqual(available.status_code, 200)
        avail_ids = [t.get("id") for t in available.json().get("templates", [])]
        self.assertIn(template_id, avail_ids)

        disable = self.httpx.put(
            f"/contracts/templates/{template_id}",
            json={"isEnabled": False},
        )
        self.assertEqual(disable.status_code, 200)
        available_after = self.httpx.get("/contracts/templates/available")
        self.assertEqual(available_after.status_code, 200)
        avail_after_ids = [
            t.get("id") for t in available_after.json().get("templates", [])
        ]
        self.assertNotIn(template_id, avail_after_ids)

        create_from_disabled = self.httpx.post(
            f"/contracts/templates/{template_id}/contracts",
            json={
                "context": _base_context(),
                "ownerId": "owner-1",
                "metadata": {"name": "test"},
            },
        )
        self.assertEqual(create_from_disabled.status_code, 409)

        enable = self.httpx.put(
            f"/contracts/templates/{template_id}",
            json={"isEnabled": True},
        )
        self.assertEqual(enable.status_code, 200)

        create_from_template = self.httpx.post(
            f"/contracts/templates/{template_id}/contracts",
            json={
                "context": _base_context(),
                "ownerId": "owner-1",
                "metadata": {"name": "from-template"},
            },
        )
        self.assertEqual(create_from_template.status_code, 201)
        self.assertIn("id", create_from_template.json())

        invalid = self.httpx.post(
            "/contracts/templates",
            json={"name": "", "definition": {}, "extra": True},
        )
        self.assertEqual(invalid.status_code, 422)

    def test_http_request_effect_save_response(self) -> None:
        definition = {
            "id": "http-ref",
            "version": "1.0",
            "initialState": "S1",
            "states": {
                "S1": {
                    "events": {
                        "Fetch": {
                            "path": "fetch",
                            "method": "POST",
                            "payloadSchema": {"type": "object"},
                            "allowedRoles": ["g:anonymous"],
                            "contextUpdate": {"$set": {"marker": "start"}},
                            "effects": [
                                {
                                    "type": "http.request",
                                    "args": {
                                        "method": "GET",
                                        "url": "https://api.example.com/profile",
                                    },
                                    "saveResponse": {
                                        "path": "/ctx/external.profile",
                                        "select": {"$ref": "/response/data"},
                                    },
                                }
                            ],
                            "defaultTarget": "S_FINAL",
                        }
                    }
                },
                "S_FINAL": {"final": True},
            },
        }

        create = self.httpx.post(
            "/contracts",
            json={
                "definition": definition,
                "context": {},
                "ownerId": "owner-1",
                "metadata": {"name": "http"},
            },
        )
        self.assertEqual(create.status_code, 201)
        contract_id = create.json()["id"]

        res = self._post_event(
            contract_id,
            "fetch",
            actor_id="u1",
            role="user",
            payload={},
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["state"], "S_FINAL")

        updated = self.httpx.get(f"/contracts/{contract_id}")
        self.assertEqual(updated.status_code, 200)
        ctx = updated.json().get("context") or {}
        self.assertEqual(ctx.get("marker"), "start")
        self.assertEqual(ctx.get("external", {}).get("profile"), {"status": "ok"})

    def test_context_update_pipeline_mongo_subset(self) -> None:
        definition = {
            "id": "pipeline",
            "version": "1.0",
            "initialState": "S1",
            "states": {
                "S1": {
                    "events": {
                        "Update": {
                            "path": "update",
                            "method": "POST",
                            "payloadSchema": {
                                "type": "object",
                                "properties": {"userId": {"type": "string"}},
                                "required": ["userId"],
                            },
                            "allowedRoles": ["g:anonymous"],
                            "contextUpdate": [
                                {"$set": {"status": "started", "temp": "x"}},
                                {"$inc": {"count": 1}},
                                {"$addToSet": {"users": {"$ref": "/payload/userId"}}},
                                {"$unset": {"temp": 1}},
                            ],
                            "defaultTarget": "S_FINAL",
                        }
                    }
                },
                "S_FINAL": {"final": True},
            },
        }

        create = self.httpx.post(
            "/contracts",
            json={
                "definition": definition,
                "context": {"count": 0, "users": []},
                "ownerId": "owner-1",
                "metadata": {"name": "pipeline"},
            },
        )
        self.assertEqual(create.status_code, 201)
        contract_id = create.json()["id"]

        res = self._post_event(
            contract_id,
            "update",
            actor_id="u1",
            role="user",
            payload={"userId": "u1"},
        )
        self.assertEqual(res.status_code, 200)

        updated = self.httpx.get(f"/contracts/{contract_id}")
        self.assertEqual(updated.status_code, 200)
        ctx = updated.json().get("context") or {}
        self.assertEqual(ctx.get("status"), "started")
        self.assertEqual(ctx.get("count"), 1)
        self.assertEqual(ctx.get("users"), ["u1"])
        self.assertNotIn("temp", ctx)
