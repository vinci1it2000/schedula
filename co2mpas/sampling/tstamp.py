#!/usr/b in/env python
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
import imaplib
import io
import os
import re
import smtplib
import sys
from typing import (
    List, Sequence, Iterable, Text, Tuple, Dict, Callable)  # @UnusedImport

import traitlets as trt
import traitlets.config as trtc

from . import baseapp, project, CmdException, PFiles
from .. import (__version__, __updated__, __file_version__,   # @UnusedImport
                __input_file_version__, __copyright__, __license__)  # @UnusedImport
from .. import __uri__  # @UnusedImport


class MailSpec(baseapp.Spec):
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

    kwds = trt.Dict(
        help="""
            Any extra key-value pairs passed to the SMTP/IMAP mail-client libraries.
            For instance, :class:`smtlib.SMTP_SSL` and :class:`smtlib.IMAP4_SSL`
            support `keyfile` and `timeout`, while SMTP/SSL support additionally
            `local_hostname` and `source_address`.
        """
    ).tag(config=True)

    def _log_into_server(self, login_cb, login_cmd, prompt):
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
        for login_data in iter(lambda: login_cb.ask_user_pswd(prompt), None):
            user, pswd = login_data
            try:
                return login_cmd(user, pswd)
            except Exception as ex:
                login_cb.report_failure('%r' % ex)
        else:
            raise CmdException("User abort logging into %r email-server." % prompt)


class ConsoleLoginCb(baseapp.Spec):
    user = None

    def __init__(self, *args, user=None, **kwds):
        super().__init__(*args, **kwds)
        self.user = user

    def convert_prompt_to_env_var(self, prompt):
        return re.sub('\W+', '_', prompt.strip()).upper()

    def ask_user_pswd(self, prompt):
        import getpass

        var_name = self.convert_prompt_to_env_var(prompt)
        pswd = os.environ.get(var_name)
        self.log.debug('Found password in env-var %r? %s', var_name, bool(pswd))
        if pswd is None:
            pswd = getpass.getpass('%s? ' % prompt)

        user = self.user
        if user is None:
            user = getpass.getuser()
        return user, pswd

    def report_failure(self, err):
        self.log.error('%s', err)


class TstampSender(MailSpec):
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

#     @trt.validate('from_address')
#     def _validate(self, proposal):
#         v = proposal['value']
#         if not v:

    def send_timestamped_email(self, msg, login_cb):
        x_recs = '\n'.join('X-Stamper-To: %s' % rec for rec in self.x_recipients)
        msg = "\n\n%s\n%s" % (x_recs, msg)

        host = self.host
        port = self.port
        srv_kwds = self.kwds.copy()
        if port is not None:
            srv_kwds['port'] = port

        self.log.info("Timestamping dice-report from %r through %r%s to %s-->%s",
                      self.from_address,
                      host, srv_kwds or '',
                      self.timestamping_addresses, self.x_recipients)
        mail = MIMEText(msg)
        mail['Subject'] = self.subject
        mail['From'] = self.from_address
        mail['To'] = ', '.join(self.timestamping_addresses)

        prompt = 'SMTP pswd for %s' % host
        with (smtplib.SMTP_SSL(host, **srv_kwds)
              if self.ssl else smtplib.SMTP(host, **srv_kwds)) as srv:
            self._log_into_server(login_cb, srv.login, prompt)

            srv.send_message(mail)
        return mail


class TstampReceiver(MailSpec):
    """IMAP & timestamp parameters and methods for receiving & parsing dice emails."""

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

        srv = self._log_into_server(login_cb, login_cmd, prompt)
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


class TstampCmd(baseapp.Cmd):
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
        help="""
        If not null, extract dice-report from a file.
        """).tag(config=True)

    project = trt.Bool(
        False,
        help="""
        Whether to extract dice-report tag from the *current-project*.
        """).tag(config=True)

    __report = None

    __sender = None

    @property
    def sender(self):
        if not self.__sender:
            self.__sender = TstampSender(config=self.config)
        return self.__sender

    @property
    def projects_db(self):
        p = project.ProjectsDB.instance()
        p.config = self.config
        return p

    def __init__(self, **kwds):
        with self.hold_trait_notifications():
            dkwds = {
                'conf_classes': [project.ProjectsDB, TstampSender],
                'cmd_aliases': {
                    'file': 'TstampCmd.file',
                    'text': 'TstampCmd.text',
                },
            }
            dkwds.update(kwds)
            super().__init__(**dkwds)

    def _build_mail_from_project(self, args) -> PFiles:
        project = self.projects_db.current_project()
        pfiles = project.list_pfiles('inp', 'out', _as_index_paths=True)
        if not pfiles:
            raise CmdException(
                "Current %s contains no dice-report!" % project)
        return pfiles

    def run(self, *args):
        nargs = len(args)
        if nargs > 0:
            raise CmdException(
                "Cmd '%s' takes no arguments, received %d: %r!"
                % (self.name, len(args), args))

        file = self.file
        project = self.project

        if not (file or project):
            self.log.warning("Time-stamping STDIN; copy message verbatim!")
            mail_text = sys.stdin.read()
        else:
            assert bool(file) ^ bool(project), (file, project)
            if file:
                self.log.info('Time-stamping files %r...', file)
                with io.open(file, 'rt') as fin:
                    mail_text = fin.read()
            else:
                self.log.info('Timestamping dice-report from current-project...')
                assert False, "Not impl!"
        tstamper = TstampSender(config=self.config)
        login_cb = ConsoleLoginCb(config=self.config)
        tstamper.send_timestamped_email(mail_text, login_cb)


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
