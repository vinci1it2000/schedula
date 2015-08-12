__author__ = 'Vincenzo Arcidiacono'

import numpy as np
from functools import partial
from sklearn.tree import DecisionTreeClassifier
from compas.dispatcher.utils import SubDispatchFunction
from compas.functions.physical.utils import reject_outliers


def identify_electric_loads(
        alternator_nominal_voltage, battery_currents, gear_box_powers_in,
        times, on_engine, engine_starts):
    """
    Identifies vehicle electric load and engine start demand [kW].

    :param alternator_nominal_voltage:
        Alternator nominal voltage [V].
    :type alternator_nominal_voltage: float

    :param battery_currents:
        Low voltage battery current vector [A].
    :type battery_currents: np.array

    :param alternator_currents:
        Alternator current vector [A].
    :type alternator_currents: np.array

    :param times:
        Time vector [s].
    :type times: np.array

    :param engine_starts:
        When the engine starts [-].
    :type engine_starts: np.array

    :return:
        Vehicle electric load and engine start demand [kW].
    :rtype: ((float, float), float)
    """

    b_c = battery_currents
    b = (b_c < 0) & (gear_box_powers_in >= 0)

    c = alternator_nominal_voltage / 1000.0

    bL = b & np.logical_not(on_engine)
    bH = b & on_engine

    load_off = min(0.0, reject_outliers(c * b_c[bL], med=np.mean)[0])
    load_on = min(0.0, reject_outliers(c * b_c[bH], med=np.mean)[0])

    n_starts = sum(engine_starts)

    #start_demand = float(np.trapz(power - electric_load, x=times) / n_starts)

    return (load_off, load_on), 0


def identify_max_charging_current(battery_currents, electric_load):
    """
    Identifies the maximum charging current of the alternator [A].

    :param alternator_currents:
        Alternator current vector [A].
    :type alternator_currents: np.array

    :return:
        Maximum charging current of the alternator [A].
    :rtype: float
    """

    return electric_load[1] - max(battery_currents)


def calculate_state_of_charges(
        battery_capacity, times, initial_soc, battery_currents):
    """
    Calculates the state of charge of the battery [%].

    :param battery_capacity:
        Battery capacity [Ah].
    :type battery_capacity: float

    :param times:
        Time vector [s].
    :type times: np.array

    :param initial_soc:
        Initial state of charge of the battery [%].
    :type initial_soc: float

    :param battery_currents:
        Low voltage battery current vector [A].
    :type battery_currents: np.array

    :return:
        State of charge of the battery [%].
    :rtype: np.array
    """

    soc = [initial_soc]
    c = battery_capacity * 36.0

    bc = np.asarray(battery_currents)
    bc = (bc[:-1] + bc[1:]) * np.diff(times) / 2

    for b in bc:
        soc.append(soc[-1] + b / c)

    return np.asarray(soc)


def calculate_alternator_powers_demand(
        alternator_nominal_voltage, alternator_currents, alternator_efficiency,
        max_charging_current):
    """
    Calculates the alternator power demand to the engine [kW].

    :param alternator_nominal_voltage:
        Alternator nominal voltage [V].
    :type alternator_nominal_voltage: float

    :param alternator_currents:
        Alternator current vector [A].
    :type alternator_currents: np.array

    :param alternator_efficiency:
        Alternator efficiency [-].
    :type alternator_efficiency: float

    :return:
        Alternator power demand to the engine [kW].
    :rtype: np.array
    """

    c = alternator_nominal_voltage / (1000.0 * alternator_efficiency)

    current = np.zeros(alternator_currents.shape)

    b = max_charging_current < alternator_currents

    current[b] = alternator_currents[b]
    current[np.logical_not(b)] = max_charging_current

    return current * c


def identify_charging_statuses(
        battery_currents, gear_box_powers_in, on_engine):
    """
    Identifies when the alternator is on due to 1:state of charge or 2:BERS [-].

    :param alternator_powers_demand:
        Alternator power demand to the engine [kW].
    :type alternator_powers_demand: np.array

    :param gear_box_powers_in:
        Gear box power [kW].
    :type gear_box_powers_in: np.array

    :param on_engine:
        If the engine is on [-].
    :type on_engine: np.array

    :return:
        The alternator status (0: off, 1: on, due to state of charge, 2: on due
        to BERS) [-].
    :rtype: np.array
    """

    gb_p = gear_box_powers_in
    status = np.zeros(battery_currents.shape)

    status[battery_currents >= 0] = 2

    it = (i
          for i, (s, p) in enumerate(zip(status, gb_p))
          if s == 2 and p >= 0)

    b1 = -1

    n = len(on_engine) - 1

    while True:
        b0 = next(it, None)

        if b0 is None:
            break

        if status[b0 - 1] or b0 < b1:
            continue

        b1 = b0

        while b1 < n and (status[b1] or not on_engine[b1]):
            b1 += 1

        while b1 > b0 and (gb_p[b1] < 0 or gb_p[b1] - gb_p[b1 - 1] > 0):
            b1 -= 1

        if b1 > b0:
            status[b0:b1 + 1] = 1

    return status


