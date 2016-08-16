#!/usr/bin/env python
#
# Copyright 2014-2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
#
"""Sign and  send/receive sampling emails"""
# see https://pymotw.com/2/imaplib/ for IMAP example.

import base64
from collections import defaultdict, MutableMapping
import configparser
from email.mime.text import MIMEText
import imaplib
import inspect
import pprint
import io
import logging
import os
import re
import re
import shutil
import smtplib

from boltons.setutils import IndexedSet as iset, IndexedSet
import gnupg
import hiyapyco
import keyring
from toolz import dicttoolz
from toolz import itertoolz as itz

import functools as ft
import pandas as pd
import itertools as itt
import os.path as osp

from ..__main__ import CmdException


log = logging.getLogger(__name__)

_project = 'co2mpas'

_default_cfg = """
[dice]
    timestamping_address: post@stamper.itconsult.co.uk
    default_recipients: co2mpas@jrc.ec.europa.eu, EC-CO2-LDV-IMPLEMENTATION@ec.europa.eu
    other_recipients:
    sender:
    SMTP.ssl: on
    SMTP.host:
    SMTP.user:
    SMTP.kwds:
    IMAPv4.user:
    IMAPv4.ssl: on
    IMAPv4.host:
    IMAPv4.kwds:
    gpg.trusted_user_ids: CO2MPAS JRC-master <co2mpas@jrc.ec.europa.eu>
"""

_opts_to_remove_before_cfg_write = ['default_recipients', 'timestamping_address']
## TODO: Move to other file
def read_config_ini(projname, override_fpaths=(), default_fpaths=()):
    cfg_fpaths = list(override_fpaths) + [
                                          osp.expanduser(frmt % projname)
                                          for frmt in ('%s.cfg', '~/.%s.cfg')
                                         ] + list(default_fpaths)
    config = configparser.ConfigParser()
    cfg = config.read(cfg_fpaths, encoding='utf-8')
    return cfg

def splitnest(dic, sep=r'\.', factory=None):
    """
    Splits keys by separator and *nests* them in a new mapping (from factory).

    :param dic:     The mapping to split and nest its keys.
    :param str sep: the split-separator regex
    :param factory: The factory-function for the nested mappings.
                    By default `None`, it uses the type of the input `dic`.
                    Note that when `None`, it might fail if the constructor
                    of `dic` type expects specific args, such as `defaultdict`.

    >>> RES == {'a': {'b': {'c': {'d': 44}}, 'c': 2}, 'b': 3}
    >>> dice.splitnest({'a.b': 1, 'a-c': 2, 'b': 3, 'a.b.c,d':44}, '[.,-]') == RES
    True

    >>> dice.splitnest({'abc': 1})
    {'abc': 1}

    >>> dice.splitnest({})
    {}
    """
    def set_subkeys(d, subkeys, v):
        """
        >>> d = {}
        >>> set_subkeys(d, ['a','b',], 3)
        >>> d
        {'a': {'b': 3}}

        >>> set_subkeys(d, ['a','b',], 4)
        >>> d
        {'a': {'b': 4}}

        >>> set_subkeys(d, ['a','b', 'c'], 5)
        >>> d
        {'a': {'b': {'c' : 5}}

        >>> set_subkeys(d, ['a'], 0)
        >>> d
        {'a': 0}
        """
        k, subkeys = subkeys[0], subkeys[1:]
        if subkeys:
            try:
                set_subkeys(d[k], subkeys, v)
            except:
                d[k] = factory()
                set_subkeys(d[k], subkeys, v)
        else:
            d[k] = v

    sep = re.compile(sep)
    if factory:
        ndic = factory()
    else:
        factory = type(dic)
        ndic = factory()
    for k, v in dic.items():
        subkeys = [sk for sk in sep.split(k) if sk]
        if subkeys:
            set_subkeys(ndic, subkeys, v)
    return ndic


