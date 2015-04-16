#!python
"""
Predicts the A/T gear shifting of the NEDC from the data of WLTP,
according to decision tree approach and the corrected matrix velocity.

:input: a directory that contains WLPC and NEDC input data ['.xls','.xlsx','xlsm']
:output: a directory to store the predicted gears and plots

JRC_simplified class controlls the process.
Cycle class identifies data

Usage::

    python jrcgear.py

    Then select the input and output folders form the browser.

	N.B. see the template file for input data.

"""
import sys
import numpy as np

__author__ = 'Vincenzo Arcidiacono'

CORR_FUN_FLAG = True

GEAR_FLAG = False

MAX_ITER = 1

ERROR_LIMIT = 0.0
def pairwise(iterable):
    "s -> (s0,s1), (s1,s2), (s2, s3), ..."
    from itertools import tee

    a, b = tee(iterable)
    next(b, None)
    return zip(a, b)

def grouper(iterable, n):
    "Collect data into fixed-length chunks or blocks"
    # grouper('ABCDEF', 3,) --> ABC DEF
    args = [iter(iterable)] * n
    return zip(*args)

def median_filter(x,y,dx_window):

    def median_filter_iterator(x,y,dx_window):
        samples=[]
        dx_w=dx_window/2
        it = zip(x,y)
        val = next(it)
        samples.append(val)
        stop_add= False
        from statistics import median_high
        for x0 in x:
            #remove samples
            x_1 = x0-dx_w

            for i,xy in enumerate(samples):
                if xy[0]>=x_1:samples=samples[i:]; break

            #add samples
            x1 = x0+dx_w
            while (not stop_add) and val[0]<=x1:
                samples.append(val)
                try:
                    val = next(it)
                except StopIteration:
                    stop_add = True

            X,Y=zip(*samples)

            yield median_high(Y)

    return list(median_filter_iterator(x,y,dx_window))

def reject_outliers(data, m=2):
    from numpy import median,std
    data_median, data_std, data_len = (median(data), std(data), len(data))
    data_std = data_std * m
    data_out = [v for v in data if abs(v - data_median) < data_std]
    if not data_out: return data_median, data_std / m
    return median(data_out), std(data_out)

def correction_function(rpm,c,rpm_idle):
        return 1 - np.exp(-c * (rpm - rpm_idle))

def correction_function_domain(rpm,velocity,time,temperature=None,ratio=None):
    id_data = np.array(list(range(len(rpm)+1)))
    condition = '(velocity>=0) & (velocity<45)'
    condition += '& ((temperature>50) | (time>50))' if temperature is not None else '& (time>50)'
    if ratio is not None: condition += '& (ratio<1.05)& (ratio>=0)'
    return id_data[eval(condition)]

def apply_correction_function(rpm,args_correction_function,velocity,time,temperature):
    ratio = np.array([correction_function(x,args_correction_function[0],args_correction_function[1]) for x in rpm])
    ratio[ratio<0]=0
    rpm_gb = rpm.copy()
    id_data = correction_function_domain(rpm,velocity,time,temperature,ratio)
    rpm_gb[id_data]= rpm[id_data] * ratio[id_data]
    return rpm_gb

