# coding=utf-8
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2026, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');

"""Contracts API service (workflow JSON a stati)."""

from ..extensions import db


class Contracts:
    def __init__(self, app=None, *args, **kwargs):
        if app is not None:
            self.init_app(app, *args, **kwargs)

    def init_app(self, app, *args, **kwargs):
        app.extensions = getattr(app, "extensions", {})
        from .routes import bp
        from .routes import _ensure_indexes

        with app.app_context():
            _ensure_indexes()

        app.register_blueprint(bp, url_prefix="/contracts")
        app.extensions["contracts"] = self
        from ..utils import configure_sherlock
        db.add_seed(configure_sherlock)