def store_config(cfg, projname):
    for opt in _opts_to_remove_before_cfg_write:
        cfg.remove_option('dice', opt)
    fpath = osp.expanduser('~/.%s.cfg' % projname)
    with io.open(fpath, 'wt', encoding='utf-8') as fd:
        cfg.write(fd)

def store_secret(master_pswd, key, secret):
    """
    Uses Microsoft's DPPAPI to store the actual passwords.

    :param str master_pswd:     master-password given by the user
    """
    kr=keyring.get_keyring()
    kr.set_password('%s.%s' %(_project, master_pswd), key, secret)

def retrieve_secret(master_pswd, key):
    """
    Uses Microsoft's DPPAPI to store the actual passwords.

    :param str master_pswd:     master-password given by the user
    """
    kr=keyring.get_keyring()
    return kr.get_password('%s.%s' %(_project, master_pswd), key)

def where(program, path=None):
    ## From: http://stackoverflow.com/a/377028/548792
    winprog_exts = ('.bat', 'com', '.exe')
    def is_exec(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK) and (
                os.name != 'nt' or fpath.lower()[-4:] in winprog_exts)

    progs = []
    if not path:
        path = os.environ["PATH"]
    for folder in path.split(os.pathsep):
        folder = folder.strip('"')
        if folder:
            exe_path = os.path.join(folder, program)
            for f in [exe_path] + ['%s%s'%(exe_path, e) for e in winprog_exts]:
                if is_exec(f):
                    progs.append(f)

    return progs

def which(program):
    progs = where(program)
    return progs and progs[0]

def _describe_gpg(gpg):
    gpg_path = gpg.gpgbinary
    if not osp.isabs(gpg_path):
        gpg_path = shutil.which(gpg_path)

    ver = str(gpg.version)
    nprivkeys = len(gpg.list_keys(True))
    nallkeys = len(gpg.list_keys())
    return gpg_path, ver, nprivkeys, nallkeys


def collect_gpgs():
    inc_errors=1
    gpg_kws={}
    gpg_paths = IndexedSet(itt.chain.from_iterable(where(prog) for prog in ('gpg2', 'gpg')))
    gnupghome = osp.expanduser('~/.gnupg')
    gpg_avail = []
    for gpg_path in gpg_paths:
        try:
            gpg = gnupg.GPG(gpgbinary=gpg_path, **gpg_kws)
            row = _describe_gpg(gpg)
        except Exception as ex:
            #raise
            if inc_errors:
                row = (gpg_path, '%s: %s' % (type(ex).__name__, str(ex)), None, None)
            else:
                continue
        gpg_avail.append(row)

    cols= ['GnuPG path', 'Version', '#PRIV', '#TOTAL']
    gpg_avail = pd.DataFrame(gpg_avail, columns=cols)
    return gpg_avail


gpg_avail = collect_gpgs()

def gpg_del_gened_key(gpg, fingerprint):
    log.debug('Deleting secret+pub: %s', fingerprint)
    d = gpg.delete_keys(fingerprint, secret=1)
    assert (d.status, d.stderr) == ('ok', ''), (
            "Failed DELETING pgp-secret: %s" % d.stderr)
    d=gpg.delete_keys(fingerprint)
    assert (d.status, d.stderr) == ('ok', ''), (
            "Failed DELETING pgp-secret: %s" % d.stderr)


def gpg_genkey(name_email, name_real, name_comment=None, key_type='RSA', key_length=2048, **kwds):
    """See https://www.gnupg.org/documentation/manuals/gnupg/Unattended-GPG-key-generation.html#Unattended-GPG-key-generation"""
    args = locals().copy()
    args.pop('kwds')
    return gpg.gen_key_input(**args)

def _has_repeatitive_prefix(word, limit, char=None):
    c = word[0]
    if not char or c == char:
        for i  in range(1, limit):
            if word[i] != c:
                break
        else:
            return True


