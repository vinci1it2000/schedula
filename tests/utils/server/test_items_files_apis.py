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
from datetime import datetime, timezone
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
                            "id": str(file_id),
                            "user_id": str(self.user.id),
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
        file_id = "u:test/s3-object-id"
        file_name = "manual.pdf"
        file_bytes = b"s3-bytes"

        with self.app.app_context():
            s3_item_id = str(uuid.uuid4())
            self.vdb.items.insert_one(
                {
                    "_id": s3_item_id,
                    "category": "note",
                    "data": {"title": "s3"},
                    "files": {
                        file_name: {
                            "id": file_id,
                            "user_id": str(self.user.id),
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

        class _Body:
            def __init__(self, data: bytes):
                self._data = data
                self._read = False

            def read(self, _n=-1):
                if self._read:
                    return b""
                self._read = True
                return self._data

            def close(self):
                return None

        fake_client = Mock()
        fake_client.get_object.return_value = {
            "Body": _Body(file_bytes),
            "ContentType": "application/pdf",
        }

        with patch(
                "schedula.utils.form.server.items.files.get_s3_client_and_bucket",
                return_value=(fake_client, "test-bucket", ""),
        ):
            # Call file download with valid S3 file metadata.
            r = self.auth_client.get(
                f"/item-file/{s3_item_id}/manual.pdf",
                headers=self._auth_headers(),
            )

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers.get("Content-Type"), "application/pdf")
        self.assertIn("manual.pdf", r.headers.get("Content-Disposition", ""))
        self.assertEqual(r.data, file_bytes)

    def test_upload_file_s3_bucket_string_config(self):
        self.app.config["S3_ITEMS_FILE_STORAGE"] = "test-bucket"
        self.app.config["S3_ITEMS_FILE_ENDPOINT"] = "http://localhost:9000"
        self.app.config["S3_ITEMS_FILE_REGION"] = "eu-west-1"
        self.app.config["S3_ITEMS_FILE_ACCESS_KEY"] = "access"
        self.app.config["S3_ITEMS_FILE_SECRET_KEY"] = "secret"
        self.app.config["S3_ITEMS_FILE_USE_SSL"] = False
        self.app.config["S3_ITEMS_FILE_PREFIX"] = "items"

        fake_client = Mock()
        fake_client.upload_fileobj = Mock(
            side_effect=lambda stream, *_args, **_kwargs: stream.read()
        )

        data = {
            "data": '{"doc": {"$ref": "/files/attachment"}}',
            "attachment": (io.BytesIO(b"hello s3"), "upload.txt"),
        }

        with patch("boto3.client", return_value=fake_client) as boto_client:
            r = self.auth_client.post(
                "/item/note?include_data=1",
                data=data,
                headers=self._auth_headers(),
                content_type="multipart/form-data",
            )

        self.assertEqual(r.status_code, 201)
        body = r.get_json(silent=True) or {}
        self.assertIn("files", body)
        self.assertIn("attachment", body.get("files", {}))

        boto_client.assert_called_once()
        _, kwargs = boto_client.call_args
        self.assertEqual(kwargs.get("endpoint_url"), "http://localhost:9000")
        self.assertEqual(kwargs.get("region_name"), "eu-west-1")
        self.assertEqual(kwargs.get("aws_access_key_id"), "access")
        self.assertEqual(kwargs.get("aws_secret_access_key"), "secret")
        self.assertEqual(kwargs.get("use_ssl"), False)
        self.assertIsInstance(kwargs.get("config"), BotoConfig)

        upload_args, upload_kwargs = fake_client.upload_fileobj.call_args
        self.assertEqual(upload_args[1], "test-bucket")
        self.assertTrue(upload_args[2].startswith("items/"))
        self.assertEqual(
            upload_kwargs.get("ExtraArgs", {}).get("Metadata", {}).get("name"),
            "attachment",
        )

    def test_upload_file_s3_dict_config(self):
        self.app.config["S3_ITEMS_FILE_STORAGE"] = {
            "bucket": "test-bucket",
            "prefix": "docs",
            "endpoint_url": "http://localhost:9000",
            "region_name": "us-east-1",
            "aws_access_key_id": "access",
            "aws_secret_access_key": "secret",
            "use_ssl": True,
        }

        fake_client = Mock()
        fake_client.upload_fileobj = Mock(
            side_effect=lambda stream, *_args, **_kwargs: stream.read()
        )

        data = {
            "data": '{"doc": {"$ref": "/files/attachment"}}',
            "attachment": (io.BytesIO(b"hello s3"), "upload.txt"),
        }

        with patch("boto3.client", return_value=fake_client) as boto_client:
            r = self.auth_client.post(
                "/item/note?include_data=1",
                data=data,
                headers=self._auth_headers(),
                content_type="multipart/form-data",
            )

        self.assertEqual(r.status_code, 201)
        body = r.get_json(silent=True) or {}
        self.assertIn("files", body)
        self.assertIn("attachment", body.get("files", {}))

        boto_client.assert_called_once()
        _, kwargs = boto_client.call_args
        self.assertEqual(kwargs.get("endpoint_url"), "http://localhost:9000")
        self.assertEqual(kwargs.get("region_name"), "us-east-1")
        self.assertEqual(kwargs.get("aws_access_key_id"), "access")
        self.assertEqual(kwargs.get("aws_secret_access_key"), "secret")
        self.assertEqual(kwargs.get("use_ssl"), True)
        self.assertIsInstance(kwargs.get("config"), BotoConfig)

        upload_args, upload_kwargs = fake_client.upload_fileobj.call_args
        self.assertEqual(upload_args[1], "test-bucket")
        self.assertTrue(upload_args[2].startswith("docs/"))
        self.assertEqual(
            upload_kwargs.get("ExtraArgs", {}).get("Metadata", {}).get("name"),
            "attachment",
        )


if __name__ == "__main__":
    unittest.main()
