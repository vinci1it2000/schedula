#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

""" Defines the dispatcher exception. """
## TODO: Move it to parent package.

__author__ = 'Vincenzo Arcidiacono'

__all__ = ['DispatcherError']


class DispatcherError(ValueError):
    def __init__(self, sol, *args, **kwargs):
        super(DispatcherError, self).__init__(*args, **kwargs)
        self.sol = sol
        self.plot = self.sol.plot


class DispatcherAbort(ValueError):
    def __init__(self, sol, *args, **kwargs):
        super(DispatcherAbort, self).__init__(*args, **kwargs)
        self.sol = sol
        self.plot = self.sol.plot
