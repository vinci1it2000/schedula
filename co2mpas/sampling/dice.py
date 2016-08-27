#!/usr/b in/env python
#
# Copyright 2014-2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
#
"""co2dice: prepare/sign/send/receive/validate/archive Type Approval sampling emails of *co2mpas*."""

from collections import defaultdict, MutableMapping, OrderedDict, namedtuple
import git # from *gitpython* distribution
import types
from datetime import datetime
from typing import Sequence, Text
from email.mime.text import MIMEText
import imaplib
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
import json
import shutil
import smtplib

from boltons.setutils import IndexedSet as iset
import gnupg
import keyring
import textwrap
from toolz import dicttoolz
from toolz import itertoolz as itz
import traitlets as trt
from traitlets.config import SingletonConfigurable
from traitlets.config import get_config

import functools as ft
import pandas as pd
import itertools as itt
import os.path as osp

from co2mpas.__main__ import init_logging
from co2mpas import __uri__  # @UnusedImport
from co2mpas._version import (__version__, __updated__, __file_version__,   # @UnusedImport
                              __input_file_version__, __copyright__, __license__)  # @UnusedImport
from co2mpas.sampling.baseapp import (APPNAME, Cmd, Spec, build_sub_cmds,
    chain_cmds) # @UnusedImport
from co2mpas.sampling.baseapp import convpath, default_config_dir,ensure_dir_exists ##TODO: move to pandalone

__title__   = APPNAME
__summary__ = __doc__.split('\n')[0]


log = logging.getLogger(__name__)

try:
    _mydir = osp.dirname(__file__)
except:
    _mydir = '.'

CmdException = trt.TraitError
ProjectNotFoundException = trt.TraitError

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
    for folder in path.split(osp.sep):
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
    gpg_paths = iset(itt.chain.from_iterable(where(prog) for prog in ('gpg2', 'gpg')))
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


###################
##     Specs     ##
###################

PROJECT_VERSION = '0.0.1'  ## TODO: Move to `co2mpas/_version.py`.
PROJECT_STATUSES = '<invalid> empty full signed dice_sent sampled'.split()
CommitMsg = namedtuple('CommitMsg', 'project state msg format_version')

def _get_ref(refs, ref, default=None):
    return ref and ref in refs and refs[ref] or default


