#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2026, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');

import os
import platform
import unittest
import datetime as dt
import json
import io
from unittest import mock

EXTRAS = os.environ.get('EXTRAS', 'all')
GITHUB = os.getenv('GITHUB_ACTIONS') == 'true'
PLATFORM = platform.system().lower()

# --- optional test deps
try:
    import mongomock

    MONGO_MOCK_OK = True
except Exception:
    mongomock = None
    MONGO_MOCK_OK = False

try:
    from mongomock.gridfs import enable_gridfs_integration

    GRIDFS_MOCK_OK = True
except Exception:
    enable_gridfs_integration = None
    GRIDFS_MOCK_OK = False

# --- import module under test
try:
    import schedula.utils.form.server.items as items_mod
    from schedula.utils.form.server.extensions import db
except Exception:
    items_mod = None
    db = None


# -----------------------------
# Fake PyMongo backed by mongomock
# -----------------------------
class FakePyMongo:
    def __init__(self, app=None, uri=None):
        self._client = mongomock.MongoClient()
        self.db = self._client["testdb"]


# -----------------------------
# Dummy user objects (Flask-Security current_user)
# -----------------------------
class DummyRole:
    def __init__(self, name):
        self.name = name


class DummyUser:
    def __init__(self, user_id=None, roles=(), authenticated=False):
        self.id = user_id
        self.roles = [DummyRole(r) for r in roles]
        self.is_authenticated = authenticated

    def __bool__(self):
        return bool(self.is_authenticated)


ANON = DummyUser(None, roles=(), authenticated=False)
USER_A = DummyUser("1", roles=("user",), authenticated=True)
USER_B = DummyUser("2", roles=("user",), authenticated=True)
ADMIN = DummyUser("99", roles=("admin",), authenticated=True)


def _json(resp):
    return json.loads(resp.data.decode("utf-8"))


def _now():
    return dt.datetime.now(dt.timezone.utc)


# -----------------------------
# Shared helpers / base class
# -----------------------------
@unittest.skipIf(
    EXTRAS not in ('form', 'all') and GITHUB, 'Not for extra %s.' % EXTRAS
)
@unittest.skipIf(PLATFORM not in ('darwin', 'linux'),
                 'Not for platform %s.' % PLATFORM)
