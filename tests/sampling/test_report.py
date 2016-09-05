#! python
# -*- coding: UTF-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

import logging
import types
import unittest

import ddt
from traitlets.config import get_config

from co2mpas.__main__ import init_logging
from co2mpas.sampling import baseapp, report
import os.path as osp
import pandas as pd


init_logging(True)

log = logging.getLogger(__name__)

mydir = osp.dirname(__file__)


@ddt.ddt
class TApp(unittest.TestCase):

    @ddt.data(
        report.ReportCmd.document_config_options,
        report.ReportCmd.print_alias_help,
        report.ReportCmd.print_flag_help,
        report.ReportCmd.print_options,
        report.ReportCmd.print_subcommands,
        report.ReportCmd.print_examples,
        report.ReportCmd.print_help,
    )
    def test_app(self, meth):
        c = get_config()
        c.ReportCmd.raise_config_file_errors = True
        cmd = report.ReportCmd(config=c)
        meth(cmd)


_inp_fpath = osp.join(mydir, '..', '..', 'co2mpas', 'demos', 'co2mpas_demo-0.xlsx')
_out_fpath = osp.join(mydir, 'output.xlsx')


class TReport(unittest.TestCase):

    def test_extract_input(self):
        c = get_config()
        c.ReportCmd.raise_config_file_errors = True
        cmd = report.ReportCmd(config=c)
        res = cmd.run('inp=%s' % _inp_fpath)
        self.assertIsInstance(res, types.GeneratorType)
        res = list(res)
        self.assertEqual(len(res), 1)
        for i in res:
            self.assertIsInstance(i, pd.Series)

    def test_extract_output(self):
        c = get_config()
        c.ReportCmd.raise_config_file_errors = True
        cmd = report.ReportCmd(config=c)
        res = cmd.run('out=%s' % _out_fpath)
        self.assertIsInstance(res, types.GeneratorType)
        res = list(res)
        self.assertEqual(len(res), 3)
        for i in res:
            self.assertIsInstance(i, pd.DataFrame)

    def test_extract_both(self):
        c = get_config()
        c.ReportCmd.raise_config_file_errors = True
        cmd = report.ReportCmd(config=c)
        res = cmd.run('inp=%s' % _inp_fpath, 'out=%s' % _out_fpath)
        self.assertIsInstance(res, types.GeneratorType)
        res = list(res)
        self.assertEqual(len(res), 4)
        for i in res:
            self.assertIsInstance(i, (pd.Series, pd.DataFrame))

    def test_bad_prefix(self):
        c = get_config()
        c.ReportCmd.raise_config_file_errors = True
        cmd = report.ReportCmd(config=c)
        with self.assertRaisesRegexp(baseapp.CmdException, "arg number 1 was"):
            list(cmd.run('inp%s' % _inp_fpath))
        with self.assertRaisesRegexp(baseapp.CmdException, "arg number 1 was"):
            list(cmd.run('out%s' % _out_fpath))
        with self.assertRaisesRegexp(baseapp.CmdException, "arg number 2 was"):
            list(cmd.run('inp=%s' % _inp_fpath, 'out:%s' % _out_fpath))
