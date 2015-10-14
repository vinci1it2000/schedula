#! python
# -*- coding: UTF-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

import unittest
from co2mpas.functions import plot as co2plot
from co2mpas.__main__ import _init_logging

_init_logging(True)


class TPlot(unittest.TestCase):

    def test_plot_all_models(self):
        models = co2plot.get_models_path()
        for model in models:
            dot_graphs = co2plot.plot_model_graphs([model],
                                                   view_in_browser=False,
                                                   depth=1)
            self.assertGreaterEqual(len(dot_graphs), 1)
