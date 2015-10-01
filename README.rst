##############################################################################
CO2MPAS: Vehicle simulator predicting NEDC CO2 emissions from WLTP time-series
##############################################################################

:Release:       1.0.1
:Sources:       https://github.com/JRCSTU/co2mpas
:Repository:    http://pypi.wltp.io/simple/co2mpas/
:Keywords:      CO2, wltp, engineering, scientific, python, excel, library,
:Developers:    .. include:: ../AUTHORS.rst
:Copyright:     2015 European Commission (`JRC-IET
                <https://ec.europa.eu/jrc/en/institutes/iet>`_)
:License:       `EUPL 1.1+ <https://joinup.ec.europa.eu/software/page/eupl>`_


CO2MPAS is backward-looking longitudinal-dynamics CO2 & fuel-consumption
simulator for Light-Duty Vehicles (cars and vans) specially crafted
to back-translate consumption figures from WLTP cycles into NEDC ones.

It is an open-source python-3 project, currently developed with python 3.4,
using Anaconda/WinPython under Windows 7, using Anaconda under MacOS, and
using Linux'sstandard python environment.
The program runs as a **console command**.

History
-------
The *European Commission* is supporting the introduction of the WLTP cycle
for Light-duty vehicles developed at the United Nations (UNECE)
level, in the shortest possible time-frame. Its introduction requires
the adaptation of CO2 certification and CO2 monitoring procedures set
by European Regulations. European Commission's *Joint Research Centre* has been
assigned the development of this vehicle simulator to facilitate this step.



