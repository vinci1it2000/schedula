#!/usr/b in/env python
#
# Copyright 2014-2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
#
"""co2dice: prepare/sign/send/receive/validate/archive Type Approval sampling emails of *co2mpas*."""

import base64
from collections import defaultdict, MutableMapping, OrderedDict
import locale
import copy
import git # from *gitpython* distribution
import errno
import configparser
from email.mime.text import MIMEText
import imaplib
import json
import inspect
import subprocess
import pprint
from pandalone.pandata import resolve_path
from pandalone import utils as pndl_utils
import io
import logging
import os
import re
import sys
import tempfile
import shutil
import smtplib

from boltons.setutils import IndexedSet as iset, IndexedSet
import gnupg
import keyring
import textwrap
from traitlets.config import ConfigFileNotFound
from toolz import dicttoolz
from toolz import itertoolz as itz
import traitlets as trt
from traitlets.config import Application, Configurable, LoggingConfigurable, get_config, catch_config_error

import functools as ft
import pandas as pd
import itertools as itt
import os.path as osp

from co2mpas.__main__ import CmdException, init_logging
from co2mpas import __uri__  # @UnusedImport
from co2mpas._version import (__version__, __updated__, __file_version__,   # @UnusedImport
                              __input_file_version__, __copyright__, __license__)  # @UnusedImport
__title__ = 'co2dice'
__summary__   = __doc__.split('\n')[0]


log = logging.getLogger(__name__)
# from traitlets import log as tlog
# log = tlog.get_logger()

try:
    _mydir = osp.dirname(__file__)
except:
    mydir = '.'
CONF_VAR_NAME = '%s_CONFIG_FILE' % __title__.upper()

_default_cfg = textwrap.dedent("""
        ---
        dice:
            timestamping_address: post@stamper.itconsult.co.uk
            default_recipients: [co2mpas@jrc.ec.europa.eu,EC-CO2-LDV-IMPLEMENTATION@ec.europa.eu]
            #other_recipients:
            #sender:
        gpg:
            trusted_user_ids: [CO2MPAS JRC-master <co2mpas@jrc.ec.europa.eu>]
        """)

_opts_to_remove_before_cfg_write = ['default_recipients', 'timestamping_address']

def get_home_dir():
    """Get the real path of the home directory"""
    homedir = osp.expanduser('~')
    # Next line will make things work even when /home/ is a symlink to
    # /usr/home as it is on FreeBSD, for example
    homedir = osp.realpath(homedir)
    return homedir


def app_config_dir():
    """Get the config directory for this platform and user.

    Returns CO2DICE_CONFIG_DIR if defined, else ~/.co2dice
    """

    env = os.environ
    home_dir = get_home_dir()

    if env.get('CO2DICE_CONFIG_DIR'):
        return env['CO2DICE_CONFIG_DIR']

    return osp.abspath(osp.join(home_dir, '.co2dice'))

def store_secret(master_pswd, key, secret):
    """
    Uses Microsoft's DPPAPI to store sensitive infos (e.g. passwords).

    :param str master_pswd:     master-password given by the user
    """
    kr=keyring.get_keyring()
    kr.set_password('%s.%s' %(__title__, master_pswd), key, secret)

def retrieve_secret(master_pswd, key):
    """
    Uses Microsoft's DPPAPI to store sensitive infos (e.g. passwords).

    :param str master_pswd:     master-password given by the user
    """
    kr=keyring.get_keyring()
    return kr.get_password('%s.%s' %(__title__, master_pswd), key)

def py_where(program, path=None):
    ## From: http://stackoverflow.com/a/377028/548792
    winprog_exts = ('.bat', 'com', '.exe')
    def is_exec(fpath):
        return osp.isfile(fpath) and os.access(fpath, os.X_OK) and (
                os.name != 'nt' or fpath.lower()[-4:] in winprog_exts)

    progs = []
    if not path:
        path = os.environ["PATH"]
    for folder in path.split(ospsep):
        folder = folder.strip('"')
        if folder:
            exe_path = osp.join(folder, program)
            for f in [exe_path] + ['%s%s'%(exe_path, e) for e in winprog_exts]:
                if is_exec(f):
                    progs.append(f)
    return progs


