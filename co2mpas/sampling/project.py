#!/usr/b in/env python
#
# Copyright 2014-2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
#
"""co2dice: prepare/sign/send/receive/validate/archive Type Approval sampling emails of *co2mpas*."""
# TODO: to move to pandalone.

from collections import (
    OrderedDict, namedtuple)  # @UnusedImport
import copy
from datetime import datetime
import inspect
import io
import json
import logging
import textwrap
from typing import (
    List, Sequence, Iterable, Text, Tuple, Callable)  # @UnusedImport

from boltons.setutils import IndexedSet as iset
import git  # From: pip install gitpython
from toolz import itertoolz as itz, dicttoolz as dtz
from traitlets.config import SingletonConfigurable

from co2mpas import __uri__  # @UnusedImport
from co2mpas._version import (__version__, __updated__, __file_version__,   # @UnusedImport
                              __input_file_version__, __copyright__, __license__)  # @UnusedImport
from co2mpas.dispatcher import Dispatcher
from co2mpas.sampling import dice, baseapp
from co2mpas.sampling.baseapp import convpath, ensure_dir_exists, where
import os.path as osp
import traitlets as trt


log = logging.getLogger(__name__)

try:
    _mydir = osp.dirname(__file__)
except:
    _mydir = '.'

CmdException = trt.TraitError
ProjectNotFoundException = trt.TraitError




class UFun(object):
    """
     A 3-tuple ``(out, fun, **kwds)``, used to prepare a list of calls to :meth:`Dispatcher.add_function()`.

     The workhorse is the :meth:`addme()` which delegates to :meth:`Dispatcher.add_function():

       - ``out``: a scalar string or a string-list that, sent as `output` arg,
       - ``fun``: a callable, sent as `function` args,
       - ``kwds``: any keywords of :meth:`Dispatcher.add_function()`.
       - Specifically for the 'inputs' argument, if present in `kwds`, use them
         (a scalar-string or string-list type, possibly empty), else inspect function;
         in any case wrap the result in a tuple (if not already a list-type).

         NOTE: Inspection works only for regular args, no ``*args, **kwds`` supported,
         and they will fail late, on :meth:`addme()`, if no `input` or `inp` defined.

    Example::

        ufuns = [
            UFun('res', lambda num: num * 2),
            UFun('res2', lambda num, num2: num + num2, weight=30),
            UFun(out=['nargs', 'res22'],
                 fun=lambda *args: (len(args), args),
                 inp=('res', 'res1')
            ),
        ]
    """
    def __init__(self, out, fun, inputs=None, **kwds):
        self.out = out
        self.fun = fun
        if inputs is not None:
            kwds['inputs'] = inputs
        self.kwds = kwds
        assert 'outputs' not in kwds and 'function' not in kwds, self

    def __repr__(self, *args, **kwargs):
        kwds = dtz.keyfilter(lambda k: k not in ('fun', 'out'), self.kwds)
        return 'UFun(%r, %r, %s)' % (
            self.out,
            self.fun,
            ', '.join('%s=%s' %(k, v) for k, v in kwds.items()))

    def copy(self):
        cp = UFun(**vars(self))
        cp.kwds = dict(self.kwds)
        return cp

    def inspect_inputs(self):
        fun_params = inspect.signature(self.fun).parameters
        assert not any(p.kind for p in fun_params.values()
                       if p.kind != inspect.Parameter.POSITIONAL_OR_KEYWORD), (
                           "Found '*args or **kwds on function!", self)
        return tuple(fun_params.keys())

    def addme(self, dsp):
        out = self.out
        if not isinstance(out, (tuple, list)):
            out = (out, )

        inp = self.kwds.pop('inputs', None)
        if inp is None:
            inp = self.inspect_inputs()

        if not isinstance(inp, (tuple, list)):
            inp = (inp, )

        return dsp.add_function(inputs=inp,
                                outputs=out,
                                function=self.fun,
                                **self.kwds)

    @classmethod
    def add_ufuns(cls, ufuns: Iterable, dsp: Dispatcher):
        for uf in ufuns:
            try:
                uf.addme(dsp)
            except Exception as ex:
                raise ValueError("Failed adding ufun %s due to: %s: %s"
                                 % (uf, type(ex).__name__, ex)) from ex


###################
##     Specs     ##
###################

