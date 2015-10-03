##############################################################################
CO2MPAS: Vehicle simulator predicting NEDC CO2 emissions from WLTP time-series
##############################################################################

:Release:       1.0.2b1
:Home:          http://co2mpas.io/
:Releases:      http://files.co2mpas.io/
:Sources:       https://github.com/JRCSTU/co2mpas
:pypi-repo:     http://pypi.co2mpas.io/
:Keywords:      CO2, fuel-consumption, WLTP, NEDC, vehicle, simulator,
                EU, JRC, IET, STU, back-translation, policy,
                engineering, scientific
:Developers:    .. include:: ../AUTHORS.rst
:Copyright:     2015 European Commission (`JRC-IET
                <https://ec.europa.eu/jrc/en/institutes/iet>`_)
:License:       `EUPL 1.1+ <https://joinup.ec.europa.eu/software/page/eupl>`_


**CO2MPAS** is backward-looking longitudinal-dynamics CO2 & fuel-consumption
simulator for Light-Duty Vehicles (cars and vans) specially crafted
to back-translate consumption figures from WLTP cycles into NEDC ones.

It is an open-source project developed with Python-3.4,
using Anaconda & WinPython under Windows 7, Anaconda under MacOS, and
Linux's standard python environment.
The program runs as a *console command*.

History
-------
The *European Commission* is supporting the introduction of the *WLTP cycle*
for Light-duty vehicles developed at the *United Nations (UNECE)*
level, in the shortest possible time-frame. Its introduction requires
the adaptation of CO\ :sub:`2` certification and monitoring procedures set
by European regulations. European Commission's *Joint Research Centre* has been
assigned the development of this vehicle simulator to facilitate this
adaptation.



Quickstart
----------
.. Tip::
    - Commands beginning with ``$`` symbol are for the *bash-console* (UNIX)
      i.e. the one included in the ``console.lnk`` file in top folder of
      the *all-in-one* distribution-archive (see :ref:`begin-install` below).

    - Windows's ``cmd.exe`` console commands begin with ``>`` symbol.
      You can adapt most UNIX commands with minor modifications
      (i.e. replace ``mkdir --> md``, ``rm --> del`` and ``cygstart --> start``).

    - In Windows you may download and install `Portable Git
      <https://github.com/sheabunge/GitPortable>`_ which contains *bash* and
      other unix-utilities, run from a *console* supporting decent copy-paste
      (BUT make sure you run the correct Python installation, by setting
      your ``PATH`` variable appropriately).

    - To get generic help for *bash* commands (``ls``, ``pwd``, ``cd``, etc),
      you can try any of the VARIOUS tutorials and crash-courses available:

          - a concise one: http://www.ks.uiuc.edu/Training/Tutorials/Reference/unixprimer.html
          - or a more detailed guide (just ignore the linux-specific part):
            http://linuxcommand.org/lc3_lts0020.php

IF you have familiarity with v1 release AND IF you already have a full-blown
*python-3 environment* (i.e. *Linux*) you can immediately start working with
the following console-commands; otherwise follow the detailed instructions
under sections :ref:`begin-install` and :ref:`begin-usage`.

.. code-block:: console

    ## Install co2mpas.
    ## NOTE: If behind proxy, specify additionally this option:
    ##    --proxy http://user:password@yourProxyUrl:yourProxyPort
    ##
    $ pip install co2mpas --extra-index http://pypi.co2mpas.io/simple/ --trusted-host pypi.co2mpas.io

    ## Where to store input and output files.
    ## In *Windows* cmd-prompt use `md` command instead.
    $ mkdir input output

    ## Create a template excel-file for inputs.
    $ co2mpas template input/vehicle_1.xlsx

    ###################################################
    ## Edit generated `./input/vehicle_1.xlsx` file.  ##
    ###################################################

    ## Run simulator.
    $ co2mpas -I input -O output

    ###################################################
    ## Inspect generated results inside `./output/`. ##
    ###################################################


.. _end-opening:
.. contents:: Table of Contents
  :backlinks: top



.. _begin-install:

Install
=======
The installation procedure has 2-stages:

