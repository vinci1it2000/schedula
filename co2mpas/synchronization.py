#!/usr/bin/env python
#
# Copyright 2014-2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

import logging
import numpy as np
from numpy.fft import fft, ifft, fftshift
from scipy.interpolate import InterpolatedUnivariateSpline as Spline
from pandalone.xleash import lasso, parse_xlref, SheetsFactory
from itertools import chain
from .functions.io.excel import clone_excel
from collections import OrderedDict
import pandas as pd

log = logging.getLogger(__name__)


def cross_correlation_using_fft(x, y):
    f1 = fft(x)
    f2 = fft(np.flipud(y))
    cc = np.real(ifft(f1 * f2))
    return fftshift(cc)


# shift &lt; 0 means that y starts 'shift' time steps before x # shift &gt; 0 means that y starts 'shift' time steps after x
def compute_shift(x, y):
    assert len(x) == len(y)
    c = cross_correlation_using_fft(x, y)
    assert len(c) == len(x)
    zero_index = int(len(x) / 2) - 1
    shift = zero_index - np.argmax(c)
    return shift


def synchronization(reference, *data, x_label='times', y_label='velocities'):
    """
    Returns the data re-sampled and synchronized respect to x axes (`x_id`) and
    the reference signal `y_id`.

    :param reference:

    :type reference: dict

    :param data:

    :type data: list[dict]

    :param x_label:
    :type x_id: str, optional

    :param y_label:
    :type y_label: str, optional

    :return:
    :rtype: list[dict]
    """

    dx = np.median(np.diff(reference[x_label])) / 10
    m, M = min(reference[x_label]), max(reference[x_label])

    for d in data:
        m, M = min(min(d[x_label]), m), max(max(d[x_label]), M)

    X = np.linspace(m, M, int((M - m) / dx))
    Y = Spline(reference[x_label], reference[y_label], k=1, ext=3)(X)

    x = reference[x_label]

    yield 0, reference

    for d in data:
        s = OrderedDict([(k, Spline(d[x_label], v, k=1, ext=3))
                         for k, v in d.items() if k != x_label])

        shift = compute_shift(Y, np.nan_to_num(s[y_label](X))) * dx

        x_shift = x + shift

        r = [(k, v(x_shift)) for k, v in s.items()]

        yield shift, reference.__class__(OrderedDict(r))


def _parse_sheet_names(sheet_name, input_file=''):
    try:
        r = parse_xlref(sheet_name)
        if not r['url_file']:
            xl_ref = ''.join((input_file, sheet_name))
        else:
            xl_ref = sheet_name
        sheet_name = r['xl_ref']
    except:
        xl_ref = '%s#%s!A1(RD):._:RD' % (input_file, sheet_name)

    return {'sheet_name': sheet_name, 'xlref': xl_ref}


def apply_datasync(
        ref_sheet, sync_sheets, x_label, y_label, output_file, input_file='',
        prefix='sync', suffix='sync'):
    out_sheet = _parse_sheet_names(ref_sheet)['sheet_name']
    sheets_factory = SheetsFactory()
    if not sync_sheets:
        book = sheets_factory.fetch_sheet(input_file, 0)._sheet.book
        sync_sheets = set(book.sheet_names()).difference([out_sheet])

    data, headers = [], []
    for xl_ref in chain([ref_sheet], sync_sheets):
        xlref = _parse_sheet_names(xl_ref, input_file=input_file)['xlref']
        d = lasso(xlref, sheets_factory=sheets_factory)
        i =[i for i, r in enumerate(d)
            if any(isinstance(v, str) for v in r)]
        ix = next(d[k] for k in i if all(v in d[k] for v in (x_label, y_label)))
        i = max(i, default=0) + 1

        d, h = pd.DataFrame(d[i:], columns=ix), pd.DataFrame(d[:i], columns=ix)
        d.dropna(how='all', inplace=True)
        d.dropna(axis=1, how='any', inplace=True)
        data.append(d)
        headers.append(h)

    res = list(synchronization(*data, x_label=x_label, y_label=y_label))

    for h in headers[1:]:
        h[y_label].iloc[-1] = '%s %s' % (suffix, h[y_label].iloc[-1])

    frames = [h[df.columns].append(df) for (s, df), h in zip(res, headers)]
    df = pd.concat(frames, axis=1)

    if input_file:
        writer = clone_excel(input_file, output_file)
    else:
        writer = pd.ExcelWriter(output_file)

    df.to_excel(writer, out_sheet, header=False, index=False)
    writer.save()
    return df
