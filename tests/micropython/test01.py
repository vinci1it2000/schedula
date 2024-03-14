#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2024, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
import schedula as sh

dsp = sh.Dispatcher()


def func(a, b):
    return a + b, sh.NONE


print(dsp.add_data('a', 1, 3))
print(dsp.add_func(func, inputs=['a', 'b'], outputs=['c', 'd']))
print(list(dsp({'b': 1}).items()))
