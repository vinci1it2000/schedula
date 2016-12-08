#!/usr/b in/env python
#
# Copyright 2014-2016 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
#
"""
co2dice: prepare/sign/send/receive/validate/archive Type Approval sampling emails of *co2mpas*.

.. Warning::
    Do not run multiple instances!
"""

from co2mpas import (__version__, __updated__, __file_version__,   # @UnusedImport
                              __input_file_version__, __copyright__, __license__)  # @UnusedImport
from co2mpas import __uri__  # @UnusedImport
from co2mpas.__main__ import init_logging
from co2mpas.sampling import baseapp, CmdException
from co2mpas.sampling.baseapp import (APPNAME, Cmd, build_sub_cmds,
                                      chain_cmds)  # @UnusedImport
from collections import defaultdict, MutableMapping, OrderedDict, namedtuple
from email.mime.text import MIMEText
import io
import logging
import os
import re
import shutil
import tempfile
import textwrap
import types
from typing import Sequence, Text

from boltons.setutils import IndexedSet as iset
import gnupg  # from python-gnupg
from toolz import dicttoolz as dtz, itertoolz as itz

import functools as fnt
import itertools as itt
import os.path as osp
import pandalone.utils as pndlu
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


_list_response_regex = re.compile(r'\((?P<flags>.*?)\) "(?P<delimiter>.*)" (?P<name>.*)')


def _parse_list_response(line):
    flags, delimiter, mailbox_name = _list_response_regex.match(line).groups()
    mailbox_name = mailbox_name.strip('"')
    return (flags, delimiter, mailbox_name)


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

    exec_path = trt.Unicode(
        None, allow_none=True,
        help="""
        The path to GnuPG executable; if None, the first one in PATH variable is used: '{gpgexec}'.
        """.format(gpgexec=pndlu.convpath(pndlu.which('gpg')))).tag(config=True)

    home = trt.Unicode(
        None, allow_none=True,
        help="""
        The default home directory containing the keys; if None given and nor env-var GNUPGHOME exist,
        the executable decides (e.g. `~/.gpg` on POSIX, `%APPDATA%\Roaming\GnuPG` on Windows).
        """).tag(config=True)


###################
##    Commands   ##
###################

class MainCmd(Cmd):
    """The parent command."""

    name = trt.Unicode(__title__)
    description = trt.Unicode("""
    co2dice: prepare/sign/send/receive/validate & archive Type Approval sampling emails for *co2mpas*.

    TIP:
      If you bump into blocking errors, please use the `co2dice project backup` command and
      send the generated archive-file back to "CO2MPAS-Team <co2mpas@jrc.ec.europa.eu>",
      for examination.
    NOTE:
      Do not run multiple instances!
    """)
    version = __version__
    #examples = """TODO: Write cmd-line examples."""

    print_config = trt.Bool(
        False,
        help="""Enable it to print the configurations before launching any command."""
    ).tag(config=True)

    def __init__(self, **kwds):
        from co2mpas.sampling import project, report, tstamp
        sub_cmds = build_sub_cmds(
            project.ProjectCmd,
            report.ReportCmd,
            tstamp.TstampCmd,
            GenConfigCmd)
        with self.hold_trait_notifications():
            dkwds = {
                'name': __title__,
                'description': __summary__,
                ##'default_subcmd': 'project', ## Confusing for the user.
                'subcommands': sub_cmds,
            }
            dkwds.update(kwds)
            super().__init__(**dkwds)


## INFO: Add all conf-classes here
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

    force = trt.Bool(
        False,
        ## INFO: Add force flag explanations here.
        help="""Force overwriting config-file, even if it already exists."""
    ).tag(config=True)

    def __init__(self, **kwds):
        dkwds = {
            'cmd_flags': {
                ('f', 'force'): (
                    {'GenConfigCmd': {'force': True}, },
                    pndlu.first_line(GenConfigCmd.force.help)
                )
            },
        }
        dkwds.update(kwds)
        super().__init__(**dkwds)

    def run(self, *args):
        self.classes = all_configurables()
        args = args or [None]
        for fpath in args:
            self.write_default_config(fpath, self.force)


####################################
## INFO: Add all CMDs here.
#
def all_cmds():
    from co2mpas.sampling import project, report, tstamp
    return (
        (
            MainCmd,
            project.ProjectCmd,
            report.ReportCmd,
            tstamp.TstampCmd,
            GenConfigCmd,
        ) +
        project.all_subcmds +
        tstamp.all_subcmds)


## INFO: Add all SPECs here.
#
def all_configurables():
    from co2mpas.sampling import project, report, tstamp
    return all_cmds() + (
        baseapp.Spec, project.ProjectsDB,
        report.Report,
        tstamp.TstampSender,
        tstamp.TstampReceiver,
    )
####################################


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
    argv = 'project examine --as-json --verbose --debug'.split()
    argv = 'project examine --Project.verbose=2 --debug'.split()
#     argv = 'project list  --Project.reset_settings=True'.split()
    #argv = '--Project.reset_settings=True'.split()
    #argv = 'project list  --reset-git-settings'.split()
    #argv = 'project init one'.split()

    #argv = 'tstamp send'.split()
    # Invoked from IDEs, so enable debug-logging.
    main(argv, log_level=logging.DEBUG)

    #from traitlets.config import trtc.get_config

    #c = trtc.get_config()
    #c.Application.log_level=0
    #c.Spec.log_level='ERROR'
    #run_cmd(chain_cmds([MainCmd, ProjectCmd, ProjectCmd.InitCmd], argv=['project_foo']))
