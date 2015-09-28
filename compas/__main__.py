import sys
import os


def main(*args):
    args = list(args)
    prog_name = args.pop()

    input_folder = 'input'
    output_folder = 'output'

    if args:
        input_folder = args.pop()
    if args:
        output_folder = args.pop()
    if args:
        print("Syntax: %s [input_folder  output_folder]" % args[0])
        exit(-1)

    if not os.path.isdir(input_folder):
        import easygui as eu

        input_folder = eu.diropenbox(msg='Select input folder',
                                     title='GearTool',
                                     default=input_folder)
        if not input_folder:
            exit()

    if not os.path.isdir(output_folder):
        import easygui as eu

        output_folder = eu.diropenbox(msg='Select output folder',
                                      title='GearTool',
                                      default=output_folder)
        if not output_folder:
            exit()

    from compas.functions import process_folder_files

    process_folder_files(input_folder, output_folder)


if __name__ == '__main__':
    main(*sys.argv)
