########
Glossary  
########

.. contents::

Input file terminology  
----------------------------
Vehicle general characteristics
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
``input_version``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
It corresponds to the version of the template file used for |co2mpas| not to the |co2mpas| version of the code. Different versions of the file have been used throughout the development of the tool. Input files from version >= 2.2.5 can be used for type approving. 

``vehicle_family_id``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
It corresponds to an individual code for each vehicle that is simulated with the |co2mpas| model. This ID does not affect the NEDC prediction. The ID is allocated in the *output report* and in the *dice report*.   
    
The ID has the following structure: **FT-TA-WMI-yyyy-nnnn**
   
Where:

- **FT** is an identifier of the family type
        IP = Interpolation family as defined in paragraph 5.6.

        RL = Road load family as defined in paragraph 5.7.

        RM = Road load matrix family as defined in paragraph 5.8.

        PR = Periodically regenerating systems (Ki) family as defined in paragraph 5.9.
- **TA** is the distinguishing number of the authority responsible for the family approval as defined in section 1 of point 1 of Annex VII of Directive (EC) 2007/46.   
- **WMI** (world manufacturer identifier) is a code that identifies the manufacturer in a unique manner and is defined in ISO 3780:2009. For a single manufacturers several WMI codes may be used.   
- **yyyy** is the year when the test for the family were concluded.   
- **nnnn** is a four digit sequence number.   
   
``fuel_type``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Used to indicate the type of fuel used by the vehicle during the test. The user must select one among the following options: diesel, gasoline, LPG, NG or biomethane, ethanol(E85), or biodiesel. 

``engine fuel lower heating value``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Lower heating value of the fuel used in the test, expressed in [kJ/kg of fuel].

``fuel_carbon_content_percentage``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The amount of carbon present in the fuel by weight, expressed in [%].

``ignition_type``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Indicate wether the engine of the vehicle is a spark ignition (= positive ignition) or a compression ignition one.

``engine_capacity``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The total volume of all the cylinders of the engine, expressed in cubic centimeters [cc].

``engine_stroke``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
A stroke refers to the full travel of the piston along the cylinder, in either direction. Indicate the stroke of the engine, expressed in [mm].  

``idle_engine_speed_median``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Indicate the engine speed in warm conditions during idling, expressed in revolutions per minute [rpm].

``engine_idle_fuel_consumption``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Provide the fuel consumption of the vehicle in warm conditions during idling. The idling fuel consumption of the vehicle, expressed in grams of fuel per second [gFuel/sec] should be measured when velocity of the engine is 0, the start-stop system is disengaged, and the battery state of charge is at balance conditions. For |co2mpas| purposes, the engine idle fuel consumption can be measured as follows: after a WLTP pysical test, when the engine is warm, leave the car to idle and make a constant measure of fuel consumption for 2 minutes. Disregard the first minute (in which the FC can be affected by the electric system), then calculate idle fuel consumption as the average fuel consumption of the vehicle during the subsequent 1 minute.

``final_drive_ratio``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Set the final drive ratio. If the final drive ratio is included in the gearbox ratios, set this input to 1. If the car has two different final drive ratios, please set this variable to 1 and provide the total ratios in gear_box_ratios tab (gearbox ratio multiplied by final drive ratio).

``tyre_code``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Tyre code of the tyres used in the WLTP test (e.g., P195/55R16 85H\). |co2mpas| does not require the full tyre code to work. But at least provide the following information: nominal width of the tyre, in [mm]; ratio of height to width [%]; and the load index (e.g., 195/55R16\)

``gear_box_type``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Indicate the kind of gear box among automatic transmission, manual transmission, or continuously variable transmission (CVT).

``start_stop_activation_time``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Start/stop activation time elapsed from test start, how many seconds after the NEDC test 
the *S/S* system is expected to be enabled.

``alternator_nomimal_voltage``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Alternator nomimal voltage.

``alternator_nomimal_power``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Alternator maximum power.

``battery_capacity``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Battery capacity.

``calibration.initial_temperature.WLTP-H``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Initial temperature of the test cell during WLTP-H test. 
It is used to calibrate the thermal model. 
Default value = 23 C

