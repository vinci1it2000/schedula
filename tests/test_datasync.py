#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
from co2mpas import datasync, __main__ as cmain
import logging
import os
import tempfile
import unittest

import ddt

import os.path as osp
import pandas as pd


cmain.init_logging(False)
log = logging.getLogger(__name__)

mydir = osp.dirname(__file__)

_sync_fname = 'datasync.xlsx'
_synced_fname = 'datasync.sync.xlsx'


def _read_expected(prefix_columns):
    fname = 'datasync.sync.csv'
    df = pd.read_csv(osp.join(mydir, fname))
    if prefix_columns:
        df.columns = ('x,y1,Sheet2 y1,Sheet3 y1,y2,Sheet2 y2,Sheet3 y2,y1.1,Sheet2 y1.1'.split(','))
    return df


def _read_synced(fpath, sheet):
    df = pd.read_excel(fpath, sheet)
    return df


def _check_synced(tc, fpath, sheet, prefix_columns=False):
    exp_df = _read_expected(prefix_columns)
    synced_df = _read_synced(fpath, sheet)
    tc.assertTrue(exp_df.equals(synced_df), (synced_df, exp_df))


@ddt.ddt
class DataSync(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        os.chdir(mydir)


    @ddt.data(
            (_sync_fname, "Sheet1", ["Sheet2", "Sheet3", "Sheet4"]),
            (_sync_fname, "Sheet1", None),
#             (osp.join(mydir, _sync_fname), "Sheet1", ["Sheet2", "Sheet3"]),
#             (osp.join(mydir, _sync_fname), "Sheet1", None),
            )
    def test_main_smoke_test(self, case):
        inppath, ref_sheet, sync_sheets = case
        sync_sheets = ' '.join(sync_sheets) if sync_sheets else ''
        with tempfile.TemporaryDirectory(prefix='co2mpas_%s_'%__name__) as d:
            cmd = 'datasync -v %s x y1 %s %s -O %s' % (
                    inppath, ref_sheet, sync_sheets, d)
            cmain.main(*cmd.split())
            _check_synced(self, osp.join(d, _synced_fname), 'Sheet1')


    @ddt.data(
            (_sync_fname, "Sheet1", ["Sheet2", "Sheet3", "Sheet4"]),
            (_sync_fname, "Sheet1", None),
            (_sync_fname, "Sheet1", ()),
#             (osp.join(mydir, _sync_fname), "Sheet1", ["Sheet2", "Sheet3"]),
#             (osp.join(mydir, _sync_fname), "Sheet1", None),
#             (osp.join(mydir, _sync_fname), "Sheet1", []),
            )
    def test_api_smoke_test(self, case):
        inppath, ref_sheet, sync_sheets = case
        with tempfile.TemporaryDirectory(prefix='co2mpas_%s_'%__name__) as d:
            datasync.apply_datasync(
                    ref_sheet=ref_sheet,
                    sync_sheets=sync_sheets,
                    x_label='x',
                    y_label='y1',
                    output_file=osp.join(d, _synced_fname),
                    input_file=inppath,
                    prefix_cols=False)
            _check_synced(self, osp.join(d, _synced_fname), 'Sheet1', )

    @ddt.data(
            (_sync_fname, "Sheet1", ["Sheet2", "Sheet3", "Sheet4"]),
            (_sync_fname, "Sheet1", None),
            (_sync_fname, "Sheet1", ()),
            (_sync_fname, "Sheet1", []),
            )
    def test_empty_sheet(self, case):
        inppath, ref_sheet, sync_sheets = case
        with tempfile.TemporaryDirectory(prefix='co2mpas_%s_'%__name__) as d:
            datasync.apply_datasync(
                    ref_sheet=ref_sheet,
                    sync_sheets=sync_sheets,
                    x_label='x',
                    y_label='y1',
                    output_file=osp.join(d, _synced_fname),
                    input_file=inppath,
                    prefix_cols=False)
            _check_synced(self, osp.join(d, _synced_fname), 'Sheet1')


    @ddt.data(False, True)
    def test_prefix_columns(self, prefix_columns):
        with tempfile.TemporaryDirectory(prefix='co2mpas_%s_'%__name__) as d:
            datasync.apply_datasync(
                    ref_sheet='Sheet1',
                    sync_sheets=None,
                    x_label='x',
                    y_label='y1',
                    output_file=osp.join(d, _synced_fname),
                    input_file=_sync_fname,
                    prefix_cols=prefix_columns)
            _check_synced(self, osp.join(d, _synced_fname), 'Sheet1', prefix_columns)


    @ddt.data(
            ('bad_x', 'y1'),
            ('x', 'bad_y1'),
            ('bad_x', 'bad_y'),
            )
    def test_bad_columns(self, case):
        import _tutils as tutils # XXX import chaos!
        x, y = case
        with tempfile.TemporaryDirectory(prefix='co2mpas_%s_'%__name__) as d:
            with tutils.assertRaisesRegex(self, cmain.CmdException, 'not found in rows'):
                datasync.apply_datasync(
                        ref_sheet='Sheet1',
                        sync_sheets=['Sheet2'],
                        x_label=x,
                        y_label=y,
                        output_file=osp.join(d, _synced_fname),
                        input_file=_sync_fname,
                        prefix_cols=False)
