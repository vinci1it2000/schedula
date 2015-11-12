##################################################################
CO2MPAS: Vehicle simulator predicting NEDC CO2 emissions from WLTP
##################################################################

:Release:       1.0.5.b0
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
    **About console-commands:**

    - Console-commands beginning with ``$`` symbol are for the ``bash`` shell
      (UNIX).
      You can install it on *Windows* with **cygwin**: https://www.cygwin.com/
      along with these useful utilities::

        * git, git-completion
        * make, zip, unzip, bzip2, 7z, dos2unix
        * openssh, curl, wget

    - Console-commands beginning with ``>`` symbol are for *Windows* ``cmd.exe``
      command-prompt.
      You can augment it with bash-like capabilities using **Clink**:
      http://mridgers.github.io/clink/

    - You can adapt commands between the two shells with minor modifications
      (i.e. ``ls <--> dir``, ``rm -r <--> deltree``).

    - You may download and install the *all-in-one* archive which contains
      both shells configured in a console supporting decent copy-paste and
      resizing capabilities (see :ref:`all-in-one`).


IF you have familiarity with v1 release AND IF you already have a full-blown
*python-3 environment* (i.e. *Linux* or the *all-in-one* archive) you can
immediately start working with the following *bash* commands; otherwise
follow the detailed instructions under sections :ref:`install` and
:ref:`usage`.

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



.. _install:

Install
=======
The installation procedure has 2-stages:

1. Install (or Upgrade) Python (2 choices under *Windows*).
2. Install CO2MPAS:
    a. Install (or Upgrade) executable.
    b. (optional) Install documents.
    c. (optional) Install sources.

On *Windows* you may alternatively install the *all-In-One* archive
instead of performing the above 2 steps separately.


.. _all-in-one:

*All-In-One* Installation under Windows
---------------------------------------
- Download **all-in-one archive** from
  http://files.co2mpas.io/.
  Ensure that you download the correct 32/64 architecture for your PC
  (the 64bit archive CANNOT run on 32bit PCs, but the opposite is possible).

- Use the original `"7z" extraxtor <http://portableapps.com/apps/utilities/7-zip_portable>`_,
  since "plain-zip" produces out-of-memory errors when expanding long
  directories.
  Prefer to **extract it in a folder without any spaces in its path.**

- If you have already downloaded a previous version of the *all-in-one*
  archive, you may prefer to just upgrade CO2MPAS contained within.
  Follow the instructions in the "Upgrade" section, below.

- After installation, check that the version of CO2MPAS contained in the
  archive corresponds to the latest/the one described in these instructions.
  If not, follow the instructions in the "Upgrade" section, below.

- Visit the guidelines for its usage: :doc:`allinone`
  (also contained within the archive).


Python Installation
-------------------
If you already have a suitable python-3 installation with all scientific
packages updated to their latest versions, you may skip this 1st stage.

.. Note::
    **Installing Python under Windows:**

    The program requires CPython-3, and depends on *numpy*, *scipy*, *pandas*,
    *sklearn* and *matplotlib* packages, which depend on C-native backends
    and need a C-compiler to install from sources.

    In *Windows* it is strongly suggested **NOT to install the standard CPython
    distribution that comes up first(!) when you google for "python windows"**,
    unless you are an experienced python-developer, and you know how to
    hunt down pre-compiled dependencies from the *PyPi* repository and/or
    from the `Unofficial Windows Binaries for Python Extension Packages
    <http://www.lfd.uci.edu/~gohlke/pythonlibs/>`_.

    Therefore we suggest that you download one of the following two
    *scientific-python* distributions:

      #. `WinPython <https://winpython.github.io/>`_ **python-3** (prefer 64 bit)
      #. `Anaconda <http://continuum.io/downloads>`_ **python-3** (prefer 64 bit)



Install WinPython
~~~~~~~~~~~~~~~~~
The *WinPython* distribution is just a collection of the standard pre-compiled
binaries for *Windows* containing all the scientific packages, and much more.
It is not update-able, and has a quasi-regular release-cycle of 3 months.


1. Install the latest python-3 (preferably 64 bit) from https://winpython.github.io/.
   Prefer an **installation-folder without any spaces leading to it**.

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


4. Use this console and follow :ref:`co2mpas-install` instructions, below.



Install Anaconda
~~~~~~~~~~~~~~~~
The *Anaconda* distribution is a non-standard Python environment that
for *Windows* containing all the scientific packages we need, and much more.
It is not update-able, and has a semi-regular release-cycle of 3 months.

1. Install Anaconda python 3.4 (preferably 64 bit) from http://continuum.io/downloads.
   Prefer an **installation-folder without any spaces leading to it**.

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

