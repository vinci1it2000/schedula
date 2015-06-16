__author__ = 'Vincenzo Arcidiacono'

from itertools import product


linestyles = ('-', '--', '-.', ':')
colors = ('b', 'r', 'g', 'c', 'm', 'y', 'k')
markers = ('', 'o', 's', '+', 'x', '*', '.', '<', '>', 'v', '^', '_')


def get_styles():
    for m, l, c in product(markers, linestyles, colors):
        yield {'linestyle': l, 'color': c, 'marker': m}


def plot_series(time, series, ax=None, x_label=None, y_label=None):
    styles = get_styles()
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
    import matplotlib.pyplot as plt
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, True, figsize=(32, 20))

    g = {'Velocity [km/h]': series['Velocity [km/h]']}
    plot_series(series['Time [s]'], g, ax=ax1,
                x_label='Time [s]', y_label='Velocity [km/h]')

    g = {k.replace('Gears with ', ''): v
         for k, v in series.items()
         if 'Gears' in k}
    plot_series(series['Time [s]'], g, ax=ax2,
                x_label='Time [s]', y_label='Gear [-]')

    g = {k.replace('Gear box speeds with ', ''): v
         for k, v in series.items()
         if 'Gear box speed' in k or 'Engine speed' in k}
    plot_series(series['Time [s]'], g, ax=ax3,
                x_label='Time [s]', y_label='Gear box speed [rpm]')

    return fig