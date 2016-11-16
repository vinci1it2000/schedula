# coding=utf-8
# -*- coding: UTF-8 -*-
#
# Copyright 2014-2016 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides functions to build a celery app from a dispatcher.
"""
from .web import stack_func_rules
from functools import partial
from .alg import parent_func


def create_celery_app(dsp, rule='/', edit_data=False, depth=-1,
                      sub_dsp_function=False, **options):
    """
    Creates a Celery app from a dispatcher.

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

    :param options:
        Celery options.
    :type options: dict, optional

    :return:
        Flask app based on the given dispatcher.
    :rtype: flask.Flask
    """

    from celery import Celery
    app = Celery(**options)

    for r, v in stack_func_rules(dsp, rule, edit_data, depth, sub_dsp_function):
        if isinstance(v, partial):
            f = parent_func(v)
            for k in ('__name__', '__module__'):
                if not hasattr(v, k):
                    setattr(v, k, getattr(f, k))
                
        app.task(v, name=r, _force_evaluate=True)

    return app
