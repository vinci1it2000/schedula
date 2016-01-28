from co2mpas.__main__ import init_logging
from co2mpas.models import vehicle_processing_model
from co2mpas.functions import _file_iterator, _iter_d
import co2mpas.dispatcher.utils as dsp_utl
import os
import os.path as osp
import sys
import tempfile
import unittest
import logging
import numpy as np
from sklearn.metrics import mean_absolute_error
from pprint import pformat
from scipy.interpolate import InterpolatedUnivariateSpline

def _bool_env_var(var_name, default):
    v = os.environ.get(var_name, default)
    try:
        if v.strip().lower() in ('', '0', 'off', 'false'):
            return False
    except AttributeError:
        pass
    return bool(v)


## Set this to `True` to update setbelt data.
# NOTE: Do not commit it as `True`!
OVERWRITE_SEATBELT = _bool_env_var('OVERWRITE_SEATBELT', False)
RUN_ALL_FILES = _bool_env_var('RUN_ALL_FILES', False)
RUN_INPUT_FOLDER = os.environ.get('RUN_INPUT_FOLDER', None)

EPS = 2 * sys.float_info.epsilon

## Set to 0 to compare EXACT.
# NOTE: Do not commit it as none-zer0
DATA_DIFF_RATIO = 0 # 2 * EPS

init_logging(False)
#logging.getLogger('pandalone.xleash').setLevel(logging.INFO)
log = logging.getLogger(__name__)

class SeatBelt(unittest.TestCase):

    def _check_results(self, new_res, old_res):

        msg = "AssertionError: %f not less than or equal to %f\n" \
              "Failed [%r]: %s !~= %s"

        fail = []

        for i, (results, old_results) in enumerate(zip(new_res, old_res)):
            err = []
            results = dict(results)
            for k, ov in old_results:
                if k not in results:
                    err.append("Failed [%s]: missing" % str(k))
                    continue

                nv = results[k]
                ratio = _has_difference(nv, ov)
                if ratio:
                    nv, ov = pformat(nv), pformat(ov)
                    if DATA_DIFF_RATIO == 0:
                        err.append("Failed [%r]: %s !~= %s" %(k, nv, ov))
                    else:
                        err.append(msg %(ratio, DATA_DIFF_RATIO, k, nv, ov))

            if err:
                err = ["\nFailed results[%i]:\n" % i] + err
                fail.extend(err)

        if fail:
            self.fail('\n'.join(fail))

    def test_files(self):
        mydir = osp.dirname(__file__)
        log.info("  OVERWRITE_SEATBELT: %s \n"
                "  RUN_INPUT_FOLDER: %s \n"
                "  RUN_ALL_FILES: %s ",
                OVERWRITE_SEATBELT, RUN_INPUT_FOLDER, RUN_ALL_FILES)
        path = RUN_INPUT_FOLDER or osp.join(mydir, '..', 'co2mpas', 'demos')
        file = (path
                if (RUN_ALL_FILES or RUN_INPUT_FOLDER)
                else osp.join(path, 'co2mpas_demo_1_full_data.xlsx'))

        model = vehicle_processing_model(hide_warn_msgbox=True)

        resultes = []
        for fname, fpath in _file_iterator(file):
            log.info('Processing: %s', fname)

            inputs = {
                'vehicle_name': fname,
                'input_file_name': fpath,
            }
            r = model.dispatch(inputs=inputs, outputs=['report', 'summary'])
            r = dsp_utl.selector(['report', 'summary'], r)
            r.get('report', {}).pop('pipe', None)
            resultes.append(sorted(_iter_d(r), key=lambda x: x[0]))

        tmpdir = tempfile.gettempdir()
        res_file = osp.join(tmpdir, 'co2mpas_seatbelt_demos.json')

        if not OVERWRITE_SEATBELT and osp.isfile(res_file):
            old_resultes = dsp_utl.load_dispatcher(res_file)
            self._check_results(resultes, old_resultes)
            log.info('Comparing...')
        else:
            os.environ["OVERWRITE_SEATBELT"] = '0'
            dsp_utl.save_dispatcher(resultes, res_file)
            log.info('Overrating seat belt...')


def _has_difference(nv, ov):
    if hasattr(nv, '__call__') or (isinstance(nv, list) and isinstance(nv[0], InterpolatedUnivariateSpline)):
        return False

    if DATA_DIFF_RATIO == 0 or isinstance(nv, str):
        try:
            return not np.allclose(ov, nv)
        except:
            if isinstance(nv, np.ndarray):
                return not (ov == nv).all()
            return nv != ov
    else:
        if isinstance(nv, np.ndarray):
            ratio = mean_absolute_error(ov, nv)
        else:
            ratio = abs(nv - ov) / max(abs(min(nv, ov)), EPS)

        if ratio > DATA_DIFF_RATIO:
            return ratio
    return False