def calibrate_correction_function_parameters(gear_in,speed2velocity_ratios,time,velocity,rpm,temperature):
    import numpy as np
    from scipy.optimize import fmin
    from sklearn.metrics import mean_squared_error

    speed2velocity_ratios_list = [(k+1,speed2velocity_ratios[k+1]) for k in range(max(speed2velocity_ratios))]

    def identify_gear(velocity,rpm_gb):
        if velocity <= 0.1: return 0
        ratio = rpm_gb / velocity
        return min((abs(v-ratio),k) for k,v in speed2velocity_ratios_list)[1]

    vectorized_set_gear = np.vectorize(identify_gear)

    vectorized_speed2velocity_ratios = np.vectorize(lambda x: speed2velocity_ratios[x])


    def function_loop_error(args_correction_function, rpm, velocity,gear,time,temperature,b=None):

        ratio = [correction_function(x,args_correction_function[0],args_correction_function[1] if b is None else b) for x in rpm]

        rpm_gb0 = rpm * np.array(ratio)# vectorized_correction_function(*([rpm]+ args_correction_function))

        rpm_gb = velocity * vectorized_speed2velocity_ratios(gear)

        id_data = correction_function_domain(rpm,velocity,time,temperature,rpm_gb/rpm)

        #res = curve_fit(correction_function,rpm[id_data],ratio[id_data])
        #print(res)
        #args_correction_function[0],args_correction_function[1] = res[0]
        if id_data.any():
            res = mean_squared_error(rpm_gb[id_data],rpm_gb0[id_data])
        else:
            res = 0
        return res

    '''
    def function_loop_error(args_correction_function, rpm, velocity):

        ratio = [correction_function(x,args_correction_function[0],args_correction_function[1]) for x in rpm]

        rpm_gb0 = rpm * np.array(ratio)# vectorized_correction_function(*([rpm]+ args_correction_function))
        if gear_in is not None:
            gear = gear_in
        else:
            gear = vectorized_set_gear(velocity,rpm_gb0)
        rpm_gb = velocity * vectorized_speed2velocity_ratios(gear)

        id_data = correction_function_domain(rpm,velocity,time,temperature,rpm_gb/rpm)

        #res = curve_fit(correction_function,rpm[id_data],ratio[id_data])
        #print(res)
        #args_correction_function[0],args_correction_function[1] = res[0]
        if id_data.any():
            res = mean_squared_error(rpm_gb[id_data],rpm_gb0[id_data])
        else:
            res = 0
        return res
    args_correction_function = list(fmin(function_loop_error, [0.001,700], args=(rpm, velocity)))
    ratio = [correction_function(x,args_correction_function[0],args_correction_function[1]) for x in rpm]
    '''
    if gear_in is not None:
        args_correction_function = list(fmin(function_loop_error, [0.001,700], args=(rpm, velocity,gear_in,time,temperature)))
    else:
        gear = {}
        gear[1] = vectorized_set_gear(velocity,rpm)
        args_correction_function = {}

        args_correction_function_av = [0.001,700]
        min_res = float('inf')
        def gear_error(min_res):
            gear[0] = gear[1]

            args_av = list(fmin(function_loop_error, args_correction_function_av, args=(rpm, velocity,gear[0],time,temperature)))
            print(args_av)
            a={}
            a['av']=args_av
            for i in range(max(gear[0])+1):
                ids = gear[0]==i
                if not ids.any(): continue
                a[i] = args_av
                a[i] = list(fmin(function_loop_error, args_av, args=(rpm[ids], velocity[ids],gear[0][ids],time[ids],temperature[ids] if temperature is not None else None)))
                if abs((a[i][0]-args_av[0])/args_av[0])>1 or abs((a[i][1]-args_av[1])/args_av[1])>1:a[i] = args_av

            ratio = np.array([correction_function(x,a[g][0],a[g][1]) for x,g in zip(rpm,gear[0])])
            ratio[ratio<0]=0
            ratio[ratio>1.05]=1
            gear[1] = vectorized_set_gear(velocity,rpm * ratio)
            res = mean_squared_error(gear[1],gear[0])
            if res<min_res:
                args_correction_function_av[0],args_correction_function_av[1] = args_av
                args_correction_function.update(a)
                min_res = res
            return min_res

        k=0
        while min_res>ERROR_LIMIT and k<MAX_ITER:
            k+=1
            min_res = gear_error(min_res)


    ratio = np.array([correction_function(x,args_correction_function[g][0],args_correction_function[g][1]) for x,g in zip(rpm,vectorized_set_gear(velocity,rpm))])
    ratio[ratio<0]=0
    ratio[ratio>1.05]=1
    rpm_gb = rpm * ratio
    return args_correction_function, rpm_gb

