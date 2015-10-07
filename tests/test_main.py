#! python
# -*- coding: UTF-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

import os
import unittest
import tempfile

from co2mpas import __main__ as compas_main
import glob


mydir = os.path.dirname(__file__)
readme_path = os.path.join(mydir, '..', 'README.rst')


class Main(unittest.TestCase):

    def test_Gen_template(self):
        gen_files = ['t1', 'tt2.xlsx']
        exp_files = ['t1.xlsx', 'tt2.xlsx']
        with tempfile.TemporaryDirectory() as d:
            gen_files = [os.path.join(d, f) for f in gen_files]
            cmd = "template %s" % ' '.join(gen_files)
            compas_main._main(*cmd.split())
            files = os.listdir(path=d)
            self.assertSetEqual(set(files), set(exp_files))

    def test_Gen_ipynbs(self):
        exp_path = (mydir, '..', 'co2mpas', 'ipynbs', '*.ipynb')
        exp_files = [os.path.basename(f)
                     for f in glob.glob(os.path.join(*exp_path))]

        with tempfile.TemporaryDirectory() as d:
            cmd = "ipynb %s" % d
            compas_main._main(*cmd.split())
            files = os.listdir(path=d)
            self.assertSetEqual(set(files), set(exp_files))

    def test_Gen_demo_inputs(self):
        exp_path = (mydir, '..', 'co2mpas', 'demos', '*.xlsx')
        exp_files = [os.path.basename(f)
                     for f in glob.glob(os.path.join(*exp_path))]

        with tempfile.TemporaryDirectory() as d:
            cmd = "demo %s" % d
            compas_main._main(*cmd.split())
            files = os.listdir(path=d)
            self.assertSetEqual(set(files), set(exp_files))

    def test_run_empty(self):
        with tempfile.TemporaryDirectory() as inp, \
                tempfile.TemporaryDirectory() as out:
            cmd = "template %s/tt" % inp
            compas_main._main(*cmd.split())
            cmd = "-I %s -O %s" % (inp, out)
            compas_main._main(*cmd.split())

    #@unittest.skip('Takes too long.')
    def test_run_demos(self):
        with tempfile.TemporaryDirectory() as inp, \
                tempfile.TemporaryDirectory() as out:
            cmd = "demo %s" % inp
            compas_main._main(*cmd.split())
            cmd = "-I %s -O %s" % (inp, out)
            compas_main._main(*cmd.split())
