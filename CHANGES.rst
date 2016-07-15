###############
CO2MPAS Changes
###############
.. contents::
.. _changes:

v1.3.1, file-ver: 2.2.1, 15-Jul 2016: "Qube" release
====================================================

This release contains both key model and software changes; additional
capabilities have been added for the user, namely,

- the prediction (by default) of **WLTP** cycle with the theoretical velocity
  and gear shifting profiles,
- the prediction of two **NEDC** cycles High and Low,
- more interpolation methods and custom template according to the cycle to be
  synchronized added in the ``datasync`` command tool, and
- the ``simulation plan``, i.e. co2mpas model can be launched multiple times,
  planning some variations of the vehicle parameters that are provided in a
  single input file.

while other changes improve the quality of model runs, namely,

- the new template file that follows the regulation, and
- several model changes improving the handling of real-measurement data-series.

The study of this release's results are contained in `these 3 report files
<https://jrcstu.github.io/co2mpas/>`_ for *manual*, *automatic* and *real* cars,
respectively.


Model-changes
-------------
- :gh:`100`: Now co2mpas can predict NEDC -H and -L cycles. If just one NEDC is
  needed, the user can fill the fields of the relative NEDC and leave others
  blank.

- :gh:`225` (:git:`178d9f5`): Implement the WLTP pkg within CO2MPAS for
  calculating theoretical velocities and gear shifting.
  Now co2mpas is predicting by default the **WLTP** cycle with the theoretical
  velocity and gear shifting profiles. If velocity and/or gear shifting profiles
  are not respecting the profiles declared by the manufacturer, the correct
  theoretical profiles can be provided (as in the previous version) using the
  ``prediction.WLTP`` sheet.

- :gh:`198`, :gh:`237`: Add the **simulation plan** feature. This enables the
  possibility to launch the co2mpas model multiple times, planning some
  variations of the vehicle parameters that are provided in a single input file
  (so called **base** model). Variations are provided in additional sheets which
  names start with ``plan.``. These sheets contains a table where each row is a
  single simulation, while the columns names are the parameters that the user
  want to change.
  These tables have three special columns names:
  - **id**: Identifies the variation id.
  - **base**: this is a file path of a CO2MPAS excel input, this model will be
    used as new base vehicle.
  - **defaults**: this is a a list of file paths. The calibrated models of these
    files are used as default models of the **base** model. This behavior is
    needed to simulate, for example, a manual car (**base**) as A/T, because
    the A/T strategy and the torque converter are not in the **base** model.

Thermal model
~~~~~~~~~~~~~
- :gh:`242`: Update of the thermal model and the thermostat temperature
  identification. This is needed to fix some instabilities of the model, when
  the data provided has not a conventional behaviour. The changes applied to the
  model are the followings:
  1. Filter outliers in thermal model calibration.
  2. Select major features thermal model calibration.
  3. Use ``final_drive_powers_in`` as input of the thermal model instead the
     ``gear_box_powers_in``.
  4. Update the ``identify_engine_thermostat_temperature`` using a simplified
     thermal model.

Engine model
~~~~~~~~~~~~
- :git:`bfbbb75`: Add new node ``auxiliaries_power_loss`` to calculates engine
  power losses due to engine auxiliaries [kW]. Default value is 0 kW.

- :git:`0816e64`: Add functions to calculate the ``max_available_engine_powers``
  and the ``missing_powers``. The latest tells if the vehicle has sufficient
  power to drive the cycle.

- :git:`71baf52`: Add inverse function to calculate engine nominal power [kW]
  from ``engine_max_torque`` and ``engine_max_speed_at_max_power``.

Vehicle model
~~~~~~~~~~~~~
- :git:`1a700b6`: Add function to treat ``obd_velocities`` and produce the
  ``velocities``. This function uses a Kalman Filter in order to smooth the
  noise in the obd velocities [km/h].

- :git:`8ded622`: FIX acceleration when adjacent velocities are zero. This error
  was due to the interpolation function that does not like discontinuities.

Electrics model
~~~~~~~~~~~~~~~
- :git:`f17a7bc`, :git:`70fbef3`, :git:`e7e3198`: Enhance calibration and
  identification of the alternator model. A new model has been added to model
  the initialization of the alternator. This is used for the first seconds of
  the alternator's operation. It corresponds to a new alternator status == 3.

- :gh:`213`: Link alternator nominal power to max allowable energy recuperation.
  The amount of energy recuperated should not exceed the maximum alternator
  power provided by the user or calculated by the model.

- :git:`5d8e644`: In order to link the **start stop model** with the
  **electric model**, the latest uses as input the ``gear_box_powers`` instead
  of the ``clutch_tc_powers``.

Clutch /Torque-converter/AT models
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
- :git:`48a836e`: FIX identification of the clutch and torque converter delta
  speeds. This has corrected the calculation of the power that flows to the
  engine.


