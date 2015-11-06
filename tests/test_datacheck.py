from co2mpas.__main__ import init_logging
from co2mpas.functions import _process_folder_files
import json
import os
import sys
import tempfile
import unittest


## Set this to `True` to update setbelt data.
# NOTE: Do not commit it as `True`!
OVERWRITE_SEATBELT = False
EPS = 2 * sys.float_info.epsilon

## setting to 0  compares EXACT.
# NOTE: Do not commit it as none-zer0
DATA_DIFF_RATIO = 0 # 2 * EPS

init_logging(False)
#logging.getLogger('pandalone.xleash').setLevel(logging.INFO)

class SeatBelt(unittest.TestCase):

    def _check_summaries(self, new_sums, old_sums):

        msg = "AssertionError: %f not less than or equal to %f\n" \
              "Failed [%r]: %s !~= %s"

        fail = []

        for i, (summary, old_summary) in enumerate(zip(new_sums, old_sums)):
            err = []
            for k, ov in old_summary.items():

                nv = summary[k]
                if DATA_DIFF_RATIO == 0:
                    if nv != ov:
                        err.append("Failed [%r]: %s !~= %s"%(k, nv, ov))
                else:
                    if isinstance(nv, str):
                        ratio = DATA_DIFF_RATIO + 1 if nv != ov else 0
                    else:
                        ratio = abs(nv - ov) / max(abs(min(nv, ov)), EPS)
                    if ratio > DATA_DIFF_RATIO:
                        err.append(msg %(ratio, DATA_DIFF_RATIO, k, nv, ov))

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
        #file = path  ## Read all demo files.

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
        else:
            with open(sum_file, 'wt') as fd:
                json.dump(summaries, fd)
