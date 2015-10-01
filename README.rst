##############################################################################
co2mpas: Vehicle simulator predicting NEDC CO2 emissions from WLTP time-series
##############################################################################
|python-ver| |proj-license|

:Release:       1.0.1b5
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
The program runs as a *console-mode command**.

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
      (i.e. replace ``mkdir --> md`` and ``cygstart --> start``)

    - In Windows you may download and install (unzip) the
      `Console 2 <http://sourceforge.net/projects/console/>`_
      application that supports a more decent way to copy-paste.

IF you have familiarity with v1 release AND IF you already have a full-blown
*python-3 environment* (i.e. *Linux*) you can immediately start working with
the following console-commands; otherwise follow the detailed instructions
under sections :ref:`begin-install` and :ref:`begin-usage`.

.. code-block:: bash

    ## Install co2mpas
    $ pip install co2mpas --extra-index http://pypi.wltp.io/simple/ --trusted-host pypi.wltp.io  --pre

    ## Where to store input and output files.
    ## In *Windows* use `md` command instead.
    $ mkdir input output

    ## Create a template excel-file for inputs.
    $ co2mpas template input/vehicle1

    ###################################################
    ## Edit generated `./input/vehicle1.xlsx` file.  ##
    ###################################################

    ## Run simulator.
    $ co2mpas -I input -O output

    ###################################################
    ## Inspect generated results inside `./output/`. ##
    ###################################################


.. |proj-license| image:: https://img.shields.io/badge/license-BSD%2Bzlib%2Flibpng-blue.svg
    :target: https://raw.githubusercontent.com/pypiserver/pypiserver/master/LICENSE.txt
    :alt: Project License
.. |python-ver| image:: https://img.shields.io/pypi/pyversions/pypiserver.svg
    :target: https://pypi.python.org/pypi/pypiserver/
    :alt: Supported Python versions
.. _end-opening:
.. contents:: Table of Contents
  :backlinks: top



.. _begin-install:

Install
=======
The installation procedure is 2-stage procedure:

1. Install (or Upgrade) Python (2 choices under *Windows*)
2. Install CO2MPAS:
    a. Install (or Upgrade) executable.
    b. (optional) Install documents.
    c. (optional) Install sources.

If you have already have a suitable python installation, skip step 1.

.. Note::
    The program requires CPython-3, and depends on *numpy*, *scipy*, *pandas*,
    *sklearn* and *matplotlib* libraries that require a native C-compiler.

    For that reason, in *Windows* it is strongly suggested **NOT to install
    the standard CPython distribution** that comes up first if you google
    for "python"(!), unless you are an experienced python-developer, and
    you know how to hunt dependencies from *PyPi* repository and from the
    `Unofficial Windows Binaries for Python Extension Packages
    <http://www.lfd.uci.edu/~gohlke/pythonlibs/>`_.

    Therefore we suggest that you download and unzip the **all-in-one archive**
    (distributed separately).

    Otherwise, download one of the 2 alternatives scientific-python
    distributions:

      #. `WinPython <https://winpython.github.io/>`_ **python-3** (prefer 64 bit)
      #. `Anaconda <http://continuum.io/downloads>`_ **python-3** (prefer 64 bit)



WinPython install
-----------------

1. Install the latest python-3 (preferably 64 bit) from https://winpython.github.io/.
   Prefer an installation-folder without any spaces leading to it.

2. Open the WinPython's command-prompt console, by locating the folder where
   you just installed it and run (double-click)::

        <winpython-folder>\"WinPython Command Prompt.exe"


3. In the console-window check that you have the correct version of
   WinPython installed, by typing::

        > python --version
        Python 3.4.3

        > where python      ## Check your python's location is where you installed it.
        ....


4. Use this console and follow CO2MPAS-executable installation instructions
   (see :ref:`CO2MPAS install`, below)



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
   (see :ref:`CO2MPAS install`, below)


CO2MPAS install
---------------
1. Install CO2MPAS executable internally into your python-environment with
   the following console-command::

        > pip install co2mpas --extra-index http://pypi.wltp.io/simple/ --trusted-host pypi.wltp.io --pre
        Collecting toolz
        Installing collected packages: co2mpas
        Successfully installed co2mpas-1.0.1b5