Wheels model
~~~~~~~~~~~~
- :git:`73b3eff`: FIX function to identify the ``r_dynamic`` from
  ``velocity_speed_ratios``, ``gear_box_ratios``, and ``final_drive_ratio``.

- :gh:`229`: Add functions to calculate/identify the ``r_dynamic`` from
  ``tyre_code``. A new parameter ``tyre_dynamic_rolling_coefficient`` has been
  introduced to calculate the ``r_dynamic`` from the ``r_wheels``. This new
  calibrated coefficient belong to the ``engine_speed_model``.

Start/Stop model
~~~~~~~~~~~~~~~~
- :git:`4362cca`, :git:`b8db380`, :git:`5d8e644`: Improve identification and
  performance of `start_stop_model`:

  + Add a ``DefaultStartStopModel`` if this cannot be identified from the data.
  + Impose that during a vehicle stop (i.e., `vel == 0`) the engine cannot be
    switched on and off (just on).
  + Move start/stop functions in a separate module.
  + Add two nodes ``use_basic_start_stop`` and ``is_hybrid``.
  + Differentiate the start stop model behavior: basic and complex models. The
    basic start stop model is function of velocity and acceleration. While, the
    complex model is function of velocity, acceleration, temperature, and
    battery state of charge. If ``use_basic_start_stop`` is not defined, the
    basic model is used as default, except when the vehicle is hybrid.

CO2 model
~~~~~~~~~
- :git:`fef1cc5`: Unify ``engine_thermostat_temperature`` with
  ``normalization_engine_temperature``. The latest node has been deleted.

- :git:`fef1cc5`: Rename ``engine_normalization_temperature_window`` in
  ``engine_thermostat_temperature_window``.

- :git:`94469c7`: FIX coefficient names (``t0`` <-- ``t2``) in function
  ``calculate_extended_integration_times``.

- :git:`368caca`: Remove calculation of fuel consumption / km.

- :gh:`210`: The definition of the fuel cut off boundary has been modified.
  Now `idle_cutoff=idle * 1.1`

- :gh:`230`: Add a function to calculate ``fuel_carbon_content`` from
  ``fuel_carbon_content_percentage``.

Engine cold start model
~~~~~~~~~~~~~~~~~~~~~~~
- :gh:`244`: Update cold start RPM model. Now there is a single model that is a
  three linear model function of the temperature and three coefficients that are
  calibrated.

Datasync
--------
- :gh:`231`: The synchronization done by technical services is not as precise as
  expected for CO2MPAS. Thus, the tool provides custom template according to the
  cycle to be synchronized.

- :gh:`232`: Add more interpolation methods that the user can use for the
  signals' resampling.

IO
--
- :gh:`215`: extend the explanation of the simulation plan in the
  `naming-conventions
  <http://co2mpas.io/explanation.html#excel-input-data-naming-conventions>`_
  used in the model and in the input/output excel files.

Input
~~~~~
- :gh:`214`: Check the initial temperature provided by the user with that of the
  OBD time series. If the difference is greater than 0.5C a message is raised to
  the user and simulation does not take place. This can be disabled with adding
  to cmd ``--soft-validation``.

- :gh:`240`: Update the comments of the parameters in the input template.

- :gh:`240`: Add ``ignition_type`` node and rename ``eco_mode`` with
  ``fuel_saving_at_strategy``. New fuel_types: ``LPG``, ``NG``, ``ethanol``, and
  ``biodiesel``.

- :gh:`246`: Remove fuel consumption in l/100km from the outputs.

Output
~~~~~~
- :git:`2024df7`: Update chart format as scatter type.
- :gh:`248`: FIX **Delta Calculation** following the regulation.
  ``delta = co2_wltp - co2_nedc``.
- :git:`26f994c`: Replace ``comparison`` sheet with ``summary`` sheet.

Cmd-line
--------
- :gh:`197`: Remove ``--with-charts`` flag. Now the output has always charts.

Known limitations
-----------------
- *Model sensitivity*: The sensitivity of CO2MPAS to moderately differing input
  time-series has been tested and found within expected ranges when
  *a single measured WLTP cycle is given as input* on each run - if both
  WLTP H & L cycles are given, even small changes in those paired time-series
  may force the `model-selector <http://co2mpas.io/explanation.html#model-selection>`
  to choose different combinations of calibrated model, thus arriving in
  significantly different fuel-consumption figures between the runs.


v1.2.5, file-ver: 2.2, 25-May 2016: "Panino/Sandwich" release ("PS")
====================================================================
3nd POST-Panino release.
It contains a bug fix in for creating directories.

It is not accompanied by an ALLINONE archive.


v1.2.4, file-ver: 2.2, 12-May 2016: retracted release
=====================================================
2nd POST-Panino release.
It contains the minor filtering fixes from ``1.2.3`` EXCEPT from
the thermal changes, so as to maintain the model behavior of ``1.2.2``.

