#!/usr/b in/env python
#
# Copyright 2014-2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
#
"""
An *ipython traitlets* framework for apps with hierarchical commands(class:`App`) utilizing configurables (class:`Spec`).

To run the app use this code copied from :method:
        May yield, so check if a type:`GeneratorType`.
app = Main.instance(**app_init_kwds)
app.initialize(argv or None)
return app.start()
"""

from collections import OrderedDict
import copy
import errno
import io
import os
from pandalone import utils as pndl_utils
import re

from boltons.setutils import IndexedSet as iset
from ipython_genutils.text import indent, wrap_paragraphs, dedent
from traitlets.config import Application, LoggingConfigurable, catch_config_error

from co2mpas.__main__ import CmdException
import os.path as osp
import traitlets as trt


## INFO: Modify the following variables on a different application.
APPNAME = 'co2dice'
CONF_VAR_NAME = '%s_CONFIG_FILE' % APPNAME.upper()

try:
    _mydir = osp.dirname(__file__)
except:
    _mydir = '.'


###############################
##  TODO: Move to pandalone  ##
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
    """Turns `'CO2DiceApp' --> 'co2_dice_app'. """
    return _camel_to_snake_regex.sub(r'_\1', s).lower()

def camel_to_cmd_name(s):
    """Turns `'CO2DiceApp' --> 'co2-dice-app'. """
    return camel_to_snake_case(s).replace('_', '-')

###############################


###################
##     Specs     ##
###################

def default_config_fname():
    """The config-file's basename (no path or extension) to search when not explicitly specified."""
    return '%s_config' % APPNAME

def default_config_dir():
    """The folder of to user's config-file."""
    return convpath('~/.%s' % APPNAME)

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
        import logging
        return logging.getLogger(self.name)

    @trt.validate('user_name', 'user_email')
    def _valid_user(self, proposal):
        value = proposal['value']
        if not value:
            raise trt.TraitError('%s.%s must not be empty!'
                                 % (proposal['owner'].name, proposal['trait'].name))
        return value


###################
##    Commands   ##
###################


def app_help(app_class):
    desc = app_class.class_traits().get('description')
    return (isinstance(desc, str) and desc
        or (isinstance(app_class.description, str) and app_class.description)
        or app_class.__doc__)

def build_sub_cmds(subapp_classes):
    """Builds an ordered-dictionary of ``cmd-name --> (cmd-class, help-msg)``. """

    return OrderedDict((camel_to_cmd_name(sa.__name__), (sa, app_help(sa)))
                       for sa in subapp_classes)

class Cmd(Spec, Application):
    """Common machinery for all (sub-)commands. """
    ## INFO: Do not use it directly; inherit it.

    @trt.default('name')
    def _name(self):
        return camel_to_snake_case(self.__class__.__name__)

    description = '' ## So that dynamic-default rule, below, runs on subclasses.

    @trt.default('description')
    def _description(self):
        return __doc__ or '<no description>'

    config_files = trt.Unicode(None, allow_none=True,
            help="""
            Absolute/relative path(s) to config files to OVERRIDE default configs.
            Multiple paths are separated by '{pathsep}' in descending order.
            Any extensions are ignored, and '.json' or '.py' are searched (in this order).
            If the path specified resolves to a folder, the filename `{appname}_config.[json | py]` is appended;
            Any command-line values take precendance over the `{confvar}` envvar.
            Use `gen-config` sub-command to produce a skeleton of the config-file.
            """.format(appname=APPNAME, confvar=CONF_VAR_NAME, pathsep=osp.pathsep)
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
        paths = list(iset([default_config_dir(), _mydir]))
        self.load_config_file(default_config_fname(), path=paths)

        # Load "user" configs.
        #
        user_conf_fpaths = self.user_config_fpaths
        for fp in user_conf_fpaths[::-1]:
            cdir, cfname = osp.split(fp)
            self.load_config_file(cfname, path=cdir)

    def write_default_config(self, config_file=None):
        if not config_file:
            config_file = default_config_fpath()
        else:
            config_file = convpath(config_file)
            if osp.isdir(config_file):
                config_file = osp.join(config_file, default_config_fname())
        config_file = pndl_utils.ensure_file_ext(config_file, '.py')

        op = 'Over-writting' if osp.isfile(config_file) else 'Writting'
        self.log.info('%s config-file %r...', op, config_file)
        ensure_dir_exists(os.path.dirname(config_file), 0o700)
        config_text = self.generate_config_file();
        with io.open(config_file, mode='wt') as fp:
            fp.write(config_text)

    def print_subcommands(self):
        """Print the subcommand part of the help."""
        ## Overridden, to print "default" sub-cmd.
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

    @catch_config_error
    def initialize_subcommand(self, subc, argv=None):
        """Initialize a subcommand named `subc` with `argv`, or `sys.argv` if `None` (default)."""
        ## INFO: Overriden to set parent on subcmds and inherit config,
        #  see https://github.com/ipython/traitlets/issues/286
        subapp, _ = self.subcommands.get(subc)
        self.__class__.clear_instance()
        self.subapp = subapp.instance(parent=self)
        self.subapp.initialize(argv)

    def _is_dispatching(self):
        """True if dispatching to another command, or running ourselves."""
        return bool(self.subapp)

    def __init__(self, **kwds):
        subcmds_list = [cmd for cmd, _ in kwds.get('subcommands', {}).values()]
        super().__init__(classes=subcmds_list + [Spec], **kwds)
        self.aliases.update({
            'log-level' :       'Application.log_level',
            'config-files' :    'Cmd.config_files',
        })
        self.flags.update({
            'debug': ({'Application' : {'log_level' : 0}},
            "Set log level to logging.DEBUG (maximize logging output)."),
        })

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
            pass
        elif self.default_subcmd:
            self.initialize_subcommand(self.default_subcmd, self.argv)
        else:
            raise CmdException('Specify one of the sub-commands: %s'
                               % ', '.join(self.subcommands.keys()))
        return self.subapp.start()


## Disable logging-format configs, because their observer
#    works on on loger's handlers, which might be null.
Cmd.log_format.tag(config=False)
Cmd.log_datefmt.tag(config=False)

class GenConfig(Cmd):
    """
    Store config defaults into specified path(s), read from :attr:`extra_args` (cmd-arguments);
    '{confpath}' assumed if nonen specified.
    If a path resolves to a folder, the filename '{appname}_config.py' is appended.

    Note: It OVERWRITES any pre-existing configuration file(s)!
    """

    ## Class-docstring CANNOT contain string-interpolations!
    description = __doc__.format(confpath=convpath('~/.%s_config.py' % APPNAME),
                                 appname=APPNAME)

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