1. Install (or Upgrade) Python (2 choices under *Windows*).
2. Install CO2MPAS:
    a. Install (or Upgrade) executable.
    b. (optional) Install documents.
    c. (optional) Install sources.

If you have already have a suitable python-3 installation with all scientific
packages updated to their latest versions, you may skip the 1st stage.

.. Note::
    **Installing Python under Windows:**

    The program requires CPython-3, and depends on *numpy*, *scipy*, *pandas*,
    *sklearn* and *matplotlib* packages which have C-native backends, and need
    a C-compiler in order to to install them from sources.

    In *Windows* it is strongly suggested
    **NOT to install the standard CPython distribution**
    (then one that comes up first(!) if you google for "python windows"),
    unless you are an experienced python-developer, and you know also how to
    hunt down pre-compiled dependencies from the *PyPi* repository and/or
    the `Unofficial Windows Binaries for Python Extension Packages
    <http://www.lfd.uci.edu/~gohlke/pythonlibs/>`_.

    Therefore we suggest that you download and unzip the **all-in-one archive**
    (distributed separately, due to its size ~500Mb).

    Alternatively, download one of the following two scientific-python
    distributions:

      #. `WinPython <https://winpython.github.io/>`_ **python-3** (prefer 64 bit)
      #. `Anaconda <http://continuum.io/downloads>`_ **python-3** (prefer 64 bit)



WinPython install
-----------------
The *WinPython* distribution is just a collection of the pre-compiled binaries
for *Windows* containing all the scientific packages we need, and much more.
It is not update-able, and has a semi-regular release-cycle of 3 months.


1. Install the latest python-3 (preferably 64 bit) from https://winpython.github.io/.
   Prefer an installation-folder without any spaces leading to it.

2. Open the WinPython's command-prompt console, by locating the folder where
   you just installed it and run (double-click) the following file::

        <winpython-folder>\"WinPython Command Prompt.exe"


3. In the console-window check that you have the correct version of
   WinPython installed, by typing::

        > python --version
        Python 3.4.3

        > where python      ## Check your python's location is where you installed it.
        ....


4. Use this console and follow CO2MPAS-executable installation instructions
   (see :ref:`begin-co2mpas-install`, below)



Anaconda install
----------------
The *Anaconda* distribution is a non-standard Python environment that
for *Windows* containing all the scientific packages we need, and much more.
It is not update-able, and has a semi-regular release-cycle of 3 months.

1. Install Anaconda python 3.4 (preferably 64 bit) from http://continuum.io/downloads.
   Prefer an installation-folder without any spaces leading to it.

   .. Note::
        When asked by the installation wizard, ensure that *Anaconda* gets to be
        registered as the default python-environment for the user's account.

2. Open a *Windows* command-prompt console::

        "windows start button" --> `cmd.exe`

3. In the console-window check that you have the correct version of
   Anaconda-python installed, by typing::

        > python --version
        Python 3.4.3 :: Anaconda 2.3.0 (64-bit)

        > where python      ## Check your python's location is where you installed it.
        ....

4. Use this console and follow CO2MPAS-executable installation instructions
   (see :ref:`begin-co2mpas-install`, below)


.. _begin-co2mpas-install:

