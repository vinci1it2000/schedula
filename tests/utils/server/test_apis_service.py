from __future__ import annotations

try:
    from tests.utils.server._unittest_guard import ensure_server_test_env
except Exception:
    from _unittest_guard import ensure_server_test_env

ensure_server_test_env()

import unittest
import uuid
from datetime import datetime

import mongomock
from flask_security.utils import hash_password

from schedula.utils.form.server import basic_app
from schedula.utils.form.server.extensions import db as _db
from schedula.utils.form.server.security import User
from schedula.utils.form.server.security.casbin import get_enforcer
from schedula.utils.form.server.security.casbin.bootstrap import (
    bootstrap_user,
    set_system_admin,
)
from tests.utils.server.utils.mongo_validation import ValidatingMongoDatabase


class TestApisService(unittest.TestCase):
    def setUp(self):
        from flask import Flask

        self.app = Flask("schedula_test_app")

        class DummySitemap:
            verify_file_handler = None
            basic_app_config = None

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
            MONGO_URI="mongodb://mock",
            MONGO_DB=vdb,
            ITEMS_STORAGE_ENABLED=False,
            FILES_STORAGE_ENABLED=False,
            S3_ITEMS_FILE_STORAGE=False,
            CONTACT_ENABLED=False,
            SCHEDULA_CREDITS_ENABLED=False,
            SCHEDULA_EXPORT_FORM_ENABLED=False,
            SCHEDULA_GDPR_ENABLED=False,
            SCHEDULA_LOCALE_ENABLED=False,
            SCHEDULA_SECRETS_ENABLED=False,
            OPENAPI_ENABLED=False,
            CASBIN_ADMIN_ENABLED=True,
            CONTRACTS_ENABLED=True,
            APIS_ENABLED=True,
        )

        self.app.config["MONGO_DB"] = vdb
        with self.app.app_context():
            basic_app(DummySitemap(), self.app, config)
            _db.create_all()

            self.admin_user = User(
                email="admin_apis@gmail.com",
                password=hash_password("AdminPass123!"),
                active=True,
                fs_uniquifier=str(uuid.uuid4()),
            )
            self.admin_user.confirmed_at = datetime.utcnow()
            self.user = User(
                email="user_apis@gmail.com",
                password=hash_password("UserPass123!"),
                active=True,
                fs_uniquifier=str(uuid.uuid4()),
            )
            self.user.confirmed_at = datetime.utcnow()
            _db.session.add(self.admin_user)
            _db.session.add(self.user)
            _db.session.commit()

            bootstrap_user(self.admin_user.id)
            bootstrap_user(self.user.id)
            set_system_admin(self.admin_user.id, enabled=True)

            enforcer = get_enforcer()
            enforcer.add_policy(
                [
                    f"u:{self.admin_user.id}",
                    "acl:admin",
                    "apis:templates",
                    "manage",
                    "allow",
                ]
            )

        self.client = self.app.test_client()
        self.admin_token = self._login_token("admin_apis@gmail.com", "AdminPass123!")
        self.user_token = self._login_token("user_apis@gmail.com", "UserPass123!")

    def tearDown(self):
        with self.app.app_context():
            _db.session.remove()
            _db.drop_all()
        if getattr(self, "mm_client", None) is not None:
            self.mm_client.close()

    def _login_token(self, email: str, password: str) -> str:
        login_client = self.app.test_client()
        resp = login_client.post(
            "/user/login", json={"email": email, "password": password}
        )
        self.assertEqual(resp.status_code, 200, msg=resp.get_data(as_text=True))
        data = resp.get_json(silent=True) or {}
        token = data.get("response", {}).get("user", {}).get("token")
        self.assertIsNotNone(token)
        return str(token)

    @staticmethod
    def _auth_headers(token: str) -> dict:
        return {"Authentication-Token": token}

    def test_apis_event_uses_temp_contract_and_cleans_up(self):
        template_payload = {
            "name": "api-template",
            "is_enabled": True,
            "definition": {
                "events": {
                    "Ping": {
                        "trigger": [
                            {
                                "type": "api",
                                "path": "ping",
                                "method": "POST",
                                "response": {
                                    "ok": True,
                                    "user": {"$ctx": "user"},
                                    "name": {"$ctx": "local.user"},
                                },
                            }
                        ],
                        "effects": [
                            {
                                "title": "Compute Settlement Totals",
                                "description": "Normalizes dispute payloads and computes per-rider settlement amounts.",
                                "type": "update.contract",
                                "update": [{"$set": {"local.user": "pippo"}}],
                            }
                        ],
                    }
                }
            },
        }

        r = self.client.post(
            "/apis/templates",
            json=template_payload,
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 201, msg=r.get_data(as_text=True))
        body = r.get_json(silent=True) or {}
        template_id = body.get("id")
        self.assertTrue(template_id)

        with self.app.app_context():
            self.assertEqual(
                self.app.config["MONGO_DB"]["api_templates"].count_documents({}), 1
            )
            self.assertEqual(
                self.app.config["MONGO_DB"]["contract_templates"].count_documents({}), 0
            )

        r = self.client.post(
            f"/apis/{template_id}/ping",
            json={"hello": "world"},
            headers=self._auth_headers(self.user_token),
        )
        self.assertEqual(r.status_code, 200, msg=r.get_data(as_text=True))
        res = r.get_json(silent=True) or {}
        self.assertEqual(res.get("ok"), True)
        self.assertEqual(res.get("name"), "pippo")
        self.assertEqual(res.get("user"), f"u:{self.user.id}")

        with self.app.app_context():
            self.assertEqual(self.app.config["MONGO_DB"]["apis"].count_documents({}), 0)
            self.assertEqual(
                self.app.config["MONGO_DB"]["contracts"].count_documents({}), 0
            )


if __name__ == "__main__":
    unittest.main()
