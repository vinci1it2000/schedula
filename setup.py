#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

from distutils.core import setup

setup(
    name='dispatcher',
    version='0.0.1',
    packages=['', 'doc', 'tests', 'dispatcher'],
    url='',
    license='',
    author='Vincenzo Arcidiacono',
    author_email='vinci1it2000@gmail.com',
    description='A dispatch function calls.',
    requires=[
        'networkx',
        'matplotlib',
        'dill',
        'graphviz'
    ]
)
