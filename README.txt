###############
	jrcgear
###############
:author: Vincenzo Arcidiacono <vincenzo.arcidiacono@ext.jrc.ec.europa.eu>
:version: 0.1-a4
:date: 31-Mar-2015

Predicts the NEDC data from the WLTC tests.

:input: a directory that contains WLPC and NEDC input data ['.xls','.xlsx','xlsm']
:output: a directory to store the predicted gears and plots

JRC_simplified class controlls the process.
Cycle class identifies data

Install
=========
Requires CPython-3, and numpy/pandas, tkinter and matplotlib.
Tested only with python 3.4 in Anaconda/Winpython/MacOS

.. Note::
	On *Windows* it is strongly suggested **NOT to install the standard CPython distribution**,
    unless you are an experienced python-developer, you know how to hunt dependencies from *PyPi* repository and the `Unofficial Windows Binaries for Python Extension Packages <http://www.lfd.uci.edu/~gohlke/pythonlibs/>`_.
	
	Install py3 from one of:
	
	- `Anaconda <http://continuum.io/downloads>`_
	- `WinPython <https://winpython.github.io/>`_

Unzip the archive to some folder, `cd` to it and install its dependencies::
	
	python setup.py -r requirements.txt

Then just execute its python-code from inside this folder.



Usage
======
Just run::

	python jrcgear.py

Then select the input and output folders form the UI-browser.

N.B. see the template file for input data.
