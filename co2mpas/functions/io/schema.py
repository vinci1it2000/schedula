from schema import Schema, Use, And, Or, Optional, SchemaError
import numpy as np
import co2mpas.dispatcher.utils as dsp_utl
from .. import _iter_d, _get
from ..co2mpas_model.physical.gear_box.AT_gear import CMV, MVL, GSPV
from sklearn.tree import DecisionTreeClassifier
from lmfit import Parameters, Parameter
from collections import Iterable, OrderedDict


def validate_data(data, read=True):
    res = {}

    schema = define_data_schema(read=read)

    for k, v in _iter_d(data, depth=3):
        v = schema.validate(v)
        v = {i: j for i, j in v.items() if j is not dsp_utl.NONE}
        _get(res, *k[:-1])[k[-1]] = v

    return res


class Empty(object):
    def __repr__(self):
        return '%s' % self.__class__.__name__

    def validate(self, data):
        try:
            empty = not (data or data == 0)
        except ValueError:
            empty = np.isnan(data).all()

        if empty:
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


def _check_positive(x):
    return x >= 0


def _positive(type=float, error=None, **kwargs):
    return And(Use(type), _check_positive, error=error)


def _limits(limits=(0, 100), error=None, **kwargs):
    _check_limits = lambda x: limits[0] <= x <= limits[1]
    return And(Use(float), _check_limits, error=error)


def _eval(s, error=None, **kwargs):
    return Or(And(str, Use(lambda x: eval(x)), s), s, error=error)


def _dict(format=None, error=None, **kwargs):
    format = format or {int: float}
    c = Use(lambda x: {k: v for k, v in dict(x).items() if v})
    return _eval(Or(Empty(), And(c, Or(Empty(), format))), error=error)


def _check_length(length):
    if not isinstance(length, Iterable):
        length = (length,)

    def check_length(data):
        ld = len(data)
        return any(ld == l for l in length)

    return check_length


def _type(type=None, error=None, length=None, **kwargs):
    type = type or tuple
    if length is not None:
        return And(_type(type=type), _check_length(length), error=error)
    if not isinstance(type, (Use, Schema, And, Or)):
        type = Or(type, Use(type))
    return _eval(type, error=error)


def _index_dict(error=None, **kwargs):
    c = {int: Use(float)}
    f = lambda x: {k: v for k, v in enumerate(x, start=1)}
    return Or(c, And(_dict(), c), And(_type(), Use(f), c), error=error)


def _np_array(dtype=None, error=None, read=True, **kwargs):
    if read:
        c = Use(lambda x: np.asarray(x, dtype=dtype))
        return And(Or(c, And(_type(), c), Empty()), error=error)
    else:
        return And(_np_array(dtype=dtype), Use(lambda x: x.tolist()), error=error)


def _cmv(error=None, **kwargs):
    return _type(type=CMV)


def _mvl(error=None, **kwargs):
    return _type(type=MVL)


def _gspv(error=None, **kwargs):
    return _type(type=GSPV)


def _dtc(error=None, **kwargs):
    return _type(type=DecisionTreeClassifier)


def _parameters2str(data):
    if isinstance(data, Parameters):
        s = []
        for k, v in data.items():
            s.append("('%s', %s)" % (k, _parameters2str(v)))
        return 'Parameters(None, OrderedDict([%s]))' % ', '.join(s)
    elif isinstance(data, Parameter):
        d = {
            'name': "'%s'" % data.name,
            'vary': data.vary,
            'max': data.max,
            'min': data.min,
            'expr': "'%s'" % data._expr if data._expr else 'None',
            'value': data._val
         }
        return 'Parameter(%s)' % ', '.join('%s=%s' % v for v in d.items())


def _parameters(error=None, read=True):
    if read:
        return _type(type=Schema(Parameters), error=error)
    else:
        return And(_parameters(), Use(_parameters2str), error=error)


