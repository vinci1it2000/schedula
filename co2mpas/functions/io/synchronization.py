import numpy as np
from numpy.fft import fft, ifft, fftshift
from scipy.interpolate import InterpolatedUnivariateSpline as Spline


def cross_correlation_using_fft(x, y):
    f1 = fft(x)
    f2 = fft(np.flipud(y))
    cc = np.real(ifft(f1 * f2))
    return fftshift(cc)


# shift &lt; 0 means that y starts 'shift' time steps before x # shift &gt; 0 means that y starts 'shift' time steps after x
def compute_shift(x, y):
    assert len(x) == len(y)
    c = cross_correlation_using_fft(x, y)
    assert len(c) == len(x)
    zero_index = int(len(x) / 2) - 1
    shift = zero_index - np.argmax(c)
    return shift


def synchronization(reference, *data, x_id='times', y_id='velocities'):
    """
    Returns the data re-sampled and synchronized respect to x axes (`x_id`) and
    the reference signal `y_id`.

    :param reference:

    :type reference: dict

    :param data:

    :type data: list[dict]

    :param x_id:
    :type x_id: str, optional

    :param y_id:
    :type y_id: str, optional

    :return:
    :rtype: list[dict]
    """

    dx = np.median(np.diff(reference[x_id])) / 10
    m, M = min(reference[x_id]), max(reference[x_id])
    for d in data:
        m, M = min(min(d[x_id]), m), max(max(d[x_id]), M)

    X = np.linspace(m, M, int((M - m) / dx))

    splines = []
    for d in data:
        s = {k: Spline(d[x_id], v, k=1, ext=3) for k, v in d.items() if k != x_id}
        splines.append(s)

    Y = Spline(reference[x_id], reference[y_id], k=1, ext=3)(X)

    shifts = [compute_shift(Y, s[y_id](X)) * dx for s in splines]

    X = reference[x_id]
    res = []
    for s, dx in zip(splines, shifts):
        d = {k: v(X + dx) for k, v in s.items()}
        d[x_id] = X
        res.append(d)

    return res
