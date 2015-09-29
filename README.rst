##############################################################################
co2mpas: Vehicle simulator predicting NEDC CO2 emissions from WLTP time-series
##############################################################################

:Release:   1.0.0-dev.ank.1
:Sources:   https://github.com/JRCSTU/co2mpas
:Keywords:  CO2, wltp, engineering, scientific, python, excel, library,
:Dev-team:  .. include:: ../AUTHORS.rst
:Copyright: 2015 European Commission (`JRC-IET
            <https://ec.europa.eu/jrc/en/institutes/iet>`_)
:License:   `EUPL 1.1+ <https://joinup.ec.europa.eu/software/page/eupl>`_


The European Commission is supporting the introduction of the WLTP cycle
for Light-duty vehicles (cars and vans) developed at the United Nations (UNECE)
level, in the shortest possible time-frame. Its introduction require
the adaptation of CO2 targets for manufacturers set by European Regulations,
and JRC has been assigned the development of this vehicle simulator to
facilitate this step.

This open-source python-project is currently tested only with python 3.4,
in Anaconda/Winpython/MacOS/Windows 7.

Quickstart: Installation and Usage
----------------------------------





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

There are 3 installation option:

# Install `Anaconda <http://continuum.io/downloads>`_ python and *pip-install* it.
# Install `WinPython <https://winpython.github.io/>`_ python and *pip-install* it.
# Download the *all_in_one* distribution archive (~400MB) and unzip it.

Anaconda install
----------------
1. Install python 3.4 from one of:

	- `Anaconda <http://continuum.io/downloads>`_

	- `WinPython <https://winpython.github.io/>`_
	  (and register the installation from its Control-panel)

2. Unzip the archive to some folder.

3. Open windows command prompt::

       start --> `cmd.exe`

4. In the cmd window go in in the folder where you have unzipped the archive::

       cd \path\to\directory\compas

5. **Anaconda**-only: Run the following command to install dependencies
   with C-native code::

        conda update conda
        conda install --file requirements/exe.conda

6. Run the following command to install run-time dependencies::

       pip install -r requirements/exe.pip

7. (optionally) Install develop-time dependencies::

       pip install -r requirements/dev.pip

8. Once Python is installed appropriately,
   execute it from the command prompt and check the installed version::

        co2mpas --version
        1.0.0-dev.ank.1

WinPython install
-----------------

1. Install python 3.4 from one of:

    - `Anaconda <http://continuum.io/downloads>`_

    - `WinPython <https://winpython.github.io/>`_
      (and register the installation from its Control-panel)

2. Unzip the archive to some folder.

3. Open windows command prompt::

       start --> `cmd.exe`

4. In the cmd window go in in the folder where you have unzipped the archive::

       cd \path\to\directory\compas

5. **Anaconda**-only: Run the following command to install dependencies
   with C-native code::

        conda update conda
        conda install --file requirements/exe.conda

6. Run the following command to install run-time dependencies::

       pip install -r requirements/exe.pip

7. (optionally) Install develop-time dependencies::

       pip install -r requirements/dev.pip

8. Once Python is installed appropriately,
   execute it from the command prompt and check the installed version::

        co2mpas --version
        1.0.0-dev.ank.1

.. _begin-usage:

Usage
=====
The main entry for the simulator is the ``co2mpas`` console-command.
This command accepts multiple *input-files*, one for each vehicle,
and generates multiple *output-files* per each one vehicle,
and a *summary* file which aggregates the major result-values from all vehicles.

To get the syntax of the command, open a console where you have
installed **co2mpas** (see :ref:`Install` above) and type the following
command:

.. code-block:: bash

    $ co2mpas --help

.. Tip::
    The commands beginning with ``$`` symbol imply a *bash-console* (UNIX).
    You can run it from any similar environemnt, such as the *Windows*
    ``cmd.exe`` console, or the *console.lnk* included in the top folder
    of the *all-in-one* distribution-archive.



1. Choose a folder where you will run *co2mpas* and create the *input* and
   *output* data-folders

   .. code-block:: bash

      $ cd <some-folder>
      $ mkdir input output

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

      $ cygstart input/vehicle1.xlsx        ## Opens the excel-file.

   .. Tip::
       See the template file (excel input/Template.xlsm) for required input data.

   You can repeat the last 2 steps and add more vehicles if you need them
   to run at once.


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
- Unzip the **docs-archives** and inspect the functions mentioned in the
  workflow


.. _begin-limitations:

Known Limitations
=================

- Running with the same input might produce slightly different result values
  (i.e. for the CO2 it is in the max range of 0.5 gr/km).
- The calculations are very sensitive to the thermal time-series.
  Mixing time series from different vehicles may produce unreliable results.
- Heavily quantized velocity time-series affect greatly the accuracy of the
  results.
- Ill-formatted input data may NOT produce warnings. Check if all input
  data are also contained in the output data (calibration files).