def define_data_schema(read=True):
    schema = {
        'CMV': _cmv(read=read),
        'CMV_Cold_Hot': _dict(format={'hot': _cmv(read=read),
                                      'cold': _cmv(read=read)}, read=read),
        'DT_VA': _dtc(read=read),
        'DT_VAP': _dtc(read=read),
        'DT_VAT': _dtc(read=read),
        'DT_VATP': _dtc(read=read),
        'GSPV': _gspv(read=read),
        'GSPV_Cold_Hot': _dict(format={'hot': _gspv(read=read),
                                       'cold': _gspv(read=read)}, read=read),
        'MVL': _mvl(read=read),

        'VERSION': _string(error='VERSION should be a string.', read=read),
        'fuel_type': _select(types=('gasoline', 'diesel'),
                             error='Allowed fuel_type: %s',
                             read=read),
        'engine_fuel_lower_heating_value': _positive(read=read),
        'fuel_carbon_content': _positive(read=read),
        'engine_capacity': _positive(read=read),
        'engine_stroke': _positive(read=read),
        'engine_max_power': _positive(read=read),
        'engine_max_speed_at_max_power': _positive(read=read),
        'engine_max_speed': _positive(read=read),
        'engine_max_torque': _positive(read=read),
        'idle_engine_speed_median': _positive(read=read),
        'engine_idle_fuel_consumption': _positive(read=read),
        'final_drive_ratio': _positive(read=read),
        'r_dynamic': _positive(read=read),
        'gear_box_type': _select(types=('manual', 'automatic'),
                                 error='Allowed gear_box_type: %s',
                                 read=read),
        'start_stop_activation_time': _positive(read=read),
        'alternator_nominal_voltage': _positive(read=read),
        'battery_capacity': _positive(read=read),
        'state_of_charge_balance': _limits(read=read),
        'state_of_charge_balance_window': _limits(read=read),
        'initial_state_of_charge ': _limits(read=read),
        'initial_temperature': _positive(read=read),
        'idle_engine_speed_std': _positive(read=read),
        'alternator_nominal_power': _positive(read=read),
        'alternator_efficiency': _limits(limits=(0, 1), read=read),
        'time_cold_hot_transition': _positive(read=read),
        'co2_params': _dict(format={str: float}),
        'velocity_speed_ratios': _index_dict(read=read),
        'gear_box_ratios': _index_dict(read=read),
        'full_load_speeds': _np_array(read=read),
        'full_load_torques': _np_array(read=read),
        'full_load_powers': _np_array(read=read),
        
        'vehicle_mass': _positive(read=read),
        'f0_uncorrected': _positive(read=read),
        'f1': _positive(read=read),
        'f2': _positive(read=read),
        'f0': _positive(read=read),
        'correct_f0': _positive(read=read),
        
        'co2_emission_low': _positive(read=read),
        'co2_emission_medium': _positive(read=read),
        'co2_emission_high': _positive(read=read),
        'co2_emission_extra_high': _positive(read=read),
        
        'co2_emission_UDC': _positive(read=read),
        'co2_emission_EUDC': _positive(read=read),
        'co2_emission_value': _positive(read=read),
        'n_dyno_axes': _positive(type=int, read=read),
        'n_wheel_drive': _positive(type=int, read=read),
        
        'engine_is_turbo': _type(type=bool, read=read),
        'has_start_stop': _type(type=bool, read=read),
        'has_energy_recuperation': _type(type=bool, read=read),
        'engine_has_variable_valve_actuation': _type(type=bool, read=read),
        'has_thermal_management': _type(type=bool, read=read),
        'engine_has_direct_injection': _type(type=bool, read=read),
        'has_lean_burn': _type(type=bool, read=read),
        'engine_has_cylinder_deactivation': _type(type=bool, read=read),
        'has_exhausted_gas_recirculation': _type(type=bool, read=read),
        'has_particle_filter': _type(type=bool, read=read),
        'has_selective_catalytic_reduction': _type(type=bool, read=read),
        'has_nox_storage_catalyst': _type(type=bool, read=read),
        'has_torque_converter': _type(type=bool, read=read),
        'is_cycle_hot': _type(type=bool, read=read),
        'use_dt_gear_shifting': _type(type=bool, read=read),

        'alternator_charging_currents': _type(length=2, read=read),
        'alternator_current_model': _function(read=read),
        'alternator_status_model': _function(read=read),
        'clutch_model': _function(read=read),
        'co2_emissions_model': _function(read=read),
        'co2_error_function_on_emissions': _function(read=read),
        'co2_error_function_on_phases': _function(read=read),
        'cold_start_speed_model': _function(read=read),
        'clutch_window': _type(type=And(Use(tuple), (float,)),
                               length=2,
                               read=read),
        'co2_params_calibrated': _parameters(read=read),
        'co2_params_initial_guess': _parameters(read=read),
        'cycle_type': _type(type=str, read=read),
        'cycle_name': _type(type=str, read=read),
        'specific_gear_shifting': _type(type=str, read=read),
        'calibration_status': _type(type=And(Use(list), [(bool, OrderedDict)]),
                                    length=4,
                                    read=read),
        'electric_load': _type(type=And(Use(tuple), (float,)),
                               length=2,
                               read=read),
        'engine_normalization_temperature_window': _type(
                type=And(Use(tuple), (float,)),
                length=2,
                read=read),
        'engine_temperature_regression_model': _function(read=read),
        'engine_type': _type(type=str, read=read),
        'full_load_curve': _function(read=read),
        'gear_box_efficiency_constants': _dict(read=read),
        'gear_box_efficiency_parameters_cold_hot': _dict(read=read),
        'model_scores': _dict(format={str: dict}, read=read),
        'scores': _dict(format={str: dict}, read=read),

        'status_start_stop_activation_time': _positive(read=read),
        'idle_engine_speed': _type(type=And(Use(tuple), (float,)),
                                   length=2,
                                   read=read),
        'k1': _positive(type=int, read=read),
        'k2': _positive(type=int, read=read),
        'k5': _positive(type=int, read=read),
        'max_gear': _positive(type=int, read=read),
        
        'road_loads': _type(type=And(Use(tuple), (float,)),
                            length=3,
                            read=read),
        'start_stop_model': _function(read=read),
        'temperature_references': _type(type=And(Use(tuple), (float,)),
                                        length=2,
                                        read=read),
        'torque_converter_model': _function(read=read),
        'phases_co2_emissions': _type(type=And(Use(tuple), (float,)),
                                      length=(2, 4),
                                      read=read),

        'accelerations': _np_array(read=read),
        'alternator_currents': _np_array(read=read),
        'alternator_powers_demand': _np_array(read=read),
        'alternator_statuses': _np_array(dtype=int, read=read),
        'auxiliaries_power_losses': _np_array(read=read),
        'auxiliaries_torque_loss': _positive(read=read),
        'auxiliaries_torque_losses': _np_array(read=read),
        'battery_currents': _np_array(read=read),
        'clutch_tc_powers': _np_array(read=read),
        'clutch_tc_speeds_delta': _np_array(read=read),
        'co2_emissions': _np_array(read=read),
        'cold_start_speeds_delta': _np_array(read=read),
        'engine_coolant_temperatures': _np_array(read=read),
        'engine_powers_out': _np_array(read=read),
        'engine_speeds_out': _np_array(read=read),
        'engine_speeds_out_hot': _np_array(read=read),
        'engine_starts': _np_array(dtype=bool, read=read),
        'engine_loads': _np_array(read=read),
        'final_drive_powers_in': _np_array(read=read),
        'final_drive_speeds_in': _np_array(read=read),
        'final_drive_torques_in': _np_array(read=read),
        'fuel_consumptions': _np_array(read=read),
        'gear_box_efficiencies': _np_array(read=read),
        'gear_box_powers_in': _np_array(read=read),
        'gear_box_speeds_in': _np_array(read=read),
        'gear_box_temperatures': _np_array(read=read),
        'gear_box_torque_losses': _np_array(read=read),
        'gear_box_torques_in': _np_array(read=read),
        'gear_shifts': _np_array(dtype=bool, read=read),
        'gears': _np_array(dtype=int, read=read),
        'identified_co2_emissions': _np_array(read=read),
        'motive_powers': _np_array(read=read),
        'on_engine': _np_array(dtype=bool),
        'state_of_charges': _np_array(read=read),
        'times': _np_array(read=read),
        'velocities': _np_array(read=read),
        'wheel_powers': _np_array(read=read),
        'wheel_speeds': _np_array(read=read),
        'wheel_torques': _np_array(read=read),

    }
    schema = {Optional(k): Or(Empty(), v) for k, v in schema.items()}
    schema[Optional(str)] = _type(type=float, read=read)
    return Schema(schema)
