#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014-2016 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides a function to build a dispatcher from an excel file.

Sub-Modules:

.. currentmodule:: schedula.utils.exl

.. autosummary::
    :nosignatures:
    :toctree: exl/

    core
"""
__all__ = ['extract_dsp_from_excel']


def extract_dsp_from_excel(filename, workbook=None, sheets=None):
    from pycel.excelwrapper import ExcelOpxWrapper
    from pycel.excelcompiler import ExcelCompiler
    import openpyxl
    import functools
    from . import core

    exl = ExcelOpxWrapper(filename)
    exl.workbookDO = exl.workbook = workbook or openpyxl.load_workbook(filename)

    seeds = dict(core.get_seeds(exl, sheets))
    graph = ExcelCompiler(filename, excel=exl).gen_graph(seed=list(seeds)).G

    from ... import Dispatcher
    node, d = graph.node, Dispatcher()
    for n in graph.node:
        node_id = n.address()
        if isinstance(n, core.Cell) and not n.formula:
            d.add_data(data_id=node_id, default_value=n.value)
        else:
            inputs = sorted(v.address() for v in graph.pred[n])
            if isinstance(n, core.CellRange):
                fun_id, function = 'get_range(%s)' % node_id, core.get_range
            else:
                fun_id, function = n.formula, core.evaluate_cell
                inputs += sorted(core.get_named_range(fun_id))

            d.add_function(
                function_id=fun_id, inputs=inputs or None, outputs=[node_id],
                function=functools.partial(function, n, inputs)
            )

    return d, seeds, exl
