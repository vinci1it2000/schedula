from collections import Iterable
import unittest
import glob
import numpy as np
import os

from compas.functions import _make_summary, _extract_summary, files_exclude_regex


def process_folder_files(input_folder):
    """
    Processes all excel files in a folder with the model defined by
    :func:`architecture`.

    :param input_folder:
        Input folder.
    :type input_folder: str

    :param output_folder:
        Output folder.
    :type output_folder: str
    """

    from compas.models import architecture

    model = architecture(with_output_file=False)

    fpaths = glob.glob(input_folder + '/*.xlsx')

    summary = {}

    output_files = {
        'prediction_output_file_name': 'prediction_NEDC',
        'calibration_output_file_name': 'calibration_WLTP-H',
        'calibration_output_file_name<0>': 'calibration_WLTP-L',
        'calibration_cycle_prediction_outputs_file_name':
            'prediction_WLTP-H',
        'calibration_cycle_prediction_outputs_file_name<0>':
            'prediction_WLTP-L',
    }

    def check_printable(tag, data):
        mods = {'errors calibrated_models', 'errors AT_gear_shifting_model',
                'origin calibrated_models'}

        if tag in mods:
            return True

        if not isinstance(data, str) and isinstance(data, Iterable):
            return len(data) <= 10
        return True

    def basic_filter(value, data, tag):
        try:
            if not check_printable(tag, value):
                b = value > 0
                if b.any():
                    return np.mean(value[b])
                else:
                    return
        except:
            pass
        return value

    filters = {None: (basic_filter,)}

    sheets = {
        'TRG NEDC': {
            'results': {
                'output': 'prediction_cycle_targets',
                'check': check_printable,
                'filters': filters
            },
        },
        'PRE NEDC': {
            'results': {
                'output': 'prediction_cycle_outputs',
                'check': check_printable,
                'filters': filters
            },
        },
        'CAL WLTP-H': {
            'results': {
                'output': 'calibration_cycle_outputs',
                'check': check_printable,
                'filters': filters
            }
        },
        'CAL WLTP-L': {
            'results': {
                'output': 'calibration_cycle_outputs<0>',
                'check': check_printable,
                'filters': filters
            }
        },
        'PRE WLTP-H': {
            'results': {
                'output': 'calibration_cycle_prediction_outputs',
                'check': check_printable,
                'filters': filters
            }
        },
        'PRE WLTP-L': {
            'results': {
                'output': 'calibration_cycle_prediction_outputs<0>',
                'check': check_printable,
                'filters': filters
            }
        },
    }

    for fpath in fpaths:
        fname = os.path.basename(fpath).split('.')[0]

        if not files_exclude_regex.match(fname):
            print('Skipping: %s' % fname)
            continue

        print('Processing: %s' % fname)

        inputs = {'input_file_name': fpath}

        for k, v in output_files.items():
            inputs[k] = ''

        res = model.dispatch(inputs=inputs)

        s = _make_summary(sheets, *res, **{'vehicle': fname})
        s.update(_extract_summary(s))

        for k, v in s.items():
            summary[k] = l = summary.get(k, [])
            l.append(v)

    #from compas.dispatcher.draw import dsp2dot

    #dsp2dot(model, workflow=True, view=True, function_module=False,
    #        node_output=False, edge_attr=model.weight)
    #dsp2dot(model, view=True, function_module=False)

    return summary


class SeatBelt(unittest.TestCase):

    def test_basic(self):

        summary = process_folder_files(os.path.curdir)['SUMMARY']

        for v in summary['SUMMARY']:
            for k, r  in v.items():
                print(k, r)