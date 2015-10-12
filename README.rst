##################################################################
CO2MPAS: Vehicle simulator predicting NEDC CO2 emissions from WLTP
##################################################################

:Release:       1.0.3b0
:Home:          http://co2mpas.io/
:Releases:      http://files.co2mpas.io/
:Sources:       https://github.com/JRCSTU/co2mpas
:pypi-repo:     http://pypi.co2mpas.io/ (will move to standard Python-repo in the future)
:Keywords:      CO2, fuel-consumption, WLTP, NEDC, vehicle, automotive,
                EU, JRC, IET, STU, back-translation, policy,
                simulator, engineering, scientific
:Developers:    .. include:: ../AUTHORS.rst
:Copyright:     2015 European Commission (`JRC-IET
                <https://ec.europa.eu/jrc/en/institutes/iet>`_)
:License:       `EUPL 1.1+ <https://joinup.ec.europa.eu/software/page/eupl>`_


**CO2MPAS** is backward-looking longitudinal-dynamics CO\ :sub:`2` and
fuel-consumption simulator for light-duty vehicles (cars and vans),
specially crafted to back-translate consumption figures from WLTP cycles
into NEDC ones.

It is an open-source project developed with Python-3.4,
using Anaconda & WinPython under Windows 7, Anaconda under MacOS, and
Linux's standard python environment.
The program runs as a *console command*.

History
=======
The *European Commission* is supporting the introduction of the *WLTP cycle*
for Light-duty vehicles developed at the *United Nations (UNECE)*
level, in the shortest possible time-frame. Its introduction requires
the adaptation of CO\ :sub:`2` certification and monitoring procedures set
by European regulations. European Commission's *Joint Research Centre* has been
assigned the development of this vehicle simulator to facilitate this
adaptation.



Quickstart
==========
.. Tip::
    **Help about Console:**

    - Commands beginning with ``$`` symbol are for the *bash-console* (UNIX)
      i.e. the one included in the ``bash-console.bat`` file in top folder of
      the *all-in-one* distribution-archive (see :doc:`allinone`).

    - Windows's ``cmd.exe`` console commands begin with ``>`` symbol.
      You can adapt most UNIX commands with minor modifications
      (i.e. replace ``mkdir --> md``, ``rm --> del``).

    - You may download and install *all-in-one* archive which contains *bash*
      and and `cmd.exe` prompt configured in a *console* supporting decent
      copy-paste and resizing.


IF you have familiarity with v1 release AND IF you already have a full-blown
*python-3 environment* (i.e. *Linux* or the *all-in-one* archive) you can
immediately start working with the following *bash* commands; otherwise
follow the detailed instructions under sections :ref:`begin-install` and
:ref:`begin-usage`.

.. code-block:: console

    ## Install co2mpas.
    ## NOTE: If behind proxy, specify additionally this option:
    ##    --proxy http://user:password@yourProxyUrl:yourProxyPort
    ##
    $ pip install co2mpas --extra-index http://pypi.co2mpas.io/simple/ --trusted-host pypi.co2mpas.io --pre

    ## Where to store input and output files.
    ## In *Windows* cmd-prompt use `md` command instead.
    $ mkdir input output

    ## Create a template excel-file for inputs.
    $ co2mpas template input/vehicle_1.xlsx

    ###################################################
    ## Edit generated `./input/vehicle_1.xlsx` file. ##
    ###################################################

    ## Run simulator.
    $ co2mpas -I input -O output

    ###################################################
    ## Inspect generated results inside `./output/`. ##
    ###################################################


.. _end-opening:
.. contents:: Table of Contents
  :backlinks: top
  :depth: 4



.. _begin-install:

Install
=======
The installation procedure has 2-stages:

1. Install (or Upgrade) Python (2 choices under *Windows*).
2. Install CO2MPAS:
    a. Install (or Upgrade) executable.
    b. (optional) Install documents.
    c. (optional) Install sources.

On *Windows* you may alternatively download in unzip the *all-In-One* archive
instead of performing the above 2 steps separately.

.. Tip::
    **Installing All-In-One archive under Windows:**

    - Download **all-in-one archive** from
      http://files.co2mpas.io/.

    - Ensure that you download the correct 32/64 architecture for your PC
      (the 64bit archive CANNOT run on 32bit PCs, but the opposite is acceptable).

    - Use the `"7z" extraxtor <http://portableapps.com/apps/utilities/7-zip_portable>`_,
      since the "plain-zip" may produce minor errors when expanding long directories.

    - If you have already downloaded a previous version of the *all-in-one*
      archive, you may just upgrade CO2MPAS contained within.

    - After installation, check that the version of CO2MPAS contained in the
      archive corrseponds to the one described in the instructions here.
      If not, upgrade it by following the instructions in the respective
      section, below.


