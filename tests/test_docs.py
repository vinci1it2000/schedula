#! python
# -*- coding: UTF-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

import io
import os
import re
import sys
import subprocess
import unittest
from unittest.mock import patch

import co2mpas
from co2mpas import __main__ as cmain
from co2mpas import datasync


mydir = os.path.dirname(__file__)
proj_path = os.path.join(mydir, '..')
readme_path = os.path.join(mydir, '..', 'README.rst')


class Doctest(unittest.TestCase):

    def test_README_version_opening(self):
        ver = co2mpas.__version__
        header_len = 20
        mydir = os.path.dirname(__file__)
        with open(readme_path) as fd:
            for i, l in enumerate(fd):
                if ver in l:
                    break
                elif i >= header_len:
                    msg = "Version(%s) not found in README %s header-lines!"
                    raise AssertionError(msg % (ver, header_len))

    def test_README_version_from_cmdline(self):
        ver = co2mpas.__version__
        mydir = os.path.dirname(__file__)
        with open(readme_path) as fd:
            ftext = fd.read()
            with patch('sys.stdout', new=io.StringIO()) as stdout:
                try:
                    cmain.main('--version')
                except SystemExit as ex:
                    pass ## Cancel docopt's exit()
            ver_str = stdout.getvalue().strip()
            assert ver_str
            regex = 'co2mpas-([^ ]+)'
            m = re.match(regex, ver_str)
            self.assertIsNotNone(m, 'Version(%s) not found in: \n%s' % (
                    regex, ver_str))
            proj_ver = m.group(1)
            self.assertIn('co2mpas_version: %s' % proj_ver, ftext,
                          "Version(%s) not found in README cmd-line version-check!" %
                          ver)

    def test_README_relDate_from_cmdline(self):
        reldate = co2mpas.__updated__
        mydir = os.path.dirname(__file__)
        with open(readme_path) as fd:
            ftext = fd.read()
            with patch('sys.stdout', new=io.StringIO()) as stdout:
                try:
                    cmain.main(*'-v --version'.split())
                except SystemExit as ex:
                    pass ## Cancel docopt's exit()
            ver_str = stdout.getvalue().strip()
            assert ver_str
            regex = 'co2mpas_rel_date: (.+)'
            m = re.search(regex, ver_str)
            self.assertIsNotNone(m, 'RelDate(%s) not found in: \n%s!' % (
                    regex, ver_str))
            reldate_str = m.group(1)
            self.assertIn('co2mpas_rel_date: %s' % reldate_str, ftext,
                          "Version(%s) not found in README cmd-line version-check!" %
                          reldate)

    def test_README_contains_main_help_msg(self):
        help_msg = cmain.__doc__  # @UndefinedVariable
        mydir = os.path.dirname(__file__)
        with open(readme_path) as fd:
            ftext = fd.read()
            msg = "MAIN() help-line[%s] missing from README: \n  %s"
            for i, l in enumerate(help_msg.split('\n')):
                l = l.strip()
                if l:
                    assert l in ftext, msg % (i, l)

    def test_README_contains_datasync_help_msg(self):
        help_msg = datasync.__doc__  # @UndefinedVariable
        help_msg = re.match(r'^(.+?)-O <output>', help_msg, re.DOTALL).group(1)
        assert len(help_msg) > 200
        mydir = os.path.dirname(__file__)
        with open(readme_path) as fd:
            ftext = fd.read()
            msg = "DATASYNC() help-line[%s] missing from README: \n  %s"
            for i, l in enumerate(help_msg.split('\n')):
                l = l.strip()
                if l:
                    assert l in ftext, msg % (i, l)


    def test_README_as_PyPi_landing_page(self):
        from docutils import core as dcore

        long_desc = subprocess.check_output(
                'python setup.py --long-description'.split(),
                cwd=proj_path)
        self.assertIsNotNone(long_desc, 'Long_desc is null!')

        with patch('sys.exit'):
            dcore.publish_string(long_desc, enable_exit_status=False,
                    settings_overrides={ # see `docutils.frontend` for more.
                            'halt_level': 2 # 2=WARN, 1=INFO
                    })

