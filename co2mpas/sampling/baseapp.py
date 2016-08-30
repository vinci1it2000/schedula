#!/usr/b in/env python
#
# Copyright 2014-2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
#
"""
An *ipython traitlets* framework for apps with hierarchical chain of commands(class:`App`) utilizing configurables (class:`Spec`).

To run a base command, use this code::

    app = Main.instance(**app_init_kwds)
    app.initialize(argv or None) ## Uses `sys.argv` if `argv` is `None`.
    return app.start()

To run nested commands, use :func:`baseapp.chain_cmds()` like that::

    app = chain_cmds(Main, Project, Project.List)
    return app.start()
"""
## INFO: Modify the following variables on a different application.

from collections import OrderedDict
import copy
import errno
import io
import logging
import os
from pandalone import utils as pndl_utils
import re
import subprocess
from typing import Sequence, Text, Any, Tuple, List

from boltons.setutils import IndexedSet as iset
from ipython_genutils.text import indent, wrap_paragraphs, dedent
from toolz import dicttoolz as dtz, itertoolz as itz
from traitlets.config import Application, Configurable, LoggingConfigurable, catch_config_error

from co2mpas.__main__ import init_logging
import os.path as osp
import traitlets as trt


APPNAME = 'co2dice'
CONF_VAR_NAME = '%s_CONFIG_FILE' % APPNAME.upper()

try:
    _mydir = osp.dirname(__file__)
except:
    _mydir = '.'

CmdException = trt.TraitError

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


def format_kv_items(items: List[Tuple[Text, Any]], indent=12):
    def format_item(k, v):
        nk = len(k)
        ntabs = max (1, int(nk / indent) + bool(nk % indent))
        key_width = ntabs * indent
        item_pattern = '%%-%is = %%s' % key_width
        return item_pattern % (k, v)
    dic = [format_item(*i) for i in items]

    return '\n'.join(sorted(dic))


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


###############################


def default_config_fname():
    """The config-file's basename (no path or extension) to search when not explicitly specified."""
    return '%s_config' % APPNAME

def default_config_dir():
    """The folder of to user's config-file."""
    return convpath('~/.%s' % APPNAME)

def default_config_fpath():
    """The full path of to user's config-file, without extension."""
    return osp.join(default_config_dir(), default_config_fname())


###################
##     Specs     ##
###################

class Spec(LoggingConfigurable):
    """Common properties for all configurables."""

    @trt.default('log')
    def _log(self):
        return logging.getLogger(type(self).__name__)

    # The log level for the application
    log_level = trt.Enum((0,10,20,30,40,50,'DEBUG','INFO','WARN','ERROR','CRITICAL'),
                    default_value=logging.WARN,
                    help="Set the log level by value or name.").tag(config=True)

    @trt.observe('log_level')
    def _log_level_changed(self, change):
        """Adjust the log level when log_level is set."""
        new = change['new']
        if isinstance(new, str):
            new = getattr(logging, new)
            self.log_level = new
        self.log.setLevel(new)

    verbose = trt.Union((trt.Integer(), trt.Bool(False)),
            ## INFO: Add verbose flag explanations here.
            help="""
            Various sub-commands increase their verbosity (not to be confused with --debug):
            Can be a boolean or 0, 1(==True), 2, ....

            - project infos: Whether to include also info about the repo-configuration.
            """).tag(config=True)

    user_name = trt.Unicode('<Name Surname>',
            help="""The Name & Surname of the default user invoking the app.  Must not be empty!"""
            ).tag(config=True)
    user_email = trt.Unicode('<email-address>',
            help="""The email address of the default user invoking the app. Must not be empty!"""
            ).tag(config=True)


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

def build_sub_cmds(*subapp_classes):
    """Builds an ordered-dictionary of ``cmd-name --> (cmd-class, help-msg)``. """

    return OrderedDict((camel_to_cmd_name(sa.__name__), (sa, app_help(sa)))
                       for sa in subapp_classes)


