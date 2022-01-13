#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2022, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
import os
import unittest
import schedula as sh

EXTRAS = os.environ.get('EXTRAS', 'all')


@unittest.skipIf(EXTRAS not in ('all',), 'Not for extra %s.' % EXTRAS)
class TestDoctest(unittest.TestCase):
    def runTest(self):
        import doctest
        import schedula.utils.blue as utl
        failure_count, test_count = doctest.testmod(
            utl, optionflags=doctest.NORMALIZE_WHITESPACE | doctest.ELLIPSIS
        )
        self.assertGreater(test_count, 0, (failure_count, test_count))
        self.assertEqual(failure_count, 0, (failure_count, test_count))


@unittest.skipIf(EXTRAS not in ('all', 'io'), 'Not for extra %s.' % EXTRAS)
class TestBlueDispatcher(unittest.TestCase):
    def setUp(self):
        import functools
        ss_dsp = sh.Dispatcher()

        def fun(a, c):
            """

            :param a:
                Nice a.
            :type a: float

            :param c:
                Nice c.
            :type c: float

            :return:
                Something.
            :rtype: tuple
            """
            return a + 1, c, a - 1

        ss_dsp.add_function('fun', fun, ['a', 'e'], ['b', 'c', 'd'])
        ss_dsp_func = sh.DispatchPipe(
            ss_dsp, 'func', ['e', 'a'], ['c', 'd', 'b'])
        sub_disfun = sh.add_args(functools.partial(ss_dsp_func, 5))

        s_dsp = sh.Dispatcher()
        s_dsp.add_data('a', 1)
        s_dsp.add_data('d', 4)
        s_dsp.add_function(
            'sub_dispatch', sub_disfun, ['d', 'a'], ['b', 'c', sh.SINK]
        )

        dispatch = sh.SubDispatch(s_dsp, ['b', 'c', 'a'], output_type='list')
        self.dsp = dsp = sh.Dispatcher()
        dsp.add_data('input', default_value={'a': 3})

        dsp.add_function(
            'dispatch', dispatch, ['input'], [sh.SINK, 'h', 'i'],
            inp_weight={'input': 4}, out_weight={'h': 3, 'i': 6}
        )
        dsp.add_function('fun', lambda: None, None, ['j'])
        dsp.add_dispatcher(
            s_dsp, inputs=('a',), outputs=('b', 'c'), include_defaults=True
        )

    def test_blue_io(self):
        import dill
        s0 = self.dsp()
        pre_dsp = dill.dumps(self.dsp)
        blue = self.dsp.blue()
        self.assertEqual(pre_dsp, dill.dumps(self.dsp))
        pre = dill.dumps(blue), pre_dsp
        sol = blue()
        post = dill.dumps(blue), dill.dumps(self.dsp)
        self.assertEqual(pre, post)
        s = self.dsp()
        post = dill.dumps(blue), dill.dumps(self.dsp)
        self.assertEqual(pre, post)
        self.assertEqual(s, sol)
        self.assertEqual(s0, sol)
        self.assertLess(*map(len, post))
        self.assertLess(len(post[1]), len(dill.dumps(s)))
        blue, dsp = list(map(dill.loads, post))
        self.assertEqual(dsp.solution, {})
        self.assertEqual(s, dsp())
        self.assertEqual(s, blue())