It is not accompanied by an ALLINONE archive.


v1.2.3, file-ver: 2.2, 11-May 2016: retracted release
=====================================================
1st POST-Panino release, retracted due to unwanted thermal model changes,
and not accompanied by a ALLINONE archive.

- Thermal model calibration is done filtering out ``dT/dt`` outliers,
- the validation of currents' signs has been relaxed, accepting small errors
  in the inputs, and
- Minor fixes in ``calculate_extended_integration_times`` function, used for
  hot-cycles.



v1.2.2, file-ver: 2.2, 19-Apr 2016: "Panino" release
====================================================
This release contains both key model and software changes; additional capabilities
have been added for the user, namely,

- the capability to accept a **theoretical WLTP** cycle and predict its difference
  from the predicted NEDC (:gh:`186`, :gh:`211`),
- the synchronization ``datasync`` command tool (:gh:`144`, :gh:`218`), and
- improve and explain the `naming-conventions
  <http://co2mpas.io/explanation.html#excel-input-data-naming-conventions>`_
  used in the model and in the input/output excel files (:gh:`215`);

while other changes improve the quality of model runs, namely,

- the introduction of schema to check input values(:gh:`60`, :gh:`80`),
- several model changes improving the handling of real-measurement data-series, and
- several crucial engineering fixes and enhancements on the model-calculations,
  including fixes based on  LAT's assessment of the "O'Snow" release.

The study of this release's results are contained in `these 3 report files
<https://jrcstu.github.io/co2mpas/>`_ for *manual*,  *automatic* and *real* cars,
respectively.


Model-changes
-------------
- :gh:`6`: Confirmed that *co2mpas* results are  reproducible in various setups
  (py2.4, py2.5, with fairly recent combinations of numpy/scipy libraries);
  results are still expected to differ between 32bit-64bit platforms.

Engine model
~~~~~~~~~~~~
- :gh:`110`: Add a function to identify *on_idle* as ``engine_speeds_out > MIN_ENGINE_SPEED``
  and ``gears = 0``, or ``engine_speeds_out > MIN_ENGINE_SPEED`` and ``velocities <= VEL_EPS``.
  When engine is idling, power flowing towards the engine is disengaged, and thus
  engine power is greater than or equal to zero. This correction is applied only for cars
  not equiped with Torque Converter.
- :git:`7340700`: Remove limits from the first step ``co2_params`` optimization.
- :gh:`195`: Enable calibration of ``co2_params`` with vectorial inputs in addition to bag values (in order of priority):
    - ``fuel_consumptions``,
    - ``co2_emissions``,
    - ``co2_normalization_references`` (e.g. engine loads)

  When either ``fuel_consumptions`` or ``co2_emissions`` are available, a direct
  calibration of the co2_emissions model is performed. When those are not available,
  the optimization takes place using the reference normalization signal - if available -
  to redefine the initial solution and then optimize based on the bag values.
- :git:`346963a`: Add ``tau_function`` and make thermal exponent (parameter *t*)
  a function of temperature.
- :git:`9d7dd77`: Remove parameter *trg* from the optimization, keep temperature
  target as defined by the identification phase.
- :git:`079642e`: Use ``scipy.interpolate.InterpolatedUnivariateSpline.derivative``
  for the calculation of ``accelerations``.
- :git:`31f8ccc`: Fix prediction of unreliable rpm taking max gear and idle into account.
- :gh:`169`: Add derivative function for conditioning the temperature signal (resolves resolution issues).
- :gh:`153`: Add ``correct_start_stop_with_gears`` function and flag; default value
  ``True`` for manuals and ``False`` for automatics. The functions *forces* the
  engine to start when gear goes from zero to one, independent of the status of
  the clutch.
- :gh:`47`: Exclude first seconds when the engine is off before performing the
  temperature model calibration.

Electrics model
~~~~~~~~~~~~~~~
- :gh:`200`: Fix identification of ``alternator_status_threshold`` and ``charging_statuses``
  for cars with no break eenergy-recuperation-system(BERS). Engine start windows and
  positive alternator currents are now excluded from the calibration.
- :gh:`192`: Add ``alternator_current_threshold`` in the identification of the
  ``charging_statuses``.
- :gh:`149`: Fix identification of the charging status at the beginning of the
  cycle.
- :gh:`149`, :gh:`157`: Fix identification of minimum and maximum state of charge.
- :gh:`149`: Add previous state of charge to the alternator current model calibration.
  Use GradientBoostingRegressor instead of DecisionTreeRegressor, due to over-fitting
  of the later.

Clutch /Torque-converter/AT models
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
- :gh:`179`: Add lock up mode in the torque converter module.
- :gh:`161`: Apply ``correct_gear_shifts`` function before clearing the fluctuations
  on the ``AT_gear`` model.


