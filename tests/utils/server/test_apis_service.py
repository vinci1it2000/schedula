from __future__ import annotations

try:
    from tests.utils.server._unittest_guard import ensure_server_test_env
except Exception:
    from _unittest_guard import ensure_server_test_env

ensure_server_test_env()

import os
import unittest
import uuid
from copy import deepcopy
from datetime import datetime
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from flask_security.utils import hash_password

from schedula.utils.form.server import basic_app
from schedula.utils.form.server.extensions import db as _db
from tests.utils.server.utils.testcontainers_support import _ensure_docker_host, _wait_for_mongo, _wait_for_mysql
from schedula.utils.form.server.utils import now_utc
from schedula.utils.form.server.security import User
from schedula.utils.form.server.security.casbin import get_enforcer
from schedula.utils.form.server.security.casbin.bootstrap import (
    bootstrap_user,
    set_system_admin,
)
EVENTS_CUSTOM_TEMPLATE = {
    "name": "events-custom-apis",
    "description": "",
    "definition": {
        "id": "events-custom-apis",
        "version": "1.0",
        "events": {
            "JoinEvent": {
                "trigger": [
                    {
                        "type": "api",
                        "path": "join-event",
                        "method": "POST",
                        "payload_schema": {
                            "type": "object",
                            "required": ["item_id"],
                            "properties": {
                                "item_id": {"type": "string", "minLength": 1}
                            },
                            "additionalProperties": False,
                        },
                        "response": {
                            "ok": "$$ctx.local.join_ok",
                            "event": "join_event",
                        },
                    }
                ],
                "effects": [
                    {
                        "title": "Load Event Item",
                        "description": "Loads the item referenced by payload to verify it is an event.",
                        "type": "get.item",
                        "item_id": "$$ctx.payload.item_id",
                        "key": "event_item",
                    },
                    {
                        "title": "Check Event Category",
                        "description": "Validates item category before joining.",
                        "type": "update.contract",
                        "update": {
                            "$set": {
                                "local.is_event": {
                                    "$eq": [
                                        "$$ctx.local.event_item.data.category",
                                        "events",
                                    ]
                                }
                            }
                        },
                    },
                    {
                        "title": "Join Decision",
                        "description": "Updates item participation only if category is correct.",
                        "type": "if.else",
                        "condition": {"$ctx": "local.is_event"},
                        "then_effects": [
                            {
                                "title": "Add Participant",
                                "description": "Adds current user to event participants.",
                                "type": "update.item",
                                "item_id": "$$ctx.payload.item_id",
                                "update": {
                                    "$set": {
                                        "data.participants": {
                                            "$setUnion": [
                                                {"$ifNull": ["$data.participants", []]},
                                                ["$$ctx.user"],
                                            ]
                                        }
                                    }
                                },
                            },
                            {
                                "title": "Set Join Ok",
                                "description": "Marks join as successful.",
                                "type": "update.contract",
                                "update": {"$set": {"local.join_ok": True}},
                            },
                            {
                                "title": "Notify Event Owner Join",
                                "type": "notify",
                                "notify": {
                                    "event": "events.join_event",
                                    "targets": {
                                        "$$ctx.local.event_item.created_by": ["in_app"]
                                    },
                                    "payload": {
                                        "item_id": "$$ctx.payload.item_id",
                                        "actor": "$$ctx.user",
                                    },
                                },
                            },
                        ],
                        "else_effects": [
                            {
                                "title": "Set Join Failed",
                                "description": "Rejects join when item is not an event.",
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "local.join_ok": False,
                                        "local.join_error": "INVALID_CATEGORY",
                                    }
                                },
                            }
                        ],
                    },
                ],
            },
            "UnjoinEvent": {
                "trigger": [
                    {
                        "type": "api",
                        "path": "unjoin-event",
                        "method": "POST",
                        "payload_schema": {
                            "type": "object",
                            "required": ["item_id"],
                            "properties": {
                                "item_id": {"type": "string", "minLength": 1}
                            },
                            "additionalProperties": False,
                        },
                        "response": {
                            "ok": "$$ctx.local.unjoin_ok",
                            "event": "unjoin_event",
                        },
                    }
                ],
                "effects": [
                    {
                        "title": "Load Event Item",
                        "type": "get.item",
                        "item_id": "$$ctx.payload.item_id",
                        "key": "event_item",
                    },
                    {
                        "title": "Check Event Category",
                        "type": "update.contract",
                        "update": {
                            "$set": {
                                "local.is_event": {
                                    "$eq": [
                                        "$$ctx.local.event_item.data.category",
                                        "events",
                                    ]
                                }
                            }
                        },
                    },
                    {
                        "title": "Unjoin Decision",
                        "type": "if.else",
                        "condition": {"$ctx": "local.is_event"},
                        "then_effects": [
                            {
                                "title": "Remove Participant",
                                "type": "update.item",
                                "item_id": "$$ctx.payload.item_id",
                                "update": {
                                    "$set": {
                                        "data.participants": {
                                            "$setDifference": [
                                                {"$ifNull": ["$data.participants", []]},
                                                ["$$ctx.user"],
                                            ]
                                        }
                                    }
                                },
                            },
                            {
                                "title": "Set Unjoin Ok",
                                "type": "update.contract",
                                "update": {"$set": {"local.unjoin_ok": True}},
                            },
                            {
                                "title": "Notify Event Owner Unjoin",
                                "type": "notify",
                                "notify": {
                                    "event": "events.unjoin_event",
                                    "targets": {
                                        "$$ctx.local.event_item.created_by": ["in_app"]
                                    },
                                    "payload": {
                                        "item_id": "$$ctx.payload.item_id",
                                        "actor": "$$ctx.user",
                                    },
                                },
                            },
                        ],
                        "else_effects": [
                            {
                                "title": "Set Unjoin Failed",
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "local.unjoin_ok": False,
                                        "local.unjoin_error": "INVALID_CATEGORY",
                                    }
                                },
                            }
                        ],
                    },
                ],
            },
        },
    },
    "metadata": {},
    "is_enabled": True,
}

