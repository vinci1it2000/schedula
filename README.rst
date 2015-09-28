###################################################################################
co2mpas: Vehicle simulator predicting CO2 emissions for NEDC using WLTP time-series
###################################################################################

:Release:   1.0.0-dev.ank.1
:Dev-team:  .. include:: ../AUTHORS.rst
:Keywords:  CO2, wltp, engineering, scientific, python, excel, library,
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



Install
=======
The program requires CPython-3, and depends on *numpy*, *scipy* and *pandas*
libraries that require native C-backends.

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

5. Run the following command to install dependent libraries::

       pip install -r requirements.txt


Usage
=====

1. Once Python is installed appropriately,
   you can execute it from the command prompt::

	    > python co2mpas --version
        1.0.0-dev.ank.1


2. Then select the input and output folders form the UI-browser.

   .. Tip:
       See the template file (excel input/Template.xlsm) for required input data.


Known Limitations
=================
- asdf