IO
--
- :gh:`215`: improve and explain the `naming-conventions
  <http://co2mpas.io/explanation.html#excel-input-data-naming-conventions>`_
  used in the model and in the input/output excel files;
  on model parameters internally and on model parameters used on the Input/Output excel files.

Input
~~~~~
- :gh:`186`, :gh:`211`: Add a ``theoretical_WLTP`` sheet on the inputs. If inputs are provided,
  calculate the additional theoretical cycles on the prediction and add the results
  on the outputs.
- :gh:`60`, :gh:`80`: Add schema to validate shape/type/bounds/etc of input data.
  As an example, the sign of the electric currents is now validated before running
  the model. The user can add the flag ``--soft-validation`` to skip this validation.
- :git:`113b09b`: Fix pinning of ``co2_params``, add capability to fix parameters
  outside predefined limits.
- :gh:`104`: Add ``eco_mode`` flag. Apply ``correct_gear`` function when
  ``eco_mode = True``.
- :gh:`143`: Use electrics from the preconditioning cycle to calculate initial state
  of charge for the WLTP. Default initial state of charge is set equal to 99%.

Output
~~~~~~
- :gh:`198`: Add calculation of *willans factors* for each phase.
- :gh:`164`: Add fuel consumption ``[l/100km]``, total and per subphase, in the output file.
- :gh:`173`: Fix metrics and error messages on the calibration of the clutch model
  (specifically related to calibration failures when data are not of adequate quality).
- :gh:`180`: Remove calibration outputs from the charts. Target signals are not
  presented if not provided by the user.
- :gh:`158`: Add ``apply_f0_correction`` function and report ``correct_f0`` in the
  summary, when the flag for the preconditioning correction is *True* in the input.
- :gh:`168`: Add flag/error message when input data are missing and/or vectors
  have not the same length or contain empty cells.
- :gh:`154`: Add ``calculate_optimal_efficiency`` function. The function returns
  the engine piston speeds and bmep for the calibrated co2 params, when the
  efficiency is maximum.
- :gh:`155`: Add *simple willans factors* calculation on the physical model and
  on the outputs, along with average positive power, average speed when power is
  positive, and average fuel consumption.
- :gh:`160`: Add process bar to the console when running batch simulations.
- :gh:`163`: Add sample logconf-file with all loggers; ``pandalone.xleash.io`` logger silenced bye default.


Jupyter notebooks
-----------------
- :gh:`171`: Fix ``simVehicle.ipynb`` notebook of *O'snow*.

Cmd-line
--------
- :gh:`60`, :gh:`80`: Add flag ``--soft-validation`` to skip schema validation
  of the inputs.
- :gh:`144`, :gh:`145`, :gh:`148`, :gh:`29`, :gh:`218`: Add ``datasync`` command.
  that performs resampling and shifting of the provided signals read from excel-tables.
  Foreseen application is to resync dyno times/velocities with OBD ones as reference.
- :gh:`152`: Add ``--overwrite-cache`` flag.
- : Add ``sa`` command, allowing to perform Sensitivity Analysis
  runs on fuel parameters.
- :gh:`140`, :gh:`162`, :gh:`198`, :git:`99530cb`: Add ``sa`` command that
  builds and run batches with slightly modified values on each run, useful for
  sensitivity-analysis; not fully documented yet.
- :git:`284a7df`: Add output folder option for the model graphs.

Internals
---------
- :gh:`135`: Merge physical calibration and prediction models in a unique physical
  model.
- :gh:`134`: Probable fix for generating dispatcher docs under *Cygwin*.
- :git:`e562551`, :git:`3fcd6ce`: *Dispatcher*: Boost and fix *SubDispatchPipe*,
  fix ``check wait_in`` for sub-dispatcher nodes.
- :gh:`131`: ``test_sub_modules.py`` deleted. Not actually used and difficult
  in the maintenance. To be re-drafted when will be of use.

Documentation
-------------
- improve and explain the `naming-conventions
  <http://co2mpas.io/explanation.html#excel-input-data-naming-conventions>`_
  used in the model and in the input/output excel files (:gh:`215`);

Known limitations
-----------------
- *Model sensitivity*: The sensitivity of CO2MPAS to moderately differing input
  time-series has been tested and found within expected ranges when
  *a single measured WLTP cycle is given as input* on each run - if both
  WLTP H & L cycles are given, even small changes in those paired time-series
  may force the `model-selector <http://co2mpas.io/explanation.html#model-selection>`
  to choose different combinations of calibrated model, thus arriving in
  significantly different fuel-consumption figures between the runs.


v1.1.1.fix2, file-ver: 2.1, 09-March 2016: "O'Udo" 2nd release
==============================================================
2nd POSTFIX release.

- electrics, :gh:`143`: Add default value ``initial_state_of_charge := 99``.
- clutch, :gh:`173`: FIX calibration failures with a `No inliers found` by
  `ransac.py` error.