class Cycle(object):
    '''
    A class that contains all cycle (WLTC or NEDC) data and methods
    to configure model parameters form the WLPC profiles.
    '''

    def __init__(self, name, velocity=None, rpm=None,gear=None,temperature=None, time=None, speed2velocity_ratios=None,
                 final_drive=None, r_dynamic=None, gb_ratios=None, excel_file=None,
                 time_name_sheet_tag_cols=('target_', [0]), rpm_name_sheet_tag_cols=('target_', [1]),
                 velocity_name_sheet_tag_cols=('velocity_', [1]),
                 gear_shifting_name_sheet_cols=('gearshifting_',[1]),
                 temperature_name_sheet_tag_cols=('temperature_',[1]),
                 input_name_sheet_cols_rows=('Input', [3, 4], 2),
                 inputs=None):

        self.name, self.time, self.velocity, self.rpm,self.gear,self.temperature = \
            (name, time, velocity, rpm, gear, temperature)

        sheet_names = excel_file.sheet_names if excel_file else []

        def set_attr(attr, sn, cols):
            value = getattr(self, attr)
            if value is None and sn in sheet_names and cols:
                value = excel_file.parse(sheetname=sn, parse_cols=cols)
                value = None if value.empty or np.isnan(value.values[:,0]).any() else value.values[:, 0]
            setattr(self, attr, value)

        [set_attr(attr, tag + name, cols) for (tag, cols), attr in [(rpm_name_sheet_tag_cols, 'rpm'),
                                                                    (velocity_name_sheet_tag_cols, 'velocity'),
                                                                    (time_name_sheet_tag_cols, 'time'),
                                                                    (gear_shifting_name_sheet_cols, 'gear'),
                                                                    (temperature_name_sheet_tag_cols,'temperature')]]
        if not GEAR_FLAG: self.gear=None
        if self.gear is not None: self.gear=list(self.gear)
        if inputs is None:
            inputs = excel_file.parse(sheetname=input_name_sheet_cols_rows[0],
                                      parse_cols=input_name_sheet_cols_rows[1],
                                      skiprows=input_name_sheet_cols_rows[2], header=None, index_col=0)[1]

        self.final_drive, self.r_dynamic, self.min_rpm, self.gb_ratios, self.max_gear, self.speed2velocity_ratios \
            = (final_drive, r_dynamic, None, gb_ratios, None, speed2velocity_ratios)

        self.correction_function_flag = inputs.get(' ',CORR_FUN_FLAG)

        def set_inputs(attr, tag, fun, default):
            value = getattr(self, attr)
            input_name = (attr + tag).replace('_', ' ')
            if value is None and input_name in inputs:
                value = inputs[input_name]
                if not (value is np.nan or (hasattr(value,'empty') and value.empty)):value=fun(value)
            if value: setattr(self, attr, value)

        [set_inputs(*v) for v in [('final_drive', '', np.float64, None),
                                  ('r_dynamic', '', np.float64, None),
                                  ('gb_ratios', '', eval, 'None'),
                                  ('final_drive', '', np.float64, None),
                                  ('speed2velocity_ratios','',eval,'None')]]

        del set_attr, sheet_names, set_inputs

        def set_gear(attr):
            v = {i + 1: v for i, v in enumerate(getattr(self,attr)) if v > 0}
            v[0] = 0
            setattr(self,attr,v)

        if self.gb_ratios is not None: set_gear('gb_ratios')

        if self.speed2velocity_ratios is not None:
            set_gear('speed2velocity_ratios')
        else:
            self.speed2velocity_ratios=self.evaluate_speed2velocity_ratios()

        if self.speed2velocity_ratios is not None:self.max_gear=max(self.speed2velocity_ratios)

        if self.rpm is not None and self.velocity is not None:
            self.min_rpm = self.evaluate_rpm_min()

        self.acceleration = self.evaluate_acceleration(self.time,self.velocity)

    def evaluate_acceleration(self,time=None, velocity=None):
        if time is None:time=self.time
        if velocity is None:velocity=self.velocity
        if not (time is not None and velocity is not None):return None
        from numpy import diff
        from scipy.interpolate import InterpolatedUnivariateSpline

        delta_time = diff(time)
        return InterpolatedUnivariateSpline(time[:-1] + delta_time / 2, diff(velocity) / 3.6 / delta_time, k=1)(time)

    def evaluate_rpm_min(self, velocity=None, rpm=None):
        '''
        A function that evaluate the minimum engine speed

        :param velocity: cycle velocity
        :param rpm: cycle engine speed
        :return: tuple containing (minimum engine speed, minimum engine speed plus one standard deviation)
        '''
        from numpy import median, std

        if rpm is None: rpm = self.rpm
        if velocity is None: velocity = self.velocity

        x = rpm[velocity <= 0.1]
        x = (median(x), std(x))

        return (x[0], x[0] + x[1])

    def evaluate_correction_function_parameters(self):
        return calibrate_correction_function_parameters(self.gear,self.speed2velocity_ratios,self.time,self.velocity,self.rpm,self.temperature)

    def evaluate_rpm_upper_bound_goal(self, gear=None, rpm=None, min_rpm=None, max_gear=None):
        '''
        A function that evaluate the upper bound of engine speed goal.

        This is evaluated as the median value plus one standard deviation of the filtered cycle engine speed (i.e.,
        the engine speeds when engine speed > minimum engine speed plus one standard deviation and gear < maximum gear)

        :param gear: cycle gear
        :param rpm: cycle engine speed
        :param min_rpm: cycle minimum engine speed
        :param max_gear: maximum gear of the vehicle
        :return: float with minimum engine speed plus one standard deviation
        '''

        from numpy import array, median, std

        if rpm is None: rpm = self.rpm
        if min_rpm is None: min_rpm = self.min_rpm if self.min_rpm is not None else self.evaluate_rpm_min(rpm=rpm)
        if max_gear is None: max_gear = self.max_gear

        return sum(reject_outliers(rpm[(rpm > min_rpm[1]) & (array(gear) < max_gear)], m=1))

    def gear_shifting_decision_tree(self, gear=None,temperature=None):
        from sklearn.tree import DecisionTreeClassifier

        if gear is None: gear = self.gear if self.gear else self.evaluate_gear()

        if temperature is None: temperature = self.temperature

        previous_gear = [0]
        previous_gear.extend(gear[:-1])

        tree = DecisionTreeClassifier(random_state=0)
        params = (previous_gear, self.velocity, self.acceleration)
        params_type = ('previous_gear', 'velocity', 'acceleration')
        if temperature is not None: params=params+(temperature,);params_type=params_type+('temperature',)
        X, y = ([v for v in zip(*params)], gear)

        tree.fit(X, y)


        return {'tree': tree, 'rpm_upper_bound_goal': self.evaluate_rpm_upper_bound_goal(gear),
                'max_gear': self.max_gear,
                'params_type': params_type}

    def gear_shifting_velocities(self, gear=None, corrected=False):
        from numpy import median, std
        from collections import OrderedDict

        if gear is None: gear = self.gear if self.gear else self.evaluate_gear()
        gsv = {}

        for s, (g0, g1) in zip(self.velocity, pairwise(gear)):
            if s > 0.1 and g0 != g1: gsv[g0] = gsv.get(g0, [[], []]); gsv[g0][g0 < g1].append(s)

        def reject_outliers(data, m=2):
            data_median, data_std, data_len = (median(data), std(data), len(data))
            data_std = data_std * m
            data_out = [v for v in data if abs(v - data_median) < data_std]
            if not data_out: return data_median, (data_len, m / data_std)
            return median(data_out), (len(data_out), 1 / std(data_out))

        gsv = OrderedDict(
            [(k, [reject_outliers(v0) if v0 else (-1, (0, 0)), reject_outliers(v1) if v1 else float('inf')])
             for k, (v0, v1) in ((i, gsv.get(i, [[0], [0]])) for i in range(max(gsv) + 1))])

        def set_reliable_gsv(gsv):
            import sys

            eps = 1+sys.float_info.epsilon

            gsv[0] = [0, (eps, (float('inf'), 0))]

            for v0, v1, up0, down1 in ((v0, v1, v0[1][0], v1[0][0]) for v0, v1 in pairwise(gsv.values())):
                if down1+eps <= v0[0]: down1 = float('inf'); v1[0] = (down1, (0, 0))
                if up0 >= down1 or not corrected: v0[1], v1[0] = (up0, down1); continue
                v0[1] = v1[0] = up0 if max([(True, v0[1][1]), (False, v1[0][1])], key=lambda x: x[1])[0] else down1
                v0[1] = v0[1] + eps

            return gsv

        return {'gsv': set_reliable_gsv(gsv), 'rpm_upper_bound_goal': self.evaluate_rpm_upper_bound_goal(gear),
                'max_gear': self.max_gear}

    def evaluate_gear(self, rpm=None, gear_shifting_velocities=None, gear_shifting_decision_tree=None):
        from numpy import array
        gear = None
        if rpm is None: rpm = self.rpm
        def correct_gear(v, a, gear, max_gear, rpm_upper_bound_goal):
            if self.name.lower() != 'nedc': return gear
            while True:
                rpm = self.evaluate_rpm(self.evaluate_gear_ratios([gear]), array([v]))[0]
                if abs(a) < 0.1 and rpm > rpm_upper_bound_goal and gear < max_gear:
                    gear = gear + 1
                    continue
                return gear

        if gear_shifting_velocities:
            gsv = gear_shifting_velocities['gsv']
            rpm_upper_bound_goal = gear_shifting_velocities['rpm_upper_bound_goal']
            max_gear = gear_shifting_velocities['max_gear']
            v = self.velocity[0]
            current_gear, (down, up) = next(((k, (v0, v1)) for k, (v0, v1) in gsv.items() if v0 <= v < v1))
            gear = [current_gear]
            for v,a in zip(self.velocity[1:],self.acceleration[1:]):
                if not down <= v < up:
                    add = 1 if v >= up else -1
                    while True:
                        current_gear = current_gear + add
                        if current_gear in gsv: break
                current_gear = correct_gear(v, a, current_gear, max_gear, rpm_upper_bound_goal)
                down, up = gsv[current_gear]
                gear.append(current_gear)

        elif gear_shifting_decision_tree:
            previous_gear, gear = (0, [])
            tree = gear_shifting_decision_tree['tree']
            rpm_upper_bound_goal = gear_shifting_decision_tree['rpm_upper_bound_goal']
            max_gear = gear_shifting_decision_tree['max_gear']
            params_type=gear_shifting_decision_tree['params_type']
            params = (self.velocity, self.acceleration)
            if 'temperature' in params_type: params=params+(self.temperature,)
            for v in zip(*params):
                previous_gear = correct_gear(v[0], v[1], tree.predict([[previous_gear]+list(v)])[0], max_gear,
                                             rpm_upper_bound_goal)
                gear.append(previous_gear)

        elif self.speed2velocity_ratios is not None and rpm is not None and self.velocity is not None and self.acceleration is not None:
            speed2velocity_ratios = [(k+1, self.speed2velocity_ratios[k+1]) for k in range(max(self.speed2velocity_ratios))]

            def set_gear(ratio,velocity,acceleration):
                if velocity <= 0.1: return 0
                k, v = min((abs(v - ratio), (k, v)) for k, v in speed2velocity_ratios)[1]
                gear = 0 if v * velocity < self.min_rpm[1] else k
                if velocity>0.1 and acceleration>0 and gear==0: gear=1
                return gear

            ratio = rpm/self.velocity

            gear = [set_gear(*v) for v in zip(ratio,self.velocity,self.acceleration)]

            gear = median_filter(self.time,gear,4)

        return gear

    def evaluate_speed2velocity_ratios(self,gb_ratios=None,gear=None,velocity=None,rpm=None,final_drive=None,r_dynamic=None):

        if gb_ratios is None: gb_ratios = self.gb_ratios
        if final_drive is None: final_drive = self.final_drive
        if r_dynamic is None: r_dynamic = self.r_dynamic

        speed2velocity_ratios = {}
        if gb_ratios is not None and final_drive is not None and r_dynamic is not None:
            from math import pi
            c = final_drive * 60 / (3.6 * 2 * pi * r_dynamic)
            return {k:c * v for k,v in gb_ratios.items()}

        if gear is None: gear = self.gear if self.gear else self.evaluate_gear()
        if velocity is None: velocity = self.velocity
        if rpm is None: rpm = self.rpm
        if gear is not None and velocity is not None and rpm is not None:
            ratio=rpm/velocity; ratio[velocity<0.1]=0
            max_gear=max(gear)
            for k,v in ((k,ratio[gear==k]) for k in range(max_gear+1)):
                if v:
                    speed2velocity_ratios[k] = reject_outliers(v,m=1)[0]
                elif k>0:
                    speed2velocity_ratios[k] = speed2velocity_ratios[k-1]
                else:
                    speed2velocity_ratios[k] = 0

            return speed2velocity_ratios

    def evaluate_gear_ratios(self, gear):
        from numpy import array
        return array(list(map(lambda x: self.speed2velocity_ratios[x], gear)))

    def evaluate_rpm(self, gear_ratios, velocity=None):
        if velocity is None: velocity = self.velocity
        rpm = velocity * gear_ratios
        if not self.correction_function_flag:
            rpm[rpm < self.min_rpm[1]] = self.min_rpm[0]
        return rpm

    def evaluate_correlation(self, values, attr='rpm'):
        from numpy import corrcoef

        return corrcoef(getattr(self, attr), values)[0, 1]

    def evaluate_mean_absolute_error(self, values, attr='rpm'):
        from sklearn.metrics import mean_absolute_error

        return mean_absolute_error(getattr(self, attr), values)