``calibration.initial_temperature.WLTP-L``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Initial temperature of the test cell during WLTP-L test. It is used to calibrate the thermal model. _Default value = 23 C

``alternator_efficiency``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Average alternator efficiency as declared by the manufacturer; 
if not provided equal to _default value=0.67

``gear_box_ratios``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Gear box ratios ``[ratio gear 1, ratio gear 2, ...]``

``full_load_speeds``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
T1 max speed. Input the engine speed [rpm] array used by the OEM to calculate the gearshifting in WLTP.   

``full_load_powers``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
T1 max power. Input the engine power [kW] array used by the OEM to calculate the gearshifting in WLTP.  
  
Road loads
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
``vehicle_mass.WLTP-H``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Dyno applied mass [kg]

``f0.WLTP-H``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
road load coefficient WLTP-H. Rolling resistance force [N], when angle_slope==0

``f1.WLTP-H``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
F1 road load coefficient WLTP-H. Defined by Dyno procedure [N/(km/h)].

``f2.WLTP-H``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
F2 road load coefficient WLTP-H. As used in the Dyno and defined by respective guidelines :math:`[N/(km/h)^2]`.

``vehicle_mass.WLTP-L``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Dyno applied mass [kg]

``f0.WLTP-L``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
F0 road load coefficient WLTP-L. Rolling resistance force [N], when angle_slope==0

``f1.WLTP-L``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
F1 road load coefficient WLTP-L. Defined by Dyno procedure [N/(km/h)].

``f2.WLTP-L``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
F2 road load coefficient WLTP-L. As used in the Dyno and defined by respective guidelines [N/(km/h)^2].

``vehicle_mass.NEDC-H``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Dyno applied mass [kg].

``f0.NEDC-H``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
F0 road load coefficient NEDC-H. Rolling resistance force [N], when angle_slope==0

``f1.NEDC-H``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
F1 road load coefficient NEDC-H. Defined by Dyno procedure [N/(km/h)].

``f2.NEDC-H``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
F2 road load coefficient NEDC-H. As used in the Dyno and defined by respective guidelines [N/(km/h)^2].

``vehicle_mass.NEDC-L``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Dyno applied mass [kg]

``f0.NEDC-L``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The ``F0`` road load coefficient NEDC-L. Rolling resistance force [N], when angle_slope==0

``f1.NEDC-L``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The  ``F1`` road load coefficient NEDC-L. Defined by Dyno procedure [N/(km/h)].

``f2.NEDC-L``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The ``F2`` road load coefficient NEDC-L. As used in the Dyno and defined by respective guidelines [N/(km/h)^2].




Targets
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
``co2_emissions_low.WLTP-H``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Phase low, |CO2| emissions bag values [g|CO2|/km], not corrected for RCB, not rounded WLTP-H test measurements. 

``co2_emissions_medium.WLTP-H``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Phase medium, |CO2| emissions bag values [g|CO2|/km], not corrected for RCB, not rounded WLTP-H test measurements.

``co2_emissions_high.WLTP-H``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Phase high, |CO2| emissions bag values [g|CO2|/km], not corrected for RCB, not rounded WLTP-H test measurements.

``co2_emissions_extra_high.WLTP-H``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Phase extra high, |CO2| emissions bag values [g|CO2|/km], not corrected for RCB, not rounded WLTP-H test measurements.

``co2_emissions_low.WLTP-L``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Phase low, |CO2| emissions bag values [g|CO2|/km], not corrected for RCB, not rounded WLTP-L test measurements.

``co2_emissions_medium.WLTP-L``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Phase medium, |CO2| emissions bag values [g|CO2|/km], not corrected for RCB, not rounded WLTP-L test measurements.

``co2_emissions_high.WLTP-L``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Phase high, |CO2| emissions bag values [g|CO2|/km], not corrected for RCB, not rounded WLTP-L test measurements.

``co2_emissions_extra_high.WLTP-L``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Phase extra high, |CO2| emissions bag values [g|CO2|/km], not corrected for RCB, not rounded WLTP-L test measurements.