def where(program):
    try:
        res = subprocess.check_output('where "%s"' % program,
                universal_newlines=True)
        return res and [s.strip()
                       for s in res.split('\n') if s.strip()]
    except subprocess.CalledProcessError:
        return []
    except:
        return py_where(program)


def which(program):
    res = where(program)
    return res[0] if res else None


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


#gpg_avail = collect_gpgs()

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

# see https://pymotw.com/2/imaplib/ for IMAP example.
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

def git_read_bytes(obj):
    bytes_sink = io.BytesIO()
    obj.stream_data(bytes_sink)
    return bytes_sink.getvalue()


_PGP_SIGNATURE  = b'-----BEGIN PGP SIGNATURE-----'
_PGP_MESSAGE    = b'-----BEGIN PGP MESSAGE-----'

def split_detached_signed(tag: bytes) -> (bytes, bytes):
    """
    Look at GPG signed content (e.g. the message of a signed tag object),
    whose payload is followed by a detached signature on it, and
    split these two; do nothing if there is no signature following.

    :param tag:
            As fetched from ``git cat-file tag v1.2.1``.
    :return:
            A 2-tuple(sig, msg), None if no sig found.
    """
    nl = b'\n'
    lines = tag.split(nl)
    for i, l in enumerate(lines):
        if l.startswith(_PGP_SIGNATURE) or l.startswith(_PGP_MESSAGE):
            return nl.join(lines[i:]), nl.join(lines[:i]) + nl


class DiceGPG(gnupg.GPG):
    def __init__(self, *args, **kws):
        super().__init__(*args, **kws)

    def verify_detached_armor(self, sig: str, data: str):
    #def verify_file(self, file, data_filename=None):
        """Verify `sig` on the `data`."""
        logger = gnupg.logger
        #with tempfile.NamedTemporaryFile(mode='wt+',
        #                encoding='latin-1') as sig_fp:
        #sig_fp.write(sig)
        #sig_fp.flush(); sig_fp.seek(0) ## paranoid seek(), Windows at least)
        #sig_fn = sig_fp.name
        sig_fn = osp.join(tempfile.gettempdir(), 'sig.sig')
        logger.debug('Wrote sig to temp file: %r', sig_fn)

        args = ['--verify', gnupg.no_quote(sig_fn), '-']
        result = self.result_map['verify'](self)
        data_stream = io.BytesIO(data.encode(self.encoding))
        self._handle_io(args, data_stream, result, binary=True)
        return result


    def verify_detached(self, sig: bytes, msg: bytes):
        with tempfile.NamedTemporaryFile('wb+', prefix='co2dice_') as sig_fp:
            with tempfile.NamedTemporaryFile('wb+', prefix='co2dice_') as msg_fp:
                sig_fp.write(sig)
                sig_fp.flush()
                sig_fp.seek(0) ## paranoid seek(), Windows at least)

                msg_fp.write(msg)
                msg_fp.flush();
                msg_fp.seek(0)

                sig_fn = gnupg.no_quote(sig_fp.name)
                msg_fn = gnupg.no_quote(msg_fp.name)
                args = ['--verify', sig_fn, msg_fn]
                result = self.result_map['verify'](self)
                p = self._open_subprocess(args)
                self._collect_output(p, result, stdin=p.stdin)
                return result

def __GPG__init__(self, my_gpg_key):
    gpg_prog = 'gpg2.exe'
    gpg2_path = which(prog)
    self.assertIsNotNone(gpg2_path)
    gpg=gnupg.GPG(r'C:\Program Files (x86)\GNU\GnuPG\gpg2.exe')
    self.my_gpg_key
    self._cfg = read_config('co2mpas')

#####
## TODO: Move to pandalone
_is_dir_regex = re.compile(r'[^/\\][/\\]$')

def normpath(path):
    """Like :func:`osp.normpath()`, but preserving last slash."""
    p = osp.normpath(path)
    if _is_dir_regex.search(path) and p[-1] != os.sep:
        p = p + osp.sep
    return p