class GitSpec(SingletonConfigurable, Spec):
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
            When enabled, re-writes default git's config-settings on app start up.
            Git settings include user-name and email address, so this option might be usefull
            when the regular owner running the app has changed.
            """).tag(config=True)

    ## Useless, see https://github.com/ipython/traitlets/issues/287
    # @trt.validate('repo_path')
    # def _normalize_path(self, proposal):
    #     repo_path = proposal['value']
    #     if not osp.isabs(repo_path):
    #         repo_path = osp.join(default_config_dir(), repo_path)
    #     repo_path = convpath(repo_path)
    # return repo_path

    def __init__(self, **kwds):
        super().__init__(**kwds)
        repo_path = self.repo_path
        if not osp.isabs(repo_path):
            repo_path = osp.join(default_config_dir(), repo_path)
        repo_path = convpath(repo_path)
        if osp.isdir(repo_path):
            log.debug('Opening git-repo %r...', repo_path)
            self.repo = git.Repo(repo_path)
            if self.reset_settings:
                log.info('Resetting to default settings of git-repo %r...', self.repo.git_dir)
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
            cw.set_value('alias', 'lg',
                     r"log --graph --abbrev-commit --decorate --date=relative --format=format:'%C(bold blue)%h%C(reset) "
                     r"- %C(bold green)(%ar)%C(reset) %C(white)%s%C(reset) %C(dim white)- "
                     r"%an%C(reset)%C(bold yellow)%d%C(reset)' --all")

    def _make_commit_msg(self, projname, state, msg):
        msg = '\n'.join(textwrap.wrap(msg, width=50))
        return json.dumps(CommitMsg(projname, state, msg, PROJECT_VERSION)._asdict())

    def _parse_commit_msg(self, msg, scream=False):
        """
        :return: a :class:`CommitMsg` instance, or `None` if cannot parse.
        """
        try:
            return json.loads(msg,
                    object_hook=lambda seq: CommitMsg(**seq))
        except Exception as ex:
            if scream:
                raise
            else:
                log.debug('Found the non-project commit-msg in project-db'
                       ', due to: %s\n %s', ex, msg, exc_info=1)

    def _commit(self, index, projname, state, msg):
        index.commit(self._make_commit_msg(projname, state, msg))

    def exists(self, projname: Text, validate=False):
        """
        :param projname: some branch ref
        """
        repo = self.repo
        found = projname in repo.refs
        if validate:
            proj = repo.refs[projname]
            found = bool(self._parse_commit_msg(proj.commit.message))
        return found

    def _make_readme(self, projname):
        return textwrap.dedent("""
        This is the CO2MPAS-project named %r (see https://co2mpas.io/ for more).

        - created: %s
        """ %(projname, datetime.now()))

    def create(self, projname: str):
        """
        :param projname: some branch ref
        """
        self.log.info('Creating project %r...', projname)
        repo = self.repo
        if self.exists(projname):
            raise CmdException('Project %r already exists!' % projname)
        repo.git.checkout(projname, orphan=True)

        index = repo.index
        state_fpath = osp.join(repo.working_tree_dir, 'CO2MPAS')
        with io.open(state_fpath, 'wt') as fp:
            fp.write(self._make_readme(projname))
        index.add([state_fpath])
        self._commit(index, projname, 'empty', 'Project created.')

    def open(self, projname: str):
        """
        :param projname: some branch ref
        """
        self.log.info('Opening project %r...', projname)
        if self.exists(projname):
            raise CmdException('Project %r already exists!' % projname)
        self.repo.create_head(projname)

    def _yield_projects(self, refs=None):
        if not refs:
            refs = self.repo.heads
        for ref in refs:
            if self.exists(ref):
                yield self.examine(ref)

    def list(self, *projnames: str):
        """
        :param projnames: some branch ref, or none for all
        :retun: yield any match projects, or all if `projnames` were empty.
        """
        self.log.info('Listing %s projects...', projnames or 'all')
        refs = self.repo.heads
        if projnames and refs:
            refs =  iset(projnames) & iset(refs)
        yield from self._yield_projects(refs)

    def examine(self, projname: str):
        """
        :param projname: some branch ref
        """
#         repo = self.repo
#         proj = self.repo.refs[projname]
#         if not proj:
#             raise ProjectNotFoundException('Project %r does not exist!' % projname)
#         else:
#             cmt = proj.commit
#             tre = cmt.tree
#             cmsg = self._parse_commit_msg(cmt.message)
#             if not cmsg:
#                 ('author', '%s <%s>' % (cmt.author.name, cmt.author.email) ),
#                 ('last_date', str(cmt.authored_datetime)),
#                 ('tree_SHA', tre.hexsha),
#                 ('revisions_count', itz.count(cmt.iter_parents())),
#                 ('files_count', itz.count(tre.list_traverse())),
#         #return '<branch_ref>: %s' % proj_name # TODO: Impl proj-examine.
        return projname

    def infos(self, project=None, verbose=False, as_text=False):
        """
        :param project: use current branch if unspecified.
        :retun: text message with infos.
        """
        repo = self.repo
        infos = OrderedDict()
        proj = _get_ref(repo.heads, project, repo.active_branch)
        if not proj:
            infos['current'] = '<none>'
        else:
            cmt = proj.commit
            tre = cmt.tree
            cmsg = self._parse_commit_msg(cmt.message)
            if not cmsg:
                cproj_infos = OrderedDict([
                        ('name', proj.name),
                        ('state', '<invalid>'),
                        ('msg', cmt.message),
                ])
            else:
                cproj_infos = cmsg._asdict()
                cproj_infos.update([
                        ('author', '%s <%s>' % (cmt.author.name, cmt.author.email) ),
                        ('last_date', str(cmt.authored_datetime)),
                        ('tree_SHA', tre.hexsha),
                        ('revisions_count', itz.count(cmt.iter_parents())),
                        ('files_count', itz.count(tre.list_traverse())),
            ])
            infos['current'] = cproj_infos
        if verbose:
            git_exec = repo.git.git_exec_name
            if git_exec == 'git':
                git_exec = which('git')

            infos['git'] = OrderedDict([
                    ('repo_path', repo.working_tree_dir),
                    ('projects_count', itz.count(self._yield_projects()) ),
                    ('exec_path', repo.git.git_exec_name),
                    ('exec_version', '.'.join(str(v) for v in repo.git.version_info)),
            ])

        if as_text:
            infos = json.dumps(infos, indent=2)
        return infos


class GpgSpec(SingletonConfigurable, Spec):
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

class Project(Cmd):
    """
    The `co2dice` sub-cmd to administer the TA of *projects*.

    A *project* stores all CO2MPAS files for a single vehicle,
    and tracks the sampling procedure.
    """

    examples = trt.Unicode("""
        To get the list with the status of all existing projects, try:

            co2dice project list
        """)


    class _SubCmd(Cmd):
        @property
        def gitspec(self):
            return GitSpec.instance(parent=self)

    class Create(_SubCmd):
        """Create a new project."""
        def run(self):
            if len(self.extra_args) != 1:
                raise CmdException('Cmd %r takes a SINGLE project-name to create, recieved %r!'
                                   % (self.name, self.extra_args))
            return self.gitspec.create(self.extra_args[0])

    class Open(_SubCmd):
        """Make an existing project the *current*.  Returns the *current* if no args specified."""
        def run(self):
            if len(self.extra_args) != 1:
                raise CmdException("Cmd %r takes a SINGLE project-name to open, received: %r!"
                                   % (self.name, self.extra_args))
            return self.gitspec.open(self.extra_args[0])

    class List(_SubCmd):
        """List information about the specified projects (or all if no projects specified)."""
        def run(self):
            return self.gitspec.list(*self.extra_args)

    class Infos(_SubCmd):
        """Print a text message with current-project, status, and repo-config data if --verbose."""
        verbose = trt.Union((trt.Integer(), trt.Bool(False)),
               help="""
               Whether to include also info about the repo-configuration.
               Can be a boolean (# TODO: or 0, 1, 2).
               """).tag(config=True)

        def run(self):
            if len(self.extra_args) != 0:
                raise CmdException('Cmd %r takes no args, received %r!'
                                   % (self.name, self.extra_args))
            return self.gitspec.infos(self.verbose, as_text=True)


    def __init__(self, **kwds):
        with self.hold_trait_notifications():
            super().__init__(**kwds)
            self.conf_classes = [Spec, GitSpec]
            self.subcommands = build_sub_cmds(Project.Infos, Project.Create, Project.Open, Project.List)
            self.default_subcmd = 'infos'
            self.cmd_flags = {
                'reset-git-settings': ({
                        'GitSpec': {'reset_settings': True},
                    }, GitSpec.reset_settings.help),
                'verbose':  ({
                        'Infos': {'verbose': True},
                    }, Project.Infos.verbose.help),
            }



class Main(Cmd):
    """The parent command."""

    name        = __title__
    description = __summary__
    version     = __version__
    #examples = """TODO: Write cmd-line examples."""

    print_config = trt.Bool(False,
            help="""Enable it to print the configurations before launching any command."""
    ).tag(config=True)

    def __init__(self, **kwds):
        with self.hold_trait_notifications():
            super().__init__(**kwds)
            self.default_subcmd = 'project'
            self.subcommands = build_sub_cmds(Project, GenConfig)



## INFO: Add al conf-classes here
class GenConfig(Cmd):
    """
    Store config defaults into specified path(s), read from :attr:`extra_args` (cmd-arguments);
    '{confpath}' assumed if nonen specified.
    If a path resolves to a folder, the filename '{appname}_config.py' is appended.

    Note: It OVERWRITES any pre-existing configuration file(s)!
    """


    ## Class-docstring CANNOT contain string-interpolations!
    description = trt.Unicode(__doc__.format(confpath=convpath('~/.%s_config.py' % APPNAME),
                                 appname=APPNAME))

    examples = trt.Unicode("""
        Generate a config-file at your home folder:

            co2dice gen-config ~/my_conf

        Re-use this custom config-file:

            co2dice --config-files=~/my_conf  ...
        """)

    def run(self):
        ## INFO: Add al conf-classes here
        self.classes = [
              Project, Project.Infos, Project.Create, Project.Open, Project.List,
              GenConfig,
              Spec, GitSpec, Main,
        ]
        extra_args = self.extra_args or [None]
        for fpath in extra_args:
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
    if res:
        if isinstance(res, types.GeneratorType):
            for i in res:
                print(i)
        else:
            print(res)

def main(argv=None, verbose=None, **app_init_kwds):
    """
    :param argv:
        If `None`, use :data:`sys.argv`; use ``[]`` to explicitely use no-args.
    """
    ## Invoked from cmd-line, so suppress debug-logging by default.
    init_logging(verbose=verbose)
    try:
        ##Main.launch_instance(argv or None, **app_init_kwds) ## NO No, does not return `start()`!
        app = Main.instance(**app_init_kwds)
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
    # Invoked from IDEs, so enable debug-logging.
    init_logging(verbose=True)

    argv = None
    ## DEBUG AID ARGS, remember to delete them once developed.
    #argv = ''.split()
    argv = '--debug'.split()
    #argv = '--help'.split()
    argv = '--help-all'.split()
    argv = 'gen-config'.split()
    #argv = 'gen-config --help-all'.split()
    #argv = 'gen-config help'.split()
    #argv = '--debug --log-level=0 --Mail.port=6 --Mail.user="ggg" abc def'.split()
    #argv = 'project --help-all'.split()
    #argv = '--debug'.split()
    #argv = 'project list --help-all'.split()
#     argv = 'project --GitSpec.reset_settings=True'.split()
    #argv = 'project --reset-git-settings'.split()
    #argv = 'project infos --help-all'.split()
    #argv = 'project infos'.split()
#     argv = 'project infos --verbose'.split()
    #argv = 'project infos --verbose --debug'.split()
#     argv = 'project list  --GitSpec.reset_settings=True'.split()
    #argv = '--GitSpec.reset_settings=True'.split()
    #argv = 'project list'.split()
    #argv = 'project list  --reset-git-settings'.split()
    #argv = '--debug'.split()
    #argv = 'project list --help'.split()
    #argv = 'project list'.split()
    #argv = 'project'.split()
    #argv = 'project create one'.split()
    main(argv)

    #run_cmd(chain_cmds([Main, Project, Project.Create], argv=['project_foo']))
    #run_cmd(chain_cmds([Main, Project, Project.List], argv=['project_foo']))
