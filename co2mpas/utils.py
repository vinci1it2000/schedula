#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides utils for the CO2MPAS.
"""

import yaml
from networkx.utils import open_file


class Constants(dict):
    def __init__(self, *args, **kwargs):
        super(Constants, self).__init__(*args, **kwargs)
        self.__dict__ = self

    @open_file(1, mode='rb')
    def load(self, file, **kw):
        self.update(yaml.load(file, **kw))
        return self

    @open_file(1, mode='w')
    def dump(self, file, default_flow_style=False, **kw):
        yaml.dump(dict(self), file, default_flow_style=default_flow_style, **kw)


def stack_nested_keys(nested_dict, key=(), depth=-1):
    """
    Stacks the keys of nested-dictionaries into tuples and yields a list of k-v pairs.

    :param nested_dict:
        Nested dictionary.
    :type nested_dict: dict

    :param key:
        Initial keys.
    :type key: tuple, optional

    :param depth:
        Maximum keys depth.
    :type depth: int, optional

    :return:
        List of k-v pairs.
    :rtype: generator
    """

    if depth != 0 and hasattr(nested_dict, 'items'):
        for k, v in nested_dict.items():
            yield from stack_nested_keys(v, key=key + (k,), depth=depth - 1)
    else:
        yield key, nested_dict


def get_nested_dicts(nested_dict, *keys, default=None):
    """
    Get/Initialize the value of nested-dictionaries.

    :param nested_dict:
        Nested dictionary.
    :type nested_dict: dict

    :param keys:
        Nested keys.
    :type keys: tuple

    :param default:
        Function used to initialize a new value.
    :type default: function, optional

    :return:
        Value of nested-dictionary.
    :rtype: generator
    """

    if keys:
        default = default or dict
        d = default() if len(keys) == 1 else {}
        nd = nested_dict[keys[0]] = nested_dict.get(keys[0], d)
        return get_nested_dicts(nd, *keys[1:], default=default)
    return nested_dict


def combine_nested_dicts(*nested_dicts, depth=-1):
    """
    Merge nested-dictionaries.

    :param nested_dicts:
        Nested dictionaries.
    :type nested_dicts: tuple[dict]

    :param depth:
        Maximum keys depth.
    :type depth: int, optional

    :return:
        Combined nested-dictionary.
    :rtype: dict
    """

    result = {}
    for nested_dict in nested_dicts:
        for k, v in stack_nested_keys(nested_dict, depth=depth):
            get_nested_dicts(result, *k[:-1])[k[-1]] = v

    return result
