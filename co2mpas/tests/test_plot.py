#! python
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2016 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

import logging
import unittest

import ddt

from co2mpas import plot as co2plot
from co2mpas.__main__ import init_logging


init_logging(level=logging.DEBUG)


@ddt.ddt
class TPlot(unittest.TestCase):

    @ddt.data(*co2plot.get_model_paths())
    def test_plot_all_models(self, model):
        dot_graphs = co2plot.plot_model_graphs(
            [model], view_in_browser=False, depth=1
        )
        self.assertGreaterEqual(len(dot_graphs), 1, model)
