#!/usr/bin/env python
#
# Copyright 2014-2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
r"""
Shift and resample excel-tables.

Usage:
  datasync  [(-v | --verbose) | --logconf <conf-file>]
            [--force | -f] [--out-frmt=<frmy>] [--prefix-cols] [-O <output-path>]
            <ref-sheet> <x-label> <y-label> [<sync-sheets> ...]
  datasync  [--verbose | -v]  (--version | -V)
  datasync  --help

Options:
  -O <output-path>             Output folder.  Fails if intermediate folders not exist
                               and not --force. [default: .]
  -f, --force                  Overwrite excel-file(s) and/or create any missing folders.
  --out-frmt=<frmt>            printf format-string generate the output-filename from `fname` & `.ext`
                               [default: %s.sync%s].
  --prefix-cols                Prefix all synced column names with their source sheet-names.
                               By default, only clashing column-names are prefixed.
  <ref-sheet>                  The excel-sheet containing the reference table,
                               in xl-ref notation e.g. folder/Book.xlsx#Sheet1!
                               Synced columns will be appended into this table.
                               For xl-refs see https://pandalone.readthedocs.org/en/latest/reference.html#module-pandalone.xleash
  <x-label>                    Column-name of x-axis (e.g. 'times').
  <y-label>                    Column-name of y-axis to cross-correlate between <ref-sheet>
                               and all <sync-sheet>.
  <sync-sheets>                Sheets to be synced, also in xl-ref notation.
                               If unspecified, syncs all other non-empty sheets of <ref-sheet>.

Miscellaneous:
  -h, --help                   Show this help message and exit.
  -V, --version                Print version of the program, with --verbose
                               list release-date and installation details.
  -v, --verbose                Print more verbosely messages - overridden by --logconf.
  --logconf=<conf-file>        Path to a logging-configuration file, according to:
                               See https://docs.python.org/3/library/logging.config.html#configuration-file-format
                               Uses reads a dict-schema if file ends with '.yaml' or '.yml'.
                               See https://docs.python.org/3.5/library/logging.config.html#logging-config-dictschema

Examples::

    ## Sync all sheets of `wbook.xlsx`:
    datasync folder/wbook.xlsx#Sheet1  times  velocity

    ## Sync selected sheets of `wbook.xlsx`:
    datasync folder/wbook.xlsx#Sheet1  times  velocity Sheet1 Sheet2

    ## Sync Sheet1 from `other_wbook.xlsx` into `wbook.xlsx`:
    datasync folder/wbook.xlsx#Sheet1!:  times  velocity other_wbook.xlsx#Sheet1!:

    # Typical usage for CO2MPAS velocity time-series from Dyno and OBD:
    datasync -O ../output book.xlsx  times  velocities  WLTP-H  WLTP-H_OBD

    ## View "big" version:
    datasync -vV

Known Limitations:
 * Absolute paths with drive-letters currently do not work
  (as of Apr-2016, pandalone-0.1.9).
"""
from collections import OrderedDict, Counter
import functools as fnt
import itertools as itt
import logging
import os
from pandalone import xleash
import sys

from boltons.setutils import IndexedSet
import docopt
from numpy.fft import fft, ifft, fftshift

import numpy as np
import os.path as osp
import pandas as pd

from .__main__ import CmdException, init_logging, build_version_string


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


def synchronization(ref, *data, x_label='times', y_label='velocities'):
    """
    Yields the data re-sampled and synchronized respect to x axes (`x_id`) and
    the reference signal `y_id`.

    :param ref:
        Reference data.
    :type ref: dict

    :param data:
        Data to synchronize.
    :type data: list[dict]

    :param x_label:
        X label of the reference signal.
    :type x_label: str, optional

    :param y_label:
        Y label of the reference signal.
    :type y_label: str, optional

    :return:
        The re-sampled and synchronized data.
    :rtype: generator
    """

    dx = float(np.median(np.diff(ref[x_label])) / 10)
    m, M = min(ref[x_label]), max(ref[x_label])

    for d in data:
        m, M = min(min(d[x_label]), m), max(max(d[x_label]), M)

    X = np.arange(m, M + dx, dx)
    Y = np.interp(X, ref[x_label], ref[y_label])

    x = ref[x_label]

    yield 0, ref

    for d in data:
        s = OrderedDict([(k, fnt.partial(np.interp, xp=d[x_label], fp=v))
                         for k, v in d.items() if k != x_label])

        shift = compute_shift(Y, s[y_label](X)) * dx

        x_shift = x + shift

        r = [(k, v(x_shift)) for k, v in s.items()]

        yield shift, ref.__class__(OrderedDict(r))


