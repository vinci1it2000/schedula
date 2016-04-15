#!/usr/bin/env python
#
# Copyright 2014-2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
r"""
Predict NEDC CO2 emissions from WLTP.

:Home:         http://co2mpas.io/
:Copyright:    2015-2016 European Commission (JRC-IET <https://ec.europa.eu/jrc/en/institutes/iet>
:License:       EUPL 1.1+ <https://joinup.ec.europa.eu/software/page/eupl>

Use the `batch` sub-command to simulate a vehicle contained in an excel-file.


USAGE:
  co2mpas batch       [-v | --logconf=<conf-file>] [--gui]
                      [--overwrite-cache]
                      [--out-template=<xlsx-file> | --charts]
                      [--plot-workflow]  [-O=<output-folder>]
                      [--only-summary]  [--soft-validation]
                      [<input-path>]...
  co2mpas demo        [-v | --logconf=<conf-file>] [--gui]
                      [-f] [<output-folder>]
  co2mpas template    [-v | --logconf=<conf-file>] [--gui] [-f] [<excel-file-path> ...]
  co2mpas ipynb       [-v | --logconf=<conf-file>] [--gui] [-f] [<output-folder>]
  co2mpas modelgraph  [-v | --logconf=<conf-file>] [-O=<output-folder>]
                      (--list | [--graph-depth=<levels>] [<models> ...])
  co2mpas sa          [-v | --logconf=<conf-file>] [-f] [-O=<output-folder>]
                      [--soft-validation] [--only-summary] [--overwrite-cache]
                      [--out-template=<xlsx-file> | --charts]
                      [<input-path>] [<input-params>] [<defaults>]...
  co2mpas             [--verbose | -v]  (--version | -V)
  co2mpas             --help

Syntax tip:
  The brackets `[ ]`, parens `( )`, pipes `|` and ellipsis `...` signify
  "optional", "required", "mutually exclusive", and "repeating elements";
  for more syntax-help see: http://docopt.org/


OPTIONS:
  <input-path>                Input xlsx-file or folder. Assumes current-dir if missing.
  -O=<output-folder>          Output folder or file [default: .].
  --gui                       Launches GUI dialog-boxes to choose Input, Output
                              and Options. [default: False].
  --only-summary              Do not save vehicle outputs, just the summary file.
  --overwrite-cache           Overwrite the cached file.
  --charts                    Add basic charts to output file.
  --soft-validation           Validate only partially input-data (no schema).
  --out-template=<xlsx-file>  Clone the given excel-file and appends model-results into it.
                              By default, results are appended into an empty excel-file.
                              Use `--out-template=-` to use input excel-files as templates.
  --plot-workflow             Open workflow-plot in browser, after run finished.
  -l, --list                  List available models.
  --graph-depth=<levels>      An integer to Limit the levels of sub-models plotted
                              (no limit by default).
  -f, --force                 Overwrite template/demo excel-file(s).

Miscellaneous:
  -h, --help                  Show this help message and exit.
  -V, --version               Print version of the program, with --verbose
                              list release-date and installation details.
  -v, --verbose               Print more verbosely messages - overridden by --logconf.
  --logconf=<conf-file>       Path to a logging-configuration file, according to:
                                https://docs.python.org/3/library/logging.config.html#configuration-file-format
                              If the file-extension is '.yaml' or '.yml', it reads a dict-schema from YAML:
                                https://docs.python.org/3.5/library/logging.config.html#logging-config-dictschema


SUB-COMMANDS:
    batch                   Simulate vehicle for all <input-path> excel-files & folder.
                            If no <input-path> given, reads all excel-files from current-dir.
                            Read this for explanations of the param names:
                              http://co2mpas.io/explanation.html#excel-input-data-naming-conventions
    demo                    Generate demo input-files for the `batch` cmd inside <output-folder>.
    template                Generate "empty" input-file for the `batch` cmd as <excel-file-path>.
    ipynb                   Generate IPython notebooks inside <output-folder>; view them with cmd:
                              jupyter --notebook-dir=<output-folder>
    modelgraph              List or plot available models. If no model(s) specified, all assumed.
    sa                      (undocumented - subject to change)


EXAMPLES::

    # Don't enter lines starting with `#`.

    # Create work folders and then fill `input` with sample-vehicles:
    md input output
    co2mpas  demo  input

    # Launch GUI dialog-boxes on the sample-vehicles just created:
    co2mpas  batch  --gui  input

    # or specify them with output-charts and workflow plots:
    co2mpas  batch  input  -O output  --charts  --plot-workflow

    # Create an empty vehicle-file inside `input` folder:
    co2mpas  template  input/vehicle_1.xlsx

    # View a specific submodel on your browser:
    co2mpas  modelgraph  co2mpas.model.physical.wheels.wheels

    # View full version specs:
    co2mpas -vV

"""

