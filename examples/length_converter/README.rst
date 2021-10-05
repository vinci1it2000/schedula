Unit Length Converter
=====================
This example shows how to build a unit length converter using the
**functional programming** paradigm, the **dataflow programming** paradigm, and
**schedula**. The scope is to build a general model that can convert the length
defined with a unit to all other units. For example, the model should take as
input 1 foot and return as output 30.48 cm, 12 inches, etc.

Imperial and metric models
--------------------------
We built two models to handle the imperial unit system separately
(i.e., English system, see ``models/imperial.py``) and the metric system (i.e.,
International System, see ``models/metric.py``).
Each model file starts with the definition of the conversion functions of the
relative system and ends with a model definition that combines all functions
together.

Converter model
---------------
The converter model is defined in the ``converter.py`` file. We merge the
previously generated models (imperial and metric) into a single model that has
two functions (i.e., ``inch2cm`` and ``cm2inch``) to connect the unit
systems.

Converter execution
-------------------
You can see how to use the converter model with the ipython notebook
``converter.ipynb``. To run the notebook you have to type the following command
in the terminal and open the ``converter.ipynb``. Remember to click
`Kernel/Restart & Run All`.

     $ jupyter notebook

