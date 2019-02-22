"""
Defines the utility functions to plot the time series.
"""

import plotly.offline as py
import plotly.graph_objs as go


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
        it.append({
            'x': data[x_name],
            'y': data[k],
            'name': k
        })
    return it


def plot_lines(it):
    """
    Plotting lines.

    :param it:
        Data to plot where key value is the name of the series.
    :type it: list[dict]

    :return:
        The plot.
    :rtype: plotly.plotly.iplot
    """
    data = [go.Scatter(mode='lines', **d) for d in it]
    return py.iplot(data, filename='scatter-mode')