def calibrate_alternator_status_model(
        alternator_statuses, state_of_charges, gear_box_powers_in):
    """
    Calibrates the alternator status model.

    :param alternator_statuses:
        The alternator status (0: off, 1: on, due to state of charge, 2: on due
        to BERS) [-].
    :type alternator_statuses: np.array

    :param state_of_charges:
        State of charge of the battery [%].
    :type state_of_charges: np.array

    :param gear_box_powers_in:
        Gear box power [kW].
    :type gear_box_powers_in: np.array

    :return:
        A function that predicts the alternator status.
    :rtype: function
    """

    bers = DecisionTreeClassifier(random_state=0, max_depth=3)
    charge = DecisionTreeClassifier(random_state=0, max_depth=3)

    X = list(zip(gear_box_powers_in[1:]))

    bers.fit(X, alternator_statuses[1:] == 2)

    X = list(zip(alternator_statuses[:-1], state_of_charges[1:]))

    charge.fit(X, alternator_statuses[1:] == 1)

    # shortcut names
    bers_pred = bers.predict
    charge_pred = charge.predict

    def model(prev_status, battery_soc, gear_box_power_in):
        status = 0

        if battery_soc < 100:
            if charge_pred([prev_status, battery_soc])[0]:
                status = 1

            elif bers_pred([gear_box_power_in])[0]:
                status = 2

        return status

    return model


def predict_vehicle_electrics(
        battery_capacity, alternator_status_model, max_alternator_current,
        alternator_nominal_voltage, start_demand, electric_load,
        initial_state_of_charge, times, gear_box_powers_in, on_engine,
        engine_starts):
    """
    Predicts alternator and battery currents, state of charge, and alternator
    status.

    :param battery_capacity:
        Battery capacity [Ah].
    :type battery_capacity: float

    :param alternator_status_model:
        A function that predicts the alternator status.
    :type alternator_status_model: function

    :param max_alternator_current:
        Maximum charging current of the alternator [A].
    :type max_alternator_current: float

    :param alternator_nominal_voltage:
        Alternator nominal voltage [V].
    :type alternator_nominal_voltage: float

    :param start_demand:
         Engine start demand [kW].
    :type start_demand: float

    :param electric_load:
        Vehicle electric load.
    :type electric_load: float

    :param initial_state_of_charge:
        Initial state of charge of the battery [%].
    :type initial_state_of_charge: float

    :param times:
        Time vector [s].
    :type times: np.array

    :param gear_box_powers_in:
        Gear box power [kW].
    :type gear_box_powers_in: np.array

    :param on_engine:
        If the engine is on [-].
    :type on_engine: np.array

    :param engine_starts:
        When the engine starts [-].
    :type engine_starts: np.array
    :return:
    """

    from compas.models.physical.electrics.electrics_prediction import \
        electrics_prediction

    func = SubDispatchFunction(
        dsp=electrics_prediction(),
        function_id='electric_sub_model',
        inputs=['battery_capacity', 'alternator_status_model',
                'max_alternator_current', 'alternator_nominal_voltage',
                'start_demand', 'electric_load',

                'delta_time', 'gear_box_power_in',
                'on_engine', 'engine_start',

                'battery_state_of_charge', 'alternator_status',
                'prev_battery_current'],
        outputs=['alternator_current', 'battery_state_of_charge',
                 'alternator_status', 'battery_current']
    )

    func = partial(
        func, battery_capacity, alternator_status_model, max_alternator_current,
        alternator_nominal_voltage, start_demand, electric_load)

    delta_times = np.append([0], np.diff(times))

    res = [(0, initial_state_of_charge, 0, None)]
    for x in zip(delta_times, gear_box_powers_in, on_engine, engine_starts):
        res.append(tuple(func(*(x + res[-1][1:]))))

    alt_c, soc, alt_stat, bat_c = zip(*res[1:])

    return np.array(alt_c), np.array(bat_c), np.array(soc), np.array(alt_stat)
