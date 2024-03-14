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
        options = webdriver.ChromeOptions()
        options.add_argument("--incognito")
        cls.driver = driver = webdriver.Chrome(options=options)
        driver.implicitly_wait(2)
        cls.form_dir = form_dir = osp.abspath(osp.join(
            osp.dirname(__file__), '..', '..', 'examples', 'length_converter'
        ))
        sys.path.insert(0, form_dir)

        cls.stripe_form_dir = stripe_form_dir = osp.abspath(osp.join(
            osp.dirname(__file__), 'form'
        ))
        sys.path.insert(0, stripe_form_dir)

    def setUp(self):
        from examples.length_converter.form import form as dsp
        self.dsp = dsp.register()
        self.site = None
        self.stripe_site = None

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'driver'):
            cls.driver.close()
        if hasattr(cls, 'display'):
            cls.display.stop()

    def tearDown(self):
        if self.site:
            self.site.shutdown()
        if self.stripe_site:
            self.stripe_site.shutdown()

        sh.shutdown_executors(False)

    def test_form1(self):
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.common.exceptions import NoSuchElementException
        from selenium.webdriver.support import expected_conditions as EC
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
            WebDriverWait(driver, 30).until(
                EC.visibility_of_element_located((
                    By.XPATH, "//span[text()='OK']"
                ))
            ).click()
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

    @unittest.skipIf(
        'STRIPE_SECRET_KEY' not in os.environ, 'Stripe keys not configured.'
    )
    def test_form_stripe(self):
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        status = [False]

        def stripe_event_handler(event):
            if event['type'] == 'payment_intent.created':
                status[0] = True

        self.stripe_site = sh.Dispatcher().form(
            directory=self.stripe_form_dir, run=False, view=False,
            stripe_event_handler=stripe_event_handler
        ).site().run(port=5009)

        driver = self.driver
        driver.get('%s/' % self.stripe_site.url)

        def send_payment(card):
            driver.switch_to.frame(WebDriverWait(driver, 30).until(
                EC.visibility_of_element_located((
                    By.NAME, 'embedded-checkout'
                ))
            ))
            driver.find_element(By.ID, 'email').send_keys('schedula@gmail.com')
            driver.find_element(By.ID, 'cardNumber').send_keys(card)
            driver.find_element(By.ID, 'cardExpiry').send_keys('1225')
            driver.find_element(By.ID, 'cardCvc').send_keys('123')
            driver.find_element(By.ID, 'billingName').send_keys('Schedula User')
            driver.find_element(
                By.XPATH,
                '//button[@data-testid="hosted-payment-submit-button"]'
            ).click()

        for card in ('4000000000000002',):
            send_payment(card)
            self.assertTrue(bool(WebDriverWait(driver, 60).until(
                EC.visibility_of_element_located((
                    By.XPATH,
                    '//input[contains(@class, "CheckoutInput--invalid")]'
                ))
            )))
            driver.get('%s/' % self.stripe_site.url)
            driver.switch_to.alert.accept()
        send_payment('4242424242424242')
        import requests
        fp = osp.join(osp.dirname(__file__), 'form', 'webhook.json')
        with open(fp, 'rb') as f:
            payload = f.read()
        resp = requests.post(
            self.stripe_site.url + '/stripe/webhook', data=payload,
            headers={
                'STRIPE-SIGNATURE': (
                    't=1710289463,v1=349b804a6deab4c867dc598b8f277abc7e9bd4bcd756b896d086570bbc311d13,v0=e44e68f09d9b568184155abd7fbb8589438c0d0a817fe1db74d120d1ffcd3515'
                )
            }
        )
        self.assertTrue(resp.json()['success'])
        self.assertTrue(status[0])
