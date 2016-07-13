#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2014 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

import doctest
import unittest

from co2mpas.model.physical.wheels import calculate_tyre_dimensions

import ddt

@ddt.ddt
class TCO2(unittest.TestCase):

    @ddt.data(
        'LT265/75R15 D',
        'LT245/75R16 120/116S E',
        '32X11.50 R 15 C',
        '9.50R16.5 LT 121/117T E',
        '205/65R15 C 102/100R',
        '7.50R16 C 112/110N'
    )
    def test_calculate_tyre_dimensions(self, case):
        tyre_code = case
        result = res = calculate_tyre_dimensions(tyre_code)
        self.assertEqual(result, res)
    @ddt.data(
        ('LT265/75R15 D', {
            'code': 'iso', 'carcass': 'R',
            'nominal_section_width': 265.0, 'use': 'LT',
            'load_range': 'D', 'rim_diameter': 15.0, 'aspect_ratio': 75.0}),
        ('LT245/75R16 120/116S E', {
            'nominal_section_width': 245.0, 'use': 'LT', 'aspect_ratio': 75.0,
            'code': 'iso', 'load_index': '120/116', 'carcass': 'R',
            'rim_diameter': 16.0, 'load_range': 'E',
            'speed_rating': 'S'}),
        ('32X11.50 R 15 LT C', {
            'nominal_section_width': 11.5, 'aspect_ratio': 92.0,
            'carcass': 'R', 'code': 'numeric', 'load_range': 'C',
            'rim_diameter': 15.0, 'use': 'LT', 'diameter': 32.0}),
        ('9.50R16.5 LT 121/117T E', {
            'carcass': 'R', 'speed_rating': 'T', 'code': 'numeric',
            'load_range': 'E', 'use': 'LT', 'load_index': '121/117',
            'aspect_ratio': 92.0, 'nominal_section_width': 9.5,
            'rim_diameter': 16.5}),
        ('9.50R16.5 LT 121/117T M+S', {
            'carcass': 'R', 'speed_rating': 'T', 'code': 'numeric',
            'use': 'LT', 'load_index': '121/117',
            'aspect_ratio': 92.0, 'nominal_section_width': 9.5,
            'rim_diameter': 16.5, 'additional_marks': 'M+S'}),
        ('205/65R15 C 102/100R',{
            'rim_diameter': 15.0, 'carcass': 'R', 'speed_rating': 'R',
            'load_index': '102/100', 'use': 'C',
            'code': 'iso', 'aspect_ratio': 65.0,
            'nominal_section_width': 205.0}),
        ('7.50R16 C 112/110N', {
            'use': 'C', 'aspect_ratio': 92.0,
            'load_index': '112/110', 'rim_diameter': 16.0, 'speed_rating': 'N',
            'carcass': 'R', 'nominal_section_width': 7.5, 'code': 'numeric'}),
    )
    def test_calculate_tyre_dimensions(self, case):
        tyre_code, result = case
        res = calculate_tyre_dimensions(tyre_code)
        self.assertEqual(result, res)