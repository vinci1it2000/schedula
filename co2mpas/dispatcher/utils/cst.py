#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides constants data node ids and values.
"""

__author__ = 'Vincenzo Arcidiacono'

from .gen import Token

__all__ = ['EMPTY', 'START', 'NONE', 'SINK']

#: It is used set and unset empty values.
#:
#: .. seealso:: :func:`~dispatcher.Dispatcher.set_default_value`
EMPTY = Token('empty')

#: Starting node that identifies initial inputs of the workflow.
#:
#: .. seealso:: :func:`~dispatcher.Dispatcher.dispatch`
START = Token('start')
START.__doc__ = 'Starting node that identifies initial inputs of the workflow.'

#: Fake value used to set a default value to call functions without arguments.
#:
#: .. seealso:: :func:`~dispatcher.Dispatcher.add_function`
NONE = Token('none')

#: Sink node of the dispatcher that collects all unused outputs.
#:
#: .. seealso:: :func:`~dispatcher.Dispatcher.add_data`,
#:    :func:`~dispatcher.Dispatcher.add_function`,
#:    :func:`~dispatcher.Dispatcher.add_dispatcher`
SINK = Token('sink')
SINK.__doc__ = 'Sink node of the dispatcher that collects all unused outputs.'

#: Ending node of SubDispatcherFunction.
#:
#: .. seealso:: :func:`~dispatcher.utils.dsp.SubDispatchFunction`
END = Token('end')