#! python
# -*- coding: UTF-8 -*-
#
# Copyright 2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

from getpass import getpass
import io
import logging
import os
import sys
import tempfile
from unittest import mock
import unittest

import ddt
import git
import gnupg
from traitlets.config import get_config
import yaml

from co2mpas.__main__ import init_logging
from co2mpas.sampling import baseapp, dice, project
import os.path as osp


init_logging(level=logging.DEBUG)

log = logging.getLogger(__name__)

mydir = osp.dirname(__file__)

#
# _test_cfg = """
# sampling:
#     sender: 'konstantinos.anagnostopoulos@ext.jrc.ec.europa.eu'
#     dice_recipients:
#         - konstantinos.anagnostopoulos@ext.jrc.ec.europa.eu
#         - ankostis@gmail.com
#     mail_server:
#         host: email.jrc.it
#         ssl: true
# """
#
# # b=lambda: (input('User? '), getpass('Paswd? '))
# class LoginCb(object):
#     max_smtp_login_attempts = 3
#
#
#     def ask_user_pswd(self, mail_server):
#         self.max_smtp_login_attempts -= 1
#         if self.max_smtp_login_attempts > 0:
#             return 'konstantinos.anagnostopoulos', 'zhseme1T'
#
#     def report_failure(self, errmsg):
#         print(errmsg)
#
# # with open(fpath) as fp:
# #     # Create a text/plain message
# #     msg = MIMEText(fp.read())
# _signed_msg = """
# -----BEGIN PGP SIGNED MESSAGE-----
# Hash: SHA256
#
# hi gpg
# -----BEGIN PGP SIGNATURE-----
# Version: GnuPG v2
#
# iQEcBAEBCAAGBQJW3YK+AAoJEDOsPX8JK97lgTAH/2C2TF5dsVaEWqI5grhHnERK
# kMkq9sHK5Gi3g8VbRB5gcaSM0xN3YmdzQlwp1kKdbQTffUwJk9U4ErQ9LT7RJNaH
# e5Rr9w45nRiSjAyJME4858kWNv0vvRdloB58y/eRzcO5WfTsOQsnl471Lct6wSN1
# gQHZcRQVW4p18rJ9kaeBr5C9H2vg5CRTfrwMKDRX+ntGj1HY/obl4Kb2IgWSLDcd
# 5uGImNIDu3gQ15ibh1bIwH8/ya8tg38JBNhlYdvt9/y24jgsKKO+iOHVLUMj7LO6
# q1mI64ULC1SlW2KBKdGV0xDcq+YA3GoXhD5FDPS70cTQ+DBkx1lUa6xmZgBR0uE=
# =ctnm
# -----END PGP SIGNATURE-----
# """
#
# _signed_tags = {'v1.2.1': [b"""object 76bcb73a24bfc40d6480a1a3050d743b02f71625
# type commit
# tag v1.2.1
# tagger Kostis Anagnostopoulos <ankostis@gmail.com> 1461012303 +0200
#
# Panino release-no2:
#
# - real-cars,
# - theoritical-wltp,
# - repeatable 64bit,
# - input-schema.
#
# See https://github.com/JRCSTU/co2mpas/releases/tag/v1.2.0
# """, b"""-----BEGIN PGP SIGNATURE-----
# Version: GnuPG v1
#
# iEYEABECAAYFAlcVR08ACgkQnPJ3xAqKGwi9sQCeJ4qO6a30FqBMoDJhW5esS+Q0
# uYMAn3l0GhwyCkob9OQ9EBjqETse+LoE
# =W4tm
# -----END PGP SIGNATURE-----
# """]}
#
# _timestamped_msg = """
#
# -----BEGIN PGP SIGNED MESSAGE-----
#
# ########################################################
# #
# # This is a proof of posting certificate from
# # stamper.itconsult.co.uk certifying that a user
# # claiming to be:-
# #     konstantinos.anagnostopoulos@ext.jrc.ec.europa.eu
# # requested that this message be sent to:-
# #     ankostis@gmail.com
# #     konstantinos.anagnostopoulos@ext.jrc.ec.europa.eu
# #
# # This certificate was issued at 14:50 (GMT)
# # on Monday 07 March 2016 with reference 0891345
# #
# # CAUTION: while the message may well be from the sender
# #          indicated in the "From:" header, the sender
# #          has NOT been authenticated by this service
# #
# # For information about the Stamper service see
# #        http://www.itconsult.co.uk/stamper.htm
# #
# ########################################################
#
#
#
#
# - -----BEGIN PGP SIGNED MESSAGE-----
# Hash: SHA256
#
# hi gpg
# - -----BEGIN PGP SIGNATURE-----
# Version: GnuPG v2
#
# iQEcBAEBCAAGBQJW3YK+AAoJEDOsPX8JK97lgTAH/2C2TF5dsVaEWqI5grhHnERK
# kMkq9sHK5Gi3g8VbRB5gcaSM0xN3YmdzQlwp1kKdbQTffUwJk9U4ErQ9LT7RJNaH
# e5Rr9w45nRiSjAyJME4858kWNv0vvRdloB58y/eRzcO5WfTsOQsnl471Lct6wSN1
# gQHZcRQVW4p18rJ9kaeBr5C9H2vg5CRTfrwMKDRX+ntGj1HY/obl4Kb2IgWSLDcd
# 5uGImNIDu3gQ15ibh1bIwH8/ya8tg38JBNhlYdvt9/y24jgsKKO+iOHVLUMj7LO6
# q1mI64ULC1SlW2KBKdGV0xDcq+YA3GoXhD5FDPS70cTQ+DBkx1lUa6xmZgBR0uE=
# =ctnm
# - -----END PGP SIGNATURE-----
#
# -----BEGIN PGP SIGNATURE-----
# Version: 2.6.3i
# Charset: noconv
# Comment: Stamper Reference Id: 0891345
#
# iQEVAgUBVt2VGIGVnbVwth+BAQHzMgf+I5X0bMvFjxgrlskt1IqlXahuGmh20okQ
# wEC01LEZb0v8vTVKYyjSllvRdDp93Debm6ll3GieuCNs80FWkkY45yi7pKOk68Em
# ia2RkPRrZRBllTc8ZIlezt1/XJBw4RdqEbk4pExNIfnjGfBv4aKAuMlS/B6XijWv
# EnNc6rb3HFpbYwboHi1yA/HvlIGnWEwNPFdDJLEacsV6acBTAG7TGiXYv7S/I4wQ
# 0rjbqjGvGijyt5XKjI8fFYApPBcNiwlmLSSovn4JglBHC6Cfo0PG7HTZvbTMFwlh
# KTv1GRz3C2ofyMwqx4TGueTHr8ANtNm7ByUEVLzmCq3Aod6r5CGXUg==
# =ahMl
# -----END PGP SIGNATURE-----
#
# """
#
# def _make_test_cfg():
#     cfg = io.StringIO(_test_cfg)
#     return yaml.load(cfg)
#
# def gitrepo():
#     repo = git.Repo(osp.join(mydir, '..'))
#     return repo
#
#
# class TGit(unittest.TestCase):
#
#     def test_git_tag(self):
#         repo = gitrepo()
#         tagref = repo.tag('refs/tags/v1.2.1')
#         self.assertEqual(tagref.commit.hexsha, '76bcb73a24bfc40d6480a1a3050d743b02f71625')
#         tag = tagref.tag
#         self.assertEqual(tag.hexsha, '66a4def7930187427b9abc9200b1b981fa22ea6e')
#
#     def test_parse_git_tags(self):
#         gpg = dice.DiceGPG(verbose=1)
#         repo = gitrepo()
#         tag = repo.tag('refs/tags/v1.2.1').tag
#         tag_bytes = dice.git_read_bytes(tag)
#         res = dice.split_detached_signed(tag_bytes)
#         self.assertIsInstance(res, tuple)
#         self.assertEqual(len(res), 2)
#
#         sig, msg = res
#         gpg = dice.DiceGPG(verbose=1)
#         ver = gpg.verify_detached(sig, msg)
#         self.assertTrue(ver, ver)
#
# class TGPG(unittest.TestCase):
#     def test_pverify_git_tags(self):
#         gpg = dice.DiceGPG(verbose=1)
#         for _, (msg, sig) in _signed_tags.items():
#             msg = msg.replace(b'\n\r', b'\n')
#             ver = gpg.verify_detached(sig, msg)
#             self.assertTrue(ver, ver)
#
# @ddt.ddt
# class TDice(unittest.TestCase):
#
#     @unittest.skip('FFF')
#     def test_send_email(self):
#         cfg = _make_test_cfg()
#         email = dice.send_timestamped_email(msg, login_cb=LoginCb(), **cfg['mail_server'])
#         log.info(email)
#
#     @unittest.skip('FFF')
#     def test_receive_emails(self):
#         emails = dice.receive_timestamped_email(mail_server, LoginCb(), ssl=True)
#         log.info(emails)
#
#     @unittest.skip('Enabled it to generate test-keys!!')
#     def test_gen_key_proof_of_work(self):
#         import gnupg
#         gpg_prog = 'gpg2.exe'
#         gpg2_path = dice.which(gpg_prog)
#         self.assertIsNotNone(gpg2_path)
#         gpg=gnupg.GPG(gpg2_path)
#
#         def key_predicate(fingerprint):
#             keyid = fingerprint[24:]
#             return dice._has_repeatitive_prefix(keyid, limit=2)
#
#         def keyid_starts_repetitively(fingerprint):
#             keyid = fingerprint[24:]
#             return dice._has_repeatitive_prefix(keyid, limit=2)
#         def keyid_n_fingerprint_start_repetitively(fingerprint):
#             keyid = fingerprint[24:]
#             return dice._has_repeatitive_prefix(keyid, limit=2)
#
#         name_real='Sampling Test',
#         name_email='sampling@co2mpas.jrc.ec.europa.eu'
#         key_length=1024
#         dice.gpg_gen_interesting_keys(gpg, key_length, name_real, name_email,
#                 keyid_n_fingerprint_start_repetitively)

@ddt.ddt
class TApp(unittest.TestCase):

    @ddt.data(
        dice.MainCmd.document_config_options,
        dice.MainCmd.print_alias_help,
        dice.MainCmd.print_flag_help,
        dice.MainCmd.print_options,
        dice.MainCmd.print_subcommands,
        dice.MainCmd.print_examples,
        dice.MainCmd.print_help,
    )
    def test_app(self, meth):
        c = get_config()
        c.MainCmd.raise_config_file_errors = True
        cmd = dice.MainCmd(config=c)
        meth(cmd)

    def test_gen_conf(self):
        c = get_config()
        c.MainCmd.raise_config_file_errors = True
        cmd = dice.GenConfigCmd(config=c)
        with tempfile.TemporaryDirectory() as td:
            conf_fpath = osp.join(td, 'cc.py')
            cmd.run(conf_fpath)
            self.assertTrue(osp.isfile(conf_fpath),
                            (conf_fpath, os.listdir(osp.split(conf_fpath)[0])))
            stat = os.stat(conf_fpath)
            self.assertGreater(stat.st_size, 7000, stat)

