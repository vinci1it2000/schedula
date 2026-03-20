# coding: utf-8
from __future__ import annotations

import os
import unittest
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.parse import urlsplit, urlunsplit

import pytest
from flask import Flask
from flask.testing import FlaskClient
from pymongo import MongoClient
from schedula.utils.form.server import basic_app
from schedula.utils.form.server.extensions import db as _db

from .utils.seed import seed_admin_user, seed_regular_user, try_login_for_token


EXTRAS = os.environ.get("EXTRAS", "all")
if EXTRAS not in ("all", "form"):
    pytest.skip("Not for extra %s." % EXTRAS, allow_module_level=True)


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


@pytest.fixture(scope="session")
def mongo_base_uri() -> str:
    desktop_sock = os.path.join(os.path.expanduser("~"), ".docker", "run", "docker.sock")
    if not os.environ.get("DOCKER_HOST") and os.path.exists(desktop_sock):
        os.environ["DOCKER_HOST"] = f"unix://{desktop_sock}"
    try:
        from testcontainers.mongodb import MongoDbContainer
    except Exception as ex:
        raise unittest.SkipTest("server pytest tests require testcontainers[mongodb,mysql]") from ex
    container = MongoDbContainer("mongo:7.0")
    try:
        container.start()
        yield str(container.get_connection_url())
    finally:
        container.stop()


@pytest.fixture(scope="session")
def sqlalchemy_uri() -> str:
    desktop_sock = os.path.join(os.path.expanduser("~"), ".docker", "run", "docker.sock")
    if not os.environ.get("DOCKER_HOST") and os.path.exists(desktop_sock):
        os.environ["DOCKER_HOST"] = f"unix://{desktop_sock}"
    try:
        from testcontainers.mysql import MySqlContainer
    except Exception as ex:
        raise unittest.SkipTest("server pytest tests require testcontainers[mongodb,mysql]") from ex
    container = MySqlContainer("mysql:8.0")
    try:
        container.start()
        uri = str(container.get_connection_url())
        if uri.startswith("mysql://"):
            uri = "mysql+pymysql://" + uri[len("mysql://"):]
        yield uri
    finally:
        container.stop()


def _build_mongo_uri(base_uri: str, db_name: str) -> str:
    parts = urlsplit(base_uri)
    query = parts.query
    if "authSource=" not in query:
        query = f"{query}&authSource=admin" if query else "authSource=admin"
    return urlunsplit((parts.scheme, parts.netloc, f"/{db_name}", query, parts.fragment))


@pytest.fixture()
def app(monkeypatch: pytest.MonkeyPatch, mongo_base_uri: str, sqlalchemy_uri: str) -> Flask:
    # Ensure deterministic config for tests
    os.environ.pop("MONGO_URI", None)

    app = Flask("schedula_test_app")

    # Core test config
    config = dict(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI=sqlalchemy_uri,
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

    mongo_db_name = f"schedula_pytest_{uuid.uuid4().hex}"
    mongo_uri = _build_mongo_uri(mongo_base_uri, mongo_db_name)
    mongo_client = MongoClient(mongo_uri)
    mongo_db = mongo_client[mongo_db_name]
    config["MONGO_URI"] = mongo_uri
    config["MONGO_DB"] = mongo_db

    sitemap = DummySitemap()
    basic_app(sitemap, app, config)

    # --- SQL init per-test
    with app.app_context():
        _db.create_all()

    yield app

    # Teardown
    with app.app_context():
        _db.session.remove()
        _db.drop_all()
    try:
        mongo_client.drop_database(mongo_db_name)
    except Exception:
        pass
    mongo_client.close()


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
