#!/usr/bin/env python
#
# Copyright 2014-2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
r"""
Shift and resample excel-tables; see http://co2mpas.io/usage.html#Synchronizing-time-series.

Usage:
  datasync  [(-v | --verbose) | --logconf <conf-file>]
            [--force | -f] [--no-clone] [--prefix-cols] [-O <output>]
            <x-label> <y-label> <ref-table> [<sync-table> ...]
  datasync  [--verbose | -v]  (--version | -V)
  datasync  --help

Options:
  <x-label>              Column-name of the common x-axis (e.g. 'times') to be resampled if needed.
  <y-label>              Column-name of y-axis cross-correlated between all <sync-table>
                         and <ref-table>.
  <ref-table>            The reference table, in *xl-ref* notation (usually given as  `file#sheet!`);
                         synced columns will be appended into this table.
                         The captured table must contain <x_label> & <y_label> as column labels.
                         If hash(`#`) symbol missing, assumed as file-path and
                         the table is read from its 1st sheet .
  <sync-table>           Sheets to be synced in relation to <ref-table>, also in *xl-ref* notation.
                         All tables must contain <x_label> & <y_label> as column labels.
                         Each xlref may omit file or sheet-name parts; in that case,
                         those from the previous xlref(s) are reused.
                         If hash(`#`) symbol missing, assumed as sheet-name.
                         If none given, all non-empty sheets of <ref-table> are synced
                         against the 1st one.
  -O <output>            Output folder or file path to write synchronized results:
                         - Non-existent path: taken as the new file-path; fails
                           if intermediate folders do not exist, unless --force.
                         - Existent file: file-path to overwrite if --force, fails otherwise.
                         - Existent folder: writes a new file `<ref-file>.sync<.ext>`
                           in that folder; --force required if that file exists.
                         By default, use folder of the <ref-table>.
  -f, --force            Overwrite excel-file(s) and create any missing intermediate folders.
  --prefix-cols          Prefix all synced column names with their source sheet-names.
                         By default, only clashing column-names are prefixed.
  --no-clone             Do not clone excel-sheets contained in <ref-table> workbook
                         into output.

Miscellaneous:
  -h, --help             Show this help message and exit.
  -V, --version          Print version of the program, with --verbose
                         list release-date and installation details.
  -v, --verbose          Print more verbosely messages - overridden by --logconf.
  --logconf=<conf-file>  Path to a logging-configuration file, according to:
                         See https://docs.python.org/3/library/logging.config.html#configuration-file-format
                         Uses reads a dict-schema if file ends with '.yaml' or '.yml'.
                         See https://docs.python.org/3.5/library/logging.config.html#logging-config-dictschema

* For xl-refs see: https://pandalone.readthedocs.org/en/latest/reference.html#module-pandalone.xleash

Examples::

    ## Read the full contents from all `wbook.xlsx` sheets as tables and
    ## sync their columns using the table from the 1st sheet as reference:
    datasync times  velocity  folder/Book.xlsx

    ## Sync `Sheet1` using `Sheet3` as reference:
    datasync times  velocity  wbook.xlsx#Sheet3!  Sheet1!

    ## The same as above- NOTE that sheet-indices are zero based!
    datasync times  velocity  wbook.xlsx#2!  0

    ## Complex Xlr-ref example:
    ## Read the table in sheet2 of wbook-2 starting at D5 cell
    ## or more Down 'n Right if that was empty, till Down n Right,
    ## and sync this based on 1st sheet of wbook-1:
    datasync times  velocity wbook-1.xlsx  wbook-2.xlsx#0!D5(DR):..(DR)

    # Typical usage for CO2MPAS velocity time-series from Dyno and OBD:
    datasync -O ../output times  velocities  ../input/book.xlsx  WLTP-H  WLTP-H_OBD

"""
from collections import OrderedDict, Counter
import logging
import os
import sys

from boltons.setutils import IndexedSet
import docopt
from numpy.fft import fft, ifft, fftshift
from pandalone import xleash

import functools as fnt
import numpy as np
import os.path as osp
import pandas as pd

from .__main__ import CmdException, init_logging, build_version_string


log = logging.getLogger(__name__)


synced_file_frmt = '%s.sync%s'


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