def abspath(path):
    """Like :func:`osp.abspath()`, but preserving last slash."""
    p = osp.abspath(path)
    if _is_dir_regex.search(path) and p[-1] != os.sep:
        p = p + osp.sep
    return p

## TODO: Move path-util to pandalone.
def convpath(fpath, abs_path=True, exp_user=True, exp_vars=True):
    """Without any flags, just pass through :func:`osp.normpath`. """
    if exp_user:
        fpath = osp.expanduser(fpath)
    if exp_vars:
        ## Mask UNC '\\server\share$\path` from expansion.
        fpath = fpath.replace('$\\', '_UNC_PATH_HERE_')
        fpath = osp.expandvars(fpath)
        fpath = fpath.replace('_UNC_PATH_HERE_', '$\\')
    fpath = abspath(fpath) if abs_path else normpath(fpath)
    return fpath

def ensure_dir_exists(path, mode=0o755):
    """ensure that a directory exists

    If it doesn't exist, try to create it and protect against a race condition
    if another process is doing the same.

    The default permissions are 755, which differ from os.makedirs default of 777.
    """
    if not os.path.exists(path):
        try:
            os.makedirs(path, mode=mode)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise
    elif not os.path.isdir(path):
        raise IOError("%r exists but is not a directory" % path)

_camel_to_snake_regex = re.compile('(?<=[a-z0-9])([A-Z]+)') #('(?!^)([A-Z]+)')
def camel_to_snake_case(s):
    """Trurns `'CO2DiceApp' --> 'co2_dice_app'. """
    return _camel_to_snake_regex.sub(r'_\1', s).lower()

def camel_to_cmd_name(s):
    """Trurns `'CO2DiceApp' --> 'co2-dice-app'. """
    return camel_to_snake_case(s).replace('_', '-')

#####

###################
##     Specs     ##
###################

def default_config_fname():
    """The config-file's basename (no path or extension) to search when not explicitly specified."""
    return '%s_config' % __title__

def default_config_dir():
    """The folder of to user's config-file."""
    return convpath('~/.%s' % __title__)

def default_config_fpath():
    """The full path of to user's config-file, without extension."""
    return osp.join(default_config_dir(), default_config_fname())



class Spec(LoggingConfigurable):
    """Common properties for all configurables."""

    user_name = trt.Unicode('<Name Surname>',
            help="""The Name & Surname of the default user invoking the app.  Must not be empty!"""
            ).tag(config=True)
    user_email = trt.Unicode('<email-address>',
            help="""The email address of the default user invoking the app. Must not be empty!"""
            ).tag(config=True)

    @trt.default('log')
    def _log(self):
        return logging.getLogger(self.name)

    @trt.validate('user_name', 'user_email')
    def _valid_user(self, proposal):
        value = proposal['value']
        if not value:
            raise trt.TraitError('%s.%s must not be empty!'
                                 % (proposal['owner'].name, proposal['trait'].name))
        return value


class GitSpec(Spec):
    """A git-based repository storing the TA projects (containing signed-files and sampling-resonses).

    Git Command Debugging and Customization:

    - :envvar:`GIT_PYTHON_TRACE`: If set to non-0,
      all executed git commands will be shown as they happen
      If set to full, the executed git command _and_ its entire output on stdout and stderr
      will be shown as they happen

      NOTE: All logging is outputted using a Python logger, so make sure your program is configured
      to show INFO-level messages. If this is not the case, try adding the following to your program:

    - :envvar:`GIT_PYTHON_GIT_EXECUTABLE`: If set, it should contain the full path to the git executable, e.g.
      ``c:\Program Files (x86)\Git\bin\git.exe on windows`` or ``/usr/bin/git`` on linux.
    """

    repo_path = trt.Unicode('repo',
            help="""
            The path to the Git repository to store TA files (signed and exchanged).
            If relative, it joined against default config-dir: '{confdir}'
            """.format(confdir=default_config_dir())).tag(config=True)
    reset_settings = trt.Bool(False,
            help="""
            Set to `True`, not to re-write default git's config-settings on app start up.
            Git settings include user-name and email address.
            """).tag(config=True)

    def __init__(self, **kwds):
        repo_path = self.repo_path
        if not osp.isabs(repo_path):
            repo_path = osp.join(default_config_dir(), repo_path)
        repo_path = convpath(repo_path)
        if osp.isdir(repo_path):
            log.info('Opening git-repo %r...', repo_path)
            self.repo = git.Repo(repo_path)
            if self.reset_settings:
                self._write_repo_configs()
        else:
            log.info('Creating new git-repo %r...', repo_path)
            ensure_dir_exists(repo_path)
            self.repo = git.Repo.init(repo_path)
            self._write_repo_configs()


    def _write_repo_configs(self):
        with self.repo.config_writer() as cw:
            cw.set_value('core', 'filemode', False)
            cw.set_value('core', 'ignorecase', False)
            cw.set_value('user', 'email', self.user_email)
            cw.set_value('user', 'name', self.user_name)


