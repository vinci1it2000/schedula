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


.. _begin-usage:

Usage
=====

1. Once Python is installed appropriately,
   execute it from the command prompt and check the version::

	    > co2mpas --version
        1.0.0-dev.ank.1


2. Then run it without any options and select the input and output folders
   from the UI-browser::

        > co2mpas

   .. Tip:
       See the template file (excel input/Template.xlsm) for required input data.

3. To get the syntax of the command use::

    > co2mpas --help



Debugging and investigating results
-----------------------------------

- Make sure that you have installed `graphviz` and invoke the `co2mpas` cmd
  with the ``--plot-workflow`` option.


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


.. _begin-limitations:

Known Limitations
=================

- Running with the same input might produce slightly different result values
  (i.e. for the CO2 it is in the max range of 0.5 gr/km).
- The calculations are very sensitive to the thermal time-series.
  Mixing time series from different vehicles produce unreliable results.
- Heavily quantized velocity time-series heavily affect the accuracy of the
  results.
- Ill-formatted input data may NOT produce warnings. Check if all input
  data are also contained in the output data (calibration files).
