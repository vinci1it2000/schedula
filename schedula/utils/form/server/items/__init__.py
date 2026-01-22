# coding=utf-8
# -*- coding: UTF-8 -*-

from __future__ import annotations

import os

from flask_pymongo import PyMongo

from .crud import bp as crud_bp
from .files import bp as files_bp
from .manage import bp as manage_bp
from .schema import bp as schema_bp


class Items:
    def __init__(self, app=None, *args, **kwargs):
        self.mongo_db = None
        if app is not None:
            self.init_app(app, *args, **kwargs)

    def init_app(self, app, *args, **kwargs):
        app.extensions = getattr(app, "extensions", {})

        app.config["MONGO_URI"] = app.config.get(
            "MONGO_URI", os.environ.get("MONGO_URI")
        )

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
            ("ITEMS_MONGO_MAX_TIME_MS", 2000),
        ]:
            app.config[key] = app.config.get(key, os.environ.get(key, default))

        app.register_blueprint(crud_bp, url_prefix="/item")
        app.register_blueprint(manage_bp, url_prefix="/item")
        app.register_blueprint(schema_bp, url_prefix="/admin/item-schema")
        app.register_blueprint(files_bp, url_prefix="/item-file")

        mongo_uri = app.config.get("MONGO_URI")
        if not mongo_uri:
            raise RuntimeError("MONGO_URI is not set.")
        if app.config.get("MONGO_DB"):
            self.mongo_db = app.config.get("MONGO_DB")
        else:
            pymongo = PyMongo(app, uri=mongo_uri)
            self.mongo_db = pymongo.db

        coll = self.mongo_db.items
        coll.create_index(
            [("category", 1), ("acl_dom", 1), ("updated_at", -1)]
        )
        coll.create_index(
            [("category", 1), ("grants_ref", 1), ("updated_at", -1)]
        )
        coll.create_index([("category", 1), ("_id", -1)])

        app.extensions["item_storage"] = self
