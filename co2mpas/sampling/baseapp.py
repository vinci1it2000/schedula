#!/usr/bin/env python
#
# Copyright 2014-2016 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
#
"""
A *traitlets*[#]_ framework for building hierarchical cmd-line tools (class:`Cmd`) delegating to backend classes (class:`Spec`).

To run a base command, use this code::

    app = MainCmd.instance(**app_init_kwds)
    app.initialize(argv or None) ## Uses `sys.argv` if `argv` is `None`.
    return app.start()

To run nested commands, use :func:`baseapp.chain_cmds()` like that::

    app = chain_cmds(MainCmd, Project, Project.List)
    return app.start()

## Configuration and Initialization guidelines for *Spec* and *Cmd* classes

0. The configuration of :class:`HasTraits` instance gets stored in its ``config`` attribute.
1. A :class:`HasTraits` instance receives its configuration from 3 sources, in this order:

  a. code specifying class-attributes or running on constructors;
  b. configuration files (*json* or ``.py`` files);
  c. command-line arguments.

2. Constructors must allow for properties to be overwritten on construction; any class-defaults
   must function as defaults for any constructor ``**kwds``.

3. Some utility code depends on trait-defaults (i.e. construction of help-messages), so for certain properties
   (e.g. description), it is preferable to set them as traits-with-defaults on class-attributes.

.. [#] http://traitlets.readthedocs.io/
"""
from collections import OrderedDict
import copy
import io
import logging
import os
from typing import Sequence, Text, Any, Tuple, List  # @UnusedImport

from boltons.setutils import IndexedSet as iset
from ipython_genutils.text import indent, wrap_paragraphs, dedent
from toolz import dicttoolz as dtz, itertoolz as itz

import os.path as osp
import pandalone.utils as pndlu
import traitlets as trt
import traitlets.config as trtc

from . import CmdException
from ..__main__ import init_logging


## INFO: Modify the following variables on a different application.
APPNAME = 'co2dice'
CONF_VAR_NAME = '%s_CONFIG_FILE' % APPNAME.upper()

try:
    _mydir = osp.dirname(__file__)
except:
    _mydir = '.'



def default_config_fname():
    """The config-file's basename (no path or extension) to search when not explicitly specified."""
    return '%s_config' % APPNAME

def default_config_dir():
    """The folder of to user's config-file."""
    return pndlu.convpath('~/.%s' % APPNAME)

def default_config_fpath():
    """The full path of to user's config-file, without extension."""
    return osp.join(default_config_dir(), default_config_fname())


###################
##     Specs     ##
###################

