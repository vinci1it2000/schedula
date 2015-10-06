#!/usr/bin/env python
#
# Copyright 2014-2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
"""
Predict NEDC CO2 emissions from WLTP cycles.

Usage:
    co2mpas [simulate] [-v] [--more-output] [--no-warn-gui] [--plot-workflow]
                       [-I <folder>] [-O <folder>]
    co2mpas demo       [--force] <folder>
    co2mpas template   [--force] <excel-file-path> ...
    co2mpas ipynb      [--force] <folder>
    co2mpas modelgraph [--list | <model-path>]
    co2mpas --help
    co2mpas --version

-I <folder>      Input folder, prompted with GUI if missing [default: ./input]
-O <folder>      Input folder, prompted with GUI if missing [default: ./output]
--more-output    Output also per-vehicle output-files.
--no-warn-gui    Does not pause batch-run to report inconsistencies.
--plot-workflow  Show workflow in browser, after run finished.
-F, --force      Overwrite template/sample excel-file(s).
-v, --verbose    Print more verbosely messages.


Sub-commands:
    simulate  [default] Run simulation for all excel-files in input-folder (-I).
    demo      Generate demo input-files inside <folder>.
    template  Generate "empty" input-file at <excel-file-path>.
    ipynb     Generate IPython notebooks inside <folder>; view them with cmd:
                ipython --notebook-dir=<folder>

* Items enclosed in `[]` are optional.

Examples:

    # Create sample-vehicles inside the `input` folder.
    # (the `input` folder must exist)
    co2mpas demo input

    # Run the sample-vehicles just created.
    # (the `output` folder must exist)
    co2mpas -I input -O output

    # Create an empty vehicle-file inside `input` folder.
    co2mpas template input/vehicle_1.xlsx

"""
from co2mpas import __version__ as proj_ver, __file__ as proj_file
import logging
import os
import re
import shutil
import sys

from docopt import docopt
import pkg_resources


class CmdException(Exception):
    pass

proj_name = 'co2mpas'

log = logging.getLogger(__name__)


def _init_logging(verbose):
    level = logging.DEBUG if verbose else logging.INFO
    frmt = "%(asctime)-15s:%(levelname)s:%(name)s:%(message)s"
    logging.basicConfig(level=level, format=frmt)


def _generate_files_from_streams(
        dst_folder, file_stream_pairs, force, file_category):
    dst_folder = os.path.abspath(dst_folder)
    if not os.path.exists(dst_folder):
        raise CmdException(
            "Destination folder '%s' does not exist!" % dst_folder)
    if not os.path.isdir(dst_folder):
        raise CmdException(
            "Destination '%s' is not a <folder>!" % dst_folder)

    for src_fname, streamer in file_stream_pairs:
        dst_fpath = os.path.join(dst_folder, src_fname)
        if os.path.exists(dst_fpath) and not force:
            msg = "Creating %s file '%s' skipped, already exists! \n  " \
                  "Use '-F' to overwrite it."
            log.info(msg, file_category, dst_fpath)
        else:
            log.info("Creating %s file '%s'...", file_category, dst_fpath)
            with open(dst_fpath, 'wb') as fd:
                shutil.copyfileobj(streamer(), fd, 16 * 1024)


def _cmd_ipynb(opts):
    dst_folder = opts['<folder>']
    force = opts['--force']
    file_category = 'IPYTHON NOTEBOOKS'
    file_stream_pairs = _get_internal_file_streams('ipynbs', r'.*\.ipynb$')
    file_stream_pairs = sorted(file_stream_pairs.items())
    _generate_files_from_streams(dst_folder, file_stream_pairs,
                                 force, file_category)


def _get_input_template_fpath():
    fname = 'co2mpas_template.xlsx'
    return pkg_resources.resource_stream(__name__, fname)  # @UndefinedVariable


def _cmd_template(opts):
    dst_fpaths = opts['<excel-file-path>']
    force = opts['--force']
    for fpath in dst_fpaths:
        fpath = os.path.abspath(fpath)
        if not fpath.endswith('.xlsx'):
            fpath = '%s.xlsx' % fpath
        if os.path.exists(fpath) and not force:
            raise CmdException(
                "Writing file '%s' skipped, already exists! "
                "Use '-f' to overwrite it." % fpath)
        if os.path.isdir(fpath):
            raise CmdException(
                "Expecting a file-name instead of directory '%s'!" % fpath)

        log.info("Creating TEMPLATE INPUT file '%s'...", fpath)
        stream = _get_input_template_fpath()
        with open(fpath, 'wb') as fd:
            shutil.copyfileobj(stream, fd, 16 * 1024)


def _get_internal_file_streams(internal_folder, incl_regex=None):
    """
    :return: a mappings of {filename--> stream-gen-function}.

    NOTE: Add internal-files also in `setup.py` & `MANIFEST.in` and
    update checks in `./bin/packahe.sh`.
    """

    samples = pkg_resources.resource_listdir(__name__,  # @UndefinedVariable
                                             internal_folder)
    if incl_regex:
        incl_regex = re.compile(incl_regex)
    return {f: lambda: pkg_resources.resource_stream(  # @UndefinedVariable
            __name__,
            os.path.join(internal_folder, f))
        for f in samples
        if not incl_regex or incl_regex.match(f)}


def _cmd_demo(opts):
    dst_folder = opts['<folder>']
    force = opts['--force']
    file_category = 'DEMO INPUT'
    file_stream_pairs = _get_internal_file_streams('demos', r'.*\.xlsx$')
    file_stream_pairs = sorted(file_stream_pairs.items())
    _generate_files_from_streams(dst_folder, file_stream_pairs,
                                 force, file_category)
    msg = "You may run DEMOS with:\n    co2mpas simulate -I %s"
    log.info(msg, dst_folder)


def _prompt_folder(folder_name, folder):
    import easygui as eu

    while folder and not os.path.isdir(folder):
        log.info('Cannot find %s folder: %r', folder_name, folder)
        folder = eu.diropenbox(msg='Select %s folder:' % folder_name,
                               title='%s-v%s' % (proj_name, proj_ver),
                               default=folder)
        if not folder:
            raise CmdException('User abort.')
    return folder


def _run_simulation(opts):
    input_folder = _prompt_folder(folder_name='INPUT', folder=opts['-I'])
    input_folder = os.path.abspath(input_folder)

    output_folder = _prompt_folder(folder_name='OUTPUT', folder=opts['-O'])
    output_folder = os.path.abspath(output_folder)

    log.info("Processing '%s' --> '%s'...", input_folder, output_folder)

    from co2mpas.functions import process_folder_files
    process_folder_files(input_folder, output_folder,
                         plot_workflow=opts['--plot-workflow'],
                         hide_warn_msgbox=opts['--no-warn-gui'],
                         extended_summary=opts['--more-output'])


def _main(*args):
    """Does not ``sys.exit()`` like :func:`main()` but throws any exception."""

    proj_file2 = os.path.dirname(proj_file)
    opts = docopt(__doc__,
                  argv=args or sys.argv[1:],
                  version='%s-%s at %s' % (proj_name, proj_ver, proj_file2))
    _init_logging(opts['--verbose'])

    if opts['template']:
        _cmd_template(opts)
    elif opts['demo']:
        _cmd_demo(opts)
    elif opts['ipynb']:
        _cmd_ipynb(opts)
    else:
        _run_simulation(opts)


def main(*args):
    try:
        _main(*args)
    except CmdException as ex:
        exit(ex.args[0])

if __name__ == '__main__':
    main()
