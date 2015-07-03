__author__ = 'Vincenzo Arcidiacono'

from math import pi
import numpy as np
from compas.dispatcher.utils.dsp import SubDispatchFunction
from compas.models.gear_box_efficiency import gear_box_eff
from compas.functions.constants import *

def torque_required(gear_box_torque, engine_speed, wheel_speed, par):
    """
    Calculates torque required according to the temperature profile.

    :param gear_box_torque:
        Torque gear_box.
    :type gear_box_torque: float

    :param engine_speed:
        Engine speed.
    :type engine_speed: float

    :param wheel_speed:
        Wheel speed.
    :type wheel_speed: float

    :param par:
        Parameters of gear box efficiency model:

            - `gbp00`,
            - `gbp10`,
            - `gbp01`
    :type par: dict

    :return:
        Torque required.
    :rtype: float
    """

    tgb, es, ws = gear_box_torque, engine_speed, wheel_speed

    if tgb < 0:
        return par['gbp01'] * tgb - par['gbp10'] * ws - par['gbp00']
    elif es > 0 and ws > 0:
        return (tgb - par['gbp10'] * es - par['gbp00']) / par['gbp01']
    return 0


def calculate_torque_required(
        gear_box_torque, engine_speed, wheel_speed, gear_box_temperature,
        gear_box_efficiency_parameters, temperature_references):
    """
    Calculates torque required according to the temperature profile.

    :param gear_box_torque:
        Torque gear box.
    :type gear_box_torque: float

    :param engine_speed:
        Engine speed.
    :type engine_speed: float

    :param wheel_speed:
        Wheel speed.
    :type wheel_speed: float

    :param gear_box_temperature:
        Temperature.
    :type gear_box_temperature: float

    :param gear_box_efficiency_parameters:
        Parameters of gear box efficiency model for cold/hot phases:

            - 'hot': `gbp00`, `gbp10`, `gbp01`
            - 'cold': `gbp00`, `gbp10`, `gbp01`
    :type gear_box_efficiency_parameters: dict

    :param temperature_references:
        Cold and hot reference temperatures.
    :type temperature_references: tuple

    :return:
        Torque required according to the temperature profile.
    :rtype: float
    """

    par = gear_box_efficiency_parameters
    T_cold, T_hot = temperature_references
    t_out, e_s, gb_s = gear_box_torque, engine_speed, wheel_speed

    t = torque_required(t_out, e_s, gb_s, par['hot'])

    if not T_cold == T_hot and gear_box_temperature <= T_hot:

        t_cold = torque_required(t_out, e_s, gb_s, par['cold'])

        t += (T_hot - gear_box_temperature) / (T_hot - T_cold) * (t_cold - t)

    return t


def correct_torque_required(
        gear_box_torque, torque_required, gear, gear_box_ratios):
    """
    Corrects the torque when the gear box ratio is equal to 1.

    :param gear_box_torque:
        Torque gear_box.
    :type gear_box_torque: float

    :param torque_required:
        Torque required.
    :type torque_required: float

    :param gear:
        Gear.
    :type gear: int

    :return:
        Corrected torque required.
    :rtype: float
    """

    gbr = gear_box_ratios

    return gear_box_torque if gbr.get(gear, 0) == 1 else torque_required


def calculate_gear_box_efficiency(
        wheel_power, engine_speed, wheel_speed, gear_box_torque,
        torque_required):
    """
    Calculates torque entering the gear box.

    :param wheel_power:
        Power at wheels.
    :type wheel_power: float

    :param engine_speed:
        Engine speed.
    :type engine_speed: float

    :param wheel_speed:
        Wheel speed.
    :type wheel_speed: float

    :return:

        - Gear box efficiency.
        - Torque loss.
    :rtype: (float, float)

    .. note:: Torque entering the gearbox can be from engine side
       (power mode or from wheels in motoring mode).
    """

    eff, torque_loss = 0, torque_required - gear_box_torque
    if torque_required == gear_box_torque:
        eff = 1
    else:
        eff = torque_required / wheel_power * (pi / 30000)
        eff = 1 / (engine_speed * eff) if wheel_power > 0 else wheel_speed * eff

    return max(0, min(1, eff)), torque_loss