4. Use this console and follow :ref:`co2mpas-install` instructions, below.


.. _co2mpas-install:

CO2MPAS installation
--------------------
1. Install CO2MPAS executable internally into your python-environment with
   the following console-command:

   .. code-block:: console

        > pip install co2mpas --extra-index http://pypi.co2mpas.io/simple/ --trusted-host pypi.co2mpas.io
        Collecting co2mpas
        Downloading http://pypi.co2mpas.io/packages/co2mpas-...
        ...
        Installing collected packages: co2mpas
        Successfully installed co2mpas-1.0.5.b0

   .. Note::
        **Installing Behind Firewall:**

        This previous step requires http-connectivity to Python's "standard"
        repository (https://pypi.python.org/) and to co2mpas-site
        (http://files.co2mpas.io).
        In case you are behind a **corporate proxy**, you may either:

        a) Append the following option to all ``pip`` commands, appropriately
           adapted: ``--proxy http://user:password@yourProxyUrl:yourProxyPort``.

           To avert any security deliberations for this http-proxy "tunnel",
           JRC *cryptographically signs* all *final releases*, so that you or
           your IT staff may `validate their authenticity
           <https://www.davidfischer.name/2012/05/signing-and-verifying-python-packages-with-pgp/>`_
           and detect *man-in-the-middle* attacks, however impossible.

        b) Download all *wheel* packages from `co2mpas-site
           <http://files.co2mpas.io>`_ for the specific version you are
           interested in , and install them one by one (see next section).

           .. code-block:: console

               REM Download MANUALLY all `*.whl` files contained in release folder
               REM from co2mpas-site in some folder.
               > cd <folder-where-wheels_downloaded>
               > pip install *.whl


   .. Warning::
       If you cannot install CO2MPAS, re-run the ``pip`` command adding
       2 *verbose* flags ``-vv``, copy-paste the console-output, and send it
       to JRC.


2. Check that when you run ``co2mpas``, the version executed is indeed the one
   installed above (check both version-identifiers and paths):

   .. code-block:: console

       > python -v --version
       co2mpas_version: 1.0.5.b0
       co2mpas_rel_date: 2015-12-09 10:48:11
       co2mpas_path: d:\co2mpas_ALLINONE-XXbit-v1.0.4.post1\Apps\WinPython\python-3.4.3\lib\site-packages\co2mpas
       python_path: D:\co2mpas_ALLINONE-XXbit-v1.0.4.post1\WinPython\python-3.4.3
       python_version: 3.4.3 (v3.4.3:9b73f1c3e601, Feb 24 2015, 22:44:40) [MSC v.1600 XXX]
       PATH: D:\co2mpas_ALLINONE-XXbit-v1.0.5.b0\WinPython...


   .. Note::
       The above procedure installs the *latest* CO2MPAS, which
       **might be more up-to-date than the version described here!**

       In that case you can either:

       a) Visit the documents for the newer version actually installed.
       b) "Pin" the exact version you wish to install with a ``pip`` command
          (see section below).


Install extras
~~~~~~~~~~~~~~
Internally CO2MPAS uses an algorithmic scheduler to execute model functions.
In order to visualize the *design-time models* and *run-time workflows*
you need to install the **Graphviz** visualization library  from:
http://www.graphviz.org/.

If you skip this step, the ``graphplot`` sub-command and the ``--plot-workflow``
option would both fail to run (see :ref:`debug`).



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


Installing different version of CO2MPAS
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
You may get multiple versions of CO2MPAS, from various places, but all
require the use of ``pip`` command to install:

- **Latest STABLE:**
  use the default ``pip`` described command above.

- **Latest PRE-RELEASE:**
  append the ``--pre`` option in the ``pip`` command.

- **Specific version:**
  modify the ``pip`` command like that, with optionally appending ``--pre``:

  .. code-block:: console

      pip install co2mpas==1.0.1 ... # Other options, like above.

- **Specific branch** from the sources (github):
  use a command like that (e.g. ``dev``):

      .. code-block:: console

      pip install git+https://github.com/JRCSTU/co2mpas.git@dev

- **Specific commit** from the sources (github):
  use a command like that (e.g. ``dev``):

  .. code-block:: console

      pip install git+https://github.com/JRCSTU/co2mpas.git@2927346f4c513a

- All of the above, but with internet through **http-proxy**:
  append an appropriately adapted option: ``--proxy http://user:password@yourProxyUrl:yourProxyPort``.

- All of the above, **without internet connectivity**:  download locally
  all ``.whl`` files present in the desired version on `CO2MPAS site <http://files.co2mpas.io/>`_
  and install them with a command like that:

  .. code-block:: console

      pip install *.whl

