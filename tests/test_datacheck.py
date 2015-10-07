import unittest
import os
import sys

from co2mpas.functions import _process_folder_files
import tempfile
import json

OVERWRITE_SEATBELT = False # NOTE: Do not commit it as `True`!
DATA_DIFF_RATIO = 1e-6
EPS = 2 * sys.float_info.epsilon / DATA_DIFF_RATIO


class SeatBelt(unittest.TestCase):

    def _check_summaries(self, new_sums, old_sums):

        msg = "AssertionError: %f not less than or equal to %f\n" \
              "Failed [%r]: %s !~= %s"

        fail = []

        for i, (summary, old_summary) in enumerate(zip(new_sums, old_sums)):
            err = []
            for k, nv in summary.items():

                ov = old_summary[k]
                if isinstance(ov, str):
                    ratio = DATA_DIFF_RATIO + 1 if ov != nv else 0
                else:
                    ratio = abs(ov - nv) / max(abs(min(ov, nv)), EPS)
                if ratio > DATA_DIFF_RATIO:
                    err.append(msg %(ratio, DATA_DIFF_RATIO, k, ov, nv))

            if err:
                err = ["\nFailed summary[%i]:\n" % i] + err
                err.append('  +--NEW: %s' % sorted(summary.items()))
                err.append('  +--OLD: %s' % sorted(old_summary.items()))
                fail.extend(err)

        if fail:
            self.fail('\n'.join(fail))

    def test_demos(self):
        path = os.path.join(os.path.dirname(__file__), '..', 'co2mpas', 'demos')
        file = '%s/co2mpas_demo_1_full_data.xlsx' % path

        res = _process_folder_files(
            file, hide_warn_msgbox=True, extended_summary=False,
            with_output_file=False)[0]

        print(res)
        summaries = res['SUMMARY']

        tmpdir = tempfile.gettempdir()
        sum_file = os.path.join(tmpdir, 'co2mpas_seatbelt_demos.json')

        if not OVERWRITE_SEATBELT and os.path.isfile(sum_file):
            with open(sum_file, 'rt') as fd:
                old_summaries = json.load(fd)
                self._check_summaries(summaries, old_summaries)
        with open(sum_file, 'wt') as fd:
            json.dump(summaries, fd)
