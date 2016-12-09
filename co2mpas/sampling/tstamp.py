#!/usr/bin/env python
#
# Copyright 2014-2016 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
"""A *report* contains the co2mpas-run values to time-stamp and disseminate to TA authorities & oversight bodies."""
#
###################
##     Specs     ##
###################

from collections import (
    defaultdict, OrderedDict, namedtuple, Mapping)  # @UnusedImport
from email.mime.text import MIMEText
import getpass
import imaplib
import io
import os
import re
import smtplib
import sys
import tempfile
from typing import (
    List, Sequence, Iterable, Text, Tuple, Dict, Callable)  # @UnusedImport

import traitlets as trt
import traitlets.config as trtc

from . import baseapp, project, CmdException
from .. import (__version__, __updated__, __uri__, __copyright__, __license__)  # @UnusedImport


class LoginCb(baseapp.Spec):
    """Reads os-user & password from env-var based on `prompt`, used by :meth:`TStampSpec._log_into_server()`."""

    def __init__(self, *args, user: Text=None, **kwds):
        super().__init__(*args, **kwds)

    def convert_prompt_to_env_var(self, prompt: Text):
        return re.sub('\W+', '_', prompt.strip()).upper()

    def ask_user_pswd(self, prompt: Text):

        var_name = self.convert_prompt_to_env_var(prompt)
        pswd = os.environ.get(var_name)
        self.log.debug('Found password in env-var %r? %s', var_name, bool(pswd))
        if pswd is not None:
            user = self.user_name
            if user is None:
                user = getpass.getuser()
            return user, pswd

    def report_failure(self, err):
        self.log.error('%s', err)


class ConsoleLoginCb(LoginCb):
    """Reads password from environment or from console (if tty)."""

    def ask_user_pswd(self, prompt):
        creds = super().ask_user_pswd(prompt)
        if creds:
            user, pswd = creds
        elif os.isatty(sys.stdin.fileno()):
            try:
                pswd = getpass.getpass('%s? ' % prompt)
            except KeyboardInterrupt:
                return None

            user = self.user_name
            if user is None:
                user = getpass.getuser()

        return user, pswd


class TStampSpec(baseapp.Spec):
    """Common parameters and methods for both SMTP(sending emails) & IMAP(receiving emails)."""

    host = trt.Unicode(
        '',
        help="""The SMTP/IMAP server, e.g. 'smtp.gmail.com'."""
    ).tag(config=True)

    port = trt.Int(
        allow_none=True,
        help="""
            The SMTP/IMAP server's port, usually 587/465 for SSL, 25 otherwise.
            If undefined, defaults to 0 and does its best.
        """).tag(config=True)

    ssl = trt.Bool(
        True,
        help="""Whether to talk TLS/SSL to the SMTP/IMAP server; configure `port` separately!"""
    ).tag(config=True)

    user = trt.Unicode(
        None, allow_none=True,
        help="""The user to authenticate with the SMTP/IMAP server."""
    ).tag(config=True)

    mail_kwds = trt.Dict(
        help="""
            Any extra key-value pairs passed to the SMTP/IMAP mail-client libraries.
            For instance, :class:`smtlib.SMTP_SSL` and :class:`smtlib.IMAP4_SSL`
            support `keyfile` and `timeout`, while SMTP/SSL support additionally
            `local_hostname` and `source_address`.
        """
    ).tag(config=True)

    login_cb = trt.Instance(ConsoleLoginCb, (), {},
                            help="If none, replaced by a new :class:`ConsoleLoginCb` instance.")

    def _log_into_server(self, login_cmd, prompt, login_cb=None):
        """
        Connects a credential-source(`login_cb`) to a consumer(`login_cmd`).

        :param login_cmd:
            A function like::

        :param login_cb:
            An object with 2 methods::

                ask_user_pswd(prompt) --> (user, pswd)  ## or `None` to abort.
                report_failure(obj)

                    login_cmd(user, pswd) --> xyz  ## `xyz` might be the server.

            If none, an instance of :class:`ConsoleLoginCb` is used.
        """
        if not login_cb:
            login_cb = self.login_cb

        for login_data in iter(lambda: login_cb.ask_user_pswd(prompt), None):
            user, pswd = login_data
            try:
                return login_cmd(user, pswd)
            except Exception as ex:
                login_cb.report_failure('%r' % ex)
        else:
            raise CmdException("User abort logging into %r email-server." % prompt)


