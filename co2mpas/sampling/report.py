#!/usr/b in/env python
#
# Copyright 2014-2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
#
"""A *report* contains the co2mpas-run values to time-stamp and disseminate to TA authorities & oversight bodies."""

from collections import (
    defaultdict, OrderedDict, namedtuple, Mapping)  # @UnusedImport
import re
from typing import (
    List, Sequence, Iterable, Text, Tuple, Dict, Callable)  # @UnusedImport

from co2mpas import __uri__  # @UnusedImport
from co2mpas._version import (__version__, __updated__, __file_version__,   # @UnusedImport
                              __input_file_version__, __copyright__, __license__)  # @UnusedImport
from co2mpas.sampling import baseapp, dice, project
from co2mpas.sampling.baseapp import convpath, first_line
import pandas as pd
import traitlets as trt


def parse_io_args(*args: Text) -> dice.IOFiles or None:
    """
    Separates args into those starting with 'inp=', 'out=', or none.

    For example, given the 3 args::

        'inp=abc', 'out:gg' 'out=bar'

    It will return::

        IOFiles(inp=['abc'], out=['bar'], other={2: 'out:gg'})

    """
    inp, out = [], []
    other = {}
    for i, arg in enumerate(args, 1):
        m = _file_arg_regex.match(arg)
        if not m:
            other[i] = arg
        else:
            l = inp if m.group(1).lower() == 'inp' else out
            l.append(convpath(m.group(2), 0, 0))

    if inp or out or other:
        return dice.IOFiles(inp, out, other)


###################
##     Specs     ##
###################
REPORT_VERSION = '0.0.1'  ## TODO: Move to `co2mpas/_version.py`.

_file_arg_regex = re.compile('(inp|out)=(.+)', re.IGNORECASE)

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

    def extract_input_params(self, fpath):
        from pandalone import xleash

        #fpath = convpath(fpath)
        self.input_params = xleash.lasso(self.input_xlref, url_file=fpath)
        return self.input_params

    def extract_output_tables(self, fpath):
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

    def yield_from_iofiles(self, iofiles: dice.IOFiles):
        for fpath in iofiles.inp:
            yield self.extract_input_params(convpath(fpath))

        for fpath in iofiles.out:
            yield from self.extract_output_tables(convpath(fpath))


###################
##    Commands   ##
###################


class ReportCmd(baseapp.Cmd):
    """
    Extract the report parameters from the co2mpas input/output files, or from *current-project*.

    The *report parameters* will be time-stamped and disseminated to
    TA authorities & oversight bodies with an email, to receive back
    the sampling decision.

    If multiple files given from a kind (inp/out), later ones overwrite any previous.

    SYNTAX
        co2dice report ( inp=<co2mpas-file-1> | out=<co2mpas-file-1> ) ...
        co2dice report --project
    """

    examples = trt.Unicode("""
        To extract the report-parameters from an INPUT co2mpas file, try:

            co2dice report  inp=co2mpas_input.xlsx

        To extract the report from both INPUT and OUTPUT files, try:

            co2dice report  inp=co2mpas_input.xlsx out=co2mpas_results.xlsx

        To view the report of the *current-project*, try:

            co2dice report  --project
        """)

    project = trt.Bool(False,
            help="""
            Whether to extract report from files present already in the *current-project*.
            """).tag(config=True)

    __report = None

    @property
    def report(self):
        if not self.__report:
            self.__report = Report(config=self.config)
        return self.__report

    @property
    def projects_db(self):
        p = project.ProjectsDB.instance()
        p.config = self.config
        return p

    def __init__(self, **kwds):
        with self.hold_trait_notifications():
            dkwds = {
                'conf_classes': [Report],
                'cmd_flags': {
                    'project': ({
                            'ReportCmd': {'project': True},
                        }, first_line(ReportCmd.project.help)),
                }
            }
            dkwds.update(kwds)
            super().__init__(**dkwds)


    def _build_io_files_from_project(self, args) -> dice.IOFiles:
        project = self.projects_db.current_project()
        iofiles = project.list_iofiles()
        if not iofiles:
            raise baseapp.CmdException(
                    "Current project %r contains no input/output files!"
                    % project.pname)
        return iofiles


    def _build_io_files_from_args(self, args) -> dice.IOFiles:
        iofiles = parse_io_args(*args)
        if iofiles.other:
            raise baseapp.CmdException(
                    "Cmd %r filepaths must either start with 'inp=' or 'out=' prefix!\n%s"
                    % (self.name, '\n'.join('  arg[%d]: %s' % i for i in iofiles.other.items())))

        return iofiles

    def run(self, *args):
        nargs = len(args)
        if self.project:
            if nargs > 0:
                raise baseapp.CmdException(
                    "Cmd '%s --project' takes no arguments, received %d: %r!"
                    % (self.name, len(args), args))

            self.log.info('Extracting report-parameters from current-project...')
            iofiles = self._build_io_files_from_project(args)
        else:
            self.log.info('Extracting report-parameters from files %s...', args)
            if nargs < 1:
                raise baseapp.CmdException(
                    "Cmd %r takes at least one filepath as argument, received %d: %r!"
                    % (self.name, len(args), args))
            iofiles = self._build_io_files_from_args(args)

        yield from self.report.yield_from_iofiles(iofiles)


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