PROJECT_VERSION = '0.0.1'  ## TODO: Move to `co2mpas/_version.py`.
PROJECT_STATUSES = '<invalid> empty full signed dice_sent sampled'.split()
CommitMsg = namedtuple('CommitMsg', 'project state msg format_version')

def _get_ref(refs, ref, default=None):
    return ref and ref in refs and refs[ref] or default


class GitSpec(SingletonConfigurable, baseapp.Spec):
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
            """.format(confdir=baseapp.default_config_dir())).tag(config=True)
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

    __repo = None

    @property
    def repo(self):
        if not self.__repo:
            repo_path = self.repo_path
            if not osp.isabs(repo_path):
                repo_path = osp.join(baseapp.default_config_dir(), repo_path)
            repo_path = convpath(repo_path)
            ensure_dir_exists(repo_path)
            try:
                self.log.debug('Opening repo %r...', repo_path)
                self.__repo = git.Repo(repo_path)
                if self.reset_settings:
                    self.log.info('Resetting to default settings of repo %r...',
                                  self.__repo.git_dir)
                    self._write_repo_configs()
            except git.InvalidGitRepositoryError as ex:
                self.log.info("...failed opening repo '%s', initializing a new repo %r...",
                              ex, repo_path)
                self.__repo = git.Repo.init(repo_path)
                self._write_repo_configs()
        return self.__repo

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
                self.log.warn('Found the non-project commit-msg in project-db'
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

    def proj_add(self, projname: str):
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

    def proj_open(self, projname: str):
        """
        :param projname: some branch ref
        """
#         self.log.info('Archiving repo into %r...', projname)
#         with io.open(convpath(projname, 0, 0), 'wb') as fd:
#             self.repo.archive(fd)
#         return
        self.log.info('Opening project %r...', projname)
        if not self.exists(projname):
            raise CmdException('Project %r not found!' % projname)
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

    def read_git_settings(self, prefix: Text='', config_level: Text=None):# -> List(Text):
        """
        :param prefix:
            prefix of all settings.key (better end with a dot).
        :param config_level:
            One of: ( system | global | repository )
            If None, all applicable levels will be merged.
            See :meth:`git.Repo.config_reader`.
        :return: a list with ``section.setting = value`` str lines
        """
        settings = []
        sec = '<not-started>'
        cname = '<not-started>'
        try:
            with self.repo.config_reader(config_level) as conf_reader:
                for sec in conf_reader.sections():
                    for cname, citem in conf_reader.items(sec):
                        settings.append('%s%s.%s = %s' % (prefix, sec, cname, citem))
        except Exception as ex:
            log.warn('Failed reading git-settings on %s.%s due to: %s',
                     sec, cname, ex, exc_info=1)
        return settings

    def infos(self, project=None, verbose=None, as_text=False, as_json=False):
        """
        :param project: use current branch if unspecified.
        :retun: text message with infos.
        """
        if verbose is None:
            verbose = self.verbose

        ufuns = {
            UFun('repo',         lambda infos: self.repo),
            UFun('git_cmds',     lambda infos: where('git')),
            UFun('exec_version', lambda repo: '.'.join(str(v) for v in repo.git.version_info)),
            UFun('heads_count',  lambda repo: len(repo.heads)),
            UFun('projects_count',  lambda repo: itz.count(self._yield_projects())),
            UFun('tags_count',   lambda repo: len(repo.tags)),
            UFun('git_settings', lambda repo: self.read_git_settings(prefix='settings.')),
            UFun('ref',          lambda repo: _get_ref(repo.heads, project, repo.active_branch)),
            UFun('dirty',        lambda repo: repo.is_dirty()),

            UFun('cmt',          lambda ref: ref.commit),

            UFun('tree',         lambda cmt: cmt.tree),
            UFun('author',       lambda cmt: '%s <%s>' % (cmt.author.name, cmt.author.email)),
            UFun('last_cdate',   lambda cmt: str(cmt.authored_datetime)),
            UFun('commit_SHA',   lambda cmt: cmt.hexsha),
            UFun('revs_count',   lambda cmt: itz.count(cmt.iter_parents())),
            UFun('cmsg',         lambda cmt: cmt.message),
            UFun('cmsg',         lambda cmt: '<invalid: %s>' % cmt.message, weight=10),

            UFun(CommitMsg._fields, lambda cmsg: list(self._parse_commit_msg(cmsg))),

            UFun('tree_SHA',     lambda tree: tree.hexsha),
            UFun('files_count',  lambda tree: itz.count(tree.list_traverse())),
        }


        to_hide = ['files_count']
        fallback_value = '<invalid>'
        def filter_fun(ufun:UFun) -> Tuple:
            """
            Duplicate `ufun` as "fallback" one, or hide it.

            :return: either ``(<original-ufun>, <failback-ufun>)``, or ``()`` when hidden
            """
            if ufun.out in to_hide:
                return ()

            fail_ufun = ufun.copy()
            fail_ufun.kwds['weight'] = 50

            ## Handle functions with multiple outputs.
            #
            out = ufun.out
            if isinstance(out, (list, tuple)) and len(out):
                fvalue = (fallback_value, ) * len(out)
            else:
                fvalue = fallback_value

            fail_ufun.fun = lambda *a, **k: fvalue
            fail_ufun.kwds['inputs'] = ufun.inspect_inputs() # Pin inputs.

            return (ufun, fail_ufun)

        fault_tolerant_ufuns = itz.concat(filter_fun(uf) for uf in ufuns)
        d = Dispatcher()
        UFun.add_ufuns(fault_tolerant_ufuns, d)
        infos = d.dispatch(inputs={'infos': 'ok'})

        if as_text:
            import pprint
            infos = pprint.pprint(infos)
        elif as_json:
            infos = json.dumps(infos, indent=2, default=str)

        return infos



###################
##    Commands   ##
###################

class Project(baseapp.Cmd):
    """
    Administer the storage repo of TA *projects*.

    A *project* stores all CO2MPAS files for a single vehicle,
    and tracks its sampling procedure.
    """

    examples = trt.Unicode("""
        To get the list with the status of all existing projects, try:

            co2dice project list
        """)


    class _SubCmd(baseapp.Cmd):
        @property
        def gitspec(self):
            return GitSpec.instance(parent=self)

    class Add(_SubCmd):
        """Add a new project."""
        def run(self):
            if len(self.extra_args) != 1:
                raise CmdException('Cmd %r takes a SINGLE project-name to add, recieved %r!'
                                   % (self.name, self.extra_args))
            return self.gitspec.proj_add(self.extra_args[0])

    class Open(_SubCmd):
        """Make an existing project the *current*.  Returns the *current* if no args specified."""
        def run(self):
            if len(self.extra_args) != 1:
                raise CmdException("Cmd %r takes a SINGLE project-name to open, received: %r!"
                                   % (self.name, self.extra_args))
            return self.gitspec.proj_open(self.extra_args[0])

    class List(_SubCmd):
        """List information about the specified projects (or all if no projects specified)."""
        def run(self):
            return self.gitspec.list(*self.extra_args)

    class Infos(_SubCmd):
        """Print a text message with current-project, status, and repo-config data if --verbose."""

        as_json = trt.Bool(False,
                help="Whether to return infos as JSON, instead of python-code."
                ).tag(config=True)

        def run(self):
            if len(self.extra_args) != 0:
                raise CmdException('Cmd %r takes no args, received %r!'
                                   % (self.name, self.extra_args))
            return self.gitspec.infos(as_text=True, as_json=self.as_json)


    def __init__(self, **kwds):
        with self.hold_trait_notifications():
            super().__init__(**kwds)
            self.conf_classes = [GitSpec]
            self.subcommands = baseapp.build_sub_cmds(Project.Infos, Project.Add, Project.Open, Project.List)
            self.default_subcmd = 'infos'
            self.cmd_flags = {
                'reset-git-settings': ({
                        'GitSpec': {'reset_settings': True},
                    }, GitSpec.reset_settings.help),
                'as-json': ({
                        'Infos': {'as_json': True},
                    }, Project.Infos.as_json.help),
            }


if __name__ == '__main__':
    from traitlets.config import get_config
    # Invoked from IDEs, so enable debug-logging.
    c = get_config()
    c.Application.log_level=0
    #c.Spec.log_level='ERROR'

    argv = None
    ## DEBUG AID ARGS, remember to delete them once developed.
    #argv = ''.split()
    #argv = '--debug'.split()

    dice.run_cmd(baseapp.chain_cmds(
        [dice.Main, Project, Project.List],
        config=c))#argv=['project_foo']))