class Spec(trtc.LoggingConfigurable):
    """Common properties for all configurables."""
    ## See module documentation for developer's guidelines.

    @trt.default('log')
    def _log(self):
        return logging.getLogger(type(self).__name__)

    # The log level for the application
    log_level = trt.Enum((0, 10, 20, 30, 40, 50, 'DEBUG', 'INFO', 'WARN', 'ERROR', 'CRITICAL'),
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

    verbose = trt.Union((trt.Integer(0), trt.Bool(False)),
            ## INFO: Add verbose flag explanations here.
            help="""
            Make various sub-commands increase their verbosity (not to be confused with --debug):
            Can be a boolean or 0, 1(==True), 2, ....

            - project list  : List project with the "long" format.
            - project infos : Whether to include also info about the repo-configuration (when 2).
            """).tag(config=True)

    force = trt.Bool(False,
            ## INFO: Add force flag explanations here.
            help="""
            Force various sub-commands perform their duties without complaints.

            - project backup: Whether to overwrite existing archives or to create intermediate folders.
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


def app_short_help(app_class):
    desc = app_class.class_traits().get('description')
    doc = (isinstance(desc, str) and desc
        or (isinstance(app_class.description, str) and app_class.description)
        or app_class.__doc__)
    return pndlu.first_line(doc)

def class2cmd_name(cls):
    name = cls.__name__
    if name.lower().endswith('cmd') and len(name) > 3:
        name = name[:-3]
    return pndlu.camel_to_cmd_name(name)

def build_sub_cmds(*subapp_classes):
    """Builds an ordered-dictionary of ``cmd-name --> (cmd-class, help-msg)``. """

    return OrderedDict((class2cmd_name(sa), (sa, app_short_help(sa)))
                       for sa in subapp_classes)

class Cmd(trtc.Application):
    """Common machinery for all (sub-)commands. """
    ## INFO: Do not use it directly; inherit it.
    # See module documentation for developer's guidelines.

    @trt.default('name')
    def _name(self):
        name = class2cmd_name(type(self))
        return name


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
                p = pndlu.convpath(p)
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
            config_file = pndlu.convpath(config_file)
            if osp.isdir(config_file):
                config_file = osp.join(config_file, default_config_fname())
        config_file = pndlu.ensure_file_ext(config_file, '.py')

        op = 'Over-writting' if osp.isfile(config_file) else 'Writting'
        self.log.info('%s config-file %r...', op, config_file)
        pndlu.ensure_dir_exists(os.path.dirname(config_file), 0o700)
        config_text = self.generate_config_file();
        with io.open(config_file, mode='wt') as fp:
            fp.write(config_text)

    def print_subcommands(self):
        """Print the subcommand part of the help."""
        ## Overridden, to print "default" sub-cmd.
        if not self.subcommands:
            return

        lines = ["Subcommands"]
        lines.append('-' * len(lines[0]))
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

    @trtc.catch_config_error
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

    conf_classes = trt.List(trt.Type(trtc.Configurable), default_value=[],
            help="""
            Any *configurables* found in this prop up the cmd-chain are merged,
            along with any subcommands, into :attr:`classes`.
            """)

    cmd_aliases = trt.Dict({},
            help="Any *flags* found in this prop up the cmd-chain are merged into :attr:`aliases`. """)

    cmd_flags = trt.Dict({},
            help="Any *flags* found in this prop up the cmd-chain are merged into :attr:`flags`. """)

    def my_cmd_chain(self):
        """Return the chain of cmd-classes starting from my self or subapp."""
        cmd_chain = []
        pcl = self.subapp if self.subapp else self
        while pcl:
            cmd_chain.append(pcl)
            pcl = pcl.parent

        return cmd_chain

    @trt.observe('parent', 'conf_classes', 'cmd_aliases', 'cmd_flags', 'subapp', 'subcommands')
    def _inherit_parent_cmd(self, change):
        """ Inherit config-related stuff from up the cmd-chain. """
        if self.parent:
            ## Collect parents, ordered like that:
            #    subapp, self, parent1, ...
            #
            cmd_chain = self.my_cmd_chain()

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

        init_logging(level=log_level)

    def __init__(self, **kwds):
        cls = type(self)
        dkwds = {
            ## Traits defaults are always applied...??
            #
            'description': cls.__doc__,
            'name': class2cmd_name(cls),

            ## Set some nice defaults for root-CMDs.
            #
            'cmd_aliases': {
                'config-files': 'Cmd.config_files',
            },
            'cmd_flags': {
                ('d', 'debug'): ({
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
                ('v', 'verbose'):  ({
                        'Spec': {'verbose': True},
                    },
                    pndlu.first_line(Spec.verbose.help)
                ),
                ('f', 'force'):  ({
                        'Spec': {'force': True},
                    },
                    pndlu.first_line(Spec.force.help)
                )
            },
        }
        dkwds.update(kwds)
        super().__init__(**dkwds)

    def _is_dispatching(self):
        """True if dispatching to another command."""
        return bool(self.subapp)


    @trtc.catch_config_error
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
            return self.run(*self.extra_args)

        return self.subapp.start()

    def run(self, *args):
        """Leaf sub-commands must inherit this instead of :meth:`start()` without invoking :func:`super()`.

        By default, screams about using sub-cmds, or about doing nothing!

        :param args: Invoked by :meth:`start()` with :attr:`extra_args`.
        """
        if self.subcommands:
            cmd_line = ' '.join(cl.name
                                for cl in reversed(self.my_cmd_chain()))
            raise CmdException("Specify one of the sub-commands: "
                               "\n    %s\nor type: \n    %s -h"
                               % (', '.join(self.subcommands.keys()), cmd_line))
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
trtc.Application.raise_config_file_errors.tag(config=True)
Cmd.raise_config_file_errors.help = 'Whether failing to load config files should prevent startup.'



def chain_cmds(app_classes: Sequence[type(trtc.Application)],
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
        if not isinstance(app_cl, type(trtc.Application)):
                    raise ValueError("Expected an Application-class instance, got %r!" % app_cl)
        if not root:
            ## The 1st cmd is always orphan, and gets returned.
            root = app = app_cl(**root_kwds)
        else:
            app.subapp = app = app_cl(parent=app)
        app.initialize(argv or [])

    app_classes[0]._instance = app
    return root