def gpg_gen_interesting_keys(gpg, name_real, name_email, key_length,
        predicate, nkeys=1, runs=0):
    keys = []
    for i in itt.count(1):
        del_key = True
        key = gpg.gen_key(gpg.gen_key_input(key_length=key_length,
                name_real=name_real, name_email=name_email))
        try:
            log.debug('Created-%i: %s', i, key.fingerprint)
            if predicate(key.fingerprint):
                del_key = False
                keys.append(key.fingerprint)
                keyid = key.fingerprint[24:]
                log.info('FOUND-%i: %s-->%s', i, keyid, key.fingerprint)
                nkeys -= 1
                if nkeys == 0:
                    break
        finally:
            if del_key:
                gpg_del_gened_key(gpg, key.fingerprint)
    return keys


def _log_into_server(login_cb, login_cmd, prompt):
    """
    Connects a credential-source(`login_db`) to a consumer(`login_cmd`).

    :param login_cb:
            An object with 2 methods::

                ask_user_pswd(prompt) --> (user, pswd)  ## or `None` to abort.
                report_failure(obj)
    :param login_cmd:
            A function like::

                login_cmd(user, pswd) --> xyz  ## `xyz` might be the server.
    """
    for login_data in iter(lambda: login_cb.ask_user_pswd('%s? ' % prompt), None):
        user, pswd = login_data
        try:
            return login_cmd(user, pswd)
        except smtplib.SMTPAuthenticationError as ex:
            login_cb.report_failure('%r' % ex)
    else:
        raise CmdException("User abort logging into %r email-server." % prompt)


def send_timestamped_email(msg, sender, recipients, host,
        login_cb=None, ssl=False, **srv_kwds):
    x_recs = '\n'.join('X-Stamper-To: %s' % rec for rec in recipients)
    msg = "\n\n%s\n%s" % (x_recs, msg)

    mail = MIMEText(msg)
    mail['Subject'] = '[CO2MPAS-dice] test'
    mail['From'] = sender
    mail['To'] = ', '.join([_timestamping_address, sender])
    with (smtplib.SMTP_SSL(host, **srv_kwds)
            if ssl else smtplib.SMTP(host, **srv_kwds)) as srv:
        if login_cb:
            login_cmd = lambda user, pswd: srv.login(user, pswd)
            prompt = 'SMTP(%r)' % host
            _log_into_server(login_cb, login_cmd, prompt)

        srv.send_message(mail)
    return mail


_list_response_regex = re.compile(r'\((?P<flags>.*?)\) "(?P<delimiter>.*)" (?P<name>.*)')


def _parse_list_response(line):
    flags, delimiter, mailbox_name = _list_response_regex.match(line).groups()
    mailbox_name = mailbox_name.strip('"')
    return (flags, delimiter, mailbox_name)


def receive_timestamped_email(host, login_cb, ssl=False, **srv_kwds):
    prompt = 'IMAP(%r)' % host

    def login_cmd(user, pswd):
        srv = (imaplib.IMAP4_SSL(host, **srv_kwds)
                if ssl else imaplib.IMAP4(host, **srv_kwds))
        repl = srv.login(user, pswd)
        """GMAIL-2FAuth: imaplib.error: b'[ALERT] Application-specific password required:
        https://support.google.com/accounts/answer/185833 (Failure)'"""
        log.debug("Sent %s-user/pswd, server replied: %s", prompt, repl)
        return srv

    srv = _log_into_server(login_cb, login_cmd, prompt)
    try:
        resp = srv.list()
        print(resp[0])
        return [srv.retr(i+1) for i, msg_id in zip(range(10), resp[1])]
    finally:
        resp = srv.logout()
        if resp:
            log.warning('While closing %s srv responded: %s', prompt, resp)


class Signer(object):

    def __init__(self, my_gpg_key):
        gpg_prog = 'gpg2.exe'
        gpg2_path = which(prog)
        self.assertIsNotNone(gpg2_path)
        gpg=gnupg.GPG(r'C:\Program Files (x86)\GNU\GnuPG\gpg2.exe')
        self.my_gpg_key
        self._cfg = read_config('co2mpas')

