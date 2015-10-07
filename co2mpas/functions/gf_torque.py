

from itertools import repeat

import numpy as np
from sklearn.metrics import mean_squared_error
from scipy.optimize import fmin

from co2mpas.functions.physical.gear_box import identify_gears, VEL_EPS
from co2mpas.functions.physical.utils import median_filter


# deprecated
def correction_function(rpm, coeff):
    c, rpm_idle = coeff
    # noinspection PyTypeChecker
    return 1 - np.exp(-c * (rpm - rpm_idle))


# deprecated
def eng_speed2gb_speed_error_fun(args_corr_fun, svr_get, rpm, vel, gear, time,
                                 temp=None):
    it = zip(rpm, repeat(args_corr_fun))

    rpm_gb0 = rpm * list(map(correction_function, it))

    rpm_gb = vel * list(map(svr_get, gear))

    # noinspection PyUnresolvedReferences
    ratio = rpm_gb / rpm

    t = (0 <= vel) & (vel < 45) & (0 <= ratio) & (ratio < 1.05)

    if temp is None:
        t &= 50 < time
    else:
        t &= ((50 < temp) | (50 < time))

    return mean_squared_error(rpm_gb[t], rpm_gb0[t]) if t.any() else 0


# deprecated
def eng_speed2gb_speed(speed2velocity_ratios, time, vel, acc, speed_eng,
                       temp=None):
    svr = speed2velocity_ratios

    svr_get = svr.get

    if temp is None:
        def set_args(*a, ids=None):
            if ids is not None:
                return (svr_get, ) + tuple(v[ids] for v in a)
            else:
                return (svr_get, ) + a
    else:
        def set_args(*a, ids=None):
            p = a + (temp, )
            if ids is not None:
                p = tuple(v[ids] for v in p)
            return (svr_get, ) + p

    gear_eng = identify_gears(time, vel, acc, speed_eng, svr)

    args = set_args(speed_eng, vel, gear_eng, time)

    c_av = list(fmin(eng_speed2gb_speed_error_fun, [0.001, 700], args=args))

    coeff_cf = {'av': c_av}

    for i in range(max(gear_eng) + 1):
        coeff_cf[i] = c_av

        if i in gear_eng:
            args = set_args(speed_eng, vel, gear_eng, time, ids=gear_eng == i)

            res = list(fmin(eng_speed2gb_speed_error_fun, c_av, args=args))

            if all(abs((res[j] - c_av[j]) / c_av[j]) <= 1 for j in [0, 1]):
                coeff_cf[i] = res

    coeff = list(map(coeff_cf.get, gear_eng))
    ratio = np.vectorize(correction_function)(speed_eng, coeff)
    ratio[ratio < 0] = 0
    ratio[ratio > 1.05] = 1

    return coeff_cf, median_filter(time, speed_eng * ratio, 4)


def fun(engine_speeds, gear_box_speeds, times, velocities, accelerations,
        idle_engine_speed,
        time_shift_engine_speeds):
    ratio = gear_box_speeds / engine_speeds

    ratio[accelerations < -0.1] = 1 / ratio[accelerations < -0.1]

    b = (velocities > VEL_EPS) & (times > 100) & (0 <= ratio) & (ratio < 1.05)

