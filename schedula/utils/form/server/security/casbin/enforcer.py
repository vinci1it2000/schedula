# coding=utf-8
# -*- coding: UTF-8 -*-

from __future__ import annotations

import os
import os.path as osp
import atexit
from contextlib import contextmanager

import casbin
import threading
import sqlalchemy_adapter
from casbin import util
from flask import current_app, has_app_context

from .watcher import new_watcher
from ...extensions import db

_EXT_KEY = "casbin_enforcer"
_WATCHER_KEY = "casbin_watcher"
_WATCHER_ATEXIT_KEY = "casbin_watcher_atexit_registered"

_init_lock = threading.Lock()
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


def _yield_users(e, role, _seen=None):
    if role not in _seen:
        _seen.add(role)
        if role.startswith("u:"):
            yield role
        else:
            for v in e.get_users_for_role(role):
                if v not in _seen:
                    yield from _yield_users(e, v, _seen)


class Enforcer(casbin.SyncedEnforcer):
    def get_implicit_users_for_role(self, role, _seen=None):
        with self._rl:
            _seen = set() if _seen is None or _seen is False else _seen
            return sorted(set(list(_yield_users(self._e, role, _seen))))


def get_enforcer() -> Enforcer:
    """Return a cached Casbin enforcer.

    The enforcer is stored in `current_app.extensions['casbin_enforcer']`.
    """
    app = current_app._get_current_object()
    if _EXT_KEY in app.extensions:
        return app.extensions[_EXT_KEY]
    with _init_lock:
        if _EXT_KEY in app.extensions:
            return app.extensions[_EXT_KEY]
        adapter = Adapter(db.engine)
        adapter.session_local = db.session
        model_path = app.config.get(
            "CASBIN_MODEL_CONF",
            osp.join(osp.dirname(__file__), "model.conf"),
        )
        e = Enforcer(model_path, adapter)
        e.add_function("key_match", util.key_match)
        e.enable_auto_save(True)
        uri = app.config.get("MONGO_URI", None)
        enable_watcher = str(app.config.get(
            "CASBIN_WATCHER_ENABLED", os.environ.get("CASBIN_WATCHER_ENABLED", "false")
        )).lower() == "true"

        if uri and enable_watcher:
            watcher = new_watcher(uri, app=app)
            watcher.bind_enforcer(e)
            e.set_watcher(watcher)
            watcher.start()
            app.extensions[_WATCHER_KEY] = watcher
            if not app.extensions.get(_WATCHER_ATEXIT_KEY):
                def _shutdown_watcher() -> None:
                    try:
                        w = app.extensions.get(_WATCHER_KEY)
                        if w is not None:
                            w.stop()
                    except Exception:
                        pass

                atexit.register(_shutdown_watcher)
                app.extensions[_WATCHER_ATEXIT_KEY] = True
        # Load from DB
        e.load_policy()

        app.extensions[_EXT_KEY] = e
    return e
