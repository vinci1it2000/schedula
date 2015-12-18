#!/usr/bin/env python
#
# Copyright 2014-2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
"""
Predict NEDC CO2 emissions from WLTP cycles.

Usage:
    co2mpas [simulate] [-v] [--predict-wltp] [--report-stages] [--no-warn-gui]
                       [--plot-workflow] [--only-summary] [--out-template <fpath>]
                       [-I <fpath>] [-O <fpath>]
    co2mpas demo       [-v] [-f] [<folder>]
    co2mpas template   [-v] [-f] [<excel-file-path> ...]
    co2mpas ipynb      [-v] [-f] [<folder>]
    co2mpas modelgraph [-v] --list
    co2mpas modelgraph [-v] [--depth=INTEGER] [<models> ...]
    co2mpas [-v] --version
    co2mpas --help

-I <fpath>              Input folder or file, prompted with GUI if missing [default: ./input]
-O <fpath>              Input folder or file, prompted with GUI if missing [default: ./output]
-l, --list              List available models.
--only-summary          Does not save vehicle outputs just the summary file.
--predict-wltp          Whether to predict also WLTP values.
--report-stages         Add report-sheets with stage-scores into summary file.
--no-warn-gui           Does not pause batch-run to report inconsistencies.
--out-template <fpath>  A '*.xlsx' file to clone and append vehicle-results into it.
                        By default, the input xlsx-file is used as output-template.
                        To create "fresh" output xl-files, set '0' as <fpath>.
--plot-workflow         Open workflow-plot in browser, after run finished.
--depth=INTEGER         Limit the number of sub-dispatchers plotted (no limit by default).
-f, --force             Overwrite template/demo excel-file(s).
-v, --verbose           Print more verbosely messages.

* Items enclosed in `[]` are optional.


Sub-commands:
    simulate    [default] Run simulation for all excel-files in input-folder (-I).
    demo        Generate demo input-files inside <folder>.
    template    Generate "empty" input-file at <excel-file-path>.
    ipynb       Generate IPython notebooks inside <folder>; view them with cmd:
                  ipython --notebook-dir=<folder>
    modelgraph  List all or plot available models.  If no model(s) specified, all assumed.

Examples:

    # Create sample-vehicles inside the `input` folder.
    # (the `input` folder must exist)
    co2mpas demo input

    # Run the sample-vehicles just created.
    # (the `output` folder must exist)
    co2mpas -I input -O output

    # Create an empty vehicle-file inside `input` folder.
    co2mpas template input/vehicle_1.xlsx

    # View a specific submodel on your browser.
    co2mpas modelgraph gear_box_calibration

"""
from co2mpas import (__version__ as proj_ver, __file__ as proj_file,
                     __updated__ as proj_date)
from collections import OrderedDict
import logging
import os
import re
import shutil
import sys

from docopt import docopt


class CmdException(Exception):
    """Polite user-message avoiding ``exit(msg)`` when ``main()`` invoked from python."""
    pass

proj_name = 'co2mpas'

log = logging.getLogger(__name__)


def init_logging(verbose):
    if verbose is None:
        level = logging.WARNING
    elif verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO
    frmt = "%(asctime)-15s:%(levelname)5.5s:%(name)s:%(message)s"
    logging.basicConfig(level=level, format=frmt)


def build_version_string(verbose):
    v = '%s-%s' % (proj_name, proj_ver)
    if verbose:
        v_infos = OrderedDict([
            ('co2mpas_version', proj_ver),
            ('co2mpas_rel_date', proj_date),
            ('co2mpas_path', os.path.dirname(proj_file)),
            ('python_version', sys.version),
            ('python_path', sys.prefix),
            ('PATH', os.environ.get('PATH', None)),
        ])
        v = ''.join('%s: %s\n' % kv for kv in v_infos.items())
    return v


def _cmd_modelgraph(opts):
    from co2mpas.functions import plot as co2plot
    if opts['--list']:
        print('\n'.join(co2plot.get_model_paths()))
    else:
        depth = opts['--depth']
        if depth:
            try:
                depth = int(depth)
            except:
                msg = "The '--depth' must be an integer!  Not %r."
                raise CmdException(msg % depth)
        else:
            depth = None
        dot_graphs = co2plot.plot_model_graphs(opts['<models>'], depth=depth)
        if not dot_graphs:
            raise CmdException("No models plotted!")


def _generate_files_from_streams(
        dst_folder, file_stream_pairs, force, file_category):
    if not os.path.exists(dst_folder):
        raise CmdException(
            "Destination folder '%s' does not exist!" % dst_folder)
    if not os.path.isdir(dst_folder):
        raise CmdException(
            "Destination '%s' is not a <folder>!" % dst_folder)

    for src_fname, stream in file_stream_pairs:
        dst_fpath = os.path.join(dst_folder, src_fname)
        if os.path.exists(dst_fpath) and not force:
            msg = "Creating %s file '%s' skipped, already exists! \n  " \
                  "Use '-f' to overwrite it."
            log.info(msg, file_category, dst_fpath)
        else:
            log.info("Creating %s file '%s'...", file_category, dst_fpath)
            with open(dst_fpath, 'wb') as fd:
                shutil.copyfileobj(stream, fd, 16 * 1024)


def _cmd_ipynb(opts):
    dst_folder = opts.get('<folder>', None)
    is_gui = not dst_folder
    if is_gui:
        import easygui as eu
        msg=("Select folder to store IPYTHON NOTEBOOKS:"
                "\n(existing ones will be overwritten)")
        dst_folder = eu.diropenbox(msg=msg,
                                   title='%s-v%s' % (proj_name, proj_ver),
                                   default=os.environ.get('HOME', '.'))
        if not dst_folder:
            raise CmdException('User abort creating IPYTHON NOTEBOOKS.')

    force = opts['--force'] or is_gui
    file_category = 'IPYTHON NOTEBOOK'
    file_stream_pairs = _get_internal_file_streams('ipynbs', r'.*\.ipynb$')
    file_stream_pairs = sorted(file_stream_pairs.items())
    _generate_files_from_streams(dst_folder, file_stream_pairs,
                                 force, file_category)


