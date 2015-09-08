#-*- coding: utf-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains functions to plot cycle time series.

.. note:: these functions are used in :mod:`compas.functions.write_outputs`.
"""


from itertools import product
import matplotlib.pyplot as plt

linestyles = ('-', '--', '-.', ':')
colors = ('b', 'r', 'g', 'c', 'm', 'y', 'k')
markers = ('', 'o', 's', '+', 'x', '*', '.', '<', '>', 'v', '^', '_')


def _get_styles():
    for m, l, c in product(markers, linestyles, colors):
        yield {'linestyle': l, 'color': c, 'marker': m}


def _plot_series(time, series, ax=None, x_label=None, y_label=None):
    styles = _get_styles()
    if ax is None:
        import matplotlib.pyplot as plt
        fig = plt.figure()
        ax = fig.add_subplot(111)

    for l, v in sorted(series.items()):
        ax.plot(time, v, label=l, **next(styles))

    ax.legend(loc=8, ncol=8, mode='expand')
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)


def plot_gear_box_speeds(series):
    """
    Plots the time series for velocity, gear, gear box speed, and engine speed.

    :param series:
        Vehicle time series:

            - Time [s]
            - Velocity [km/h]
            - Gears [-]
            - Gears with ... [-]
            - Engine speed [rpm]
            - Gear box speeds with ... [rpm]

    :type series: pandas.DataFrame

    :return:
        A figure.
    :rtype: plt.Figure
    """

    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, True, figsize=(32, 20))

    g = {'Velocity [km/h]': series['Velocity [km/h]']}
    _plot_series(series['Time [s]'], g, ax=ax1,
                 x_label='Time [s]', y_label='Velocity [km/h]')

    g = {k.replace('Gears with ', ''): v
         for k, v in series.items()
         if 'Gears' in k}
    _plot_series(series['Time [s]'], g, ax=ax2,
                 x_label='Time [s]', y_label='Gear [-]')

    g, e = {}, {}
    for k, v in series.items():
        if 'Gearbox speeds engine side [RPM] with' in k:
            g[k.replace('Gearbox speeds engine side [RPM] with ', '')] = v
        elif 'Engine speed' in k:
            e[k] = v

    g1 = {}
    g1.update(e)
    for i in range(int((len(g) - 1) / 2) + 1):
        k, v = g.popitem()
        g1[k] = v
    g.update(e)

    _plot_series(series['Time [s]'], g, ax=ax3,
                 x_label='Time [s]', y_label='Gearbox speed [rpm]')

    _plot_series(series['Time [s]'], g1, ax=ax4,
                 x_label='Time [s]', y_label='Gearbox speed [rpm]')

    return fig