Python Installation
-------------------
If you have already a suitable python-3 installation with all scientific
packages updated to their latest versions, you may skip this 1st stage.

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

    Therefore we suggest that you download one of the following two
    *scientific-python* distributions:

      #. `WinPython <https://winpython.github.io/>`_ **python-3** (prefer 64 bit)
      #. `Anaconda <http://continuum.io/downloads>`_ **python-3** (prefer 64 bit)



Install WinPython
~~~~~~~~~~~~~~~~~
The *WinPython* distribution is just a collection of the pre-compiled binaries
for *Windows* containing all the scientific packages we need, and much more.
It is not update-able, and has a semi-regular release-cycle of 3 months.


1. Install the latest python-3 (preferably 64 bit) from https://winpython.github.io/.
   Prefer an installation-folder without any spaces leading to it.

2. Open the WinPython's command-prompt console, by locating the folder where
   you just installed it and run (double-click) the following file::

        <winpython-folder>\"WinPython Command Prompt.exe"


3. In the console-window check that you have the correct version of
   WinPython installed, and expect a similar response:

   .. code-block:: console

        > python --version
        Python 3.4.3

        REM Check your python is indeed where you installed it.
        > where python
        ....


4. Use this console and follow CO2MPAS-installation instructions, below.



Install Anaconda
~~~~~~~~~~~~~~~~
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
   Anaconda-python installed, by typing:

   .. code-block:: console

        > python --version
        Python 3.4.3 :: Anaconda 2.3.0 (64-bit)

        REM Check your python is indeed where you installed it.
        > where python
        ....

4. Use this console and follow CO2MPAS-executable installation instructions
   (see :ref:`begin-co2mpas-install`, below)



.. _begin-co2mpas-install:

CO2MPAS installation
--------------------
1. Install CO2MPAS executable internally into your python-environment with
   the following console-command:

   .. code-block:: console

        > pip install co2mpas --extra-index http://pypi.co2mpas.io/simple/ --trusted-host pypi.co2mpas.io  --pre
        Collecting co2mpas
        Downloading http://pypi.co2mpas.io/packages/co2mpas-...
        ...
        Installing collected packages: co2mpas
        Successfully installed co2mpas-1.0.3b0

   .. Note::
        **Installing Behind Firewall:**

        This previous step requires http-connectivity to Python's
        "standard" repository (https://pypi.python.org/) and to co2mpas-site.
        In case you are behind a **corporate proxy**, you may either:

        a) Append the following option to all ``pip`` commands, appropriatly
           adapted: ``--proxy http://user:password@yourProxyUrl:yourProxyPort``.

           For averting any security deliberations, JRC cryptographically signes
           all *final releases*, so that you or your IT staff may
           `validate their authenticity
           <https://www.davidfischer.name/2012/05/signing-and-verifying-python-packages-with-pgp/>`_
           and detect *man-in-the-middle* attacks, however impossible.

        b) Download all *wheel* packages from `co2mpas-site
           <http://files.co2mpas.io>`_ for the specific version you are
           intereseted in , and install them one by one:

           .. code-block:: console

                REM Download MANUALLY all `*.whl` files contained in release folder
                REM from co2mpas-site in some folder.
                > cd <folder-where-wheels_downloaded>
                > pip install *.whl


   .. Warning::
       If you cannot install CO2MPAS, re-run the command adding 2 *verbose*
       flags ``-vv``, copy-paste the console-output, and send it to JRC.


2. Check that when you run ``co2mpas``, the version executed is indeed the one
   installed above:

   .. code-block:: console

        > python -v --version
        co2mpas_version: 1.0.3b0
        co2mpas_path: d:\co2mpas_ALLINONE-XXbit-v1.0.3b0\Apps\WinPython\python-3.4.3\lib\site-packages\co2mpas
        python_path: D:\co2mpas_ALLINONE-XXbit-v1.0.3b0\WinPython\python-3.4.3
        python_version: 3.4.3 (v3.4.3:9b73f1c3e601, Feb 24 2015, 22:44:40) [MSC v.1600 XXX]


   .. Warning::
        The above procedure installs the *latest* CO2MPAS, which
        *might be more up-to-date than the version described here!*

        In that case you can either:

        a) Visit the documents for the CO2MPAS version actually installed.
        b) "Pin" the exact version to install with a ``pip`` command like this:

           .. code-block:: console

                > pip install co2mpas==1.0.3b0 ... # Other options, like above.