class Cmd(Application):
    """Common machinery for all (sub-)commands. """
    ## INFO: Do not use it directly; inherit it.

    @trt.default('name')
    def _name(self):
        return camel_to_snake_case(type(self).__name__)


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

    @trt.default('log')
    def _log(self):
        ## Use a regular logger.
        return logging.getLogger(type(self).__name__)

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

    def print_flag_help(self):
        """Print the flag part of the help."""
        if not self.flags:
            return

        lines = []
        for m, (cfg, fhelp) in self.flags.items():
            try:
                prefix = '--' if len(m) > 1 else '-'
                lines.append(prefix+m)
                lines.append(indent(dedent(fhelp.strip())))
                cfg_list = ['%s.%s=%s' %(clname, prop, val)
                            for clname, props_dict
                            in cfg.items() for prop, val in props_dict.items()]
                cfg_txt = "Equivalent to: %s" % cfg_list
                lines.append(indent(dedent(cfg_txt)))
            except Exception as ex:
                self.log.error('Failed collecting help-message for flag %r, due to: %s',
                               m, ex, exc_info=1)
        # lines.append('')
        print(os.linesep.join(lines))

    def print_help(self, classes=False):
        """Print the help for each Configurable class in self.classes.

        If classes=False (the default), only flags and aliases are printed.
        """
        ## TODO: Remove if https://github.com/ipython/traitlets/issues/296
        self.print_description()
        self.print_subcommands()
        self.print_options()

        if classes:
            help_classes = self._classes_in_config_sample()
            if help_classes:
                print("Class parameters")
                print("----------------")
                print()
                for p in wrap_paragraphs(self.keyvalue_description):
                    print(p)
                    print()

            for cls in help_classes:
                cls.class_print_help()
                print()
        else:
            print("To see all available configurables, use `--help-all`")
            print()

        self.print_examples()

    @classmethod
    def class_get_help(cls, inst=None):
        """Get the help string for this class in ReST format.

        If `inst` is given, it's current trait values will be used in place of
        class defaults.
        """
        assert inst is None or isinstance(inst, cls)
        final_help = []
        base_classes = ','.join(p.__name__ for p in cls.__bases__)
        final_help.append(u'%s(%s) options' % (cls.__name__, base_classes))
        final_help.append(len(final_help[0])*u'-')
        for k, v in sorted(cls.class_traits(config=True).items()):
            help = cls.class_get_trait_help(v, inst)
            final_help.append(help)
        return '\n'.join(final_help)

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
                subc = '%s[*]' % subc
            lines.append(subc)

            if hlp:
                lines.append(indent(dedent(hlp.strip())))
        if self.default_subcmd:
            lines.append('')
            lines.append("""Note: The asterisk '[*]' marks the "default" sub-command to run when none specified.""")
        lines.append('')
        print(os.linesep.join(lines))

    @catch_config_error
    def initialize_subcommand(self, subc, argv=None):
        """Initialize a subcommand named `subc` with `argv`, or `sys.argv` if `None` (default)."""
        ## INFO: Overriden to set parent on subcmds and inherit config,
        #  see https://github.com/ipython/traitlets/issues/286
        subcmd_tuple = self.subcommands.get(subc)
        assert subcmd_tuple, "Cannot find sub-cmd %r in sub-cmds of %r: %s" % (
            subc, self.name, list(self.subcommands.keys()))
        subapp, _ = subcmd_tuple
        type(self).clear_instance()
        self.subapp = subapp.instance(parent=self)
        self.subapp.initialize(argv)

    default_subcmd = trt.Unicode(None, allow_none=True,
            help="The name of the sub-command to use if unspecified.")

    conf_classes = trt.List(trt.Type(Configurable), default_value=[],
            help="""
            Any *configurables* found in this prop up the cmd-chain are merged,
            along with any subcommands, into :attr:`classes`.
            """)

    cmd_aliases = trt.Dict({},
            help="Any *flags* found in this prop up the cmd-chain are merged into :attr:`aliases`. """)

    cmd_flags = trt.Dict({},
            help="Any *flags* found in this prop up the cmd-chain are merged into :attr:`flags`. """)

    @trt.observe('parent', 'conf_classes', 'cmd_aliases', 'cmd_flags', 'subapp', 'subcommands')
    def _inherit_parent_cmd(self, change):
        """ Inherit config-related stuff from up the cmd-chain. """
        if self.parent:
            ## Collect parents, ordered like that:
            #    subapp, self, parent1, ...
            #
            cmd_chain = []
            pcl = self.subapp if self.subapp else self
            while pcl:
                cmd_chain.append(pcl)
                pcl = pcl.parent

            ## Collect separately and merge  SPECs separately,
            #  to prepend them before SPECs at the end.
            #
            conf_classes = list(itz.concat(cmd.conf_classes for cmd in cmd_chain))

            ## Merge aliases/flags reversed.
            #
            cmd_aliases = dtz.merge(cmd.cmd_aliases for cmd in cmd_chain[::-1])
            cmd_flags = dtz.merge(cmd.cmd_flags for cmd in cmd_chain[::-1])
        else:
            ## We are root.

            cmd_chain = [self]
            conf_classes = list(self.conf_classes)
            cmd_aliases = self.cmd_aliases
            cmd_flags = self.cmd_flags

        cmd_classes = [type(cmd) for cmd in cmd_chain]
        self.classes = list(iset(cmd_classes + conf_classes))
        self.aliases.update(cmd_aliases)
        self.flags.update(cmd_flags)

    @trt.observe('log_level')
    def _init_logging(self, change):
        log_level = change['new']
        if isinstance(log_level, str):
            log_level = getattr(logging, log_level)
        if log_level <= logging.DEBUG:
            verbose = True
        elif log_level == logging.INFO:
            verbose = None
        else:
            verbose = False
        init_logging(verbose=verbose)

    def __init__(self, **kwds):
        cls = type(self)
        dkwds = {
            ## Traits defaults are not always applied...
            #
            'description': cls.__doc__,
            'name': camel_to_snake_case(cls.__name__),

            ## Set some nice defaults for root-CMDs.
            #
            'cmd_aliases': {
                'config-files': 'Cmd.config_files',
            },
            'cmd_flags': {
                'debug': ({
                    'Application' : {'log_level' : 0},
                    'Spec' : {'log_level' : 0},
                    'Cmd' : {
                        'raise_config_file_errors': True,
                        'print_config': True,
                    },
                },
                "Log more logging, fail on configuration errors, "
                "and print configuration on each cmd startup."
                ),
                'verbose':  ({
                    'Spec': {'verbose': True},
                },
                Spec.verbose.help
                ),
            },
        }
        dkwds.update(kwds)
        super().__init__(**dkwds)

    def _is_dispatching(self):
        """True if dispatching to another command."""
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
            ## Only the final child gets file-configs.
            #  Also avoid contaminations with user if generating-config.
            return
        cl_config = copy.deepcopy(self.config)
        self.load_config_files()
        self.update_config(cl_config)

    print_config = trt.Bool(False,
            help="""Enable it to print the configurations before launching any command."""
    ).tag(config=True)

    def start(self):
        """Dispatches into sub-cmds (if any), and then delegates to :meth:`run().

        If overriden, better invoke :func:`super()`, but even better
        to override :meth:``run()`.
        """
        if self.print_config:
            self.log.info('Running cmd %r with config: \n  %s', self.name, self.config)

        if self.subapp is not None:
            pass
        elif self.default_subcmd:
            self.initialize_subcommand(self.default_subcmd, self.argv)
        else:
            return self.run()

        return self.subapp.start()

    def run(self):
        """Leaf sub-commands must inherit this instead of :meth:`start()` without invoking :func:`super()`.

        By default, screams about using sub-cmds, or about doing nothing!
        """
        if self.subcommands:
            raise CmdException('Specify one of the sub-commands: %s'
                               % ', '.join(self.subcommands.keys()))
        assert False, "Override run() method in cmd subclasses."




