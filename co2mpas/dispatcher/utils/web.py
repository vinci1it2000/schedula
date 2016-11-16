# coding=utf-8
# -*- coding: UTF-8 -*-
#
# Copyright 2014-2016 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides functions to build a flask app from a dispatcher.
"""

__author__ = 'Vincenzo Arcidiacono'

from .gen import caller_name
from .alg import parent_func
from .dsp import SubDispatch
from functools import partial
import logging
log = logging.getLogger(__name__)

__all__ = ['create_flask_app', 'add_dsp_url_rules']


def create_flask_app(dsp, import_name=None, **options):
    """
    Creates a Flask app from a dispatcher.

    :param dsp:
        A dispatcher that identifies the model adopted.
    :type dsp: co2mpas.dispatcher.Dispatcher

    :param import_name:
        The name of the application package.
    :type import_name: str, optional

    :param options:
        Flask options.
    :type options: dict, optional

    :return:
        Flask app based on the given dispatcher.
    :rtype: flask.Flask
    """
    from flask import Flask
    if import_name is None:
        import_name = '/'.join((caller_name(), dsp.name))

    app = Flask(import_name, **options)

    add_dsp_url_rules(dsp, app, '/')

    return app


def _func_handler_maker(func):
    from flask import request, jsonify

    def func_handler():
        data = request.get_json(force=True)
        data['return'] = func(*data.get('args', ()), **data.get('kwargs', {}))
        return jsonify(data)

    return func_handler


def _add_rule(add_rule, *args, **kwargs):
    try:
        add_rule(*args, **kwargs)
    except ValueError as ex:
        log.warn(ex)


def stack_func_rules(dsp, rule='/', edit_data=False, depth=-1,
                     sub_dsp_function=False, yield_self=True):
    """
    Stacks function rules.

    :param dsp:
        A dispatcher that identifies the model adopted.
    :type dsp: co2mpas.dispatcher.Dispatcher

    :param rule:
        Parent rule.
    :type rule: str

    :param edit_data:
        Add rule to set data node?
    :type edit_data: bool

    :param depth:
        Maximum depth of nested rules.
    :type depth: int

    :param sub_dsp_function:
        Enable nested rules for sub-dispatcher nodes?
    :type sub_dsp_function: bool

    :param yield_self:
        Add `dsp.dispatch` rule?
    :type yield_self: bool
    """
    if yield_self:
        yield rule, dsp.dispatch
    rule += '%s/'

    if edit_data:
        set_value = dsp.set_default_value
        for k in dsp.data_nodes.keys():
            yield rule % k, partial(set_value, k)

    for k, v in dsp.function_nodes.items():
        if 'function' in v:
            r, f = rule % k, v['function']
            yield r, f
            if depth != 0:
                f = parent_func(f)
                if isinstance(f, SubDispatch):
                    yield from stack_func_rules(
                        f.dsp, r, edit_data, depth - 1, sub_dsp_function, 0
                    )

    if depth == 0 or sub_dsp_function:
        return

    for k, v in dsp.sub_dsp_nodes.items():
        yield from stack_func_rules(
            v['function'], rule % k, edit_data, depth - 1, sub_dsp_function, 0
        )


def add_dsp_url_rules(dsp, app, rule, edit_data=False, methods=('POST',),
                      func_handler_maker=_func_handler_maker, **options):
    """
    Add url-rules derived from the given dispatcher to a given Flask app.

    :param dsp:
        A dispatcher that identifies the model adopted.
    :type dsp: co2mpas.dispatcher.Dispatcher

    :param app:
        Flask app where to add url-rules derived from the given dispatcher.
    :type app: flask.Flask

    :param rule:
        Base URL rule.
    :type rule: str

    :param edit_data:
        Allow to set data node values with a request.
    :type edit_data: bool, optional

    :param methods:
        A list of methods this rule should be limited to (GET, POST etc.).
    :type methods: tuple[str], optional

    :param func_handler_maker:
        A function that return a function call handler.
    :type func_handler_maker: function, optional

    :param options:
        Options to be forwarded to the underlying Rule object.
    :type options: dict, optional
    """

    options['methods'] = methods
    add_rule = partial(_add_rule, app.add_url_rule)
    for r, func in stack_func_rules(dsp, rule, edit_data):
        add_rule(r, r, func_handler_maker(func), **options)
