from schema import Schema, Use, And, Or, Optional, SchemaError
import numpy as np
import co2mpas.dispatcher.utils as dsp_utl
from .. import _iter_d, _get
from ..co2mpas_model.physical.gear_box.AT_gear import CMV, MVL, GSPV
from sklearn.tree import DecisionTreeClassifier
from lmfit import Parameters, Parameter
from collections import Iterable, OrderedDict


def validate_data(data, read_schema):
    res = {}
    validate = read_schema.validate
    for k, v in _iter_d(data, depth=3):
        v = {i: j for i, j in validate(v).items() if j is not dsp_utl.NONE}
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


def _function(error=None, read=True, **kwargs):
    def _check_function(f):
        assert callable(f)
        return f
    if read:
        return Use(_check_function, error=error)
    return And(_function(), Use(lambda x: dsp_utl.NONE), error=error)


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
        return And(_np_array(dtype=dtype), Use(lambda x: x.tolist()),
                   error=error)


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
    cmv = _cmv(read=read)
    dtc = _dtc(read=read)
    gspv = _gspv(read=read)
    string = _string(read=read)
    positive = _positive(read=read)
    positive_int = _positive(type=int, read=read)
    limits = _limits(read=read)
    index_dict = _index_dict(read=read)
    np_array = _np_array(read=read)
    np_array_bool = _np_array(dtype=bool, read=read)
    np_array_int = _np_array(dtype=int, read=read)
    _bool = _type(type=bool, read=read)
    function = _function(read=read)
    tuplefloat2 = _type(type=And(Use(tuple), (float,)), length=2, read=read)
    dictstrdict = _dict(format={str: dict}, read=read)
    parameters = _parameters(read=read)
    schema = {
        'CMV': cmv,
        'CMV_Cold_Hot': _dict(format={'hot': cmv, 'cold': cmv}, read=read),
        'DT_VA': dtc,
        'DT_VAP': dtc,
        'DT_VAT': dtc,
        'DT_VATP': dtc,
        'GSPV': gspv,
        'GSPV_Cold_Hot': _dict(format={'hot': gspv, 'cold': gspv}, read=read),
        'MVL': _mvl(read=read),

        'VERSION': string,
        'fuel_type': _select(types=('gasoline', 'diesel'),
                             error='Allowed fuel_type: %s',
                             read=read),
        'engine_fuel_lower_heating_value': positive,
        'fuel_carbon_content': positive,
        'engine_capacity': positive,
        'engine_stroke': positive,
        'engine_max_power': positive,
        'engine_max_speed_at_max_power': positive,
        'engine_max_speed': positive,
        'engine_max_torque': positive,
        'idle_engine_speed_median': positive,
        'engine_idle_fuel_consumption': positive,
        'final_drive_ratio': positive,
        'r_dynamic': positive,
        'gear_box_type': _select(types=('manual', 'automatic'),
                                 error='Allowed gear_box_type: %s',
                                 read=read),
        'start_stop_activation_time': positive,
        'alternator_nominal_voltage': positive,
        'battery_capacity': positive,
        'state_of_charge_balance': limits,
        'state_of_charge_balance_window': limits,
        'initial_state_of_charge ': limits,
        'initial_temperature': positive,
        'idle_engine_speed_std': positive,
        'alternator_nominal_power': positive,
        'alternator_efficiency': _limits(limits=(0, 1), read=read),
        'time_cold_hot_transition': positive,
        'co2_params': _dict(format={str: float}),
        'velocity_speed_ratios': index_dict,
        'gear_box_ratios': index_dict,
        'full_load_speeds': np_array,
        'full_load_torques': np_array,
        'full_load_powers': np_array,
        
        'vehicle_mass': positive,
        'f0_uncorrected': positive,
        'f1': positive,
        'f2': positive,
        'f0': positive,
        'correct_f0': positive,
        
        'co2_emission_low': positive,
        'co2_emission_medium': positive,
        'co2_emission_high': positive,
        'co2_emission_extra_high': positive,
        
        'co2_emission_UDC': positive,
        'co2_emission_EUDC': positive,
        'co2_emission_value': positive,
        'n_dyno_axes': positive_int,
        'n_wheel_drive': positive_int,
        
        'engine_is_turbo': _bool,
        'has_start_stop': _bool,
        'has_energy_recuperation': _bool,
        'engine_has_variable_valve_actuation': _bool,
        'has_thermal_management': _bool,
        'engine_has_direct_injection': _bool,
        'has_lean_burn': _bool,
        'engine_has_cylinder_deactivation': _bool,
        'has_exhausted_gas_recirculation': _bool,
        'has_particle_filter': _bool,
        'has_selective_catalytic_reduction': _bool,
        'has_nox_storage_catalyst': _bool,
        'has_torque_converter': _bool,
        'is_cycle_hot': _bool,
        'use_dt_gear_shifting': _bool,

        'alternator_charging_currents': tuplefloat2,
        'alternator_current_model': function,
        'alternator_status_model': function,
        'clutch_model': function,
        'co2_emissions_model': function,
        'co2_error_function_on_emissions': function,
        'co2_error_function_on_phases': function,
        'cold_start_speed_model': function,
        'clutch_window': tuplefloat2,
        'co2_params_calibrated': parameters,
        'co2_params_initial_guess': parameters,
        'cycle_type': string,
        'cycle_name': string,
        'specific_gear_shifting': string,
        'calibration_status': _type(type=And(Use(list), [(bool, OrderedDict)]),
                                    length=4,
                                    read=read),
        'electric_load': tuplefloat2,
        'engine_normalization_temperature_window': tuplefloat2,
        'engine_temperature_regression_model': function,
        'engine_type': string,
        'full_load_curve': function,
        'gear_box_efficiency_constants': dictstrdict,
        'gear_box_efficiency_parameters_cold_hot': dictstrdict,
        'model_scores': dictstrdict,
        'scores': dictstrdict,

        'status_start_stop_activation_time': positive,
        'idle_engine_speed': tuplefloat2,
        'k1': positive_int,
        'k2': positive_int,
        'k5': positive_int,
        'max_gear': positive_int,
        
        'road_loads': _type(type=And(Use(tuple), (float,)),
                            length=3,
                            read=read),
        'start_stop_model': function,
        'temperature_references': tuplefloat2,
        'torque_converter_model': function,
        'phases_co2_emissions': _type(type=And(Use(tuple), (float,)),
                                      length=(2, 4),
                                      read=read),

        'accelerations': np_array,
        'alternator_currents': np_array,
        'alternator_powers_demand': np_array,
        'alternator_statuses': np_array_int,
        'auxiliaries_power_losses': np_array,
        'auxiliaries_torque_loss': positive,
        'auxiliaries_torque_losses': np_array,
        'battery_currents': np_array,
        'clutch_tc_powers': np_array,
        'clutch_tc_speeds_delta': np_array,
        'co2_emissions': np_array,
        'cold_start_speeds_delta': np_array,
        'engine_coolant_temperatures': np_array,
        'engine_powers_out': np_array,
        'engine_speeds_out': np_array,
        'engine_speeds_out_hot': np_array,
        'engine_starts': np_array_bool,
        'engine_loads': np_array,
        'final_drive_powers_in': np_array,
        'final_drive_speeds_in': np_array,
        'final_drive_torques_in': np_array,
        'fuel_consumptions': np_array,
        'gear_box_efficiencies': np_array,
        'gear_box_powers_in': np_array,
        'gear_box_speeds_in': np_array,
        'gear_box_temperatures': np_array,
        'gear_box_torque_losses': np_array,
        'gear_box_torques_in': np_array,
        'gear_shifts': np_array_bool,
        'gears': np_array_int,
        'identified_co2_emissions': np_array,
        'motive_powers': np_array,
        'on_engine': np_array_bool,
        'state_of_charges': np_array,
        'times': np_array,
        'velocities': np_array,
        'wheel_powers': np_array,
        'wheel_speeds': np_array,
        'wheel_torques': np_array,

    }

    schema = {Optional(k): Or(Empty(), v) for k, v in schema.items()}
    schema[Optional(str)] = _type(type=float, read=read)

    if not read:
        f = lambda x: x is dsp_utl.NONE
        schema = {k: And(v, Or(f, Use(str))) for k, v in schema.items()}

    return Schema(schema)
