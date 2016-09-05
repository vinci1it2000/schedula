#!/usr/b in/env python
#
# Copyright 2014-2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
#
"""A *report* contains the co2mpas-run values to time-stamp and disseminate to TA authorities & oversight bodies."""
from collections import (defaultdict, OrderedDict, namedtuple, Mapping)  # @UnusedImport
import textwrap
from typing import (
    List, Sequence, Iterable, Text, Tuple, Callable)  # @UnusedImport

from toolz import itertoolz as itz, dicttoolz as dtz

from co2mpas import __uri__  # @UnusedImport
from co2mpas import utils
from co2mpas._version import (__version__, __updated__, __file_version__,   # @UnusedImport
                              __input_file_version__, __copyright__, __license__)  # @UnusedImport
from co2mpas.sampling import dice, baseapp
from co2mpas.sampling.baseapp import convpath
import pandas as pd
import functools as fnt
import re
import os.path as osp
import traitlets as trt


###################
##     Specs     ##
###################

REPORT_VERSION = '0.0.1'  ## TODO: Move to `co2mpas/_version.py`.

class Report(baseapp.Spec):
    """Mines reported-parameters from co2mpas excel-files and serves them as a pandas dataframes."""

    input_xlref = trt.Unicode('#Inputs!B2:C_:"sr"',
            help="""
            The *xlref* expression to resolving to 2 columns (<param-name>, <value>) to extract
            from co2mpas input files.'
            """).tag(config=True)
    output_master_xlref = trt.Unicode('#xlref!::"dict"',
            help="""
            The *xlref* expression resolving to a *dictionary* of other xlrefs
            inside co2mpas output files.'
            """).tag(config=True)

    output_table_keys = trt.List(trt.Unicode(),
            default_value=['summary.results', 'summary.selection', 'summary.comparison', ],
            help="""
            A list of the keys within `output_master_xlref` dictionary to read
            and resolve as *xlref* expressions, while extracting from co2mpas output files.'
            """).tag(config=True)

    input_params = trt.Instance(pd.Series, allow_none=True)
    output_tables = trt.List(trt.Instance(pd.DataFrame), allow_none=True)

    def clear_params(self, fpath):
        self.input_params = self.output_tables = None

    def extract_input_params(self, fpath, skip_collect=False):
        from pandalone import xleash

        #fpath = convpath(fpath)
        self.input_params = xleash.lasso(self.input_xlref, url_file=fpath)
        return self.input_params

    def extract_output_tables(self, fpath, skip_collect=False):
        from pandalone import xleash

        #fpath = convpath(fpath)
        master_xlrefs = xleash.lasso(self.output_master_xlref, url_file=fpath)
        assert isinstance(master_xlrefs, Mapping), (
            "The `output_master_xlref(%s) must resolve to a dictionary, not type(%r): %s"
            % (self.output_master_xlref, type(master_xlrefs), master_xlrefs))

        tables = []
        for tab_key in self.output_table_keys:
            assert tab_key in master_xlrefs, (
                "The `output_table_key` %r were not found in *master-xlref* dictionary: %s"
                % (tab_key, master_xlrefs))

            tab_xlref = master_xlrefs[tab_key]
            tab = xleash.lasso(tab_xlref, url_file=fpath)
            assert isinstance(tab, pd.DataFrame), (
            "The `output_master_xlref` key (%r --> %r) must resolve to a DataFrame, not type(%r): %s"
            % (tab_key, tab_xlref, type(tab), tab))
            tables.append(tab)

        self.output_tables = tables
        return self.output_tables

###################
##    Commands   ##
###################


_file_arg_regex = re.compile('(inp|out)=(.+)', re.IGNORECASE)

class ReportCmd(baseapp.Cmd):
    """
    SYNTAX
        co2dice report ( inp=<co2mpas-file-1> | out=<co2mpas-file-1> ) ...
    DESCRIPTION
        Extract the report parameters from the co2mpas input/output files.

        The *report parameters* will be time-stamped and disseminated to
        TA authorities & oversight bodies with an email, to receive back
        the sampling decision.

        If multiple files given from a kind (inp/out), later ones overwrite any previous.
    """

    examples = trt.Unicode("""
        To extract the report-parameters from an input co2mpas file, try:

            co2dice report  inp=co2mpas_input.xlsx

        To extract the report from both input and output files, try:

            co2dice report  inp=co2mpas_input.xlsx out=co2mpas_results.xlsx
        """)

    __report = None

    @property
    def report(self):
        if not self.__report:
            self.__report = Report(config=self.config)
        return self.__report

    def run(self, *args):
        self.log.info('Extracting report-parameters from files %s...', args)
        if len(args) < 1:
            raise baseapp.CmdException('Cmd %r takes at least one argument, received %d: %r!'
                               % (self.name, len(args), args))
        for fpath in args:
            m = _file_arg_regex.match(fpath)
            if not m:
                raise baseapp.CmdException("Cmd %r filepaths must either start with 'inp=' or 'out=' prefix,\n  was just: %r!"
                                   % (self.name, fpath))

            meth = (self.report.extract_input_params
                    if m.group(1).lower() == 'inp' else
                    self.report.extract_output_tables)
            fpath = m.group(2)

            res = meth(fpath)
            if isinstance(res, list):
                yield from res
            else:
                yield res


if __name__ == '__main__':
    from traitlets.config import get_config
    # Invoked from IDEs, so enable debug-logging.
    c = get_config()
    c.Application.log_level=0
    #c.Spec.log_level='ERROR'

    argv = None
    ## DEBUG AID ARGS, remember to delete them once developed.
    #argv = ''.split()
    #argv = '--debug'.split()

    ReportCmd(config=c).run('foo.xlsx')
