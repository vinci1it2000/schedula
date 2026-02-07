# coding=utf-8
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2026, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');

"""Contracts API service (workflow JSON a stati)."""


class Contracts:
    def __init__(self, app=None, *args, **kwargs):
        if app is not None:
            self.init_app(app, *args, **kwargs)

    def init_app(self, app, *args, **kwargs):
        app.extensions = getattr(app, "extensions", {})
        defaults = {
            "CONTRACTS_ACTION_TYPES": "noop",
            "CONTRACTS_ENABLED": True,
        }
        for k, v in defaults.items():
            app.config[k] = app.config.get(k, v)
        from .routes import bp
        from .routes import _ensure_indexes

        with app.app_context():
            _ensure_indexes()
        app.register_blueprint(bp)
        app.extensions["contracts"] = self
