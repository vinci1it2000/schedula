import numpy as np
from functools import partial
from scipy.integrate import trapz
from scipy.optimize import brute, minimize, differential_evolution, fmin, basinhopping, fmin_powell

from sklearn.metrics import mean_absolute_error, mean_squared_error
from compas.dispatcher.utils import pairwise
from compas.functions.physical.utils import reject_outliers


def calculate_normalized_engine_speeds_out(engine_speeds_out, engine_stroke):

    return (engine_stroke / 30000) * engine_speeds_out  # [m/sec]


def calculate_normalized_engine_temperatures(
        engine_temperatures, temperature_target):

    T = (engine_temperatures + 273) / (temperature_target + 273)

    T[T > 1] = 1

    return T


def calculate_normalized_engine_powers_out(
        engine_speeds_out, engine_powers_out, engine_capacity):

    p = (1200000 / engine_capacity) * engine_powers_out / engine_speeds_out

    return np.nan_to_num(p)  # BMEP [bar]


def _ABC(params, n_speeds, n_powers, n_temperatures):

    p = params

    B = p['a'] + (p['b'] + p['c'] * n_speeds) * n_speeds
    C = np.power(n_temperatures, -p['t']) * (p['l'] + p['l2'] * n_speeds**2)
    C -= n_powers

    if p['a2'] == 0 and p['b2'] == 0:
        return -C / B, B

    A_2 = (p['a2'] + p['b2'] * n_speeds)

    v = np.sqrt(np.abs(B**2 - 2 * A_2 * C))

    return (-B + v) / A_2, v


def calculate_fuel_consumptions(
        engine_speeds_out, engine_powers_out, normalized_engine_speeds_out,
        normalized_engine_powers_out, engine_temperatures,
        engine_fuel_lower_heating_value, idle_engine_speed, engine_stroke,
        engine_capacity,engine_idle_fuel_consumtion, params):
    p = {'a': 0.0, 'b': 0.0, 'c': 0.0, 'a2': 0.0, 'b2': 0.0, 'l': 0.0, 'l2': 0.0, 't': 3.0, 'trg': 88.0}
    n_speeds = normalized_engine_speeds_out
    n_powers = normalized_engine_powers_out
    lhv = engine_fuel_lower_heating_value
    p.update(params)
    n_temperatures = calculate_normalized_engine_temperatures(engine_temperatures, p['trg'])

    ABC = partial(_ABC, p)

    fc = ABC(n_speeds, n_powers, n_temperatures)[0]  # FMEP [bar]

    fc *= engine_speeds_out * (engine_capacity / (lhv * 1200))  # [g/sec]

    engine_cm_idle = idle_engine_speed[0] * engine_stroke / 30000

    engine_wfb_idle, engine_wfa_idle = ABC(engine_cm_idle, 0, 1)
    engine_wfa_idle = (3600000 / lhv) / engine_wfa_idle
    engine_wfb_idle *= (3 * engine_capacity / lhv * idle_engine_speed[0])

    ec_P0 = -engine_wfb_idle / engine_wfa_idle

    #fc[engine_speeds_out < idle_engine_speed[0] + 50] = engine_idle_fuel_consumtion

    fc[(engine_powers_out <= ec_P0) | (engine_speeds_out == 0) | (fc < 0)] = 0
    return np.nan_to_num(fc)  # [g/sec]


def calculate_cumulative_fuels(
        times, fuel_integration_times, engine_fuel_consumptions):

    fuels = []

    for t0, t1 in pairwise(fuel_integration_times):
        b = (t0 <= times) & (times < t1)
        fuels.append(trapz(engine_fuel_consumptions[b], times[b]))

    return np.array(fuels)


def identify_target_engine_temperature(engine_temperatures):
    """
    Identifies target engine temperature [°C].

    :param engine_temperatures:
        Engine temperature vector [°C].
    :type engine_temperatures: np.array

    :return:
        target engine temperature [°C].
    :rtype: float
    """

    m, s = reject_outliers(engine_temperatures, n=2)
    s = max(s, 10.0)
    return m - s * 2, max(engine_temperatures)


def calibrate_fuel_consumption_model(
        times, fuel_integration_times, velocities, engine_speeds_out,
        engine_powers_out, normalized_engine_speeds_out,
        normalized_engine_powers_out, engine_temperatures,
        engine_fuel_lower_heating_value, idle_engine_speed, engine_stroke,
        engine_capacity, engine_idle_fuel_consumtion, fuel_consumptions):

    fuel = partial(
        calculate_fuel_consumptions, engine_speeds_out, engine_powers_out,
        normalized_engine_speeds_out, normalized_engine_powers_out,
        engine_temperatures, engine_fuel_lower_heating_value,
        idle_engine_speed, engine_stroke, engine_capacity, engine_idle_fuel_consumtion
    )

    integral = partial(
        calculate_cumulative_fuels, times, fuel_integration_times
    )

    step = 3

    params_values_limits = {
        'a': (0.346548, 0.54315, step),
        'b': (-0.00247, 0.054688, step),
        'c': (-0.00138, 0.0000888, step),
        'a2': (-0.00663 * 2, 0.000064 * 2, step),
        #'b2': (0, 0, step),
        'l': (-3.27698, -0.82022, step),
        'l2': (-0.01852, 0.0, step),
        #'t': (3, 3, step),
        'tgr': identify_target_engine_temperature(engine_temperatures) + (step, ),
    }
    param_keys, params_bounds = zip(*params_values_limits.items())
    params_ranges = tuple([(i, j) for i, j, k in params_bounds])

    params_bounds = [(i - k, j + k) for i, j, k in ((i, j, (j - i) / float(k) * 2.0)for i, j, k in params_bounds)]

    params ={}

    #dist = integral(velocities) / 3600

    goal = integral(fuel_consumptions)

    def update_params(params_values):
        try:
            params.update({k: v for k, v in zip(param_keys, params_values)})
        except TypeError:
            params.update({k: v for k, v in zip(param_keys, [params_values])})


    w = np.array([6, 4, 5, 3])**3
    m = [np.inf, None]

    def error_func(params_values):
        update_params(params_values)

        fc = integral(fuel(params))
        res = mean_squared_error(goal, fc, w)
        if res < m[0]:
            m[1] = params_values.copy()
        return res


    def finish_minimization(fun, x0, args=(), full_output=0, disp=False):
        res = minimize(fun, x0, bounds=params_bounds)

        if res.status:
            return res.x

        return m[1]

    update_params(brute(error_func, params_ranges, finish=finish_minimization, Ns=step))

    return params, fuel(params)