Install extras
~~~~~~~~~~~~~~
Internally CO2MPAS uses an algorithmic scheduler to execute model functions.
In order to visualize the *design-time models* and/or *run-time workflows*
you need to install the **Graphviz** graph visualization library  from:
http://www.graphviz.org/.

If you skip this step, the ``graphplot`` sub-command and the ``--plot-workflow``
option would both fail (see :ref:`begin-debug` below).



Upgrade CO2MPAS
~~~~~~~~~~~~~~~

1. Uninstall (see below) and re-install it.


Uninstall CO2MPAS
~~~~~~~~~~~~~~~~~
To uninstall CO2MPAS type the following command, and confirm it with ``y``:

.. code-block:: console

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
    for the **all-in-one** archive.  More generic guidelines for this archive
    are contained in :doc:`allinone`.


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
        co2mpas [simulate] [-v] [--predict-wltp] [--more-output] [--no-warn-gui] [--plot-workflow]
                           [-I <fpath>] [-O <fpath>]
        co2mpas demo       [-v] [-f] <folder>
        co2mpas template   [-v] [-f] <excel-file-path> ...
        co2mpas ipynb      [-v] [-f] <folder>
        co2mpas modelgraph [-v] [-l | <models> ...]
        co2mpas [-v] --version
        co2mpas --help

    -I <fpath>       Input folder or file, prompted with GUI if missing [default: ./input]
    -O <fpath>       Input folder or file, prompted with GUI if missing [default: ./output]
    -l, --list       List available models.
    --predict-wltp   Whether predict also WLTP values.
    --more-output    Output also per-vehicle output-files.
    --no-warn-gui    Does not pause batch-run to report inconsistencies.
    --plot-workflow  Open workflow-plot in browser, after run finished.
    -f, --force      Overwrite template/sample excel-file(s).
    -v, --verbose    Print more verbosely messages.

    * Items enclosed in `[]` are optional.


    Sub-commands:
        simulate    [default] Run simulation for all excel-files in input-folder (-I).
        demo        Generate demo input-files inside <folder>.
        template    Generate "empty" input-file at <excel-file-path>.
        ipynb       Generate IPython notebooks inside <folder>; view them with cmd:
                      ipython --notebook-dir=<folder>
        modelgraph  List all or plot available models.

    Examples:

        # Create sample-vehicles inside the `input` folder.
        # (the `input` folder must exist)
        co2mpas demo input

        # Run the sample-vehicles just created.
        # (the `output` folder must exist)
        co2mpas -I input -O output

        # Create an empty vehicle-file inside `input` folder.
        co2mpas template input/vehicle_1.xlsx

        # View a specific submodel on your browser.
        co2mpas modelgraph gear_box_calibration

Running Samples
---------------
The simulator contains sample input files for 2 vehicles that
are a nice starting point to try out.

1. Choose a folder where you will store the *input* and *output* files:

   .. code-block:: console

        ## Skip this if ``tutorial`` folder already exists.
        $ mkdir tutorial         ## Replace `mkdir` with `md` in *Windows* (`cmd.exe`)
        $ cd tutorial

        ## Skip also this if folders exist.
        $ mkdir input output

  .. Note::
    The input & output folders do not have to reside in the same parent,
    neither to have these names.
    It is only for demonstration purposes that we decided to group them both
    under a hypothetical ``some-folder``.

3. Create the demo vehicles inside the *input-folder* with the ``template``
   sub-command:


   .. code-block:: console

        $ co2mpas demo input
        Creating DEMO INPUT file 'D:\Apps\cygwin64\home\anastkn\Work\tut\input\co2mpas_demo_1_full_data.xlsx'...
        Creating DEMO INPUT file 'D:\Apps\cygwin64\home\anastkn\Work\tut\input\co2mpas_demo_2_wltp_high_only.xlsx'...
        Creating DEMO INPUT file 'D:\Apps\cygwin64\home\anastkn\Work\tut\input\co2mpas_demo_3_wltp_low_only.xlsx'...
        Creating DEMO INPUT file 'D:\Apps\cygwin64\home\anastkn\Work\tut\input\co2mpas_demo_4_baseline_no_battery_currents - Copy.xlsx'...
        Creating DEMO INPUT file 'D:\Apps\cygwin64\home\anastkn\Work\tut\input\co2mpas_demo_5_baseline_no_gears.xlsx'...
        You may run DEMOS with:
            co2mpas simulate -I input

