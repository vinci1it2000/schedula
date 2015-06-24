#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

from setuptools import setup
from doc.conf import release
setup(
    name='dispatcher',
    version=release,
    packages=['dispatcher'],
    url='',
    license='',
    author='Vincenzo Arcidiacono',
    author_email='vinci1it2000@gmail.com',
    description='A dispatch function calls.',
    keywords=[
        "python", "utility", "library", "data", "processing",
        "calculation", "dependencies", "resolution", "scientific",
        "engineering", "dispatch", "simulink", "graphviz",
    ],
    classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.3",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: Implementation :: CPython",
        "Development Status :: 1 - Alpha",
        'Natural Language :: English',
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "Intended Audience :: Manufacturing",
        "License :: OSI Approved :: European Union Public Licence 1.1 (EUPL 1.1)",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX",
        "Operating System :: Unix",
        "Operating System :: OS Independent",
        "Topic :: Scientific/Engineering",
        "Topic :: Scientific/Engineering :: Information Analysis",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Utilities",
    ],
    requires=[
        'networkx',
        'matplotlib',
        'dill',
        'graphviz',
    ],
    test_suite='nose.collector',
    setup_requires=['nose>=1.0'],

)