@unittest.skipIf(not MONGO_MOCK_OK, 'mongomock not installed.')
class _BaseItemsServiceTests:
    """
    Base class: provides helpers + schema seeding.
    Concrete subclasses must implement _make_app_config() and _backend_name().
    """

    @classmethod
    def _clear_s3_env(cls):
        for k in (
                "S3_ITEMS_FILE_STORAGE",
                "S3_ITEMS_FILE_ENDPOINT",
                "S3_ITEMS_FILE_REGION",
                "S3_ITEMS_FILE_ACCESS_KEY",
                "S3_ITEMS_FILE_SECRET_KEY",
                "S3_ITEMS_FILE_USE_SSL",
                "S3_ITEMS_FILE_PREFIX",
        ):
            os.environ.pop(k, None)

    @classmethod
    def _make_app_config(cls):
        raise NotImplementedError

    @classmethod
    def _backend_name(cls):
        raise NotImplementedError

    @classmethod
    def _seed_schemas(cls):
        # schemas
        default_acl = {
            "roles": {
                "admin": {"create": "all", "list": "all", "read": "all",
                          "update": "all", "delete": "all"},
                "user": {"create": "own", "list": "own", "read": "own",
                         "update": "own", "delete": "own"},
            },
            "default_role": "user",
        }

        db.session.add(items_mod.ItemSchema(
            category="__default__",
            schema={"type": "object", "additionalProperties": True},
            acl=default_acl,
            is_default=True,
        ))

        db.session.add(items_mod.ItemSchema(
            category="docs",
            schema={
                "type": "object",
                "properties": {"title": {"type": "string"}},
                "required": ["title"],
                "additionalProperties": True
            },
            acl=default_acl,
            is_default=False,
        ))

        # category with role config "none" to hit 403 branch
        db.session.add(items_mod.ItemSchema(
            category="blocked",
            schema={"type": "object", "additionalProperties": True},
            acl={"roles": {
                "user": {"list": "none", "read": "none", "create": "none",
                         "update": "none", "delete": "none"},
                "admin": {"create": "all", "list": "all", "read": "all",
                          "update": "all", "delete": "all"}},
                "default_role": "user"},
            is_default=False,
        ))

    @classmethod
    def setUpClass(cls):
        from flask import Flask

        # isolate PyMongo (mongomock)
        cls._pymongo_patch = mock.patch.object(items_mod, "PyMongo",
                                               FakePyMongo)
        cls._pymongo_patch.start()

        cls.app = Flask(__name__)
        cls.app.config.update(**cls._make_app_config())

        db.init_app(cls.app)

        cls.items_ext = items_mod.Items()

        with cls.app.app_context():
            cls.items_ext.init_app(cls.app)
            db.create_all()
            cls._seed_schemas()
            db.session.commit()

            cls.app.extensions["item_storage"].mongo_db.items.delete_many({})

        cls.client = cls.app.test_client()

    @classmethod
    def tearDownClass(cls):
        try:
            cls._pymongo_patch.stop()
        except Exception:
            pass
        with cls.app.app_context():
            db.session.remove()
            db.drop_all()

    def setUp(self):
        with self.app.app_context():
            self.app.extensions["item_storage"].mongo_db.items.delete_many({})

    def _as(self, user):
        return mock.patch.object(items_mod, "cu", user)

    # ---------------------------
    # Common tests (work for both backends)
    # ---------------------------
    def test_backend_expected(self):
        with self.app.app_context():
            self.assertEqual(self._backend_name(), items_mod.get_file_backend())

    def test_http_exception_json(self):
        with self._as(ANON):
            r = self.client.get("/item/docs/NOT_AN_OBJECTID")
        self.assertEqual(400, r.status_code)
        self.assertEqual("Invalid item_id", _json(r)["error"])

    def test_unhandled_exception_json(self):
        with mock.patch.object(items_mod, "get_mongo",
                               side_effect=RuntimeError("boom")):
            with self._as(USER_A):
                r = self.client.get("/item/docs")
        self.assertEqual(500, r.status_code)
        self.assertEqual("Internal server error", _json(r)["error"])

    def test_write_requires_auth(self):
        with self._as(ANON):
            r = self.client.post("/item/docs", json={"data": {"title": "x"}})
        self.assertEqual(401, r.status_code)
        self.assertEqual("Authentication required", _json(r)["error"])

    def test_acl_none_returns_403(self):
        with self._as(USER_A):
            r = self.client.get("/item/blocked")
        self.assertEqual(403, r.status_code)
        self.assertEqual("Access denied", _json(r)["error"])

    def test_schema_validation_fail_and_ok(self):
        with self._as(USER_A):
            r = self.client.post("/item/docs", json={"data": {}})
        self.assertEqual(400, r.status_code)
        self.assertIn("Schema validation failed", _json(r)["error"])

        with self._as(USER_A):
            r2 = self.client.post("/item/docs", json={"data": {"title": "ok"}})
        self.assertEqual(201, r2.status_code)
        self.assertEqual("docs", _json(r2)["category"])

    def test_default_schema_fallback(self):
        with self._as(USER_A):
            r = self.client.post("/item/unknown", json={"data": {"x": 1}})
        self.assertEqual(201, r.status_code)
        self.assertEqual("unknown", _json(r)["category"])

    def test_parse_request_payload_json_is_public_variants(self):
        with self._as(USER_A):
            r = self.client.post("/item/docs", json={"data": {"title": "x"},
                                                     "is_public": "true"})
        self.assertEqual(201, r.status_code)
        self.assertTrue(_json(r)["is_public"])

        with self._as(USER_A):
            r2 = self.client.post("/item/docs", json={"data": {"title": "x2"},
                                                      "is_public": False})
        self.assertEqual(201, r2.status_code)
        self.assertFalse(_json(r2)["is_public"])

    def test_parse_request_payload_multipart_bad_json(self):
        payload = {"data": "{bad json"}
        with self._as(USER_A):
            r = self.client.post("/item/docs", data=payload,
                                 content_type="multipart/form-data")
        self.assertEqual(400, r.status_code)
        self.assertIn("Invalid JSON in form field 'data'", _json(r)["error"])

    def test_include_data_arg_variants(self):
        with self._as(USER_A):
            r = self.client.post("/item/docs", json={"data": {"title": "x"}})
        item_id = _json(r)["id"]

        with self._as(USER_A):
            r2 = self.client.get("/item/docs?include_data=1")
        self.assertEqual(200, r2.status_code)
        items = _json(r2)["items"]
        self.assertTrue("data" in items[0])

        with self._as(USER_A):
            r3 = self.client.get("/item/docs?include=full")
        self.assertEqual(200, r3.status_code)
        self.assertTrue("data" in _json(r3)["items"][0])

        with self._as(USER_A):
            r4 = self.client.get(f"/item/docs/{item_id}")
        self.assertEqual(200, r4.status_code)
        self.assertTrue("data" in _json(r4))

    def test_public_filtering(self):
        with self._as(USER_A):
            rp = self.client.post("/item/docs", json={"data": {"title": "priv"},
                                                      "is_public": False})
            ru = self.client.post("/item/docs", json={"data": {"title": "pub"},
                                                      "is_public": True})
        self.assertEqual(201, rp.status_code)
        self.assertEqual(201, ru.status_code)

        with self._as(ANON):
            r = self.client.get("/item/docs")
        self.assertEqual(200, r.status_code)
        self.assertEqual(1, _json(r)["total"])
        self.assertTrue(all(it["is_public"] for it in _json(r)["items"]))

        with self._as(USER_B):
            r2 = self.client.get("/item/docs")
        self.assertEqual(200, r2.status_code)
        self.assertEqual(1, _json(r2)["total"])

        with self._as(USER_A):
            r3 = self.client.get("/item/docs")
        self.assertEqual(200, r3.status_code)
        self.assertEqual(2, _json(r3)["total"])

    def test_invalid_file_names(self):
        with self._as(USER_A):
            r = self.client.post("/item/docs", json={"data": {"title": "x"},
                                                     "is_public": True})
        item_id = _json(r)["id"]

        with self._as(ANON):
            r2 = self.client.get(f"/item-file/{item_id}/..\\x")
        self.assertEqual(400, r2.status_code)
        self.assertEqual("Invalid file name", _json(r2)["error"])

        with self._as(ANON):
            r3 = self.client.get(f"/item-file/{item_id}/a/b.txt")
        self.assertEqual(404, r3.status_code)

    def test_mq_invalid_json_and_non_object(self):
        with self._as(ANON):
            r = self.client.get("/item/docs?mq={bad")
        self.assertEqual(400, r.status_code)

        with self._as(ANON):
            r2 = self.client.get("/item/docs?mq=%5B1%2C2%5D")
        self.assertEqual(400, r2.status_code)
        self.assertIn("mq must be a JSON object", _json(r2)["error"])

    def test_mq_too_deep(self):
        node = {}
        cur = node
        for _ in range(12):
            nxt = {}
            cur["a"] = nxt
            cur = nxt
        mq = json.dumps(node)
        with self._as(ANON):
            r = self.client.get(f"/item/docs?mq={mq}")
        self.assertEqual(400, r.status_code)
        self.assertIn("mq too deep", _json(r)["error"])

    def test_mq_too_large(self):
        node = {f"k{i}": i for i in range(250)}
        mq = json.dumps(node)
        with self._as(ANON):
            r = self.client.get(f"/item/docs?mq={mq}")
        self.assertEqual(400, r.status_code)
        self.assertIn("mq too large", _json(r)["error"])

    def test_mq_regex_too_long(self):
        node = {"field": {"$regex": "a" * 200}}
        mq = json.dumps(node)
        with self._as(ANON):
            r = self.client.get(f"/item/docs?mq={mq}")
        self.assertEqual(400, r.status_code)
        self.assertIn("mq regex too long", _json(r)["error"])

    def test_mq_protected_fields_are_dropped(self):
        with self.app.app_context():
            coll = self.app.extensions["item_storage"].mongo_db.items
            now = _now()
            coll.insert_many([
                {"category": "docs", "data": {"title": "A"}, "files": {},
                 "user_id": "1", "is_public": True, "created_at": now,
                 "updated_at": now},
                {"category": "docs", "data": {"title": "B"}, "files": {},
                 "user_id": "2", "is_public": True, "created_at": now,
                 "updated_at": now},
            ])

        mq = json.dumps({"user_id": "2", "category": "xxx", "_id": "yyy",
                         "is_public": False})
        with self._as(ANON):
            r = self.client.get(f"/item/docs?mq={mq}")
        self.assertEqual(200, r.status_code)
        self.assertEqual(2, _json(r)["total"])

    def test_pagination_offset_and_page_modes(self):
        with self.app.app_context():
            coll = self.app.extensions["item_storage"].mongo_db.items
            now = _now()
            for i in range(5):
                coll.insert_one({
                    "category": "docs",
                    "data": {"title": f"T{i}"},
                    "files": {},
                    "user_id": "1",
                    "is_public": True,
                    "created_at": now, "updated_at": now
                })

        with self._as(ANON):
            r = self.client.get("/item/docs?limit=2&offset=0&sort=-updated_at")
        self.assertEqual(200, r.status_code)
        self.assertEqual(2, len(_json(r)["items"]))

        with self._as(ANON):
            r2 = self.client.get("/item/docs?page=2&page_size=2")
        self.assertEqual(200, r2.status_code)
        self.assertEqual(2, len(_json(r2)["items"]))

    def test_sort_invalid(self):
        with self._as(ANON):
            r = self.client.get("/item/docs?sort=title")
        self.assertEqual(400, r.status_code)
        self.assertIn("Invalid 'sort'", _json(r)["error"])

    def test_after_invalid(self):
        with self._as(ANON):
            r = self.client.get("/item/docs?after=NOTOID&sort=-_id")
        self.assertEqual(400, r.status_code)
        self.assertIn("Invalid 'after'", _json(r)["error"])

    def test_after_with_offset_conflict(self):
        with self.app.app_context():
            coll = self.app.extensions["item_storage"].mongo_db.items
            now = _now()
            res = coll.insert_one({
                "category": "docs", "data": {"title": "x"}, "files": {},
                "user_id": "1", "is_public": True,
                "created_at": now, "updated_at": now
            })
            after = str(res.inserted_id)

        with self._as(ANON):
            r = self.client.get(f"/item/docs?after={after}&offset=10&sort=-_id")
        self.assertEqual(400, r.status_code)
        self.assertIn("Use either 'after'", _json(r)["error"])

    def test_init_app_missing_mongo_uri_raises(self):
        from flask import Flask
        app = Flask("x")
        app.config.update(
            TESTING=True,
            SECRET_KEY="x",
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            ITEMS_MONGO_URI=None,
            S3_ITEMS_FILE_STORAGE=None,
        )
        db.init_app(app)
        ext = items_mod.Items()
        with app.app_context():
            with self.assertRaises(RuntimeError):
                ext.init_app(app)

    def test_method_not_allowed(self):
        import werkzeug
        with self.app.test_request_context("/item/docs", method="TRACE"):
            with self._as(USER_A):
                with self.assertRaises(werkzeug.exceptions.MethodNotAllowed):
                    items_mod.item("docs", None)