class GpgSpec(Spec):
    """Provider of GnuPG high-level methods."""

    exec_path = trt.Unicode(None, allow_none=True,
            help="""
            The path to GnuPG executable; if None, the first one in PATH variable is used: '{gpgexec}'.
            """.format(gpgexec=convpath(which('gpg')))).tag(config=True)

    home = trt.Unicode(None, allow_none=True,
            help="""
            The default home directory containing the keys; if None given and nor env-var GNUPGHOME exist,
            the executable decides (e.g. `~/.gpg` on POSIX, `%APPDATA%\Roaming\GnuPG` on Windows).
            """).tag(config=True)


class MailSpec(Spec):
    """Common parameters and methods for both SMTP(sending emails) & IMAP(receiving emails)."""

    host = trt.Unicode('',
            help="""The SMTP/IMAP server, e.g. 'smtp.gmail.com'."""
            ).tag(config=True)

    port = trt.Int(587,
            help="""The SMTP/IMAP server's port, usually 587/465 for SSL, 25 otherwise."""
            ).tag(config=True)

    ssl = trt.Bool(True,
            help="""Whether to talk TLS/SSL to the SMTP/IMAP server; configure `port` separately!"""
            ).tag(config=True)

    user = trt.Unicode(None, allow_none=True,
            help="""The user to authenticate with the SMTP/IMAP server."""
            ).tag(config=True)


class SmtpSpec(MailSpec):
    """Parameters and methods for SMTP(sending emails)."""

    login = trt.CaselessStrEnum('login simple'.split(), default_value=None, allow_none=True,
            help="""Which SMTP mechanism to use to authenticate: [ login | simple | <None> ]. """
             ).tag(config=True)

    kwds = trt.Dict(
            help="""Any key-value pairs passed to the SMTP/IMAP mail-client libraries."""
            ).tag(config=True)


class ImapSpec(MailSpec):
    """Parameters and methods for IMAP(receiving emails)."""


###################
##    Commands   ##
###################

#: INFO: Add HERE all CONFs.
_conf_classes = [GitSpec, GpgSpec, MailSpec, SmtpSpec, ImapSpec]


def build_sub_cmds(subapp_classes):
    return OrderedDict((camel_to_cmd_name(sa.__name__), (sa, sa.__doc__))
            for sa in subapp_classes)

_base_aliases = {
    'log-level' :       'Application.log_level',
    'config-files' :    'Cmd.config_files',
}

_base_flags = {
    'debug': ({'Application' : {'log_level' : logging.DEBUG}},
            "Set log level to logging.DEBUG (maximize logging output)."),
}