``target declared_co2_emission_value.NEDC-H``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Declared value for NEDC vehicle H [g|CO2|M/km]. Value should be Ki factor corrected.

``target declared_co2_emission_value.NEDC-L``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Declared value for NEDC vehicle L [g|CO2|/km]. Value should be Ki factor corrected.

``ta_certificate_number``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Type approving body certificate number. This number is printed in the output file of |co2mpas|

Drive mode
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The |co2mpas| model can handle vehicles that have 2x4 and 4x4 wheel drive. Provide in this section the driving mode used in the WLTP and NEDC tests. The default value for all tests is 2x4 wheel drive.

``n_wheel_drive.WLTP-H``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Specify whether WLTP-H test is conducted on 2-wheel driving or 4-wheel driving. The default is 2-wheel drive.

``n_wheel_drive.WLTP-L``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Specify whether the WLTP-L test is conducted on 2-wheel driving or 4-wheel driving. The default is 2-wheel drive.

``n_wheel_drive.NEDC-H``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Specify whether the NEDC-H test is conducted on 2-wheel driving or 4-wheel driving. The default is 2-wheel drive.

``n_wheel_drive.NEDC-L``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Specify whether NEDC-L test is conducted on 2-wheel driving or 4-wheel driving. The default is 2-wheel drive.




Vehicle technologies   
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The |co2mpas| model calculates the NEDC |CO2| emission prediction considering the presence/absence of a set of technologies in the vehicle. For the following |co2mpas| inputs, 0 corresponds to the absence of the technology whereas 1 is when the vehicle is equipped with the technology. If no input is provided, the |co2mpas| model will use the default value.

``engine_is_turbo``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
If the engine is equipped with any kind of forced induction system set like a turbocharger or supercharger, then set ``engine_is_turbo`` to 1. Alternatively, if the air intake of the engine relies on natural aspiration then set ``engine_is_turbo`` to 0. The default value is 1.   

``has_start_stop``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The start-stop (S-S) system shuts down the engine of the vehicle during idling to reduce fuel consumption and it restarts it again when the footbrake/clutch is pressed. If the vehicle has a S-S system, set ``has_start_stop`` to 1. If the vehicle is not equipped with this technology, set it to 0. The default is 1.

``has_energy_recuperation``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Set ``has_energy_recuperation`` to 1 if the vehicle is equipped with any kind of brake energy recuperation technology / regenerative breaks. Otherwise, set it to 0. The default is 1.

``has_torque_converter``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Set ``has_torque_converter`` to 1 if the vehicle is equipped with this technology otherwise, set ``has_torque_converter`` to 0. For manual transmission vehicles the default is 0. For automatic tranmission vehicles, the default is 1. For vehicles with continuously variable transmission, the default is 0.

``fuel_saving_at_strategy``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Setting ``fuel_saving_at_strategy`` to 1 will allow |co2mpas| to use a higher gear at constant speed driving than in case of transient conditions, resulting in a reduction of fuel consumption. This technology was refered as ``eco_mode`` in previous releases of |co2mpas|. The default is 1. 

``has_periodically_regenerating_systems``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
If the vehicle is equipped with periodically regenerating systems (anti-pollution devices such as catalytic converter or particulate trap) that require a periodical regeneration process in less than 4 000 km of normal vehicle operation, set ``has_periodically_regenerating_systems`` to 1. Otherwise, set it to 0. The default is 0.

``ki_factor``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
For vehicles without `periodically regenerating systems <https://github.com/JRCSTU/CO2MPAS-TA/wiki/CO2MPAS-glossary-reST#has_periodically_regenerating_systems>`_ ``ki_factor`` is set to 1. For vehicles with periodically regenerating systems, if not provided, this value is set to 1.05.

``engine_has_variable_valve_actuation``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Variable Valve Actuation (VVA) includes a range of technologies which are used to enable variable valve event timing, duration and/or lift. The term as set includes Valve Timing Control (VTC)—also referred to as Variable Valve Timing (VVT) systems and Variable Valve Lift (VVL) or a combination of these systems (phasing, timing and lift variation). If the vehicle features VVA, set ``engine_has_variable_valve_actuation`` to 1. Otherwise, set it to 0. The default is 0.