v1.1.1.fix1, file-ver: 2.1, 03-March 2016: "O'Udo" 1st release
==============================================================
1st POSTFIX release.

- :gh:`169`, :gh:`169`: modified theta-filtering for real-data.
- :gh:`171`: update forgotten ``simVehicle.ipynb`` notebook to run ok.


v1.1.1, file-ver: 2.1, 09-Feb 2016: "O'snow" release
====================================================
This release contains mostly model changes; some internal restructurings have
not affected the final user.

Several crucial bugs and enhancements have been been implemented based on
assessments performed by LAT.  A concise study of this release's results
and a high-level description of the model changes is contained in this `JRC-LAT presentation
<http://files.co2mpas.io/CO2MPAS-1.1.1/JRC_LAT_CO2MPAS_Osnow-validation_n_changelog.pptx>`_.


Model-changes
-------------
Engine model
~~~~~~~~~~~~
- Fix extrapolation in ``engine.get_full_load()``, keeping constant the boundary
  values.
- Update ``engine.get_engine_motoring_curve_default()``. The default motoring
  curve is now determined from the engine's friction losses parameters.
- Add engine speed cut-off limits.
- :gh:`104`: Apply *derivative* scikit-function for smoothing
  real data to acceleration & temperature.
- :gh:`82`, :gh:`50`: Add (partial) engine-inertia & auxiliaries torque/power
  losses.
- Optimizer:

  - :git:`84cc3ae8`: Fix ``co2_emission.calibrate_model_params()`` results selection.
  - :gh:`58`: Change error functions: *mean-abs-error* is used instead of
    *mean-squared-error*.
  - :gh:`56`: Cold/hot parts distinction based on the first occurrence of *trg*;
    *trg* not optimized.
  - :gh:`25`: Simplify calibration method for hot part of the cycle,
    imposing ``t=0``.

Temperature model
~~~~~~~~~~~~~~~~~
- :gh:`118`, :gh:`53`: Possible to run hot start cycles & fixed
  temperature cycles.
- :gh:`94`: Fix bug in ``co2_emission.calculate_normalized_engine_coolant_temperatures()``,
  that returned *0* when ``target_Theta > max-Theta`` in NEDC.
- :gh:`79`: Enhance temperature model: the calibration does not take into account
  the first 10secs and the points where ``Delta-Theta = 0``.
- :gh:`55`: Add an additional temperature model, ``f(previous_T, S, P, A)``;
  chose the one which gives the best results.

Gearbox model
~~~~~~~~~~~~~
- :gh:`49`: Fix bug in the estimation of the gear box efficiency for negative power,
  leading to an overestimation of the gear box temperature. (still open)
- :gh:`45`: ATs: Fix bug in the *GSPV matrix* leading to vertical up-shifting lines.

S/S model
~~~~~~~~~
- :gh:`85`: Correct internal gear-shifting profiles according to legislation.
- :gh:`81`: MTs: correct S/S model output -start engine- when ``gear > 0``.
- :gh:`75`, :git:`3def98f3`: Fix gear-identification for
  initial time-steps for real-data; add warning message if WLTP does not
  respect input S/S activation time.

Electrics model
~~~~~~~~~~~~~~~
- :gh:`78`, :gh:`46`: Fix bug in ``electrics.calibrate_alternator_current_model()``
  for real cars, fix fitting error when alternator is always off.
- :gh:`17`: Add new alternator status model, bypassing the DT when ``battery_SOC_balance``
  is given, ``has_energy_recuperation`` equals to one, but BERS is not
  identified in WLTP. ???

Clutch/Torque-converter models
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
- :gh:`83`: Add a second clutch model, equals to no-clutch, when clutch model fails.
- :gh:`16`: Add torque converter.

Vehicle model
~~~~~~~~~~~~~
- :gh:`76`: Remove first 30 seconds for the engine speed model
  selection.
- :git:`e8cabe10`, :git:`016e7060`: Rework model-selection code.


IO
--

Inputs:
~~~~~~~
- :gh:`62`: New compulsory fields in input data::

      velocity_speed_ratios
      co2_params
      gear_box_ratios
      full_load_speeds
      full_load_torques
      full_load_powers

- Add `fuel_carbon_content` input values for each cycle.
- Correct units in `initial_SOC_NEDC`.
- Replace `Battery SOC [%]` time series with `target state_of_charges`.
- :gh:`61`, :gh:`119`: Add dyno type and driveline type (2WD, 4WD) for each cycle.
  Those are used to specify inertia coefficients and drivetrain efficiency
  (default efficiency for `final_drive_efficiency` changed to 0.98).(still open)
- :gh:`44`: Correct `battery_SOC_balance` and `battery_SOC_window` as
  not *compulsory*.
- :gh:`25`: Add option of 'freezing' the optimization parameters.

