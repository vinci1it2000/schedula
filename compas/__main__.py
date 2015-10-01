"""
Predict NEDC CO2 emissions from WLTP cycles.

Usage:
    co2mpas [options] [-I <folder>]  [-O <folder>]
    co2mpas example [-f | --force] <folder>
    co2mpas template [-f | --force] <excel-file> ...
    co2mpas --help
    co2mpas --version

-I <folder>             Input folder, prompted with GUI if missing.
                        [default: ./input]
-O <folder>             Input folder, prompted with GUI if missing.
                        [default: ./output]
--more-output           Output also per-vehicle output-files.
--no-warn-gui           Does not pause batch-run to report inconsistencies.
--plot-workflow         Show workflow in browser, after run finished.
-f --force              Overwrite template/sample excel-file(s).

* Items enclosed in `[]` are optional.

Examples:

    ## Create sample-vehicles inside the `input` folder.
    ## (the `input` folder must exist)
    co2mpas example input

    ## Run the sample-vehicles just created.
    ## (the `output` folder must exist)
    co2mpas -I input -O output

    ## Create an empty vehicle-file inside `input` folder.
    co2mpas template input/vehicle_1.xlsx

"""
import sys
import os
import shutil
import pkg_resources
from docopt import docopt

from compas import __version__ as proj_ver, __file__ as proj_file


proj_name = 'co2mpas'


def _get_input_template_fpath():
    return pkg_resources.resource_filename(__name__,  # @UndefinedVariable
                                           'co2mpas_template.xlsx')


def _create_input_template(opts):
    dst_fpaths = opts['<excel-file>']
    force = opts['--force']
    for fpath in dst_fpaths:
        fpath = os.path.abspath(fpath)
        if not fpath.endswith('.xlsx'):
            fpath = '%s.xlsx' % fpath
        if os.path.exists(fpath) and not force:
            exit("File '%s' already exists! Use '-f' to overwrite it." % fpath)
        if os.path.isdir(fpath):
            exit("Expecting a file-name instead of directory '%s'!" % fpath)

        print("Creating co2mpas TEMPLATE input-file '%s'..." % fpath,
              file=sys.stderr)
        shutil.copy(_get_input_template_fpath(), fpath)


def _get_sample_files():
    samples = pkg_resources.resource_listdir(__name__,  # @UndefinedVariable
                                             'samples')
    return [pkg_resources.resource_filename(__name__,  # @UndefinedVariable
                                            os.path.join('samples', f))
            for f in samples]


def _copy_sample_files(opts):
    dst_folder = opts['<folder>']
    force = opts['--force']
    dst_folder = os.path.abspath(dst_folder)
    if not os.path.exists(dst_folder):
        exit("Destination folder '%s' does not exist!" % dst_folder)
    if not os.path.isdir(dst_folder):
        exit("Destination '%s' is not a <folder>!" % dst_folder)

    for src_fpath in _get_sample_files():
        dst_fpath = os.path.join(dst_folder, os.path.basename(src_fpath))
        if os.path.exists(dst_fpath) and not force:
            print("Skipping file '%s', already exists! Use '-f' to overwrite it." %
                 dst_fpath, file=sys.stderr)
        else:
            print("Creating co2mpas EXAMPLE input-file '%s'..." % dst_fpath,
                  file=sys.stderr)
            shutil.copy(src_fpath, dst_fpath)


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
    input_folder = _prompt_folder(folder_name='INPUT', folder=opts['-I'])
    input_folder = os.path.abspath(input_folder)

    output_folder = _prompt_folder(folder_name='OUTPUT', folder=opts['-O'])
    output_folder = os.path.abspath(output_folder)

    print("Processing '%s' --> '%s'..." %
          (input_folder, output_folder), file=sys.stderr)

    from compas.functions import process_folder_files
    process_folder_files(input_folder, output_folder,
                         plot_workflow=opts['--plot-workflow'],
                         hide_warn_msgbox=opts['--no-warn-gui'],
                         gen_outfiles_per_vehicle=opts['--more-output'])


def main(*args):
    proj_file2 = os.path.dirname(proj_file)
    opts = docopt(__doc__,
                  argv=args or sys.argv[1:],
                  version='%s %s at %s' % (proj_name, proj_ver, proj_file2))
    if opts['template']:
        _create_input_template(opts)
    elif opts['example']:
        _copy_sample_files(opts)
    else:
        _run_simulation(opts)

if __name__ == '__main__':
    main()
