from schema import Schema, Use, And, Or, Optional, SchemaError
import numpy as np
import co2mpas.dispatcher.utils as dsp_utl
from .. import _iter_d, _get
from ..co2mpas_model.physical.gear_box.AT_gear import CMV, MVL, GSPV
from sklearn.tree import DecisionTreeClassifier
from lmfit import Parameters


def validate_data(data):
    res = {}

    schema = define_data_schema()
    for k, v in _iter_d(data, depth=3):
        for i, j in v.items():
            try:
                schema.validate({i: j})
            except:
                pass
        _get(res, *k[:-1])[k[-1]] = schema.validate(v)

    return data


class Empty(object):
    def __repr__(self):
        return '%s' % self.__class__.__name__

    def validate(self, data):
        valid = True
        try:
            if data:
                valid = False
            elif data is None or (isinstance(data, np.ndarray) and not data):
                pass
            elif data != '':
                valid = False
        except ValueError:
            if not np.isnan(data).all():
                valid = False
        if valid:
            return dsp_utl.NONE
        else:
            raise SchemaError('%r is not empty' % data, None)


def _function(error=None, **kwargs):
    def _check_function(f):
        assert callable(f)
        return f
    return Use(_check_function, error=error)


def _string(error=None, **kwargs):
    return Use(str, error=error)


def _select(types=(), error=None, **kwargs):
    try:
        error = '%s.' %(error % ', '.join(types))
    except TypeError:
        pass
    return And(str, Use(lambda x: x.lower()), lambda x: x in types, error=error)


def _positive(type=float, error=None, **kwargs):
    _check_positive = lambda x: x > 0
    return And(Use(type), _check_positive, error=error)


def _limits(limits=(0, 100), error=None, **kwargs):
    _check_limits = lambda x: limits[0] <= x <= limits[1]
    return And(Use(float), _check_limits, error=error)


def _eval(s, error=None, **kwargs):
    return Or(And(str, Use(eval), s), s, error=error)


def _dict(format={int: float}, error=None, **kwargs):
    c = Use(lambda x: {k: v for k, v in dict(x).items() if v})
    return _eval(Or(Empty, And(c, format)), error=error)


def _type(type=tuple, error=None, length=None, **kwargs):
    if length:
        length = Or(*(lambda x: len(x) == l for l in tuple(length)))
        return And(_type(type=type), length, error=error)
    return _eval(Use(type), error=error)


def _index_dict(error=None, **kwargs):
    c = {int: Use(float)}
    f = lambda x: {k: v for k, v in enumerate(x, start=1)}
    return Or(c, And(_dict(), c), And(_type(), Use(f), c), error=error)


def _np_array(dtype=None, error=None, read=True, **kwargs):
    if read:
        c = Use(lambda x: np.asarray(x, dtype=dtype))
        return Or(c, And(_type(), c), error=error)
    else:
        return And(_np_array(dtype=dtype), Use(lambda x: x.tolist()), error=error)


def _cmv(**kwargs):
    return _type(type=CMV)


def _mvl(**kwargs):
    return _type(type=CMV)


def _gspv():
    return _type(type=GSPV)