Outputs:
~~~~~~~~
- :gh:`96`: Produce a single excel with all infos in multiple sheets.
- :gh:`20`: Produce html report with basic interactive graphs (unfinished).
- :git:`5064efd3`: Add charts in excel output.
- :gh:`120`, :gh:`123`: Use excel named-ranges for all columns -
  possible to use specific xl-file as output template, utilizing those
  named-ranges.
- :git:`a03c6805`: Add `status_start_stop_activation_time` to cycle results.
- :git:`f8b85d98`: Add comparison between WLTP prediction vs WLTP inputs &
  WLTP calibration.
- :gh:`102`: Write errors/warnings in the output.(still open)
- :gh:`101`: Add target UDC and target EUDC to the summary.
- :gh:`97`, :gh:`114`, :gh:`64`: Add packages and CO2MPAS versions,
  functions run info, and models' scores to the *proc_info* sheet.(still open)
- :gh:`93`, :gh:`52`: Add success/fail flags related to the optimization steps
  for each cycle, and global success/fail flags on the summary.


Cmd-line (running CO2MPAS)
--------------------------

- Normalize `main()` syntax (see ``co2mpas --help``):

  - Always require a subcommand (tip: try ``co2mpas batch <input-file-1>...``).
  - Drop the ``-I`` option, support multiple input files & folders as simple
    positional arguments in the command-line - ``-O`` now defaults to
    current-folder!
  - Report and halt if no input-files found.
  - GUI dialog-boxes kick-in only if invoked with the  ``--gui`` option.
    Added new dialog-box for cmd-line options (total GUIs 3 in number).
  - Autocomomplete cmd-line with ``[Tab]`` both for `cmd.exe` and *bash*
    (consoles pre-configured in ALLINONE).
  - Support logging-configuration with a file.
  - Other minor options renames and improvements.

- :gh:`5e91993c`: Add option to skip saving WLTP-prediction.
- :gh:`88`: Raise warning (console & summary-file) if incompatible ``VERSION``
  detected in input-file.
- :gh:`102`: Remove UI pop-up boxes when running - users have to check
  the *scores* tables in the result xl-file.
- :gh:`91`: Disallow installation and/or execution under ``python < 3.4``.
- :gh:`5e91993c`: Add option to skip saving WLTP-prediction.
- :gh:`130`: Possible to plot workflow int the output folder with ``--plot-workflow``
  option.


Documentation
-------------

- :gh:`136`: Add section explaining the CO2MPAS selector model (:ref:`explanation`)
  (to be augmented in the future).
- Comprehensive JRC-LAT presentation for validation and high-level summary
  of model changes  (mentioned above).
- New section on how to setup autocompletion for *bash* and *clink* on `cmd.exe`.
- Link to the "fatty" (~40Mb) `tutorial input xl-file
  <http://files.co2mpas.io/CO2MPAS-1.1.1/co2mpas_tutorial_1_1_0.xls>`_.


Internals
---------

- *dispatcher*: Functionality, performance, documentation and debugging
  enhancements for the central module that is executing model-nodes.
- :git:`1a6a901f6c`: Implemented new architecture for IO files.
- :gh:`103`: Problem with simulation time resolved (caused by new IO).
- :gh:`94`, :gh:`99`: Fixed error related to ``argmax()`` function.
- :gh:`25`: Retrofit optimizer code to use *lmfit* library to provide for
  easily playing with parameters and optimization-methods.
- :gh:`107`: Add *Seatbelt-TC* reporting sources of discrepancies, to
  investigate repeatability(:gh:`7`) and reproducibility(:gh:`6`) problems.
- :gh:`63`: Add TCs for the core models. (still open)



v1.1.0-dev1, 18-Dec-2015: "Natale" internal JRC version
=======================================================
Distributed before Christmas and included assessments from LAT.
Model changes reported in "O'snow" release, above.



v1.0.5, 11-Dec 2015: "No more console" release, no model changes
================================================================