Quickstart
----------
.. Tip::
    - Commands beginning with ``$`` symbol are for the *bash-console* (UNIX)
      i.e. the one included in the ``console.lnk`` file in top folder of
      the *all-in-one* distribution-archive (see :ref:`begin-install` below).

    - Windows's ``cmd.exe`` console commands begin with ``>`` symbol.
      You can adapt most UNIX commands with minor modifications
      (i.e. replace ``mkdir --> md``, '`rm --> del`` and ``cygstart --> start``).

    - In Windows you may download and install (unzip) the
      `Console 2 <http://sourceforge.net/projects/console/>`_
      application that supports a more decent way to copy-paste
      (BUT make sure that your command-interpreter contains the correct
      python installation).

IF you have familiarity with v1 release AND IF you already have a full-blown
*python-3 environment* (i.e. *Linux*) you can immediately start working with
the following console-commands; otherwise follow the detailed instructions
under sections :ref:`begin-install` and :ref:`begin-usage`.

.. code-block:: bash

    ## Install co2mpas
    $ pip install co2mpas --extra-index http://pypi.wltp.io/simple/ --trusted-host pypi.wltp.io

    ## Where to store input and output files.
    ## In *Windows* use `md` command instead.
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
The installation procedure is 2-stage procedure and requires internet connectivity:

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
    *sklearn* and *matplotlib* libraries that require a native C-compiler
    to install.

    For that reason, in *Windows* it is strongly suggested **NOT to install
    the standard CPython distribution** that comes up first if you google
    for "python"(!), unless you are an experienced python-developer, and
    you know how to hunt dependencies from *PyPi* repository and/or the
    `Unofficial Windows Binaries for Python Extension Packages
    <http://www.lfd.uci.edu/~gohlke/pythonlibs/>`_.

    Therefore we suggest that you download and unzip the **all-in-one archive**
    (distributed separately, due to its size ~500Mb).

    Otherwise, download one of the following 2 scientific-python distributions:

      #. `WinPython <https://winpython.github.io/>`_ **python-3** (prefer 64 bit)
      #. `Anaconda <http://continuum.io/downloads>`_ **python-3** (prefer 64 bit)



WinPython install
-----------------

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
1. Install CO2MPAS executable internally into your python-environment with
   the following console-command::

        > pip install co2mpas --extra-index http://pypi.wltp.io/simple/ --trusted-host pypi.wltp.io
        Collecting toolz
        Installing collected packages: co2mpas
        Successfully installed co2mpas-1.0.1

   .. Warning::
       In case of errors, re-run the command adding the *verbose* flags ``-vv``,
       copy-paste the console-output, and send it to JRC.


2. Check that when you run ``co2mpas``, the version executed is indeed the one
   installed above::

        > co2mpas --version
        1.0.1 at <your-python-folders>\compas


3. (optionally) Unzip the documents archive (distributed separately)
   to have them ready when inspecting the workflow for each simulation-run.
   (see :ref:`begin-usage`, below).

   To view them, open in your browser the ``index.html`` file.

4. (optionally) Download sources (download the latest ``zip`` archive
   from http://pypi.wltp.io/simple/co2mpas/) and unzip them; then
   install additional develop-time dependencies::

       > cd <sources-folder>
       > pip install -r requirements/dev.pip
       Collecting co2mpas


Upgrade CO2MPAS
---------------
To update CO2MPAS when a new minor release has been announced,
just append the ``-U --no-deps`` options in the ``pip`` command::

    > pip install co2mpas --extra-index http://pypi.wltp.io/simple/ --trusted-host pypi.wltp.io -U --no-deps

.. Note::
    In case CO2MPAS complains about a missing libraries, run the following command::

        pip install co2mpas --extra-index http://pypi.wltp.io/simple/ --trusted-host pypi.wltp.io -I

    If still in trouble, call JRC.


Uninstall CO2MPAS
-----------------
To uninstall CO2MPAS type the following command, and confirm it with ``y``::

    > pip uninstall co2mpas
    Uninstalling co2mpas-<installed-version>
    ...
    Proceed (y/n)?


Run the command *again*, to make sure that no dangling installations are left
over; disregard any errors this time.




.. _begin-usage:

Usage
=====
Ensure that the latest version of CO2MPAS is properly installed, and that
these instructions match its version.

The main entry for the simulator is the ``co2mpas`` console-command.
This command accepts multiple **input-excel-files**, one for each vehicle,
and generates a **summary-excel-file** aggregating the major result-values
from these vehicles, and (optionally) multiple **output-excel-files** for each
vehicle run.

To get the syntax of the ``co2mpas`` console-command, open a console where
you have installed CO2MPAS (see :ref:`begin-install` above) and type:

.. code-block:: bash

    $ co2mpas --help
    Predict NEDC CO2 emissions from WLTP cycles.

    Usage:
        co2mpas [options] [-I <folder>]  [-O <folder>]
        co2mpas example [-f | --force] <folder>
        co2mpas template [-f | --force] <excel-file> ...
        co2mpas --help
        co2mpas --version

    -I <folder>             Input folder, prompted with GUI if missing.
                            [default: ./input]
    -O <folder>             Input folder, prompted with GUI if missing.
                            [default: ./output]
    --more-output           Output also per-vehicle output-files.
    --no-warn-gui           Does not pause batch-run to report inconsistencies.
    --plot-workflow         Show workflow in browser, after run finished.
    -f --force              Overwrite template/sample excel-file(s).

    * Items enclosed in `[]` are optional.

Running samples
---------------
The simulator contains sample input files for 2 vehicles that
are a nice starting point to try out.

1. Choose a folder where you will store the *input* and *output* files:

   .. code-block:: bash

      $ cd <some-folder>       ## You should have created that hypothetical <some-folder>.
      $ mkdir input output     ## Replace `mkdir` with `md` in *Windows* (`cmd.exe`)

  .. Note::
    The input & output folders do not have to reside in the same parent.
    It is only for demonstration purposes that we decided to group them both
    under a hypothetical ``some-folder``.

3. Create the example vehicles inside the *input-folder* with the ``template``
   sub-command:


   .. code-block:: bash

        $ co2mpas example input
        Creating co2mpas EXAMPLE input-file 'D:\Apps\cygwin64\home\anastkn\Work\tut\input\co2mpas_example_1_full_data.xlsx'...
        Creating co2mpas EXAMPLE input-file 'D:\Apps\cygwin64\home\anastkn\Work\tut\input\co2mpas_example_2_wltp_high_only.xlsx'...
        Creating co2mpas EXAMPLE input-file 'D:\Apps\cygwin64\home\anastkn\Work\tut\input\co2mpas_example_3_wltp_low_only.xlsx'...
        Creating co2mpas EXAMPLE input-file 'D:\Apps\cygwin64\home\anastkn\Work\tut\input\co2mpas_example_4_baseline_no_battery_currents - Copy.xlsx'...
        Creating co2mpas EXAMPLE input-file 'D:\Apps\cygwin64\home\anastkn\Work\tut\input\co2mpas_example_5_baseline_no_gears.xlsx'...


4. Run the simulator:

   .. code-block:: bash

      $ co2mpas -I input -O output
      Processing './input' --> './output'...
      Processing: co2mpas_example_1_full_data
      ...
      ...
      Done! [90.765501 sec]


6. Inspect the results:

   .. code-block:: bash

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

   .. code-block:: bash

        $ rm -r ./input/* ./output/*        Replace `rm` with `del` in *Windows* (`cmd.exe`)


2. Create an empty vehicle template-file (eg. ``vehicle_1.xlsx``) inside
   the *input-folder* with the ``template`` sub-command:

   .. code-block:: bash

        $ co2mpas template input/vehicle_1.xlsx  ## Note that here we specify the filename, not the folder!
        Creating co2mpas INPUT template-file './input/vehicle_1.xlsx'...


3. Open the template excel-file to fill-in your vehicle data
   (and save it afterwards):

   .. code-block:: bash

      $ cygstart input/vehicle_1.xlsx        ## Opens the excel-file. Use `start` in *cmd.exe*.

   .. Tip::
       The generated file contains help descriptions to help you populate it
       with vehicle data.  For items where an array of values is required
       (i.e. gear-box ratios) you may reference different parts of
       the spreadsheet following the syntax of `the "xlref" mini-language
       <https://pandalone.readthedocs.org/en/latest/reference.html#module-pandalone.xleash>`_.

   You may repeat these last 2 steps if you want to add more vehicles in
   the *batch-run*.

4. Run the simulator:

   .. code-block:: bash

      $ co2mpas -I input -O output
      Processing './input' --> './output'...
      Processing: vehicle_1
      ...
      Done! [12.938986 sec]

5. Assuming you do receive any error, you may now inspect the results:

   .. code-block:: bash

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

