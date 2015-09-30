##############################################################################
co2mpas: Vehicle simulator predicting NEDC CO2 emissions from WLTP time-series
##############################################################################

:Release:   1.0.1b1
:Sources:   https://github.com/JRCSTU/co2mpas
:Keywords:  CO2, wltp, engineering, scientific, python, excel, library,
:Dev-team:  .. include:: ../AUTHORS.rst
:Copyright: 2015 European Commission (`JRC-IET
            <https://ec.europa.eu/jrc/en/institutes/iet>`_)
:License:   `EUPL 1.1+ <https://joinup.ec.europa.eu/software/page/eupl>`_


CO2MPAS is backward-looking longitudinal-dynamics CO2 & fuel-consumption
simulator for Light-Duty Vehicles specially build to back-translate consumption
figures from WLTP cycles into NEDC ones.

It is an open-source python-3 project currently tested with python 3.4,
in Anaconda under MacOS & Anaconda/WinPython under Windows 7.


History
-------
The *European Commission* is supporting the introduction of the WLTP cycle
for Light-duty vehicles (cars and vans) developed at the United Nations (UNECE)
level, in the shortest possible time-frame. Its introduction requires
the adaptation of CO2 certification and CO2 monitoring procedures set
by European Regulations. European Commission's *Joint Research Centre* has been
assigned the development of this vehicle simulator to facilitate this step.



Quickstart: Installation and Usage
----------------------------------
If you already have a full-blown *python-3 environment* (i.e. *Linux*) you can
immediately start working with these console-commands:

.. code-block:: bash

    ## Install co2mpas
    $ pip install co2mpas --extra-index http://pypi.wltp.io/simple/ --trusted-host pypi.wltp.io  --pre

    ## Where to store input and output files.
    ## In *Windows* use `md` command instead.
    $ mkdir input output

    ## Create a template excel-file for inputs.
    $ co2mpas --create-template input/vehicle1

    ######################################################
    ## edit the generated `./input/vehicle1.xlsx` file. ##
    ######################################################

    ## Run simulator.
    $ co2mpas -I input -O output


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


Anaconda install
----------------
1. Install Anaconda python 3.4 (preferably 64 bit) from http://continuum.io/downloads.
   Prefer an installation-folder without any spaces leading to it.

   .. Note::
       When asked by the installation wizard, ensure that *Anaconda* gets to be
       registered as the default python-environment for the user's account.

2. Open a windows command-prompt console::

       start button --> `cmd.exe`

3. In the console-window check that you have the correct version of
   Anaconda-python installed, by typing::

        > python --version
        Python 3.4.3 :: Anaconda 2.3.0 (64-bit)


4. Install **co2mpas** by typing::

       > pip install co2mpas --extra-index http://pypi.wltp.io/simple/ --trusted-host pypi.wltp.io --pre


5. (optionally) Unzip the sources (distributed separately) and install
   the develop-time dependencies::

       > cd <sources-folder>
       > pip install -r requirements/dev.pip


Upgrade Anaconda
~~~~~~~~~~~~~~~~
If you already have installed *Anaconda*, you may simply upgrade it.

[TBD: Ask JRC]



WinPython install
-----------------

1. Install the latest python-3 (preferably 64 bit) from https://winpython.github.io/ preferably
   Prefer an installation-folder without any spaces leading to it.

2. Open the WinPython's command-prompt console, by locating the folder where
   you installed it and execute::

        <winpython-folder>\"WinPython Command Prompt.exe"


3. In the console-window check that you have the correct version of
   Anaconda-python installed, by typing::

        > python --version
        Python 3.4.3


4. Install **co2mpas** by typing::

       > pip install co2mpas --extra-index http://pypi.wltp.io/simple/ --trusted-host pypi.wltp.io --pre


4. (optionally) Unzip the sources (distributed separately) and install
   the develop-time dependencies::

       > cd <sources-folder>
       > pip install -r requirements/dev.pip


*All-in-one* distributed archive
--------------------------------
[TBD]



Check installation
------------------
Check everything was OK by comparing the versions with the strings below::

    > co2mpas --version
    1.0.1b1


.. _begin-usage:

Usage
=====
The main entry for the simulator is the ``co2mpas`` console-command.
This command accepts multiple *input-files*, one for each vehicle,
and generates multiple *output-files* per each one vehicle,
and a *summary* file which aggregates the major result-values from all vehicles.

To get the syntax of the command, open a console where you have
installed **co2mpas** (see `Install`_ above) and type the
following command:

.. code-block:: bash

    $ co2mpas --help

.. Tip::
    The commands beginning with ``$`` symbol are for the *bash-console* (UNIX)
    included in the ``console.lnk`` file in top folder of the *all-in-one*
    distribution-archive (see above `Install`).

    You can run them with minor modifications in any similar environemnt,
    such as the *Windows* ``cmd.exe`` console (i.e. replace ``mkdir --> md`` and
    ``cygstart --> start``)



1. Choose a folder where you will run *co2mpas* and create the *input* and
   *output* data-folders

   .. code-block:: bash

      $ cd <some-folder>
      $ mkdir input output     ## Replace `mkdir` with `md` in *Windows* (`cmd.exe`)

  .. Note::
    The input & output folders do not have to reside in the same parent.
    It is only for demonstration purposes that we decided to group them both
    under a hypothetical ``some-folder``.

3. Create inside the *input-folder* a vehicle-data template file
   (eg. ``vehicle1.xlsx``):

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
  unzipped the **source-archive**.