- main: Failback to GUI when demo/template/ipynb folder not specified in
  cmdline (prepare for Window's start-menu shortcuts).
- Install from official PyPi repo (simply type ``pip install co2mpas``).
- Add logo.

- ALLINONE:

  - FIX "empty" folder-selection lists bug.
  - Renamed ``cmd-console.bat`` --> ``CONSOLE.bat``.
  - By default store app's process STDOUT/STDERR into logs-files.
  - Add ``INSTALL.bat`` script that creates menu-entries for most common
    CO2MPAS task into *window StartMenu*.
  - Known Issue: Folder-selection dialogs still might appear
    beneath current window sometimes.



v1.0.4, 9-Nov 2015: 3rd public release, mostly model changes
============================================================
Model-changes in comparison to v1.0.1:

- Vehicle/Engine/Gearbox/Transmission:

  - :gh:`13`: If no `r_dynamic` given, attempt to identify it from ``G/V/N`` ratios.
  - :gh:`14`: Added clutch model for correcting RPMs. Power/losses still pending.
  - :gh:`9`: Start-Stop: new model based on the given `start_stop_activation_time`,
    failing back to previous model if not provided. It allows engine stops
    after the 'start_stop_activation_time'.
  - :gh:`21`: Set default value of `k5` equal to `max_gear` to resolve high rpm
    at EUDC deceleration.
  - :gh:`18`: FIX bug in `calculate_engine_start_current` function (zero division).

- Alternator:

  - :gh:`13`: Predict alternator/battery currents if not privded.
  - :gh:`17`: Impose `no_BERS` option when ``has_energy_recuperation == False``.

- A/T:

  - :gh:`28`: Change selection criteria for A/T model
    (``accuracy_score-->mean_abs_error``); not tested due to lack of data.
  - :gh:`34`: Update *gspv* approach (cloud interpolation -> vertical limit).
  - :gh:`35`: Add *eco mode* (MVL) in the A/T model for velocity plateau.
    It selects the highest possible gear.
  - Add option to the input file in order to use a specific A/T model (
    ``specific_gear_shifting=A/T model name``).

- Thermal:

  - :gh:`33`, :gh:`19`: More improvements when fitting of the thermal model.

- Input files:

  - Input-files specify their own version number (currently at `2`).
  - :gh:`9`: Enabled Start-Stop activation time cell.
  - :gh:`25`, :gh:`38`: Add separate sheet for overriding engine's
    fuel-consumption and thermal fitting parameters (trg, t)
    (currently ALL or NONE have to be specified).
  - Added Engine load (%) signal from OBD as input vector.
    Currently not used but will improve significantly the accuracy of the
    cold start model and the execution speed of the program.
    JRC is working on a micro-phases like approach based on this signal.
  - Gears vector not necessary anymore. However providing gears vector
    improves the results for A/Ts and may also lead to better accuracies
    in M/Ts in case the RPM or gear ratios values are not of good quality.
    JRC is still analyzing the issue.

- Output & Summary files:

  - :gh:`23`: Add units and descriptions into output files as a 2nd header-line.
  - :gh:`36`, :gh:`37`: Add comparison-metrics into the summary (target vs output).
    New cmd-line option [--only-summary] to skip saving vehicle-files.

- Miscellaneous:

  - Fixes for when input is 10 Hz.
  - :gh:`20`: Possible to plot workflows of nested models (see Ipython-notebook).
  - Cache input-files in pickles, and read with up-to-date check.
  - Speedup workflow dispatcher internals.


v1.0.3, 13-Oct 2015, CWG release
================================
Still no model-changes in comparison to v1.0.1; released just to distribute
the *all-in-one* archive, provide better instructions, and demonstrate ipython
UI.

- Note that the CO2MPAS contained in the ALLINONE archive is ``1.0.3b0``,
  which does not affect the results or the UI in any way.


v1.0.2, 6-Oct 2015: "Renata" release, unpublished
=================================================
No model-changes, beta-testing "all-in-one" archive for *Windows* distributed
to selected active users only:

- Distributed directly from newly-established project-home on http://co2mpas.io/
  instead of emailing docs/sources/executable (to deal with blocked emails and
  corporate proxies)
- Prepare a pre-populated folder with WinPython + CO2MPAS + Consoles
  for Windows 64bit & 32bit (ALLINONE).
- ALLINONE actually contains ``co2mpas`` command versioned
  as ``1.0.2b3``.
- Add **ipython** notebook for running a single vehicle from the browser
  (see respective Usage-section in the documents) but fails!
- docs:
    - Update Usage instructions based on *all-in-one* archive.
    - Tip for installing behind corporate proxies (thanks to Michael Gratzke),
       and provide link to ``pandalone`` dependency.
    - Docs distributed actually from `v1.0.2-hotfix.0` describing
      also IPython instructions, which, as noted above, fails.

Breaking Changes
----------------
- Rename ``co2mpas`` subcommand: ``examples --> demo``.
- Rename internal package, et all ``compas --> co2mpas``.
- Log timestamps when printing messages.


v1.0.1, 1-Oct 2015: 2nd release
===============================
- Comprehensive modeling with multiple alternative routes depending on
  available data.
- Tested against a sample of 1800 artificially generated vehicles (simulations).
- The model is currently optimized to calculate directly the NEDC CO2 emissions.

Known Limitations
-----------------

#. When data from both WLTP H & L cycles are provided, the model results in
   average NEDC error of ~0.3gCO2/km +- 5.5g/km (stdev) over the 1800 cases
   available to the JRC. Currently no significant systematic errors are observed
   for UDC and EUDC cycles.  No apparent correlations to specific engine or
   vehicle characteristics have been observed in the present release.
   Additional effort is necessary in order to improve the stability of the tool
   and reduce the standard deviation of the error.
#. It has been observed that CO2MPAS tends to underestimate the power
   requirements due to accelerations in WLTP.
   More feedback is needed from real test cases.
#. The current gearbox thermal model overestimates the warm up rate of the
   gearbox.
   The bug is identified and will be fixed in future versions.
#. Simulation runs may under certain circumstances produce different families
   of solutions for the same inputs
   (i.e. for the CO2 it is in the max range of 0.5 g/km).
   The bug is identified and will be fixed in future versions.
#. The calculations are sensitive to the input data provided, and in particular
   the time-series. Time series should originate from measurements/simulations
   that correspond to specific tests from which the input data were derived.
   Mixing time series from different vehicles, tests or cycles may produce
   results that lay outside the expected error band.
#. Heavily quantized velocity time-series may affect the accuracy of the
   results.
#. Ill-formatted input data may NOT produce warnings.
   Should you find a case where a warning should have been raised, we kindly
   ask you to communicate the finding to the developers.
#. Misspelled input-data which are not compulsory, are SILENTLY ignored, and
   the calculations proceed with alternative routes or default-values.
   Check that all your input-data are also contained in the output data
   (calibration files).
#. The A/T module has NOT been tested by the JRC due to the lack of respective
   test-data.
#. The A/T module should be further optimized with respect to the gear-shifting
   method applied for the simulations. An additional error of 0.5-1.5g/km  in
   the NEDC prediction is expected under the current configuration based
   on previous indications.
#. The model lacks a torque-converter / clutch module. JRC requested additional
   feedback on the necessity of such modules.
#. The electric systems module has not been tested with real test data.
   Cruise time series result in quantized squared-shaped signals which are,
   in general, different from analog currents recorded in real tests.
   More test cases are necessary.
#. Currently the electric system module requires input regarding both
   alternator current and battery current in  order to operate. Battery current
   vector can be set to zero but this may reduce the accuracy of the tool.
#. The preconditioning cycle and the respective functions has not been tested
   due to lack of corresponding data.


v0, Aug 2015: 1st unofficial release
====================================
Bugs reported from v0 with their status up to date:

#. 1s before acceleration "press clutch" not applied in WLTP:
   **not fixed**, lacking clutch module, problem not clear in Cruise time series,
   under investigation
#. Strange engine speed increase before and after standstill:
   **partly corrected**, lack of clutch, need further feedback on issue
#. Upshifting seems to be too early, also observed in WLTP, probably
   gearshift point is not "in the middle" of shifting:
   **not fixed**, will be revisited in future versions after comparing with
   cruise results
#. RPM peaks after stop don't match the real ones:
   **pending**, cannot correct based on Cruise inputs
#. Although temperature profile is simulated quite good, the consumption between
   urban and extra-urban part of NEDC is completely wrong:
   **problem partly fixed**, further optimization in UDC CO2 prediction
   will be attempted for future versions.
#. Delta-RCB is not simulated correctly due to a too high recuperation energy
   and wrong application down to standstill:
   **fixed**, the present release has a completely new module for
   calculating electric systems. Battery currents are necessary.
#. Output of more signals for analysis would be necessary:
   **fixed**, additional signals are added to the output file.
   Additional signals could be made available if necessary (which ones?)
#. Check whether a mechanical load (pumps, alternator and climate offset losses)
   as torque-input at the crankshaft is applied:
   **pending**, mechanical loads to be reviewed in future versions after more
   feedback is received.
#. Missing chassis dyno setting for warm-up delta correction:
   **unclear** how this should be treated (as a correction inside the tool or
   as a correction in the input data)
#. SOC Simulation: the simulation without the SOC input is much too optimistic
   in terms of recuperation / providing the SOC signals does not work as
   intended with the current version:
   **fixed**, please review new module for electrics.
#. The gearshift module 0.5.5 miscalculates gearshifts:
   **partially fixed**, the module is now included in CO2MPAS v1 but due to lack
   in test cases has not been further optimized.
#. Overestimation of engine-power in comparison to measurements:
   **indeterminate**, in fact this problem is vehicle specific. In the test-cases
   provided to the JRC both higher and lower power demands are experienced.
   Small deviations are expected to have a limited effect on the final calculation.
   What remains open is the amount of power demand over WLTP transient phases
   which so far appears to be systematically underestimated in the test cases
   available to the JRC.
#. Overestimation of fuel-consumption during cold start:
   **partially fixed**, cold start over UDC has been improved since V0.
#. CO2MPAS has a pronounced fuel cut-off resulting in zero fuel consumption
   during over-runs:
   **fixed**, indeed there was a bug in the cut-off operation associated to
   the amount of power flowing back to the engine while braking.
   A limiting function is now applied. Residual fuel consumption is foreseen
   for relatively low negative engine power demands (engine power> -2kW)
#. A 5 second start-stop anticipation should not occur in the case of A/T
   vehicles: **fixed**.
