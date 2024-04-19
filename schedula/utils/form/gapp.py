# coding=utf-8
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2024, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides the `gunicorn` BaseApplication to run the server in production.
"""
import sys
import runpy
import functools
import os.path as osp
import multiprocessing
from gunicorn.app.base import BaseApplication


@functools.lru_cache()
def _get_module(module, path):
    return runpy.run_module(module)


def get_module(module=None, extra_sys_paths=()):
    gbl = {}
    if module:
        path = sys.path.copy() if extra_sys_paths else sys.path
        try:
            for d in extra_sys_paths[::-1]:
                sys.path.insert(0, osp.abspath(d))
            cpath = tuple(sys.path)
            for v in ([module] if isinstance(module, str) else module):
                gbl.update(_get_module(v, cpath))
        finally:
            sys.path = path
    return gbl


class Application(BaseApplication):
    def __init__(self, app, workers=None, timeout=0, threads=10,
                 accesslog='-', **options):
        self.options = {
            'threads': threads,
            'timeout': timeout,
            'workers': workers or (multiprocessing.cpu_count() * 2) + 1,
            'accesslog': accesslog,
            **options
        }
        self.application = app
        super().__init__()

    def load_config(self):
        invalid = {key for key in self.options if key not in self.cfg.settings}
        if invalid:
            raise ValueError(f'Invalid gunicorn options `{", ".join(invalid)}`.')
        config = {
            key: value for key, value in self.options.items()
            if key in self.cfg.settings and value is not None
        }
        for key, value in config.items():
            self.cfg.set(key.lower(), value)

    def load(self):
        return self.application
