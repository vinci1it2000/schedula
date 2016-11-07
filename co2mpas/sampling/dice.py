#!/usr/b in/env python
#
# Copyright 2014-2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
#
"""
co2dice: prepare/sign/send/receive/validate/archive Type Approval sampling emails of *co2mpas*.

.. Warning::
    Do not run multiple instances!
"""

from collections import defaultdict, MutableMapping, OrderedDict, namedtuple
from email.mime.text import MIMEText
import imaplib
import io
import logging
import os
import re
import shutil
import smtplib
import tempfile
import textwrap
import types
from typing import Sequence, Text

from boltons.setutils import IndexedSet as iset
import gnupg # from python-gnupg
import keyring
from toolz import dicttoolz as dtz, itertoolz as itz

from co2mpas import __uri__  # @UnusedImport
from co2mpas.__main__ import init_logging
from co2mpas import (__version__, __updated__, __file_version__,   # @UnusedImport
                              __input_file_version__, __copyright__, __license__)  # @UnusedImport
from co2mpas.sampling import baseapp, CmdException
from co2mpas.sampling.baseapp import (APPNAME, Cmd, build_sub_cmds,
                                      chain_cmds)  # @UnusedImport
import pandalone.utils as pndlu
import functools as fnt
import itertools as itt
import os.path as osp
import pandas as pd  # SLOW!
import traitlets as trt
import traitlets.config as trtc


# TODO: move to pandalone
__title__   = APPNAME
__summary__ = __doc__.split('\n')[0]


log = logging.getLogger(__name__)

try:
    _mydir = osp.dirname(__file__)
except:
    _mydir = '.'

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


def _describe_gpg(gpg):
    gpg_path = gpg.gpgbinary
    if not osp.isabs(gpg_path):
        gpg_path = shutil.pndlu.which(gpg_path)

    ver = str(gpg.version)
    nprivkeys = len(gpg.list_keys(True))
    nallkeys = len(gpg.list_keys())
    return gpg_path, ver, nprivkeys, nallkeys


def collect_gpgs():
    inc_errors=1
    gpg_kws={}
    gpg_paths = iset(itt.chain.from_iterable(pndlu.where(prog) for prog in ('gpg2', 'gpg')))
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
    gpg2_path = pndlu.which(prog)
    self.assertIsNotNone(gpg2_path)
    gpg=gnupg.GPG(r'C:\Program Files (x86)\GNU\GnuPG\gpg2.exe')
    self.my_gpg_key
    self._cfg = read_config('co2mpas')


###################
##     Specs     ##
###################



class GpgSpec(trtc.SingletonConfigurable, baseapp.Spec):
    """Provider of GnuPG high-level methods."""

    exec_path = trt.Unicode(None, allow_none=True,
            help="""
            The path to GnuPG executable; if None, the first one in PATH variable is used: '{gpgexec}'.
            """.format(gpgexec=pndlu.convpath(pndlu.which('gpg')))).tag(config=True)

    home = trt.Unicode(None, allow_none=True,
            help="""
            The default home directory containing the keys; if None given and nor env-var GNUPGHOME exist,
            the executable decides (e.g. `~/.gpg` on POSIX, `%APPDATA%\Roaming\GnuPG` on Windows).
            """).tag(config=True)


class MailSpec(baseapp.Spec):
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


class MainCmd(Cmd):
    """The parent command."""

    name        = trt.Unicode(__title__)
    description = trt.Unicode("""
    co2dice: prepare/sign/send/receive/validate & archive Type Approval sampling emails for *co2mpas*.

    TIP:
      If you bump into blocking errors, please use the `co2dice project backup` command and
      send the generated archive-file back to "CO2MPAS-Team <co2mpas@jrc.ec.europa.eu>",
      for examination.
    NOTE:
      Do not run multiple instances!
    """)
    version     = __version__
    #examples = """TODO: Write cmd-line examples."""

    print_config = trt.Bool(False,
            help="""Enable it to print the configurations before launching any command."""
    ).tag(config=True)

    def __init__(self, **kwds):
        from co2mpas.sampling import project, report
        with self.hold_trait_notifications():
            dkwds = {
                'name': __title__,
                'description': __summary__,
                ##'default_subcmd': 'project', ## Confusing for the user.
                'subcommands': build_sub_cmds(project.ProjectCmd, report.ReportCmd, GenConfigCmd),
            }
            dkwds.update(kwds)
            super().__init__(**dkwds)

