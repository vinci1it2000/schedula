#! python
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2016 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

from co2mpas.__main__ import init_logging
from co2mpas.sampling import crypto
import doctest
import logging
import unittest

import ddt

import itertools as itt
import os.path as osp


init_logging(level=logging.DEBUG)

log = logging.getLogger(__name__)

mydir = osp.dirname(__file__)

texts = ('', ' ', 'a' * 2048, '123', 'asdfasd|*(KJ|KL97GDk;')
objs = ('', ' ', 'a' * 2048, 1244, b'\x22', {1: 'a', '2': {3, b'\x04'}})

ciphertexts = set()


class TestDoctest(unittest.TestCase):
    def runTest(self):
        failure_count, test_count = doctest.testmod(
            crypto,
            optionflags=doctest.NORMALIZE_WHITESPACE | doctest.ELLIPSIS)
        self.assertGreater(test_count, 0, (failure_count, test_count))
        self.assertEqual(failure_count, 0, (failure_count, test_count))


@ddt.ddt
class TCrypto(unittest.TestCase):

    @ddt.idata(itt.product(('user', '&^a09|*(K}'), texts, objs))
    def test_encrypt_text(self, case):
        pswdid, pswd, obj = case
        ciphertext = crypto.tencrypt_any(pswdid, pswd, obj)
        msg = ('CASE:', case, ciphertext)

        self.assertTrue(ciphertext.startswith(crypto.ENC_PREFIX), msg)

        ## Check not generating indetical ciphers.
        #
        self.assertNotIn(ciphertext, ciphertexts)
        ciphertexts.add(ciphertext)

        plainbytes2 = crypto.tdecrypt_any(pswdid, pswd, ciphertext)
        self.assertEqual(obj, plainbytes2, msg)

    @ddt.idata(texts)
    def test_derive_key(self, pswd):
        k1 = crypto.derive_key('test_derive_key', pswd)
        k2 = crypto.derive_key('test_derive_key', pswd)

        SHA256_LEN = 32
        self.assertEqual(len(k1), SHA256_LEN, pswd)
        self.assertEqual(k1, k2, pswd)
