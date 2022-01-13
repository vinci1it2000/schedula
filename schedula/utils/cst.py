#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2022, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides constants data node ids and values.
"""

from .gen import Token

__author__ = 'Vincenzo Arcidiacono <vinci1it2000@gmail.com>'

#: It is used set and unset empty values.
#:
#: .. seealso:: :func:`~schedula.dispatcher.Dispatcher.set_default_value`
EMPTY = Token('empty')

#: Starting node that identifies initial inputs of the workflow.
#:
#: .. seealso:: :func:`~schedula.dispatcher.Dispatcher.dispatch`
START = Token('start')
START.__doc__ = 'Starting node that identifies initial inputs of the workflow.'

#: Fake value used to set a default value to call functions without arguments.
#:
#: .. seealso:: :func:`~schedula.dispatcher.Dispatcher.add_function`
NONE = Token('none')

#: Sink node of the dispatcher that collects all unused outputs.
#:
#: .. seealso:: :func:`~schedula.dispatcher.Dispatcher.add_data`,
#:    :func:`~schedula.dispatcher.Dispatcher.add_func`,
#:    :func:`~schedula.dispatcher.Dispatcher.add_function`,
#:    :func:`~schedula.dispatcher.Dispatcher.add_dispatcher`
SINK = Token('sink')
SINK.__doc__ = 'Sink node of the dispatcher that collects all unused outputs.'

#: Ending node of SubDispatcherFunction.
#:
#: .. seealso:: :class:`~schedula.utils.dsp.SubDispatchFunction`
END = Token('end')

#: Self node of the dispatcher, it is a node that contains the dispatcher.
SELF = Token('self')

#: Plot node, it is a node that plot the dispatcher solution.
#: .. note:: you can pass the `kwargs` of :class:`~schedula.utils.drw._DspPlot`
#: .. seealso:: :func:`~schedula.dispatcher.Dispatcher.add_data`,
#: :func:`~schedula.dispatcher.Dispatcher.add_func`,
#: :func:`~schedula.dispatcher.Dispatcher.add_function`,
#: :func:`~schedula.dispatcher.Dispatcher.add_dispatcher`
PLOT = Token('plot')
