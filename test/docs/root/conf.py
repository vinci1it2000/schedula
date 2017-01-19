# -*- coding: utf-8 -*-

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