def calculate_gear_box_temperature(
        gear_box_heat, starting_temperature, equivalent_gear_box_capacity,
        thermostat_temperature):
    """
    Calculates the gear box temperature not finalized [°].

    :param gear_box_heat:
        Gear box heat.
    :type gear_box_heat: float

    :param starting_temperature:
        Starting temperature.
    :type starting_temperature: float

    :param equivalent_gear_box_capacity:
        Equivalent gear box capacity (from cold start model).
    :type equivalent_gear_box_capacity: float

    :param thermostat_temperature:
        Thermostat temperature [°].
    :type thermostat_temperature: float

    :return:
        Gear box temperature not finalized.
    :rtype: float
    """

    temp = starting_temperature + gear_box_heat / equivalent_gear_box_capacity

    return min(temp, thermostat_temperature - 5.0)


def calculate_gear_box_heat(gear_box_efficiency, wheel_power):
    """
    Calculates the gear box temperature heat.

    :param gear_box_efficiency:
        Gear box efficiency.
    :type gear_box_efficiency: float

    :param wheel_power:
        Power at wheels.
    :type wheel_power: float

    :return:
        Gear box heat.
    :rtype: float
    """

    if gear_box_efficiency and wheel_power:
        return abs(wheel_power) * (1.0 - gear_box_efficiency) * 1000.0

    return 0


def get_gear_box_efficiency_constants(gear_box_type):
    """
    Returns vehicle gear box efficiency constants.

    :param gear_box_type:
        Gear box type:

            - 'manual',
            - 'automatic'.
    :type gear_box_type: str

    :return:
        Vehicle gear box efficiency constants.
    :rtype: dict
    """
    gb_eff_constants = {
        'automatic': {
            'gbp00': {'m': -0.0054, 'q': {'hot': -1.9682, 'cold': -3.9682}},
            'gbp10': {'q': {'hot': -0.0012, 'cold': -0.0016}},
            'gbp01': {'q': {'hot': 0.965, 'cold': 0.965}},
        },
        'manual': {
            'gbp00': {'m': -0.0034, 'q': {'hot': -0.3119, 'cold': -0.7119}},
            'gbp10': {'q': {'hot': -0.00018, 'cold': 0}},
            'gbp01': {'q': {'hot': 0.97, 'cold': 0.97}},
        }
    }

    return gb_eff_constants[gear_box_type]


def calculate_gear_box_efficiency_parameters(
        gear_box_efficiency_constants, engine_max_torque):
    """
    Calculates the parameters of gear box efficiency model for cold/hot phases.

    :param gear_box_efficiency_constants:
        Vehicle gear box efficiency constants.
    :type gear_box_efficiency_constants: dict

    :param engine_max_torque:
        Engine Max Torque (Nm).
    :type engine_max_torque: float

    :return:
        Parameters of gear box efficiency model for cold/hot phases:

            - 'hot': `gbp00`, `gbp10`, `gbp01`
            - 'cold': `gbp00`, `gbp10`, `gbp01`
    :rtype: dict
    """

    def get_par(obj, key, default=None):
        if default is None:
            default = obj

        try:
            return obj.get(key, default)
        except AttributeError:
            return default

    _linear = lambda x, m, q: x * m + q

    par = {'hot': {}, 'cold': {}}

    for p in ['hot', 'cold']:
        for k, v in gear_box_efficiency_constants.items():
            m = get_par(get_par(v, 'm', default=0.0), p)
            q = get_par(get_par(v, 'q', default=0.0), p)
            par[p][k] = _linear(engine_max_torque, m, q)

    return par