``engine_has_cylinder_deactivation``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
This technology allows the deactivation of one or more cylinders under specific conditions predefined in the |co2mpas| code. The implementation in |co2mpas| allows to use different deactivation ratios. So in the case of an 8-cylinder engine, a 50% deactivation (4 cylinders off) or a 25% deactivation ratio (2 cylinders off) are plausible. |co2mpas| selects the optimal ratio at each point from the plausible deactivation ratios provided by the user. The user cannot alter the deactivation strategy. If the vehicle is equipped with a cylinder deactivation system, then set ``engine_has_cylinder_deactivation`` to 1 and indicate the deactivation ratios in the ``active_cylinder_ratios`` tab. Note that the ``active_cylinder_ratios`` always starts with 1 (all cylinders are active) and then it the user can set the corresponding ratios. For example, if the vehicle has an engine with 6 cylinders and it has the possibility to deactivate 2 or 3 or 4 cylinders, you have to introduce the following ratios: 0.66 (4/6), 0.5 (3/6), and 0.33 (2/6). If the vehicle does not have cylinder deactivation set ``engine_has_cylinder_deactivation`` to 0. The default is 0.
Note that **as of November 2016 this specific technology is in validation phase** due to lack of sufficient data to support its appropriate implementation in the code. For **Rally** release, this specific input is considered to be optional.

``has_lean_burn``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The lean burn (LB) technology refers to the burning of fuel with an excess of air in an internal combustion engine. All compression ignition vehicles are supposed to be equipped with LB by default therefore for compression ignition ``has_lean_burn`` must be set to 0. For positive ignition engines set ``has_lean_burn`` to 1 if the vehicle is equipped with LB, otherwise set it to 0. The default is 0.

``has_gear_box_thermal_management``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
This specific technology option applies only to vehicles in which the temperature of the gearbox is regulated from the vehicle's cooling circuit using a heat-exchanger, heating storage system or other methods for directing engine waste-heat to the gearbox. Gearbox mounting and other passive systems (encapsulation) should not be considered. In case the vehicle is equipped with the described gear box thermal management system, set ``has_gear_box_thermal_management`` to 1, otherwise, set it to 0. The default is 0.   
Note that **as of November 2016 this specific technology is in validation phase** due to lack of sufficient data to support its appropriate implementation in the code. For **Rally** release, this specific input is considered to be optional.

``has_exhausted_gas_recirculation``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Exhaust gas recirculation (EGR) recirculates a portion of an engine's exhaust gas back to the engine cylinders to reduce NO\ :sub:`x`\ emissions. The technology does not concern internal (in-cylinder) EGR. Set ``has_exhausted_gas_recirculation`` to 1 if the vehicle is equipped with external EGR (High pressure, Low pressure, or a combination of the two) Otherwise, set it to 0. The default is 0 for gasolines, and 1 for diesel vehicles. 

``has_selective_catalytic_reduction``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
On compression ignition vehicles, the Selective Catalytic Reduction (SCR) system uses urea to reduce NO\ :sub:`x`\  emissions. Therefore this technology is only applicable for compression ignition engines. If the vehicle is equipped with SCR set ``has_selective_catalytic_reduction`` to 1 (True), otherwise, set it to 0 (False). The default value is 0.
Note that **as of November 2016 this specific technology is in validation phase** due to lack of sufficient data to support its appropriate implementation in the code. For **Rally** release, this specific input is considered to be optional.



Dyno configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
``n_dyno_axes.WLTP-H``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The WLTP regulation states that WLTP tests should be performed using a dyno with 2 rotating axis. Therefore, the default value for this variable is 2. Set ``n_dyno_axes.WLTP-H`` to 1 in case a 1 rotating axis dyno was used during the WLTP-H test.

``n_dyno_axes.WLTP-L``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The WLTP regulation states that WLTP tests should be performed using a dyno with 2 rotating axis. Therefore, the default value for this variable is 2. Set ``n_dyno_axes.WLTP-L`` to 1 in case a 1 rotating axis dyno was used during the WLTP-L test.



Generic terms
--------------
NEDC
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
New European Driving Cycle

