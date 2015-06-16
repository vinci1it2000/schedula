__author__ = 'Vincenzo Arcidiacono'

import sys
import math
from itertools import tee
from heapq import heappush
from statistics import median_high
from collections import OrderedDict

import numpy as np
from scipy.interpolate import InterpolatedUnivariateSpline

from compas.dispatcher.utils import heap_flush


def pairwise(iterable, n=2):
    """s -> (s0,s1), (s1,s2), (s2, s3), ..."""
    a = tee(iterable)
    next(a[1], None)
    for i in range(n - 2):
        b = tee(a[-1])[1]
        next(b, None)
        a += (b, )

    return zip(*a)


def grouper(iterable, n):
    """Collect data into fixed-length chunks or blocks"""
    args = [iter(iterable)] * n
    return zip(*args)


def sliding_window(xy, dx_window):
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


def median_filter(x, y, dx_window):
    xy = [list(v) for v in zip(x, y)]
    Y = []
    add = Y.append
    for v in sliding_window(xy, dx_window):
        add(median_high(list(zip(*v))[1]))
    return np.array(Y)


def reject_outliers(x, n=1):

    x = np.asarray(x)

    m, s = np.median(x), np.std(x)

    y = n > (abs(x - m) / s)

    if y.any():
        y = x[y]

        m, s = np.median(y), np.std(y)

    return m, s


def bin_split(x, bin_std=(0.01, 0.1), n_min=None, bins_min=None):
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

            heappush(edges, m)
            _bin_split(y0, m_y0, std_y0, x_min, m)
            _bin_split(y1, m_y1, std_y1, m, x_max)

        else:
            heappush(bin_stats, [np.median(x), std / n, std, m, n])

    def _stats(x):
        m = np.mean(x)
        std = np.std(x) / m
        return [m, std]

    _bin_split(x, *(_stats(x) + edges))

    edges = heap_flush(edges)

    bin_stats = heap_flush(bin_stats)

    def _bin_merge(x, edges, bin_stats):
        bins = OrderedDict(enumerate(zip(pairwise(edges), bin_stats)))
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
                heappush(new_bin_stats, s[1:] + [s[0]])

        new_bin_stats = heap_flush(new_bin_stats)
        return new_edges, new_bin_stats

    return _bin_merge(x, edges, bin_stats)

def interpolate_cloud(x, y):
    p = np.asarray(x)
    v = np.asarray(y)

    edges, s = bin_split(p, bin_std=(0, 10))

    if len(s) > 2:
        x, y = ([0.0], [None])

        for e0, e1 in pairwise(edges):
            b = (e0 <= p) & (p < e1)
            x.append(np.mean(p[b]))
            y.append(np.mean(v[b]))

        y[0] = y[1]
        x.append(x[-1] + 1)
        y.append(y[-1])
    else:
        x, y = ([0, 1], [np.mean(y)] * 2)

    return InterpolatedUnivariateSpline(x, y, k=1)