import glob
import io
import logging
import os
import re
import shutil
import sys
from collections import OrderedDict
from os import path as osp

import docopt
import yaml

from co2mpas import (__version__ as proj_ver, __file__ as proj_file,
                     __updated__ as proj_date)
from co2mpas import autocompletion


class CmdException(Exception):
    """Polite user-message avoiding ``exit(msg)`` when ``main()`` invoked from python."""
    pass

proj_name = 'co2mpas'

log = logging.getLogger(__name__)
logging.getLogger('pandalone.xleash.io').setLevel(logging.WARNING)


def init_logging(verbose, frmt=None, logconf_file=None):
    if logconf_file:
        if osp.splitext(logconf_file)[1] in '.yaml' or '.yml':
            with io.open(logconf_file) as fd:
                log_dict = yaml.safe_load(fd)
                logging.config.dictConfig(log_dict)
        else:
            logging.config.fileConfig(logconf_file)
    else:
        if verbose is None:
            level = logging.WARNING
        elif verbose:
            level = logging.DEBUG
        else: # Verbose: False
            level = logging.INFO
        if not frmt:
            frmt = "%(asctime)-15s:%(levelname)5.5s:%(name)s:%(message)s"
        logging.basicConfig(level=level, format=frmt)
    logging.captureWarnings(True)


def build_version_string(verbose):
    v = '%s-%s' % (proj_name, proj_ver)
    if verbose:
        v_infos = OrderedDict([
            ('co2mpas_version', proj_ver),
            ('co2mpas_rel_date', proj_date),
            ('co2mpas_path', osp.dirname(proj_file)),
            ('python_version', sys.version),
            ('python_path', sys.prefix),
            ('PATH', os.environ.get('PATH', None)),
        ])
        v = ''.join('%s: %s\n' % kv for kv in v_infos.items())
    return v


def print_autocompletions():
    """
    Prints the auto-completions list from docopt in stdout.

    .. Note::
        Must be registered as `setup.py` entry-point.
    """
    autocompletion.print_wordlist_from_docopt(__doc__)


def _cmd_modelgraph(opts):
    import co2mpas.plot as co2plot
    if opts['--list']:
        print('\n'.join(co2plot.get_model_paths()))
    else:
        depth = opts['--graph-depth']
        if depth:
            try:
                depth = int(depth)
                if depth < 0:
                    depth = None
            except:
                msg = "The '--graph-depth' must be an integer!  Not %r."
                raise CmdException(msg % depth)
        else:
            depth = None
        dot_graphs = co2plot.plot_model_graphs(opts['<models>'], depth=depth,
                                               output_folder=opts['-O'])
        if not dot_graphs:
            raise CmdException("No models plotted!")


def _generate_files_from_streams(
        dst_folder, file_stream_pairs, force, file_category):
    if not osp.exists(dst_folder):
        raise CmdException(
            "Destination folder '%s' does not exist!" % dst_folder)
    if not osp.isdir(dst_folder):
        raise CmdException(
            "Destination '%s' is not a <output-folder>!" % dst_folder)

    for src_fname, stream in file_stream_pairs:
        dst_fpath = osp.join(dst_folder, src_fname)
        if osp.exists(dst_fpath) and not force:
            msg = "Creating %s file '%s' skipped, already exists! \n  " \
                  "Use '-f' to overwrite it."
            log.info(msg, file_category, dst_fpath)
        else:
            log.info("Creating %s file '%s'...", file_category, dst_fpath)
            with open(dst_fpath, 'wb') as fd:
                shutil.copyfileobj(stream, fd, 16 * 1024)