def calculate_gear_box_torques(wheel_powers, engine_speeds, wheel_speeds):
    """
    Calculates torque entering the gear box.

    :param wheel_powers:
        Power at wheels vector.
    :type wheel_powers: np.array

    :param engine_speeds:
        Engine speed vector.
    :type engine_speeds: np.array

    :param wheel_speeds:
        Wheel speed vector.
    :type wheel_speeds: np.array

    :return:
        Torque gear box vector.
    :rtype: np.array

    .. note:: Torque entering the gearbox can be from engine side
       (power mode or from wheels in motoring mode)
    """

    x = np.where(wheel_powers > 0, engine_speeds, wheel_speeds)

    y = np.zeros(wheel_powers.shape)

    b = x > MIN_ENGINE_SPEED

    y[b] = wheel_powers[b] / x[b]

    return y * (30000 / pi)


def calculate_torques_required(
        gear_box_torques, engine_speeds, wheel_speeds, temperatures,
        gear_box_efficiency_parameters, temperature_references):
    """
    Calculates torque required according to the temperature profile.

    :param gear_box_torques:
        Torque gear box vector.
    :type gear_box_torques: np.array

    :param engine_speeds:
        Engine speed vector.
    :type engine_speeds: np.array

    :param wheel_speeds:
        Wheel speed vector.
    :type wheel_speeds: np.array

    :param temperatures:
        Temperature vector.
    :type temperatures: np.array

    :param gear_box_efficiency_parameters:
        Parameters of gear box efficiency model for cold/hot phases:

            - 'hot': `gbp00`, `gbp10`, `gbp01`
            - 'cold': `gbp00`, `gbp10`, `gbp01`
    :type gear_box_efficiency_parameters: dict

    :param temperature_references:
        Cold and hot reference temperatures.
    :type temperature_references: tuple

    :return:
        Torque required vector according to the temperature profile.
    :rtype: np.array
    """

    par = gear_box_efficiency_parameters
    T_cold, T_hot = temperature_references
    t_out, e_s, gb_s = gear_box_torques, engine_speeds, wheel_speeds
    fun = torques_required

    t = fun(t_out, e_s, gb_s, par['hot'])

    if not T_cold == T_hot:
        b = temperatures <= T_hot

        t_cold = fun(t_out[b], e_s[b], gb_s[b], par['cold'])

        t[b] += (T_hot - temperatures[b]) / (T_hot - T_cold) * (t_cold - t[b])

    return t


def torques_required(gear_box_torques, engine_speeds, wheel_speeds, par):
    """
    Calculates torque required according to the temperature profile.

    :param gear_box_torques:
        Torque gear_box vector.
    :type gear_box_torques: np.array

    :param engine_speeds:
        Engine speed vector.
    :type engine_speeds: np.array

    :param wheel_speeds:
        Wheel speed vector.
    :type wheel_speeds: np.array

    :param par:
        Parameters of gear box efficiency model:

            - `gbp00`,
            - `gbp10`,
            - `gbp01`
    :type par: dict

    :return:
        Torque required vector.
    :rtype: np.array
    """

    tgb, es, ws = gear_box_torques, engine_speeds, wheel_speeds

    b = tgb < 0

    y = np.zeros(tgb.shape)

    y[b] = par['gbp01'] * tgb[b] - par['gbp10'] * ws[b] - par['gbp00']

    b = (np.logical_not(b)) & (es > MIN_ENGINE_SPEED) & (ws > MIN_ENGINE_SPEED)

    y[b] = (tgb[b] - par['gbp10'] * es[b] - par['gbp00']) / par['gbp01']

    return y


def correct_torques_required(
        gear_box_torques, torques_required, gears, gear_box_ratios):
    """
    Corrects the torque when the gear box ratio is equal to 1.

    :param gear_box_torques:
        Torque gear_box vector.
    :type gear_box_torques: np.array

    :param torques_required:
        Torque required vector.
    :type torques_required: np.array

    :param gears:
        Gear vector.
    :type gears: np.array

    :return:
        Corrected torque required vector.
    :rtype: np.array
    """
    b = np.zeros(gears.shape, dtype=bool)

    for k, v in gear_box_ratios.items():
        if v == 1:
            b |= gears == k

    return np.where(b, gear_box_torques, torques_required)


