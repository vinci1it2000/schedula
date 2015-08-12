__author__ = 'arcidvi'

def calculate_battery_current(
        electric_load, engine_start_current, alternator_current,
        alternator_nominal_voltage, on_engine):

    c = electric_load[on_engine] / alternator_nominal_voltage * 1000.0

    return c + engine_start_current - alternator_current


def calculate_alternator_current(
        alternator_status, on_engine, max_alternator_current):

    return max_alternator_current if alternator_status and on_engine else 0.0


def calculate_battery_state_of_charge(
        prev_battery_state_of_charge, battery_capacity,
        delta_time, battery_current, prev_battery_current=None):

    if prev_battery_current is None:
        prev_battery_current = battery_current

    c = battery_capacity * 36.0

    b = (battery_current + prev_battery_current) / 2 * delta_time

    return prev_battery_state_of_charge + b / c


def predict_alternator_status(
        alternator_status_model, prev_status, battery_state_of_charge,
        gear_box_power_in):

    args = (prev_status, battery_state_of_charge, gear_box_power_in)

    return alternator_status_model(*args)


def calculate_engine_start_current(
        engine_start, start_demand, alternator_nominal_voltage, delta_time):

    if engine_start:
        return start_demand / (delta_time * alternator_nominal_voltage) * 1000.0
    return 0.0