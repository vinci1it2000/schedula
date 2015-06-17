CO2MPAS
#######

:author: Vincenzo Arcidiacono 
:version: 0.5.1
:date: 17-June-2015
:reviewed by:

For info contact <vincenzo.arcidiacono@ext.jrc.ec.europa.eu> or <georgios.fontaras@jrc.ec.europa.eu>


Summary
#######

Install CO2MPAS
===============
The program requires CPython-3, and numpy/pandas, tkinter, networkx and matplotlib.
Code is currently tested only with python 3.4 in Anaconda/Winpython/MacOS/Windows 7

.. Note::
	In *Windows* it is strongly suggested **NOT to install the standard CPython distribution**,
    unless you are an experienced python-developer, you know how to hunt dependencies from *PyPi* repository and the `Unofficial Windows Binaries for Python Extension Packages <http://www.lfd.uci.edu/~gohlke/pythonlibs/>`_.
	
Install python 3.4 from one of:
	
	- `Anaconda <http://continuum.io/downloads>`_
	- `WinPython <https://winpython.github.io/>`_

Unzip the archive to some folder, `cd` to it and install its dependencies::
Open windows command prompt: start-->search cmd.exe --> run cmd.exe 

In the cmd window go in in the folder where you have unzipped the archive
(eg. cd\ --> cd\compas)

Run the following command:

	python setup.py -r requirements.txt

In case the command fails please refer to alternative usage method below for runnng jrc gear	

Usage of CO2MPAS
================
Once Python is installed appropriately

Execute the python-code from inside the extracted folder.

Just run (or directly double click):

	python compas.py

Then select the input and output folders form the UI-browser.

N.B. see the template file for input data.

Alternative usage:
Open any python development environment (eg spyder2 comes together with WinPython) or an ipython console from the python folder
Run the command
run 'C:/compas/compas.py'

where in ' '  you define the actual path where you have saved the file compas.py

The program should run and a window asking you to select the input and output folders should appear.
In case the you cannot see the respective window try minimizing your console in case the window appears in the background.