CO2MPAS install
---------------
.. Tip::
    This step requires Internet connectivity to Python's "standard" repository
    (https://pypi.python.org/). In case you are behind a **corporate proxy**,
    append an appropriate option to the ``pip`` commands that follow::

        --proxy http://user:password@yourProxyUrl:yourProxyPort


1. Install CO2MPAS executable internally into your python-environment with
   the following console-command::

        > pip install co2mpas --extra-index http://pypi.co2mpas.io/simple/ --trusted-host pypi.co2mpas.io
        Collecting co2mpas
        Downloading http://pypi.co2mpas.io/packages/co2mpas-...
        ...
        Installing collected packages: co2mpas
        Successfully installed co2mpas-1.0.2b1

   .. Warning::
       In case of errors, re-run the command adding the *verbose* flags ``-vv``,
       copy-paste the console-output, and send it to JRC.

2. Check that when you run ``co2mpas``, the version executed is indeed the one
   installed above::

        > co2mpas --version
        co2mpas-1.0.2b1 at <your-python-folders>\compas


Upgrade CO2MPAS
---------------
There are 2 ways to upgrade:

1. (preferred) Uninstall and re-install it.
2. Use the `pip` *--upgrade* option:
   To update CO2MPAS when a new minor release has been announced,
   just append the ``-U --no-deps`` options in the ``pip`` command::

       > pip install co2mpas --extra-index http://pypi.co2mpas.io/simple/ --trusted-host pypi.co2mpas.io -U --no-deps

   .. Note::
       In case CO2MPAS complains about a missing libraries, run the following command::

           pip install co2mpas --extra-index http://pypi.co2mpas.io/simple/ --trusted-host pypi.co2mpas.io -I

       Don't forget to specify your "proxy" option, if applicable.
       If still in trouble, call JRC.


Uninstall CO2MPAS
-----------------
To uninstall CO2MPAS type the following command, and confirm it with ``y``::

    > pip uninstall co2mpas
    Uninstalling co2mpas-<installed-version>
    ...
    Proceed (y/n)?


Re-run the command *again*, to make sure that no dangling installations are left
over; disregard any errors this time.



.. _begin-usage:

Usage
=====
.. Note::
    The following commands are for the **bash console**, specifically tailored
    for the **all-in-one** archive.  More specific instructions for this archive
    are contained within it.


First ensure that the latest version of CO2MPAS is properly installed, and that
its version match the version declared on this file.

The main entry for the simulator is the ``co2mpas`` console-command.
This command accepts multiple **input-excel-files**, one for each vehicle,
and generates a **summary-excel-file** aggregating the major result-values
from these vehicles, and (optionally) multiple **output-excel-files** for each
vehicle run.

To get the syntax of the ``co2mpas`` console-command, open a console where
you have installed CO2MPAS (see :ref:`begin-install` above) and type:

.. code-block:: console

    $ co2mpas --help
    Predict NEDC CO2 emissions from WLTP cycles.

    Usage:
        co2mpas [simulate] [--more-output] [--no-warn-gui] [--plot-workflow] [-I <folder>] [-O <folder>]
        co2mpas example    [--force] <folder>
        co2mpas template   [--force] <excel-file-path> ...
        co2mpas ipynb      [--force] <folder>
        co2mpas --help
        co2mpas --version

    -I <folder>      Input folder, prompted with GUI if missing [default: ./input]
    -O <folder>      Input folder, prompted with GUI if missing [default: ./output]
    --more-output    Output also per-vehicle output-files.
    --no-warn-gui    Does not pause batch-run to report inconsistencies.
    --plot-workflow  Show workflow in browser, after run finished.
    -F, --force      Overwrite template/sample excel-file(s).


    Sub-commands:
        simulate [default] Run simulation for all excel-files in input-folder (-I).
        example  Generate demo input-files inside <folder>.
        template Generate "empty" input-file at <excel-file-path>.
        ipynb    Generate IPython notebooks inside <folder>; view them with cmd:
                    ipython --notebook-dir=<folder>

    * Items enclosed in `[]` are optional.

    Examples:

        ## Create sample-vehicles inside the `input` folder.
        ## (the `input` folder must exist)
        co2mpas example input

        ## Run the sample-vehicles just created.
        ## (the `output` folder must exist)
        co2mpas -I input -O output

        ## Create an empty vehicle-file inside `input` folder.
        co2mpas template input/vehicle_1.xlsx

Running samples
---------------
The simulator contains sample input files for 2 vehicles that
are a nice starting point to try out.

1. Choose a folder where you will store the *input* and *output* files:

   .. code-block:: console

      $ cd <some-folder>       ## You should have created that hypothetical <some-folder>.
      $ mkdir input output     ## Replace `mkdir` with `md` in *Windows* (`cmd.exe`)

  .. Note::
    The input & output folders do not have to reside in the same parent.
    It is only for demonstration purposes that we decided to group them both
    under a hypothetical ``some-folder``.

3. Create the example vehicles inside the *input-folder* with the ``template``
   sub-command:


   .. code-block:: console

        $ co2mpas example input
        Creating EXAMPLE INPUT file 'D:\Apps\cygwin64\home\anastkn\Work\tut\input\co2mpas_example_1_full_data.xlsx'...
        Creating EXAMPLE INPUT file 'D:\Apps\cygwin64\home\anastkn\Work\tut\input\co2mpas_example_2_wltp_high_only.xlsx'...
        Creating EXAMPLE INPUT file 'D:\Apps\cygwin64\home\anastkn\Work\tut\input\co2mpas_example_3_wltp_low_only.xlsx'...
        Creating EXAMPLE INPUT file 'D:\Apps\cygwin64\home\anastkn\Work\tut\input\co2mpas_example_4_baseline_no_battery_currents - Copy.xlsx'...
        Creating EXAMPLE INPUT file 'D:\Apps\cygwin64\home\anastkn\Work\tut\input\co2mpas_example_5_baseline_no_gears.xlsx'...


4. Run the simulator:

   .. code-block:: console

      $ co2mpas -I input -O output
      Processing './input' --> './output'...
      Processing: co2mpas_example_1_full_data
      ...
      ...
      Done! [90.765501 sec]


6. Inspect the results:

   .. code-block:: console

      $ cygstart output/*summary.xlsx       ## More summaries might exist in the folder from previous runs.
      $ cygstart output                     ## View the folder with all files generated.


Entering new vehicles
---------------------
You may modify the samples vehicles and run again the model.
But to be sure that your vehicle does not contain by accident any of
the sample-data, use the ``template`` sub-command to make an *empty* input
excel-file:


1. Decide the *input/output* folders.  Assuming we want to re-use the folders
   from the above example, we should just clear everything that they contain:

   .. code-block:: console

        $ rm -r ./input/* ./output/*        Replace `rm` with `del` in *Windows* (`cmd.exe`)


2. Create an empty vehicle template-file (eg. ``vehicle_1.xlsx``) inside
   the *input-folder* with the ``template`` sub-command:

   .. code-block:: console

        $ co2mpas template input/vehicle_1.xlsx  ## Note that here we specify the filename, not the folder!
        Creating TEMPLATE INPUT file './input/vehicle_1.xlsx'...


3. Open the template excel-file to fill-in your vehicle data
   (and save it afterwards):

   .. code-block:: console

      $ cygstart input/vehicle_1.xlsx        ## Opens the excel-file. Use `start` in *cmd.exe*.

   .. Tip::
       The generated file contains help descriptions to help you populate it
       with vehicle data.  For items where an array of values is required
       (i.e. gear-box ratios) you may reference different parts of
       the spreadsheet following the syntax of the `"xlref" mini-language
       <https://pandalone.readthedocs.org/en/latest/reference.html#module-pandalone.xleash>`_.

   You may repeat these last 2 steps if you want to add more vehicles in
   the *batch-run*.

4. Run the simulator:

   .. code-block:: console

      $ co2mpas -I input -O output
      Processing './input' --> './output'...
      Processing: vehicle_1
      ...
      Done! [12.938986 sec]

5. Assuming you do receive any error, you may now inspect the results:

   .. code-block:: console

      $ cygstart output/*summary.xlsx       ## More summaries might open from previous runs.
      $ cygstart output                     ## View all files generated (see below).


6. In the case of errors, or if the results are not satisfactory, repeat the
   above procedure from step 3 to modify the vehicle and re-run the model.
   See also :ref:`begin-debug`, below.

Output files
------------
Below is the structure of the output-files produced for each vehicle::

    +--<date>-<time>_precondition_WLTP_<inp-fname>.xls:
    |               Input and calibrated values for electrics.
    |
    +--<date>-<time>_calibration_WLTP-H_<inp-fname>.xls:
    |               Input and calibrated values.
    |
    +--<date>-<time>_calibration_WLTP-L_<inp-fname>.xls:
    |               Input and calibrated values.
    |
    +--<date>-<time>_prediction_NEDC_<inp-fname>.xls:
    |               Input and predicted values.
    |
    +--<date>-<time>_summary.xls:
                    Major CO2 values from all vehicles in the batch-run.


.. _begin-debug:

Debugging and investigating results
-----------------------------------

- Make sure that you have installed `graphviz` and invoke the `co2mpas` cmd
  with the ``--plot-workflow`` option.
- Inspect the functions mentioned in the workflow and search them in the
  **documentstion** (archive distributed separately).

