# coding=utf-8
# -*- coding: UTF-8 -*-

from __future__ import annotations

import os.path as osp

from flask import current_app, has_app_context

from contextlib import contextmanager

import casbin
from casbin import util
import sqlalchemy_adapter
from mongo_watcher import new_watcher
from ...extensions import db

_EXT_KEY = "casbin_enforcer"


class Adapter(sqlalchemy_adapter.Adapter):
    @contextmanager
    def _session_scope(self):
        """Provide a transactional scope around a series of operations."""
        if not has_app_context():
            raise RuntimeError(
                "Casbin Adapter requires a Flask app context to use db.session"
            )

        try:
            yield db.session
        except Exception as e:
            db.session.rollback()
            raise e
        finally:
            pass


def get_enforcer() -> casbin.SyncedEnforcer:
    """Return a cached Casbin enforcer.

    The enforcer is stored in `current_app.extensions['casbin_enforcer']`.
    """
    app = current_app
    if _EXT_KEY in app.extensions:
        return app.extensions[_EXT_KEY]

    adapter = Adapter(db.engine)
    adapter.session_local = db.session
    model_path = app.config.get(
        "CASBIN_MODEL_CONF",
        osp.join(osp.dirname(__file__), "model.conf"),
    )
    e = casbin.SyncedEnforcer(model_path, adapter)
    e.add_function("key_match", util.key_match)
    e.enable_auto_save(True)
    uri = app.config.get("MONGO_URI", None)
    enable_watcher = app.config.get("CASBIN_WATCHER_ENABLED")
    if enable_watcher is None:
        enable_watcher = not app.config.get("TESTING", False)
    if uri and enable_watcher:
        watcher = new_watcher(uri)
        watcher.set_update_callback(lambda: e.load_policy())
    # Load from DB
    e.load_policy()

    app.extensions[_EXT_KEY] = e
    return e
