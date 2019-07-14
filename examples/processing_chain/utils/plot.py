"""
Defines the utility functions to plot the time series.
"""


def define_plot_data(data, x_name, *y_names):
    """
    Defines the data to be plotted.

    :param data:
        All data.
    :type data: dict

    :param x_name:
        x-axes name.
    :type x_name: str

    :param y_names:
        y-axes names to be plotted.
    :type y_names: str

    :return:
        Data to be plotted.
    :rtype: list
    """
    it = []
    for k in y_names:
        it.append(dict(
            x=data[x_name],
            y=data[k],
            name=k,
            mode='lines'
        ))
    return it