class TstampSender(TStampSpec):
    """SMTP & timestamp parameters and methods for sending dice emails."""

    login = trt.CaselessStrEnum(
        'login simple'.split(), default_value=None, allow_none=True,
        help="""Which SMTP mechanism to use to authenticate: [ login | simple | <None> ]. """
    ).tag(config=True)

    timestamping_addresses = trt.List(
        type=trtc.Unicode(), allow_none=False,
        help="""The plain email-address(s) of the timestamp service must be here. Ask JRC to provide that. """
    ).tag(config=True)

    x_recipients = trt.List(
        type=trtc.Unicode(), allow_none=False,
        help="""The plain email-address of the receivers of the timestamped response. Ask JRC to provide that."""
    ).tag(config=True)

    subject = trt.Unicode(
        '[dice test]',
        help="""The subject-line to use for email sent to timestamp service. """
    ).tag(config=True)

    from_address = trt.Unicode(
        None,
        allow_none=False,
        help="""Your email-address to use as `From:` for email sent to timestamp service.
        Specify you correct address, or else you will never receive the sampling flag!
        """
    ).tag(config=True)

    def _sign_msg_mody(self, text):
        return text

    def _append_x_recipients(self, msg):
        x_recs = '\n'.join('X-Stamper-To: %s' % rec for rec in self.x_recipients)
        msg = "\n\n%s\n%s" % (x_recs, msg)

        return msg

    def _prepare_mail(self, msg):
        mail = MIMEText(msg)
        mail['Subject'] = self.subject
        mail['From'] = self.from_address
        mail['To'] = ', '.join(self.timestamping_addresses)

        return mail

    def send_timestamped_email(self, msg, login_cb=None):
        print(self.config)
        return
        msg = self._sign_msg_mody(msg)

        msg = self._append_x_recipients(msg)

        host = self.host
        port = self.port
        srv_kwds = self.mail_kwds.copy()
        if port is not None:
            srv_kwds['port'] = port

        self.log.info("Timestamping dice-report from %r through %r%s to %s-->%s",
                      self.from_address,
                      host, srv_kwds or '',
                      self.timestamping_addresses,
                      self.x_recipients)
        mail = self._prepare_mail(msg)

        prompt = 'SMTP pswd for %s' % host
        with (smtplib.SMTP_SSL(host, **srv_kwds)
              if self.ssl else smtplib.SMTP(host, **srv_kwds)) as srv:
            self._log_into_server(srv.login, prompt, login_cb)

            srv.send_message(mail)
        return mail


_PGP_SIGNATURE = b'-----BEGIN PGP SIGNATURE-----'  # noqa: E221
_PGP_MESSAGE = b'-----BEGIN PGP MESSAGE-----'    # noqa: E221
_PGP_SIG_REGEX = re.compile(
    br"""
        -----BEGIN PGP SIGNATURE-----
        .+
        Comment: Stamper Reference Id: (\d+)
        \n\n
        (.+?)
        \n-----END PGP SIGNATURE-----
    """,
    re.DOTALL | re.VERBOSE)


