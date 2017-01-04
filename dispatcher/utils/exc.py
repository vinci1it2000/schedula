#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014-2016 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

""" Defines the dispatcher exception. """

__author__ = 'Vincenzo Arcidiacono'


class DispatcherError(ValueError):
    def __init__(self, sol, *args, **kwargs):
        super(DispatcherError, self).__init__(*args, **kwargs)
        self.update(sol)

    def update(self, sol):
        self.sol = sol
        self.plot = self.sol.plot

class DispatcherAbort(DispatcherError):
    pass