## Disable logging-format configs, because their observer
#    works on on loger's handlers, which might be null.
Cmd.log_format.tag(config=False)
Cmd.log_datefmt.tag(config=False)

## So that dynamic-default rules apply.
#
Cmd.description.default_value = None
Cmd.name.default_value = None

## Expose `raise_config_file_errors` instead of relying only on
#  :envvar:`TRAITLETS_APPLICATION_RAISE_CONFIG_FILE_ERROR`.
Application.raise_config_file_errors.tag(config=True)
Cmd.raise_config_file_errors.help = 'Whether failing to load config files should prevent startup.'



def chain_cmds(app_classes: Sequence[type(Application)],
               argv: Sequence[Text]=None,
               **root_kwds):
    """
    Instantiate(optionally) a list of ``[cmd, subcmd, ...]`` and link each one as child of its predecessor.

    TODO: FIX `chain_cmds()`, argv not working!

    :param argv:
        cmdline args for the the 1st cmd.
        Make sure they do not specify some cub-cmds.
        Do NOT replace with `sys.argv` if none.
        Note: you have to "know" the correct nesting-order of the commands ;-)
    :return:
        the 1st cmd, to invoke :meth:`start()` on it
    """
    if not app_classes:
        raise ValueError("No cmds to chained passed in!")

    app_classes = list(app_classes)
    root = app = None
    for app_cl in app_classes:
        if not isinstance(app_cl, type(Application)):
                    raise ValueError("Expected an Application-class instance, got %r!" % app_cl)
        if not root:
            ## The 1st cmd is always orphan, and gets returned.
            root = app = app_cl(**root_kwds)
        else:
            app.subapp = app = app_cl(parent=app)
        app.initialize(argv or [])

    app_classes[0]._instance=app
    return root