## INFO: Add al conf-classes here
class GenConfigCmd(Cmd):
    """
    Store config defaults into specified path(s); '{confpath}' assumed if none specified.

    - If a path resolves to a folder, the filename '{appname}_config.py' is appended.
    - It OVERWRITES any pre-existing configuration file(s)!

    SYNTAX
        co2dice gen-config [<config-path-1>] ...
    """


    ## Class-docstring CANNOT contain string-interpolations!
    description = trt.Unicode(__doc__.format(confpath=pndlu.convpath('~/.%s_config.py' % APPNAME),
                                 appname=APPNAME))

    examples = trt.Unicode("""
        Generate a config-file at your home folder:

            co2dice gen-config ~/my_conf

        Re-use this custom config-file:

            co2dice --config-files=~/my_conf  ...
        """)

    def run(self, *args):
        from co2mpas.sampling import project, report
        ## INFO: Add all conf-classes here
        pp = project.ProjectCmd
        self.classes = [
              pp, pp.CurrentCmd, pp.ListCmd, pp.AddCmd, pp.OpenCmd, pp.ExamineCmd, pp.BackupCmd,
              report.ReportCmd,
              GenConfigCmd,
              baseapp.Spec, project.ProjectsDB, report.Report, MainCmd,
        ]
        args = args or [None]
        for fpath in args:
            self.write_default_config(fpath)


def run_cmd(cmd: Cmd, argv: Sequence[Text]=None):
    """
    Executes a (possibly nested) command, and print its (possibly lazy) results to `stdout`.

    Remember to have logging setup properly before invoking this.

    :param cmd:
        Use :func:`make_app()`, or :func:`chain_cmds()` if you want to prepare
        a nested cmd instead.
    :param argv:
        If `None`, use :data:`sys.argv`; use ``[]`` to explicitely use no-args.
    :return:
        May yield, so check if a type:`GeneratorType`.
    """
    cmd.initialize(argv)
    res = cmd.start()
    if res is not None:
        if isinstance(res, types.GeneratorType):
            for i in res:
                print(i)
        elif isinstance(res, (tuple, list)):
            print(os.linesep.join(res))
        else:
            print(res)

def main(argv=None, log_level=None, **app_init_kwds):
    """
    :param argv:
        If `None`, use :data:`sys.argv`; use ``[]`` to explicitely use no-args.
    """
    init_logging(level=log_level)
    try:
        ##MainCmd.launch_instance(argv or None, **app_init_kwds) ## NO No, does not return `start()`!
        app = MainCmd.instance(**app_init_kwds)
        run_cmd(app, argv)
    except (CmdException, trt.TraitError) as ex:
        ## Suppress stack-trace for "expected" errors.
        log.debug('App exited due to: %s', ex, exc_info=1)
        exit(ex.args[0])
    except Exception as ex:
        ## Shell will see any exception x2, but we have to log it anyways,
        #  in case log has been redirected to a file.
        #
        log.error('Launch failed due to: %s', ex, exc_info=1)
        raise ex


if __name__ == '__main__':
    argv = None
    ## DEBUG AID ARGS, remember to delete them once developed.
    #argv = ''.split()
    argv = '--debug'.split()
    #argv = '--help'.split()
    argv = '--help-all'.split()
    #argv = 'gen-config'.split()
    #argv = 'gen-config --help-all'.split()
    #argv = 'gen-config help'.split()
    #argv = '--debug --log-level=0 --Mail.port=6 --Mail.user="ggg" abc def'.split()
    #argv = 'project --help-all'.split()
    #argv = '--debug'.split()
    #argv = 'project list --help-all'.split()
#     argv = 'project --Project.reset_settings=True'.split()
    #argv = 'project --reset-git-settings'.split()
    #argv = 'project infos --help-all'.split()
    #argv = 'project infos'.split()
    argv = 'project --help-all'.split()
    argv = 'project infos --as-json --verbose --debug'.split()
    argv = 'project infos --Project.verbose=2 --debug'.split()
#     argv = 'project list  --Project.reset_settings=True'.split()
    #argv = '--Project.reset_settings=True'.split()
    #argv = 'project list  --reset-git-settings'.split()
    #argv = 'project add one'.split()

    # Invoked from IDEs, so enable debug-logging.
    main(argv, log_level=logging.DEBUG)

    #from traitlets.config import trtc.get_config

    #c = trtc.get_config()
    #c.Application.log_level=0
    #c.Spec.log_level='ERROR'
    #run_cmd(chain_cmds([MainCmd, ProjectCmd, ProjectCmd.Add], argv=['project_foo']))