# ======================================================================
# GRIDFS BACKEND
# ======================================================================
@unittest.skipIf(
    EXTRAS not in ('form', 'all') and GITHUB, 'Not for extra %s.' % EXTRAS
)
@unittest.skipIf(PLATFORM not in ('darwin', 'linux'),
                 'Not for platform %s.' % PLATFORM)
@unittest.skipIf(not GRIDFS_MOCK_OK,
                 'mongomock gridfs integration not available.')
class TestItemsServiceGridFS(_BaseItemsServiceTests, unittest.TestCase):
    @classmethod
    def _make_app_config(cls):
        # Force GridFS: clear env so init_app can't pick S3 from env
        cls._clear_s3_env()
        enable_gridfs_integration()

        return dict(
            TESTING=True,
            SECRET_KEY="test",
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            ITEMS_MONGO_URI="mongodb://example.invalid/testdb",
            S3_ITEMS_FILE_STORAGE=None,
            ITEMS_MONGO_MAX_TIME_MS=2000,
        )

    @classmethod
    def _backend_name(cls):
        return "gridfs"

    # ---------------------------
    # GridFS-specific tests
    # ---------------------------
    def test_crud_matrix_gridfs_with_file(self):
        # --- CREATE (multipart + file ref)
        data = {"title": "doc", "attachment": {"$ref": "/files/a.txt"}}
        payload = {
            "data": json.dumps(data),
            "is_public": "1",
            "a.txt": (io.BytesIO(b"HELLO"), "a.txt", "text/plain"),
        }
        with self._as(USER_A):
            r = self.client.post("/item/docs?include_data=1", data=payload,
                                 content_type="multipart/form-data")
        self.assertEqual(201, r.status_code)
        j = _json(r)
        item_id = j["id"]
        self.assertEqual("docs", j["category"])
        self.assertTrue(j["is_public"])
        self.assertEqual("doc", j["data"]["title"])
        self.assertIn("a.txt", j["files"])

        # --- LIST (anon sees public)
        with self._as(ANON):
            r = self.client.get("/item/docs?include_data=1")
        self.assertEqual(200, r.status_code)
        self.assertEqual(1, _json(r)["total"])
        self.assertEqual(item_id, _json(r)["items"][0]["id"])

        # --- READ ONE
        with self._as(ANON):
            r = self.client.get(f"/item/docs/{item_id}?include_data=1")
        self.assertEqual(200, r.status_code)
        self.assertEqual("doc", _json(r)["data"]["title"])
        self.assertIn("a.txt", _json(r)["files"])

        # --- DOWNLOAD (anon ok because item public)
        with self._as(ANON):
            d = self.client.get(f"/item-file/{item_id}/a.txt")
        self.assertEqual(200, d.status_code)
        self.assertEqual(b"HELLO", d.data)
        self.assertEqual("text/plain", d.mimetype)

        # --- PATCH (merge + null removes attachment => drops file)
        patch_payload = {
            "data": json.dumps({"title": "doc", "attachment": None})}
        with self._as(USER_A):
            r = self.client.patch(f"/item/docs/{item_id}?include_data=1",
                                  data=patch_payload,
                                  content_type="multipart/form-data")
        self.assertEqual(200, r.status_code)
        self.assertEqual({}, _json(r)["files"])

        # --- PUT (replace data)
        with self._as(USER_A):
            r = self.client.put(f"/item/docs/{item_id}?include_data=1",
                                json={"data": {"title": "NEW"}})
        self.assertEqual(200, r.status_code)
        self.assertEqual("NEW", _json(r)["data"]["title"])

        # --- DELETE
        with self._as(USER_A):
            r = self.client.delete(f"/item/docs/{item_id}")
        self.assertEqual(200, r.status_code)
        self.assertEqual("deleted", _json(r)["status"])

        # --- READ after delete
        with self._as(USER_A):
            r = self.client.get(f"/item/docs/{item_id}")
        self.assertEqual(404, r.status_code)
        self.assertEqual("Item not found", _json(r)["error"])

        # --- DOWNLOAD after delete (item missing -> 404)
        with self._as(ANON):
            d = self.client.get(f"/item-file/{item_id}/a.txt")
        self.assertEqual(404, d.status_code)
        self.assertEqual("Item not found", _json(d)["error"])

    def test_patch_null_prunes_nested(self):
        with self._as(USER_A):
            r = self.client.post("/item/docs", json={
                "data": {"title": "t", "nested": {"a": 1, "b": 2}}
            })
        item_id = _json(r)["id"]

        with self._as(USER_A):
            r2 = self.client.patch(f"/item/docs/{item_id}?include_data=1",
                                   json={
                                       "data": {"nested": {"a": None}}
                                   })
        self.assertEqual(200, r2.status_code)
        self.assertEqual({"b": 2}, _json(r2)["data"]["nested"])

    def test_create_with_file_ref_success_and_download_matrix(self):
        data = {"title": "doc", "attachment": {"$ref": "/files/a.txt"}}
        payload = {
            "data": json.dumps(data),
            "is_public": "1",
            "a.txt": (io.BytesIO(b"hello"), "a.txt", "text/plain"),
        }
        with self._as(USER_A):
            r = self.client.post("/item/docs", data=payload,
                                 content_type="multipart/form-data")
        self.assertEqual(201, r.status_code)
        item_id = _json(r)["id"]

        with self._as(ANON):
            d1 = self.client.get(f"/item-file/{item_id}/a.txt")
        self.assertEqual(200, d1.status_code)
        self.assertEqual(b"hello", d1.data)

        with self._as(USER_B):
            d2 = self.client.get(f"/item-file/{item_id}/a.txt")
        self.assertEqual(200, d2.status_code)

    def test_download_gridfs_content_type_fallback_from_gridfs(self):
        with self.app.app_context():
            mongo = self.app.extensions["item_storage"].mongo_db
            fs = items_mod.gridfs.GridFS(mongo)
            fid = fs.put(
                io.BytesIO(b"HELLO"), filename="a.txt",
                contentType="text/plain", user_id="1"
            )

            now = _now()
            res = mongo.items.insert_one({
                "category": "docs",
                "data": {"title": "x", "attachment": {"$ref": "/files/a.txt"}},
                "files": {"a.txt": {"id": str(fid), "user_id": "1",
                                    "content_type": None, "size": 5}},
                "user_id": "1",
                "is_public": True,
                "created_at": now, "updated_at": now
            })
            item_id = str(res.inserted_id)

        with self._as(ANON):
            r = self.client.get(f"/item-file/{item_id}/a.txt")
        self.assertEqual(200, r.status_code)
        self.assertEqual(b"HELLO", r.data)
        self.assertEqual("text/plain", r.mimetype)
        self.assertIn('attachment; filename="a.txt"',
                      r.headers.get("Content-Disposition", ""))

    def test_download_gridfs_fs_get_raises_404(self):
        with self.app.app_context():
            mongo = self.app.extensions["item_storage"].mongo_db
            now = _now()
            fake_oid = "656565656565656565656565"  # valido
            res = mongo.items.insert_one({
                "category": "docs",
                "data": {"title": "x", "attachment": {"$ref": "/files/a.txt"}},
                "files": {"a.txt": {"id": fake_oid, "user_id": "1",
                                    "content_type": None, "size": 5}},
                "user_id": "1",
                "is_public": True,
                "created_at": now, "updated_at": now
            })
            item_id = str(res.inserted_id)

        with mock.patch.object(items_mod.gridfs.GridFS, "get",
                               side_effect=Exception("missing")):
            with self._as(ANON):
                r = self.client.get(f"/item-file/{item_id}/a.txt")
        self.assertEqual(404, r.status_code)
        self.assertEqual("File not found", _json(r)["error"])

    def test_create_missing_upload_for_ref(self):
        data = {"title": "doc", "attachment": {"$ref": "/files/a.txt"}}
        payload = {"data": json.dumps(data)}
        with self._as(USER_A):
            r = self.client.post("/item/docs", data=payload,
                                 content_type="multipart/form-data")
        self.assertEqual(400, r.status_code)
        self.assertIn("File references validation failed", _json(r)["error"])

    def test_create_orphan_upload_fails_refs(self):
        payload = {
            "data": json.dumps({"title": "doc"}),
            "a.txt": (io.BytesIO(b"hello"), "a.txt", "text/plain"),
        }
        with self._as(USER_A):
            r = self.client.post("/item/docs", data=payload,
                                 content_type="multipart/form-data")
        self.assertEqual(400, r.status_code)
        self.assertIn("File references validation failed", _json(r)["error"])

    def test_create_empty_file_size_path(self):
        data = {"title": "doc", "attachment": {"$ref": "/files/a.txt"}}
        payload = {
            "data": json.dumps(data),
            "a.txt": (io.BytesIO(b""), "a.txt", "text/plain"),
        }
        with self._as(USER_A):
            r = self.client.post("/item/docs", data=payload,
                                 content_type="multipart/form-data")
        self.assertEqual(400, r.status_code)

    def test_put_replaces_data(self):
        with self._as(USER_A):
            r = self.client.post("/item/docs",
                                 json={"data": {"title": "old", "x": 1}})
        item_id = _json(r)["id"]

        with self._as(USER_A):
            r2 = self.client.put(f"/item/docs/{item_id}?include_data=1",
                                 json={"data": {"title": "new"}})
        self.assertEqual(200, r2.status_code)
        self.assertEqual("new", _json(r2)["data"]["title"])
        self.assertFalse("x" in _json(r2)["data"])

    def test_patch_merges_data_and_toggles_public(self):
        with self._as(USER_A):
            r = self.client.post("/item/docs", json={
                "data": {"title": "old", "nested": {"a": 1}},
                "is_public": False
            })
        item_id = _json(r)["id"]

        with self._as(USER_A):
            r2 = self.client.patch(
                f"/item/docs/{item_id}?include_data=1",
                json={"data": {"nested": {"b": 2}}, "is_public": True}
            )
        self.assertEqual(200, r2.status_code)
        j = _json(r2)
        self.assertTrue(j["is_public"])
        self.assertEqual(1, j["data"]["nested"]["a"])
        self.assertEqual(2, j["data"]["nested"]["b"])

    def test_patch_file_replace_and_drop(self):
        data = {"title": "doc", "attachment": {"$ref": "/files/a.txt"}}
        payload = {"data": json.dumps(data),
                   "a.txt": (io.BytesIO(b"v1"), "a.txt", "text/plain")}
        with self._as(USER_A):
            r = self.client.post("/item/docs", data=payload,
                                 content_type="multipart/form-data")
        item_id = _json(r)["id"]

        payload2 = {"data": json.dumps(data),
                    "a.txt": (io.BytesIO(b"v2"), "a.txt", "text/plain")}
        with self._as(USER_A):
            r2 = self.client.patch(
                f"/item/docs/{item_id}?include_data=1", data=payload2,
                content_type="multipart/form-data"
            )
        self.assertEqual(200, r2.status_code)

        payload3 = {"data": json.dumps({"title": "doc", "attachment": None})}
        with self._as(USER_A):
            r3 = self.client.patch(
                f"/item/docs/{item_id}?include_data=1", data=payload3,
                content_type="multipart/form-data"
            )
        self.assertEqual(200, r3.status_code)
        self.assertEqual({}, _json(r3)["files"])

    def test_delete_item_and_delete_files_meta_exception_path(self):
        data = {"title": "doc", "attachment": {"$ref": "/files/a.txt"}}
        payload = {"data": json.dumps(data),
                   "a.txt": (io.BytesIO(b"hello"), "a.txt", "text/plain")}
        with self._as(USER_A):
            r = self.client.post("/item/docs", data=payload,
                                 content_type="multipart/form-data")
        item_id = _json(r)["id"]

        with mock.patch.object(items_mod.gridfs.GridFS, "delete",
                               side_effect=Exception("fail")):
            with self._as(USER_A):
                rd = self.client.delete(f"/item/docs/{item_id}")
        self.assertEqual(200, rd.status_code)

    def test_download_private_requires_owner_or_admin(self):
        data = {"title": "doc", "attachment": {"$ref": "/files/a.txt"}}
        payload = {"data": json.dumps(data),
                   "a.txt": (io.BytesIO(b"hello"), "a.txt", "text/plain")}
        with self._as(USER_A):
            r = self.client.post("/item/docs", data=payload,
                                 content_type="multipart/form-data")
        item_id = _json(r)["id"]

        with self._as(ANON):
            d1 = self.client.get(f"/item-file/{item_id}/a.txt")
        self.assertEqual(401, d1.status_code)

        with self._as(USER_B):
            d2 = self.client.get(f"/item-file/{item_id}/a.txt")
        self.assertEqual(403, d2.status_code)

        with self._as(USER_A):
            d3 = self.client.get(f"/item-file/{item_id}/a.txt")
        self.assertEqual(200, d3.status_code)

        with self._as(ADMIN):
            d4 = self.client.get(f"/item-file/{item_id}/a.txt")
        self.assertEqual(200, d4.status_code)

    def test_download_inconsistent_meta_user_id(self):
        with self.app.app_context():
            coll = self.app.extensions["item_storage"].mongo_db.items
            now = _now()
            fs = items_mod.gridfs.GridFS(
                self.app.extensions["item_storage"].mongo_db)
            file_id = fs.put(io.BytesIO(b"hello"), filename="a.txt",
                             contentType="text/plain", user_id="2")
            res = coll.insert_one({
                "category": "docs",
                "data": {"title": "x", "attachment": {"$ref": "/files/a.txt"}},
                "files": {"a.txt": {"id": str(file_id), "user_id": "2",
                                    "content_type": "text/plain", "size": 5}},
                "user_id": "1",
                "is_public": True,
                "created_at": now, "updated_at": now
            })
            item_id = str(res.inserted_id)

        with self._as(ANON):
            r = self.client.get(f"/item-file/{item_id}/a.txt")
        self.assertEqual(409, r.status_code)
        self.assertEqual("File metadata inconsistent", _json(r)["error"])

    def test_download_missing_file_in_gridfs(self):
        with self.app.app_context():
            coll = self.app.extensions["item_storage"].mongo_db.items
            now = _now()
            fake_oid = "656565656565656565656565"
            res = coll.insert_one({
                "category": "docs",
                "data": {"title": "x", "attachment": {"$ref": "/files/a.txt"}},
                "files": {"a.txt": {"id": fake_oid, "user_id": "1",
                                    "content_type": "text/plain", "size": 5}},
                "user_id": "1",
                "is_public": True,
                "created_at": now, "updated_at": now
            })
            item_id = str(res.inserted_id)

        with self._as(ANON):
            r = self.client.get(f"/item-file/{item_id}/a.txt")
        self.assertEqual(404, r.status_code)

    def test_store_uploaded_file_gridfs_error_branch(self):
        with mock.patch.object(items_mod.gridfs.GridFS, "put",
                               side_effect=Exception("fail")):
            class F:
                mimetype = "text/plain"
                stream = io.BytesIO(b"hello")

            with self._as(USER_A):
                with self.app.test_request_context("/"):
                    with self.assertRaises(Exception):
                        items_mod.store_uploaded_file(
                            "a.txt", F(),
                            self.app.extensions["item_storage"].mongo_db,
                            USER_A
                        )


