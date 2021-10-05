File Processing Chain
=====================
This example shows how **functional programming** paradigm, the
**dataflow programming** paradigm and **schedula** can be used to:

- **read** from an excel file,
- **process** some data with a generic model,
- **write** the outputs in a new excel file, and
- **plot** the results.

For example, the input file (``files/inp.xlsx``) has two columns `Time [s]` and
`Velocity [m/s]` and we want to compute the distance and the acceleration.

Computational model
-------------------
The general computational model is defined in ``model.py``. It uses the
``numpy.gradient`` function to calculate the ``acceleration`` and the
``scipy.integrate.cumtrapz`` to calculate the ``distance``.


Plotting results
----------------
We built a separate module ``utils/plot.py`` that has two utility functions
(i.e., ``define_plot_data`` and ``plot_lines`` to help the plotting of
time-series in the ipython notebook using ``plotly`` library.


Process model
-------------
The process model is composed of four blocks:

1. to read the excel file,
2. to parse the data renaming the column's names to match the model ids,
3. to compute the outputs with our computational model, and
4. to save the outputs in a new excel file.

You can see the execution of the example with the ipython notebook
``processing.ipynb``. To run the notebook you have to type the following command
in the terminal and open the ``processing.ipynb``. Remember to click
`Kernel/Restart & Run All`.

     $ jupyter notebook
