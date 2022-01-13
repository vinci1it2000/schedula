#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2022, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

import os
from setup import (
    name, proj_ver, get_long_description, url, download_url, project_urls
)

if __name__ == '__main__':
    from setuptools import setup, find_packages
    from micropython.sdist_upip import sdist

    long_description = ''
    if os.environ.get('ENABLE_SETUP_LONG_DESCRIPTION') == 'TRUE':
        try:
            long_description = get_long_description()
            print('LONG DESCRIPTION ENABLED!')
        except Exception as ex:
            print('LONG DESCRIPTION ERROR:\n %r', ex)

    # noinspection PyTypeChecker
    setup(
        name='micropython-%s' % name,
        version=proj_ver,
        packages=find_packages(exclude=[
            'doc', 'doc.*',
            'tests', 'tests.*',
            'examples', 'examples.*',
            'micropython', 'micropython.*',
            'schedula.ext', 'schedula.ext.*',
            'schedula.utils.io', 'schedula.utils.io.*',
            'schedula.utils.drw', 'schedula.utils.drw.*',
            'schedula.utils.web', 'schedula.utils.web.*',
            'schedula.utils.des', 'schedula.utils.des.*',
            'requirements', 'binder', 'bin'
        ]),
        url=url,
        project_urls=project_urls,
        download_url=download_url,
        license='EUPL 1.1+',
        author='Vincenzo Arcidiacono',
        author_email='vinci1it2000@gmail.com',
        description='Produce a plan that dispatches calls based on a graph of '
                    'functions, satisfying data dependencies.',
        long_description=long_description,
        keywords=[
            "flow-based programming", "dataflow", "parallel", "asynchronous",
            "async", "scheduling", "dispatch", "functional programming",
            "dataflow programming",
        ],
        classifiers=[
            "Programming Language :: MicroPython",
            "Development Status :: 5 - Production/Stable",
            'Natural Language :: English',
            "Intended Audience :: Developers",
            "Intended Audience :: Science/Research",
            "License :: OSI Approved :: European Union Public Licence 1.1 "
            "(EUPL 1.1)",
            "Operating System :: MacOS :: MacOS X",
            "Operating System :: Unix",
            "Topic :: Scientific/Engineering",
            "Topic :: Scientific/Engineering :: Information Analysis",
            "Topic :: Software Development :: Libraries :: Python Modules",
            "Topic :: Utilities",
        ],
        cmdclass={'sdist': sdist},
        install_requires=[
            'micropython-itertools', 'micropython-logging', 'micropython-types',
            'micropython-functools', 'micropython-inspect', 'micropython-copy',
            'micropython-collections.deque', 'micropython-collections',
        ],
        tests_require=['micropython-unittest', 'micropython-timeit'],
    )
