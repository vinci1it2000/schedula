"""
Run TC with env-var CO2MPAS_DATA_FOLDER pointing your `co2pas-data.git` project.
"""
#
# from co2mpas.__main__ import init_logging
# import tempfile
# import unittest
# import logging
#
# import functools as ft
#
# from tests import _tutils as tutils
#
#
# DATA_VERSION = '1'
# DATA_SUBFOLDER = 'thermal'
#
# init_logging(level=logging.WARNING)
# #logging.getLogger('pandalone.xleash').setLevel(logging.INFO)
#
# class TThermal(unittest.TestCase):
#
#
#     @classmethod
#     def setUpClass(cls):
#         ver_validator = ft.partial(tutils.default_ver_validator, DATA_VERSION)
#
#         cls.tc_module_folder = tutils.get_tc_data_fpath(
#                 ver_validator, subfolder=DATA_SUBFOLDER)
#
#     def test_smoke(self):
#         tmpdir = tempfile.gettempdir()
#         print(self.tc_module_folder)
#
#         ## proc-files
