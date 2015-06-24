#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides constants data node ids and values.


.. data:: EMPTY
   :annotation: = Empty value.

   It is used set and unset empty values.

.. seealso:: :func:`~dispatcher.Dispatcher.set_default_value`

.. data:: START
   :annotation: = Starting node for the workflow.

   Starting node that identifies initial inputs of the workflow.

.. seealso:: :func:`~dispatcher.Dispatcher.dispatch`

.. data:: NONE
   :annotation: = None value.

   Fake value used to set a default value to call functions without arguments.

.. seealso:: :func:`~dispatcher.Dispatcher.add_function`

.. data:: SINK
   :annotation: = Sink node of the dispatcher.

   Sink node of the dispatcher that collects all unused outputs.

.. seealso:: :func:`~dispatcher.Dispatcher.add_data`,
   :func:`~dispatcher.Dispatcher.add_function`
"""

__author__ = 'Vincenzo Arcidiacono'

from compas.utils.gen import Token

__all__ = ['EMPTY', 'START', 'NONE', 'SINK']


EMPTY = Token('empty')


START = Token('start')


NONE = Token('none')


SINK = Token('sink')