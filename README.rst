##############################################################################
co2mpas: Vehicle simulator predicting NEDC CO2 emissions from WLTP time-series
##############################################################################

:Release:       1.0.1b2
:Sources:       https://github.com/JRCSTU/co2mpas
:Keywords:      CO2, wltp, engineering, scientific, python, excel, library,
:Developers:    .. include:: ../AUTHORS.rst
:Copyright:     2015 European Commission (`JRC-IET
                <https://ec.europa.eu/jrc/en/institutes/iet>`_)
:License:       `EUPL 1.1+ <https://joinup.ec.europa.eu/software/page/eupl>`_


CO2MPAS is backward-looking longitudinal-dynamics CO2 & fuel-consumption
simulator for Light-Duty Vehicles (cars and vans) specially crafted
to back-translate consumption figures from WLTP cycles into NEDC ones.

It is an open-source python-3 project currently developed with python 3.4,
in Anaconda/WinPython under Windows 7, in Anaconda under MacOS, and in Linux's
standard python environment.


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
If you already have a full-blown *python-3 environment* (i.e. *Linux*) you can
immediately start working with the following console-commands:

.. Tip::
    - Commands beginning with ``$`` symbol are for the *bash-console* (UNIX)
      i.e. the one included in the ``console.lnk`` file in top folder of
      the *all-in-one* distribution-archive (see `Install` below).

    - Windows's ``cmd.exe`` console commands begin with ``>`` symbol.
      You can adapt most UNIX commands with minor modifications
      (i.e. replace ``mkdir --> md`` and ``cygstart --> start``)


.. code-block:: bash

    ## Install co2mpas
    $ pip install co2mpas --extra-index http://pypi.wltp.io/simple/ --trusted-host pypi.wltp.io  --pre

    ## Where to store input and output files.
    ## In *Windows* use `md` command instead.
    $ mkdir input output

    ## Create a template excel-file for inputs.
    $ co2mpas --create-template input/vehicle1

    ###################################################
    ## Edit generated `./input/vehicle1.xlsx` file.  ##
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
The program requires CPython-3, and depends on *numpy*, *scipy*, *pandas*,
*sklearn* and *matplotlib* libraries that require native C-backends.

.. note::
   In *Windows* it is strongly suggested **NOT to install the standard CPython
   distribution**, unless you are an experienced python-developer, you know how
   to hunt dependencies from *PyPi* repository and the `Unofficial Windows
   Binaries for Python Extension Packages
   <http://www.lfd.uci.edu/~gohlke/pythonlibs/>`_.

    There are 3 installation option for *Windows*:

    #. Install `Anaconda <http://continuum.io/downloads>`_ **python-3** (prefer 64 bit),
       ``pip install co2mpas``, and download sources (distributed separately) and
       unzip them to get the documents.
    #. Install the latest `WinPython <https://winpython.github.io/>`_ **python-3** (prefer 64 bit),
       ``pip install co2mpas``, and download sources (distributed separately) and
       unzip them to get the documents.
    #. Unzip the *all_in_one* distribution archive (~400MB) (distributed separately).

Read further for detailed instructions for each method.


Anaconda install
----------------
1. Install Anaconda python 3.4 (preferably 64 bit) from http://continuum.io/downloads.
   Prefer an installation-folder without any spaces leading to it.

   .. Note::
       When asked by the installation wizard, ensure that *Anaconda* gets to be
       registered as the default python-environment for the user's account.

2. Open a *Windows* command-prompt console::

       start button --> `cmd.exe`

3. In the console-window check that you have the correct version of
   Anaconda-python installed, by typing::

        > python --version
        Python 3.4.3 :: Anaconda 2.3.0 (64-bit)


4. Install CO2MPAS by typing::

       > pip install co2mpas --extra-index http://pypi.wltp.io/simple/ --trusted-host pypi.wltp.io --pre


