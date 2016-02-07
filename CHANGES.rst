###############
CO2MPAS Changes
###############
.. contents::
.. _changes:

v1.1.0, 09-Feb 2016: "O'snow" release
================================================================
This release contains mainly model & I/O changes.
Several crucial bugs and enhancements have been been implemented based on
assessments performed by LAT.  A concise study of this release's results
and a high-level description of the model changes is contained in this `JRC-LAT presentation
<http://files.co2mpas.io/CO2MPAS-1.1.0/2016_02_1-JRC_LAT_CO2MPAS_Osnow-validation_n_changelog.pptx>`_.


Model-changes
-------------

- Engine model:

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

- Temperature model:

  - :gh:`118`, :gh:`53`: Possible to run hot start cycles & fixed
    temperature cycles.
  - :gh:`94`: Fix bug in ``co2_emission.calculate_normalized_engine_coolant_temperatures()``,
    that returned *0* when ``target_Theta > max-Theta`` in NEDC.
  - :gh:`79`: Enhance temperature model: the calibration does not take into account
    the first 10secs and the points where ``Delta-Theta = 0``.
  - :gh:`55`: Add an additional temperature model, ``f(previous_T, S, P, A)``;
    chose the one which gives the best results.

- Gearbox model:

  - :gh:`49`: Fix bug in the estimation of the gear box efficiency for negative power,
    leading to an overestimation of the gear box temperature. (still open)
  - :gh:`45`: ATs: Fix bug in the *GSPV matrix* leading to vertical up-shifting lines.

- S/S model:

  - :gh:`85`: Correct internal gear-shifting profiles according to legislation.
  - :gh:`81`: MTs: correct S/S model output -start engine- when ``gear > 0``.
  - :gh:`75`, :git:`3def98f3`: Fix gear-identification for
    initial time-steps for real-data; add warning message if WLTP does not
    respect input S/S activation time.

- Electrics model:

  - :gh:`78`, :gh:`46`: Fix bug in ``electrics.calibrate_alternator_current_model()``
    for real cars, fix fitting error when alternator is always off.
  - :gh:`17`: Add new alternator status model, bypassing the DT when ``battery_SOC_balance``
    is given, ``has_energy_recuperation`` equals to one, but BERS is not
    identified in WLTP. ???

- Clutch model:

  - :gh:`83`: Add a second clutch model, equals to no-clutch, when clutch model fails.
  - :gh:`16`: Add torque converter.

- Vehicle model:

  - :gh:`76`: Remove first 30 seconds for the engine speed model
    selection.
  - :git:`e8cabe10`, :git:`016e7060`: Rework model-selection code.


IO
--

- Inputs:

  - :gh:`62`: Compulsory fields in input data::

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


- Outputs:

  - :gh:`96`: Produce a single excel with all infos in multiple sheets.
  - Produce html report with basic interactive graphs.(still open)
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

- :gh:`88`: Don't produce results for incompatible ``VERSION`` in input-file.
- :gh:`102`: Remove UI pop-up boxes when running - users have to check
  the *scores* tables in the result xl-file.
- :gh:`91`: Disallow installation and/or execution under ``python < 3.4``.
- :gh:`5e91993c`: Add option to skip saving WLTP-prediction.


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
================================================================
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
