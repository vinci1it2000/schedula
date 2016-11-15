# -*- coding: utf-8 -*-
# !/usr/bin/env python
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
  co2mpas gui         [-v | -q | --logconf=<conf-file>]
  co2mpas ta          [-f] [-O=<output-folder>] [<input-path>]...
  co2mpas batch       [-v | -q | --logconf=<conf-file>] [-f]
                      [--overwrite-cache] [-O=<output-folder>]
                      [--modelconf=<yaml-file>]
                      [-D=<key=value>]... [<input-path>]...
  co2mpas demo        [-v | -q | --logconf=<conf-file>] [-f]
                      [<output-folder>]
  co2mpas template    [-v | -q | --logconf=<conf-file>] [-f]
                      [<excel-file-path> ...]
  co2mpas ipynb       [-v | -q | --logconf=<conf-file>] [-f] [<output-folder>]
  co2mpas modelgraph  [-v | -q | --logconf=<conf-file>] [-O=<output-folder>]
                      [--modelconf=<yaml-file>]
                      (--list | [--graph-depth=<levels>] [<models> ...])
  co2mpas modelconf   [-v | -q | --logconf=<conf-file>] [-f]
                      [--modelconf=<yaml-file>] [-O=<output-folder>]
  co2mpas             [-v | -q | --logconf=<conf-file>] (--version | -V)
  co2mpas             --help

Syntax tip:
  The brackets `[ ]`, parens `( )`, pipes `|` and ellipsis `...` signify
  "optional", "required", "mutually exclusive", and "repeating elements";
  for more syntax-help see: http://docopt.org/


OPTIONS:
  <input-path>                Input xlsx-file or folder. Assumes current-dir if missing.
  -O=<output-folder>          Output folder or file [default: .].
  <excel-file-path>           Output file.
  --modelconf=<yaml-file>     Path to a model-configuration file, according to YAML:
                                https://docs.python.org/3.5/library/logging.config.html#logging-config-dictschema
  --overwrite-cache           Overwrite the cached input file.
  --override, -D=<key=value>  Input data overrides (e.g., `-D fuel_type=diesel`,
                              `-D prediction.nedc_h.vehicle_mass=1000`).
  -l, --list                  List available models.
  --graph-depth=<levels>      An integer to Limit the levels of sub-models plotted.
  -f, --force                 Overwrite output/template/demo excel-file(s).


Model flags (-D flag.xxx, example -D flag.engineering_mode=True):
 engineering_mode=<bool>     Use all data and not only the declaration data.
 soft_validation=<bool>      Relax some Input-data validations, to facilitate experimentation.
 run_base=<bool>             If True and the input file is a plan, the
                             simulation plan will not be launched, but the file
                             will be executed as a normal file with base inputs.
 use_selector=<bool>         Select internally the best model to predict both NEDC H/L cycles.
 only_summary=<bool>         Do not save vehicle outputs, just the summary.
 plot_workflow=<bool>        Open workflow-plot in browser, after run finished.
 output_template=<xlsx-file> Clone the given excel-file and appends results into
                             it. By default, results are appended into an empty
                             excel-file. Use `output_template=-` to use
                             input-file as template.

Miscellaneous:
  -h, --help                  Show this help message and exit.
  -V, --version               Print version of the program, with --verbose
                              list release-date and installation details.
  -v, --verbose               Print more verbosely messages - overridden by --logconf.
  -q, --quite                 Print less verbosely messages (warnings) - overridden by --logconf.
  --logconf=<conf-file>       Path to a logging-configuration file, according to:
                                https://docs.python.org/3/library/logging.config.html#configuration-file-format
                              If the file-extension is '.yaml' or '.yml', it reads a dict-schema from YAML:
                                https://docs.python.org/3.5/library/logging.config.html#logging-config-dictschema


SUB-COMMANDS:
    gui             Launches co2mpas GUI.
    ta              Simulate vehicle in type approval mode for all <input-path>
                    excel-files & folder. If no <input-path> given, reads all
                    excel-files from current-dir. It reads just the declaration
                    inputs, if it finds some extra input will raise a warning
                    and will not produce any result.
                    Read this for explanations of the param names:
                      http://co2mpas.io/explanation.html#excel-input-data-naming-conventions
    batch           Simulate vehicle in scientific mode for all <input-path>
                    excel-files & folder. If no <input-path> given, reads all
                    excel-files from current-dir. By default reads just the
                    declaration inputs and skip the extra inputs. Thus, it will
                    produce always a result. To read all inputs the flag
                    `engineering_mode` have to be set to True.
                    Read this for explanations of the param names:
                      http://co2mpas.io/explanation.html#excel-input-data-naming-conventions
    demo            Generate demo input-files for the `batch` cmd inside <output-folder>.
    template        Generate "empty" input-file for the `batch` cmd as <excel-file-path>.
    ipynb           Generate IPython notebooks inside <output-folder>; view them with cmd:
                      jupyter --notebook-dir=<output-folder>
    modelgraph      List or plot available models. If no model(s) specified, all assumed.
    modelconf       Save a copy of all model defaults in yaml format.