class TstampReceiver(TStampSpec):
    """IMAP & timestamp parameters and methods for receiving & parsing dice emails."""

    def _split_pgp_clear_signed(self, mail_bytes: bytes) -> (bytes, bytes):
        """
        Look at GPG signed content (e.g. the message of a signed tag object),
        whose payload is followed by a detached signature on it, and
        split these two; do nothing if there is no signature following.

        :param tag:
            As fetched from ``git cat-file tag v1.2.1``.
        :return:
            A 2-tuple(msg, sig), None if no sig found.
        """
        nl = b'\n'
        lines = mail_bytes.split(nl)
        for i, l in enumerate(lines):
            if l.startswith(_PGP_SIGNATURE) or l.startswith(_PGP_MESSAGE):
                sig = nl.join(lines[i:])
                msg = nl.join(lines[:i]) + nl

                return msg, sig

    def _pgp_sig2int(self, sig_bytes: bytes) -> int:
        import base64
        import binascii

        m = _PGP_SIG_REGEX.search(sig_bytes)
        if not m:
            raise CmdException("Invalid signature: %r" % sig_bytes)
        sig = base64.decodebytes(m.group(0))
        num = int(binascii.b2a_hex(sig), 16)

        return num

    def _verify_detached_armor(self, sig: str, data: str):
        """Verify `sig` on the `data`."""
    #def verify_file(self, file, data_filename=None):
        #with tempfile.NamedTemporaryFile(mode='wt+',
        #                encoding='latin-1') as sig_fp:
        #sig_fp.write(sig)
        #sig_fp.flush(); sig_fp.seek(0) ## paranoid seek(), Windows at least)
        #sig_fn = sig_fp.name
        with tempfile.TemporaryFile('wb+', prefix='dicesig_') as dicesig_file:
            sig_fn = dicesig_file.name
            self.log.debug('Wrote sig to temp file: %r', sig_fn)

            args = ['--verify', gnupg.no_quote(sig_fn), '-']
            result = self.result_map['verify'](self)
            data_stream = io.BytesIO(data.encode(self.encoding))
            self._handle_io(args, data_stream, result, binary=True)

            return result

    def parse_tsamp_response(self, mail_text: Text) -> int:
        mbytes = mail_text.encode('utf-8')
        # TODO: validate sig!
        msg, sig = self._split_pgp_clear_signed(mbytes)
        num = self._pgp_sig2int(sig)
        mod100 = num % 100
        decision = 'OK' if mod100 < 90 else 'SAMPLE'

        return sig, num, mod100, decision

    # see https://pymotw.com/2/imaplib/ for IMAP example.
    def receive_timestamped_email(self, host, login_cb, ssl=False, **srv_kwds):
        prompt = 'IMAP(%r)' % host

        def login_cmd(user, pswd):
            srv = (imaplib.IMAP4_SSL(host, **srv_kwds)
                   if ssl else imaplib.IMAP4(host, **srv_kwds))
            repl = srv.login(user, pswd)
            """GMAIL-2FAuth: imaplib.error: b'[ALERT] Application-specific password required:
            https://support.google.com/accounts/answer/185833 (Failure)'"""
            self.log.debug("Sent %s-user/pswd, server replied: %s", prompt, repl)
            return srv

        srv = self._log_into_server(login_cmd, prompt, login_cb)
        try:
            resp = srv.list()
            print(resp[0])
            return [srv.retr(i + 1) for i, msg_id in zip(range(10), resp[1])]
        finally:
            resp = srv.logout()
            if resp:
                self.log.warning('While closing %s srv responded: %s', prompt, resp)


###################
##    Commands   ##
###################


class _Subcmd(baseapp.Cmd):
    @property
    def projects_db(self):
        p = project.ProjectsDB.instance()
        p.config = self.config
        return p


