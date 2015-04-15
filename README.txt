###############
	jrcgear
###############
:author: Vincenzo Arcidiacono <vincenzo.arcidiacono@ext.jrc.ec.europa.eu>
:version: 0.1b1
:date: 15-Apr-2015

Predicts the NEDC gearshifting for automatic gearboxes from the WLTC measurement.

:input: a directory that contains WLTC and NEDC input data ['.xls','.xlsx','xlsm']
:output: a directory to store the predicted gears and plots

Class: JRC_simplified  controlls the process.
Class: Cycle identifies data


Install jrcgear
==================
The program requires CPython-3, and numpy/pandas, tkinter and matplotlib.
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
(eg. cd\ --> cd\jrcgear)

Run the following command:

	python setup.py -r requirements.txt


Usage of jrcgear
===================
Once Python is installed appropriately

Execute the python-code from inside the extracted folder.

Just run::

	python jrcgear.py

Then select the input and output folders form the UI-browser.

N.B. see the template file for input data.