def calculate_gear_box_efficiencies_v2(
        wheel_powers, engine_speeds, wheel_speeds, gear_box_torques,
        torques_required):
    """
    Calculates torque entering the gear box.

    :param wheel_powers:
        Power at wheels vector.
    :type wheel_powers: np.array

    :param engine_speeds:
        Engine speed vector.
    :type engine_speeds: np.array

    :param wheel_speeds:
        Wheel speed vector.
    :type wheel_speeds: np.array

    :return:

        - Gear box efficiency vector.
        - Torque losses.
    :rtype: (np.array, np.array)

    .. note:: Torque entering the gearbox can be from engine side
       (power mode or from wheels in motoring mode).
    """

    wp = wheel_powers
    tgb = gear_box_torques
    tr = torques_required
    ws = wheel_speeds
    es = engine_speeds

    eff = np.zeros(wp.shape)

    b0 = tr * tgb >= 0
    b1 = (b0) & (wp >= 0) & (es > MIN_ENGINE_SPEED) & (tr != 0)
    b = (((b0) & (wp < 0)) | (b1))

    s = np.where(b1, es, ws)

    eff[b] = s[b] * tr[b] / wp[b] * (pi / 30000)

    eff[b1] = 1 / eff[b1]

    return eff, tr - tgb


def calculate_gear_box_efficiencies(
        wheel_powers, engine_speeds, wheel_speeds, gear_box_torques,
        gear_box_efficiency_parameters, equivalent_gear_box_capacity,
        thermostat_temperature, temperature_references,
        gear_box_starting_temperature, gears=None, gear_box_ratios=None):
    """
    Calculates torque entering the gear box.

    :param wheel_powers:
        Power at wheels vector.
    :type wheel_powers: np.array

    :param engine_speeds:
        Engine speed vector.
    :type engine_speeds: np.array

    :param wheel_speeds:
        Wheel speed vector.
    :type wheel_speeds: np.array

    :return:

        - Gear box efficiency vector.
        - Torque losses.
    :rtype: (np.array, np.array)

    .. note:: Torque entering the gearbox can be from engine side
       (power mode or from wheels in motoring mode).
    """

    inputs = ['thermostat_temperature', 'equivalent_gear_box_capacity',
              'gear_box_efficiency_parameters', 'temperature_references',
              'wheel_power', 'wheel_speed', 'engine_speed', 'gear_box_torque']

    outputs = ['gear_box_temperature', 'gear_box_torque_loss',
               'gear_box_efficiency']

    dfl = (thermostat_temperature, equivalent_gear_box_capacity,
           gear_box_efficiency_parameters, temperature_references)

    it = (wheel_powers, wheel_speeds, engine_speeds, gear_box_torques)

    if gear_box_ratios and gears is not None:
        inputs = ['gear_box_ratios'] + inputs
        inputs.append('gear')
        dfl = (gear_box_ratios, ) + dfl
        it = it + (gears, )

    inputs.append('gear_box_temperature')

    fun = SubDispatchFunction(gear_box_eff, 'gear_box_eff', inputs, outputs)
    T0 = gear_box_starting_temperature
    res = []
    for args in zip(*it):
        res.append(fun(*(dfl + args + (T0, ))))
        T0 = res[-1][0]

    temp, loss, eff = zip(*res)
    temp = (gear_box_starting_temperature, ) + temp[:-1]
    return np.array(eff), np.array(loss), np.array(temp)


def calculate_gear_box_speeds(gears, velocities, velocity_speed_ratios):
    """
    Calculates gear box speed vector.

    :param gears:
        Gear vector.
    :type gears: np.array

    :param velocities:
        Velocity vector.
    :type velocities: np.array

    :param velocity_speed_ratios:
        Constant velocity speed ratios of the gear box.
    :type velocity_speed_ratios: dict

    :return:
        Gear box speed vector.
    :rtype: np.array
    """

    vsr = [0]

    def get_vsr(g):
        vsr[0] = velocity_speed_ratios.get(g, vsr[0])
        return float(vsr[0])

    vsr = np.vectorize(get_vsr)(gears)

    speeds = velocities / vsr

    speeds[(velocities < VEL_EPS) | (vsr == 0)] = 0

    return speeds