class TstampCmd(baseapp.Cmd):
    """Commands to manage the communications with the Timestamp server."""

    class SendCmd(_Subcmd):
        """
        Send dice-reports to be timestamped and parse back the response.

        The time-stamp service will disseminate the dice-report to the TA authorities & oversight bodies.
        From its response the sampling decision will be deduced.

        Many options related to sending & receiving the email are expected to be stored in the config-file.

        - The sending command is NOT to be used directly (just for experimenting).
          If neither `--file` nor `--project` given, reads dice-report from stdin.
        - The receiving command waits for the response.and returns: 1: SAMPLE | 0: NO-SAMPLE
          Any other code is an error-code - communicate it to JRC.

        SYNTAX
            co2dice tstamp send [ file=<dice-report-file> ]
            co2dice tstamp send [ file=<dice-report-file> ]
            co2dice tstamp recv
        """

        examples = trt.Unicode("""
            To wait for the response after you have sent the dice-report, use this bash commands:

                co2dice tstamp recv
                if [ $? -eq 0 ]; then
                    echo "NO-SAMPLE"
                elif [ $? -eq 1 ]; then
                    echo "SAMPLE!"
                else
                    echo "ERROR CODE: $?"
            """)

        file = trt.Unicode(
            None, allow_none=True,
            help="""If not null, read mail body from the specified file."""
        ).tag(config=True)

        __sender = None

        @property
        def sender(self):
            if not self.__sender:
                self.__sender = TstampSender(config=self.config)
            return self.__sender

        def __init__(self, **kwds):
            with self.hold_trait_notifications():
                dkwds = {
                    'conf_classes': [project.ProjectsDB, TstampSender],
                    'cmd_aliases': {
                        'file': 'SendCmd.file',
                    },
                }
                dkwds.update(kwds)
                super().__init__(**dkwds)

        def run(self, *args):
            nargs = len(args)
            if nargs > 0:
                raise CmdException(
                    "Cmd '%s' takes no arguments, received %d: %r!"
                    % (self.name, len(args), args))

            file = self.file

            if not file:
                self.log.warning("Time-stamping STDIN; paste message verbatim!")
                mail_text = sys.stdin.read()
            else:
                self.log.info('Time-stamping files %r...', file)
                with io.open(file, 'rt') as fin:
                    mail_text = fin.read()
            sender = self.sender
            login_cb = ConsoleLoginCb(config=self.config)
            sender.send_timestamped_email(mail_text, login_cb)

    class ParseCmd(_Subcmd):
        """
        Derives the *decision* OK/SAMPLE flag from time-stamped email.

        SYNTAX
            cat <mail> | co2dice tstamp parse
        """

        __recver = None

        @property
        def recver(self) -> TstampReceiver:
            if not self.__recver:
                self.__recver = TstampReceiver(config=self.config)
            return self.__recver

        def run(self, *args):
            nargs = len(args)
            if nargs > 0:
                raise CmdException(
                    "Cmd '%s' takes no arguments, received %d: %r!"
                    % (self.name, len(args), args))

            rcver = self.recver
            mail_text = sys.stdin.read()
            decision_tuple = rcver.parse_tsamp_response(mail_text)

            return ('SIG: %s\nNUM: %s\nMOD100: %s\nDECISION: %s' %
                    decision_tuple)

    def __init__(self, **kwds):
        with self.hold_trait_notifications():
            dkwds = {
                'conf_classes': [project.ProjectsDB, TstampSender, TstampReceiver],
                'subcommands': baseapp.build_sub_cmds(*all_subcmds),
            }
            dkwds.update(kwds)
            super().__init__(**dkwds)

all_subcmds = (TstampCmd.SendCmd, TstampCmd.ParseCmd)


if __name__ == '__main__':
    from traitlets.config import get_config
    # Invoked from IDEs, so enable debug-logging.
    c = get_config()
    c.Application.log_level = 0
    #c.Spec.log_level='ERROR'

    argv = None
    ## DEBUG AID ARGS, remember to delete them once developed.
    #argv = ''.split()
    #argv = '--debug'.split()

    #TstampCmd(config=c).run('--text ')
    from . import dice
    dice.run_cmd(baseapp.chain_cmds(
        [dice.MainCmd, TstampCmd],
        config=c))
