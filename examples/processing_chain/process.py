"""
Defines the file processing chain model.
"""

import pandas as pd
import schedula as sh
from model import model

process = sh.BlueDispatcher(name='Processing Model')


@sh.add_function(process, outputs=['raw_data'])
def read_excel(input_fpath):
    """
    Reads the excel file.

    :param input_fpath:
        Input file path.
    :type input_fpath: str

    :return:
        Raw Data.
    :rtype: dict
    """
    return {k: v.values for k, v in pd.read_excel(input_fpath).items()}


process.add_data(
    data_id='column_mapping', default_value={},
    description='Column renaming mapping.'
)

process.add_function(
    function_id='parse_data',
    function=sh.map_dict,
    inputs=['column_mapping', 'raw_data'],
    outputs=['data'],
    description='Rename the raw data names.'
)

process.add_function(
    function_id='compute_outputs',
    function=sh.SubDispatch(model),
    inputs=['data'],
    outputs=['outputs'],
    description='Executes the computational model.'
)


@sh.add_function(process)
def save_outputs(outputs, output_fpath):
    """
    Save model outputs in an Excel file.

    :param outputs:
        Model outputs.
    :type outputs: dict

    :param output_fpath:
        Output file path.
    :type output_fpath: str
    """
    df = pd.DataFrame(outputs)
    with pd.ExcelWriter(output_fpath) as writer:
        df.to_excel(writer)


if __name__ == '__main__':
    process.register().plot(index=True)