EXAMPLES::

    # Don't enter lines starting with `#`.

    # View full version specs:
    co2mpas -vV

    # Create an empty vehicle-file inside `input` folder:
    co2mpas  template  input/vehicle_1.xlsx

    # Create work folders and then fill `input` with sample-vehicles:
    md input output
    co2mpas  demo  input

    # View a specific submodel on your browser:
    co2mpas  modelgraph  co2mpas.model.physical.wheels.wheels

    # Run co2mpas with batch cmd plotting the workflow:
    co2mpas  batch  input  -O output  -D flag.plot_workflow=True

    # Run co2mpas with ta cmd:
    co2mpas  batch  input/co2mpas_demo-0.xlsx  -O output

    # or launch the co2mpas GUI:
    co2mpas  gui

    # View all model defaults in yaml format:
    co2maps modelconf -O output
"""

from co2mpas import (__version__ as proj_ver, __file__ as proj_file,
                     __updated__ as proj_date)
import collections
import glob
import io
import logging
import os.path as osp
import os
import re
import shutil
import sys
import docopt
import yaml
import warnings


class CmdException(Exception):
    """Polite user-message avoiding ``exit(msg)`` when ``main()`` invoked from python."""
    pass

proj_name = 'co2mpas'

log = logging.getLogger('co2mpas_main')
logging.getLogger('pandalone.xleash.io').setLevel(logging.WARNING)
warnings.filterwarnings(
    action="ignore", module="scipy", message="^internal gelsd"
)

warnings.filterwarnings(
    action="ignore", module="openpyxl", message="^Unknown extension"
)


def _set_numpy_logging():
    rlog = logging.getLogger()
    if not rlog.isEnabledFor(logging.DEBUG):
        import numpy as np
        np.seterr(divide='ignore', invalid='ignore')


def init_logging(level=None, frmt=None, logconf_file=None):
    if logconf_file:
        if osp.splitext(logconf_file)[1] in '.yaml' or '.yml':
            with io.open(logconf_file) as fd:
                log_dict = yaml.safe_load(fd)
                logging.config.dictConfig(log_dict)
        else:
            logging.config.fileConfig(logconf_file)
    else:
        if level is None:
            level = logging.INFO
        if not frmt:
            frmt = "%(asctime)-15s:%(levelname)5.5s:%(name)s:%(message)s"
        logging.basicConfig(level=level, format=frmt)
        rlog = logging.getLogger()
        rlog.level = level  # because `basicConfig()` does not reconfig root-logger when re-invoked.

    _set_numpy_logging()

    logging.captureWarnings(True)


def build_version_string(verbose):
    v = '%s-%s' % (proj_name, proj_ver)
    if verbose:
        v_infos = collections.OrderedDict([
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
    from . import docoptutils
    docoptutils.print_wordlist_from_docopt(__doc__)


def _cmd_modelgraph(opts):
    import co2mpas.plot as co2plot
    _init_defaults(opts['--modelconf'])
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
        if force:
            os.makedirs(dst_folder)
        else:
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
    if not dst_folder:
        raise CmdException('Missing destination folder for INPUT-DEMO files!')

    force = opts['--force']
    file_category = 'INPUT-DEMO'
    file_stream_pairs = _get_internal_file_streams('demos', r'.*\.xlsx$')
    file_stream_pairs = sorted(file_stream_pairs.items())
    _generate_files_from_streams(dst_folder, file_stream_pairs,
                                 force, file_category)
    msg = "You may run DEMOS with:\n    co2mpas batch %s"
    log.info(msg, dst_folder)


def _cmd_ipynb(opts):
    dst_folder = opts.get('<output-folder>', None)
    if not dst_folder:
        raise CmdException('Missing destination folder for IPYTHON NOTEBOOKS!')

    force = opts['--force']
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
    if not dst_fpaths:
        raise CmdException('Missing destination filepath for INPUT-TEMPLATE!')

    save_template(dst_fpaths, opts['--force'])


def save_template(dst_fpaths, force):
    for fpath in dst_fpaths:
        if not fpath.endswith('.xlsx'):
            fpath = '%s.xlsx' % fpath
        if osp.exists(fpath) and not force:
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
    return {f: pkg_resources.resource_stream(# @UndefinedVariable
            __name__,
            osp.join(internal_folder, f))
            for f in samples
            if not incl_regex or incl_regex.match(f)}


_input_file_regex = re.compile('^\w')


def file_finder(xlsx_fpaths, file_ext='*.xlsx'):
    files = set()
    for f in xlsx_fpaths:
        if osp.isfile(f):
            files.add(f)
        elif osp.isdir(f):
            files.update(glob.glob(osp.join(f, file_ext)))

    return [f for f in sorted(files) if _input_file_regex.match(osp.basename(f))]


_re_override = re.compile(r"^\s*([^=]+)\s*=\s*(.*?)\s*$")


def parse_overrides(override, option_name='--override'):
    res = {}
    for ov in override:
        m = _re_override.match(ov)
        if not m:
            raise CmdException('Wrong %s format %r! ' % (option_name, ov))

        k, v = m.groups()
        if k in res:
            raise CmdException('Duplicated %s key %r!' % (option_name, k))
        res[k] = v

    return res


def _init_defaults(modelconf):
    from co2mpas.conf import defaults
    if modelconf:
        try:
            defaults.load(modelconf)
        except FileNotFoundError:
            msg = "--modelconf: No such file or directory: %s."
            raise CmdException(msg % modelconf)
    return defaults


def _run_batch(opts, **kwargs):
    input_paths = opts['<input-path>'] or ['.']
    output_folder = opts['-O']
    log.info("Processing %r --> %r...", input_paths, output_folder)
    input_paths = file_finder(input_paths)
    if not input_paths:
        raise CmdException("No <input-path> found! \n"
                "\n  Try: co2mpas batch <fpath-1>..."
                "\n  or : co2mpas gui"
                "\n  or : co2mpas --help")

    if not osp.isdir(output_folder):
        if opts['--force']:
            from graphviz.tools import mkdirs
            if not ''.endswith('/'):
                output_folder = '%s/' % output_folder
            mkdirs(output_folder)
        else:
            raise CmdException("Specify a folder for "
                               "the '-O %s' option!" % output_folder)

    _init_defaults(opts['--modelconf'])

    kw = {
        'variation': parse_overrides(opts['--override']),
        'overwrite_cache': opts['--overwrite-cache'],
        'modelconf': opts['--modelconf']
    }
    kw.update(kwargs)

    from co2mpas.batch import process_folder_files
    process_folder_files(input_paths, output_folder, **kw)


def _cmd_modelconf(opts):
    output_folder = opts['-O']
    if not osp.isdir(output_folder):
        if opts['--force']:
            from graphviz.tools import mkdirs
            if not ''.endswith('/'):
                output_folder = '%s/' % output_folder
            mkdirs(output_folder)
        else:
            raise CmdException("Specify a folder for "
                               "the '-O %s' option!" % output_folder)
    import datetime
    fname = datetime.datetime.now().strftime('%Y%m%d_%H%M%S-conf.yaml')
    fname = osp.join(output_folder, fname)
    defaults = _init_defaults(opts['--modelconf'])
    defaults.dump(fname)
    log.info('Default model config written into yaml-file(%s)...', fname)


def _cmd_gui(opts):
    from co2mpas import tkui
    tkui.main()


def _main(*args):
    """Does not ``sys.exit()`` like :func:`main()` but throws any exception."""

    opts = docopt.docopt(__doc__, argv=args or sys.argv[1:])

    verbose = opts['--verbose']
    quiet = opts['--quite']
    assert not (verbose and quiet), "Specify one of `verbose` and `quiet` as true!"
    level = None  # Let `init_logging()` decide.
    if verbose:
        level = logging.DEBUG
    if quiet:
        level = logging.WARNING
    init_logging(level=level, logconf_file=opts.get('--logconf'))

    if opts['--version']:
        v = build_version_string(verbose)
        # noinspection PyBroadException
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
        elif opts['modelconf']:
            _cmd_modelconf(opts)
        elif opts['gui']:
            _cmd_gui(opts)
        elif opts['ta']:
            _run_batch(opts, type_approval_mode=True, overwrite_cache=True)
        else:
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
    if sys.version_info < (3, 5):
        sys.exit("Sorry, Python >= 3.5 is required,"
                 " but found: {}".format(sys.version_info))
    main()
