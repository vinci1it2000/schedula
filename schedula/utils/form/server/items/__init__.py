# coding=utf-8
# -*- coding: UTF-8 -*-

from __future__ import annotations

import os

import click
from flask.cli import with_appcontext

from ..utils import abort_json, get_mongo, config_get


def normalize_category(category: str) -> str:
    c = (category or "").strip()
    if not c:
        abort_json(400, "Missing category")
    if any(ch.isspace() for ch in c):
        abort_json(400, "Invalid category")
    return c


class Items:
    def __init__(self, app=None, *args, **kwargs):
        if app is not None:
            self.init_app(app, *args, **kwargs)

    def init_app(self, app, *args, **kwargs):
        app.extensions = getattr(app, "extensions", {})

        app.config["S3_ITEMS_FILE_STORAGE"] = app.config.get(
            "S3_ITEMS_FILE_STORAGE",
            os.environ.get("S3_ITEMS_FILE_STORAGE", None),
        )

        for key, default in [
            ("S3_ITEMS_FILE_ENDPOINT", None),
            ("S3_ITEMS_FILE_REGION", "us-east-1"),
            ("S3_ITEMS_FILE_ACCESS_KEY", None),
            ("S3_ITEMS_FILE_SECRET_KEY", None),
            ("S3_ITEMS_FILE_USE_SSL", None),
            ("S3_ITEMS_FILE_PREFIX", ""),
            ("ITEM_ARTIFACT_STAGING_TTL_SECONDS", 3600),
            ("MONGO_MAX_TIME_MS", 2000),
        ]:
            app.config[key] = app.config.get(key, os.environ.get(key, default))

        from .crud import bp as crud_bp
        from .files import bp as files_bp
        from .manage import bp as manage_bp
        from .schema import bp as schema_bp
        app.register_blueprint(crud_bp, url_prefix="/item")
        app.register_blueprint(manage_bp, url_prefix="/item")
        app.register_blueprint(schema_bp, url_prefix="/admin/item-schema")
        app.register_blueprint(files_bp, url_prefix="/item-file")

        coll = get_mongo(app, collection=config_get("ITEMS_COLLECTION", "items", app=app))
        coll.create_index(
            [("category", 1), ("acl_dom", 1), ("updated_at", -1)]
        )
        coll.create_index([("category", 1), ("_id", -1)])
        coll.create_index([("category", 1), ("public", 1), ("updated_at", -1)])
        coll.create_index([("category", 1), ("created_at", -1)])

        cleanup_coll = get_mongo(
            app,
            collection=config_get("ITEM_FILES_STAGING_CLEANUP_COLLECTION", "item_file_staging_cleanup", app=app),
        )
        cleanup_coll.create_index([("expires_at", 1)])
        cleanup_coll.create_index([("storage_key", 1)], unique=True)

        @app.cli.command("item-files-cleanup-staging")
        @with_appcontext
        def item_files_cleanup_staging_command():
            from .files import cleanup_expired_staging_files_count

            deleted = cleanup_expired_staging_files_count()
            click.echo(f"Deleted {deleted} expired staged file(s).")