class JRC_simplified(object):
    '''
    A a bag of loops and IO for controlling the invocation of Cycle methods.

    - :meth:`__init__` reads cycles profiles and vehicle data
    - :meth:`JRC_gear_corrected_matrix_velocity_tool` evaluate the velocity limits for A/T gear shifting
    - :meth:`JRC_gear_tree_tool` evaluate the decision tree parameters for A/T gear shifting
    - :meth:`evaluate_save_plot_gear` evaluate, save, and plot the gear predictions

    :*_sheet_tag_cols: 0-based
    '''

    def __init__(self, excel_file_path=None, velocity={}, rpm={},gear={}, temperature = {}, time={},
                 r_dynamic=None, final_drive=None, gb_ratios=None,speed2velocity_ratios=None,
                 time_name_sheet_tag_cols=('target_', [0]), rpm_name_sheet_tag_cols=('target_', [1]),
                 velocity_name_sheet_tag_cols=('velocity_', [1]),
                 gear_shifting_name_sheet_cols=('gearshifting_',[1]),
                 temperature_name_sheet_tag_cols=('temperature_',[1]),
                 input_name_sheet_cols_rows=('Input', [3, 4], 2)):

        from pandas import ExcelFile

        excel_file = ExcelFile(excel_file_path) if excel_file_path else None

        inputs = excel_file.parse(sheetname=input_name_sheet_cols_rows[0], parse_cols=input_name_sheet_cols_rows[1],
                                  skiprows=input_name_sheet_cols_rows[2], header=None, index_col=0)[1]
        self.correction_function_flag = inputs.get('correction function flag',CORR_FUN_FLAG)

        def set_cycle(cycle):
            CYCLE = cycle.upper()
            setattr(self, cycle, Cycle(CYCLE, velocity.get(CYCLE, None), rpm.get(CYCLE, None), gear.get(CYCLE, None),
                                       temperature.get(CYCLE, None),
                                       time.get(CYCLE, None),
                                       speed2velocity_ratios, final_drive, r_dynamic, gb_ratios, excel_file,
                                       time_name_sheet_tag_cols, rpm_name_sheet_tag_cols, velocity_name_sheet_tag_cols,
                                       gear_shifting_name_sheet_cols,
                                       temperature_name_sheet_tag_cols,
                                       input_name_sheet_cols_rows, inputs))

        self.wltp, self.nedc = (None, None)
        set_cycle('wltp')
        set_cycle('nedc')


    def JRC_gear_corrected_matrix_velocity_tool(self, cycle_name='wltp'):

        from scipy.optimize import fmin
        from itertools import chain
        from numpy import append

        cycle = getattr(self, cycle_name)

        if cycle.gear is None:
            cycle.gear = cycle.evaluate_gear()

        gsv = cycle.gear_shifting_velocities(cycle.gear, corrected=True)
        gear_id, velocity_limits = zip(*list(gsv['gsv'].items())[1:])

        def update_gvs(velocity_limits):
            gsv['gsv'][0] = (0, velocity_limits[0])
            gsv['gsv'].update({k: v for k, v in zip(gear_id, grouper(append(velocity_limits[1:], float('inf')), 2))})

        def JRC_func(velocity_limits, cycle):
            update_gvs(velocity_limits)
            return cycle.evaluate_mean_absolute_error(
                cycle.evaluate_rpm(cycle.evaluate_gear_ratios(cycle.evaluate_gear(gear_shifting_velocities=gsv))))

        update_gvs(fmin(JRC_func, [gsv['gsv'][0][1]] + list(chain(*velocity_limits))[:-1], args=(cycle,)))

        def correct_gsv_for_constant_velocities(gear_shifting_velocities, up_constant_velocities=[15, 32, 50, 70],
                                                up_limit=3.5, up_delta=-0.5,
                                                down_constant_velocities=[35, 50], down_limit=3.5, down_delta=-1):

            def set_velocity(velocity, const_steps, limit, delta):
                for v in const_steps:
                    if v < velocity < v + limit: return v + delta
                return velocity

            return {'gsv': {k: (set_velocity(v[0], down_constant_velocities, down_limit, down_delta),
                                set_velocity(v[1], up_constant_velocities, up_limit, up_delta)) for k, v in
                            gsv['gsv'].items()},
                    'rpm_upper_bound_goal': gear_shifting_velocities['rpm_upper_bound_goal'],
                    'max_gear': gear_shifting_velocities['max_gear']}

        return correct_gsv_for_constant_velocities(gsv)

    def JRC_gear_tree_tool(self, cycle_name='wltp'):
        cycle = getattr(self, cycle_name)

        if cycle.gear is None:
            cycle.gear = cycle.evaluate_gear()

        return cycle.gear_shifting_decision_tree(cycle.gear)

    def evaluate_save_plot_gear(self, vehicle, writer, doday, output_folder, df_correlation):
        from pandas import DataFrame

        if self.correction_function_flag:
            self.wltp.rpm_given = self.wltp.rpm
            correction_function_parameters,self.wltp.rpm = self.wltp.evaluate_correction_function_parameters()
            #self.wltp.rpm = apply_correction_function(self.wltp.rpm,correction_function_parameters,self.wltp.velocity,self.wltp.time,self.wltp.temperature)
            #self.nedc.rpm = apply_correction_function(self.nedc.rpm,correction_function_parameters,self.nedc.velocity,self.nedc.time,self.nedc.temperature)
            self.wltp.min_rpm = self.wltp.evaluate_rpm_min()

        gsv_corrected = self.JRC_gear_corrected_matrix_velocity_tool()
        gear_tree = self.JRC_gear_tree_tool()

        def evaluate_rpm_correlation(cycle_name, gear_shifting):
            cycle = getattr(self, cycle_name)
            gear = cycle.evaluate_gear(**gear_shifting)
            rpm = cycle.evaluate_rpm(cycle.evaluate_gear_ratios(gear))
            return cycle.evaluate_correlation(rpm), cycle.evaluate_mean_absolute_error(rpm), gear, rpm


        def plot_velocity_gear_rpm(correlation, method, cycle_name,marker, gear, rpm, line='-', color='red', linewidth=2,
                                   fig=True, df=None):
            from numpy import array
            from matplotlib.markers import MarkerStyle
            pl.subplot(2, 2, 1)

            cycle = getattr(self, cycle_name)
            if fig:
                if cycle.gear is None:cycle.gear = cycle.evaluate_gear()
                df = DataFrame()
                df['Time [s]'] = cycle.time
                df['Measured velocity'] = cycle.velocity

            pl.scatter(cycle.gear,array(gear), s=80,color=color, alpha=0.7,label='Gear calculated [%s]' % (method),marker=marker,facecolors='none')
            pl.xlabel('Gear identified/Input')
            pl.ylabel('Gear calculated')
            pl.xlim((0,cycle.max_gear+2))
            pl.ylim((0,cycle.max_gear+2))
            pl.title('Gear correlation')
            pl.legend(loc=2)

            pl.subplot(2, 2, 2)

            if fig:

                df['Gear identified/Input'] = cycle.gear
                pl.plot(cycle.time, array(cycle.gear), color='red', linewidth=2, linestyle='-',
                        label='Gear identified/Input')

            df['Gear calculated [%s]' % (method)] = array(gear)
            pl.plot(cycle.time, array(gear), color=color, alpha=0.7, linestyle=line, linewidth=linewidth,
                    label='Gear calculated [%s]' % (method))
            pl.grid()
            pl.xlabel('Time [s]')
            pl.ylabel('Gear')
            pl.ylim((0,cycle.max_gear+2))
            pl.title('Gear profile')
            pl.legend(loc=2)

            pl.subplot(2, 2, 3)
            if fig:
                if cycle_name == 'wltp':
                    df['GBin_eng [rpm]'] = cycle.rpm
                    pl.plot(cycle.time, cycle.rpm, color='red', linewidth=2, label='GBin_eng')
                    df['Input [rpm]'] = cycle.rpm_given
                    pl.plot(cycle.time, cycle.rpm_given, color='cyan', linewidth=2, label='Input')
                else:
                    df['Input [rpm]'] = cycle.rpm
                    pl.plot(cycle.time, cycle.rpm, color='cyan', linewidth=2, label='Input')

            df['Calculated GBin_wh [%s]' % (method)] = rpm
            pl.plot(cycle.time, rpm, color=color, alpha=0.7, linestyle=line, linewidth=linewidth,
                    label='Calculated GBin_wh [%s] (corr: %.3f, mean abs error: %.1f)' % (
                        method, correlation[0], correlation[1]))
            pl.xlabel('Time [s]')
            pl.ylabel('Speed [RPM]')
            pl.legend(bbox_to_anchor=(1.05, 1), loc=2, borderaxespad=0.)
            pl.title('Speed')
            pl.grid()

            d = {'vehicle': vehicle, 'cycle': cycle_name, 'gear shifting method': method,
                                   'gear shifting correlation': correlation[0],
                                   'gear shifting mean abs error': correlation[1],
                                   'params':''}
            if self.correction_function_flag:
                d['params'] = str(correction_function_parameters)
            df_correlation.append(d)
            return df

        df = None
        sheet_name = ''
        for fig, line,marker, linewidth, color, cycle, method, gear_shifting, text in [
            (True, '-','x', 2, 'blue', 'nedc', 'corrected matrix velocity', {'gear_shifting_velocities': gsv_corrected},
             'nedc rpm correlation with corrected gsv:'),
            (False, '--','+', 2, 'orange', 'nedc', 'decision tree', {'gear_shifting_decision_tree': gear_tree},
             'nedc rpm correlation with decision tree:'),
            (True, '-','x', 2, 'blue', 'wltp', 'corrected matrix velocity', {'gear_shifting_velocities': gsv_corrected},
             'wltp rpm correlation with corrected gsv:'),
            (False, '--','+', 2, 'orange', 'wltp', 'decision tree', {'gear_shifting_decision_tree': gear_tree},
             'wltp rpm correlation with decision tree:'),
        ]:
            if fig:
                if df is not None: df.to_excel(writer, sheet_name);pl.savefig('%s/%s%s.png'%(output_folder,doday,sheet_name))
                df = DataFrame()
                sheet_name = ' '.join([vehicle, cycle])
                pl.figure(figsize=(20,12))

                pl.suptitle(sheet_name.capitalize())


            rpm_correlation = evaluate_rpm_correlation(cycle, gear_shifting)

            print(text, rpm_correlation[0], rpm_correlation[1])

            df = plot_velocity_gear_rpm((rpm_correlation[0], rpm_correlation[1]), method, cycle,marker, rpm_correlation[2],
                                        rpm_correlation[3], line, color, linewidth, fig, df)
        if sheet_name:
            df.to_excel(writer, sheet_name)
            pl.savefig('%s/%s%s.png'%(output_folder,doday,sheet_name))