class Cmd(Spec, Application):
    """Common machinery for all (sub-)commands. """
    ## INFO: Do not use it directly; inherit it.

    @trt.default('name')
    def _name(self):
        return camel_to_snake_case(self.__class__.__name__)

    description = '' ## So that dynamic-default rule, below, runs on subclasses.

    @trt.default('description')
    def _description(self):
        return self.__class__.__doc__ or '<no description>'

    config_files = trt.Unicode(None, allow_none=True,
            help="""
            Absolute/relative path(s) to config files to OVERRIDE default configs.
            Multiple paths are separated by '{pathsep}' in descending order.
            Any extensions are ignored, and '.json' or '.py' are searched (in this order).
            If the path specified resolves to a folder, the filename `{appname}_config.[json | py]` is appended;
            Any command-line values take precendance over the `{confvar}` envvar.
            Use `gen-config` sub-command to produce a skeleton of the config-file.
            """.format(appname=__title__, confvar=CONF_VAR_NAME, pathsep=osp.pathsep)
            ).tag(config=True)

    @property
    def user_config_fpaths(self):
        fpaths = []
        config_files = os.environ.get(CONF_VAR_NAME, self.config_files)
        if config_files:
            def _procfpath(p):
                p = convpath(p)
                if osp.isdir(p):
                    p = osp.join(p, default_config_fname())
                else:
                    p = osp.splitext(p)[0]
                return p

            fpaths = config_files.split(osp.pathsep)
            fpaths = [_procfpath(p) for p in fpaths]

        return fpaths

    def load_config_files(self):
        """Load default user-specified overrides config files.


        Config-files in descending orders:

        - user-overrides:
          - :envvar:`<APPNAME>_CONFIG_FILE`, or if not set,
          - :attr:`config_file`;

        - default config-files:
            - ~/.<appname>/<appname>_config.{json,py} and
            - <this-file's-folder>/<appname>_config.{json,py}.
        """
        # Load "standard" configs,
        #      path-list in descending priority order.
        #
        paths = list(IndexedSet([default_config_dir(), _mydir]))
        self.load_config_file(default_config_fname(), path=paths)

        # Load "user" configs.
        #
        user_conf_fpaths = self.user_config_fpaths
        for fp in user_conf_fpaths[::-1]:
            cdir, cfname = osp.split(fp)
            self.load_config_file(cfname, path=cdir)

    def write_default_config(self, config_file=None):
        if not config_file:
            config_file = '%s.py' % default_config_fpath()
        else:
            config_file = convpath(config_file)
            if osp.isdir(config_file):
                config_file = osp.join(config_file, default_config_fname())
            config_file = pndl_utils.ensure_file_ext(config_file, '.py')

        op = 'Over-writting' if osp.isfile(config_file) else 'Writting'
        log.info('%s config-file %r...', op, config_file)
        ensure_dir_exists(os.path.dirname(config_file), 0o700)
        config_text = self.generate_config_file();
        with io.open(config_file, mode='wt') as fp:
            fp.write(config_text)

    def print_subcommands(self):
        """Print the subcommand part of the help."""
        from ipython_genutils.text import indent, wrap_paragraphs, dedent

        if not self.subcommands:
            return

        lines = ["Subcommands"]
        lines.append('-'*len(lines[0]))
        lines.append('')
        for p in wrap_paragraphs(self.subcommand_description.format(
                    app=self.name)):
            lines.append(p)
            lines.append('')
        for subc, (cls, hlp) in self.subcommands.items():
            if self.default_subcmd == subc:
                subc = '%s (default)' % subc
            lines.append(subc)

            if hlp:
                lines.append(indent(dedent(hlp.strip())))
        lines.append('')
        print(os.linesep.join(lines))

    def __init__(self, **kwds):
        ## Disable logging-format configs, because it is
        #    miss-applied on loger's handlers, which might be null.
        Cmd.log_format.tag(config=False)
        Cmd.log_datefmt.tag(config=False)

        subcmds_list = [cmd for cmd, _ in kwds.get('subcommands', {}).values()]
        super().__init__(
            classes=subcmds_list + _conf_classes,
            aliases = _base_aliases.copy(),
            flags = _base_flags.copy(),
            **kwds)

    @catch_config_error
    def initialize_subcommand(self, subc, argv=None):
        """Copied from parent to workaround: https://github.com/ipython/traitlets/issues/286"""
        subapp, _ = self.subcommands.get(subc)
        self.__class__.clear_instance()
        self.subapp = subapp.instance(parent=self)
        self.subapp.initialize(argv)

    def _is_dispatching(self):
        """True if dispatching to another command, or running ourselves."""
        return bool(self.subapp)

    @catch_config_error
    def initialize(self, argv=None):
        ## Invoked after __init__() by Cmd.launch_instance() to read configs.
        #  It parses cl-args before file-configs, to detect sub-commands
        #  and update any :attr:`config_file`,
        #  load file-configs, and then re-apply cmd-line configs as overrides
        #  (trick copied from `jupyter-core`).
        self.parse_command_line(argv)
        if self._is_dispatching():
            return # Avoid contaminations with user if generating-config.
        cl_config = copy.deepcopy(self.config)
        self.load_config_files()
        self.update_config(cl_config)

    default_subcmd = trt.Unicode(None, allow_none=True,
                                 help="The name of the sub-command to use if unspecified.")

    def start(self):
        if self.subapp is not None:
            return self.subapp.start()
        elif self.default_subcmd:
            self.initialize_subcommand(self.default_subcmd, self.argv)
            return self.subapp.start()
        else:
            raise CmdException('Specify one of the sub-commands: %s'
                               % ', '.join(self.subcommands.keys()))


