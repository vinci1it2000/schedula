#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2023, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

import os
import platform
import time
import unittest
import schedula as sh
import os.path as osp

EXTRAS = os.environ.get('EXTRAS', 'all')

PLATFORM = platform.system().lower()


@unittest.skipIf(True, 'Skip test.')
@unittest.skipIf(EXTRAS not in ('all', 'form'), 'Not for extra %s.' % EXTRAS)
@unittest.skipIf(PLATFORM not in ('darwin', 'linux'),
                 'Not for platform %s.' % PLATFORM)
class TestDispatcherForm(unittest.TestCase):
    @classmethod
    def setUpClass(cls):

        import sys
        import chromedriver_autoinstaller
        from selenium import webdriver
        from pyvirtualdisplay import Display


        if os.environ.get('ACTION', '').lower() == 'true':
            cls.display = display = Display(visible=False, size=(800, 800))
            display.start()

        chromedriver_autoinstaller.install()
        cls.driver = webdriver.Chrome()
        cls.form_dir = form_dir = osp.abspath(osp.join(
            osp.dirname(__file__), '..', '..', 'examples',
            'length_converter'
        ))
        sys.path.insert(0, form_dir)

    def setUp(self):
        from examples.length_converter.form import form as dsp
        self.dsp = dsp.register()
        self.site = None

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'driver'):
            cls.driver.close()
        if hasattr(cls, 'display'):
            cls.display.stop()

    def tearDown(self):
        if self.site:
            self.site.shutdown()

        sh.shutdown_executors(False)

    def test_form1(self):
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.common.exceptions import NoSuchElementException
        from selenium.webdriver.support import expected_conditions as EC

        self.site = self.dsp.form(directory=self.form_dir, run=True, view=False)
        driver = self.driver

        driver.get('%s/' % self.site.url)
        WebDriverWait(driver, 30).until(
            EC.visibility_of_element_located((By.ID, "run-button"))
        ).click()
        time.sleep(3)
        with self.assertRaises(NoSuchElementException):
            driver.find_element(value='context-data')
        self.assertTrue(WebDriverWait(driver, 30).until(
            EC.visibility_of_element_located((By.ID, "run-button"))
        ).get_attribute('disabled'))

        WebDriverWait(driver, 30).until(
            EC.visibility_of_element_located((By.ID, "delete-button"))
        ).click()
        time.sleep(3)
        self.assertTrue(not WebDriverWait(driver, 30).until(
            EC.visibility_of_element_located((By.ID, "run-button"))
        ).get_attribute('disabled'))
        if EXTRAS in ('all',):
            WebDriverWait(driver, 30).until(
                EC.visibility_of_element_located((By.ID, "debug-button"))
            ).click()
            time.sleep(3)
            self.assertTrue(WebDriverWait(driver, 30).until(
                EC.visibility_of_element_located((By.ID, "run-button"))
            ).get_attribute('disabled'))


    def test_form2(self):
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        sites = set()
        self.dsp.form(
            directory=self.form_dir, run=True, sites=sites, view=False,
            get_context=lambda: {
                'data': 'cool'
            }, get_data=lambda: {
                "input": {"kwargs": {
                    "inputs": {
                        "value_in": 1, "unit_in": "m",
                        "units_out": ["in", "mm", "km"]
                    },
                    "select_output_kw": {
                        "keys": ["results", "value_in", "unit_in"],
                        "output_type": "all"
                    }
                }},
                "return": {
                    "results": [
                        {"unit_out": "in", "value_out": 39.37007874015748},
                        {"unit_out": "mm", "value_out": 1000},
                        {"unit_out": "km", "value_out": 0.001}
                    ],
                    "unit_in": "m",
                    "value_in": 1
                },
                "hash": "cc051052ae52aa702474df394b5d4f23c19f3232"
            }
        )
        self.site = sites.pop()
        driver = self.driver

        driver.get('%s/index' % self.site.url)
        self.assertTrue(WebDriverWait(driver, 30).until(
            EC.visibility_of_element_located((By.ID, "run-button"))
        ).get_attribute('disabled'))
        self.assertEqual(
            driver.find_element(value='context-data').get_attribute('content'),
            'cool'
        )
