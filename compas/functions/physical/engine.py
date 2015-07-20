__author__ = 'Vincenzo Arcidiacono'

from math import pi
import numpy as np
from sklearn.tree import DecisionTreeRegressor, ExtraTreeRegressor
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from compas.functions.physical.constants import *
from compas.functions.physical.utils import bin_split, reject_outliers


def identify_idle_engine_speed_out(velocities, engine_speeds_out):
    """
    Identifies engine speed idle.

    :param velocities:
        Velocity vector [km/h].
    :type velocities: np.array

    :param engine_speeds_out:
        Engine speed vector.
    :type engine_speeds_out: np.array

    :returns:
        - Engine speed idle.
        - Its standard deviation.
    :rtype: (float, float)
    """

    x = engine_speeds_out[
        velocities < VEL_EPS & engine_speeds_out > MIN_ENGINE_SPEED]

    idle_speed = bin_split(x, bin_std=(0.01, 0.3))[1][0]

    return idle_speed[-1], idle_speed[1]


def identify_upper_bound_engine_speed(
        gears, engine_speeds_out, idle_engine_speed):
    """
    Identifies upper bound engine speed.

    It is used to correct the gear prediction for constant accelerations (see
    :func:`compas.functions.physical.AT_gear.
    correct_gear_upper_bound_engine_speed`).

    This is evaluated as the median value plus 0.67 standard deviation of the
    filtered cycle engine speed (i.e., the engine speeds when engine speed >
    minimum engine speed plus 0.67 standard deviation and gear < maximum gear).

    :param gears:
        Gear vector.
    :type gears: np.array

    :param engine_speeds_out:
        Engine speed vector.
    :type engine_speeds_out: np.array

    :param idle_engine_speed:
        Engine speed idle median and std.
    :type idle_engine_speed: (float, float)

    :returns:
        Upper bound engine speed.
    :rtype: float

    .. note:: Assuming a normal distribution then about 68 percent of the data
       values are within 0.67 standard deviation of the mean.
    """

    max_gear = max(gears)

    idle_speed = idle_engine_speed[1]

    dom = (engine_speeds_out > idle_speed) & (gears < max_gear)

    m, sd = reject_outliers(engine_speeds_out[dom])

    return m + sd * 0.674490


def calculate_piston_speeds(engine_stroke, engine_speeds_out):
    """
    Calculates piston speed.

    :param engine_stroke:
        Engine stroke.
    :type engine_stroke: np.array, float

    :param engine_speeds_out:
        Engine speed [RPM].
    :type engine_speeds_out: np.array, float

    :return:
        Engine piston speed.
    :rtype: np.array, float
    """

    return engine_speeds_out / 60 * 2 * engine_stroke / 1000


def calculate_braking_powers(
        engine_speeds_out, engine_torques_in, piston_speeds,
        engine_loss_parameters, engine_capacity):
    """
    Calculates braking power.

    :param engine_speeds_out:
        Engine speed.
    :type engine_speeds_out: np.array

    :param engine_torques_in:
        Engine torque out.
    :type engine_torques_in: np.array

    :param piston_speeds:
        Piston speed.
    :type piston_speeds: np.array

    :param engine_loss_parameters:
        Engine parameter (loss, loss2).
    :type engine_loss_parameters: (float, float)

    :param engine_capacity:
        Engine capacity.
    :type engine_capacity: float

    :return:
        Braking powers.
    :rtype: np.array
    """

    loss, loss2 = engine_loss_parameters
    cap, es = engine_capacity, engine_speeds_out

    # indicative_friction_powers
    friction_powers = ((loss2 * piston_speeds ** 2 + loss) * es * cap) / 1200000

    bp = engine_torques_in * engine_speeds_out * (pi / 30000)

    bp[bp < friction_powers] = 0

    return bp


def calibrate_engine_temperature_regression_model(
        engine_temperatures, velocities, wheel_powers, engine_speeds_out):
    """
    Calibrates an engine temperature regression model to predict engine
    temperatures.

    This model returns the delta temperature function of temperature (previous),
    acceleration, and power at the wheel.

    :param engine_temperatures:
        Engine temperature vector [°C].
    :type engine_temperatures: np.array

    :param velocities:
        Velocity vector [km/h].
    :type velocities: np.array

    :param wheel_powers:
        Power at the wheels [kW].
    :type wheel_powers: np.array

    :param engine_speeds_out:
        Engine speed [RPM].
    :type engine_speeds_out: np.array

    :return:
        The calibrated engine temperature regression model.
    :rtype: sklearn.ensemble.GradientBoostingRegressor
    """

    temp = np.zeros(engine_temperatures.shape)
    temp[1:] = engine_temperatures[:-1]

    kw = {
        'random_state': 0,
        'max_depth': 2,
        'n_estimators': int(min(300, 0.25 * (len(temp) - 1)))
    }

    model = GradientBoostingRegressor(**kw)

    X = list(zip(temp, velocities, wheel_powers, engine_speeds_out))

    model.fit(X[1:], np.diff(engine_temperatures))

    return model


