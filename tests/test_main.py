#! python
# -*- coding: UTF-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

import glob
import io
import logging
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

import ddt

from co2mpas import __main__ as cmain
from co2mpas import __version__ as proj_ver
from co2mpas.__main__ import init_logging
import co2mpas.plot as co2plot


mydir = os.path.dirname(__file__)
readme_path = os.path.join(mydir, '..', 'README.rst')

init_logging(level=logging.DEBUG)
#logging.getLogger('pandalone.xleash').setLevel(logging.INFO)


class Main(unittest.TestCase):

    def test_Version(self):
        cmd = "-v --version"
        stdout = io.StringIO()
        with patch('sys.stdout', stdout):
            cmain._main(*cmd.split())
        s = stdout.getvalue()
        self.assertIn(proj_ver, s),
        self.assertIn(sys.prefix, s),
        self.assertIn(sys.version, s),

        cmd = "--version"
        stdout = io.StringIO()
        with patch('sys.stdout', stdout):
            cmain._main(*cmd.split())
        s = stdout.getvalue()
        self.assertIn(proj_ver, s),
        self.assertNotIn(sys.prefix, s),
        self.assertNotIn(sys.version, s),

    def test_Gen_template(self):
        gen_files = ['t1', 'tt2.xlsx']
        exp_files = ['t1.xlsx', 'tt2.xlsx']
        with tempfile.TemporaryDirectory() as d:
            gen_files = [os.path.join(d, f) for f in gen_files]
            cmd = "template %s" % ' '.join(gen_files)
            cmain._main(*cmd.split())
            files = os.listdir(path=d)
            self.assertSetEqual(set(files), set(exp_files))

    def test_Gen_ipynbs(self):
        exp_path = (mydir, '..', 'co2mpas', 'ipynbs', '*.ipynb')
        exp_files = [os.path.basename(f)
                     for f in glob.glob(os.path.join(*exp_path))]

        with tempfile.TemporaryDirectory() as d:
            cmd = "ipynb %s" % d
            cmain._main(*cmd.split())
            files = os.listdir(path=d)
            self.assertSetEqual(set(files), set(exp_files))

    def test_Gen_demo_inputs(self):
        exp_path = (mydir, '..', 'co2mpas', 'demos', '*.xlsx')
        exp_files = [os.path.basename(f)
                     for f in glob.glob(os.path.join(*exp_path))]

        with tempfile.TemporaryDirectory() as d:
            cmd = "demo %s" % d
            cmain._main(*cmd.split())
            files = os.listdir(path=d)
            self.assertSetEqual(set(files), set(exp_files))

    def test_run_empty(self):
        with tempfile.TemporaryDirectory() as inp, \
                tempfile.TemporaryDirectory() as out:
            cmd = "template %s/tt" % inp
            cmain._main(*cmd.split())
            cmd = "batch %s -O %s" % (inp, out)
            cmain._main(*cmd.split())

    #@unittest.skip('Takes too long.')  # DO NOT COMIT AS SKIPPED!!
    def test_run_demos(self):
        with tempfile.TemporaryDirectory() as inp, \
                tempfile.TemporaryDirectory() as out:
            cmd = "demo %s" % inp
            cmain._main(*cmd.split())
            cmd = "batch -v -D flag.engineering_mode=2 -O %s %s" % (out, inp)
            cmain._main(*cmd.split())


@ddt.ddt
class Modelgraph(unittest.TestCase):
    def setUp(self):
        self.plot_func = co2plot.plot_model_graphs
        self.odl_dfl = self.plot_func.__defaults__
        dfl = list(self.odl_dfl)
        dfl[1] = False
        self.plot_func.__defaults__ = tuple(dfl)
        self.model = co2plot.get_model_paths()[1]
    def tearDown(self):
        self.plot_func = co2plot.plot_model_graphs
        self.plot_func.__defaults__ = self.odl_dfl

    @ddt.data(
        '',
        '--graph-depth -1',
        '--graph-depth 0',
        '--graph-depth 1',
    )
    def test_plot_graphs_depth(self, case):
        cmd = "modelgraph %s %s" % (case, self.model)
        cmain._main(*cmd.split())
