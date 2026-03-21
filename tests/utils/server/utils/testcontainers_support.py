from __future__ import annotations

import os
import time
import unittest
import uuid
from urllib.parse import quote_plus, urlsplit, urlunsplit


def _ensure_docker_host() -> None:
    desktop_sock = os.path.join(os.path.expanduser("~"), ".docker", "run", "docker.sock")
    if not os.environ.get("DOCKER_HOST") and os.path.exists(desktop_sock):
        os.environ["DOCKER_HOST"] = f"unix://{desktop_sock}"


def _wait_for_mongo(uri: str, timeout_s: int = 60) -> None:
    from pymongo import MongoClient

    deadline = time.time() + timeout_s
    last_error = None
    while time.time() < deadline:
        client = None
        try:
            client = MongoClient(uri, serverSelectionTimeoutMS=1000)
            client.admin.command("ping")
            return
        except Exception as ex:  # pragma: no cover
            last_error = ex
            time.sleep(1)
        finally:
            if client is not None:
                client.close()
    raise RuntimeError("MongoDB container not ready") from last_error


def _wait_for_mysql(host: str, port: int, user: str, password: str, db_name: str, timeout_s: int = 60) -> None:
    import pymysql

    deadline = time.time() + timeout_s
    last_error = None
    while time.time() < deadline:
        conn = None
        try:
            conn = pymysql.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                database=db_name,
                connect_timeout=1,
                read_timeout=1,
                write_timeout=1,
            )
            return
        except Exception as ex:  # pragma: no cover
            last_error = ex
            time.sleep(1)
        finally:
            if conn is not None:
                conn.close()
    raise RuntimeError("MySQL container not ready") from last_error


class MongoMySqlContainersMixin:
    _mongo_container = None
    _mongo_base_uri = ""
    _mysql_container = None
    _sqlalchemy_uri = ""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        _ensure_docker_host()
        try:
            from testcontainers.core.container import DockerContainer
        except Exception as ex:  # pragma: no cover
            raise unittest.SkipTest("server tests require testcontainers[mongodb,mysql]") from ex

        try:
            cls._mongo_container = DockerContainer("mongo:7.0").with_exposed_ports(27017)
            cls._mongo_container.start()
            mongo_host = cls._mongo_container.get_container_host_ip()
            mongo_port = int(cls._mongo_container.get_exposed_port(27017))
            cls._mongo_base_uri = f"mongodb://{mongo_host}:{mongo_port}"
            _wait_for_mongo(cls._mongo_base_uri)

            mysql_user = "test"
            mysql_password = "test"
            mysql_db = "schedula"
            cls._mysql_container = (
                DockerContainer("mysql:8.0")
                .with_env("MYSQL_DATABASE", mysql_db)
                .with_env("MYSQL_USER", mysql_user)
                .with_env("MYSQL_PASSWORD", mysql_password)
                .with_env("MYSQL_ROOT_PASSWORD", "root")
                .with_exposed_ports(3306)
            )
            cls._mysql_container.start()
            mysql_host = cls._mysql_container.get_container_host_ip()
            mysql_port = int(cls._mysql_container.get_exposed_port(3306))
            _wait_for_mysql(mysql_host, mysql_port, mysql_user, mysql_password, mysql_db)
            cls._sqlalchemy_uri = (
                f"mysql+pymysql://{quote_plus(mysql_user)}:{quote_plus(mysql_password)}"
                f"@{mysql_host}:{mysql_port}/{mysql_db}"
            )
        except Exception as ex:  # pragma: no cover
            raise unittest.SkipTest(
                "server tests require Docker with runnable MongoDB and MySQL containers"
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

    def _test_mongo_uri(self, prefix: str) -> str:
        self.mongo_db_name = f"{prefix}_{uuid.uuid4().hex}"
        parts = urlsplit(self.__class__._mongo_base_uri)
        query = parts.query
        if "authSource=" not in query:
            query = f"{query}&authSource=admin" if query else "authSource=admin"
        return urlunsplit((parts.scheme, parts.netloc, f"/{self.mongo_db_name}", query, parts.fragment))


class MinioContainerMixin:
    _minio_container = None
    _minio_endpoint = ""
    _minio_access_key = "minioadmin"
    _minio_secret_key = "minioadmin"

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        _ensure_docker_host()
        try:
            import boto3
            from testcontainers.core.container import DockerContainer
        except Exception as ex:  # pragma: no cover
            raise unittest.SkipTest("S3 tests require boto3 and testcontainers") from ex

        try:
            cls._minio_container = (
                DockerContainer("minio/minio:RELEASE.2024-01-18T22-51-28Z")
                .with_env("MINIO_ROOT_USER", cls._minio_access_key)
                .with_env("MINIO_ROOT_PASSWORD", cls._minio_secret_key)
                .with_exposed_ports(9000)
                .with_command('server /data --address ":9000"')
            )
            cls._minio_container.start()
            host = cls._minio_container.get_container_host_ip()
            port = cls._minio_container.get_exposed_port(9000)
            cls._minio_endpoint = f"http://{host}:{port}"

            client = boto3.client(
                "s3",
                endpoint_url=cls._minio_endpoint,
                region_name="us-east-1",
                aws_access_key_id=cls._minio_access_key,
                aws_secret_access_key=cls._minio_secret_key,
            )
            last_error = None
            for _ in range(60):
                try:
                    client.list_buckets()
                    last_error = None
                    break
                except Exception as ex:  # pragma: no cover
                    last_error = ex
                    time.sleep(1)
            if last_error is not None:
                raise last_error
        except Exception as ex:  # pragma: no cover
            raise unittest.SkipTest("S3 tests require Docker with a runnable MinIO container") from ex

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            if cls._minio_container is not None:
                cls._minio_container.stop()
        finally:
            cls._minio_container = None
            cls._minio_endpoint = ""
            super().tearDownClass()
