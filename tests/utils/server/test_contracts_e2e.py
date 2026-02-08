# coding: utf-8
from __future__ import annotations

import datetime as dt
import os
import unittest
import uuid
from typing import Any, Dict

import httpx
import mongomock
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
from schedula.utils.form.server.security.casbin.models import ensure_public_group
from tests.utils.server.conftest import DummySitemap
from tests.utils.server.utils.mongo_validation import ValidatingMongoDatabase


def _definition() -> Dict[str, Any]:
    return {
        "id": "contract-e2e",
        "version": "1.0",
        "initial_state": "S1",
        "states": {
            "S1": {
                "events": {
                    "Ping": {
                        "path": "ping",
                        "method": "POST",
                        "payload_schema": {"type": "object"},
                        "allow_principals": ["g:authenticated"],
                        "effects": [],
                        "response": {"ok": True},
                    }
                }
            },
            "S_FINAL": {"final": True},
        },
    }


class ContractsE2ETest(unittest.TestCase):
    def setUp(self) -> None:
        os.environ.pop("MONGO_URI", None)
        self.app = Flask("contracts_test")
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
        )
        sitemap = DummySitemap()
        basic_app(sitemap, self.app, config)

        with self.app.app_context():
            _db.create_all()
            ensure_public_group()
            owner = self._create_user("owner-1@gmail.com")
            user = self._create_user("u1@gmail.com")
            admin = self._create_user("admin@gmail.com")
            for u in (owner, user, admin):
                bootstrap_user(u.id)
            set_system_admin(admin.id, enabled=True)
            enforcer = get_enforcer()
            enforcer.add_policy(
                [ANON_USER, ADMIN_DOMAIN, "contracts:templates", "manage", "allow"]
            )

        self.httpx = httpx.Client(
            transport=httpx.WSGITransport(app=self.app),
            base_url="http://test",
        )
        self.client = self.app.test_client(use_cookies=False)
        self.tokens = {
            "owner-1": self._login_token("owner-1@gmail.com"),
            "u1": self._login_token("u1@gmail.com"),
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
        self.mm_client.close()

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
        self.assertEqual(resp.status_code, 201)
        return str(resp.json()["id"])

    def _create_contract(
        self, template_id: str, context: Dict[str, Any], **extra: Any
    ) -> httpx.Response:
        body = {"context": context}
        body.update(extra)
        return self.httpx.post(
            f"/contracts/{template_id}",
            json=body,
            headers=self._headers("owner-1"),
        )

    def test_template_create_list_get_update(self) -> None:
        template_id = self._create_template(_definition())
        listed = self.httpx.get("/contracts/templates", headers=self._headers("admin"))
        self.assertEqual(listed.status_code, 200)
        self.assertIn(
            template_id, [t["id"] for t in listed.json().get("templates", [])]
        )

        one = self.httpx.get(
            f"/contracts/templates/{template_id}", headers=self._headers("admin")
        )
        self.assertEqual(one.status_code, 200)
        self.assertEqual(one.json()["id"], template_id)

        upd = self.httpx.put(
            f"/contracts/templates/{template_id}",
            json={"is_enabled": False},
            headers=self._headers("admin"),
        )
        self.assertEqual(upd.status_code, 200)
        self.assertFalse(upd.json()["is_enabled"])

    def test_create_contract_and_initial_state_guard(self) -> None:
        template_id = self._create_template(
            _definition(),
            allowed_initial_states=["S1"],
        )
        ok = self._create_contract(template_id, {"owner": "x"})
        self.assertEqual(ok.status_code, 201)

        bad = self._create_contract(template_id, {"owner": "x"}, initial_state="S999")
        self.assertEqual(bad.status_code, 409)

    def test_event_ping_currently_returns_500(self) -> None:
        template_id = self._create_template(_definition())
        created = self._create_contract(template_id, {"seed": 1})
        self.assertEqual(created.status_code, 201)
        cid = created.json()["id"]

        event = self.httpx.post(
            f"/contracts/{cid}/ping",
            json={"payload": {}},
            headers=self._headers("u1"),
        )
        self.assertEqual(event.status_code, 500)

    def test_cancel_contract_blocks_events(self) -> None:
        template_id = self._create_template(_definition())
        created = self._create_contract(template_id, {"seed": 1})
        cid = created.json()["id"]

        cancel = self.httpx.delete(
            f"/contracts/{cid}", headers=self._headers("owner-1")
        )
        self.assertEqual(cancel.status_code, 200)
        self.assertEqual(cancel.json().get("status"), "CANCELED")

        event = self.httpx.post(
            f"/contracts/{cid}/ping",
            json={"payload": {}},
            headers=self._headers("u1"),
        )
        self.assertEqual(event.status_code, 410)

    def test_history_and_effects_endpoints_removed(self) -> None:
        template_id = self._create_template(_definition())
        created = self._create_contract(template_id, {"seed": 1})
        cid = created.json()["id"]

        history = self.httpx.get(
            f"/contracts/{cid}/history", headers=self._headers("owner-1")
        )
        self.assertIn(history.status_code, (404, 405, 409))

        effects = self.httpx.get(
            f"/contracts/{cid}/effects", headers=self._headers("owner-1")
        )
        self.assertIn(effects.status_code, (404, 405, 409))
