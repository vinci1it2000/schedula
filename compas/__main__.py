"""
Predict NEDC CO2 emissions from WLTP cycles.

Usage:
    co2mpas [options] [-I <folder>  -O <folder]
    co2mpas --help
    co2mpas --version

-I <folder> --inp <folder>     Input folder, prompted with GUI if missing.
                               [default: ./input]
-O <folder> --out <folder>     Input folder, prompted with GUI if missing.
                               [default: ./output]
--plot-workflow                Show workflow in browser, after run finished.

"""
import sys
import os
from docopt import docopt

from compas import __version__ as proj_ver


proj_name = 'co2mpas'


def _prompt_folder(folder_name, folder):
    import easygui as eu

    while folder and not os.path.isdir(folder):
        print('Cannot find %s folder: %r' % (folder_name, folder),
              file=sys.stderr)
        folder = eu.diropenbox(msg='Select %s folder' % folder_name,
                               title=proj_name,
                               default=folder)
        if not folder:
            exit('User abort.', file=sys.stderr)
    return folder


def main(*args):
    opts = docopt(__doc__,
                  argv=args or sys.argv[1:],
                  version='%s %s' % (proj_name, proj_ver))

    input_folder = _prompt_folder(folder_name='INPUT', folder=opts['--inp'])
    input_folder = os.path.abspath(input_folder)

    output_folder = _prompt_folder(folder_name='OUTPUT', folder=opts['--out'])
    output_folder = os.path.abspath(output_folder)

    print("Processing '%s' --> '%s'..." %
          (input_folder, output_folder), file=sys.stderr)

    from compas.functions import process_folder_files
    process_folder_files(input_folder, output_folder,
            plot_workflow=opts['--plot-workflow'])


if __name__ == '__main__':
    main()