def _cmd_demo(opts):
    dst_folder = opts.get('<output-folder>', None)
    is_gui = opts['--gui']
    if is_gui and not dst_folder:
        import easygui as eu
        msg=("Select folder to store INPUT-DEMO files:"
                "\n(existing ones will be overwritten)")
        dst_folder = eu.diropenbox(msg=msg,
                                   title='%s-v%s' % (proj_name, proj_ver),
                                   default=os.environ.get('HOME', '.'))
        if not dst_folder:
            raise CmdException('User abort creating INPUT-DEMO files.')
    elif not dst_folder:
        raise CmdException('Missing destination folder for INPUT-DEMO files!')

    force = opts['--force'] or is_gui
    file_category = 'INPUT-DEMO'
    file_stream_pairs = _get_internal_file_streams('demos', r'.*\.xlsx$')
    file_stream_pairs = sorted(file_stream_pairs.items())
    _generate_files_from_streams(dst_folder, file_stream_pairs,
                                 force, file_category)
    msg = "You may run DEMOS with:\n    co2mpas batch %s"
    log.info(msg, dst_folder)


def _cmd_ipynb(opts):
    dst_folder = opts.get('<output-folder>', None)
    is_gui = opts['--gui']
    if is_gui and not dst_folder:
        import easygui as eu
        msg=("Select folder to store IPYTHON NOTEBOOKS:"
                "\n(existing ones will be overwritten)")
        dst_folder = eu.diropenbox(msg=msg,
                                   title='%s-v%s' % (proj_name, proj_ver),
                                   default=os.environ.get('HOME', '.'))
        if not dst_folder:
            raise CmdException('User abort creating IPYTHON NOTEBOOKS.')
    elif not dst_folder:
        raise CmdException('Missing destination folder for IPYTHON NOTEBOOKS!')

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
    is_gui = opts['--gui']
    if is_gui and not dst_fpaths:
        import easygui as eu
        fpath = eu.filesavebox(msg='Create INPUT-TEMPLATE file as:',
                              title='%s-v%s' % (proj_name, proj_ver),
                              default='co2mpas_template.xlsx')
        if not fpath:
            raise CmdException('User abort creating INPUT-TEMPLATE file.')
        dst_fpaths = [fpath]
    elif not dst_fpaths:
        raise CmdException('Missing destination filepath for INPUT-TEMPLATE!')

    force = opts['--force']
    for fpath in dst_fpaths:
        if not fpath.endswith('.xlsx'):
            fpath = '%s.xlsx' % fpath
        if osp.exists(fpath) and not force and not is_gui:
            raise CmdException(
                "Writing file '%s' skipped, already exists! "
                "Use '-f' to overwrite it." % fpath)
        if osp.isdir(fpath):
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
            osp.join(internal_folder, f))
            for f in samples
            if not incl_regex or incl_regex.match(f)}


def _prompt_folder(folder_name, fpath):
    while not fpath or not (os.path.isfile(fpath) or os.path.isdir(fpath)):
        log.info('Cannot find %s folder/file: %r', folder_name, fpath)
        import easygui as eu
        fpath = eu.diropenbox(msg='Select %s folder:' % folder_name,
                              title='%s-v%s' % (proj_name, proj_ver),
                              default=fpath)
        if not fpath:
            raise CmdException('User abort.')
    return fpath


def _prompt_options():
    import easygui as eu
    fields = ['overwrite-cache', 'soft-validation', 'plot-workflow',
              'only-summary', 'out-template', 'charts']
    choices = ['y/[n]', 'y/[n]', 'y/[n]', 'y/[n]', 'y/[n]/<xlsx-file>', 'y/[n]']
    for values in iter(lambda: eu.multenterbox(
            msg='Select BATCH-run options:',
            title='%s-v%s' % (proj_name, proj_ver),
            fields=fields, values=choices),
            None):
        opts = {}
        for (f, c, v) in zip(fields, choices, values):
            if v and v != c:
                o = '--%s' % f
                vl = v.lower()
                if f == 'out-template':
                    if vl == 'y':
                        opts[o] = '-'
                    elif vl == 'n':
                        opts[o] = False
                    elif not vl.endswith('.xlsx'):
                        eu.msgbox('The file %r has not .xlsx extension!'% v)
                        break
                    elif not osp.isfile(v):
                        eu.msgbox('The xl-file %r does not exist!' % v)
                        break
                    else:
                        opts[o] = v
                elif vl == 'y':
                    opts[o] = True
                elif vl == 'n':
                    opts[o] = False
                else: # Invalid content
                    break
        else:
            return opts
    raise CmdException('User abort.')