if __name__ == '__main__':

    import os
    import pandas as pd
    from glob import glob
    import matplotlib.pyplot as plt

    fpaths = glob('/Users/iMac2013/Dropbox/vinz/Gear Tool/input_to_power/*.xlsx')

    error_coeff = []

    for fpath in fpaths:
        fname = os.path.basename(fpath)
        fname = fname.split('.')[0]

        print('Processing: %s' % fname)
        file = pd.ExcelFile(fpath)
        WLTP = file.parse(sheetname='WLTP')
        NEDC = file.parse(sheetname='NEDC')
        Input = file.parse(sheetname='Input', header=None, parse_cols='A:B', index_col=0)[1]

        n_s = calculate_normalized_engine_speeds_out(WLTP['rpm'].values, Input['engine stroke'])
        n_p = calculate_normalized_engine_powers_out(
            WLTP['rpm'].values, WLTP['power'].values, Input['engine capacity']
        )

        p, fc = calibrate_fuel_consumption_model(
            WLTP['time'].values, eval(Input['fuel integration times']),
            WLTP['velocity'].values, WLTP['rpm'].values, WLTP['power'].values,
            n_s, n_p, WLTP['temperature'].values, Input['engine fuel lhv'],
            (Input['engine rpm idle'], 0), Input['engine stroke'],
            Input['engine capacity'], Input['engine fuel consum idle'], WLTP['fuel consumption'].values
        )
        plt.figure()
        plt.subplot(2,1,1)
        plt.title(fname)
        plt.plot(WLTP['time'].values, WLTP['fuel consumption'].values, 'r-')
        plt.plot(WLTP['time'].values, fc, 'b-')

        print(p)
        dist = calculate_cumulative_fuels(WLTP['time'].values, eval(Input['fuel integration times']), WLTP['velocity'].values) / 3600
        print('dist', dist)

        print(mean_absolute_error(WLTP['fuel consumption'].values, fc))
        print((calculate_cumulative_fuels(WLTP['time'].values, eval(Input['fuel integration times']), WLTP['fuel consumption'].values) -
        calculate_cumulative_fuels(WLTP['time'].values, eval(Input['fuel integration times']), fc))/ dist
        )
        print(mean_absolute_error(calculate_cumulative_fuels(WLTP['time'].values, eval(Input['fuel integration times']), WLTP['fuel consumption'].values) / dist,
        calculate_cumulative_fuels(WLTP['time'].values, eval(Input['fuel integration times']), fc)/ dist
        ))
        dist = calculate_cumulative_fuels(WLTP['time'].values, (0, WLTP['time'].values[-1]), WLTP['velocity'].values) / 3600
        print('dist', dist)

        print(mean_absolute_error(calculate_cumulative_fuels(WLTP['time'].values, (0, WLTP['time'].values[-1]), WLTP['fuel consumption'].values),
        calculate_cumulative_fuels(WLTP['time'].values, (0, WLTP['time'].values[-1]), fc)
        ) / dist)

        n_s = calculate_normalized_engine_speeds_out(NEDC['rpm'].values, Input['engine stroke'])
        n_p = calculate_normalized_engine_powers_out(
            NEDC['rpm'].values, NEDC['power'].values, Input['engine capacity']
        )
        fc = calculate_fuel_consumptions(
            NEDC['rpm'].values, NEDC['power'].values,
            n_s, n_p, NEDC['temperature'].values, Input['engine fuel lhv'],
            (Input['engine rpm idle'], 0), Input['engine stroke'],
            Input['engine capacity'], Input['engine fuel consum idle'], p)

        plt.subplot(2,1,2)
        plt.plot(NEDC['time'].values, NEDC['fuel consumption'].values, 'r-')
        plt.plot(NEDC['time'].values, fc, 'b-')
        dist = calculate_cumulative_fuels(NEDC['time'].values, (0, NEDC['time'].values[-1]), NEDC['velocity'].values) / 3600
        print(mean_absolute_error(NEDC['fuel consumption'].values, fc))
        print(
            calculate_cumulative_fuels(NEDC['time'].values, (0, NEDC['time'].values[-1]), NEDC['fuel consumption'].values) / dist,
        calculate_cumulative_fuels(NEDC['time'].values, (0, NEDC['time'].values[-1]), fc) / dist
        )
        print(mean_absolute_error(
            calculate_cumulative_fuels(NEDC['time'].values, (0, NEDC['time'].values[-1]), NEDC['fuel consumption'].values) / dist,
            calculate_cumulative_fuels(NEDC['time'].values, (0, NEDC['time'].values[-1]), fc) / dist
        ))

    plt.show()