"""
Predict NEDC CO2 emissions from WLTP cycles.

Usage:
    co2mpas [options] [-I <folder>  -O <folder>]
    co2mpas template [-f | --force] <excel-file> ...
    co2mpas --help
    co2mpas --version

-I <folder> --inp <folder>       Input folder, prompted with GUI if missing.
                                 [default: ./input]
-O <folder> --out <folder>       Input folder, prompted with GUI if missing.
                                 [default: ./output]
--more-output                    Output also per-vehicle output-files.
--no-warn-gui                    Does not pause batch-run to report inconsistencies.
--plot-workflow                  Show workflow in browser, after run finished.
-f --force                       Overwrite template excel-file if it exists.
"""
# [-f | --force]
# -f --force                       Create template even if file already exists.
import sys
import os
import shutil
import pkg_resources
from docopt import docopt

from compas import __version__ as proj_ver


proj_name = 'co2mpas'


def _get_input_template_fpath():
    return pkg_resources.resource_filename(__name__,  # @UndefinedVariable
                                           'input_template.xlsx')


def _create_input_template(fpaths, force=False):
    for fpath in fpaths:
        fpath = os.path.abspath(fpath)
        if not fpath.endswith('.xlsx'):
            fpath = '%s.xlsx' % fpath
        if os.path.exists(fpath) and not force:
            exit("File '%s' already exists! Use '-f' to overwrite it." % fpath)
        if os.path.isdir(fpath):
            exit("Expecting a file-name instead of directory '%s'!" % fpath)

        print("Creating co2mpas INPUT template-file '%s'..." % fpath,
              file=sys.stderr)
        shutil.copy(_get_input_template_fpath(), fpath)


def _prompt_folder(folder_name, folder):
    import easygui as eu

    while folder and not os.path.isdir(folder):
        print('Cannot find %s folder: %r' % (folder_name, folder),
              file=sys.stderr)
        folder = eu.diropenbox(msg='Select %s folder' % folder_name,
                               title=proj_name,
                               default=folder)
        if not folder:
            exit('User abort.')
    return folder


def _run_simulation(opts):
    input_folder = _prompt_folder(folder_name='INPUT', folder=opts['--inp'])
    input_folder = os.path.abspath(input_folder)

    output_folder = _prompt_folder(folder_name='OUTPUT', folder=opts['--out'])
    output_folder = os.path.abspath(output_folder)

    print("Processing '%s' --> '%s'..." %
          (input_folder, output_folder), file=sys.stderr)

    from compas.functions import process_folder_files
    process_folder_files(input_folder, output_folder,
                         plot_workflow=opts['--plot-workflow'],
                         hide_warn_msgbox=opts['--no-warn-gui'],
                         gen_outfiles_per_vehicle=opts['--more-output'])


def main(*args):
    opts = docopt(__doc__,
                  argv=args or sys.argv[1:],
                  version='%s %s' % (proj_name, proj_ver))
    if opts['template']:
        _create_input_template(opts['<excel-file>'], opts['--force'])
    else:
        _run_simulation(opts)

if __name__ == '__main__':
    main()