4. Run the simulator:

   .. code-block:: console

      $ co2mpas -I input -O output
      Processing './input' --> './output'...
      Processing: co2mpas_demo_1_full_data
      ...
      ...
      Done! [90.765501 sec]


6. Inspect the results:

   .. code-block:: console

      $ start output/*summary.xlsx       ## More summaries might exist in the folder from previous runs.
      $ start output                     ## View the folder with all files generated.


Output files
~~~~~~~~~~~~
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


Entering new vehicles
---------------------
You may modify the samples vehicles and run again the model.
But to be sure that your vehicle does not contain by accident any of
the sample-data, use the ``template`` sub-command to make an *empty* input
excel-file:


1. Decide the *input/output* folders.  Assuming we are still in the ``tutorial``
   folder and we wish to re-use the ``input/output`` folders from the example
   above, we may clear all their contents with this:

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

      $ start input/vehicle_1.xlsx        ## Opens the excel-file. Use `start` in *cmd.exe*.

   .. Tip::
       The generated file contains help descriptions to help you populate it
       with vehicle data.  For items where an array of values is required
       (i.e. gear-box ratios) you may reference different parts of
       the spreadsheet following the syntax of the `"xlref" mini-language
       <https://pandalone.readthedocs.org/en/latest/reference.html#module-pandalone.xleash>`_.

   You may repeat these last 2 steps if you want to add more vehicles in
   the *batch-run*.

4. Run the simulator.  You may specify to run exactly the single excel-file:

   .. code-block:: console

      $ co2mpas -I ./input/vehicle_1.xlsx -O output
      Processing './input/vehicle_1.xlsx' --> 'output'...
      Processing: vehicle_1
      ...
      Done! [12.938986 sec]

5. Assuming you do receive any error, you may now inspect the results:

   .. code-block:: console

      $ start output/*summary.xlsx       ## More summaries might open from previous runs.
      $ start output                     ## View all files generated (see below).


6. In the case of errors, or if the results are not satisfactory, repeat the
   above procedure from step 3 to modify the vehicle and re-run the model.
   See also :ref:`begin-debug`, below.


Using IPython
-------------
You may enter the data for a single vehicle and run its simulation, plot its
results and experiment in your browser using `IPython <http://ipython.org/>`_.

The usage pattern is similar to "demos" but requires to have **ipython**
installed:

1. Ensure *ipython* with *notebook* "extra" is installed:

   .. Warning::
        This step requires too many libraries to provide as standalone files,
        so unless you have it already installed, you will need a proper
        *http-connectivity* to the standard python-repo.

   .. code-block:: console

        $ pip install ipython[notebook]
        Installing collected packages: ipython[notebook]
        ...
        Successfully installed ipython-x.x.x notebook-x.x.x


2. Then create the demo ipython-notebook(s) into some folder
   (i.e. assuming the same setup from above, ``tutorial/input``):

   .. code-block:: console

        $ pwd                     ## Check our current folder (``cd`` alone for Windows).
        .../tutorial

        $ co2mpas ipynb ./input

3. Start-up the server and open a browser page to run the vehicle-simulation:

   .. code-block:: console

        $ ipython notebook ./input

4. A new window should open to your default browser (AVOID IEXPLORER) listing
   the ``simVehicle.ipynb`` notebook (and all the demo xls-files).
   Click on the ``*.ippynb`` file to "load" the notebook in a new tab.

   The results are of a simulation run already pre-generated for this notebook
   but you may run it yourself again, by clicking the menu::

        "menu" --> `Cell` --> `Run All`

   And watch it as it re-calculates *cell* by cell.

5. You may edit the python code on the cells by selecting them and clicking
   ``Enter`` (the frame should become green), and then re-run them,
   with ``Ctrl + Enter``.

   Navigate your self around by taking the tutorial at::

        "menu" --> `Help` --> `User Interface Tour`

   And study the example code and diagrams.

6. When you have finished, return to the console and issue twice ``Ctrl + C``
   to shutdown the *ipython-server*.


.. _begin-debug:

Debugging and investigating results
-----------------------------------

- Make sure that you have installed `graphviz`, and when running the simulation,
  append also the ``--plot-workflow`` option.

- Use the ``modelgraph`` sub-command to plot the offending model (or just
  out of curiosity).  For instance:

  .. code-block:: console

        $ co2mpas modelgraph gear_box_calibration


- Inspect the functions mentioned in the workflow and models and search them
  in `CO2MPAS documentation <http://files.co2mpas.io/>`_ ensuring you are
  visiting the documents for the actual version you are using.

