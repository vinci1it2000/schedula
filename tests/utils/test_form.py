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
        cls.driver.implicitly_wait(2)
        cls.form_dir = form_dir = osp.abspath(osp.join(
            osp.dirname(__file__), '..', '..', 'examples', 'length_converter'
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
        from selenium.common.exceptions import NoSuchElementException
        sites = set()
        self.dsp.form(
            directory=self.form_dir, run=True, sites=sites, view=False,
            get_context=lambda: {
                'runnable': False,
                'userInfo': {}
            }, get_data=lambda: {
                "input": {"kwargs": {
                    "inputs": {
                        "value_in": 2, "unit_in": "m",
                        "units_out": ["in", "mm", "km"]
                    },
                    "select_output_kw": {
                        "keys": ["results", "value_in", "unit_in"],
                        "output_type": "all"
                    }
                }},
                "return": {
                    "results": [
                        {"unit_out": "in", "value_out": 78.74015748031496},
                        {"unit_out": "mm", "value_out": 2000},
                        {"unit_out": "km", "value_out": 0.002}
                    ],
                    "unit_in": "m",
                    "value_in": 2
                }
            }
        )
        self.site = sites.pop()
        driver = self.driver
        driver.get('%s/' % self.site.url)

        def _btn(*classes):
            classes = ' and '.join(f'contains(@class, "{v}")' for v in classes)
            return driver.find_element(By.XPATH, f'//li[{classes}]')

        def _clean():
            _btn('clean-button').click()
            time.sleep(1)
            driver.find_element(By.XPATH, "//span[text()='OK']").click()
            time.sleep(1)
            with self.assertRaises(NoSuchElementException):
                _btn('run-button', 'ant-menu-item-disabled')
            with self.assertRaises(NoSuchElementException):
                _btn('debug-button', 'ant-menu-item-disabled')

        def _run(btn):
            _btn(btn).click()
            self.assertTrue(_btn('run-button', 'ant-menu-item-disabled'))

        self.assertTrue(_btn('run-button', 'ant-menu-item-disabled'))
        _clean()
        _run('run-button')
        with self.assertRaises(NoSuchElementException):
            _btn('debug-button', 'ant-menu-item-disabled')
        _clean()
        if EXTRAS in ('all',):
            _run('debug-button')
            self.assertTrue(_btn('debug-button', 'ant-menu-item-disabled'))
            _clean()
