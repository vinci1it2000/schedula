"""
Run TC with env-var CO2MPAS_DATA_FOLDER pointing your `co2pas-data.git` project.
"""

from co2mpas.__main__ import init_logging
import json
from .. import _tutils as tutils
import os
import sys
import pathlib
import tempfile
import unittest



init_logging(False)
#logging.getLogger('pandalone.xleash').setLevel(logging.INFO)

DATA_VERSION = 1
class TThermal(unittest.TestCase):


    def setUp(self):
        try:
            tc_data_folder = os.environ.get('CO2MPAS_DATA_FOLDER')
        except KeyError:
            raise Exception("Set your env-var `CO2MPAS_DATA_FOLDER`!")
        if not tc_data_folder:
            raise AssertionError("Empty env-var `CO2MPAS_DATA_FOLDER`!")

        self.CO2MPAS_DATA_FOLDER = pathlib.Path(tc_data_folder)
        tutils.check_tc_data_version(self.CO2MPAS_DATA_FOLDER, DATA_VERSION)

    def test_smoke(self):
        tmpdir = tempfile.gettempdir()
        tc_module_folder = self.CO2MPAS_DATA_FOLDER.joinpath('thermal')

        ## proc-files
