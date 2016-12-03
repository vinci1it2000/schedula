#! python
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2016 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

from co2mpas.__main__ import init_logging
from co2mpas.sampling import crypto
import logging
import unittest

import ddt

import itertools as itt
import os.path as osp


init_logging(level=logging.DEBUG)

log = logging.getLogger(__name__)

mydir = osp.dirname(__file__)

texts = ('', ' ', 'a' * 2048, '123', 'asdfasd|*(KJ|KL97GDk;')

ciphertexts = set()


@ddt.ddt
class TCrypto(unittest.TestCase):

    @ddt.idata(itt.product(('user', '&^a09|*(K}'), texts, texts))
    def test_encrypt_text(self, case):
        pswdid, pswd, text = case
        plainbytes = text.encode()
        ciphertext = crypto.text_encrypt(pswdid, pswd, plainbytes)
        msg = ('CASE:', case, ciphertext)

        self.assertTrue(ciphertext.startswith(crypto.ENC_PREFIX), msg)

        ## Checknot generating indetical ciphers.
        #
        self.assertNotIn(ciphertext, ciphertexts)
        ciphertexts.add(ciphertext)

        plainbytes2 = crypto.text_decrypt(pswdid, pswd, ciphertext)
        self.assertEqual(plainbytes, plainbytes2, msg)

    @ddt.idata(itt.product((-1, 1, 100, 1000), texts))
    def test_rot(self, case):
        nrot, s = case
        f1, f2 = crypto.rot_funcs(nrot)
        s1 = f1(s)
        s2 = f2(s1)
        msg = ('CASE:', case, s1, s2)

        self.assertEqual(len(s), len(s1), msg)
        self.assertEqual(len(s), len(s2), msg)
        if s:  # Exlcude empty string
            self.assertNotEqual(s, s1, msg)
        else:
            self.assertEqual(s, s1, msg)
        self.assertEqual(s, s2, msg)
        
    def test_rot_random(self):
        ss = set()
        s = "abc"
        for _ in range(30000):
            f1, _ = crypto.rot_funcs()
            s1 = f1(s)
            ss.add(s1)
            # Check not ever the same.
            self.assertNotEqual(s, s1)
        self.assertGreater(len(ss), 80) # 94 letters, usually all covvered
