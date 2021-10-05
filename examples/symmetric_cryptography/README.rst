Symmetric Cryptography
======================
This example shows how to build a tool and a web API service to handle symmetric
cryptography using the **functional programming** paradigm, the
**dataflow programming** paradigm, and **schedula**. The scope is to build a
model that can read a file, generate a cryptography key, encrypt or decrypt the 
data and write them out to a new file.

Cryptography model
------------------
The general cryptography model is defined in ``model.py``. Since Python does not
come with anything that can encrypt/decrypt files, we use
a third-party module named ``cryptography``. To install it, execute
``pip install cryptography``. The ``cryptography.Fernet`` class generates the
cryptography keys to encrypt and decrypt the data.

API server
----------
The server model, which does not expose the system's reading and writing
features, and the Flask app are defined in the ``server.py`` file. The API
service can be deployed like a regular flask app or alternatively from
the code using the built-in functionality of **schedula**.

Usage
-----
You can see how to use the above models with the ipython notebook
``cryptography.ipynb``. To run the notebook, you have to type the following
command in the terminal and open the ``cryptography.ipynb``. Remember to click
`Kernel/Restart & Run All`.

     $ jupyter notebook

