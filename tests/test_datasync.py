from co2mpas import datasync
from co2mpas.__main__ import main, init_logging
import logging
import tempfile
import unittest
from pandalone import xleash
import pandas as pd
from numpy import testing as npt

import os.path as osp
import ddt


init_logging(False)
log = logging.getLogger(__name__)

mydir = osp.dirname(__file__)

_sync_fname = 'datasync.xlsx'
_synced_fname = 'datasync.sync.xlsx'

def _read_expected():
    df = pd.read_csv(osp.join(mydir, 'datasync.sync.csv'))
    return df


def _read_synced(fpath, sheet):
    df = pd.read_excel(fpath, sheet)
    return df


def _check_synced(fpath, sheet):
    exp_df = _read_expected()
    synced_df = _read_synced(fpath, sheet)
    npt.assert_array_equal(exp_df, synced_df)

@ddt.ddt
class DataSync(unittest.TestCase):


    @ddt.data(
            (_sync_fname, "Sheet1", ["Sheet2"]),
            (_sync_fname, "Sheet1", None),
            (osp.join(mydir, _sync_fname), "Sheet1", ["Sheet2"]),
            (osp.join(mydir, _sync_fname), "Sheet1", None),
            )
    def test_main_smoke_test(self, case):
        inppath, ref_sheet, sync_sheets = case
        sync_sheets = ' '.join(sync_sheets) if sync_sheets else ''
        with tempfile.TemporaryDirectory(prefix='co2mpas_%s_'%__name__) as d:
            cmd = 'datasync -v %s x y1 %s %s -O %s' % (
                    inppath, ref_sheet, sync_sheets, d)
            main(*cmd.split())
            _check_synced(osp.join(d, _synced_fname), 'Sheet1')


    @ddt.data(
            (_sync_fname, "Sheet1", ["Sheet2"]),
            (_sync_fname, "Sheet1", None),
            (_sync_fname, "Sheet1", ()),
            (osp.join(mydir, _sync_fname), "Sheet1", ["Sheet2"]),
            (osp.join(mydir, _sync_fname), "Sheet1", None),
            (osp.join(mydir, _sync_fname), "Sheet1", []),
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
                    prefix=False)
            _check_synced(osp.join(d, _synced_fname), 'Sheet1')

    @ddt.data(
            (_sync_fname, "Sheet1", ["Sheet2", "Sheet3"]),
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
                    prefix=False)
            _check_synced(osp.join(d, _synced_fname), 'Sheet1')
