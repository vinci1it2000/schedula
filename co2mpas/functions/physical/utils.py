#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains classes and functions of general utility.

These are python-specific utilities and hacks - general data-processing or
numerical operations.
"""


import sys
import math
from statistics import median_high
from collections import OrderedDict
import co2mpas.dispatcher.utils as dsp_utl
import numpy as np
from scipy.interpolate import InterpolatedUnivariateSpline

try:
    isidentifier = str.isidentifier
except AttributeError:
    import re

    isidentifier = re.compile(r'[a-z_]\w*$', re.I).match

__all__ = [
    'grouper', 'sliding_window', 'median_filter', 'reject_outliers',
    'bin_split', 'interpolate_cloud', 'clear_fluctuations', 'argmax'
]


def argmax(values, **kws):
    return np.argmax(np.append(values, [True]), **kws)


def grouper(iterable, n):
    """Collect data into fixed-length chunks or blocks"""
    args = [iter(iterable)] * n
    return zip(*args)


def sliding_window(xy, dx_window):
    "Returns a sliding window (of width dx) over data from the iterable"
    dx = dx_window / 2
    it = iter(xy)
    v = next(it)
    window = []

    for x, y in xy:
        # window limits
        x_dn = x - dx
        x_up = x + dx

        # remove samples
        window = [w for w in window if w[0] >= x_dn]

        # add samples
        while v and v[0] <= x_up:
            window.append(v)
            try:
                v = next(it)
            except StopIteration:
                v = None

        yield window


def median_filter(x, y, dx_window, filter=median_high):
    """
    Calculates the moving median-high of y values over a constant dx.

    :param x:
        x data.
    :type x: Iterable

    :param y:
        y data.
    :type y: Iterable

    :param dx_window:
        dx window.
    :type dx_window: float

    :return:
        Moving median-high of y values over a constant dx.
    :rtype: numpy.array
    """

    xy = [list(v) for v in zip(x, y)]
    Y = []
    add = Y.append
    for v in sliding_window(xy, dx_window):
        add(filter(list(zip(*v))[1]))
    return np.array(Y)


def reject_outliers(x, n=1, med=np.median, std=np.std):
    """
    Calculates the median and standard deviation of the sample rejecting the
    outliers.

    :param x:
        Input data.
    :type x: Iterable

    :param n:
        Number of standard deviations.
    :type n: int

    :param med:
        Median function.
    :type med: function, optional

    :param std:
        Standard deviation function.
    :type std: function, optional

    :return:
        Median and standard deviation.
    :rtype: (float, float)
    """

    x = np.asarray(x)
    if not x.any():
        return np.nan, np.nan
    m, s = med(x), std(x)

    y = n > (abs(x - m) / s)

    if y.any():
        y = x[y]

        m, s = med(y), std(y)

    return m, s


def bin_split(x, bin_std=(0.01, 0.1), n_min=None, bins_min=None):
    """
    Splits the input data with variable bins.

    :param x:
        Input data.
    :type x: Iterable

    :param bin_std:
        Bin standard deviation limits.
    :type bin_std: (float, float)

    :param n_min:
        Minimum number of data inside a bin [-].
    :type n_min: int

    :param bins_min:
        Minimum number of bins [-].
    :type bins_min: int

    :return:
        Bins and their statistics.
    :rtype: (list, list)
    """

    x = np.asarray(x)
    edges = [min(x), max(x) + sys.float_info.epsilon * 2]

    max_bin_size = edges[1] - edges[0]
    min_bin_size = max_bin_size / len(x)
    if n_min is None:
        n_min = math.sqrt(len(x))

    if bins_min is not None:
        max_bin_size /= bins_min
    bin_stats = []

    def _bin_split(x, m, std, x_min, x_max):
        bin_size = x_max - x_min
        n = len(x)

        y0 = x[x < m]
        y1 = x[m <= x]
        m_y0, std_y0 = _stats(y0)
        m_y1, std_y1 = _stats(y1)

        if any(
                [bin_size > max_bin_size,
                 all([std > bin_std[1],
                      x_min < m < x_max,
                      bin_size > min_bin_size,
                      n > n_min,
                      (m_y1 - m_y0) / bin_size > 0.2
                 ])
                ]) and (std_y0 > bin_std[0] or std_y1 > bin_std[0]):

            edges.append(m)
            _bin_split(y0, m_y0, std_y0, x_min, m)
            _bin_split(y1, m_y1, std_y1, m, x_max)

        else:
            bin_stats.append([np.median(x), std / n, std, m, n])

    def _stats(x):
        m = np.mean(x)
        std = abs(np.std(x) / m)
        return [m, std]

    _bin_split(x, *(_stats(x) + edges))

    edges = sorted(edges)

    bin_stats = sorted(bin_stats)

    def _bin_merge(x, edges, bin_stats):
        bins = OrderedDict(enumerate(zip(dsp_utl.pairwise(edges), bin_stats)))
        new_edges = [edges[0]]
        new_bin_stats = []

        for k0 in range(len(bins) - 1):
            v0, v1 = (bins[k0], bins[k0 + 1])
            e_min, e_max = (v0[0][0], v1[0][1])
            if (v1[1][0] - v0[1][0]) / (e_max - e_min) <= 0.33:
                y = x[(e_min <= x) & (x < e_max)]
                m, std = _stats(y)
                if std < bin_std[1]:
                    n = v0[1][3] + v1[1][3]
                    bins[k0 + 1] = (
                        (e_min, e_max), [np.median(y), std / n, std, m, n])
                    del bins[k0]

        for e, s in bins.values():
            new_edges.append(e[1])
            if s[2] < bin_std[1]:
                s[2] *= s[3]
                new_bin_stats.append(s[1:] + [s[0]])

        new_bin_stats = sorted(new_bin_stats)
        return new_edges, new_bin_stats

    return _bin_merge(x, edges, bin_stats)


def interpolate_cloud(x, y):
    """
    Defines a function that interpolate a cloud of points.

    :param x:
        x data.
    :type x: Iterable

    :param y:
        y data.
    :type y: Iterable

    :return:
        A function that interpolate a cloud of points.
    :rtype: InterpolatedUnivariateSpline
    """

    p = np.asarray(x)
    v = np.asarray(y)

    edges, s = bin_split(p, bin_std=(0, 10))

    if len(s) > 2:
        x, y = ([0.0], [None])

        for e0, e1 in dsp_utl.pairwise(edges):
            b = (e0 <= p) & (p < e1)
            x.append(np.mean(p[b]))
            y.append(np.mean(v[b]))

        y[0] = y[1]
        x.append(x[-1])
        y.append(y[-1] * 1.1)
    else:
        x, y = ([0, 1], [np.mean(y)] * 2)

    return InterpolatedUnivariateSpline(x, y, k=1)


def clear_fluctuations(times, gears, dt_window):
    """
    Clears the gear identification fluctuations.

    :param times:
        Time vector.
    :type times: numpy.array

    :param gears:
        Gear vector.
    :type gears: numpy.array

    :param dt_window:
        Time window.
    :type dt_window: float

    :return:
        Gear vector corrected from fluctuations.
    :rtype: numpy.array
    """

    xy = [list(v) for v in zip(times, gears)]

    for samples in sliding_window(xy, dt_window):

        up, dn = (None, None)

        x, y = zip(*samples)

        for k, d in enumerate(np.diff(y)):
            if d > 0:
                up = (k,)
            elif d < 0:
                dn = (k,)

            if up and dn:
                k0 = min(up[0], dn[0])
                k1 = max(up[0], dn[0]) + 1

                m = median_high(y[k0:k1])

                for i in range(k0 + 1, k1):
                    samples[i][1] = m

                up, dn = (None, None)

    return np.array([y[1] for y in xy])