WLTP
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Worldwide harmonized Light vehicles Test Procedures

reproducibility
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Reproducibility is the capacity of a |co2mpas| simulation to be duplicated in the same computer using the same input file, and the same running options. Reproducibility in |co2mpas| is guaranteed when using the All-in-One environment. However, note that differences in the output of |co2mpas| between 2 identical runs (same computer, same input file, same flags) may occur due to the rounding of decimals >= 12th position.

replicability
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Replicability is the capacity of a |co2mpas| simulation to be duplicated in a different computer (by the same or a different person) using the same input file, and the same running options. Reproducibility in |co2mpas| is guaranteed when using the All-in-One environment.

electronic-file (e-file)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Any piece of information stored in electronic form that constitutes the input or the output of some software application.

Hash-ID
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
A very big number usually expressed in hexadecimal form that can be generated cryptographically from any kind of `e-file <https://github.com/JRCSTU/CO2MPAS-TA/wiki/CO2MPAS-glossary#electronic-file-e-file>`_ based exclusively on its contents; even if a single bit of the file changes, its hash-id is guaranteed to be different.

Dice
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The |co2mpas| application responsible for producing a sampling flag that defines whether a Vehicle has to undergo a physical testing under NEDC (in addition to WLTP).

Alternative/related names: **dice application, sampling application, dice command**

Git
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
An open-source version control system use for software development that organizes files in version folders, stored based on their `SHA1 hashes <https://github.com/JRCSTU/CO2MPAS-TA/wiki/CO2MPAS-glossary#SHA1>`_.  It is distributed, in the sense that any git installation can communicate and exchange files and versions with any other installation.

SHA1
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
A fast and secure hashing algorithm with 160bit numbers (20 bytes, 40 hex digits), used also by `Git <https://github.com/JRCSTU/CO2MPAS-TA/wiki/CO2MPAS-glossary#Git>`_.

Example::

       SHA1(“Hi CO2MPAS”) = 911907f21baea8215a38a10396403bd7cd81bddf

Git DB
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The git repository maintained by the `Dice <https://github.com/JRCSTU/CO2MPAS-TA/wiki/CO2MPAS-glossary#Dice>`_ command that collects all the files and the reports generated during the Type Approving process with |co2mpas|.  It is created by the Technical Service and must be sent to the Type Approval Authority.  Any *hash-ids* generated in the mean time are retrieved by this repository.
Alternative/related names: **Hash DB, Git repo DB, Git repo, Git db**

IO
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Input/Output; when referring to a software application, we mean the internal interfaces that read and write files and streams of data from devices, databases or other external resources.

OEM
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Original Equipment Manufacturers, eg. Vehicle manufacturer 



Reports & exchanged files
----------------------------

Dice Report 
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
A sheet in the Output file containing non-confidential results of the simulation to be communicated to supervision bodies through a timestamp server.
Alternative/related names: **dice email, sampling response, sampling flag**

Dice email
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The actual email sent to be timestamped (roughly derived from Input + Output files)::

    := Dice Report + HASH #1 

Dice stamp
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The response email from timestamp-server, from which the OK/SAMPLE Decision-flag is derived:: 
 
    := Dice email + Signature (random)

Decision flag
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The OK/SAMPLE flag derived from the Dice stamp's signature - it is an abstract entity, not stored anywhere per se. SAMPLE meaning that indipendently of the result of |co2mpas| prediction the vehicle has to undergo an NEDC physical test. OK means that the declared NEDC value is accepted (if |co2mpas| prediction does not deviate more than 4% of the declared NEDC value).

Dice decision
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
A new file stored in the TAA files as received from timestamps server::

    := Dice stamp + Decision flag
    
Output Report
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
A sheet in the Output file that contains they key results of the simulation.

Alternative/related names: **output summary sheet, summary sheet, output summary report, summary report**

TAA Report
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
A "printed" PDF file sent to TAA to generate the Certificate (rouhgly unequivocally associated with all files above)::

    := Output Report + Dice Decision + Hash #2  

.. |co2mpas| replace:: CO\ :sub:`2`\ MPAS
.. |CO2| replace:: CO\ :sub:`2`