# ======================================================================
# S3 BACKEND (mocked)
# ======================================================================
class _FakeBody:
    def __init__(self, data: bytes):
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError("data must be bytes-like")
        self._data = memoryview(data)
        self._pos = 0

    def read(self, size: int = -1) -> bytes:
        if self._pos >= len(self._data):
            return b""

        if size is None or size < 0:
            chunk = self._data[self._pos:]
            self._pos = len(self._data)
            return bytes(chunk)

        end = min(self._pos + size, len(self._data))
        chunk = self._data[self._pos: end]
        self._pos = end
        return bytes(chunk)


@unittest.skipIf(
    EXTRAS not in ('form', 'all') and GITHUB, 'Not for extra %s.' % EXTRAS
)
@unittest.skipIf(PLATFORM not in ('darwin', 'linux'),
                 'Not for platform %s.' % PLATFORM)
class TestItemsServiceS3(_BaseItemsServiceTests, unittest.TestCase):
    @classmethod
    def _make_app_config(cls):
        # Force S3 via ENV + config (deterministic)
        cls._clear_s3_env()
        os.environ["S3_ITEMS_FILE_STORAGE"] = "mybucket"

        return dict(
            TESTING=True,
            SECRET_KEY="test",
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            ITEMS_MONGO_URI="mongodb://example.invalid/testdb",
            S3_ITEMS_FILE_STORAGE="mybucket",
            S3_ITEMS_FILE_PREFIX="pfx",
            S3_ITEMS_FILE_ENDPOINT="http://minio:9000",
            S3_ITEMS_FILE_REGION="us-east-1",
            S3_ITEMS_FILE_ACCESS_KEY="a",
            S3_ITEMS_FILE_SECRET_KEY="b",
            S3_ITEMS_FILE_USE_SSL=False,
            ITEMS_MONGO_MAX_TIME_MS=2000,
        )

    @classmethod
    def _backend_name(cls):
        return "s3"

    def _mock_s3_ctx(self, upload_ok=True, get_ok=True, content=b"hello",
                     content_type="text/plain", bytes_read_override=None):
        """
        bytes_read_override:
          - None: counting stream reads file and counts real bytes
          - 0: simulate 'counting_stream.bytes_read == 0' even if stream has bytes
        """
        s3 = mock.Mock()

        def _upload_side_effect(Fileobj, Bucket, Key, ExtraArgs=None, **kwargs):
            # read all from Fileobj to increment counting_reader.bytes_read
            for _ in iter(lambda: Fileobj.read(1024 * 256), b""):
                pass
            # optionally override bytes_read to simulate buggy/mocked boto behavior
            if bytes_read_override is not None and hasattr(Fileobj,
                                                           "bytes_read"):
                Fileobj.bytes_read = bytes_read_override
            return None

        if upload_ok:
            s3.upload_fileobj.side_effect = _upload_side_effect
        else:
            s3.upload_fileobj.side_effect = Exception("PutObject failed")

        if get_ok:
            s3.get_object.return_value = {"Body": _FakeBody(content),
                                          "ContentType": content_type}
        else:
            s3.get_object.side_effect = Exception("NotFound")

        s3.delete_object.return_value = None

        ctx = mock.patch.object(items_mod, "get_s3_client_and_bucket",
                                return_value=(s3, "mybucket", "pfx/"))
        return s3, ctx

    def test_crud_matrix_s3_with_file(self):
        s3, ctx = self._mock_s3_ctx(
            upload_ok=True, get_ok=True,
            content=b"HELLO", content_type="text/plain"
        )

        # --- CREATE
        data = {"title": "doc", "attachment": {"$ref": "/files/a.txt"}}
        payload = {
            "data": json.dumps(data),
            "is_public": "1",
            "a.txt": (io.BytesIO(b"HELLO"), "a.txt", "text/plain"),
        }

        with ctx:
            with self._as(USER_A):
                r = self.client.post("/item/docs?include_data=1", data=payload,
                                     content_type="multipart/form-data")
        self.assertEqual(201, r.status_code)
        j = _json(r)
        item_id = j["id"]
        self.assertTrue(s3.upload_fileobj.called)
        self.assertIn("a.txt", j["files"])

        # --- LIST (anon sees public)
        with ctx:
            with self._as(ANON):
                r = self.client.get("/item/docs?include_data=1")
        self.assertEqual(200, r.status_code)
        self.assertEqual(1, _json(r)["total"])
        self.assertEqual(item_id, _json(r)["items"][0]["id"])

        # --- READ ONE
        with ctx:
            with self._as(ANON):
                r = self.client.get(f"/item/docs/{item_id}?include_data=1")
        self.assertEqual(200, r.status_code)
        self.assertEqual("doc", _json(r)["data"]["title"])
        self.assertIn("a.txt", _json(r)["files"])

        # --- DOWNLOAD (anon ok because item public)
        with ctx:
            with self._as(ANON):
                d = self.client.get(f"/item-file/{item_id}/a.txt")
        self.assertEqual(200, d.status_code)
        self.assertEqual(b"HELLO", d.data)
        self.assertEqual("text/plain", d.mimetype)
        self.assertTrue(s3.get_object.called)

        # --- PATCH: null removes attachment => drops file => should call delete_object
        patch_payload = {
            "data": json.dumps({"title": "doc", "attachment": None})}
        with ctx:
            with self._as(USER_A):
                r = self.client.patch(f"/item/docs/{item_id}?include_data=1",
                                      data=patch_payload,
                                      content_type="multipart/form-data")
        self.assertEqual(200, r.status_code)
        self.assertEqual({}, _json(r)["files"])
        self.assertGreaterEqual(s3.delete_object.call_count, 1)

        # --- PUT: replace data
        with ctx:
            with self._as(USER_A):
                r = self.client.put(f"/item/docs/{item_id}?include_data=1",
                                    json={"data": {"title": "NEW"}})
        self.assertEqual(200, r.status_code)
        self.assertEqual("NEW", _json(r)["data"]["title"])

        # --- DELETE: should delete item (and if there were files, would delete them too)
        with ctx:
            with self._as(USER_A):
                r = self.client.delete(f"/item/docs/{item_id}")
        self.assertEqual(200, r.status_code)
        self.assertEqual("deleted", _json(r)["status"])

        # --- READ after delete
        with ctx:
            with self._as(USER_A):
                r = self.client.get(f"/item/docs/{item_id}")
        self.assertEqual(404, r.status_code)

        # --- DOWNLOAD after delete
        with ctx:
            with self._as(ANON):
                d = self.client.get(f"/item-file/{item_id}/a.txt")
        self.assertEqual(404, d.status_code)
        self.assertEqual("Item not found", _json(d)["error"])

    # --- Additional coverage: cursor pagination branches ($and append vs direct _id)
    def test_cursor_pagination_appends_to_and_query(self):
        with self.app.app_context():
            coll = self.app.extensions["item_storage"].mongo_db.items
            now = _now()
            ids = [coll.insert_one({
                "category": "docs", "data": {"title": f"T{i}"}, "files": {},
                "user_id": "1", "is_public": True,
                "created_at": now, "updated_at": now
            }).inserted_id for i in range(3)]
            after = str(ids[0])

        mq = json.dumps({"field": {"$exists": True}})
        with self._as(ANON):
            r = self.client.get(
                f"/item/docs?after={after}&sort=_id&limit=2&mq={mq}")
        self.assertEqual(200, r.status_code)
        self.assertIn("next_after", _json(r))

    def test_cursor_pagination_sets_id_directly_when_no_and(self):
        with self.app.app_context():
            coll = self.app.extensions["item_storage"].mongo_db.items
            now = _now()
            ids = [coll.insert_one({
                "category": "docs", "data": {"title": f"T{i}"}, "files": {},
                "user_id": "1", "is_public": True,
                "created_at": now, "updated_at": now
            }).inserted_id for i in range(3)]
            after = str(ids[0])

        with self._as(ANON):
            r = self.client.get(f"/item/docs?after={after}&sort=_id&limit=2")
        self.assertEqual(200, r.status_code)
        self.assertIn("next_after", _json(r))

    # --- S3 core flows (create/patch/drop/download + error branches)
    def test_download_s3_get_object_raises_404(self):
        with self.app.app_context():
            mongo = self.app.extensions["item_storage"].mongo_db
            now = _now()
            res = mongo.items.insert_one({
                "category": "docs",
                "data": {"title": "x", "attachment": {"$ref": "/files/a.txt"}},
                "files": {"a.txt": {"id": "fileid1", "user_id": "1",
                                    "content_type": None, "size": 5}},
                "user_id": "1",
                "is_public": True,
                "created_at": now, "updated_at": now
            })
            item_id = str(res.inserted_id)

        s3 = mock.Mock()
        s3.get_object.side_effect = Exception("NotFound")

        with mock.patch.object(items_mod, "get_file_backend",
                               return_value="s3"):
            with mock.patch.object(items_mod, "get_s3_client_and_bucket",
                                   return_value=(s3, "b", "")):
                with self._as(ANON):
                    r = self.client.get(f"/item-file/{item_id}/a.txt")

        self.assertEqual(404, r.status_code)
        self.assertEqual("File not found", _json(r)["error"])

    def test_download_s3_content_type_fallback_from_object(self):
        with self.app.app_context():
            mongo = self.app.extensions["item_storage"].mongo_db
            now = _now()
            res = mongo.items.insert_one({
                "category": "docs",
                "data": {"title": "x", "attachment": {"$ref": "/files/a.txt"}},
                "files": {"a.txt": {"id": "fileid1", "user_id": "1",
                                    "content_type": None, "size": 5}},
                "user_id": "1",
                "is_public": True,
                "created_at": now, "updated_at": now
            })
            item_id = str(res.inserted_id)

        s3 = mock.Mock()
        s3.get_object.return_value = {
            "Body": _FakeBody(b"S3DATA"),
            "ContentType": "application/pdf"
        }

        with mock.patch.object(items_mod, "get_file_backend",
                               return_value="s3"):
            with mock.patch.object(items_mod, "get_s3_client_and_bucket",
                                   return_value=(s3, "b", "pfx/")):
                with self._as(ANON):
                    r = self.client.get(f"/item-file/{item_id}/a.txt")

        self.assertEqual(200, r.status_code)
        self.assertEqual(b"S3DATA", r.data)
        self.assertEqual("application/pdf", r.mimetype)
        self.assertTrue(s3.get_object.called)
        args, kwargs = s3.get_object.call_args
        self.assertEqual("b", kwargs["Bucket"])
        self.assertEqual("pfx/fileid1", kwargs["Key"])

    def test_s3_create_upload_and_public_download(self):
        s3, ctx = self._mock_s3_ctx(
            upload_ok=True, get_ok=True,
            content=b"HELLO", content_type="text/plain")

        data = {"title": "doc", "attachment": {"$ref": "/files/a.txt"}}
        payload = {
            "data": json.dumps(data),
            "is_public": "1",
            "a.txt": (io.BytesIO(b"HELLO"), "a.txt", "text/plain"),
        }

        with ctx:
            with self._as(USER_A):
                r = self.client.post(
                    "/item/docs", data=payload,
                    content_type="multipart/form-data"
                )
        self.assertEqual(201, r.status_code)
        item_id = _json(r)["id"]
        self.assertTrue(s3.upload_fileobj.called)

        with ctx:
            with self._as(ANON):
                d = self.client.get(f"/item-file/{item_id}/a.txt")
        self.assertEqual(200, d.status_code)
        self.assertEqual(b"HELLO", d.data)
        self.assertTrue(s3.get_object.called)

    def test_s3_patch_replace_and_drop_triggers_deletes(self):
        s3, ctx = self._mock_s3_ctx(upload_ok=True, get_ok=True)

        data = {"title": "doc", "attachment": {"$ref": "/files/a.txt"}}
        payload1 = {"data": json.dumps(data),
                    "a.txt": (io.BytesIO(b"v1"), "a.txt", "text/plain")}
        with ctx:
            with self._as(USER_A):
                r1 = self.client.post("/item/docs", data=payload1,
                                      content_type="multipart/form-data")
        self.assertEqual(201, r1.status_code)
        item_id = _json(r1)["id"]

        payload2 = {"data": json.dumps(data),
                    "a.txt": (io.BytesIO(b"v2"), "a.txt", "text/plain")}
        with ctx:
            with self._as(USER_A):
                r2 = self.client.patch(f"/item/docs/{item_id}?include_data=1",
                                       data=payload2,
                                       content_type="multipart/form-data")
        self.assertEqual(200, r2.status_code)

        payload3 = {"data": json.dumps({"title": "doc", "attachment": None})}
        with ctx:
            with self._as(USER_A):
                r3 = self.client.patch(
                    f"/item/docs/{item_id}?include_data=1", data=payload3,
                    content_type="multipart/form-data"
                )
        self.assertEqual(200, r3.status_code)
        self.assertEqual({}, _json(r3)["files"])

        self.assertGreaterEqual(s3.upload_fileobj.call_count, 2)
        self.assertGreaterEqual(s3.delete_object.call_count, 1)

    def test_s3_upload_failure_returns_500(self):
        s3, ctx = self._mock_s3_ctx(upload_ok=False)

        data = {"title": "doc", "attachment": {"$ref": "/files/a.txt"}}
        payload = {"data": json.dumps(data),
                   "a.txt": (io.BytesIO(b"x"), "a.txt", "text/plain")}

        with ctx:
            with self._as(USER_A):
                r = self.client.post("/item/docs", data=payload,
                                     content_type="multipart/form-data")
        self.assertEqual(500, r.status_code)
        self.assertEqual("File storage error", _json(r)["error"])
        self.assertTrue(s3.upload_fileobj.called)

    def test_s3_download_missing_returns_404(self):
        s3, ctx = self._mock_s3_ctx(upload_ok=True, get_ok=False)

        data = {"title": "doc", "attachment": {"$ref": "/files/a.txt"}}
        payload = {
            "data": json.dumps(data),
            "is_public": "1",
            "a.txt": (io.BytesIO(b"HELLO"), "a.txt", "text/plain"),
        }

        with ctx:
            with self._as(USER_A):
                r = self.client.post("/item/docs", data=payload,
                                     content_type="multipart/form-data")
        self.assertEqual(201, r.status_code)
        item_id = _json(r)["id"]

        with ctx:
            with self._as(ANON):
                d = self.client.get(f"/item-file/{item_id}/a.txt")
        self.assertEqual(404, d.status_code)
        self.assertEqual("File not found", _json(d)["error"])
        self.assertTrue(s3.get_object.called)

    def test_s3_bytes_read_zero_returns_missing_ref_400(self):
        """
        Covers the case you mentioned: counting_stream.bytes_read == 0.
        In this case store_uploaded_file() should return None, and
        validate_file_refs() will report missing=['a.txt'].
        """
        s3, ctx = self._mock_s3_ctx(upload_ok=True, get_ok=True,
                                    bytes_read_override=0)

        data = {"title": "doc", "attachment": {"$ref": "/files/a.txt"}}
        payload = {
            "data": json.dumps(data),
            "is_public": "1",
            "a.txt": (io.BytesIO(b"HELLO"), "a.txt", "text/plain"),
        }

        with ctx:
            with self._as(USER_A):
                r = self.client.post("/item/docs", data=payload,
                                     content_type="multipart/form-data")
        self.assertEqual(400, r.status_code)
        self.assertIn("File references validation failed", _json(r)["error"])
        self.assertTrue(s3.upload_fileobj.called)

    def test_get_s3_client_and_bucket_parsing_paths(self):
        # string bucket path
        with self.app.app_context():
            self.app.config["S3_ITEMS_FILE_STORAGE"] = "mybucket"
            self.app.config[
                "S3_ITEMS_FILE_PREFIX"] = "abc"  # should normalize to abc/
            with mock.patch.object(items_mod.boto3, "client",
                                   return_value=object()) as m:
                s3c, bucket, prefix = items_mod.get_s3_client_and_bucket()
                self.assertEqual("mybucket", bucket)
                self.assertEqual("abc/", prefix)
                self.assertTrue(m.called)

        # dict config path
        with self.app.app_context():
            self.app.config["S3_ITEMS_FILE_STORAGE"] = {"bucket": "b",
                                                        "prefix": "p"}
            with mock.patch.object(items_mod.boto3, "client",
                                   return_value=object()):
                s3c, bucket, prefix = items_mod.get_s3_client_and_bucket()
                self.assertEqual("b", bucket)
                self.assertEqual("p/", prefix)

        # raw json string path
        with self.app.app_context():
            self.app.config[
                "S3_ITEMS_FILE_STORAGE"] = '{"bucket":"b2","prefix":"p2"}'
            with mock.patch.object(items_mod.boto3, "client",
                                   return_value=object()):
                s3c, bucket, prefix = items_mod.get_s3_client_and_bucket()
                self.assertEqual("b2", bucket)
                self.assertEqual("p2/", prefix)

        # invalid dict raises
        with self.app.app_context():
            self.app.config["S3_ITEMS_FILE_STORAGE"] = {"prefix": "x"}
            with self.assertRaises(RuntimeError):
                items_mod.get_s3_client_and_bucket()