_input_file_regex = re.compile('^\w')


def file_finder(xlsx_fpaths, file_ext='*.xlsx'):
    files = set()
    for f in xlsx_fpaths:
        if osp.isfile(f):
            files.add(f)
        elif osp.isdir(f):
            files.update(glob.glob(osp.join(f, file_ext)))

    return [f for f in sorted(files) if _input_file_regex.match(osp.basename(f))]


def _cmd_sa(opts):
    input_path = opts['<input-path>']
    defaults = opts['<defaults>']
    out_folder = opts['-O']
    force = opts['--force']
    input_params = opts['<input-params>']
    input_paths = file_finder(input_path)

    if not input_paths:
        raise CmdException("No <input-path> found! \n"
                           "\n  Try: co2mpas --help")

    if not osp.isdir(out_folder):
        if force:
            from co2mpas.dispatcher.utils.io import mkdirs
            if not ''.endswith('/'):
                out_folder = '%s/' % out_folder
            mkdirs(out_folder)
        else:
            raise CmdException("Specify a folder for "
                               "the '-O %s' option!" % out_folder)

    from co2mpas.sensitivity import run_sa
    run_sa(input_path, input_params, out_folder, *defaults,
           soft_validation=opts['--soft-validation'],
           with_output_file=not opts['--only-summary'],
           with_charts=opts['--charts'],
           output_template_xl_fpath=opts['--out-template'],
           overwrite_cache=opts['--overwrite-cache']
           )


def _run_batch(opts):
    input_paths = opts['<input-path>']
    output_folder = opts['-O']
    if opts['--gui']:
        input_paths = [
            _prompt_folder(folder_name='INPUT',
                           fpath=input_paths[-1] if input_paths else None)
        ]
        output_folder = _prompt_folder(folder_name='OUTPUT', fpath=output_folder)
        opts.update(_prompt_options())

    log.info("Processing %r --> %r...", input_paths, output_folder)
    input_paths = file_finder(input_paths)
    if not input_paths:
        raise CmdException("No <input-path> found! \n"
                "\n  Try: co2mpas batch <fpath-1>..."
                "\n  or : co2mpas --gui"
                "\n  or : co2mpas --help")

    if not osp.isdir(output_folder):
        if opts['--force']:
            from co2mpas.dispatcher.utils.io import mkdirs
            if not ''.endswith('/'):
                output_folder = '%s/' % output_folder
            mkdirs(output_folder)
        else:
            raise CmdException("Specify a folder for "
                               "the '-O %s' option!" % output_folder)

    from co2mpas.batch import process_folder_files
    process_folder_files(input_paths, output_folder,
                         with_output_file=not opts['--only-summary'],
                         plot_workflow=opts['--plot-workflow'],
                         with_charts=opts['--charts'],
                         output_template_xl_fpath=opts['--out-template'],
                         overwrite_cache=opts['--overwrite-cache'],
                         soft_validation=opts['--soft-validation'])


def _main(*args):
    """Does not ``sys.exit()`` like :func:`main()` but throws any exception."""

    opts = docopt.docopt(__doc__, argv=args or sys.argv[1:])

    verbose = opts.get('--verbose', False)
    init_logging(verbose, logconf_file=opts.get('--logconf'))
    if opts['--version']:
        v = build_version_string(verbose)
        try:
            sys.stdout.buffer.write(v.encode() + b'\n')
        except:
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
        elif opts['sa']:
            _cmd_sa(opts)
        else: #opts['batch']:
            _run_batch(opts)


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
