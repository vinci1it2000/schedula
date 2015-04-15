#! python
##
## Installs jrcgear:
## 		python setup.py install
## or
##		pip install -r requirements.txt
## and then just code from inside this folder.
#
from setuptools import setup

setup(name='doit-graphx',
      description="JRC gear tool to predict the A/T gear shifting of the NEDC from the data of WLTP,"
                  "according to decision tree approach and the corrected matrix velocity.",
      long_description="",
      version='0.1b1',
      author='Vincenzo Arcidiacono',
      author_email='vincenzo.arcidiacono@ext.jrc.ec.europa.eu',
      classifiers=[
          'Development Status :: 1 - Beta',
          'Environment :: Console',
          'License :: OSI Approved :: European Union Public Licence 1.1 (EUPL 1.1)',
          'Natural Language :: English',
          'Operating System :: OS Independent',
          'Operating System :: POSIX',
          'Programming Language :: Python :: 2',
          'Programming Language :: Python :: 2.7',
          'Programming Language :: Python :: 3',
          'Programming Language :: Python :: 3.3',
          'Programming Language :: Python :: 3.4',
          'Intended Audience :: Developers',
          'Intended Audience :: Science/Research',
          'Topic :: Scientific/Engineering',
      ],

      py_modules=['jrcgear'],
      install_requires=['pandas','tkinter','numpy','scipy','sklearn','matplotlib'],
      )
