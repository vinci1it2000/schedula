__author__ = 'Vincenzo Arcidiacono'

if __name__ == '__main__':

    from os import getcwd
    from tkinter.filedialog import askdirectory
    from tkinter import Tk

    root = Tk()
    root.withdraw()
    input_folder = askdirectory(title='Select input folder',
                                initialdir='%s/input'%(getcwd()),
                                parent=root)
    output_folder = askdirectory(title='Select output folder',
                                 initialdir='%s/output'%(getcwd()),
                                 parent=root)

    from compas.models.compas_model import process_folder_files

    process_folder_files(input_folder, output_folder)