# ======================================================================
# EXTRA DIRECT BRANCH TESTS (items.py helpers / edge branches)
# ======================================================================


@unittest.skipIf(
    EXTRAS not in ('form', 'all') and GITHUB, 'Not for extra %s.' % EXTRAS
)
@unittest.skipIf(PLATFORM not in ('darwin', 'linux'),
                 'Not for platform %s.' % PLATFORM)
class TestItemsServiceItemsPyFullBranches(unittest.TestCase):
    def test__abort_direct(self):
        from flask import Flask
        from werkzeug.exceptions import HTTPException
        app = Flask("x")
        with app.test_request_context("/"):
            with self.assertRaises(HTTPException) as ctx:
                items_mod._abort(418, "teapot")
            self.assertEqual(418, ctx.exception.code)

    def test_is_authenticated_user_exception_branch(self):
        class Bad:
            @property
            def is_authenticated(self):
                raise RuntimeError("boom")

            def __bool__(self):
                return True

        self.assertFalse(items_mod.is_authenticated_user(Bad()))

    def test_collect_file_names_in_data_nested(self):
        data = {
            "a": [{"b": {"$ref": "/files/a.txt/extra"}}],
            "c": {"$ref": "/files/b.txt"},
        }
        names = items_mod.collect_file_names_in_data(data)
        self.assertEqual({"a.txt", "b.txt"}, names)

    def test_validate_file_refs_raises(self):
        with self.assertRaises(items_mod.FileRefsError) as ctx:
            items_mod.validate_file_refs({"a.txt"}, {"b.txt": {"id": "1"}})
        self.assertIn("inconsistent", str(ctx.exception).lower())

    def test_sanitize_mq_more_branches(self):
        from werkzeug.exceptions import HTTPException
        with self.assertRaises(HTTPException):
            items_mod._sanitize_mq({"$where": "x"})

        with self.assertRaises(HTTPException):
            items_mod._sanitize_mq({1: "x"})

        out = items_mod._sanitize_mq(
            {"field": {"$regex": "abc", "$options": "i"}})
        self.assertIn("field", out)

    def test_serialize_files_public_weird_inputs(self):
        self.assertEqual({}, items_mod.serialize_files_public("x", None))
        self.assertEqual({}, items_mod.serialize_files_public("x", []))
        out = items_mod.serialize_files_public("x", {"a.txt": "bad"})
        self.assertEqual({}, out)

    def test_delete_files_meta_skips_malformed(self):
        from flask import Flask
        app = Flask("x")
        with app.app_context():
            items_mod.delete_files_meta({"a.txt": "bad"}, mongo_db=None)
            items_mod.delete_files_meta({"a.txt": {"id": None}}, mongo_db=None)

    def test_counting_reader_getattr_passthrough(self):
        fp = io.BytesIO(b"hello")
        r = items_mod._CountingReader(fp)
        self.assertTrue(r.seekable())  # __getattr__
        r.read(2)
        self.assertEqual(2, r.bytes_read)

    def test_store_uploaded_file_s3_returns_none_when_stream_empty(self):
        """
        Directly hits store_uploaded_file() empty stream => None (covers bytes_read == 0 path)
        """
        from flask import Flask
        app = Flask("x")
        with app.test_request_context("/"):
            s3 = mock.Mock()

            def _upload(Fileobj, Bucket, Key, ExtraArgs=None, **kw):
                # read all (stream empty anyway)
                for _ in iter(lambda: Fileobj.read(1024), b""):
                    pass

            s3.upload_fileobj.side_effect = _upload

            with mock.patch.object(items_mod, "get_file_backend",
                                   return_value="s3"):
                with mock.patch.object(items_mod, "get_s3_client_and_bucket",
                                       return_value=(s3, "b", "")):
                    class F:
                        mimetype = "text/plain"
                        stream = io.BytesIO(b"")  # EMPTY

                    meta = items_mod.store_uploaded_file("a.txt", F(),
                                                         mongo_db=None,
                                                         user=USER_A)
                    self.assertIsNone(meta)