def _parse_sheet_names(sheet_name, input_file=''):
    try:
        r = xleash.parse_xlref(sheet_name)
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
        prefix_cols=False):

    out_sheet = _parse_sheet_names(ref_sheet)['sheet_name']
    sheets_factory = xleash.SheetsFactory()

    if not sync_sheets:
        book = sheets_factory.fetch_sheet(input_file, 0)._sheet.book
        sync_sheets = IndexedSet(book.sheet_names()).difference([out_sheet])

    data, headers = [], []
    for xl_ref in itt.chain([ref_sheet], sync_sheets):
        xlref = _parse_sheet_names(xl_ref, input_file=input_file)
        sheet_name, xlref = xlref['sheet_name'], xlref['xlref']
        d = xleash.lasso(xlref, sheets_factory=sheets_factory)
        if not d:
            continue
        str_row_indices = [i for i, r in enumerate(d)
            if any(isinstance(v, str) for v in r)]

        req_cols = set([x_label, y_label])
        for k in str_row_indices:
            if set(d[k]) >= req_cols:
                break
        else:
            raise CmdException("Columns(%r) not found in rows(%s) of sheet(%r)!" %
                    ([x_label, y_label], str_row_indices, xlref))
        ix = d[k]
        i = max(str_row_indices, default=0) + 1

        d, h = pd.DataFrame(d[i:], columns=ix), pd.DataFrame(d[:i], columns=ix)
        d.dropna(how='all', inplace=True)
        d.dropna(axis=1, how='any', inplace=True)
        data.append(d)
        headers.append((sheet_name, k, h))

    res = list(synchronization(*data, x_label=x_label, y_label=y_label))

    if prefix_cols:
        ix = set()
        for sn, i, h in headers:
            ix.update(h.columns)
    else:
        ix = Counter()
        for sn, i, h in headers:
            ix.update(set(h.columns))
        ix = {k for k, v in ix.items() if v > 1}

    for sn, i, h in headers[1:]:
        for j in ix.intersection(h.columns):
            h[j].iloc[i] = '%s %s' % (sn, h[j].iloc[i])

    frames = [h[df.columns].append(df) for (_, df), (sn, i, h) in zip(res, headers)]
    df = pd.concat(frames, axis=1)

    return df

def _do_datasync(opts):
    ref_sheet = opts['<ref-sheet>']
    x_label = opts['<x-label>']
    y_label = opts['<y-label>']
    prefix = opts['--prefix-cols']
    out_folder = opts['-O']
    out_frmt = opts['--out-frmt']
    sync_sheets = opts['<sync-sheets>']
    force = opts['--force']

    if not osp.isdir(out_folder):
        if force:
            os.makedirs(out_folder)
        else:
            raise CmdException("Folder %r not found!"
                    "Specify --force to create intermediate folders." % out_folder)

    input_fpath, ref_sheet, df = apply_datasync(
            ref_sheet, sync_sheets, x_label, y_label, prefix)

    basename = osp.basename(input_fpath)
    output_file = osp.abspath(osp.join(out_folder, out_frmt % osp.splitext(basename)))

    if osp.isfile(output_file):
        if force:
            log.info('Overwritting datasync-file: %r...', output_file)
        else:
            raise CmdException("Output file exists! \n"
                               "\n To overwrite add '-f' option!")

    if input_fpath: ## FIXME: condition always True
        from .io.excel import clone_excel
        writer_fact = fnt.partial(clone_excel, input_fpath)
    else:
        writer_fact = pd.ExcelWriter

    with writer_fact(output_file) as writer:
        # noinspection PyUnresolvedReferences
        df.to_excel(writer, ref_sheet, header=False, index=False)
        writer.save()


def _main(*args):
    """Does not ``sys.exit()`` like :func:`main()` but throws any exception."""

    opts = docopt.docopt(__doc__, argv=args or sys.argv[1:])

    verbose = opts.get('--verbose', False)
    init_logging(verbose, logconf_file=opts.get('--logconf'))
    if opts['--version']:
        v = build_version_string(verbose)
        try:
            sys.stdout.buffer.write(v.encode() + b'\n')
            sys.stdout.buffer.flush()
        except:
            print(v)
    else:
        _do_datasync(opts)


def main(*args):
    try:
        _main(*args)
    except CmdException as ex:
        log.info('%r', ex)
        exit(ex.args[0])
    except Exception as ex:
        log.error('%r', ex)
        raise


if __name__ == '__main__':
    if sys.version_info < (3, 4):
        msg = "Sorry, Python >= 3.4 is required, but found: {}"
        sys.exit(msg.format(sys.version_info))
    main()