def _yield_synched_tables(ref, *data, x_label='times', y_label='velocities'):
    """
    Yields the data re-sampled and synchronized respect to x axes (`x_id`) and
    the reference signal `y_id`.

    :param dict ref:
        Reference data.
    :param data:
        Data to  yield synched tables from.
    :type data: list[dict]
    :param str x_label:
        X label of the reference signal.
    :param str y_label:
        Y label of the reference signal.

    :return:
        The re-sampled and synchronized data, as types of original `data`
        (e.g. dicts or DataFrames).
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


def synchronize(headers, tables, x_label, y_label, prefix_cols):
    res = list(_yield_synched_tables(*tables, x_label=x_label, y_label=y_label))

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
            h[j].iloc[i] = '%s.%s' % (sn, h[j].iloc[i])

    frames = [h[df.columns].append(df) for (_, df), (sn, i, h) in zip(res, headers)]
    df = pd.concat(frames, axis=1)

    return df



def _guess_xlref_without_hash(xlref, bias_on_fragment):
    if not xlref:
        raise CmdException("An xlref cannot be empty-string!")
    if '#' not in xlref:
        xlref = ('#%s!' if bias_on_fragment else '%s#:') % xlref
    return xlref

def _get_rest_sheet_names(url_file, sheet, sheets_factory):
    ## TODO: Move to pandalone.
    book = sheets_factory.fetch_sheet(url_file, sheet)._sheet.book
    return IndexedSet(book.sheet_names()) - [sheet]


def sheet_name(lasso):
    ## TODO: Move to pandalone.
    return lasso.sheet.get_sheet_ids().ids[0]


class Tables(object):
    ## Nice API, may adopt by pandalone.
    _sheets_factory = None

    def __init__(self, required_labels, sheets_factory=None):
        self.required_labels = required_labels
        if sheets_factory:
            self._sheets_factory = sheets_factory
        elif not self._sheets_factory:
            ## Permit class-wide sheets-fact.
            self._sheets_factory = xleash.SheetsFactory()
        self.headers = []
        self.tables = []
        self.ref_fpath = None
        self.ref_sh_name = None


    def _consume_next_xlref(self, xlref, lasso):
        """
        :param str xlref:
                an xlref that may not contain hash(`#`); in that case,
                it is taken as *file-part* or as *fragment-part* depending
                on the existence of prev lasso's `url_file`.
        :param Lasso lasso:
                reuses `url_file` & `sheet` if missing from xlref
        """

        xlref = _guess_xlref_without_hash(xlref, bias_on_fragment=bool(lasso.url_file))
        lasso = xleash.lasso(xlref,
                sheets_factory=self._sheets_factory,
                url_file=lasso.url_file,
                sheet=lasso.sheet,
                return_lasso=True)
        values = lasso.values
        if values: # Skip blank sheets.
            ## TODO: Convert column monkeybiz into pure-pandas using xleash.
            str_row_indices = [i for i, r in enumerate(values)
                if any(isinstance(v, str) for v in r)]

            req_labels = IndexedSet(self.required_labels)
            for k in str_row_indices:
                if set(values[k]) >= req_labels:
                    break
            else:
                raise CmdException("Columns %r not found in rows %r of sheet(%r)!" %
                        (self.required_labels, str_row_indices, xlref))
            ix = values[k]
            i = max(str_row_indices, default=0) + 1

            h = pd.DataFrame(values[:i], columns=ix)
            self.headers.append((sheet_name(lasso), k, h))

            values = pd.DataFrame(values[i:], columns=ix)
            values.dropna(how='all', inplace=True)
            values.dropna(axis=1, how='any', inplace=True)
            self.tables.append(values)

        return lasso


    def consume_next_xlref(self, xlref, lasso):
        i = len(self.tables)
        try:
            return self._consume_next_xlref(xlref, lasso)
        except CmdException as ex:
            raise CmdException('Cannot read sync-sheet(%i: %s) due to: %s' %
                    (i, xlref, ex.args[0]))
        except Exception as ex:
            log.error('Failed reading sync-sheet(%i: %s) due to: %s', i, xlref, ex)
            raise

    def collect_tables(self, ref_xlref, *sync_xlrefs):
        """
        Extract tables from ref and sync xlrefs.

        Each xlref may omit file or sheet-name parts; in that case, those from
        the previous xlref(s) are reused.
        """

        lasso = self.consume_next_xlref(ref_xlref, xleash.Lasso())
        self.ref_fpath = lasso.url_file
        self.ref_sh_name = sheet_name(lasso)
        assert lasso.url_file and self.ref_sh_name, (lasso.url_file, self.ref_sh_name)
        if not sync_xlrefs:
            sync_xlrefs = _get_rest_sheet_names(lasso.url_file,
                    self.ref_sh_name, self._sheets_factory)
        for xlref in sync_xlrefs:
            lasso = self.consume_next_xlref(xlref, lasso)



def _ensure_out_file(out_path, inp_path, force, out_frmt):
    """
    :param str out_path:
            If `None`, same folder as `inp_path` assumed.
    """
    basename = osp.basename(inp_path)

    if not out_path:
        out_path = osp.dirname(inp_path)

    if not osp.exists(out_path):
        out_file = out_path
        folders = osp.dirname(out_path)
        if not osp.isdir(folders):
            if force:
                log.info('Creating intermediate folders: %r...', folders)
                os.makedirs(folders)
            else:
                raise CmdException("Intermediate folders %r do not exist! \n"
                        "Tip: specify --force to create them." % out_path)
    elif osp.isfile(out_path):
        out_file = out_path
    elif osp.isdir(out_path):
        out_file = osp.join(out_path, out_frmt % osp.splitext(basename))
    else:
        assert False, 'Unexpected file-type: %r' % out_path
    assert out_file, (out_path, inp_path, force, out_frmt)

    out_file = osp.abspath(osp.expanduser(osp.expandvars(out_file)))
    if osp.isfile(out_file):
        if force:
            log.info('Overwritting datasync-file: %r...', out_file)
        else:
            raise CmdException("Output file exists! \n"
                               "\n To overwrite add '-f' option!")
    return out_file


def do_datasync(x_label, y_label, ref_xlref, *sync_xlrefs,
        out_path=None, prefix_cols=False, force=False, sheets_factory=None,
        no_clone=False):
    """
    :param str ref_xlref:
            The `xl-ref` capturing a table from a workbook-sheet to use as *reference*.
            The table must contain `x_label`, `y_label` column labels.
    :param ref_xlref:
            A list of `xl-ref` capturing tables from workbook-sheets,
            to be *synced* in relation to *reference*.
            All tables must contain `x_label`, `y_label` column labels.
            Each xlref may omit file or sheet-name parts; in that case,
            those from the previous xlref(s) are reused.
    :type ref_xlref: [str]
    :param bool prefix_cols:
            Prefix all synced column names with their source sheet-names.
            If not true, only clashing column-names are prefixed.
    :param str out_path:
            Output folder or file path to write synchronized results:
            - Non-existent path: taken as the new file-path; fails
              if intermediate folders do not exist, unless --force.
            - Existent file: fails, unless --force.
            - Existent folder: writes a new file `<ref-file>.sync<.ext>`
              in that folder; --force required if that file exists.
            If not true, use folder of the <ref-table>.
    :param bool force:
            When true, overwrites excel-file(s) and/or create missing folders.
    :param bool bo_clone:
            When true, do not clone excel-sheets contained in <ref-table> workbook
            into output.
    :param xleash.SheetsFactory sheets_factory:
            cache of workbook-sheets
    """
    tables = Tables((x_label, y_label), sheets_factory)
    tables.collect_tables(ref_xlref, *sync_xlrefs)
    df = synchronize(tables.headers, tables.tables, x_label, y_label, prefix_cols)

    if no_clone:
        writer_fact = pd.ExcelWriter
    else:
        from .io.excel import clone_excel
        writer_fact = fnt.partial(clone_excel, tables.ref_fpath)

    out_file = _ensure_out_file(out_path, tables.ref_fpath, force, synced_file_frmt)
    with writer_fact(out_file) as writer:
        # noinspection PyUnresolvedReferences
        df.to_excel(writer, tables.ref_sh_name, header=False, index=False)
        writer.save()


def main(*args):
    """Does not ``sys.exit()`` like a when invoked as script, throws exceptions instead."""

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
        do_datasync(
                opts['<x-label>'], opts['<y-label>'],
                opts['<ref-table>'], *opts['<sync-table>'],
                out_path=opts['-O'],
                prefix_cols=opts['--prefix-cols'],
                force=opts['--force'],
                no_clone=opts['--no-clone']
        )


if __name__ == '__main__':
    if sys.version_info < (3, 4):
        msg = "Sorry, Python >= 3.4 is required, but found: {}"
        sys.exit(msg.format(sys.version_info))
    try:
        main()
    except CmdException as ex:
        log.info('%r', ex)
        exit(ex.args[0])
    except Exception as ex:
        log.error('%r', ex)
        raise
