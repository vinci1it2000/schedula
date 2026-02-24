# coding: utf-8
from __future__ import annotations

try:
    from tests.utils.server._unittest_guard import ensure_server_test_env
except Exception:
    from _unittest_guard import ensure_server_test_env

ensure_server_test_env()


import importlib.resources as ir
import importlib
import os
import unittest
from typing import Dict, Set

import mongomock
from flask import Flask

from schedula.utils.form.server import basic_app
from schedula.utils.form.server.extensions import db as _db
from tests.utils.server.conftest import DummySitemap
from tests.utils.server.utils.mongo_validation import ValidatingMongoDatabase
from tests.utils.server.utils.openapi import is_multipart
from tests.utils.server.utils.seed import (
    seed_admin_user,
    seed_regular_user,
    try_login_for_token,
)

try:
    from_path = importlib.import_module("schemathesis.openapi").from_path
except Exception as ex:  # pragma: no cover
    raise unittest.SkipTest(f"Schemathesis not available: {ex}")


def _allowed_statuses(operation) -> Set[int]:
    raw = getattr(getattr(operation, "definition", None), "raw", None) or {}
    responses = raw.get("responses") or {}
    out: Set[int] = set()
    for code in responses.keys():
        if isinstance(code, int):
            out.add(code)
        elif isinstance(code, str) and code.isdigit():
            out.add(int(code))
    return out


def _openapi_resource():
    return ir.files("schedula.utils.form.server.openapi") / "openapi.yaml"


class TestOpenApiContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with ir.as_file(_openapi_resource()) as schema_path:
            cls.schema = from_path(schema_path)

    def setUp(self):
        os.environ.pop("MONGO_URI", None)
        self.app = Flask("schedula_test_app")

        config = dict(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI="sqlite+pysqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            SECURITY_ENABLED=True,
            SECURITY_REGISTERABLE=True,
            SECURITY_SEND_REGISTER_EMAIL=False,
            SECURITY_CONFIRMABLE=False,
            SECURITY_RECOVERABLE=True,
            SECURITY_CHANGEABLE=True,
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
            OPENAPI_ENABLED=True,
            CASBIN_ADMIN_ENABLED=True,
        )

        basic_app(DummySitemap(), self.app, config)
        with self.app.app_context():
            _db.create_all()

        self.mm_client = mongomock.MongoClient()
        mm_db = self.mm_client["schedula_test"]
        self.app.config["MONGO_DB"] = ValidatingMongoDatabase(mm_db)

        self.client = self.app.test_client()
        with self.app.app_context():
            admin = seed_admin_user()
            user = seed_regular_user()
        self.tokens = {
            "admin": try_login_for_token(self.client, admin["email"], admin["password"]) or "",
            "user": try_login_for_token(self.client, user["email"], user["password"]) or "",
        }

    def tearDown(self):
        with self.app.app_context():
            _db.session.remove()
            _db.drop_all()
        self.mm_client.close()

    def _auth_headers(self, which: str = "user") -> Dict[str, str]:
        token = self.tokens.get(which) or ""
        if not token:
            return {}
        return {"Authorization": f"Bearer {token}"}

    @staticmethod
    def _iter_operations(schema):
        get_all_operations = getattr(schema, "get_all_operations", None)
        if callable(get_all_operations):
            for item in get_all_operations():
                operation = getattr(item, "value", item)
                ok = getattr(item, "ok", None)
                if callable(ok):
                    try:
                        operation = ok()
                    except Exception:
                        operation = getattr(item, "value", None)
                if operation is not None:
                    yield operation
            return

        operations = getattr(schema, "operations", None)
        if operations is not None:
            for operation in operations:
                yield operation
            return

        raise unittest.SkipTest("Unable to iterate operations for this schemathesis version")

    @staticmethod
    def _build_case(operation):
        for attr in ("Case", "make_case", "as_case"):
            factory = getattr(operation, attr, None)
            if callable(factory):
                try:
                    return factory()
                except TypeError:
                    continue
        return None

    def test_openapi_contract_all_routes(self):
        default_allowed = {200, 201, 202, 204, 400, 401, 403, 404, 405, 409, 422, 500}
        executed = 0

        for operation in self._iter_operations(self.schema):
            raw = getattr(getattr(operation, "definition", None), "raw", None) or {}
            if is_multipart(raw):
                continue

            case = self._build_case(operation)
            if case is None:
                continue

            allowed = _allowed_statuses(operation) or default_allowed
            headers: Dict[str, str] = {}
            if 200 in allowed or 201 in allowed:
                headers = self._auth_headers("admin") or self._auth_headers("user")

            call_wsgi = getattr(case, "call_wsgi", None)
            if not callable(call_wsgi):
                continue

            response = call_wsgi(self.app, headers=headers)
            executed += 1

            self.assertIn(
                response.status_code,
                allowed,
                msg=(
                    response.status_code,
                    sorted(allowed),
                    getattr(case, "method", ""),
                    getattr(case, "path", ""),
                ),
            )

            validate_response = getattr(case, "validate_response", None)
            if callable(validate_response):
                validate_response(response)

        self.assertGreater(executed, 0, "No OpenAPI operations were executed")