def predict_engine_temperatures(
        model, velocities, wheel_powers, engine_speeds_out,
        initial_temperature):
    """
    Predicts the engine temperature.

    :param model:
        Engine temperature regression model.
    :type model: sklearn.ensemble.GradientBoostingRegressor

    :param velocities:
        Velocity vector [km/h].
    :type velocities: np.array

    :param wheel_powers:
        Power at the wheels [kW].
    :type wheel_powers: np.array

    :param engine_speeds_out:
        Engine speed [RPM].
    :type engine_speeds_out: np.array

    :param initial_temperature:
        Engine initial temperature [°C]
    :type initial_temperature: float

    :return:
        Engine temperature vector [°C].
    :rtype: np.array
    """

    predict = model.predict
    it = zip(velocities[:-1], wheel_powers[:-1], engine_speeds_out[:-1])

    temp = [initial_temperature]
    for v, p, e in it:
        temp.append(temp[-1] + predict([[temp[-1], v, p, e]])[0])

    return np.array(temp)


if __name__ == '__main__':
    from compas.functions.physical.vehicle import calculate_accelerations
    import pandas as pd
    import glob, os
    import matplotlib.pyplot as plt
    from sklearn.metrics import mean_absolute_error
    fpaths = glob.glob('C:/Users/arcidvi/Desktop/basecases/*.xlsx')


    for fpath in fpaths:
        fname = os.path.basename(fpath)
        fname = fname.split('.')[0]
        print('Processing: %s' % fname)
        ex = pd.ExcelFile(fpath)
        WLTP = ex.parse(sheetname='WLTP mean')
        WLTPL = ex.parse(sheetname='WLTP-Low mean')
        NEDC = ex.parse(sheetname='NEDC mean')
        time_WLTP = WLTP['Time [s]'].values
        time_WLTPL = WLTPL['Time [s]'].values
        time_NEDC = NEDC['Time [s]'].values
        vel_WLTP = WLTP['Velocity [km/h]'].values
        vel_WLTPL = WLTPL['Velocity [km/h]'].values
        vel_NEDC = NEDC['Velocity [km/h]'].values
        acc_WLTP = calculate_accelerations(time_WLTP, vel_WLTP)
        acc_WLTPL = calculate_accelerations(time_WLTPL, vel_WLTPL)
        acc_NEDC = calculate_accelerations(time_NEDC, vel_NEDC)
        temp_WLTP = WLTP['Engine Temperature [oC]'].values
        temp_WLTPL = WLTPL['Engine Temperature [oC]'].values
        temp_NEDC = NEDC['Engine Temperature [oC]'].values

        modelH = calibrate_engine_temperature_regression_model(temp_WLTP,vel_WLTP, WLTP['Wheel Power [kW]'].values, WLTP['Engine Speed [rpm]'].values)

        #modelH = calibrate_engine_temperature_regression_model(temp_NEDC, NEDC['Wheel Power [kW]'].values, NEDC['Engine Speed [rpm]'].values)
        modelL = calibrate_engine_temperature_regression_model(temp_WLTPL, vel_WLTPL,WLTPL['Wheel Power [kW]'].values, WLTPL['Engine Speed [rpm]'].values)

        t_WLTP = predict_engine_temperatures(modelL, vel_WLTP , WLTP['Wheel Power [kW]'].values, WLTP['Engine Speed [rpm]'].values, temp_WLTP[0])
        t_WLTPL = predict_engine_temperatures(modelH, vel_WLTPL, WLTPL['Wheel Power [kW]'].values, WLTPL['Engine Speed [rpm]'].values, temp_WLTPL[0])

        #if mean_absolute_error(temp_WLTP, t_WLTP) < mean_absolute_error(temp_WLTPL, t_WLTPL):
        model = modelL
        #    print('low')
        #else:
        #    model = modelH
        #    print('high')
        t_WLTP = predict_engine_temperatures(model,vel_WLTP, WLTP['Wheel Power [kW]'].values, WLTP['Engine Speed [rpm]'].values, temp_WLTP[0])
        t_NEDC = predict_engine_temperatures(model,vel_NEDC, NEDC['Wheel Power [kW]'].values, NEDC['Engine Speed [rpm]'].values, temp_NEDC[0])
        errors = (mean_absolute_error(temp_WLTP, t_WLTP), mean_absolute_error(temp_NEDC, t_NEDC))
        print(errors)
        plt.figure()
        plt.subplot(2, 1, 1)
        plt.title(fname + str(errors))
        plt.plot(time_WLTP, temp_WLTP, 'r-')
        plt.plot(time_WLTP, t_WLTP, 'b-')
        plt.subplot(2, 1, 2)
        plt.plot(time_NEDC, temp_NEDC, 'r-')
        plt.plot(time_NEDC, t_NEDC, 'b-')
    plt.show()