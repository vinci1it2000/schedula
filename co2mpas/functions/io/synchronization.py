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


def synchronization(*data, x_id='times', y_id='velocities'):
    dx = np.median(np.diff(data[0][x_id])) / 2
    m, M = float('inf'), -float('inf')
    for d in data:
        m, M = min(d[x_id], m), max(d[x_id], M)

    X = range(m, M, step=dx)

    splines = []
    for d in data:
        s = {k: Spline(d[x_id], v, k=1) for k, v in d.items() if k != x_id}
        splines.append(s)

    Y = splines[0][y_id](X)

    shifts = (compute_shift(Y, s[y_id](X)) * dx for s in splines[1:])

    X = data[0][x_id]
    res = [data[0]]
    for s, dx in zip(splines[1:], shifts):
        d = {k: v(X) for k, v in s.items()}
        d[x_id] = X
        res.append(d)

    return res