def _get_input_template_fpath():
    import pkg_resources

    fname = 'co2mpas_template.xlsx'
    return pkg_resources.resource_stream(__name__, fname)  # @UndefinedVariable


def _cmd_template(opts):
    dst_fpaths = opts.get('<excel-file-path>', None)
    is_gui = not dst_fpaths
    if is_gui:
        import easygui as eu
        fpath = eu.filesavebox(msg='Create INPUT-TEMPLATE file as:',
                              title='%s-v%s' % (proj_name, proj_ver),
                              default='co2mpas_template.xlsx')
        if not fpath:
            raise CmdException('User abort creating INPUT-TEMPLATE file.')
        dst_fpaths = [fpath]

    force = opts['--force']
    for fpath in dst_fpaths:
        if not fpath.endswith('.xlsx'):
            fpath = '%s.xlsx' % fpath
        if os.path.exists(fpath) and not force and not is_gui:
            raise CmdException(
                "Writing file '%s' skipped, already exists! "
                "Use '-f' to overwrite it." % fpath)
        if os.path.isdir(fpath):
            raise CmdException(
                "Expecting a file-name instead of directory '%s'!" % fpath)

        log.info("Creating INPUT-TEMPLATE file '%s'...", fpath)
        stream = _get_input_template_fpath()
        with open(fpath, 'wb') as fd:
            shutil.copyfileobj(stream, fd, 16 * 1024)


def _get_internal_file_streams(internal_folder, incl_regex=None):
    """
    :return: a mappings of {filename--> stream-gen-function}.

    REMEMBER: Add internal-files also in `setup.py` & `MANIFEST.in` and
    update checks in `./bin/package.sh`.
    """
    import pkg_resources

    samples = pkg_resources.resource_listdir(__name__,  # @UndefinedVariable
                                             internal_folder)
    if incl_regex:
        incl_regex = re.compile(incl_regex)
    return {f: pkg_resources.resource_stream(  # @UndefinedVariable
            __name__,
            os.path.join(internal_folder, f))
            for f in samples
            if not incl_regex or incl_regex.match(f)}


def _cmd_demo(opts):
    dst_folder = opts.get('<folder>', None)
    is_gui = not dst_folder
    if is_gui:
        import easygui as eu
        msg=("Select folder to store INPUT-DEMO files:"
                "\n(existing ones will be overwritten)")
        dst_folder = eu.diropenbox(msg=msg,
                                   title='%s-v%s' % (proj_name, proj_ver),
                                   default=os.environ.get('HOME', '.'))
        if not dst_folder:
            raise CmdException('User abort creating INPUT-DEMO files.')

    force = opts['--force'] or is_gui
    file_category = 'INPUT-DEMO'
    file_stream_pairs = _get_internal_file_streams('demos', r'.*\.xlsx$')
    file_stream_pairs = sorted(file_stream_pairs.items())
    _generate_files_from_streams(dst_folder, file_stream_pairs,
                                 force, file_category)
    msg = "You may run DEMOS with:\n    co2mpas simulate -I %s"
    log.info(msg, dst_folder)


def _prompt_folder(folder_name, fpath):
    while fpath and not (os.path.isfile(fpath) or os.path.isdir(fpath)):
        log.info('Cannot find %s folder/file: %r', folder_name, fpath)
        import easygui as eu
        fpath = eu.diropenbox(msg='Select %s folder:' % folder_name,
                              title='%s-v%s' % (proj_name, proj_ver),
                              default=fpath)
        if not fpath:
            raise CmdException('User abort.')
    return fpath


def _run_batch(opts):
    input_folder = _prompt_folder(folder_name='INPUT', fpath=opts['-I'])

    output_folder = _prompt_folder(folder_name='OUTPUT', fpath=opts['-O'])

    log.info("Processing '%s' --> '%s'...", input_folder, output_folder)

    from co2mpas.functions import process_folder_files
    process_folder_files(input_folder, output_folder,
                         with_output_file=not opts['--only-summary'],
                         plot_workflow=opts['--plot-workflow'],
                         hide_warn_msgbox=opts['--no-warn-gui'],
                         extended_summary=opts['--report-stages'],
                         enable_prediction_WLTP=opts['--predict-wltp'],
                         output_template_xl_fpath=opts['--out-template']),


def _main(*args):
    """Does not ``sys.exit()`` like :func:`main()` but throws any exception."""

    opts = docopt(__doc__,
                  argv=args or sys.argv[1:])

    verbose = opts['--verbose']
    init_logging(verbose)
    if opts['--version']:
        v = build_version_string(verbose)
        print(v)
    else:
        if opts['template']:
            _cmd_template(opts)
        elif opts['demo']:
            _cmd_demo(opts)
        elif opts['ipynb']:
            _cmd_ipynb(opts)
        elif opts['modelgraph']:
            _cmd_modelgraph(opts)
        elif opts['simulate']:
            _run_batch(opts)
        else:
            _run_batch(opts)


def main(*args):
    try:
        _main(*args)
    except CmdException as ex:
        exit(ex.args[0])

if __name__ == '__main__':
    if sys.version_info < (3, 4):
        msg = "Sorry, Python >= 3.4 is required, but found: {}"
        sys.exit(msg.format(sys.version_info))
    main()
