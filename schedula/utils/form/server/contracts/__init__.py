# coding=utf-8
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2026, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');

"""Contracts API service (workflow JSON a stati)."""

import click

from ..extensions import db


class Contracts:
    def __init__(self, app=None, *args, **kwargs):
        if app is not None:
            self.init_app(app, *args, **kwargs)

    def init_app(self, app, *args, **kwargs):
        app.extensions = getattr(app, "extensions", {})
        defaults = {
            "CONTRACTS_ENABLED": False,
        }
        for k, v in defaults.items():
            app.config[k] = app.config.get(k, v)
        from .routes import bp
        from .routes import _ensure_indexes

        with app.app_context():
            _ensure_indexes()

        @app.cli.command("contracts-worker")
        @click.option("--poll-interval", default=5.0, type=float)
        def contracts_worker(poll_interval: float):
            from .schedule import worker_loop

            worker_loop(poll_interval_s=float(poll_interval))

        app.register_blueprint(bp)
        app.extensions["contracts"] = self
        from ..utils import configure_sherlock
        db.add_seed(configure_sherlock)
