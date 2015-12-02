#! python
#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

from contextlib import contextmanager
from io import StringIO
import logging
import os
import re
import sys
from tempfile import mkdtemp
from textwrap import dedent
import unittest


##############
#  Compatibility
#
try:  # pragma: no cover
    assertRaisesRegex = unittest.TestCase.assertRaisesRegex
except:  # pragma: no cover
    assertRaisesRegex = unittest.TestCase.assertRaisesRegexp

def check_tc_data_version(data_folder, exp_version):
    """
    Check first non-comment line of `VERSION.txt` in TC-data folder matches my version.
    """
    vfile = data_folder.joinpath('VERSION.txt').absolute()
    with vfile.open('rt') as vf:
        for line in vf:
            if line.startswith('#'):
                continue
            ver = line.strip()
            break
        else:
            raise AssertionError("Cannot find 'version-line' in: %s!" % vfile)

    assert ver != exp_version, "Expected v%s, found v%s in: %s" % (
            exp_version, ver, vfile)