... Tip::
    In case of errors, re-run the command adding the *verbose* flags ``-vv``,
    and copy-paste the result to JRC


2. Check that when you run ``co2mpas``, you run indeed the version just
   installed::

        > co2mpas --version
        1.0.1b5


3. (optionally) Unzip the documents archive (distributed separately)
   to have them ready when inspecting the workflow for each simulation-run
   (see :ref:`begin-usage`, below).

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

    > pip install co2mpas --extra-index http://pypi.wltp.io/simple/ --trusted-host pypi.wltp.io --pre -U --no-deps


Uninstall CO2MPAS
-----------------
To uninstall CO2MPAS type the following command, and confirm it with ``y``::

    > pip uninstall co2mpas
    Uninstalling co2mpas-<installed-version>
    ...
    Proceed (y/n)?


Run the command *again*, to make sure that no dangling installations are left
over; disregard any errors.




.. _begin-usage:

Usage
=====
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
        co2mpas [options] [-I <folder>  -O <folder>]
        co2mpas template [-f | --force] <excel-file> ...
        co2mpas --help
        co2mpas --version

    -I <folder> --inp <folder>       Input folder, prompted with GUI if missing.
                                     [default: ./input]
    -O <folder> --out <folder>       Input folder, prompted with GUI if missing.
                                     [default: ./output]
    --more-output                    Output also per-vehicle output-files.
    --no-warn-gui                    Does not pause batch-run to report inconsistencies.
    --plot-workflow                  Show workflow in browser, after run finished.
    -f --force                       Overwrite template excel-file if it exists.


Running samples
---------------
The simulator contains sample input files for 2 vehicles.

1. Choose a folder where you will store the *sample-input* and *sample-output*
   data-folders:

   .. code-block:: bash

      $ cd <some-folder>                 ## You should have created that hypothetical <some-folder>.
      $ mkdir sample_inp sample_out      ## Replace `mkdir` with `md` in *Windows* (`cmd.exe`)

  .. Note::
    The input & output folders do not have to reside in the same parent.
    It is only for demonstration purposes that we decided to group them both
    under the hypothetical ``<some-folder>``.

2. Create the sample vehicles inside the ``./sample_inp`` folder:

   .. code-block:: bash

        $ co2mpas samples sample_inp
        Creating co2mpas SAMPLE './sample_inp/sample_vehicle_1.xlsx'...
        Creating co2mpas SAMPLE './sample_inp/sample_vehicle_2.xlsx'...


3. Run the simulator:

   .. code-block:: bash

      $ co2mpas -I sample_inp -O sample_out
      Processing './sample_inp' --> './sample_out'...
      Processing: sample_vehicle_1
      ...
      Processing: sample_vehicle_2
      ...
      Done! [0.851 min]


4. Inspect the results:

   .. code-block:: bash

      $ cygstart output/*summary.xlsx       ## View the aggregate for all vehicles.
      $ cygstart output                     ## View all files generated (see below).


Entering new vehicles
---------------------
1. Choose other input/output folders for your vehicles:

   .. code-block:: bash

      $ cd <some-folder>
      $ mkdir input output                  ## Replace `mkdir` with `md` in *Windows* (`cmd.exe`)

1. Create an empty vehicle template-file (eg. ``vehicle1.xlsx``) inside
   the *input-folder*:


   .. code-block:: bash

        $ co2mpas template input/vehicle1
        Creating co2mpas INPUT template-file './input/vehicle1.xlsx'...


4. Open the template excel-file, fill-in your vehicle data, and save it:

   .. code-block:: bash

      $ cygstart input/vehicle1.xlsx        ## Opens the excel-file. Use `start` in *cmd.exe*.

   .. Tip::
       The generated file contains help descriptions to help you populate it
       with vehicle data.

       Repeat these last 2 steps if you want to add more vehicles in
       the *batch-run*.

9. Repeat the above procedure from step 4 to modify the vehicle and run again
   the model.  Start from step 1 to construct a new batch.


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


Debugging and investigating results
-----------------------------------

- Make sure that you have installed `graphviz` and invoke the `co2mpas` cmd
  with the ``--plot-workflow`` option.
- Inspect the functions mentioned in the workflow and search them in the
  unzipped **source-archive** (distributed separately).

