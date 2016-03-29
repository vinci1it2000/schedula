#!/usr/bin/env python
#
# Copyright 2014-2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
#
## Sign and  send/receive sampling emails
# see https://pymotw.com/2/imaplib/ for IMAP example.
from email.mime.text import MIMEText
import logging
import smtplib
import imaplib
import itertools as itt
import re
from .__main__ import CmdException
import configparser
import os.path as osp
import io
from boltons.setutils import IndexedSet as iset
from toolz import dicttoolz
import inspect
import pbkdf2
import keyring
import base64


log = logging.getLogger(__name__)

_project = 'co2mpas'

_default_cfg = """
[dice]
    timestamping_address: post@stamper.itconsult.co.uk
    default_recipients: co2mpas@jrc.ec.europa.eu, EC-CO2-LDV-IMPLEMENTATION@ec.europa.eu
    other_recipients:
    sender:
    mail_server.user
    SMTP.ssl: on
    SMTP.host: %(mail_server.user)s
    SMTP.user:
    SMTP.kwds:
    IMAPv4.ssl: on
    IMAPv4.host: %(mail_server.user)s
    IMAPv4.user:
    IMAPv4.kwds:
    gpg.trusted_user_ids: CO2MPAS JRC-master <co2mpas@jrc.ec.europa.eu>
"""

_opts_to_remove_before_cfg_write = ['default_recipients', 'timestamping_address']
## TODO: Move to other file
def read_config(projname, override_fpaths=(), default_fpaths=()):
    cfg_fpaths = list(override_fpaths) + [osp.expanduser(frmt % projname)
            for frmt in ('%s.cfg', '~/.%s.cfg')] + list(default_fpaths)
    config = configparser.ConfigParser()
    cfg = config.read(cfg_fpaths, encoding='utf-8')
    return cfg

def store_config(cfg, projname):
    for opt in _opts_to_remove_before_cfg_write:
        cfg.remove_option('dice', opt)
    fpath = osp.expanduser('~/.%s.cfg' % projname)
    with io.open(fpath, 'wt', encoding='utf-8') as fd:
        cfg.write(fd)


def _get_secret_service(service, master_password, project=_project):
    return pbkdf2.crypt(service + master_password, base64.b64encode(project))

def set_pswd(secret_service, user, pswd):
    kr=keyring.get_keyring()
    kr.set_password(secret_service, user, pswd)

def get_pswd(secret_service, user, pswd):
    """Uses Microsoft's DPPAPI to store the actual passwords."""
    kr=keyring.get_keyring()
    kr.set_password(secret_service, user, pswd)

def which(program):
    ## From: http://stackoverflow.com/a/377028/548792
    import os
    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            path = path.strip('"')
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file

    return None


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
        """GMAIL-2FAuth: imaplib.error: b'[ALERT] Application-specific password required: https://support.google.com/accounts/answer/185833 (Failure)'"""
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