EVENT_ITEM_PAYLOAD = {
    "data": {
        "title": "Sagra dei Ceci e dello Zafferano di Navelli",
        "description": "Evento di test per APIs join/unjoin.",
        "date": "2026-08-20",
        "time": "12:00",
        "location": "Navelli, AQ",
        "category": "Sagra",
        "organizer_name": "Francesco Gatti",
        "participants": [],
        "max_participants": 5000,
    },
    "public": True,
}


class TestApisService(unittest.TestCase):
    _mongo_container: Any = None
    _mongo_base_uri: str = ""
    _mysql_container: Any = None
    _sqlalchemy_uri: str = ""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        _ensure_docker_host()
        try:
            from testcontainers.core.container import DockerContainer
        except Exception as ex:
            raise unittest.SkipTest(
                "apis service tests require testcontainers[mongodb,mysql]"
            ) from ex

        try:
            cls._mongo_container = DockerContainer("mongo:7.0").with_exposed_ports(27017)
            cls._mongo_container.start()
            mongo_host = cls._mongo_container.get_container_host_ip()
            mongo_port = int(cls._mongo_container.get_exposed_port(27017))
            cls._mongo_base_uri = f"mongodb://{mongo_host}:{mongo_port}"
            _wait_for_mongo(cls._mongo_base_uri)
            cls._mysql_container = (
                DockerContainer("mysql:8.0")
                .with_env("MYSQL_DATABASE", "schedula")
                .with_env("MYSQL_USER", "test")
                .with_env("MYSQL_PASSWORD", "test")
                .with_env("MYSQL_ROOT_PASSWORD", "root")
                .with_exposed_ports(3306)
            )
            cls._mysql_container.start()
            mysql_host = cls._mysql_container.get_container_host_ip()
            mysql_port = int(cls._mysql_container.get_exposed_port(3306))
            _wait_for_mysql(mysql_host, mysql_port, "test", "test", "schedula")
            cls._sqlalchemy_uri = f"mysql+pymysql://test:test@{mysql_host}:{mysql_port}/schedula"
        except Exception as ex:
            raise unittest.SkipTest(
                "apis service tests require Docker with runnable MongoDB and MySQL containers"
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
        self.mongo_db_name = f"schedula_apis_{uuid.uuid4().hex}"
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

    def setUp(self):
        from flask import Flask
        from pymongo import MongoClient

        self.app = Flask("schedula_test_app")

        class DummySitemap:
            verify_file_handler = None
            basic_app_config = None

        self.mongo_uri = self._test_mongo_uri()
        self.mongo_client = MongoClient(self.mongo_uri)
        mongo_db = self.mongo_client[self.mongo_db_name]

        config = dict(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI=self.__class__._sqlalchemy_uri,
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
            MONGO_URI=self.mongo_uri,
            MONGO_DB=mongo_db,
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
            NOTIF_ENABLED=True,
            CASBIN_ADMIN_ENABLED=True,
            CONTRACTS_ENABLED=True,
            APIS_ENABLED=True,
        )

        self.app.config["MONGO_DB"] = mongo_db
        with self.app.app_context():
            basic_app(DummySitemap(), self.app, config)
            _db.create_all()

            self.admin_user = User(
                email="admin_apis@gmail.com",
                password=hash_password("AdminPass123!"),
                active=True,
                fs_uniquifier=str(uuid.uuid4()),
            )
            self.admin_user.confirmed_at = now_utc()
            self.user = User(
                email="user_apis@gmail.com",
                password=hash_password("UserPass123!"),
                active=True,
                fs_uniquifier=str(uuid.uuid4()),
            )
            self.user.confirmed_at = now_utc()
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
        if getattr(self, "mongo_client", None) is not None:
            try:
                self.mongo_client.drop_database(self.mongo_db_name)
            finally:
                self.mongo_client.close()

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

    def _create_item(self, token: str, category: str, payload: dict) -> str:
        r = self.client.post(
            f"/item/{category}",
            json=payload,
            headers=self._auth_headers(token),
        )
        self.assertEqual(r.status_code, 201, msg=r.get_data(as_text=True))
        body = r.get_json(silent=True) or {}
        item_id = body.get("id")
        self.assertTrue(item_id)
        return str(item_id)

    def _create_events_template(self) -> str:
        r = self.client.post(
            "/apis/templates",
            json=deepcopy(EVENTS_CUSTOM_TEMPLATE),
            headers=self._auth_headers(self.admin_token),
        )
        self.assertEqual(r.status_code, 201, msg=r.get_data(as_text=True))
        template_id = (r.get_json(silent=True) or {}).get("id")
        self.assertTrue(template_id)
        return str(template_id)

    def test_apis_events_custom_template_join_unjoin_invalid_category(self):
        template_id = self._create_events_template()
        item_payload = deepcopy(EVENT_ITEM_PAYLOAD)
        item_payload["data"]["category"] = "Sagra"
        item_id = self._create_item(
            self.admin_token,
            "not-events",
            item_payload,
        )

        join_r = self.client.post(
            f"/apis/{template_id}/join-event",
            json={"item_id": item_id},
            headers=self._auth_headers(self.user_token),
        )
        self.assertEqual(join_r.status_code, 200, msg=join_r.get_data(as_text=True))
        join_body = join_r.get_json(silent=True) or {}
        self.assertEqual(join_body.get("event"), "join_event")
        self.assertEqual(join_body.get("ok"), False)

        unjoin_r = self.client.post(
            f"/apis/{template_id}/unjoin-event",
            json={"item_id": item_id},
            headers=self._auth_headers(self.user_token),
        )
        self.assertEqual(unjoin_r.status_code, 200, msg=unjoin_r.get_data(as_text=True))
        unjoin_body = unjoin_r.get_json(silent=True) or {}
        self.assertEqual(unjoin_body.get("event"), "unjoin_event")
        self.assertEqual(unjoin_body.get("ok"), False)

        with self.app.app_context():
            self.assertEqual(self.app.config["MONGO_DB"]["apis"].count_documents({}), 0)
            self.assertEqual(
                self.app.config["MONGO_DB"]["contracts"].count_documents({}),
                0,
            )
            self.assertEqual(
                self.app.config["MONGO_DB"]["notifications"].count_documents({}),
                0,
            )

    def test_apis_events_custom_template_join_unjoin_valid_category(self):
        template_id = self._create_events_template()
        item_payload = deepcopy(EVENT_ITEM_PAYLOAD)
        item_payload["data"]["category"] = "events"
        item_id = self._create_item(
            self.admin_token,
            "events",
            item_payload,
        )

        join_r = self.client.post(
            f"/apis/{template_id}/join-event",
            json={"item_id": item_id},
            headers=self._auth_headers(self.user_token),
        )
        self.assertEqual(join_r.status_code, 200, msg=join_r.get_data(as_text=True))
        join_body = join_r.get_json(silent=True) or {}
        self.assertEqual(join_body.get("event"), "join_event")
        self.assertEqual(join_body.get("ok"), True)

        with self.app.app_context():
            item = self.app.config["MONGO_DB"]["items"].find_one({"_id": item_id})
            participants = ((item or {}).get("data") or {}).get("participants") or []
            self.assertIn(f"u:{self.user.id}", participants)

        unjoin_r = self.client.post(
            f"/apis/{template_id}/unjoin-event",
            json={"item_id": item_id},
            headers=self._auth_headers(self.user_token),
        )
        self.assertEqual(unjoin_r.status_code, 200, msg=unjoin_r.get_data(as_text=True))
        unjoin_body = unjoin_r.get_json(silent=True) or {}
        self.assertEqual(unjoin_body.get("event"), "unjoin_event")
        self.assertEqual(unjoin_body.get("ok"), True)

        with self.app.app_context():
            item = self.app.config["MONGO_DB"]["items"].find_one({"_id": item_id})
            participants = ((item or {}).get("data") or {}).get("participants") or []
            self.assertNotIn(f"u:{self.user.id}", participants)
            self.assertEqual(self.app.config["MONGO_DB"]["apis"].count_documents({}), 0)
            self.assertEqual(
                self.app.config["MONGO_DB"]["contracts"].count_documents({}),
                0,
            )
            notes = list(self.app.config["MONGO_DB"]["notifications"].find({}))
            self.assertEqual(len(notes), 2)
            events = {n.get("event") for n in notes}
            self.assertEqual(events, {"events.join_event", "events.unjoin_event"})
            for n in notes:
                targets = n.get("targets") or {}
                self.assertEqual(targets.get(f"u:{self.admin_user.id}"), ["in_app"])


if __name__ == "__main__":
    unittest.main()
