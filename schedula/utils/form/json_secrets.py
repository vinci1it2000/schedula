# coding=utf-8
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2025, Vincenzo Arcidiacono;
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


def resolve_refs(schema, base=None):
    """
    Recursively resolve all $ref references in a JSON schema-like dictionary.
    """
    if isinstance(schema, dict):
        # If this is a $ref, resolve it
        if "$ref" in schema:
            ref_path = schema["$ref"]
            resolved_value = base
            for part in ref_path.lstrip('#/').split('/'):
                resolved_value = resolved_value[part]
            # Return the fully resolved value
            return resolve_refs(resolved_value, base)
        # Otherwise, process all dictionary values
        return {k: resolve_refs(v, base) for k, v in schema.items()}
    elif isinstance(schema, list):
        # Process all items in a list
        return [resolve_refs(item, base) for item in schema]
    else:
        # If it’s a plain value, return as is
        return schema


def secrets(obj, dumps=True, base=None):
    if base is None:
        base = obj
    if isinstance(obj, list):
        return [secrets(v, dumps, base) for v in obj]
    elif isinstance(obj, dict):
        res = {
            k: secrets(v, dumps, base)
            for k, v in obj.items() if '$secret' != k
        }
        if '$secret' in obj:
            if dumps:
                res['$secret'] = dumps_secret(resolve_refs(
                    obj['$secret'], base
                ))
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