..  Warning::
    If you have already a CO2MPAS version install, don't foget to uninstall it
    first.


Install multiple versions of CO2MPAS in parallel
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
In order to run and compare results from different CO2MPAS versions,
you may use `virtualenv <http://docs.python-guide.org/en/latest/dev/virtualenvs/>`_
command.

The `virtualenv` command creates isolated python-environments ("children-venvs")
where in each one you can install a different versions of CO2MPAS.

.. Note::
    The `virtualenv` command does NOT run under the "conda" python-environment.
    Use the `conda command <http://conda.pydata.org/docs/using/envs.html>`_
    in similar manner to create children-envs instead.


1. Ensure `virtualenv` command installed in your "parent" python-environment,
   i.e the "WinPython" you use:

   .. code-block:: console

       > pip install virtualenv

   .. Note::
      The `pip` command above has to run only once for each parent python-env.
      If `virtualenv` is already installed, `pip` will exit gracefully.



2. Ensure co2mpas uninstalled in your parent-env:

   .. code-block:: console

       > pip uninstall co2mpas

   .. Warning::
     It is important for the "parent" python-env NOT to have CO2MPAS installed!
     The reasone is that you must set "children venvs" to inherit all packages
     installed on their "parent" (i.e. `numpy` and `pandas`), and you cannot
     update any inherited package from within a child-env.


3. Move to the folder where you want your "venvs" to reside and create
   the "venv" with this command:

   .. code-block:: console

       > virtualenv --system-site-packages co2mpas_v1.0.1.venv.venv

   The ``--system-site-packages`` option instructs the child-venv to inherit
   all "parent" packages (numpy, pandas).

   Select a venv's  name to signify the version it will contains,
   e.g. ``co2mpas_v1.0.1.venv``.  The ``.venv`` at the end is not required,
   it is just for tagging the *venv* folders.

4. Workaround a `virtualenv bug <https://github.com/pypa/virtualenv/issues/93>`_
   with `TCL/TK` on *Windows*!

   This is technically the most "difficult" step, and it is required so that
   CO2MPAS can open GUI dialog-boxes, such as those for selecting
   the *input/output* dialogs.

   a. Open with an editor the ``co2mpas_v1.0.1.venv.venv\Scripts\activate.bat`` script,
   b. locate the `set PATH=...` line towards the bottom of the file, and
      append the following 2 lines::

        set "TCL_LIBRARY=d:\WinPython-XX4bit-3.4.3.2\python-3.4.3.amd64\tcl\tcl8.6"
        set "TK_LIBRARY=d:\WinPython-XXit-Y.Y.Y.Y\python-3.4.3.amd64\tcl\tk8.6"

   .. Tip::
       You have to **adapt the paths above** to match the `TCL` & `TK`
       folder in your parent python-env.

       If not, you will receive the following message while running CO2MPAS::

           This probably means that Tcl wasn't installed properly.


5. "Activate" the new "venv" by running the following command
   (notice the dot(``.``) at the begining of the command):

   .. code-block:: console

        > .\co2mpas_v1.0.1.venv.venv\Scripts\activate.bat

   You must now see that your prompt has been prefixed with the venv's name.


6. Install the co2mpas version you want inside the activated venv.
   See the :ref:`co2mpas-install` section, above.

   Don't forget to check that what you get when running co2mpas is what you
   installed.

7. To "deactivate" the active venv, type:

   .. code-block:: console

       > deactivate

   The prompt-prefix with the venv-name should now dissappear.  And if you
   try to invoke ``co2mpas``, it should fail.



.. Tip::
    - Repeat steps 2-->5 to create venvs for different versions of co2mpas.
    - Use steps (6: Activate) and (9: Deactivate) to switch between different
      venvs.



.. _usage:

Usage
=====
.. Note::
    The following commands are for the **bash console**, specifically tailored
    for the **all-in-one** archive.


First ensure that the latest version of CO2MPAS is properly installed, and that
its version match the version declared on this file.

The main entry for the simulator is the ``co2mpas`` console-command,
which **is not visible, but it is installed in your PATH.**
To get the syntax of the ``co2mpas`` console-command, open a console where
you have installed CO2MPAS (see :ref:`install` above) and type:

.. code-block:: console

    $ co2mpas --help
    Predict NEDC CO2 emissions from WLTP cycles.

    Usage:
        co2mpas [simulate] [-v] [--predict-wltp] [--report-stages] [--no-warn-gui]
                           [--plot-workflow] [--only-summary]
                           [-I <fpath>] [-O <fpath>]
        co2mpas demo       [-v] [-f] [<folder>]
        co2mpas template   [-v] [-f] [<excel-file-path> ...]
        co2mpas ipynb      [-v] [-f] [<folder>]
        co2mpas modelgraph [-v] --list
        co2mpas modelgraph [-v] [--depth=INTEGER] [<models> ...]
        co2mpas [-v] --version
        co2mpas --help

    -I <fpath>         Input folder or file, prompted with GUI if missing [default: ./input]
    -O <fpath>         Input folder or file, prompted with GUI if missing [default: ./output]
    -l, --list         List available models.
    --only-summary     Does not save vehicle outputs just the summary file.
    --predict-wltp     Whether to predict also WLTP values.
    --report-stages    Add report-sheets with stage-scores into summary file.
    --no-warn-gui      Does not pause batch-run to report inconsistencies.
    --plot-workflow    Open workflow-plot in browser, after run finished.
    --depth=INTEGER    Limit the number of sub-dispatchers plotted (no limit by default).
    -f, --force        Overwrite template/demo excel-file(s).
    -v, --verbose      Print more verbosely messages.

    * Items enclosed in `[]` are optional.


    Sub-commands:
        simulate    [default] Run simulation for all excel-files in input-folder (-I).
        demo        Generate demo input-files inside <folder>.
        template    Generate "empty" input-file at <excel-file-path>.
        ipynb       Generate IPython notebooks inside <folder>; view them with cmd:
                      ipython --notebook-dir=<folder>
        modelgraph  List all or plot available models.  If no model(s) specified, all assumed.

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

The default sub-command (``simulate``) accepts either a single **input-excel-file**
or a folder with multiple input-files for each vehicle, and generates a
**summary-excel-file** aggregating the major result-values from these vehicles,
and (optionally) multiple **output-excel-files** for each vehicle run.


Running Samples
---------------
The simulator contains input-files for demo-vehicles that are a nice
starting point to try out.

1. Choose a folder where you will store the *input* and *output* files:

   .. code-block:: console

        ## Skip this if ``tutorial`` folder already exists.
        $ mkdir tutorial
        $ cd tutorial

        ## Skip also this if folders exist.
        $ mkdir input output

  .. Note::
    The input & output folders do not have to reside in the same parent,
    neither to have these names.
    It is only for demonstration purposes that we decided to group them both
    under a hypothetical ``some-folder``.

3. Create the demo vehicles inside the *input-folder* with the ``demo``
   sub-command:


   .. code-block:: console

        $ co2mpas demo input
        Creating DEMO INPUT file 'input\co2mpas_demo_1_full_data.xlsx'...
        Creating DEMO INPUT file 'input\co2mpas_demo_2_wltp_high_only.xlsx'...
        Creating DEMO INPUT file 'input\co2mpas_demo_3_wltp_low_only.xlsx'...
        Creating DEMO INPUT file 'input\co2mpas_demo_4_baseline_no_battery_currents - Copy.xlsx'...
        Creating DEMO INPUT file 'input\co2mpas_demo_5_baseline_no_gears.xlsx'...
        You may run DEMOS with:
            co2mpas simulate -I input

4. Run the simulator:

   .. code-block:: console

       $ co2mpas -I input -O output
       Processing 'input' --> 'output'...
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

    ## Input and calibrated values for electrics.
    <timestamp>_precondition_WLTP_<inp-fname>.xls

    ## Input and calibrated values.
    <timestamp>_calibration_WLTP-H_<inp-fname>.xls

    ## Input and calibrated values.
    <timestamp>_calibration_WLTP-L_<inp-fname>.xls

    ## Input and predicted values.
    <timestamp>_prediction_NEDC_<inp-fname>.xls

    ## Major CO2 values from all vehicles in the batch-run.
    <timestamp>_summary.xls


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
        Creating TEMPLATE INPUT file 'input/vehicle_1.xlsx'...


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

4. Run the simulator.  Specify the single excel-file as input:

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
   See also :ref:`debug`, below.


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


.. _debug:

Debugging and investigating results
-----------------------------------

- Make sure that you have installed `graphviz`, and when running the simulation,
  append also the ``--plot-workflow`` option.

- Use the ``modelgraph`` sub-command to plot the offending model (or just
  out of curiosity).  For instance:

  .. code-block:: console

        $ co2mpas modelgraph gear_box_calibration

  .. image:: _static/GearModel.png
    :alt: Flow-diagram of the Gear-calibration model.
    :height: 240
    :width: 320

- Inspect the functions mentioned in the workflow and models and search them
  in `CO2MPAS documentation <http://files.co2mpas.io/>`_ ensuring you are
  visiting the documents for the actual version you are using.

