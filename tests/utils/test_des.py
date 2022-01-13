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


@unittest.skipIf(EXTRAS not in ('all', 'base'), 'Not for extra %s.' % EXTRAS)
class TestDispatcherDes(unittest.TestCase):
    def setUp(self):
        ss_dsp = sh.Dispatcher(name='Ciao.')

        def fun(b, c, d=0):
            """
            Fun description.

            :param b:
                Second param.

            :param int c:
                Third param.

            :return:
                Out param.
            :rtype: float
            """
            return b + c + d

        def dom(a, *args):
            """
            :param a:
                First param.
            """
            return a

        ss_dsp.add_function(
            function=sh.add_args(fun), inputs=['a', 'b', 'c', 'd'],
            outputs=['e'],
            input_domain=dom
        )

        ss_dsp.add_function(
            function=sh.bypass, inputs=['e'],
            outputs=['f']
        )

        ss_dsp.add_function(
            function=sh.replicate_value, inputs=['f'],
            outputs=['g', 'h']
        )

        sdspfunc = sh.SubDispatchFunction(
            ss_dsp, 'SubDispatchFunction', ['a', 'b', 'c', 'd'], ['g', 'h']
        )

        sdsp = sh.SubDispatch(ss_dsp, ['e', 'f'], output_type='list')

        def fun1():
            """"""
            return

        sdspfunci = sh.SubDispatchFunction(
            ss_dsp, 'SubDispatchFunction', ['a', 'b', 'c', 'd']
        )

        s_dsp = sh.Dispatcher(name='Sub-Dispatcher')
        s_dsp.add_function('3', sdspfunc, ['a', 'b', 'c', 'd'], ['g', 'h'])
        s_dsp.add_function('8', sdspfunci, ['a', 'b', 'c', 'd'], ['o'])
        s_dsp.add_function('2', sdsp, ['I'], ['e', 'f'])
        s_dsp.add_function('4', max, ['e', 'f', 'l'], ['i'])
        s_dsp.add_function('5', inputs=['i'], outputs=['n'])
        s_dsp.add_function('6', fun1)
        s_dsp.add_function('7', sh.bypass, inputs=['p'],
                           input_domain=sh.add_args(lambda p: None))
        s_dsp.add_data('i', description='max.')

        self.dsp = dsp = sh.Dispatcher()
        dsp.add_dispatcher(
            dsp_id='1',
            dsp=s_dsp,
            inputs=('n', 'd', 'I', 'l', {'m': ('b', 'c'), ('a', 'a1'): 'a'}),
            outputs=['g', 'i', {'f': ('h', 'f')}, {('e', 'h'): ('e', 'e1')}]
        )

    def test_des(self):
        d = self.dsp
        kw = dict(node_attr='description')
        self.assertEqual(d.get_node('1', **kw)[0], 'Sub-Dispatcher')
        self.assertEqual(d.get_node('a', **kw)[0], 'First param.')
        self.assertEqual(d.get_node('a1', **kw)[0], 'First param.')
        self.assertEqual(d.get_node('m', **kw)[0], 'Second param.')
        self.assertEqual(d.get_node('e', **kw)[0], 'Out param.')
        self.assertEqual(d.get_node('e1', **kw)[0], 'Out param.')
        self.assertEqual(d.get_node('f', **kw)[0], '')
        self.assertEqual(d.get_node('h', **kw)[0], '')
        self.assertEqual(d.get_node('i', **kw)[0], 'max.')
        self.assertEqual(d.get_node('l', **kw)[0], '')
        self.assertEqual(d.get_node('n', **kw)[0], '')
        self.assertEqual(d.get_node(*'1o', **kw)[0], '')

        self.assertEqual(d.get_node(*'1a', **kw)[0], 'First param.')
        self.assertEqual(d.get_node(*'1b', **kw)[0], 'Second param.')
        self.assertEqual(d.get_node(*'1c', **kw)[0], 'Third param.')
        self.assertEqual(d.get_node(*'1d', **kw)[0], '')
        self.assertEqual(d.get_node(*'12', **kw)[0], 'Ciao.')
        self.assertEqual(d.get_node(*'13', **kw)[0], 'SubDispatchFunction')
        self.assertEqual(d.get_node(*'14', **kw)[0], max.__doc__.split('\n')[0])
        self.assertEqual(d.get_node(*'15', **kw)[0], '')

        self.assertEqual(d.get_node(*'12a', **kw)[0], 'First param.')
        self.assertEqual(d.get_node(*'12b', **kw)[0], 'Second param.')
        self.assertEqual(d.get_node(*'12c', **kw)[0], 'Third param.')
        self.assertEqual(d.get_node(*'12d', **kw)[0], '')
        self.assertEqual(d.get_node(*'12e', **kw)[0], 'Out param.')
        self.assertEqual(d.get_node(*'12f', **kw)[0], '')
        self.assertEqual(d.get_node(*'12g', **kw)[0], '')
        self.assertEqual(d.get_node(*'12h', **kw)[0], '')
        self.assertEqual(d.get_node(
            '1', '2', 'fun', **kw
        )[0], 'Fun description.')
        self.assertEqual(d.get_node(*'16', **kw)[0], '')
        self.assertEqual(d.get_node(*'1p', **kw)[0], '')

        self.assertEqual(d.get_node(*'13', **kw)[0], 'SubDispatchFunction')
        kw = dict(node_attr='value_type')
        self.assertEqual(d.get_node('a', **kw)[0], '')
        self.assertEqual(d.get_node('m', **kw)[0], 'int')
        self.assertEqual(d.get_node('e', **kw)[0], 'float')