def define_data_schema():
    dtc = DecisionTreeClassifier

    schema = {
        'CMV': _cmv(),
        'CMV_Cold_Hot': _dict(format={'hot': _cmv(), 'cold': _cmv()}),
        'DT_VA': dtc,
        'DT_VAP': dtc,
        'DT_VAT': dtc,
        'DT_VATP': dtc,
        'GSPV': _gspv(),
        'GSPV_Cold_Hot': _dict(format={'hot': _gspv(), 'cold': _gspv()}),
        'MVL': _mvl,

        'VERSION': _string(error='VERSION should be a string.'),
        'fuel_type': _select(types=('gasoline', 'diesel'), error='Allowed fuel_type: %s'),

        'alternator_charging_currents': _tuple((_float,) * 2),
        'alternator_current_model': function,
        'alternator_status_model': function,
        'clutch_model': function,
        'co2_emissions_model': function,
        'co2_error_function_on_emissions': function,
        'co2_error_function_on_phases': function,
        'cold_start_speed_model': function,
        'clutch_window': _tuple((_float,) * 2),
        'co2_params_calibrated': _co2,
        'co2_params': _co2,
        'co2_params_initial_guess': Parameters,
        'cycle_type': str,
        'cycle_name': str,
        'specific_gear_shifting': str,
        'calibration_status': Or(_e(list), list),
        'electric_load': _tuple((_float,) * 2),
        'engine_normalization_temperature_window': _tuple((_float,) * 2),
        'engine_temperature_regression_model': function,
        'engine_type': str,
        'full_load_curve': function,
        'gear_box_efficiency_constants': _dict,
        'gear_box_efficiency_parameters_cold_hot': _dict,
        'model_scores': _dict,
        'scores': _dict,
        'gear_box_ratios': _index_dict,
        'gear_box_type': str,
        'engine_is_turbo': _type,
        'has_start_stop': _type,
        'has_energy_recuperation': _type,
        'engine_has_variable_valve_actuation': _type,
        'has_thermal_management': _type,
        'engine_has_direct_injection': _type,
        'has_lean_burn': _type,
        'engine_has_cylinder_deactivation': _type,
        'has_exhausted_gas_recirculation': _type,
        'has_particle_filter': _type,
        'has_selective_catalytic_reduction': _type,
        'has_nox_storage_catalyst': _type,
        'is_cycle_hot': _type,
        'use_dt_gear_shifting': _type,

        'status_start_stop_activation_time': _type,
        'idle_engine_speed': _tuple((_float,) * 2),
        'k1': _int,
        'k2': _int,
        'k5': _int,
        'max_gear': _int,
        'n_dyno_axes': _int,
        'n_wheel_drive': _int,
        'road_loads': _tuple((_float,) * 3),
        'start_stop_model': function,
        'temperature_references': _tuple((_float,) * 2),
        'torque_converter_model': function,
        'velocity_speed_ratios': _index_dict,
        'phases_co2_emissions': _tuple(Or((_float,) * 2, (_float,) * 4)),

        'accelerations': _np_array(),
        'alternator_currents': _np_array(),
        'alternator_powers_demand': _np_array(),
        'alternator_statuses': _np_array(int),
        'auxiliaries_power_losses': _np_array(),
        'auxiliaries_torque_loss': _float,
        'auxiliaries_torque_losses': _np_array(),
        'battery_currents': _np_array(),
        'clutch_TC_powers': _np_array(),
        'clutch_TC_speeds_delta': _np_array(),
        'co2_emissions': _np_array(),
        'cold_start_speeds_delta': _np_array(),
        'engine_coolant_temperatures': _np_array(),
        'engine_powers_out': _np_array(),
        'engine_speeds_out': _np_array(),
        'engine_speeds_out_hot': _np_array(),
        'engine_starts': _np_array(bool),
        'final_drive_powers_in': _np_array(),
        'final_drive_speeds_in': _np_array(),
        'final_drive_torques_in': _np_array(),
        'fuel_consumptions': _np_array(),
        'full_load_powers': _np_array(),
        'full_load_speeds': _np_array(),
        'full_load_torques': _np_array(),
        'gear_box_efficiencies': _np_array(),
        'gear_box_powers_in': _np_array(),
        'gear_box_speeds_in': _np_array(),
        'gear_box_temperatures': _np_array(),
        'gear_box_torque_losses': _np_array(),
        'gear_box_torques_in': _np_array(),
        'gear_shifts': _np_array(bool),
        'gears': _np_array(int),
        'identified_co2_emissions': _np_array(),
        'motive_powers': _np_array(),
        'on_engine': _np_array(bool),
        'state_of_charges': _np_array(),
        'times': _np_array(),
        'velocities': _np_array(),
        'wheel_powers': _np_array(),
        'wheel_speeds': _np_array(),
        'wheel_torques': _np_array(),
        str: _float
    }

    return schema



engine_fuel_lower_heating_value = _positive()
fuel_carbon_content = _positive()
engine_capacity = _positive()
engine_stroke = _positive()
engine_max_power = _positive()
engine_max_speed_at_max_power = _positive()
engine_max_speed = _positive()
engine_max_torque = _positive()
idle_engine_speed_median = _positive()
engine_idle_fuel_consumption = _positive()
final_drive_ratio = _positive()
r_dynamic = _positive()
gear_box_type = _select(types=('manual', 'automatic'), error='Allowed gear_box_type: %s')
start_stop_activation_time = _positive()
alternator_nominal_voltage = _positive()
battery_capacity = _positive()
state_of_charge_balance = _limits()
state_of_charge_balance_window = _limits()
initial_state_of_charge  = _limits()
initial_temperature = _positive()
idle_engine_speed_std = _positive()
alternator_nominal_power = _positive()
alternator_efficiency = _limits(limits=(0, 1), error=None)
time_cold_hot_transition = _positive()
co2_params = _dict()
velocity_speed_ratios = _index_dict()
gear_box_ratios = _index_dict()
full_load_speeds = _np_array()
full_load_torques = _np_array()
full_load_powers = _np_array()

vehicle_mass = _positive()
f0_uncorrected = _positive()
f1 = _positive()
f2 = _positive()
f0 = _positive()
correct_f0 = _positive()

co2_emission_low = _positive()
co2_emission_medium = _positive()
co2_emission_high = _positive()
co2_emission_extra_high = _positive()

co2_emission_UDC = _positive()
co2_emission_EUDC = _positive()
co2_emission_value = _positive()
n_dyno_axes = _positive(type=int)
n_wheel_drive = _positive(type=int)

engine_is_turbo = _type(type=bool)
has_start_stop = _type(type=bool)
has_energy_recuperation = _type(type=bool)
engine_has_variable_valve_actuation = _type(type=bool)
has_thermal_management = _type(type=bool)
engine_has_direct_injection = _type(type=bool)
has_lean_burn = _type(type=bool)
engine_has_cylinder_deactivation = _type(type=bool)
has_exhausted_gas_recirculation = _type(type=bool)
has_particle_filter = _type(type=bool)
has_selective_catalytic_reduction = _type(type=bool)
has_nox_storage_catalyst = _type(type=bool)
has_torque_converter = _type(type=bool)
