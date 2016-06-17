# coding=utf-8
# -*- coding: UTF-8 -*-
#
# Copyright 2014 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides functions to build a flask app from a dispatcher.
"""

__author__ = 'Vincenzo Arcidiacono'

from co2mpas.dispatcher.utils.gen import caller_name
from functools import partial

__all__ = ['create_app', 'add_dsp_url_rules']


def create_app(dsp, import_name=None, **options):
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
    rules, add_rule, set_value = [rule], app.add_url_rule, dsp.set_default_value
    add_rule(rule, rule, func_handler_maker(dsp.dispatch), **options)
    rule += '%s/'

    if edit_data:
        for k in dsp.data_nodes.keys():
            r = rule % k
            add_rule(r, r, func_handler_maker(partial(set_value, k)), **options)

    for k, v in dsp.function_nodes.items():
        if 'function' in v:
            r = rule % k
            add_rule(r, r, func_handler_maker(v['function']), **options)

    for k, v in dsp.sub_dsp_nodes.items():
        if 'function' in v:
            add_dsp_url_rules(v['function'], app, rule % k, **options)
