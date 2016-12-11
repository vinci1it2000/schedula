# -*- coding: utf-8 -*-
#
# Copyright 2015-2016 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It contains functions to predict the CO2 emissions.
"""

import copy
import functools
import itertools
import lmfit
import numpy as np
import numpy.ma as ma
import scipy.integrate as sci_itg
import scipy.stats as sci_sta
import sklearn.metrics as sk_met
import co2mpas.dispatcher.utils as dsp_utl
import co2mpas.dispatcher as dsp
import co2mpas.utils as co2_utl
import co2mpas.model.physical.defaults as defaults


def default_fuel_density(fuel_type):
    """
    Returns the default fuel density [g/l].

    :param fuel_type:
        Fuel type (diesel, gasoline, LPG, NG, ethanol, biodiesel).
    :type fuel_type: str

    :return:
        Fuel density [g/l].
    :rtype: float
    """

    return defaults.dfl.functions.default_fuel_density.FUEL_DENSITY[fuel_type]


def default_fuel_carbon_content(fuel_type):
    """
    Returns the default fuel carbon content [CO2g/g].

    :param fuel_type:
        Fuel type (diesel, gasoline, LPG, NG, ethanol, biodiesel).
    :type fuel_type: str

    :return:
        Fuel carbon content [CO2g/g].
    :rtype: float
    """
    CC = defaults.dfl.functions.default_fuel_carbon_content.CARBON_CONTENT
    return CC[fuel_type]


def default_engine_fuel_lower_heating_value(fuel_type):
    """
    Returns the default fuel lower heating value [kJ/kg].

    :param fuel_type:
        Fuel type (diesel, gasoline, LPG, NG, ethanol, biodiesel).
    :type fuel_type: str

    :return:
        Fuel lower heating value [kJ/kg].
    :rtype: float
    """
    LHV = defaults.dfl.functions.default_fuel_lower_heating_value.LHV
    return LHV[fuel_type]


def calculate_fuel_carbon_content(fuel_carbon_content_percentage):
    """
    Calculates the fuel carbon content as CO2g/g.

    :param fuel_carbon_content_percentage:
        Fuel carbon content [%].
    :type fuel_carbon_content_percentage: float

    :return:
        Fuel carbon content [CO2g/g].
    :rtype: float
    """
    return fuel_carbon_content_percentage / 100.0 * 44.0 / 12.0


def calculate_fuel_carbon_content_percentage(fuel_carbon_content):
    """
    Calculates the fuel carbon content as %.

    :param fuel_carbon_content:
        Fuel carbon content [CO2g/g].
    :type fuel_carbon_content: float

    :return:
        Fuel carbon content [%].
    :rtype: float
    """

    return fuel_carbon_content / calculate_fuel_carbon_content(1.0)


def calculate_normalized_engine_coolant_temperatures(
        engine_coolant_temperatures, temperature_target):
    """
    Calculates the normalized engine coolant temperatures [-].

    ..note::
        Engine coolant temperatures are first converted in kelvin and then
        normalized. The results is between ``[0, 1]``.

    :param engine_coolant_temperatures:
        Engine coolant temperature vector [°C].
    :type engine_coolant_temperatures: numpy.array

    :param temperature_target:
        Normalization temperature [°C].
    :type temperature_target: float

    :return:
        Normalized engine coolant temperature [-].
    :rtype: numpy.array
    """

    i = np.searchsorted(engine_coolant_temperatures, (temperature_target,))[0]
    # Only flatten-out hot-part if `max-theta` is above `trg`.
    T = np.ones_like(engine_coolant_temperatures, dtype=float)
    T[:i] = engine_coolant_temperatures[:i] + 273.0
    T[:i] /= temperature_target + 273.0

    return T


def calculate_brake_mean_effective_pressures(
        engine_speeds_out, engine_powers_out, engine_capacity,
        min_engine_on_speed):
    """
    Calculates engine brake mean effective pressure [bar].

    :param engine_speeds_out:
        Engine speed vector [RPM].
    :type engine_speeds_out: numpy.array

    :param engine_powers_out:
        Engine power vector [kW].
    :type engine_powers_out: numpy.array

    :param engine_capacity:
        Engine capacity [cm3].
    :type engine_capacity: float

    :param min_engine_on_speed:
        Minimum engine speed to consider the engine to be on [RPM].
    :type min_engine_on_speed: float

    :return:
        Engine brake mean effective pressure vector [bar].
    :rtype: numpy.array
    """

    b = engine_speeds_out > min_engine_on_speed

    p = np.zeros_like(engine_powers_out)
    p[b] = engine_powers_out[b] / engine_speeds_out[b]
    p[b] *= 1200000.0 / engine_capacity

    return np.nan_to_num(p)


class IdleFuelConsumptionModel(object):
    def __init__(self, fc=None):
        self.fc = fc
        self.n_s = None
        self.c = None
        self.fmep_model = None

    def fit(self, idle_engine_speed, engine_capacity, engine_stroke, lhv,
            fmep_model):
        idle = idle_engine_speed[0]
        from . import calculate_mean_piston_speeds
        self.n_s = calculate_mean_piston_speeds(idle, engine_stroke)
        self.c = idle * (engine_capacity / (lhv * 1200))
        self.fmep_model = fmep_model
        return self

    def consumption(self, params=None, ac_phases=None):
        if isinstance(params, lmfit.Parameters):
            params = params.valuesdict()

        if self.fc is not None:
            ac = params.get('acr', self.fmep_model.base_acr)
            avv = params.get('avv', 0)
            lb = params.get('lb', 0)
            egr = params.get('egr', 0)
            fc = self.fc
        else:
            fc, _, ac, avv, lb, egr = self.fmep_model(params, self.n_s, 0, 1)

            if not (ac_phases is None or ac_phases.all() or 'acr' in params):
                p = params.copy()
                p['acr'] = self.fmep_model.base_acr
                _fc, _, _ac, _avv, _lb, _egr = self.fmep_model(p, self.n_s, 0, 1)
                fc = np.where(ac_phases, fc, _fc)
                ac = np.where(ac_phases, ac, _ac)
                avv = np.where(ac_phases, avv, _avv)
                lb = np.where(ac_phases, lb, _lb)
                egr = np.where(ac_phases, egr, _egr)

            fc *= self.c  # [g/sec]
        return fc, ac, avv, lb, egr


def define_idle_fuel_consumption_model(
        idle_engine_speed, engine_capacity, engine_stroke,
        engine_fuel_lower_heating_value, fmep_model,
        idle_fuel_consumption=None):
    """
    Defines the idle fuel consumption model.

    :param idle_engine_speed:
        Engine speed idle median and std [RPM].
    :type idle_engine_speed: (float, float)

    :param engine_capacity:
        Engine capacity [cm3].
    :type engine_capacity: float

    :param engine_stroke:
        Engine stroke [mm].
    :type engine_stroke: float

    :param engine_fuel_lower_heating_value:
        Fuel lower heating value [kJ/kg].
    :type engine_fuel_lower_heating_value: float

    :param fmep_model:
        Engine FMEP model.
    :type fmep_model: FMEP

    :param idle_fuel_consumption:
        Fuel consumption at hot idle engine speed [g/s].
    :type idle_fuel_consumption: float, optional

    :return:
        Idle fuel consumption model.
    :rtype: IdleFuelConsumptionModel
    """

    model = IdleFuelConsumptionModel(idle_fuel_consumption).fit(
        idle_engine_speed, engine_capacity, engine_stroke,
        engine_fuel_lower_heating_value, fmep_model
    )

    return model


def calculate_engine_idle_fuel_consumption(
        idle_fuel_consumption_model, params=None):
    """
    Calculates fuel consumption at hot idle engine speed [g/s].

    :param idle_fuel_consumption_model:
        Idle fuel consumption model.
    :type idle_fuel_consumption_model: IdleFuelConsumptionModel

    :param params:
        CO2 emission model parameters (a2, b2, a, b, c, l, l2, t, trg).

        The missing parameters are set equal to zero.
    :type params: dict

    :return:
        Fuel consumption at hot idle engine speed [g/s].
    :rtype: float
    """

    return idle_fuel_consumption_model.consumption(params)[0]


class FMEP(object):
    def __init__(self, full_bmep_curve, active_cylinder_ratios=(1.0,),
                 has_cylinder_deactivation=False,
                 acr_full_bmep_curve_percentage=0.5,
                 acr_max_mean_piston_speeds=12.0,
                 has_variable_valve_actuation=False,
                 has_lean_burn=False,
                 lb_max_mean_piston_speeds=12.0,
                 lb_full_bmep_curve_percentage=0.4,
                 has_exhausted_gas_recirculation=False,
                 has_selective_catalytic_reduction=False,
                 egr_max_mean_piston_speeds=12.0,
                 egr_full_bmep_curve_percentage=0.7,
                 engine_type=None):

        if active_cylinder_ratios:
            self.base_acr = max(active_cylinder_ratios)
        else:
            self.base_acr = 1.0
        self.active_cylinder_ratios = set(active_cylinder_ratios)
        self.active_cylinder_ratios -= {self.base_acr}
        self.fbc = full_bmep_curve

        self.has_cylinder_deactivation = has_cylinder_deactivation
        self.acr_max_mean_piston_speeds = float(acr_max_mean_piston_speeds)
        self.acr_fbc_percentage = acr_full_bmep_curve_percentage

        self.has_variable_valve_actuation = has_variable_valve_actuation

        self.has_lean_burn = has_lean_burn
        self.lb_max_mean_piston_speeds = float(lb_max_mean_piston_speeds)
        self.lb_fbc_percentage = lb_full_bmep_curve_percentage
        self.lb_n_temp_min = 0.5

        self.has_exhausted_gas_recirculation = has_exhausted_gas_recirculation
        self.has_selective_catalytic_reduction = has_selective_catalytic_reduction
        self.egr_max_mean_piston_speeds = float(egr_max_mean_piston_speeds)
        self.egr_fbc_percentage = egr_full_bmep_curve_percentage
        self.engine_type = engine_type

    def vva(self, params, n_powers, a=None):
        a = a or {}
        if self.has_variable_valve_actuation and 'vva' not in params:
            a['vva'] = ((0, True), (1, n_powers >= 0))
        return a

    def lb(self, params, n_speeds, n_powers, n_temp, a=None):
        a = a or {}
        if self.has_lean_burn and 'lb' not in params:
            b = n_temp >= self.lb_n_temp_min
            b &= n_speeds < self.lb_max_mean_piston_speeds
            b &= n_powers <= (self.fbc(n_speeds) * self.lb_fbc_percentage)
            a['lb'] = ((0, True), (1, b))
        return a

    def egr(self, params, n_speeds, n_powers, n_temp, a=None):
        a = a or {}
        if self.has_exhausted_gas_recirculation and 'egr' not in params:
            #b = n_speeds < self.egr_max_mean_piston_speeds
            #b &= n_powers <= (self.fbc(n_speeds) * self.egr_fbc_percentage)
            k = self.engine_type, self.has_selective_catalytic_reduction
            egr = defaults.dfl.functions.FMEP_egr.egr_fact_map[k]
            if k[0] == 'compression':
                if k[1]:
                    b = n_temp < 1
                else:
                    b = n_speeds < self.egr_max_mean_piston_speeds
                    b &= n_powers <= (self.fbc(n_speeds) * self.egr_fbc_percentage)

                if b is True:
                    a['egr'] = (egr, True),
                elif b is False:
                    a['egr'] = (0, True),
                else:
                    a['egr'] = (np.where(b, egr, 0), True),
            else:
                a['egr'] = ((0, True), (egr, True))

        return a

    def acr(self, params, n_speeds, n_powers, n_temp, a=None):
        a = a or {'acr': [(self.base_acr, True)]}
        if self.has_cylinder_deactivation and self.active_cylinder_ratios and \
                        'acr' not in params:
            l = a['acr']
            b = (n_temp == 1) & (n_powers > 0)
            b &= (n_speeds < self.acr_max_mean_piston_speeds)
            ac = n_powers / (self.fbc(n_speeds) * self.acr_fbc_percentage)
            for acr in sorted(self.active_cylinder_ratios):
                l.append((acr, b & (ac < acr)))
        return a

    @staticmethod
    def _check_combinations(a):
        out = {}
        for k, v in a.items():
            for i in v:
                try:
                    if i[1] is True or i[1].any():
                        dsp_utl.get_nested_dicts(out, k, default=list).append(i)
                except AttributeError:
                    pass
        return out

    def combination(self, params, n_speeds, n_powers, n_temp):
        a = self.acr(params, n_speeds, n_powers, n_temp)
        a = self.lb(params, n_speeds, n_powers, n_temp, a=a)
        a = self.vva(params, n_powers, a=a)
        a = self.egr(params, n_speeds, n_powers, n_temp, a=a)
        a = self._check_combinations(a)

        keys, c = zip(*sorted(a.items()))
        p = params.copy()
        p.update({
            'n_speeds': n_speeds,
            'n_powers': n_powers,
            'n_temperatures': n_temp
        })
        for s in itertools.product(*c):
            b, d = True, {}

            for k, (v, n) in zip(keys, s):
                b &= n
                d[k] = v
            try:
                if b is False or not b.any():
                    continue
                if b.all():
                    b = True
            except AttributeError:
                pass

            p.update(d)
            yield {k: self.g(v, b) for k, v in p.items()}, d, b

    @staticmethod
    def g(data, b):
        if b is not True:
            try:
                return ma.masked_where(~b, data, copy=False)
            except (IndexError, TypeError):
                pass
        return data

    def __call__(self, params, n_speeds, n_powers, n_temp):
        it = self.combination(params, n_speeds, n_powers, n_temp)
        s = None
        for p, d, n in it:
            d['fmep'], d['v'] = _calculate_fc(*_fuel_ABC(**p))
            if s is None:
                s = d
            else:
                b = d['fmep'] < s['fmep']
                if n is True and b is True:
                    s = d
                elif b is not False:
                    n &= b
                    if n.all():
                        s = d
                    elif n.any():
                        for k, v in d.items():
                            s[k] = np.where(n, v, s[k])

        acr = s.get('acr', params.get('acr', self.base_acr))
        vva = s.get('vva', params.get('vva', 0))
        lb = s.get('lb', params.get('lb', 0))
        egr = s.get('egr', params.get('egr', 0))

        return s['fmep'], s['v'], acr, vva, lb, egr


def define_fmep_model(
    full_bmep_curve, engine_max_speed, engine_stroke, active_cylinder_ratios,
    has_cylinder_deactivation, has_variable_valve_actuation, has_lean_burn,
    has_exhausted_gas_recirculation, has_selective_catalytic_reduction,
    engine_type):
    """
    Defines the vehicle FMEP model.

    :param full_bmep_curve:
        Vehicle full bmep curve.
    :type full_bmep_curve: scipy.interpolate.InterpolatedUnivariateSpline

    :param engine_max_speed:
        Maximum allowed engine speed [RPM].
    :type engine_max_speed: float

    :param engine_stroke:
        Engine stroke [mm].
    :type engine_stroke: float

    :param active_cylinder_ratios:
        Possible active cylinder ratios [-].
    :type active_cylinder_ratios: tuple[float]

    :param has_cylinder_deactivation:
        Does the engine have cylinder deactivation technology?
    :type has_cylinder_deactivation: bool

    :param has_variable_valve_actuation:
        Does the engine feature variable valve actuation? [-].
    :type has_variable_valve_actuation: bool

    :param has_lean_burn:
        Does the engine have lean burn technology?
    :type has_lean_burn: bool

    :param has_exhausted_gas_recirculation:
        Does the engine have exhaust gas recirculation technology?
    :type has_exhausted_gas_recirculation: bool

    :param has_selective_catalytic_reduction:
        Does the engine have selective catalytic reduction technology?
    :type has_selective_catalytic_reduction: bool

    :param engine_type:
        Engine type (positive turbo, positive natural aspiration, compression).
    :type engine_type: str

    :return:
        Vehicle FMEP model.
    :rtype: FMEP
    """

    dfl = defaults.dfl.functions.define_fmep_model
    acr_fbcp = dfl.acr_full_bmep_curve_percentage
    lb_fbcp = dfl.lb_full_bmep_curve_percentage
    egr_fbcp = dfl.egr_full_bmep_curve_percentage

    acr_mps = dfl.acr_max_mean_piston_speeds_percentage * engine_max_speed
    lb_mps = dfl.lb_max_mean_piston_speeds_percentage * engine_max_speed
    egr_mps = dfl.egr_max_mean_piston_speeds_percentage * engine_max_speed


    from . import calculate_mean_piston_speeds
    bmep = calculate_mean_piston_speeds

    model = FMEP(
        full_bmep_curve,
        active_cylinder_ratios=active_cylinder_ratios,
        has_cylinder_deactivation=has_cylinder_deactivation,
        acr_full_bmep_curve_percentage=acr_fbcp,
        acr_max_mean_piston_speeds=bmep(acr_mps, engine_stroke),
        has_variable_valve_actuation=has_variable_valve_actuation,
        has_lean_burn=has_lean_burn,
        lb_max_mean_piston_speeds=bmep(lb_mps, engine_stroke),
        lb_full_bmep_curve_percentage=lb_fbcp,
        has_exhausted_gas_recirculation=has_exhausted_gas_recirculation,
        has_selective_catalytic_reduction=has_selective_catalytic_reduction,
        egr_max_mean_piston_speeds=bmep(egr_mps, engine_stroke),
        egr_full_bmep_curve_percentage=egr_fbcp,
        engine_type=engine_type
    )

    return model


def _yield_factors(param_id, factor):
    try:
        for k, v in factor.get(param_id, {}).items():
            yield k, v, 1
    except TypeError:
        p = {}

        def _defaults():
            j = np.zeros_like(param_id, dtype=float)
            n = np.zeros_like(param_id, dtype=int)
            return j, n

        for m in np.unique(param_id):
            if not isinstance(m, np.ma.core.MaskedConstant):
                b = m == param_id
                for k, v in factor.get(m, {}).items():
                    j, i = dsp_utl.get_nested_dicts(p, k, default=_defaults)
                    j[b], i[b] = v, 1

        for k, (j, n) in p.items():
            b = n == 0
            j[b], n[b] = 1, 1
            yield k, j, n


def _tech_mult_factors(**params):
    p = {}
    factors = defaults.dfl.functions._tech_mult_factors.factors
    for k, v in factors.items():
        for i, j, n in _yield_factors(params.get(k, 0), v):
            s = dsp_utl.get_nested_dicts(p, i, default=lambda: [0, 0])
            s[0] += j
            s[1] += n

    for k, (n, d) in p.items():
        m = n / d
        params[k] = m * params[k]

    return params


def _fuel_ABC(n_speeds, **kw):
    return _ABC(n_speeds, **_tech_mult_factors(**kw))


# noinspection PyUnusedLocal
def _ABC(
    n_speeds, n_powers=0, n_temperatures=1,
    a2=0, b2=0, a=0, b=0, c=0, t=0, l=0, l2=0, acr=1, **kw):

    acr2 = (acr ** 2)
    A = a2 / acr2 + (b2 / acr2) * n_speeds
    B = a / acr + (b / acr + (c / acr) * n_speeds) * n_speeds
    C = l + l2 * n_speeds ** 2
    if n_temperatures is not 1:
        C *= np.power(n_temperatures, -t)
    C -= n_powers / acr

    return A, B, C


def _calculate_fc(A, B, C):
    b = np.array(A, dtype=bool)
    if b.all():
        v = np.sqrt(np.abs(B ** 2 - 4.0 * A * C))
        return (-B + v) / (2 * A), v
    elif ~b.all():
        return -C / B, B
    else:
        fc, v = np.zeros_like(C), np.zeros_like(C)
        fc[b], v[b] = _calculate_fc(A[b], B[b], C[b])
        b = ~b
        fc[b], v[b] = _calculate_fc(A[b], B[b], C[b])
        return fc, v


def calculate_p0(
        fmep_model, params, engine_capacity, engine_stroke,
        idle_engine_speed_median, engine_fuel_lower_heating_value):
    """
    Calculates the engine power threshold limit [kW].

    :param params:
        CO2 emission model parameters (a2, b2, a, b, c, l, l2, t, trg).

        The missing parameters are set equal to zero.
    :type params: dict

    :param engine_capacity:
        Engine capacity [cm3].
    :type engine_capacity: float

    :param engine_stroke:
        Engine stroke [mm].
    :type engine_stroke: float

    :param idle_engine_speed_median:
        Engine speed idle median [RPM].
    :type idle_engine_speed_median: float

    :param engine_fuel_lower_heating_value:
        Fuel lower heating value [kJ/kg].
    :type engine_fuel_lower_heating_value: float

    :param fmep_model:
        Engine FMEP model.
    :type fmep_model: FMEP

    :return:
        Engine power threshold limit [kW].
    :rtype: float
    """

    engine_cm_idle = idle_engine_speed_median * engine_stroke / 30000.0

    lhv = engine_fuel_lower_heating_value

    wfb_idle, wfa_idle = fmep_model(params, engine_cm_idle, 0, 1)[:2]
    wfa_idle = (3600000.0 / lhv) / wfa_idle
    wfb_idle *= (3.0 * engine_capacity / lhv * idle_engine_speed_median)
    return -wfb_idle / wfa_idle


def _apply_ac_phases(func, fmep_model, params, *args, ac_phases=None):
    res_with_ac = func(fmep_model, params, *args)
    if ac_phases is None or ac_phases.all() or not (
                fmep_model.has_cylinder_deactivation and
                fmep_model.active_cylinder_ratios):
        return res_with_ac
    else:
        p = params.copy()
        p['acr'] = fmep_model.base_acr
        return np.where(ac_phases, res_with_ac, func(fmep_model, p, *args))


def _get_sub_values(*args, sub_values=None):
    if sub_values is not None:
        return tuple(a[sub_values] for a in args)
    return args


def calculate_co2_emissions(
        engine_speeds_out, engine_powers_out, mean_piston_speeds,
        brake_mean_effective_pressures, engine_coolant_temperatures, on_engine,
        engine_fuel_lower_heating_value, idle_engine_speed, engine_stroke,
        engine_capacity, idle_fuel_consumption_model, fuel_carbon_content,
        min_engine_on_speed, tau_function, fmep_model, params, sub_values=None):
    """
    Calculates CO2 emissions [CO2g/s].

    :param engine_speeds_out:
        Engine speed vector [RPM].
    :type engine_speeds_out: numpy.array

    :param engine_powers_out:
        Engine power vector [kW].
    :type engine_powers_out: numpy.array

    :param mean_piston_speeds:
        Mean piston speed vector [m/s].
    :type mean_piston_speeds: numpy.array

    :param brake_mean_effective_pressures:
        Engine brake mean effective pressure vector [bar].
    :type brake_mean_effective_pressures: numpy.array

    :param engine_coolant_temperatures:
        Engine coolant temperature vector [°C].
    :type engine_coolant_temperatures: numpy.array

    :param on_engine:
        If the engine is on [-].
    :type on_engine: numpy.array

    :param engine_fuel_lower_heating_value:
        Fuel lower heating value [kJ/kg].
    :type engine_fuel_lower_heating_value: float

    :param idle_engine_speed:
        Engine speed idle median and std [RPM].
    :type idle_engine_speed: (float, float)

    :param engine_stroke:
        Engine stroke [mm].
    :type engine_stroke: float

    :param engine_capacity:
        Engine capacity [cm3].
    :type engine_capacity: float

    :param idle_fuel_consumption_model:
        Model of fuel consumption at hot idle engine speed.
    :type idle_fuel_consumption_model: IdleFuelConsumptionModel

    :param fuel_carbon_content:
        Fuel carbon content [CO2g/g].
    :type fuel_carbon_content: float

    :param min_engine_on_speed:
        Minimum engine speed to consider the engine to be on [RPM].
    :type min_engine_on_speed: float

    :param tau_function:
        Tau-function of the extended Willans curve.
    :type tau_function: function

    :param fmep_model:
        Engine FMEP model.
    :type fmep_model: FMEP

    :param params:
        CO2 emission model parameters (a2, b2, a, b, c, l, l2, t, trg).

        The missing parameters are set equal to zero.
    :type params: lmfit.Parameters

    :param sub_values:
        Boolean vector.
    :type sub_values: numpy.array, optional

    :return:
        CO2 emissions vector [CO2g/s].
    :rtype: numpy.array
    """

    p = params.valuesdict()

    # namespace shortcuts
    n_speeds, n_powers, e_speeds, e_powers, e_temp = _get_sub_values(
        mean_piston_speeds, brake_mean_effective_pressures, engine_speeds_out,
        engine_powers_out, engine_coolant_temperatures, sub_values=sub_values
    )
    lhv = engine_fuel_lower_heating_value
    idle_fc_model = idle_fuel_consumption_model.consumption
    fc, ac = np.zeros_like(e_powers), np.zeros_like(e_powers)
    vva, lb = np.zeros_like(e_powers), np.zeros_like(e_powers)
    egr = np.zeros_like(e_powers)

    # Idle fc correction for temperature
    n = (e_speeds < idle_engine_speed[0] + min_engine_on_speed)
    _b = (e_speeds >= min_engine_on_speed)
    if p['t0'] == 0 and p['t1'] == 0:
        ac_phases, n_temp = np.ones_like(e_powers, dtype=bool), 1
        par = defaults.dfl.functions.calculate_co2_emissions
        idle_cutoff = idle_engine_speed[0] * par.cutoff_idle_ratio
        ec_p0 = calculate_p0(
            fmep_model, p, engine_capacity, engine_stroke, idle_cutoff, lhv
        )
        _b &= ~((e_powers <= ec_p0) & (e_speeds > idle_cutoff))
        b = n & _b
        fc[b], ac[b], vva[b], lb[b], egr[b] = idle_fc_model(p)
        b = ~n & _b
    else:
        p['t'] = tau_function(p['t0'], p['t1'], e_temp)
        func = calculate_normalized_engine_coolant_temperatures
        n_temp = func(e_temp, p['trg'])
        ac_phases = n_temp == 1
        par = defaults.dfl.functions.calculate_co2_emissions
        idle_cutoff = idle_engine_speed[0] * par.cutoff_idle_ratio
        ec_p0 = _apply_ac_phases(
            calculate_p0, fmep_model, p, engine_capacity, engine_stroke,
            idle_cutoff, lhv, ac_phases=ac_phases
        )
        _b &= ~((e_powers <= ec_p0) & (e_speeds > idle_cutoff))
        b = n & _b
        # noinspection PyUnresolvedReferences
        idle_fc, ac[b], vva[b], lb[b], egr[b] = idle_fc_model(p, ac_phases[b])
        fc[b] = idle_fc * np.power(n_temp[b], -p['t'][b])
        b = ~n & _b
        p['t'] = p['t'][b]
        n_temp = n_temp[b]

    fc[b], _, ac[b], vva[b], lb[b], egr[b] = fmep_model(
        p, n_speeds[b], n_powers[b], n_temp
    )

    fc[b] *= e_speeds[b] * (engine_capacity / (lhv * 1200))  # [g/sec]

    fc[fc < 0] = 0

    co2 = fc * fuel_carbon_content

    return np.nan_to_num(co2), ac, vva, lb, egr


def define_co2_emissions_model(
        engine_speeds_out, engine_powers_out, mean_piston_speeds,
        brake_mean_effective_pressures, engine_coolant_temperatures, on_engine,
        engine_fuel_lower_heating_value, idle_engine_speed, engine_stroke,
        engine_capacity, idle_fuel_consumption_model, fuel_carbon_content,
        min_engine_on_speed, tau_function, fmep_model):
    """
    Returns CO2 emissions model (see :func:`calculate_co2_emissions`).

    :param engine_speeds_out:
        Engine speed vector [RPM].
    :type engine_speeds_out: numpy.array

    :param engine_powers_out:
        Engine power vector [kW].
    :type engine_powers_out: numpy.array

    :param mean_piston_speeds:
        Mean piston speed vector [m/s].
    :type mean_piston_speeds: numpy.array

    :param brake_mean_effective_pressures:
        Engine brake mean effective pressure vector [bar].
    :type brake_mean_effective_pressures: numpy.array

    :param engine_coolant_temperatures:
        Engine coolant temperature vector [°C].
    :type engine_coolant_temperatures: numpy.array

    :param on_engine:
        If the engine is on [-].
    :type on_engine: numpy.array

    :param engine_fuel_lower_heating_value:
        Fuel lower heating value [kJ/kg].
    :type engine_fuel_lower_heating_value: float

    :param idle_engine_speed:
        Engine speed idle median and std [RPM].
    :type idle_engine_speed: (float, float)

    :param engine_stroke:
        Engine stroke [mm].
    :type engine_stroke: float

    :param engine_capacity:
        Engine capacity [cm3].
    :type engine_capacity: float

    :param idle_fuel_consumption_model:
        Idle fuel consumption model.
    :type idle_fuel_consumption_model: IdleFuelConsumptionModel

    :param fuel_carbon_content:
        Fuel carbon content [CO2g/g].
    :type fuel_carbon_content: float

    :param min_engine_on_speed:
        Minimum engine speed to consider the engine to be on [RPM].
    :type min_engine_on_speed: float

    :param tau_function:
        Tau-function of the extended Willans curve.
    :type tau_function: function

    :param fmep_model:
        Engine FMEP model.
    :type fmep_model: FMEP

    :return:
        CO2 emissions model (co2_emissions = models(params)).
    :rtype: function
    """

    model = functools.partial(
        calculate_co2_emissions, engine_speeds_out, engine_powers_out,
        mean_piston_speeds, brake_mean_effective_pressures,
        engine_coolant_temperatures, on_engine, engine_fuel_lower_heating_value,
        idle_engine_speed, engine_stroke, engine_capacity,
        idle_fuel_consumption_model, fuel_carbon_content, min_engine_on_speed,
        tau_function, fmep_model
    )

    return model


def calculate_phases_distances(times, phases_integration_times, velocities):
    """
    Calculates cycle phases distances [km].

    :param times:
        Time vector [s].
    :type times: numpy.array

    :param phases_integration_times:
        Cycle phases integration times [s].
    :type phases_integration_times: tuple

    :param velocities:
        Velocity vector [km/h].
    :type velocities: numpy.array

    :return:
        Cycle phases distances [km].
    :rtype: numpy.array
    """

    vel = velocities / 3600.0

    return calculate_cumulative_co2(times, phases_integration_times, vel)


def calculate_cumulative_co2(
        times, phases_integration_times, co2_emissions,
        phases_distances=1.0):
    """
    Calculates CO2 emission or cumulative CO2 of cycle phases [CO2g/km or CO2g].

    If phases_distances is not given the result is the cumulative CO2 of cycle
    phases [CO2g] otherwise it is CO2 emission of cycle phases [CO2g/km].

    :param times:
        Time vector [s].
    :type times: numpy.array

    :param phases_integration_times:
        Cycle phases integration times [s].
    :type phases_integration_times: tuple

    :param co2_emissions:
        CO2 instantaneous emissions vector [CO2g/s].
    :type co2_emissions: numpy.array

    :param phases_distances:
        Cycle phases distances [km].
    :type phases_distances: numpy.array | float, optional

    :return:
        CO2 emission or cumulative CO2 of cycle phases [CO2g/km or CO2g].
    :rtype: numpy.array
    """

    co2 = []

    for p in phases_integration_times:
        i, j = np.searchsorted(times, p)
        co2.append(sci_itg.trapz(co2_emissions[i:j], times[i:j]))

    return np.array(co2) / phases_distances


def calculate_cumulative_co2_v1(phases_co2_emissions, phases_distances):
    """
    Calculates cumulative CO2 of cycle phases [CO2g].

    :param phases_co2_emissions:
        CO2 emission of cycle phases [CO2g/km].
    :type phases_co2_emissions: numpy.array

    :param phases_distances:
        Cycle phases distances [km].
    :type phases_distances: numpy.array

    :return:
        Cumulative CO2 of cycle phases [CO2g].
    :rtype: numpy.array
    """

    return phases_co2_emissions * phases_distances


def calculate_extended_integration_times(
        times, velocities, on_engine, phases_integration_times,
        engine_coolant_temperatures, after_treatment_temperature_threshold,
        stop_velocity):
    """
    Calculates the extended integration times [-].

    :param times:
        Time vector [s].
    :type times: numpy.array

    :param velocities:
        Velocity vector [km/h].
    :type velocities: numpy.array

    :param on_engine:
        If the engine is on [-].
    :type on_engine: numpy.array

    :param phases_integration_times:
        Cycle phases integration times [s].
    :type phases_integration_times: tuple

    :param engine_coolant_temperatures:
        Engine coolant temperature vector [°C].
    :type engine_coolant_temperatures: numpy.array

    :param after_treatment_temperature_threshold:
        Engine coolant temperature threshold when the after treatment system is
        warm [°C].
    :type after_treatment_temperature_threshold: (float, float)

    :param stop_velocity:
        Maximum velocity to consider the vehicle stopped [km/h].
    :type stop_velocity: float

    :return:
        Extended cycle phases integration times [s].
    :rtype: tuple
    """

    lv, pit = velocities <= stop_velocity, phases_integration_times
    pit = set(itertools.chain(*pit))
    hv = ~lv
    j, l, phases = np.argmax(hv), len(lv), []
    while j < l:
        i = np.argmax(lv[j:]) + j
        j = np.argmax(hv[i:]) + i

        if i == j:
            break

        t0, t1 = times[i], times[j]
        if t1 - t0 < 20 or any(t0 <= x <= t1 for x in pit):
            continue

        b = ~on_engine[i:j]
        if b.any() and not b.all():
            t = np.median(times[i:j][b])
        else:
            t = (t0 + t1) / 2
        phases.append(t)
    try:
        i = np.searchsorted(engine_coolant_temperatures,
                            (after_treatment_temperature_threshold[1],))[0]
        t = times[i]
        phases.append(t)
    except IndexError:
        pass

    return sorted(phases)


def calculate_extended_cumulative_co2_emissions(
        times, on_engine, extended_integration_times,
        co2_normalization_references, phases_integration_times,
        phases_co2_emissions, phases_distances):
    """
    Calculates the extended cumulative CO2 of cycle phases [CO2g].

    :param times:
        Time vector [s].
    :type times: numpy.array

    :param on_engine:
        If the engine is on [-].
    :type on_engine: numpy.array

    :param extended_integration_times:
        Extended cycle phases integration times [s].
    :type extended_integration_times: tuple

    :param co2_normalization_references:
        CO2 normalization references (e.g., engine loads) [-].
    :type co2_normalization_references: numpy.array

    :param phases_integration_times:
        Cycle phases integration times [s].
    :type phases_integration_times: tuple

    :param phases_co2_emissions:
        CO2 emission of cycle phases [CO2g/km].
    :type phases_co2_emissions: numpy.array

    :param phases_distances:
        Cycle phases distances [km].
    :type phases_distances: numpy.array

    :return:
        Extended cumulative CO2 of cycle phases [CO2g].
    :rtype: numpy.array
    """

    r = co2_normalization_references.copy()
    r[~on_engine] = 0
    _cco2, phases = [], []
    cco2 = phases_co2_emissions * phases_distances
    trapz = sci_itg.trapz
    for cco2, (t0, t1) in zip(cco2, phases_integration_times):
        i, j = np.searchsorted(times, (t0, t1))
        if i == j:
            continue
        v = trapz(r[i:j], times[i:j])
        c = [0.0]

        p = [t for t in extended_integration_times if t0 < t < t1]

        for k, t in zip(np.searchsorted(times, p), p):
            phases.append((t0, t))
            t0 = t
            c.append(trapz(r[i:k], times[i:k]) / v)
        phases.append((t0, t1))
        c.append(1.0)

        _cco2.extend(np.diff(c) * cco2)

    return np.array(_cco2), phases


def calculate_phases_co2_emissions(cumulative_co2_emissions, phases_distances):
    """
    Calculates the CO2 emission of cycle phases [CO2g/km].

    :param cumulative_co2_emissions:
        Cumulative CO2 of cycle phases [CO2g].
    :type cumulative_co2_emissions: numpy.array

    :param phases_distances:
        Cycle phases distances [km].
    :type phases_distances: numpy.array

    :return:
        CO2 emission of cycle phases [CO2g/km].
    :rtype: numpy.array
    """

    return cumulative_co2_emissions / phases_distances


def _rescale_co2_emissions(
        co2_emissions_model, times, phases_integration_times,
        cumulative_co2_emissions, params_initial_guess):
    co2_emissions = co2_emissions_model(params_initial_guess)[0]
    trapz = sci_itg.trapz
    k_factors = []
    for cco2, p in zip(cumulative_co2_emissions, phases_integration_times):
        i, j = np.searchsorted(times, p)
        k = cco2 / trapz(co2_emissions[i:j], times[i:j])
        if np.isnan(k):
            k = 1

        co2_emissions[i:j] *= k
        k_factors.append(k)
    return co2_emissions, np.array(k_factors)


def identify_co2_emissions(
        co2_emissions_model, params_initial_guess, times,
        phases_integration_times, cumulative_co2_emissions,
        co2_error_function_on_phases, engine_coolant_temperatures,
        is_cycle_hot):
    """
    Identifies instantaneous CO2 emission vector [CO2g/s].

    :param co2_emissions_model:
        CO2 emissions model (co2_emissions = models(params)).
    :type co2_emissions_model: function

    :param params_initial_guess:
        Initial guess of co2 emission model params.
    :type params_initial_guess: dict

    :param times:
        Time vector [s].
    :type times: numpy.array

    :param phases_integration_times:
        Cycle phases integration times [s].
    :type phases_integration_times: tuple

    :param cumulative_co2_emissions:
        Cumulative CO2 of cycle phases [CO2g].
    :type cumulative_co2_emissions: numpy.array

    :param co2_error_function_on_phases:
        Error function (according to co2 emissions phases) to calibrate the CO2
        emission model params.
    :type co2_error_function_on_phases: function

    :param engine_coolant_temperatures:
        Engine coolant temperature vector [°C].
    :type engine_coolant_temperatures: numpy.array

    :param is_cycle_hot:
        Is an hot cycle?
    :type is_cycle_hot: bool

    :return:
        The instantaneous CO2 emission vector [CO2g/s].
    :rtype: numpy.array
    """

    p = params_initial_guess
    rescale = functools.partial(
        _rescale_co2_emissions, co2_emissions_model, times,
        phases_integration_times, cumulative_co2_emissions
    )
    dfl = defaults.dfl.functions.identify_co2_emissions
    calibrate = functools.partial(
        calibrate_co2_params, is_cycle_hot, engine_coolant_temperatures,
        co2_error_function_on_phases, _3rd_step=dfl.enable_third_step,
        _3rd_emissions=dfl.third_step_against_emissions
    )
    error_function = define_co2_error_function_on_emissions
    co2, k0 = rescale(p)
    n, xatol = dfl.n_perturbations, dfl.xatol
    for i in range(n):
        p = calibrate(error_function(co2_emissions_model, co2), p)[0]
        co2, k1 = rescale(p)
        if np.max(np.abs(k1 - k0)) <= xatol:
            break
        k0 = k1

    return co2


def define_co2_error_function_on_emissions(co2_emissions_model, co2_emissions):
    """
    Defines an error function (according to co2 emissions time series) to
    calibrate the CO2 emission model params.

    :param co2_emissions_model:
        CO2 emissions model (co2_emissions = models(params)).
    :type co2_emissions_model: function

    :param co2_emissions:
        CO2 instantaneous emissions vector [CO2g/s].
    :type co2_emissions: numpy.array

    :return:
        Error function (according to co2 emissions time series) to calibrate the
        CO2 emission model params.
    :rtype: function
    """

    def error_func(params, sub_values=None):
        x = co2_emissions if sub_values is None else co2_emissions[sub_values]
        y = co2_emissions_model(params, sub_values=sub_values)[0]
        return np.mean(np.abs(x - y))

    return error_func


def define_co2_error_function_on_phases(
        co2_emissions_model, phases_co2_emissions, times,
        phases_integration_times, phases_distances):
    """
    Defines an error function (according to co2 emissions phases) to
    calibrate the CO2 emission model params.

    :param co2_emissions_model:
        CO2 emissions model (co2_emissions = models(params)).
    :type co2_emissions_model: function

    :param phases_co2_emissions:
        Cumulative CO2 of cycle phases [CO2g].
    :type phases_co2_emissions: numpy.array

    :param times:
        Time vector [s].
    :type times: numpy.array

    :param phases_integration_times:
        Cycle phases integration times [s].
    :type phases_integration_times: tuple

    :param phases_distances:
        Cycle phases distances [km].
    :type phases_distances: numpy.array

    :return:
        Error function (according to co2 emissions phases) to calibrate the CO2
        emission model params.
    :rtype: function
    """

    def error_func(params, phases=None):

        if phases:
            co2 = np.zeros_like(times, dtype=float)
            b = np.zeros_like(times, dtype=bool)
            w = []
            for i, p in enumerate(phases_integration_times):
                if i in phases:
                    m, n = np.searchsorted(times, p)
                    b[m:n] = True
                    w.append(phases_co2_emissions[i])
                else:
                    w.append(0)

            co2[b] = co2_emissions_model(params, sub_values=b)[0]
        else:
            co2 = co2_emissions_model(params)[0]
            w = None  # cumulative_co2_emissions

        cco2 = calculate_cumulative_co2(
            times, phases_integration_times, co2, phases_distances)
        return sk_met.mean_absolute_error(phases_co2_emissions, cco2, w)

    return error_func


def predict_co2_emissions(co2_emissions_model, params):
    """
    Predicts CO2 instantaneous emissions vector [CO2g/s].

    :param co2_emissions_model:
        CO2 emissions model (co2_emissions = models(params)).
    :type co2_emissions_model: function

    :param params:
        CO2 emission model parameters (a2, b2, a, b, c, l, l2, t, trg).

        The missing parameters are set equal to zero.
    :type params: dict

    :return:
        CO2 instantaneous emissions vector [CO2g/s].
    :rtype: numpy.array
    """

    return co2_emissions_model(params)


def calculate_fuel_consumptions(co2_emissions, fuel_carbon_content):
    """
    Calculates the instantaneous fuel consumption vector [g/s].

    :param co2_emissions:
        CO2 instantaneous emissions vector [CO2g/s].
    :type co2_emissions: numpy.array

    :param fuel_carbon_content:
        Fuel carbon content [CO2g/g].
    :type fuel_carbon_content: float

    :return:
        The instantaneous fuel consumption vector [g/s].
    :rtype: numpy.array
    """

    return co2_emissions / fuel_carbon_content


def calculate_co2_emission(phases_co2_emissions, phases_distances):
    """
    Calculates the CO2 emission of the cycle [CO2g/km].

    :param phases_co2_emissions:
        CO2 emission of cycle phases [CO2g/km].
    :type phases_co2_emissions: numpy.array

    :param phases_distances:
        Cycle phases distances [km].
    :type phases_distances: numpy.array | float

    :return:
        CO2 emission value of the cycle [CO2g/km].
    :rtype: float
    """

    n = sum(phases_co2_emissions * phases_distances)

    if isinstance(phases_distances, float):
        d = phases_distances * len(phases_co2_emissions)
    else:
        d = sum(phases_distances)

    return float(n / d)


def _select_initial_friction_params(co2_params_initial_guess):
    """
    Selects initial guess of friction params l & l2 for the calculation of
    the motoring curve.

    :param co2_params_initial_guess:
        Initial guess of CO2 emission model params.
    :type co2_params_initial_guess: lmfit.Parameters

    :return:
        Initial guess of friction params l & l2.
    :rtype: float, float
    """

    params = co2_params_initial_guess.valuesdict()

    return dsp_utl.selector(('l', 'l2'), params, output_type='list')


def define_initial_co2_emission_model_params_guess(
        params, engine_type, engine_normalization_temperature,
        engine_thermostat_temperature_window, is_cycle_hot=False,
        bounds=None):
    """
    Selects initial guess and bounds of co2 emission model params.

    :param params:
        CO2 emission model params (a2, b2, a, b, c, l, l2, t, trg).
    :type params: dict

    :param engine_type:
        Engine type (positive turbo, positive natural aspiration, compression).
    :type engine_type: str

    :param engine_normalization_temperature:
        Engine normalization temperature [°C].
    :type engine_normalization_temperature: float

    :param engine_thermostat_temperature_window:
        Thermostat engine temperature limits [°C].
    :type engine_thermostat_temperature_window: (float, float)

    :param is_cycle_hot:
        Is an hot cycle?
    :type is_cycle_hot: bool, optional

    :param bounds:
        Parameters bounds.
    :type bounds: bool, optional

    :return:
        Initial guess of co2 emission model params and of friction params.
    :rtype: lmfit.Parameters, list[float]
    """

    bounds = bounds or {}
    par = defaults.dfl.functions.define_initial_co2_emission_model_params_guess
    default = copy.deepcopy(par.CO2_PARAMS)[engine_type]
    default['trg'] = {
        'value': engine_normalization_temperature,
        'min': engine_thermostat_temperature_window[0],
        'max': engine_thermostat_temperature_window[1],
        'vary': False
    }

    if is_cycle_hot:
        default['t0'].update({'value': 0.0, 'vary': False})
        default['t1'].update({'value': 0.0, 'vary': False})

    p = lmfit.Parameters()
    from ..defaults import dfl
    EPS = dfl.EPS
    for k, kw in sorted(default.items()):
        kw['name'] = k
        kw['value'] = params.get(k, kw['value'])

        if k in bounds:
            b = bounds[k]
            kw['min'] = b.get('min', kw.get('min', None))
            kw['max'] = b.get('max', kw.get('max', None))
            kw['vary'] = b.get('vary', kw.get('vary', True))
        elif 'vary' not in kw:
            kw['vary'] = k not in params

        if 'min' in kw and kw['value'] < kw['min']:
            kw['min'] = kw['value'] - EPS
        if 'max' in kw and kw['value'] > kw['max']:
            kw['max'] = kw['value'] + EPS

        if 'min' in kw and 'max' in kw and kw['min'] == kw['max']:
            kw['vary'] = False
            kw['max'] = kw['min'] = None
        kw['max'] = kw['min'] = None
        p.add(**kw)

    friction_params = _select_initial_friction_params(p)
    if not missing_co2_params(params):
        p = dsp_utl.NONE

    return p, friction_params


def calculate_after_treatment_temperature_threshold(
        engine_normalization_temperature, initial_engine_temperature):
    """
    Calculates the engine coolant temperature when the after treatment system
    is warm [°C].

    :param engine_normalization_temperature:
        Engine normalization temperature [°C].
    :type engine_normalization_temperature: float

    :param initial_engine_temperature:
        Initial engine temperature [°C].
    :type initial_engine_temperature: float

    :return:
        Engine coolant temperature threshold when the after treatment system is
        warm [°C].
    :rtype: (float, float)
    """

    ti = 273 + initial_engine_temperature
    t = (273 + engine_normalization_temperature) / ti - 1
    T_mean = 40 * t + initial_engine_temperature
    T_end = 40 * t ** 2 + T_mean

    return T_mean, T_end


def define_tau_function(after_treatment_temperature_threshold):
    """
    Defines tau-function of the extended Willans curve.

    :param after_treatment_temperature_threshold:
        Engine coolant temperature threshold when the after treatment system is
        warm [°C].
    :type after_treatment_temperature_threshold: (float, float)

    :return:
        Tau-function of the extended Willans curve.
    :rtype: function
    """
    T_mean, T_end = np.array(after_treatment_temperature_threshold) + 273
    s = np.log(T_end / T_mean) / sci_sta.norm.ppf(0.95)
    f = sci_sta.lognorm(s, 0, T_mean).cdf

    def tau_function(t0, t1, temp):
        return t0 - (t1 - t0) * f(temp + 273)

    return tau_function


def _set_attr(params, data, default=False, attr='vary'):
    """
    Set attribute to CO2 emission model parameters.

    :param params:
        CO2 emission model parameters (a2, b2, a, b, c, l, l2, t, trg).
    :type params: lmfit.Parameters

    :param data:
        Parameter ids to be set or key/value to set.
    :type data: list | dict

    :param default:
        Default value to set if a list of parameters ids is provided.
    :type default: bool | float

    :param attr:
        Parameter attribute to set.
    :type attr: str

    :return:
        CO2 emission model parameters.
    :rtype: lmfit.Parameters
    """
    if not isinstance(data, dict):
        data = dict.fromkeys(data, default)

    d = {'min', 'max', 'value', 'vary', 'expr'} - {attr}

    for k, v in data.items():
        p = params[k]
        s = {i: getattr(p, i) for i in d}
        s[attr] = v
        p.set(**s)

        if lmfit.parameter.isclose(p.min, p.max, atol=1e-13, rtol=1e-13):
            p.set(value=np.mean((p.max, p.min)), min=None, max=None, vary=False)

    return params


def calibrate_co2_params(
    is_cycle_hot, engine_coolant_temperatures, co2_error_function_on_phases,
    co2_error_function_on_emissions, co2_params_initial_guess,
    _3rd_step=defaults.dfl.functions.calibrate_co2_params.enable_third_step,
    _3rd_emissions=defaults.dfl.functions.calibrate_co2_params.third_step_against_emissions):
    """
    Calibrates the CO2 emission model parameters (a2, b2, a, b, c, l, l2, t, trg
    ).

    :param engine_coolant_temperatures:
        Engine coolant temperature vector [°C].
    :type engine_coolant_temperatures: numpy.array

    :param co2_error_function_on_emissions:
        Error function (according to co2 emissions time series) to calibrate the
        CO2 emission model params.
    :type co2_error_function_on_emissions: function

    :param co2_error_function_on_phases:
        Error function (according to co2 emissions phases) to calibrate the CO2
        emission model params.
    :type co2_error_function_on_phases: function

    :param co2_params_initial_guess:
        Initial guess of CO2 emission model params.
    :type co2_params_initial_guess: Parameters

    :param is_cycle_hot:
        Is an hot cycle?
    :type is_cycle_hot: bool

    :return:
        Calibrated CO2 emission model parameters (a2, b2, a, b, c, l, l2, t,
        trg) and their calibration statuses.
    :rtype: (lmfit.Parameters, list)
    """

    p = copy.deepcopy(co2_params_initial_guess)
    vary = {k: v.vary for k, v in p.items()}
    values = {k: v._val for k, v in p.items()}

    cold = np.zeros_like(engine_coolant_temperatures, dtype=bool)
    if not is_cycle_hot:
        i = co2_utl.argmax(engine_coolant_temperatures >= p['trg'].value)
        cold[:i] = True
    hot = ~cold

    success = [(True, copy.deepcopy(p))]

    def calibrate(id_p, p, **kws):
        _set_attr(p, id_p, default=False)
        p, s = calibrate_model_params(co2_error_function_on_emissions, p, **kws)
        _set_attr(p, vary)
        success.append((s, copy.deepcopy(p)))
        return p

    cold_p = ['t0', 't1']
    if hot.any():
        _set_attr(p, ['t0', 't1'], default=0.0, attr='value')
        p = calibrate(cold_p, p, sub_values=hot)
    else:
        success.append((True, copy.deepcopy(p)))

    if cold.any():
        _set_attr(p, {'t0': values['t0'], 't1': values['t1']}, attr='value')
        hot_p = ['a2', 'a', 'b', 'c', 'l', 'l2']
        p = calibrate(hot_p, p, sub_values=cold)
    else:
        success.append((True, copy.deepcopy(p)))
        _set_attr(p, ['t0', 't1'], default=0.0, attr='value')
        _set_attr(p, cold_p, default=False)

    if _3rd_step:
        #p = restrict_bounds(p)

        if _3rd_emissions:
            err = co2_error_function_on_emissions
        else:
            err = co2_error_function_on_phases
        p, s = calibrate_model_params(err, p)

    else:
        s = True

    success.append((s, copy.deepcopy(p)))
    _set_attr(p, vary)

    return p, success


def restrict_bounds(co2_params):
    """
    Returns restricted bounds of CO2 emission model params (a2, b2, a, b, c, l,
    l2, t, trg).

    :param co2_params:
        CO2 emission model params (a2, b2, a, b, c, l, l2, t, trg).
    :type co2_params: Parameters

    :return:
        Restricted bounds of CO2 emission model params (a2, b2, a, b, c, l, l2,
        t, trg).
    :rtype: dict
    """
    p = copy.deepcopy(co2_params)
    m = defaults.dfl.functions.restrict_bounds.CO2_PARAMS_LIMIT_MULTIPLIERS

    def _limits(k, v):
        try:
            v = tuple(np.asarray(m[k]) * v.value)
            return min(v), max(v)
        except KeyError:
            return v.min, v.max

    for k, v in p.items():
        v.min, v.max = _limits(k, v)

        if lmfit.parameter.isclose(v.min, v.max, atol=1e-13, rtol=1e-13):
            v.set(value=np.mean((v.max, v.min)), min=None, max=None, vary=False)

    return p


def calibrate_model_params(
        error_function, params, *args, method='nelder', **kws):
    """
    Calibrates the model params minimising the error_function.

    :param error_function:
        Model error function.
    :type error_function: function

    :param params:
        Initial guess of model params.

        If not specified a brute force is used to identify the best initial
        guess with in the bounds.
    :type params: dict, optional

    :param method:
        Name of the fitting method to use.
    :type method: str, optional

    :return:
        Calibrated model params.
    :rtype: dict
    """

    if not any(p.vary for p in params.values()):
        return params, True

    if callable(error_function):
        error_f = error_function
    else:
        def error_f(p, *a, **k):
            return sum(f(p, *a, **k) for f in error_function)

    min_e_and_p = [np.inf, copy.deepcopy(params)]

    def error_func(params, *args, **kwargs):
        res = error_f(params, *args, **kwargs)

        if res < min_e_and_p[0]:
            min_e_and_p[0], min_e_and_p[1] = (res, copy.deepcopy(params))

        return res

    # See #7: Neither BFGS nor SLSQP fix "solution families".
    # leastsq: Improper input: N=6 must not exceed M=1.
    # nelder is stable (297 runs, 14 vehicles) [average time 181s/14 vehicles].
    # lbfgsb is unstable (2 runs, 4 vehicles) [average time 23s/4 vehicles].
    # cg is stable (20 runs, 4 vehicles) [average time 37s/4 vehicles].
    # newton: Jacobian is required for Newton-CG method
    # cobyla is unstable (8 runs, 4 vehicles) [average time 16s/4 vehicles].
    # tnc is unstable (6 runs, 4 vehicles) [average time 23s/4 vehicles].
    # dogleg: Jacobian is required for dogleg minimization.
    # slsqp is unstable (4 runs, 4 vehicles) [average time 18s/4 vehicles].
    # differential_evolution is unstable (1 runs, 4 vehicles)
    # [average time 270s/4 vehicles].
    res = _minimize(error_func, params, args=args, kws=kws, method=method)

    # noinspection PyUnresolvedReferences
    return (res.params if res.success else min_e_and_p[1]), res.success


# correction of lmfit bug.
def _minimize(fcn, params, method='leastsq', args=None, kws=None,
              scale_covar=True, iter_cb=None, **fit_kws):
    fitter = _Minimizer(fcn, params, fcn_args=args, fcn_kws=kws,
                        iter_cb=iter_cb, scale_covar=scale_covar, **fit_kws)

    return fitter.minimize(method=method)


class _Minimizer(lmfit.Minimizer):
    def scalar_minimize(self, method='Nelder-Mead', params=None, **kws):
        """
        Use one of the scalar minimization methods from
        scipy.optimize.minimize.

        Parameters
        ----------
        method : str, optional
            Name of the fitting method to use.
            One of:
                'Nelder-Mead' (default)
                'L-BFGS-B'
                'Powell'
                'CG'
                'Newton-CG'
                'COBYLA'
                'TNC'
                'trust-ncg'
                'dogleg'
                'SLSQP'
                'differential_evolution'

        params : Parameters, optional
           Parameters to use as starting points.
        kws : dict, optional
            Minimizer options pass to scipy.optimize.minimize.

        If the objective function returns a numpy array instead
        of the expected scalar, the sum of squares of the array
        will be used.

        Note that bounds and constraints can be set on Parameters
        for any of these methods, so are not supported separately
        for those designed to use bounds. However, if you use the
        differential_evolution option you must specify finite
        (min, max) for each Parameter.

        Returns
        -------
        success : bool
            Whether the fit was successful.

        """

        result = self.prepare_fit(params=params)
        vars = result.init_vals
        params = result.params

        fmin_kws = dict(method=method,
                        options={'maxiter': 1000 * (len(vars) + 1)})
        fmin_kws.update(self.kws)
        fmin_kws.update(kws)

        # hess supported only in some methods
        if 'hess' in fmin_kws and method not in ('Newton-CG',
                                                 'dogleg', 'trust-ncg'):
            fmin_kws.pop('hess')

        # jac supported only in some methods (and Dfun could be used...)
        if 'jac' not in fmin_kws and fmin_kws.get('Dfun', None) is not None:
            self.jacfcn = fmin_kws.pop('jac')
            fmin_kws['jac'] = self.__jacobian

        if 'jac' in fmin_kws and method not in ('CG', 'BFGS', 'Newton-CG',
                                                'dogleg', 'trust-ncg'):
            self.jacfcn = None
            fmin_kws.pop('jac')

        if method == 'differential_evolution':
            from lmfit.minimizer import _differential_evolution
            fmin_kws['method'] = _differential_evolution
            bounds = [(par.min, par.max) for par in params.values()]
            if not np.all(np.isfinite(bounds)):
                raise ValueError('With differential evolution finite bounds '
                                 'are required for each parameter')
            bounds = [(-np.pi / 2., np.pi / 2.)] * len(vars)
            fmin_kws['bounds'] = bounds

            # in scipy 0.14 this can be called directly from scipy_minimize
            # When minimum scipy is 0.14 the following line and the else
            # can be removed.
            ret = _differential_evolution(self.penalty, vars, **fmin_kws)
        else:
            from lmfit.minimizer import scipy_minimize
            ret = scipy_minimize(self.penalty, vars, **fmin_kws)

        result.aborted = self._abort
        self._abort = False

        for attr, val in ret.items():
            if not attr.startswith('_'):
                setattr(result, attr, val)

        result.chisqr = result.residual = self.__residual(ret.x)
        result.nvarys = len(vars)
        result.ndata = 1
        result.nfree = 1
        if isinstance(result.residual, np.ndarray):
            # noinspection PyUnresolvedReferences
            result.chisqr = (result.chisqr ** 2).sum()
            result.ndata = len(result.residual)
            result.nfree = result.ndata - result.nvarys
        result.redchi = result.chisqr / result.nfree
        _log_likelihood = result.ndata * np.log(result.redchi)
        result.aic = _log_likelihood + 2 * result.nvarys
        result.bic = _log_likelihood + np.log(result.ndata) * result.nvarys

        return result


def calculate_phases_willans_factors(
        params, engine_fuel_lower_heating_value, engine_stroke, engine_capacity,
        min_engine_on_speed, fmep_model, times, phases_integration_times,
        engine_speeds_out, engine_powers_out, velocities, accelerations,
        motive_powers, engine_coolant_temperatures, missing_powers,
        angle_slopes):
    """
    Calculates the Willans factors for each phase.

    :param params:
        CO2 emission model parameters (a2, b2, a, b, c, l, l2, t, trg).

        The missing parameters are set equal to zero.
    :type params: lmfit.Parameters

    :param engine_fuel_lower_heating_value:
        Fuel lower heating value [kJ/kg].
    :type engine_fuel_lower_heating_value: float

    :param engine_stroke:
        Engine stroke [mm].
    :type engine_stroke: float

    :param engine_capacity:
        Engine capacity [cm3].
    :type engine_capacity: float

    :param min_engine_on_speed:
        Minimum engine speed to consider the engine to be on [RPM].
    :type min_engine_on_speed: float

    :param fmep_model:
        Engine FMEP model.
    :type fmep_model: FMEP

    :param times:
        Time vector [s].
    :type times: numpy.array

    :param phases_integration_times:
        Cycle phases integration times [s].
    :type phases_integration_times: tuple

    :param engine_speeds_out:
        Engine speed vector [RPM].
    :type engine_speeds_out: numpy.array

    :param engine_powers_out:
        Engine power vector [kW].
    :type engine_powers_out: numpy.array

    :param velocities:
        Velocity vector [km/h].
    :type velocities: numpy.array

    :param accelerations:
        Acceleration vector [m/s2].
    :type accelerations: numpy.array

    :param motive_powers:
        Motive power [kW].
    :type motive_powers: numpy.array

    :param engine_coolant_temperatures:
        Engine coolant temperature vector [°C].
    :type engine_coolant_temperatures: numpy.array

    :param missing_powers:
        Missing engine power [kW].
    :type missing_powers: numpy.array

    :param angle_slopes:
        Angle slope vector [rad].
    :type angle_slopes: numpy.array

    :return:
        Willans factors:

        - av_velocities                         [km/h]
        - av_slope                              [rad]
        - distance                              [km]
        - init_temp                             [°C]
        - av_temp                               [°C]
        - end_temp                              [°C]
        - av_vel_pos_mov_pow                    [kw/h]
        - av_pos_motive_powers                  [kW]
        - sec_pos_mov_pow                       [s]
        - av_neg_motive_powers                  [kW]
        - sec_neg_mov_pow                       [s]
        - av_pos_accelerations                  [m/s2]
        - av_engine_speeds_out_pos_pow          [RPM]
        - av_pos_engine_powers_out              [kW]
        - engine_bmep_pos_pow                   [bar]
        - mean_piston_speed_pos_pow             [m/s]
        - fuel_mep_pos_pow                      [bar]
        - fuel_consumption_pos_pow              [g/sec]
        - willans_a                             [g/kWh]
        - willans_b                             [g/h]
        - specific_fuel_consumption             [g/kWh]
        - indicated_efficiency                  [-]
        - willans_efficiency                    [-]

    :rtype: dict
    """

    factors = []

    for p in phases_integration_times:
        i, j = np.searchsorted(times, p)

        factors.append(calculate_willans_factors(
            params, engine_fuel_lower_heating_value, engine_stroke,
            engine_capacity, min_engine_on_speed, fmep_model,
            engine_speeds_out[i:j], engine_powers_out[i:j], times[i:j],
            velocities[i:j], accelerations[i:j], motive_powers[i:j],
            engine_coolant_temperatures[i:j], missing_powers[i:j],
            angle_slopes[i:j]
        ))

    return factors


def calculate_willans_factors(
        params, engine_fuel_lower_heating_value, engine_stroke, engine_capacity,
        min_engine_on_speed, fmep_model, engine_speeds_out, engine_powers_out,
        times, velocities, accelerations, motive_powers,
        engine_coolant_temperatures, missing_powers, angle_slopes):
    """
    Calculates the Willans factors.

    :param params:
        CO2 emission model parameters (a2, b2, a, b, c, l, l2, t, trg).

        The missing parameters are set equal to zero.
    :type params: lmfit.Parameters

    :param engine_fuel_lower_heating_value:
        Fuel lower heating value [kJ/kg].
    :type engine_fuel_lower_heating_value: float

    :param engine_stroke:
        Engine stroke [mm].
    :type engine_stroke: float

    :param engine_capacity:
        Engine capacity [cm3].
    :type engine_capacity: float

    :param min_engine_on_speed:
        Minimum engine speed to consider the engine to be on [RPM].
    :type min_engine_on_speed: float

    :param fmep_model:
        Engine FMEP model.
    :type fmep_model: FMEP

    :param engine_speeds_out:
        Engine speed vector [RPM].
    :type engine_speeds_out: numpy.array

    :param engine_powers_out:
        Engine power vector [kW].
    :type engine_powers_out: numpy.array

    :param times:
        Time vector [s].
    :type times: numpy.array

    :param velocities:
        Velocity vector [km/h].
    :type velocities: numpy.array

    :param accelerations:
        Acceleration vector [m/s2].
    :type accelerations: numpy.array

    :param motive_powers:
        Motive power [kW].
    :type motive_powers: numpy.array

    :param engine_coolant_temperatures:
        Engine coolant temperature vector [°C].
    :type engine_coolant_temperatures: numpy.array

    :param missing_powers:
        Missing engine power [kW].
    :type missing_powers: numpy.array

    :param angle_slopes:
        Angle slope vector [rad].
    :type angle_slopes: numpy.array

    :return:
        Willans factors:

        - av_velocities                         [km/h]
        - av_slope                              [rad]
        - distance                              [km]
        - init_temp                             [°C]
        - av_temp                               [°C]
        - end_temp                              [°C]
        - av_vel_pos_mov_pow                    [kw/h]
        - av_pos_motive_powers                  [kW]
        - sec_pos_mov_pow                       [s]
        - av_neg_motive_powers                  [kW]
        - sec_neg_mov_pow                       [s]
        - av_pos_accelerations                  [m/s2]
        - av_engine_speeds_out_pos_pow          [RPM]
        - av_pos_engine_powers_out              [kW]
        - engine_bmep_pos_pow                   [bar]
        - mean_piston_speed_pos_pow             [m/s]
        - fuel_mep_pos_pow                      [bar]
        - fuel_consumption_pos_pow              [g/sec]
        - willans_a                             [g/kWh]
        - willans_b                             [g/h]
        - specific_fuel_consumption             [g/kWh]
        - indicated_efficiency                  [-]
        - willans_efficiency                    [-]

    :rtype: dict
    """

    from . import calculate_mean_piston_speeds
    av = np.average

    w = np.zeros_like(times, dtype=float)
    t = (times[:-1] + times[1:]) / 2
    # noinspection PyUnresolvedReferences
    w[0], w[1:-1], w[-1] = t[0] - times[0], np.diff(t), times[-1] - t[-1]

    f = {
        'av_velocities': av(velocities, weights=w),  # [km/h]
        'av_slope': av(angle_slopes, weights=w),
        'has_sufficient_power': not missing_powers.any(),
        'max_power_required': max(engine_powers_out + missing_powers)
    }

    f['distance'] = f['av_velocities'] * (times[-1] - times[0]) / 3600.0  # [km]

    b = engine_powers_out >= 0
    if b.any():
        p = params.valuesdict()
        _w = w[b]
        av_s = av(engine_speeds_out[b], weights=_w)
        av_p = av(engine_powers_out[b], weights=_w)
        av_mp = av(missing_powers[b], weights=_w)

        n_p = calculate_brake_mean_effective_pressures(
            av_s, av_p, engine_capacity, min_engine_on_speed
        )
        n_s = calculate_mean_piston_speeds(av_s, engine_stroke)

        f_mep, wfa = fmep_model(p, n_s, n_p, 1, 0)[:2]

        c = engine_capacity / engine_fuel_lower_heating_value * av_s
        fc = f_mep * c / 1200.0
        ieff = av_p / (fc * engine_fuel_lower_heating_value) * 1000.0

        willans_a = 3600000.0 / engine_fuel_lower_heating_value / wfa
        willans_b = fmep_model(p, n_s, 0, 1, 0)[0] * c * 3.0

        sfc = willans_a + willans_b / av_p

        willans_eff = 3600000.0 / (sfc * engine_fuel_lower_heating_value)

        f.update({
            'av_engine_speeds_out_pos_pow': av_s,  # [RPM]
            'av_pos_engine_powers_out': av_p,  # [kW]
            'av_missing_powers_pos_pow': av_mp,  # [kW]
            'engine_bmep_pos_pow': n_p,  # [bar]
            'mean_piston_speed_pos_pow': n_s,  # [m/s]
            'fuel_mep_pos_pow': f_mep,  # [bar]
            'fuel_consumption_pos_pow': fc,  # [g/sec]
            'willans_a': willans_a,  # [g/kW]
            'willans_b': willans_b,  # [g]
            'specific_fuel_consumption': sfc,  # [g/kWh]
            'indicated_efficiency': ieff,  # [-]
            'willans_efficiency': willans_eff  # [-]
        })

    b = motive_powers > 0
    if b.any():
        _w = w[b]
        f['av_vel_pos_mov_pow'] = av(velocities[b], weights=_w)  # [km/h]
        f['av_pos_motive_powers'] = av(motive_powers[b], weights=_w)  # [kW]
        f['sec_pos_mov_pow'] = np.sum(_w)  # [s]

    b = accelerations > 0
    if b.any():
        _w = w[b]
        f['av_pos_accelerations'] = av(accelerations[b], weights=_w)  # [m/s2]

    b = motive_powers < 0
    if b.any():
        _w = w[b]
        f['av_neg_motive_powers'] = av(motive_powers[b], weights=_w)  # [kW]
        f['sec_neg_mov_pow'] = np.sum(_w)  # [s]

    f['init_temp'] = engine_coolant_temperatures[0]  # [°C]
    f['av_temp'] = av(engine_coolant_temperatures, weights=w)  # [°C]
    f['end_temp'] = engine_coolant_temperatures[-1]  # [°C]

    return f


def calculate_optimal_efficiency(params, mean_piston_speeds):
    """
    Calculates the optimal efficiency [-] and t.

    :param params:
        CO2 emission model parameters (a2, b2, a, b, c, l, l2, t, trg).

        The missing parameters are set equal to zero.
    :type params: lmfit.Parameters

    :param mean_piston_speeds:
        Mean piston speed vector [m/s].
    :type mean_piston_speeds: numpy.array

    :return:
        Optimal efficiency and the respective parameters:

        - mean_piston_speeds [m/s],
        - engine_bmep [bar],
        - efficiency [-].

    :rtype: dict[str | tuple]
    """

    n_s = np.linspace(mean_piston_speeds.min(), mean_piston_speeds.max(), 10)
    bmep, eff = _calculate_optimal_point(params, n_s)

    return {'mean_piston_speeds': n_s, 'engine_bmep': bmep, 'efficiency': eff}


def _calculate_optimal_point(params, n_speed):
    A, B, C = _fuel_ABC(n_speed, **params)
    ac4, B2 = 4 * A * C, B ** 2
    sabc = np.sqrt(ac4 * B2)
    n = sabc - ac4

    y = 2 * C - sabc / (2 * A)
    eff = n / (B - np.sqrt(B2 - sabc - n))

    return y, eff


# noinspection PyUnusedLocal
def missing_co2_params(params, *args, _not=False):
    """
    Checks if all co2_params are not defined.

    :param params:
        CO2 emission model parameters (a2, b2, a, b, c, l, l2, t, trg).
    :type params: dict | lmfit.Parameters

    :param _not:
        If True the function checks if not all co2_params are defined.
    :type _not: bool

    :return:
        If is missing some parameter.
    :rtype: bool
    """

    s = {'a', 'b', 'c', 'a2', 'b2', 'l', 'l2', 't0', 't1', 'trg'}

    if _not:
        return set(params).issuperset(s)

    return not set(params).issuperset(s)


def define_co2_params_calibrated(params):
    """
    Defines the calibrated co2_params if all co2_params are given.

    :param params:
        CO2 emission model parameters (a2, b2, a, b, c, l, l2, t, trg).
    :type params: dict | lmfit.Parameters

    :return:
        Calibrated CO2 emission model parameters (a2, b2, a, b, c, l, l2, t,
        trg) and their calibration statuses.
    :rtype: (lmfit.Parameters, list)
    """

    if isinstance(params, lmfit.Parameters):
        p = params
    else:
        p = lmfit.Parameters()
        for k, v in params.items():
            p.add(k, value=v, vary=False)

    success = [(None, copy.deepcopy(p))] * 4

    return p, success


def calibrate_co2_params_v1(
        co2_emissions_model, fuel_consumptions, fuel_carbon_content,
        co2_params_initial_guess):
    """
    Calibrates the CO2 emission model parameters (a2, b2, a, b, c, l, l2, t, trg
    ).

    :param co2_emissions_model:
        CO2 emissions model (co2_emissions = models(params)).
    :type co2_emissions_model: function

    :param fuel_consumptions:
        Instantaneous fuel consumption vector [g/s].
    :type fuel_consumptions: numpy.array

    :param fuel_carbon_content:
        Fuel carbon content [CO2g/g].
    :type fuel_carbon_content: float

    :param co2_params_initial_guess:
        Initial guess of CO2 emission model params.
    :type co2_params_initial_guess: Parameters:param co2_params_initial_guess:

    :return:
        Calibrated CO2 emission model parameters (a2, b2, a, b, c, l, l2, t,
        trg) and their calibration statuses.
    :rtype: (lmfit.Parameters, list)
    """

    co2 = fuel_consumptions * fuel_carbon_content
    err = define_co2_error_function_on_emissions(co2_emissions_model, co2)
    p = copy.deepcopy(co2_params_initial_guess)
    success = [(True, copy.deepcopy(p))]

    p, s = calibrate_model_params(err, p)
    success += [(s, p), (None, None), (None, None)]

    return p, success


def calculate_phases_fuel_consumptions(
        phases_co2_emissions, fuel_carbon_content, fuel_density):
    """
    Calculates cycle phases fuel consumption [l/100km].

    :param phases_co2_emissions:
        CO2 emission of cycle phases [CO2g/km].
    :type phases_co2_emissions: numpy.array

    :param fuel_carbon_content:
        Fuel carbon content [CO2g/g].
    :type fuel_carbon_content: float

    :param fuel_density:
        Fuel density [g/l].
    :type fuel_density: float

    :return:
        Fuel consumption of cycle phases [l/100km].
    :rtype: tuple
    """

    c = 100.0 / (fuel_density * fuel_carbon_content)

    return tuple(np.asarray(phases_co2_emissions) * c)


def default_ki_factor(has_periodically_regenerating_systems):
    """
    Returns the default ki factor [-].

    :param has_periodically_regenerating_systems:
        Does the vehicle has periodically regenerating systems? [-].
    :type has_periodically_regenerating_systems: bool

    :return:
        Correction for vehicles with periodically regenerating systems [-].
    :rtype: float
    """

    par = defaults.dfl.functions.default_ki_factor.ki_factor
    return par.get(has_periodically_regenerating_systems, 1.0)


def calculate_declared_co2_emission(co2_emission_value, ki_factor):
    """
    Calculates the declared CO2 emission of the cycle [CO2g/km].

    :param co2_emission_value:
        CO2 emission value of the cycle [CO2g/km].
    :type co2_emission_value: float

    :param ki_factor:
        Correction for vehicles with periodically regenerating systems [-].
    :type ki_factor: float

    :return:
        Declared CO2 emission value of the cycle [CO2g/km].
    :rtype: float
    """

    return co2_emission_value * ki_factor


def default_engine_has_exhausted_gas_recirculation(fuel_type):
    """
    Returns the default engine has exhaust gas recirculation value [-].

    :param fuel_type:
        Fuel type (diesel, gasoline, LPG, NG, ethanol, biodiesel).
    :type fuel_type: str

    :return:
        Does the engine have exhaust gas recirculation technology?
    :rtype: bool
    """

    return fuel_type in ('diesel', 'biodiesel')


def co2_emission():
    """
    Defines the engine CO2 emission sub model.

    .. dispatcher:: d

        >>> d = co2_emission()

    :return:
        The engine CO2 emission sub model.
    :rtype: co2mpas.dispatcher.Dispatcher
    """

    d = dsp.Dispatcher(
        name='Engine CO2 emission sub model',
        description='Calculates CO2 emission.'
    )

    d.add_data(
        data_id='active_cylinder_ratios',
        default_value=defaults.dfl.values.active_cylinder_ratios
    )

    d.add_data(
        data_id='engine_has_cylinder_deactivation',
        default_value=defaults.dfl.values.engine_has_cylinder_deactivation
    )

    d.add_data(
        data_id='engine_has_variable_valve_actuation',
        default_value=defaults.dfl.values.engine_has_variable_valve_actuation
    )

    d.add_data(
        data_id='has_lean_burn',
        default_value=defaults.dfl.values.has_lean_burn
    )

    d.add_data(
        data_id='has_selective_catalytic_reduction',
        default_value=defaults.dfl.values.has_selective_catalytic_reduction
    )

    d.add_function(
        function=default_engine_has_exhausted_gas_recirculation,
        inputs=['fuel_type'],
        outputs=['has_exhausted_gas_recirculation']
    )

    d.add_function(
        function=define_fmep_model,
        inputs=['full_bmep_curve', 'engine_max_speed', 'engine_stroke',
                'active_cylinder_ratios', 'engine_has_cylinder_deactivation',
                'engine_has_variable_valve_actuation', 'has_lean_burn',
                'has_exhausted_gas_recirculation',
                'has_selective_catalytic_reduction', 'engine_type'],
        outputs=['fmep_model']
    )

    # d.add_function(
    #    function=default_engine_fuel_lower_heating_value,
    #    inputs=['fuel_type'],
    #    outputs=['engine_fuel_lower_heating_value'],
    # )

    # d.add_function(
    #    function=default_fuel_carbon_content,
    #    inputs=['fuel_type'],
    #    outputs=['fuel_carbon_content'],
    #    weight=3
    # )

    d.add_function(
        function=calculate_fuel_carbon_content_percentage,
        inputs=['fuel_carbon_content'],
        outputs=['fuel_carbon_content_percentage']
    )

    d.add_function(
        function=calculate_fuel_carbon_content,
        inputs=['fuel_carbon_content_percentage'],
        outputs=['fuel_carbon_content']
    )

    d.add_function(
        function=calculate_brake_mean_effective_pressures,
        inputs=['engine_speeds_out', 'engine_powers_out', 'engine_capacity',
                'min_engine_on_speed'],
        outputs=['brake_mean_effective_pressures']
    )

    d.add_function(
        function=calculate_after_treatment_temperature_threshold,
        inputs=['engine_thermostat_temperature',
                'initial_engine_temperature'],
        outputs=['after_treatment_temperature_threshold']
    )

    d.add_function(
        function=define_tau_function,
        inputs=['after_treatment_temperature_threshold'],
        outputs=['tau_function']
    )

    d.add_data(
        data_id='stop_velocity',
        default_value=defaults.dfl.values.stop_velocity
    )

    d.add_data(
        data_id='min_engine_on_speed',
        default_value=defaults.dfl.values.min_engine_on_speed
    )

    d.add_function(
        function=calculate_extended_integration_times,
        inputs=['times', 'velocities', 'on_engine', 'phases_integration_times',
                'engine_coolant_temperatures',
                'after_treatment_temperature_threshold', 'stop_velocity'],
        outputs=['extended_integration_times'],
    )

    d.add_function(
        function=calculate_extended_cumulative_co2_emissions,
        inputs=['times', 'on_engine', 'extended_integration_times',
                'co2_normalization_references', 'phases_integration_times',
                'phases_co2_emissions', 'phases_distances'],
        outputs=['extended_cumulative_co2_emissions',
                 'extended_phases_integration_times']
    )

    d.add_data(
        data_id='idle_fuel_consumption_initial_guess',
        default_value=None,
        description='Initial guess of fuel consumption '
                    'at hot idle engine speed [g/s].'
    )

    d.add_function(
        function=define_idle_fuel_consumption_model,
        inputs=['idle_engine_speed', 'engine_capacity', 'engine_stroke',
                'engine_fuel_lower_heating_value', 'fmep_model',
                'idle_fuel_consumption_initial_guess'],
        outputs=['idle_fuel_consumption_model']
    )

    d.add_function(
        function=calculate_engine_idle_fuel_consumption,
        inputs=['idle_fuel_consumption_model', 'co2_params_calibrated'],
        outputs=['engine_idle_fuel_consumption']
    )

    d.add_function(
        function=define_co2_emissions_model,
        inputs=['engine_speeds_out', 'engine_powers_out',
                'mean_piston_speeds', 'brake_mean_effective_pressures',
                'engine_coolant_temperatures', 'on_engine',
                'engine_fuel_lower_heating_value', 'idle_engine_speed',
                'engine_stroke', 'engine_capacity',
                'idle_fuel_consumption_model', 'fuel_carbon_content',
                'min_engine_on_speed', 'tau_function', 'fmep_model'],
        outputs=['co2_emissions_model']
    )

    d.add_data(
        data_id='is_cycle_hot',
        default_value=defaults.dfl.values.is_cycle_hot
    )

    d.add_function(
        function=define_initial_co2_emission_model_params_guess,
        inputs=['co2_params', 'engine_type', 'engine_thermostat_temperature',
                'engine_thermostat_temperature_window', 'is_cycle_hot'],
        outputs=['co2_params_initial_guess', 'initial_friction_params'],
    )

    d.add_function(
        function=calculate_phases_distances,
        inputs=['times', 'phases_integration_times', 'velocities'],
        outputs=['phases_distances']
    )

    d.add_function(
        function=calculate_phases_distances,
        inputs=['times', 'extended_phases_integration_times', 'velocities'],
        outputs=['extended_phases_distances']
    )

    d.add_function(
        function=calculate_phases_co2_emissions,
        inputs=['extended_cumulative_co2_emissions',
                'extended_phases_distances'],
        outputs=['extended_phases_co2_emissions']
    )

    d.add_function(
        function=dsp_utl.bypass,
        inputs=['phases_integration_times', 'cumulative_co2_emissions',
                'phases_distances'],
        outputs=['extended_phases_integration_times',
                 'extended_cumulative_co2_emissions',
                 'extended_phases_distances'],
        weight=300
    )

    d.add_function(
        function=calculate_cumulative_co2_v1,
        inputs=['phases_co2_emissions', 'phases_distances'],
        outputs=['cumulative_co2_emissions']
    )

    d.add_function(
        function=identify_co2_emissions,
        inputs=['co2_emissions_model', 'co2_params_initial_guess', 'times',
                'extended_phases_integration_times',
                'extended_cumulative_co2_emissions',
                'co2_error_function_on_phases', 'engine_coolant_temperatures',
                'is_cycle_hot'],
        outputs=['identified_co2_emissions'],
        weight=5
    )

    d.add_function(
        function=dsp_utl.bypass,
        inputs=['co2_emissions'],
        outputs=['identified_co2_emissions']
    )

    d.add_function(
        function=define_co2_error_function_on_emissions,
        inputs=['co2_emissions_model', 'identified_co2_emissions'],
        outputs=['co2_error_function_on_emissions']
    )

    d.add_function(
        function=define_co2_error_function_on_phases,
        inputs=['co2_emissions_model', 'phases_co2_emissions', 'times',
                'phases_integration_times', 'phases_distances'],
        outputs=['co2_error_function_on_phases']
    )

    d.add_function(
        function=calibrate_co2_params,
        inputs=['is_cycle_hot', 'engine_coolant_temperatures',
                'co2_error_function_on_phases',
                'co2_error_function_on_emissions',
                'co2_params_initial_guess'],
        outputs=['co2_params_calibrated', 'calibration_status']
    )

    d.add_function(
        function=define_co2_params_calibrated,
        inputs=['co2_params'],
        outputs=['co2_params_calibrated', 'calibration_status'],
        input_domain=functools.partial(missing_co2_params, _not=True)
    )

    d.add_function(
        function=predict_co2_emissions,
        inputs=['co2_emissions_model', 'co2_params_calibrated'],
        outputs=['co2_emissions', 'active_cylinders', 'active_variable_valves',
                 'active_lean_burns', 'active_exhausted_gas_recirculations']
    )

    d.add_data(
        data_id='co2_params',
        default_value=defaults.dfl.values.co2_params.copy()
    )

    d.add_function(
        function_id='calculate_phases_co2_emissions',
        function=calculate_cumulative_co2,
        inputs=['times', 'phases_integration_times', 'co2_emissions',
                'phases_distances'],
        outputs=['phases_co2_emissions']
    )

    d.add_function(
        function=calculate_fuel_consumptions,
        inputs=['co2_emissions', 'fuel_carbon_content'],
        outputs=['fuel_consumptions']
    )

    d.add_function(
        function=calculate_co2_emission,
        inputs=['phases_co2_emissions', 'phases_distances'],
        outputs=['co2_emission_value']
    )

    d.add_data(
        data_id='has_periodically_regenerating_systems',
        default_value=defaults.dfl.values.has_periodically_regenerating_systems
    )

    d.add_function(
        function=default_ki_factor,
        inputs=['has_periodically_regenerating_systems'],
        outputs=['ki_factor']
    )

    d.add_function(
        function=calculate_declared_co2_emission,
        inputs=['co2_emission_value', 'ki_factor'],
        outputs=['declared_co2_emission_value']
    )

    d.add_data(
        data_id='co2_emission_low',
        description='CO2 emission on low WLTP phase [CO2g/km].'
    )

    d.add_data(
        data_id='co2_emission_medium',
        description='CO2 emission on medium WLTP phase [CO2g/km].'
    )

    d.add_data(
        data_id='co2_emission_high',
        description='CO2 emission on high WLTP phase [CO2g/km].'
    )

    d.add_data(
        data_id='co2_emission_extra_high',
        description='CO2 emission on extra high WLTP phase [CO2g/km].'
    )

    d.add_function(
        function_id='merge_wltp_phases_co2_emission',
        function=dsp_utl.bypass,
        inputs=['co2_emission_low', 'co2_emission_medium', 'co2_emission_high',
                'co2_emission_extra_high'],
        outputs=['phases_co2_emissions']
    )

    d.add_data(
        data_id='co2_emission_UDC',
        description='CO2 emission on UDC NEDC phase [CO2g/km].'
    )

    d.add_data(
        data_id='co2_emission_EUDC',
        description='CO2 emission on EUDC NEDC phase [CO2g/km].'
    )

    d.add_function(
        function_id='merge_nedc_phases_co2_emission',
        function=dsp_utl.bypass,
        inputs=['co2_emission_UDC', 'co2_emission_EUDC'],
        outputs=['phases_co2_emissions']
    )

    d.add_data(
        data_id='enable_willans',
        default_value=defaults.dfl.values.enable_willans,
        description='Enable the calculation of Willans coefficients for '
                    'the cycle?'
    )

    d.add_function(
        function=dsp_utl.add_args(calculate_willans_factors),
        inputs=['enable_willans', 'co2_params_calibrated',
                'engine_fuel_lower_heating_value', 'engine_stroke',
                'engine_capacity', 'min_engine_on_speed', 'fmep_model',
                'engine_speeds_out', 'engine_powers_out', 'times', 'velocities',
                'accelerations', 'motive_powers', 'engine_coolant_temperatures',
                'missing_powers', 'angle_slopes'],
        outputs=['willans_factors'],
        input_domain=lambda *args: args[0]
    )

    d.add_data(
        data_id='enable_phases_willans',
        default_value=defaults.dfl.values.enable_phases_willans,
        description='Enable the calculation of Willans coefficients for '
                    'all phases?'
    )

    d.add_function(
        function=dsp_utl.add_args(calculate_phases_willans_factors),
        inputs=['enable_phases_willans', 'co2_params_calibrated',
                'engine_fuel_lower_heating_value', 'engine_stroke',
                'engine_capacity', 'min_engine_on_speed', 'fmep_model', 'times',
                'phases_integration_times', 'engine_speeds_out',
                'engine_powers_out', 'velocities', 'accelerations',
                'motive_powers', 'engine_coolant_temperatures',
                'missing_powers', 'angle_slopes'],
        outputs=['phases_willans_factors'],
        input_domain=lambda *args: args[0]
    )

    d.add_function(
        function=calculate_optimal_efficiency,
        inputs=['co2_params_calibrated', 'mean_piston_speeds'],
        outputs=['optimal_efficiency']
    )

    d.add_function(
        function=calibrate_co2_params_v1,
        inputs=['co2_emissions_model', 'fuel_consumptions',
                'fuel_carbon_content', 'co2_params_initial_guess'],
        outputs=['co2_params_calibrated', 'calibration_status']
    )

    d.add_function(
        function=calculate_phases_fuel_consumptions,
        inputs=['phases_co2_emissions', 'fuel_carbon_content', 'fuel_density'],
        outputs=['phases_fuel_consumptions']
    )

    return d
