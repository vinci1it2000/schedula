#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides tools to find data, function, and sub-dispatcher node description.
"""

__author__ = 'Vincenzo Arcidiacono'

__all__ = ['DispatcherError']


class DispatcherError(ValueError):
    def __init__(self, dsp, *args, kw_failure_plot=None, **kwargs):
        super(DispatcherError, self).__init__(*args, **kwargs)
        self.dsp = dsp
        self.kw_failure_plot = kw_failure_plot

    def __str__(self, *args, **kwargs):
        if self.kw_failure_plot is not None:
            self.dsp.plot(**self.kw_failure_plot)
        return ValueError.__str__(self, *args, **kwargs)