5. (optionally) Unzip the sources (distributed separately) and install
   the develop-time dependencies::

       > cd <sources-folder>
       > pip install -r requirements/dev.pip


Upgrade Anaconda-python
~~~~~~~~~~~~~~~~~~~~~~~
If you already have installed *Anaconda*, you may upgrade it before install.

[TBD: Ask JRC]


WinPython install
-----------------

1. Install the latest python-3 (preferably 64 bit) from https://winpython.github.io/.
   Prefer an installation-folder without any spaces leading to it.

2. Open the WinPython's command-prompt console, by locating the folder where
   you installed it and run (double-click)::

        <winpython-folder>\"WinPython Command Prompt.exe"


3. In the console-window check that you have the correct version of
   Anaconda-python installed, by typing:

        > python --version
        Python 3.4.3


4. Install CO2MPAS by typing::

       > pip install co2mpas --extra-index http://pypi.wltp.io/simple/ --trusted-host pypi.wltp.io --pre


5. (optionally) Unzip the sources (distributed separately) and install
   the develop-time dependencies::

       > cd <sources-folder>
       > pip install -r requirements/dev.pip


*All-in-one* distributed archive
--------------------------------
Just download and unzip the archive, and from the unzipped-folder's file run
(double-click) on ``console.lnk``.

[TBD]



Check installation
------------------
Compare the co2mpas-version reported with the strings below::

    > co2mpas --version
    1.0.1b2

Upgrade CO2MPAS
---------------
Regardless of the method of installation, to update CO2MPAS just append
the ``-U --no-deps`` options in the ``pip`` command::


    > pip install co2mpas --extra-index http://pypi.wltp.io/simple/ --trusted-host pypi.wltp.io --pre -U --no-deps


Uninstall CO2MPAS
-----------------
Regardless of the method of installation, to uninstall CO2MPAS just type
(preferably twice to be sure no dangling instances are left over)::

    > pip uninstall co2mpas


.. _begin-usage:

Usage
=====
The main entry for the simulator is the ``co2mpas`` console-command.
This command accepts multiple **input-excel-files**, one for each vehicle,
and generates a **summary-excel-file** aggregating the major result-values
from these vehicles, and (optionally) multiple **output-excel-files** for each
vehicle run.

To get the syntax of the ``co2mpas`` console-command, open a console where
you have installed CO2MPAS (see Install_ above) and type:

.. code-block:: bash

    $ co2mpas --help


1. Choose a folder where you will run CO2MPAS and create the *input* and
   *output* data-folders

   .. code-block:: bash

      $ cd <some-folder>
      $ mkdir input output     ## Replace `mkdir` with `md` in *Windows* (`cmd.exe`)

  .. Note::
    The input & output folders do not have to reside in the same parent.
    It is only for demonstration purposes that we decided to group them both
    under a hypothetical ``some-folder``.

3. Create a vehicle template-file (eg. ``vehicle1.xlsx``) inside
   the *input-folder*:


   .. code-block:: bash

        $ co2mpas --create-template input/vehicle1
        Creating co2mpas INPUT template-file './input/vehicle1.xlsx'...


4. Open the template excel-file, fill-in your vehicle data, and save it:

   .. code-block:: bash

      $ cygstart input/vehicle1.xlsx        ## Opens the excel-file. Use `start` in *cmd.exe*.

   .. Tip::
       The generated file contains help descriptions to help you populate it
       with vehicle data.

       Repeat these last 2 steps if you want to add more vehicles in
       the *batch-run*.


5. Run the simulator:

   .. code-block:: bash

      $ co2mpas -I input -o output
      Processing './input' --> './output'...
      Processing: vehicle1
      ...
      Done! [0.851 min]


6. Inspect the results:

   .. code-block:: bash

      $ cygstart output/*summary.xlsx       ## View the aggregate for all vehicles.
      $ cygstart output                     ## View all files generated (see below).

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

