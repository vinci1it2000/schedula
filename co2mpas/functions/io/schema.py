from schema import Schema, Use, And, Or, Optional

def define_data_schema():
    from ..co2mpas_model.physical.gear_box.AT_gear import CMV, MVL, GSPV
    from sklearn.tree import DecisionTreeClassifier
    from lmfit import Parameters
    import numpy

    def _function(f):
        assert callable(f)
        return f

    def _p(c):
        return Or(c, Use(c))

    def _e(c):
        return Or(And(eval, c), c)


    function = Use(_function)
    cmv, gspv, mvl = _p(CMV), _p(GSPV), _p(MVL)
    dtc = DecisionTreeClassifier
    _bool, _int, _float, _str = _p(bool), _p(int), _p(float), _p(str)

    def _np_array(t=float):
        return Use(lambda x: numpy.array(x, dtype=t))

    schema = Schema({
        Optional('CMV'): cmv,
        Optional('CMV_Cold_Hot'): _e({'hot': cmv, 'cold': cmv}),
        Optional('DT_VA'): dtc,
        Optional('DT_VAP'): dtc,
        Optional('DT_VAT'): dtc,
        Optional('DT_VATP'): dtc,
        Optional('GSPV'): gspv,
        Optional('GSPV_Cold_Hot'): _e({'hot': gspv, 'cold': gspv}),
        Optional('MVL'): mvl,
        Optional('VERSION'): _str,
        Optional('alternator_charging_currents'): _e((_float,) * 2),
        Optional('alternator_current_model'): function,
        Optional('alternator_status_model'): function,
        Optional('clutch_model'): function,
        Optional('co2_emissions_model'): function,
        Optional('co2_error_function_on_emissions'): function,
        Optional('co2_error_function_on_phases'): function,
        Optional('cold_start_speed_model'): function,
        Optional('clutch_window'): _e((_float,) * 2),
        Optional('co2_params_calibrated'): _e({str: _float}),
        Optional('co2_params_initial_guess'): Parameters,
        Optional('cycle_type'): str,
        Optional('electric_load'): _e((_float,) * 2),
        Optional('engine_is_turbo'): _bool,
        Optional('engine_normalization_temperature_window'): _e((_float,) * 2),
        Optional('engine_temperature_regression_model'): function,
        Optional('engine_type'): str,
        Optional('fuel_type'): str,
        Optional('full_load_curve'): function,
        Optional('gear_box_efficiency_constants'): dict,
        Optional('gear_box_efficiency_parameters_cold_hot'): dict,
        Optional('gear_box_ratios'): _e({_int: _float}),
        Optional('gear_box_type'): str,
        Optional('has_energy_recuperation'): _bool,
        Optional('is_cycle_hot'): _bool,
        Optional('idle_engine_speed'): _e((_float,) * 2),
        Optional('k1'): _int,
        Optional('k2'): _int,
        Optional('k5'): _int,
        Optional('max_gear'): _int,
        Optional('n_dyno_axes'): _int,
        Optional('n_wheel_drive'): _int,
        Optional('road_loads'): _e((_float,) * 3),
        Optional('start_stop_model'): function,
        Optional('temperature_references'): _e((_float,) * 2),
        Optional('torque_converter_model'): function,
        Optional('velocity_speed_ratios'): _e({_int: _float}),

        Optional('accelerations'): _np_array(),
        Optional('alternator_currents'): _np_array(),
        Optional('alternator_powers_demand'): _np_array(),
        Optional('alternator_statuses'): _np_array(int),
        Optional('auxiliaries_power_losses'): _np_array(),
        Optional('auxiliaries_torque_loss'): _float,
        Optional('auxiliaries_torque_losses'): _np_array(),
        Optional('battery_currents'): _np_array(),
        Optional('clutch_TC_powers'): _np_array(),
        Optional('clutch_TC_speeds_delta'): _np_array(),
        Optional('co2_emissions'): _np_array(),
        Optional('cold_start_speeds_delta'): _np_array(),
        Optional('engine_coolant_temperatures'): _np_array(),
        Optional('engine_powers_out'): _np_array(),
        Optional('engine_speeds_out'): _np_array(),
        Optional('engine_speeds_out_hot'): _np_array(),
        Optional('engine_starts'): _np_array(bool),
        Optional('final_drive_powers_in'): _np_array(),
        Optional('final_drive_speeds_in'): _np_array(),
        Optional('final_drive_torques_in'): _np_array(),
        Optional('fuel_consumptions'): _np_array(),
        Optional('full_load_powers'): _np_array(),
        Optional('full_load_speeds'): _np_array(),
        Optional('full_load_torques'): _np_array(),
        Optional('gear_box_efficiencies'): _np_array(),
        Optional('gear_box_powers_in'): _np_array(),
        Optional('gear_box_speeds_in'): _np_array(),
        Optional('gear_box_temperatures'): _np_array(),
        Optional('gear_box_torque_losses'): _np_array(),
        Optional('gear_box_torques_in'): _np_array(),
        Optional('gear_shifts'): _np_array(bool),
        Optional('gears'): _np_array(int),
        Optional('identified_co2_emissions'): _np_array(),
        Optional('motive_powers'): _np_array(),
        Optional('on_engine'): _np_array(bool),
        Optional('phases_co2_emissions'): _np_array(),
        Optional('state_of_charges'): _np_array(),
        Optional('times'): _np_array(),
        Optional('velocities'): _np_array(),
        Optional('wheel_powers'): _np_array(),
        Optional('wheel_speeds'): _np_array(),
        Optional('wheel_torques'): _np_array(),
        Optional(str): _float
    })

    return schema