__author__ = 'Vincenzo Arcidiacono'

from math import pi
import numpy as np
from sklearn.tree import DecisionTreeRegressor

from compas.functions.physical.constants import *
from compas.functions.physical.utils import bin_split, reject_outliers


def identify_idle_engine_speed_out(velocities, engine_speeds_out):
    """
    Identifies engine speed idle.

    :param velocities:
        Velocity vector.
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
        engine_temperatures, accelerations, wheel_powers):
    """
    Calibrates an engine temperature regression model to predict engine
    temperatures.

    This model returns the delta temperature function of temperature (previous),
    acceleration, and power at the wheel.

    :param engine_temperatures:
        Engine temperature vector [°C].
    :type engine_temperatures: np.array

    :param accelerations:
        Acceleration vector [m/s2].
    :type accelerations: np.array

    :param wheel_powers:
        Power at the wheels [kW].
    :type wheel_powers: np.array

    :return:
        The calibrated engine temperature regression model.
    :rtype: sklearn.tree.DecisionTreeRegressor
    """

    temp = np.zeros(engine_temperatures.shape)
    temp[1:] = engine_temperatures[:-1]

    model = DecisionTreeRegressor(random_state=0)

    X = list(zip(temp, accelerations, wheel_powers))

    model.fit(X[1:], np.diff(engine_temperatures))

    return model


def predict_engine_temperatures(
        model, accelerations, wheel_powers, initial_temperature):
    """
    Predicts the engine temperature.

    :param model:
        Engine temperature regression model.
    :type model: sklearn.tree.DecisionTreeRegressor

    :param accelerations:
        Acceleration vector [m/s2].
    :type accelerations: np.array

    :param wheel_powers:
        Power at the wheels [kW].
    :type wheel_powers: np.array

    :param initial_temperature:
        Engine initial temperature [°C]
    :type initial_temperature: float

    :return:
        Engine temperature vector [°C].
    :rtype: np.array
    """

    temp = [initial_temperature]
    for  p, a in zip(accelerations[:-1], wheel_powers[:-1]):
        temp.append(temp[-1] + model.predict([[temp[-1], p, a]])[0])

    return np.array(temp)