class GenConfig(Cmd):
    """
    A `co2dice` sub-cmd that stores config defaults into specified path(s).
    Any cmd-arguments are taken as the paths to generate into;
    '{confpath}' assumed if no args given.
    If a path resolves to a folder, the filename `{appname}_config.py` is appended.

    Note: It OVERWRITES any pre-existing configuration file(s)!
    """
    ## Class-docstring CANNOT contain string-interpolations!
    #.format(confpath=convpath('~/.%s_config.py' % __title__), appname=__title__)

    examples="""
    Generate a config-file at your home folder:

        co2dice gen-config ~/my_conf

    Re-use this custom config-file:

        co2dice --config-files=~/my_conf  ...
    """

    def start(self):
        extra_args = self.extra_args or [None]
        for fpath in extra_args:
            self.parent.write_default_config(fpath)


class Project(Cmd):
    """
    The `co2dice` sub-cmd to administer the storage holding the TA projects.
    """

    examples = """
    To get the list with the status of all existing projects, try:

        co2dice project list
    """


    class New(Cmd):
        """Create a new project.  This action is eeded before anything else"""
        def start(self):
            print('Creating...')
            print(self.name, self.description)

    class Open(Cmd):
        """Open an existing project."""
        def start(self):
            print('OPEN...')

    class List(Cmd):
        """List all projects."""
        #gs = GitSpec(parent=self)
        def start(self):
            print('LLIS"')

    default_subcmd = 'list'

    def __init__(self, **kwds):
        subcommands = [Project.New, Project.Open, Project.List]
        super().__init__(
                subcommands=build_sub_cmds(subcommands),
                **kwds)
        self.aliases.update({
            'reset-git-settings' :    'GitSpec.reset_settings',
        })



class Main(Cmd):
    """The parent command."""

    name        = __title__
    description = __summary__
    version     = __version__
    #examples = """TODO: Write cmd-line examples."""

    def __init__(self, **kwds):
        ## INFO: Add HERE all top-level sub-CMDs.
        super().__init__(subcommands=build_sub_cmds([GenConfig, Project]))


def main(*argv, **app_init_kwds):
    app_init_kwds['raise_config_file_errors'] = True
    #argv = ''.split()
    #argv = '--help'.split()
    #argv = '--help-all'.split()
    #argv = 'gen-config'.split()
    #argv = 'gen-config --help-all'.split()
    #argv = 'gen-config help'.split()
    #argv = '--debug --log-level=0 --Mail.port=6 --Mail.user="ggg" abc def'.split()
    #argv = 'project --help-all'.split()
    argv = 'project help'.split()
    #argv = '--debug'.split()
    #argv = 'project new help'.split()
    #argv = 'project list'.split()
    #argv = 'project'.split()
    Main.launch_instance(argv or sys.argv, **app_init_kwds)

if __name__ == '__main__':
    try:
        init_logging(verbose=True)
        main()
    except CmdException as ex:
        log.info('%r', ex)
        exit(ex.args[0])
    except Exception as ex:
        log.error('%r', ex)
        raise
