from co2mpas import datasync
from co2mpas.__main__ import main, init_logging
import logging
import tempfile
import unittest

import os.path as osp
import ddt


init_logging(False)
log = logging.getLogger(__name__)

mydir = osp.dirname(__file__)
sync_fname = 'datasync.xlsx'

@ddt.ddt
class DataSync(unittest.TestCase):

    @ddt.data(
            (sync_fname, None, "Sheet1", ["Sheet2"]),
            (sync_fname, None, "Sheet1", None),
            (sync_fname, None, "Sheet1", ()),
            (osp.join(mydir, sync_fname), None, "Sheet1", ["Sheet2"]),
            (osp.join(mydir, sync_fname), None, "Sheet1", None),
            (osp.join(mydir, sync_fname), None, "Sheet1", []),
            )
    def test_api_smoke_text(self, case):
        inppath, outfile, ref_sheet, sync_sheets = case
        with tempfile.TemporaryDirectory() as d:
            outpath = d if outfile is None else osp.join(d, outfile)
            datasync.apply_datasync(
                    ref_sheet=ref_sheet,
                    sync_sheets=sync_sheets,
                    x_label='x',
                    y_label='y1',
                    output_file=outpath,
                    input_file=inppath,
                    prefix=False)

    @ddt.data(
            (sync_fname, None, "Sheet1", ["Sheet2"]),
            (sync_fname, None, "Sheet1", None),
            (sync_fname, None, "Sheet1", ()),
            (osp.join(mydir, sync_fname), None, "Sheet1", ["Sheet2"]),
            (osp.join(mydir, sync_fname), None, "Sheet1", None),
            (osp.join(mydir, sync_fname), None, "Sheet1", []),
            )
    def test_main_smoke_text(self, case):
        inppath, outfile, ref_sheet, sync_sheets = case
        with tempfile.TemporaryDirectory() as d:
            outpath = d if outfile is None else osp.join(d, outfile)
            cmd = 'datasync -v %s x y1 %s %s -O %s' % (
                    inppath, ref_sheet, ' '.join(sync_sheets), outpath)
            main(*cmd.split())
