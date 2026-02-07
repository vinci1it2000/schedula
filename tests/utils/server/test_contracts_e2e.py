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
from flask_security.utils import hash_password

from schedula.utils.form.server import basic_app
from schedula.utils.form.server.contracts.registry import get_registry
from schedula.utils.form.server.extensions import db as _db
from schedula.utils.form.server.security import User
from schedula.utils.form.server.security.casbin import get_enforcer
from schedula.utils.form.server.security.casbin.helpers import ADMIN_DOMAIN, ANON_USER
from schedula.utils.form.server.security.casbin.bootstrap import (
    bootstrap_user,
    set_system_admin,
)
from schedula.utils.form.server.security.casbin.models import ensure_public_group
from schedula.utils.form.server.utils import get_mongo, now_utc
from tests.utils.server.conftest import DummySitemap
from tests.utils.server.utils.mongo_validation import ValidatingMongoDatabase


def _iso(ts: dt.datetime) -> str:
    return ts.astimezone(dt.timezone.utc).isoformat()


def _abort_event():
    return {
        "path": "abort",
        "method": "POST",
        "allowedPrincipals": ["g:authenticated"],
        "payloadSchema": {"type": "object"},
        "effects": [
            {
                "type": "charge_credits",
                "argsMapping": {
                    "ownerId": {"$ctx": "ownerId"},
                    "amount": {"$ctx": "penaltyCredits"},
                    "reason": "owner_abort",
                },
            },
            {
                "type": "notify",
                "argsMapping": {
                    "kind": "owner_abort",
                    "ownerId": {"$ctx": "ownerId"},
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
                                "invitees": {"$ctx": "eligibleResponders"},
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
                        "allowedPrincipals": ["g:authenticated"],
                        "dedupKey": {"$ctx": "payload.userId"},
                        "effects": [
                            {
                                "type": "context.update",
                                "update": {
                                    "byValue": {
                                        "value": {"$ctx": "payload.choice"},
                                        "cases": {
                                            "accept": {
                                                "inc": {
                                                    "acceptedCount": 1,
                                                    "respondedCount": 1,
                                                },
                                                "pushUnique": {
                                                    "acceptedUsers": {
                                                        "$ctx": "payload.userId"
                                                    },
                                                    "respondedUsers": {
                                                        "$ctx": "payload.userId"
                                                    },
                                                },
                                            },
                                            "reject": {
                                                "inc": {
                                                    "rejectedCount": 1,
                                                    "respondedCount": 1,
                                                },
                                                "pushUnique": {
                                                    "rejectedUsers": {
                                                        "$ctx": "payload.userId"
                                                    },
                                                    "respondedUsers": {
                                                        "$ctx": "payload.userId"
                                                    },
                                                },
                                            },
                                        },
                                    }
                                },
                            },
                            {
                                "type": "notify",
                                "argsMapping": {
                                    "kind": "response",
                                    "userId": {"$ctx": "payload.userId"},
                                    "choice": {"$ctx": "payload.choice"},
                                    "ownerId": {"$ctx": "ownerId"},
                                },
                            },
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
                        "allowedPrincipals": ["g:authenticated"],
                        "dedupKey": {"$ctx": "payload.userId"},
                        "effects": [
                            {
                                "type": "context.update",
                                "update": {
                                    "byValue": {
                                        "value": "reject",
                                        "cases": {
                                            "reject": {
                                                "inc": {
                                                    "rejectedCount": 1,
                                                    "respondedCount": 1,
                                                },
                                                "pushUnique": {
                                                    "rejectedUsers": {
                                                        "$ctx": "payload.userId"
                                                    },
                                                    "respondedUsers": {
                                                        "$ctx": "payload.userId"
                                                    },
                                                },
                                            }
                                        },
                                    }
                                },
                            },
                            {
                                "type": "notify",
                                "argsMapping": {
                                    "kind": "reject",
                                    "userId": {"$ctx": "payload.userId"},
                                    "ownerId": {"$ctx": "ownerId"},
                                },
                            },
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
                        "allowedPrincipals": ["g:authenticated"],
                        "effects": [
                            {
                                "type": "context.update",
                                "update": {
                                    "set": {
                                        "verifiedUsers": {
                                            "$ctx": "payload.approvedUsers"
                                        },
                                        "verifiedCount": {
                                            "$ctx": "payload.verifiedCount"
                                        },
                                    }
                                },
                            }
                        ],
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
                        "allowedPrincipals": ["g:authenticated"],
                        "effects": [
                            {
                                "type": "notify",
                                "argsMapping": {
                                    "kind": "owner_reject",
                                    "ownerId": {"$ctx": "ownerId"},
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
                                "ownerId": {"$ctx": "ownerId"},
                                "members": {"$ctx": "verifiedUsers"},
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
                        "allowedPrincipals": ["g:authenticated"],
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
                                "contractId": {"$ctx": "contractId"},
                                "name": "checkin",
                                "fireAt": {"$ctx": "nextCheckinAt"},
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
                        "allowedPrincipals": ["g:authenticated"],
                        "payloadSchema": {"type": "object"},
                        "defaultTarget": "S4B_SEND_CHECKIN",
                    },
                    "AbortByOwner": _abort_event(),
                    "RejectBySystem": {
                        "path": "__system__/reject",
                        "method": "POST",
                        "allowedPrincipals": ["g:authenticated"],
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
                                "users": {"$ctx": "verifiedUsers"},
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
                        "allowedPrincipals": ["g:authenticated"],
                        "dedupKey": {"$ctx": "payload.userId"},
                        "effects": [
                            {
                                "type": "context.update",
                                "update": {
                                    "byValue": {
                                        "value": {"$ctx": "payload.answer"},
                                        "cases": {
                                            "yes": {
                                                "inc": {"confirmedCount": 1},
                                                "pushUnique": {
                                                    "confirmedYes": {
                                                        "$ctx": "payload.userId"
                                                    }
                                                },
                                            },
                                            "no": {
                                                "inc": {"confirmedNoCount": 1},
                                                "pushUnique": {
                                                    "confirmedNo": {
                                                        "$ctx": "payload.userId"
                                                    }
                                                },
                                            },
                                        },
                                    }
                                },
                            }
                        ],
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
                        "allowedPrincipals": ["g:authenticated"],
                        "dedupKey": {"$ctx": "payload.userId"},
                        "effects": [
                            {
                                "type": "notify",
                                "argsMapping": {
                                    "kind": "user_reject",
                                    "userId": {"$ctx": "payload.userId"},
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
            SECURITY_ENABLED=True,
            SECURITY_REGISTERABLE=True,
            SECURITY_SEND_REGISTER_EMAIL=False,
            SECURITY_CONFIRMABLE=True,
            SECURITY_RECOVERABLE=True,
            SECURITY_CHANGEABLE=True,
            SECURITY_LOGIN_AFTER_REGISTER=False,
            SECURITY_URL_PREFIX="/user",
            WTF_CSRF_ENABLED=False,
            SCHEDULA_CSRF_ENABLED=False,
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

        with self.app.app_context():
            _db.create_all()
            ensure_public_group()

            owner = self._create_user("owner-1@gmail.com")
            u1 = self._create_user("u1@gmail.com")
            u2 = self._create_user("u2@gmail.com")
            u3 = self._create_user("u3@gmail.com")
            admin = self._create_user("admin@gmail.com")

            for u in (owner, u1, u2, u3, admin):
                bootstrap_user(u.id)
            set_system_admin(admin.id, enabled=True)

            self.owner_sub = f"u:{owner.id}"
            self.actor_sub_map = {
                "owner-1": f"u:{owner.id}",
                "u1": f"u:{u1.id}",
                "u2": f"u:{u2.id}",
                "u3": f"u:{u3.id}",
                "admin": f"u:{admin.id}",
            }

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
        self.client = self.app.test_client(use_cookies=False)
        self.actor_token_map = {
            "owner-1": self._login_token("owner-1@gmail.com"),
            "u1": self._login_token("u1@gmail.com"),
            "u2": self._login_token("u2@gmail.com"),
            "u3": self._login_token("u3@gmail.com"),
            "admin": self._login_token("admin@gmail.com"),
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
            self.mm_client.close()
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
        else:
            user.password = hash_password("UserPass123!")
            user.active = True
            if not getattr(user, "fs_uniquifier", None):
                user.fs_uniquifier = str(uuid.uuid4())
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

    def _auth_headers(self, actor: str) -> Dict[str, str]:
        token = self.actor_token_map.get(actor)
        self.assertIsNotNone(token)
        return {"Authentication-Token": str(token)}

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
        actor_id = _ignored.get("actor_id")
        actor = actor_id if isinstance(actor_id, str) and actor_id else "owner-1"
        headers: Dict[str, str] = dict(self._auth_headers(actor))
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

    def _create_contract(
        self,
        *,
        definition: Dict[str, Any],
        context: Dict[str, Any],
        actor: str = "owner-1",
        name: str = "test",
    ) -> Dict[str, Any]:
        t = self.httpx.post(
            "/contracts/templates",
            json={
                "name": f"tmpl-{uuid.uuid4()}",
                "description": "auto",
                "definition": definition,
                "isEnabled": True,
                "isPublic": True,
                "metadata": {"name": name},
            },
            headers=self._auth_headers("admin"),
        )
        self.assertEqual(t.status_code, 201)
        template_id = t.json()["id"]
        c = self.httpx.post(
            "/contracts",
            json={"templateId": template_id, "context": context},
            headers=self._auth_headers(actor),
        )
        self.assertEqual(c.status_code, 201)
        return c.json()

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
            headers=self._auth_headers("owner-1"),
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
            headers=self._auth_headers("owner-1"),
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
            headers=self._auth_headers("owner-1"),
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
        self.assertEqual(further.status_code, 410)

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
                headers=self._auth_headers("owner-1"),
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
            headers=self._auth_headers("admin"),
        )
        self.assertEqual(create.status_code, 201)
        tmpl = create.json()
        template_id = tmpl["id"]

        listed = self.httpx.get(
            "/contracts/templates", headers=self._auth_headers("admin")
        )
        self.assertEqual(listed.status_code, 200)
        ids = [t.get("id") for t in listed.json().get("templates", [])]
        self.assertIn(template_id, ids)

        get_one = self.httpx.get(
            f"/contracts/templates/{template_id}", headers=self._auth_headers("admin")
        )
        self.assertEqual(get_one.status_code, 200)
        self.assertEqual(get_one.json().get("id"), template_id)

        available = self.httpx.get(
            "/contracts/templates/available", headers=self._auth_headers("owner-1")
        )
        self.assertEqual(available.status_code, 200)
        avail_ids = [t.get("id") for t in available.json().get("templates", [])]
        self.assertIn(template_id, avail_ids)

        disable = self.httpx.put(
            f"/contracts/templates/{template_id}",
            json={"isEnabled": False},
            headers=self._auth_headers("admin"),
        )
        self.assertEqual(disable.status_code, 200)
        available_after = self.httpx.get(
            "/contracts/templates/available", headers=self._auth_headers("owner-1")
        )
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
            headers=self._auth_headers("owner-1"),
        )
        self.assertEqual(create_from_disabled.status_code, 409)

        enable = self.httpx.put(
            f"/contracts/templates/{template_id}",
            json={"isEnabled": True},
            headers=self._auth_headers("admin"),
        )
        self.assertEqual(enable.status_code, 200)

        create_from_template = self.httpx.post(
            f"/contracts/templates/{template_id}/contracts",
            json={
                "context": _base_context(),
                "ownerId": "owner-1",
                "metadata": {"name": "from-template"},
            },
            headers=self._auth_headers("owner-1"),
        )
        self.assertEqual(create_from_template.status_code, 201)
        self.assertIn("id", create_from_template.json())

        invalid = self.httpx.post(
            "/contracts/templates",
            json={"name": "", "definition": {}, "extra": True},
            headers=self._auth_headers("admin"),
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
                            "allowedPrincipals": ["g:authenticated"],
                            "effects": [
                                {
                                    "type": "context.update",
                                    "update": {"$set": {"marker": "start"}},
                                },
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
                                },
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
            headers=self._auth_headers("owner-1"),
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
                            "allowedPrincipals": ["g:authenticated"],
                            "effects": [
                                {
                                    "type": "context.update",
                                    "update": [
                                        {"$set": {"status": "started", "temp": "x"}},
                                        {"$inc": {"count": 1}},
                                        {
                                            "$addToSet": {
                                                "users": {"$ctx": "payload.userId"}
                                            }
                                        },
                                        {"$unset": {"temp": 1}},
                                    ],
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
                "context": {"count": 0, "users": []},
                "ownerId": "owner-1",
                "metadata": {"name": "pipeline"},
            },
            headers=self._auth_headers("owner-1"),
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
