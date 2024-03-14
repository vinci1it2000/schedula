#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2024, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl


import sys
import os
from schedula._version import __version__

sys.path.append(os.path.abspath('.'))

extensions = [
    'sphinx.ext.doctest',
    'sphinx.ext.mathjax',
    'schedula.ext.autosummary',
    'schedula.ext.dispatcher'
]

templates_path = ['_templates']
master_doc = 'index'
autosummary_generate = True

autodoc_member_order = 'bysource'

version = '.'.join(__version__.split('.')[:-1])
release = __version__
