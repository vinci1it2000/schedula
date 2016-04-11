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
import io
import tempfile
import unittest

import ddt
from numpy import testing as npt

import os.path as osp
import pandas as pd


cmain.init_logging(False)
log = logging.getLogger(__name__)

mydir = osp.dirname(__file__)

_sync_fname = 'datasync.xlsx'
_synced_fname = 'datasync.sync.xlsx'


def _abspath(fname):
    return osp.join(mydir, _sync_fname)


def _file_url(fname):
    return ('file://' + _abspath(fname)).replace('\\', '/')


_synced_values = """
0,0,0,0,0,0,0,0,0\n1,1,2,1,2,4,1,2,4\n2,2,4,2,4,8,2,4,8\n3,3,6,3,6,12,3,6,12\n4,4,8,4,8,16,3.5,8,16\n5,4,10,4,10,20,4,10,20
6,4,12,4,12,24,4,12,24\n7,3,14,3,14,28,3,14,28\n8,2,16,2,16,32,2,16,32\n9,1,18,1,18,36,1,18,36\n10,0,20,0,20,40,0,20,40
11,0,22,0,22,44,0.5,22,44\n12,1,24,1,24,48,1,24,48\n13,1,26,1,26,52,1,26,52\n14,0,28,0,28,56,0,28,56\n15,1,30,1,30,60,1,30,60
16,2,32,2,32,64,2,32,64\n17,3,34,3,34,68,3,34,68\n18,2,36,2,36,72,2,36,72\n19,1,38,1,38,76,1,38,76\n20,0,40,0,40,80,0,40,80
21,0,42,0,42,84,0,42,84\n22,1,44,1,44,88,1,44,88\n23,2,46,2,46,92,2,46,92\n24,3,48,3,48,96,3,48,96\n25,4,50,4,50,100,4,50,100
26,3,52,3,52,104,3,52,104\n27,2,54,2,54,108,2,54,108\n28,1,56,1,56,112,1,56,112\n29,0,58,0,58,116,0,58,116"""
def _read_expected(prefix_columns):
    txtio = io.StringIO(_synced_values)
    df = pd.read_csv(txtio, header=None)
    if prefix_columns:
        df.columns = ('x,y1,y2,Sheet2 y1,Sheet2 y2,Sheet2 y3,Sheet3 y1,Sheet3 y2,Sheet3 OtherY'.split(','))
    else:
        df.columns = ('x,y1,y2,Sheet2 y1,Sheet2 y2,y3,Sheet3 y1,Sheet3 y2,OtherY'.split(','))
    return df


def _read_synced(fpath, sheet):
    df = pd.read_excel(fpath, sheet)
    return df


def _check_synced(tc, fpath, sheet, prefix_columns=False):
    exp_df = _read_expected(prefix_columns)
    synced_df = _read_synced(fpath, sheet)
    npt.assert_array_equal(exp_df, synced_df, 'VALUES mismatch!')
    npt.assert_array_equal(exp_df.columns, synced_df.columns, 'COLUMNS mismatch!')
    npt.assert_array_equal(exp_df.index, synced_df.index, 'INDEX mismatch!')


_def_file = 'DEFILE'
_def_ref = 'A1(RD):._:RD'

@ddt.ddt
class DataSync(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        os.chdir(mydir)


    @ddt.data(
            (_sync_fname, "Sheet1", ["Sheet2", "Sheet3", "Sheet4"]),
            (_sync_fname, "Sheet1", None),
            (_abspath(_sync_fname), "Sheet1", ["Sheet2", "Sheet3"]),
            (_abspath(_sync_fname), "Sheet1", None),
            (_file_url(_sync_fname), "Sheet1", None),  ## FAILS due to clone-excel!
            )
    def test_main_smoke_test(self, case):
        inppath, ref_sheet, sync_sheets = case
        sync_sheets = ' '.join(sync_sheets) if sync_sheets else ''
        with tempfile.TemporaryDirectory(prefix='co2mpas_%s_'%__name__) as d:
            cmd = '-v -O %s %s x y1 %s %s' % (
                    d, inppath, ref_sheet, sync_sheets)
            datasync.main(*cmd.split())
            _check_synced(self, osp.join(d, _synced_fname), 'Sheet1')


    @ddt.data(
            (_sync_fname, "Sheet1", ["Sheet2", "Sheet3", "Sheet4"]),
            (_sync_fname, "Sheet1", None),
            (_sync_fname, "Sheet1", ()),
            (_abspath(_sync_fname), "Sheet1", ["Sheet2", "Sheet3"]),
            (_abspath(_sync_fname), "Sheet1", None),
            (_abspath(_sync_fname), "Sheet1", []),
            (_file_url(_sync_fname), "Sheet1", None), ## FAILS due to clone-excel!
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
        from . import _tutils as tutils # XXX import chaos if outside!
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

    @ddt.data(
            ('sheet',       (_def_file, 'sheet', '%s#sheet!%s'%(_def_file, _def_ref))),
            ('#sheet!:',    (_def_file, 'sheet', '%s#sheet!:'%_def_file)),
            ('file#sheet!:',    (_def_file, 'sheet', '%s#sheet!:'%_def_file)),
            #('file#sheet!:', ('file', 'sheet', ':')),
            )
    def test_parse_sheet_names(self, case):
        xlurl, (file, sheet, xlref) = case
        m = datasync._parse_sheet_names(xlurl, _def_file)
        self.assertEqual(m['sheet_name'], xlurl, (m, case))
        self.assertEqual(m['xlref'], xlref, (m, case))

