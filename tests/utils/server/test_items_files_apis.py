# coding: utf-8
from __future__ import annotations

try:
    from tests.utils.server._unittest_guard import ensure_server_test_env
except Exception:
    from _unittest_guard import ensure_server_test_env

ensure_server_test_env()

import io
import os
import sys
import urllib.request
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, cast

import boto3
from itsdangerous import URLSafeSerializer

import gridfs
from botocore.config import Config as BotoConfig
from flask import Flask
from flask_security.utils import hash_password
from pymongo import MongoClient

# Add project root to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from schedula.utils.form.server import basic_app
from schedula.utils.form.server.extensions import db as _db
from schedula.utils.form.server.security import User
from schedula.utils.form.server.security.casbin.bootstrap import bootstrap_user
from tests.utils.server.utils.testcontainers_support import MinioContainerMixin, MongoMySqlContainersMixin


class TestItemsFilesApis(MinioContainerMixin, MongoMySqlContainersMixin, unittest.TestCase):
    """Functional tests for item file download endpoints."""

    def setUp(self):
        os.environ.pop("MONGO_URI", None)

        self.app = Flask("schedula_test_app")

        class DummySitemap:
            verify_file_handler = None
            basic_app_config = None

        self.mongo_uri = self._test_mongo_uri("schedula_items_files")
        self.mongo_client = MongoClient(self.mongo_uri)
        self.vdb = self.mongo_client[self.mongo_db_name]
        self.s3_bucket = f"items-files-{uuid.uuid4().hex[:16]}"

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
            MONGO_DB=self.vdb,
            MAIL_SUPPRESS_SEND=True,
            ITEMS_STORAGE_ENABLED=True,
            FILES_STORAGE_ENABLED=False,
            S3_ITEMS_FILE_STORAGE=False,
            CONTACT_ENABLED=True,
            SCHEDULA_CREDITS_ENABLED=False,
            SCHEDULA_EXPORT_FORM_ENABLED=False,
            SCHEDULA_GDPR_ENABLED=False,
            SCHEDULA_LOCALE_ENABLED=False,
            SCHEDULA_SECRETS_ENABLED=False,
            OPENAPI_ENABLED=True,
            CASBIN_ADMIN_ENABLED=True,
        )

        with self.app.app_context():
            basic_app(DummySitemap(), self.app, config)
            _db.create_all()

            self.user = self._create_user("files_user@gmail.com")
            bootstrap_user(self.user.id)

            self.other_user = self._create_user("files_other@gmail.com")
            bootstrap_user(self.other_user.id)

            self.item_id = str(uuid.uuid4())
            file_name = "report.txt"
            file_bytes = b"hello world"

            fs = gridfs.GridFS(cast(Any, self.vdb))
            file_id = fs.put(file_bytes, filename=file_name, content_type="text/plain", _id=str(uuid.uuid4()))

            self.vdb.items.insert_one(
                {
                    "_id": self.item_id,
                    "category": "note",
                    "data": {"title": "hello"},
                    "files": {
                        file_name: {
                            "storage_key": str(file_id),
                            "content_type": "text/plain",
                            "size": len(file_bytes),
                        }
                    },
                    "acl_dom": f"acl:user:{self.user.id}",
                    "created_by": str(self.user.id),
                    "updated_by": str(self.user.id),
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }
            )

        self.s3_client = boto3.client(
            "s3",
            endpoint_url=self.__class__._minio_endpoint,
            region_name="us-east-1",
            aws_access_key_id=self.__class__._minio_access_key,
            aws_secret_access_key=self.__class__._minio_secret_key,
            config=BotoConfig(signature_version="s3v4", s3={"addressing_style": "path"}),
        )
        self.s3_client.create_bucket(Bucket=self.s3_bucket)

        self.auth_client = self.app.test_client()
        self.anon_client = self.app.test_client()
        self.user_token = self._login_token("files_user@gmail.com")
        self.other_token = self._login_token("files_other@gmail.com")

    def tearDown(self):
        with self.app.app_context():
            _db.session.remove()
            _db.drop_all()
        if getattr(self, "mongo_client", None) is not None:
            try:
                self.mongo_client.drop_database(self.mongo_db_name)
            except Exception:
                pass
            self.mongo_client.close()
        if getattr(self, "s3_client", None) is not None:
            try:
                response = self.s3_client.list_objects_v2(Bucket=self.s3_bucket)
                for obj in response.get("Contents", []) or []:
                    self.s3_client.delete_object(Bucket=self.s3_bucket, Key=obj["Key"])
                self.s3_client.delete_bucket(Bucket=self.s3_bucket)
            except Exception:
                pass

    def _enable_s3_backend(self, prefix: str = "") -> None:
        self.app.config["S3_ITEMS_FILE_STORAGE"] = self.s3_bucket
        self.app.config["S3_ITEMS_FILE_ENDPOINT"] = self.__class__._minio_endpoint
        self.app.config["S3_ITEMS_FILE_REGION"] = "us-east-1"
        self.app.config["S3_ITEMS_FILE_ACCESS_KEY"] = self.__class__._minio_access_key
        self.app.config["S3_ITEMS_FILE_SECRET_KEY"] = self.__class__._minio_secret_key
        self.app.config["S3_ITEMS_FILE_USE_SSL"] = False
        self.app.config["S3_ITEMS_FILE_PREFIX"] = prefix

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
            if not getattr(user, "fs_uniquifier", None):
                user.fs_uniquifier = str(uuid.uuid4())
            user.active = True
        user.confirmed_at = datetime.utcnow()
        _db.session.commit()
        return user

    def _login_token(self, email: str) -> str:
        login_client = self.app.test_client()
        # Call login to obtain auth token.
        resp = login_client.post(
            "/user/login", json={"email": email, "password": "UserPass123!"}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json(silent=True) or {}
        token = data.get("response", {}).get("user", {}).get("token")
        self.assertIsNotNone(token)
        return token

    def _auth_headers(self) -> dict:
        return {"Authentication-Token": self.user_token}

    def _other_headers(self) -> dict:
        return {"Authentication-Token": self.other_token}

    def test_download_file_success(self):
        # Call file download with valid item and file name.
        r = self.auth_client.get(
            f"/item-file/{self.item_id}/report.txt", headers=self._auth_headers()
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers.get("Content-Type"), "text/plain; charset=utf-8")
        self.assertIn("report.txt", r.headers.get("Content-Disposition", ""))
        self.assertEqual(r.data, b"hello world")

    def test_download_file_invalid_name(self):
        # Call file download with invalid file name.
        r = self.auth_client.get(
            f"/item-file/{self.item_id}/.. bad", headers=self._auth_headers()
        )
        self.assertEqual(r.status_code, 400)
        data = r.get_json(silent=True) or {}
        self.assertIn("error", data)
        self.assertEqual(data.get("error"), "Invalid file name")

    def test_download_file_missing_item(self):
        missing_id = str(uuid.uuid4())
        # Call file download with missing item id.
        r = self.auth_client.get(
            f"/item-file/{missing_id}/report.txt", headers=self._auth_headers()
        )
        self.assertEqual(r.status_code, 404)
        data = r.get_json(silent=True) or {}
        self.assertIn("error", data)
        self.assertEqual(data.get("error"), "Item not found")

    def test_download_file_missing_file(self):
        # Call file download with missing file name.
        r = self.auth_client.get(
            f"/item-file/{self.item_id}/missing.txt", headers=self._auth_headers()
        )
        self.assertEqual(r.status_code, 404)
        data = r.get_json(silent=True) or {}
        self.assertIn("error", data)
        self.assertEqual(data.get("error"), "File not found")

    def test_download_file_access_denied(self):
        # Call file download without authentication.
        r = self.anon_client.get(f"/item-file/{self.item_id}/report.txt")
        self.assertEqual(r.status_code, 401)
        data = r.get_json(silent=True) or {}
        self.assertIn("error", data)
        self.assertEqual(data.get("error"), "Access denied")

    def test_download_file_forbidden_other_user(self):
        # Call file download as a different authenticated user.
        r = self.auth_client.get(
            f"/item-file/{self.item_id}/report.txt", headers=self._other_headers()
        )
        self.assertEqual(r.status_code, 403)
        data = r.get_json(silent=True) or {}
        self.assertIn("error", data)
        self.assertEqual(data.get("error"), "Access denied")

    def test_download_file_anonymous_allowed_when_item_public_flag_true(self):
        with self.app.app_context():
            self.vdb.items.update_one(
                {"_id": self.item_id},
                {"$set": {"public": True}},
            )

        # Anonymous can read the item when `public` data flag is enabled.
        item_r = self.anon_client.get(f"/item/note/{self.item_id}")
        self.assertEqual(item_r.status_code, 200)
        item_data = item_r.get_json(silent=True) or {}
        self.assertEqual(item_data.get("id"), self.item_id)

        # Anonymous can also download related files.
        file_r = self.anon_client.get(
            f"/item-file/{self.item_id}/report.txt", buffered=True
        )
        self.assertEqual(file_r.status_code, 200)
        self.assertEqual(file_r.data, b"hello world")

    def test_download_file_s3_success(self):
        # Call file download with S3 backend enabled.
        self._enable_s3_backend()
        file_id = f"u:{self.user.id}/s3-object-id"
        file_name = "manual.pdf"
        file_bytes = b"s3-bytes"
        self.s3_client.put_object(
            Bucket=self.s3_bucket,
            Key=file_id,
            Body=file_bytes,
            ContentType="application/pdf",
        )

        with self.app.app_context():
            s3_item_id = str(uuid.uuid4())
            self.vdb.items.insert_one(
                {
                    "_id": s3_item_id,
                    "category": "note",
                    "data": {"title": "s3"},
                    "files": {
                        file_name: {
                            "storage_key": file_id,
                            "content_type": "application/pdf",
                            "size": len(file_bytes),
                        }
                    },
                    "acl_dom": f"acl:user:{self.user.id}",
                    "created_by": str(self.user.id),
                    "updated_by": str(self.user.id),
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }
            )
        r = self.auth_client.get(
            f"/item-file/{s3_item_id}/{file_name}",
            headers=self._auth_headers(),
        )

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers.get("Content-Type"), "application/pdf")
        self.assertIn(file_name, r.headers.get("Content-Disposition", ""))
        self.assertEqual(r.data, file_bytes)

    def test_upload_file_s3_bucket_string_config(self):
        self._enable_s3_backend(prefix="items")
        self.app.config["S3_ITEMS_FILE_REGION"] = "eu-west-1"

        data = {
            "data": '{"doc": {"$ref": "/files/report.pdf"}}',
            "report.pdf": (io.BytesIO(b"hello s3"), "upload.txt"),
        }

        r = self.auth_client.post(
            "/item/note?include_data=1",
            data=data,
            headers=self._auth_headers(),
            content_type="multipart/form-data",
        )

        self.assertEqual(r.status_code, 201)
        body = r.get_json(silent=True) or {}
        self.assertIn("files", body)
        self.assertIn("report.pdf", body.get("files", {}))

        stored_item = self.vdb.items.find_one({"_id": body["id"]}) or {}
        key = ((stored_item.get("files") or {}).get("report.pdf") or {}).get("storage_key")
        obj = self.s3_client.get_object(Bucket=self.s3_bucket, Key=f"items/{key}")
        self.assertEqual(obj["ContentType"], "text/plain")
        self.assertEqual(obj["Metadata"].get("name"), "report.pdf")
        self.assertEqual(obj["Body"].read(), b"hello s3")

    def test_upload_file_s3_dict_config(self):
        self.app.config["S3_ITEMS_FILE_STORAGE"] = {
            "bucket": self.s3_bucket,
            "prefix": "docs",
            "endpoint_url": self.__class__._minio_endpoint,
            "region_name": "us-east-1",
            "aws_access_key_id": self.__class__._minio_access_key,
            "aws_secret_access_key": self.__class__._minio_secret_key,
            "use_ssl": False,
        }

        data = {
            "data": '{"doc": {"$ref": "/files/report.pdf"}}',
            "report.pdf": (io.BytesIO(b"hello s3"), "upload.txt"),
        }

        r = self.auth_client.post(
            "/item/note?include_data=1",
            data=data,
            headers=self._auth_headers(),
            content_type="multipart/form-data",
        )

        self.assertEqual(r.status_code, 201)
        body = r.get_json(silent=True) or {}
        self.assertIn("files", body)
        self.assertIn("report.pdf", body.get("files", {}))

        stored_item = self.vdb.items.find_one({"_id": body["id"]}) or {}
        key = ((stored_item.get("files") or {}).get("report.pdf") or {}).get("storage_key")
        obj = self.s3_client.get_object(Bucket=self.s3_bucket, Key=f"docs/{key}")
        self.assertEqual(obj["Metadata"].get("name"), "report.pdf")
        self.assertEqual(obj["Body"].read(), b"hello s3")

    def test_presign_s3_attach_staged_file(self):
        self._enable_s3_backend(prefix="items")
        presign = self.auth_client.post(
            "/item-file/staging/presign/report.pdf",
            headers=self._auth_headers(),
            json={
                "operations": ["put", "head"],
                "mimetype": "application/pdf",
            },
        )

        self.assertEqual(presign.status_code, 200)
        body = presign.get_json(silent=True) or {}
        self.assertTrue((body.get("ref") or "").startswith("/files/staging/"))
        self.assertIn("put", body.get("methods") or {})
        put_headers = (body.get("methods") or {}).get("put", {}).get("headers") or {}
        self.assertNotIn("x-amz-tagging", put_headers)
        self.assertIn("x-amz-meta-name", put_headers)

        request_obj = urllib.request.Request(
            body["methods"]["put"]["url"],
            data=b"hello staged s3 payload",
            method="PUT",
            headers=put_headers,
        )
        with urllib.request.urlopen(request_obj) as response:
            self.assertLess(response.status, 300)

        create = self.auth_client.post(
            "/item/note?include_data=1",
            headers=self._auth_headers(),
            json={"data": {"doc": {"$ref": body["ref"]}}},
        )

        self.assertEqual(create.status_code, 201)
        item = create.get_json(silent=True) or {}
        self.assertEqual(item.get("data", {}).get("doc", {}).get("$ref"), "/files/report.pdf")
        meta = (item.get("files") or {}).get("report.pdf") or {}
        self.assertEqual(meta.get("content_type"), "application/pdf")

        doc = self.vdb.items.find_one({"_id": item.get("id")}) or {}
        stored = (doc.get("files") or {}).get("report.pdf") or {}
        self.assertTrue(str(stored.get("storage_key", "")).startswith("u:"))
        obj = self.s3_client.head_object(Bucket=self.s3_bucket, Key=f"items/{stored['storage_key']}")
        self.assertEqual(obj["ContentType"], "application/pdf")
        self.assertIsNone(
            self.vdb["item_file_staging_cleanup"].find_one(
                {"storage_key": stored.get("storage_key")}
            )
        )

    def test_presign_gridfs_attach_staged_file(self):
        presign = self.auth_client.post(
            "/item-file/staging/presign/report.txt",
            headers=self._auth_headers(),
            json={
                "operations": ["put", "get", "head", "delete"],
                "mimetype": "text/plain",
            },
        )
        self.assertEqual(presign.status_code, 200)
        body = presign.get_json(silent=True) or {}
        self.assertIn("ref", body)
        self.assertIn("expires_at", body)
        self.assertSetEqual(set(body.get("methods", ())), {"put", "get", "head", "delete"})
        put = ((body.get("methods") or {}).get("put") or {}).get("url")
        self.assertIsInstance(put, str)

        upload = self.auth_client.put(
            put,
            data=b"hello staged",
            headers={**self._auth_headers(), "Content-Type": "text/plain"},
        )
        self.assertEqual(upload.status_code, 200)

        create = self.auth_client.post(
            "/item/note?include_data=1",
            headers=self._auth_headers(),
            json={"data": {"doc": {"$ref": body["ref"]}}},
        )
        self.assertEqual(create.status_code, 201)
        item = create.get_json(silent=True) or {}
        self.assertEqual(item.get("data", {}).get("doc", {}).get("$ref"), "/files/report.txt")

        doc = self.vdb.items.find_one({"_id": item.get("id")}) or {}
        stored = (doc.get("files") or {}).get("report.txt") or {}
        self.assertIsNone(
            self.vdb["item_file_staging_cleanup"].find_one(
                {"storage_key": stored.get("storage_key")}
            )
        )

        download = self.auth_client.get(
            f"/item-file/{item.get('id')}/report.txt",
            headers=self._auth_headers(),
        )
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download.data, b"hello staged")

    def test_presign_gridfs_forbids_other_user_attach(self):
        presign = self.auth_client.post(
            "/item-file/staging/presign/secret.txt",
            headers=self._auth_headers(),
            json={"operations": ["put"], "name": "secret", "mimetype": "text/plain"},
        )
        body = presign.get_json(silent=True) or {}
        upload_url = ((body.get("methods") or {}).get("put") or {}).get("url")
        upload = self.auth_client.put(
            upload_url,
            data=b"hello",
            headers={**self._auth_headers(), "Content-Type": "text/plain"},
        )
        self.assertEqual(upload.status_code, 200)

        create = self.auth_client.post(
            "/item/note?include_data=1",
            headers=self._other_headers(),
            json={"data": {"doc": {"$ref": body["ref"]}}},
        )
        self.assertEqual(create.status_code, 403)

    def test_cleanup_staging_cli_removes_expired_gridfs_files(self):
        stale_id = f"u:{self.user.id}/{uuid.uuid4()}"
        fresh_id = f"u:{self.user.id}/{uuid.uuid4()}"
        fs = gridfs.GridFS(cast(Any, self.vdb))
        fs.put(
            b"stale",
            _id=stale_id,
            filename="stale.txt",
            storage_key=f"u:{self.user.id}/stale.txt",
        )
        fs.put(
            b"fresh",
            _id=fresh_id,
            filename="fresh.txt",
            storage_key=f"u:{self.user.id}/fresh.txt",
        )
        cleanup = self.vdb["item_file_staging_cleanup"]
        cleanup.insert_many([
            {
                "storage_key": stale_id,
                "filename": "stale.txt",
                "expires_at": datetime.now(timezone.utc) - timedelta(minutes=10),
            },
            {
                "storage_key": fresh_id,
                "filename": "fresh.txt",
                "expires_at": datetime.now(timezone.utc) + timedelta(minutes=10),
            },
        ])

        runner = self.app.test_cli_runner()
        result = runner.invoke(args=["item-files-cleanup-staging"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Deleted 1 expired staged file(s).", result.output)
        self.assertIsNone(self.vdb["fs.files"].find_one({"_id": stale_id}))
        self.assertIsNotNone(self.vdb["fs.files"].find_one({"_id": fresh_id}))
        self.assertIsNone(cleanup.find_one({"storage_key": stale_id}))
        self.assertIsNotNone(cleanup.find_one({"storage_key": fresh_id}))

    def test_cleanup_staging_cli_removes_expired_s3_files(self):
        self._enable_s3_backend(prefix="items")
        self.s3_client.put_object(Bucket=self.s3_bucket, Key="items/u:1/old.txt", Body=b"old")
        self.s3_client.put_object(Bucket=self.s3_bucket, Key="items/u:1/fresh.txt", Body=b"fresh")
        cleanup = self.vdb["item_file_staging_cleanup"]
        cleanup.insert_many([
            {
                "storage_key": "u:1/old.txt",
                "filename": "old.txt",
                "expires_at": datetime.now(timezone.utc) - timedelta(hours=2),
            },
            {
                "storage_key": "u:1/fresh.txt",
                "filename": "fresh.txt",
                "expires_at": datetime.now(timezone.utc) + timedelta(hours=2),
            },
        ])

        runner = self.app.test_cli_runner()
        result = runner.invoke(args=["item-files-cleanup-staging"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Deleted 1 expired staged file(s).", result.output)
        with self.assertRaises(Exception):
            self.s3_client.head_object(Bucket=self.s3_bucket, Key="items/u:1/old.txt")
        self.s3_client.head_object(Bucket=self.s3_bucket, Key="items/u:1/fresh.txt")
        self.assertIsNone(cleanup.find_one({"storage_key": "u:1/old.txt"}))
        self.assertIsNotNone(cleanup.find_one({"storage_key": "u:1/fresh.txt"}))

    def test_attach_staged_file_expired_returns_410(self):
        signer = URLSafeSerializer(self.app.config["SECRET_KEY"], salt="item-files-staging")
        token = signer.dumps({
            "sub": f"u:{self.user.id}",
            "filename": "expired.txt",
            "mimetype": "text/plain",
            "operations": ["put"],
            "storage_key": f"u:{self.user.id}/{uuid.uuid4().hex}.txt",
            "exp": 1,
        })
        create = self.auth_client.post(
            "/item/note?include_data=1",
            headers=self._auth_headers(),
            json={"data": {"doc": {"$ref": f"/files/staging/{token}"}}},
        )
        self.assertEqual(create.status_code, 410)

    def test_attach_missing_s3_staged_file_returns_404(self):
        self._enable_s3_backend(prefix="items")

        signer = URLSafeSerializer(self.app.config["SECRET_KEY"], salt="item-files-staging")
        token = signer.dumps({
            "sub": f"u:{self.user.id}",
            "filename": "missing.txt",
            "mimetype": "text/plain",
            "operations": ["put"],
            "storage_key": f"u:{self.user.id}/{uuid.uuid4().hex}.txt",
            "exp": int(datetime.now(timezone.utc).timestamp()) + 3600,
        })

        create = self.auth_client.post(
            "/item/note?include_data=1",
            headers=self._auth_headers(),
            json={"data": {"doc": {"$ref": f"/files/staging/{token}"}}},
        )
        self.assertEqual(create.status_code, 404)


if __name__ == "__main__":
    unittest.main()