def main(args):
    from os.path import isfile, join
    from pandas import DataFrame, ExcelWriter
    from os import listdir,getcwd
    from tkinter.filedialog import askdirectory
    from datetime import datetime
    from tkinter import Tk

    df_correlation = []
    tag_name = ''
    doday= datetime.today().strftime('%d_%b_%Y_%H_%M_%S_')
    root=Tk()
    root.withdraw()
    input_folder = askdirectory(title='Select input folder',initialdir='%s/input'%(getcwd()),parent=root)
    output_folder = askdirectory(title='Select output folder',initialdir='%s/output'%(getcwd()),parent=root)

    if not (input_folder and output_folder):
        print('ERROR: missing input and/or output folder')
        return

    confidential = False

    def run(writer, file, vehicle, df_correlation, tag_name, output_folder,doday):
        JRC = JRC_simplified(excel_file_path=file,
                             time_name_sheet_tag_cols=(tag_name, [0]),
                             rpm_name_sheet_tag_cols=(tag_name, [1]),
                             velocity_name_sheet_tag_cols=(tag_name, [2]),
                             gear_shifting_name_sheet_cols=(tag_name, [3]),
                             temperature_name_sheet_tag_cols=(tag_name, [4]),
                             input_name_sheet_cols_rows=('Input', [0, 1], 0))

        JRC.evaluate_save_plot_gear(vehicle, writer, doday, output_folder, df_correlation)

    files = [f for f in listdir(input_folder) if isfile(join(input_folder, f)) and
             f[0] not in ('~', '.') and
             f.split('.')[1] in ('.xls', '.xlsx', 'xlsm')]

    for i, file in enumerate(files):
        vehicle_name = 'Vehicle %d' % (i) if confidential else file.split('_')[-1].split('.')[0]
        writer = ExcelWriter('%s/%s%s.xlsx' % (output_folder, doday, vehicle_name))
        run(writer, input_folder + '/' + file, vehicle_name, df_correlation, tag_name, output_folder,doday)

    writer = ExcelWriter('%s/%s%s.xlsx' % (output_folder, doday, 'Summary'))
    DataFrame.from_records(df_correlation).to_excel(writer, 'Summary')
    return root


if __name__ == '__main__':
    import pylab as pl

    root = main(sys.argv)
    pl.show()
    root.destroy()
