# coding=utf-8
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2024, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides functions to dump and load secrets from flask session when dealing
with JSON.
"""

import json
import hashlib


def dumps_secret(o):
    dhash = hashlib.sha256()
    dhash.update(json.dumps(o, sort_keys=True).encode())
    key = dhash.hexdigest()
    from flask import session
    if not '$secrets' in session:
        session['$secrets'] = {}
    if key not in session['$secrets']:
        session['$secrets'] = {**session['$secrets'], key: o}
    return key


def loads_secret(key):
    from flask import session
    return session['$secrets'][key]


def secrets(obj, dumps=True):
    if isinstance(obj, list):
        return [secrets(v, dumps) for v in obj]
    elif isinstance(obj, dict):
        res = {
            k: secrets(v, dumps)
            for k, v in obj.items() if '$secret' != k
        }
        if '$secret' in obj:
            if dumps:
                res['$secret'] = dumps_secret(obj['$secret'])
            else:
                obj = loads_secret(obj['$secret'])
                if res:
                    res.update(obj)
                else:
                    res = obj
        return res
    return obj


def dumps(obj, **kwargs):
    return json.dumps(secrets(obj), **kwargs)


def loads(s, **kwargs):
    return secrets(json.loads(s, **kwargs), dumps=False)
