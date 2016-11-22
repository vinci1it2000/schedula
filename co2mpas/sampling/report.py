#!/usr/b in/env python
#
# Copyright 2014-2016 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
#
"""A *report* contains the co2mpas-run values to time-stamp and disseminate to TA authorities & oversight bodies."""

from collections import (
    defaultdict, OrderedDict, namedtuple, Mapping)  # @UnusedImport
from typing import (
    List, Sequence, Iterable, Text, Tuple, Dict, Callable)  # @UnusedImport

import pandas as pd
import traitlets as trt
import pandalone.utils as pndlu

from . import baseapp, project, CmdException, PFiles
from .. import __uri__  # @UnusedImport
from .. import (__version__, __updated__, __file_version__,   # @UnusedImport
                __input_file_version__, __copyright__, __license__)  # @UnusedImport


###################
##     Specs     ##
###################
REPORT_VERSION = '0.0.1'  ## TODO: Move to `co2mpas/_version.py`.


class Report(baseapp.Spec):
    """Mines reported-parameters from co2mpas excel-files and serves them as a pandas dataframes."""

    dice_report_xlref = trt.Unicode('#dice_report!:"df"',
                                    help="The *xlref* expression to read the dice-report from output-file."
                                    ).tag(config=True)

    input_params = trt.Instance(pd.Series, allow_none=True)
    output_tables = trt.List(trt.Instance(pd.DataFrame), allow_none=True)

    def clear_params(self, fpath):
        self.input_params = self.output_tables = None

    def extract_dice_report(self, fpath):
        from pandalone import xleash
        dice_report_xlref = '#dice_report!:"df"'
        tab = xleash.lasso(dice_report_xlref, url_file=fpath)
        assert isinstance(tab, pd.DataFrame), (
            "The dice_report xlref(%s) for %r must resolve to a DataFrame, not type(%r): %s" %
            (dice_report_xlref, dice_report_xlref, type(tab), tab))
        self.output_tables.append(tab)

        return self.output_tables

    def yield_from_iofiles(self, iofiles: PFiles):
        for fpath in iofiles.out:
            yield from self.extract_dice_report(pndlu.convpath(fpath))


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
                        }, pndlu.first_line(ReportCmd.project.help)),
                }
            }
            dkwds.update(kwds)
            super().__init__(**dkwds)


    def _build_io_files_from_project(self, args) -> PFiles:
        project = self.projects_db.current_project()
        pfiles = project.list_pfiles('inp', 'out', _as_index_paths=True)
        if not pfiles:
            raise CmdException(
                    "Current %s contains no input/output files!"
                    % project)
        return pfiles

    def _build_io_files_from_args(self, args) -> PFiles:
        """Just to report any stray files>"""
        pfiles = PFiles.parse_io_args(*args)
        if pfiles.other:
            bad_args = ('  arg[%d]: %s' % (1+ args.index(a), a)
                        for a in pfiles.other)
            raise CmdException(
                    "Cmd %r filepaths must either start with 'inp=' or 'out=' prefix!\n%s"
                    % (self.name, '\n'.join(bad_args)))

        return pfiles

    def run(self, *args):
        nargs = len(args)
        if self.project:
            if nargs > 0:
                raise CmdException(
                    "Cmd '%s --project' takes no arguments, received %d: %r!"
                    % (self.name, len(args), args))

            self.log.info('Extracting report-parameters from current-project...')
            pfiles = self._build_io_files_from_project(args)
        else:
            self.log.info('Extracting report-parameters from files %s...', args)
            if nargs < 1:
                raise CmdException(
                    "Cmd %r takes at least one filepath as argument, received %d: %r!"
                    % (self.name, len(args), args))
            pfiles = self._build_io_files_from_args(args)

        yield from self.report.yield_from_iofiles(pfiles)


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
