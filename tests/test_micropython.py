#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2024, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
import unittest


# noinspection PyTypeChecker
def _make_suite():
    from .utils.test_dsp import (
        TestDispatcherUtils, TestSubDispatcher, TestSubDispatchFunction,
        TestSubDispatchPipe, TestDispatchPipe
    )
    from .utils.test_alg import TestDispatcherGetSubNode
    from .utils.test_gen import TestUtils
    from .test_dispatcher import (
        TestDispatch, TestPerformance, TestBoundaryDispatch, TestNodeOutput,
        TestShrinkDispatcher, TestPipe, TestSubDMap, TestCreateDispatcher
    )

    suite = unittest.TestSuite()
    suite.addTest(TestDispatcherUtils)
    return suite


if __name__ == '__main__':
    import os
    import sys

    os.environ['EXTRAS'] = os.environ.get('EXTRAS', 'micropython')

    runner = unittest.TestRunner()
    result = runner.run(_make_suite())

    # noinspection PyUnresolvedReferences
    sys.exit(result.failuresNum > 0)
