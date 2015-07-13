#############################################################
CO2MPAS: Predict CO2 emissions of NEDC using WLTP time-series
#############################################################
:Version: 1.0.0
:date: 13-July-2015
:author: Vincenzo Arcidiacono <vincenzo.arcidiacono@ext.jrc.ec.europa.eu>
:contributors:  Stefanos Tsiamakis <stefanos.tsiakmakis@jrc.ec.europa.eu>, 
				Georgios Fontaras <georgios.fontaras@jrc.ec.europa.eu>
				Kostis Anagnostopoulos <konstantinos.anagnostopoulos@ext.jrc.ec.europa.eu>
:Keywords:  CO2, wltp, engineering, scientific, python, excel, library,
:Copyright: 2015 European Commission (`JRC-IET
            <https://ec.europa.eu/jrc/en/institutes/iet>`_)
:License:   `EUPL 1.1+ <https://joinup.ec.europa.eu/software/page/eupl>`_


Install
=======

The program requires CPython-3, and depends on, among others,  
numpy/scipy, pandas and matplotlib libraries that require native backends.

Code is currently tested only with python 3.4 in
Anaconda/Winpython/MacOS/Windows 7.

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
   you can execute the python-code from inside the extracted folder.
   Just run from the command prompt::

	    python compas.py

   or directly double click the python-file.


2. Then select the input and output folders form the UI-browser.

   .. Tip: 
       See the template file (excel input/Template.xlsm) for required input data.

   
