#! python
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2016 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

import logging
import re
import tempfile
import types
import unittest

import ddt
from traitlets.config import get_config

from co2mpas.__main__ import init_logging
from co2mpas.sampling import CmdException, report, project
from tests.sampling import _inp_fpath, _out_fpath
import os.path as osp
import pandas as pd


init_logging(level=logging.DEBUG)

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


class TReportArgs(unittest.TestCase):

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
        self.assertIsInstance(res[0], pd.Series)
        for i in res[1:]:
            self.assertIsInstance(i, pd.DataFrame)

    def test_bad_prefix(self):
        c = get_config()
        c.ReportCmd.raise_config_file_errors = True
        cmd = report.ReportCmd(config=c)

        arg = 'BAD_ARG'
        with self.assertRaisesRegexp(CmdException, re.escape("arg[1]: %s" % arg)):
            list(cmd.run(arg))

        arg = 'inp:BAD_ARG'
        with self.assertRaisesRegexp(CmdException, re.escape("arg[1]: %s" % arg)):
            list(cmd.run(arg))

        arg1 = 'inp:FOO'
        arg2 = 'out.BAR'
        with self.assertRaises(CmdException) as cm:
            list(cmd.run('inp=A', arg1, 'out=B', arg2))
        #print(cm.exception)
        self.assertIn("arg[2]: %s" % arg1, str(cm.exception))
        self.assertIn("arg[4]: %s" % arg2, str(cm.exception))


class TReportProject(unittest.TestCase):
    def test_fails_with_args(self):
        c = get_config()
        c.ReportCmd.raise_config_file_errors = True
        c.ReportCmd.project = True
        with self.assertRaisesRegex(CmdException, "--project' takes no arguments, received"):
            list(report.ReportCmd(config=c).run('EXTRA_ARG'))

    def test_fails_when_no_project(self):
        c = get_config()
        c.ReportCmd.raise_config_file_errors = True
        c.ReportCmd.project = True
        with tempfile.TemporaryDirectory() as td:
            c.ProjectsDB.repo_path = td
            cmd = report.ReportCmd(config=c)
            with self.assertRaisesRegex(CmdException, r"No current-project exists yet!"):
                list(cmd.run())

    def test_fails_when_empty(self):
        c = get_config()
        c.ReportCmd.raise_config_file_errors = True
        c.ReportCmd.project = True
        with tempfile.TemporaryDirectory() as td:
            c.ProjectsDB.repo_path = td
            project.ProjectCmd.AddCmd(config=c).run('proj1')
            cmd = report.ReportCmd(config=c)
            with self.assertRaisesRegex(CmdException, r"Current project 'proj1' contains no input/output files!"):
                list(cmd.run())

    def test_input_output(self):
        c = get_config()
        c.ReportCmd.raise_config_file_errors = True
        c.ReportCmd.project = True
        with tempfile.TemporaryDirectory() as td:
            c.ProjectsDB.repo_path = td
            project.ProjectCmd.AddCmd(config=c).run('proj1')

            project.ProjectCmd.AddReportCmd(config=c).run('inp=%s' % _inp_fpath)
            cmd = report.ReportCmd(config=c)
            res = cmd.run()
            self.assertIsInstance(res, types.GeneratorType)
            res = list(res)
            self.assertEqual(len(res), 1)
            for i in res:
                self.assertIsInstance(i, pd.Series)

            project.ProjectCmd.AddReportCmd(config=c).run('out=%s' % _out_fpath)
            cmd = report.ReportCmd(config=c)
            res = cmd.run()
            self.assertIsInstance(res, types.GeneratorType)
            res = list(res)
            self.assertEqual(len(res), 4)
            self.assertIsInstance(res[0], pd.Series)
            for i in res[1:]:
                self.assertIsInstance(i, pd.DataFrame)

    def test_output_input(self):
        c = get_config()
        c.ReportCmd.raise_config_file_errors = True
        c.ReportCmd.project = True
        with tempfile.TemporaryDirectory() as td:
            c.ProjectsDB.repo_path = td
            project.ProjectCmd.AddCmd(config=c).run('proj1')

            project.ProjectCmd.AddReportCmd(config=c).run('out=%s' % _out_fpath)
            cmd = report.ReportCmd(config=c)
            res = cmd.run()
            self.assertIsInstance(res, types.GeneratorType)
            res = list(res)
            self.assertEqual(len(res), 3)
            for i in res:
                self.assertIsInstance(i, pd.DataFrame)

            project.ProjectCmd.AddReportCmd(config=c).run('inp=%s' % _inp_fpath)
            cmd = report.ReportCmd(config=c)
            res = cmd.run()
            self.assertIsInstance(res, types.GeneratorType)
            res = list(res)
            self.assertEqual(len(res), 4)
            self.assertIsInstance(res[0], pd.Series)
            for i in res[1:]:
                self.assertIsInstance(i, pd.DataFrame)

    def test_both(self):
        c = get_config()
        c.ReportCmd.raise_config_file_errors = True
        c.ReportCmd.project = True
        with tempfile.TemporaryDirectory() as td:
            c.ProjectsDB.repo_path = td
            project.ProjectCmd.AddCmd(config=c).run('proj1')

            cmd = project.ProjectCmd.AddReportCmd(config=c)
            cmd.run('out=%s' % _out_fpath, 'inp=%s' % _inp_fpath)
            cmd = report.ReportCmd(config=c)
            res = cmd.run()
            self.assertIsInstance(res, types.GeneratorType)
            res = list(res)
            self.assertEqual(len(res), 4)
            self.assertIsInstance(res[0], pd.Series)
            for i in res[1:]:
                self.assertIsInstance(i, pd.DataFrame)

