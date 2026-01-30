# coding: utf-8
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

import mongomock
import pytest
from flask import Flask
from flask.testing import FlaskClient
from schedula.utils.form.server import basic_app
from schedula.utils.form.server.extensions import db as _db

from .utils.mongo_validation import ValidatingMongoDatabase
from .utils.seed import seed_admin_user, seed_regular_user, try_login_for_token


@dataclass
class TestUsers:
    admin: Dict[str, Any]
    user: Dict[str, Any]


class DummySitemap:
    """Minimal sitemap stub used by basic_app(app)."""

    basic_app_config: Optional[object] = None
    verify_file_handler = None


@pytest.fixture(scope="session")
def openapi_path() -> str:
    """
    Locate openapi.yaml from the installed package or from the repo checkout.

    Expected repo location:
      schedula/utils/form/server/openapi/openapi.yaml
    """
    # 1) Try package-relative path (installed / editable)
    try:
        import schedula.utils.form.server as server_pkg  # type: ignore

        base_dir = os.path.dirname(server_pkg.__file__)
        cand = os.path.join(base_dir, "openapi", "openapi.yaml")
        if os.path.exists(cand):
            return os.path.abspath(cand)
    except Exception:
        pass

    # 2) Walk up from this conftest.py
    here = os.path.abspath(os.path.dirname(__file__))
    cur = here
    for _ in range(8):
        cand = os.path.join(
            cur, "schedula", "utils", "form", "server", "openapi", "openapi.yaml"
        )
        if os.path.exists(cand):
            return os.path.abspath(cand)
        cur = os.path.dirname(cur)

    raise FileNotFoundError(
        "openapi.yaml not found (expected under schedula/utils/form/server/openapi/)"
    )


@pytest.fixture()
def app(monkeypatch: pytest.MonkeyPatch) -> Flask:
    # Ensure deterministic config for tests
    os.environ.pop("MONGO_URI", None)

    app = Flask("schedula_test_app")

    # Core test config
    config = dict(
        TESTING=True,
        # --- SQLAlchemy in-memory
        SQLALCHEMY_DATABASE_URI="sqlite+pysqlite:///:memory:",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        # --- Security
        SECURITY_ENABLED=True,
        SECURITY_REGISTERABLE=True,
        SECURITY_SEND_REGISTER_EMAIL=False,
        SECURITY_CONFIRMABLE=False,  # keep flows simple in tests
        SECURITY_RECOVERABLE=True,
        SECURITY_CHANGEABLE=True,
        SECURITY_URL_PREFIX="/user",
        WTF_CSRF_ENABLED=False,
        SCHEDULA_CSRF_ENABLED=False,
        # --- Items / Mongo
        ITEMS_STORAGE_ENABLED=True,
        FILES_STORAGE_ENABLED=False,
        S3_ITEMS_FILE_STORAGE=False,
        # --- Optional modules off
        CONTACT_ENABLED=False,
        SCHEDULA_CREDITS_ENABLED=False,
        SCHEDULA_EXPORT_FORM_ENABLED=False,
        SCHEDULA_GDPR_ENABLED=False,
        SCHEDULA_LOCALE_ENABLED=False,
        SCHEDULA_SECRETS_ENABLED=False,
        OPENAPI_ENABLED=True,
        CASBIN_ADMIN_ENABLED=True,
    )

    sitemap = DummySitemap()
    basic_app(sitemap, app, config)

    # --- SQL init per-test
    with app.app_context():
        _db.create_all()

    # --- Mongo in-memory + validator emulation
    mm_client = mongomock.MongoClient()
    mm_db = mm_client["schedula_test"]
    vdb = ValidatingMongoDatabase(
        mm_db
    )  # adds db.command(collMod) + JSONSchema validation

    app.config["MONGO_DB"] = vdb

    yield app

    # Teardown
    with app.app_context():
        _db.session.remove()
        _db.drop_all()
    mm_client.close()


@pytest.fixture()
def client(app: Flask) -> FlaskClient:
    return app.test_client()


@pytest.fixture()
def users(app: Flask) -> TestUsers:
    """Create minimal users and return their credentials."""
    with app.app_context():
        admin = seed_admin_user()
        user = seed_regular_user()
    return TestUsers(admin=admin, user=user)


@pytest.fixture()
def tokens(client: FlaskClient, users: TestUsers) -> Dict[str, str]:
    """
    Return tokens (bearer) for admin/user if the server returns tokens,
    otherwise empty strings (tests will skip token-required assertions).
    """
    admin_t = try_login_for_token(client, users.admin["email"], users.admin["password"])
    user_t = try_login_for_token(client, users.user["email"], users.user["password"])
    return {"admin": admin_t or "", "user": user_t or ""}


@pytest.fixture()
def auth_headers(tokens: Dict[str, str]):
    def _headers(which: str = "user") -> Dict[str, str]:
        tok = tokens.get(which) or ""
        if not tok:
            return {}
        return {"Authorization": f"Bearer {tok}"}

    return _headers
