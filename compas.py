__author__ = 'Vincenzo Arcidiacono'

import sys
from os import getcwd

def main(*args):

    if len(args) == 1:
        from tkinter.filedialog import askdirectory
        from tkinter import Tk

        root = Tk()
        #root.withdraw()
        input_folder = askdirectory(title='Select input folder',
                                    initialdir='%s/input'%(getcwd()),
                                    parent=root)
        if not input_folder:
            exit()
        output_folder = askdirectory(title='Select output folder',
                                     initialdir='%s/output'%(getcwd()),
                                     parent=root)
        if not output_folder:
            exit()

    elif len(args) == 3:
        input_folder, output_folder = args[1:]

    else:
        print("%s [input_folder  output_folder]" % args[0])

    if not (input_folder and output_folder):
        print('ERROR: missing input and/or output folder')
    else:
        from compas.models.compas import process_folder_files

        process_folder_files(input_folder, output_folder)

    root.destroy()

if __name__ == '__main__':
    main(*sys.argv)
