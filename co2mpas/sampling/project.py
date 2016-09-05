#!/usr/b in/env python
#
# Copyright 2014-2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
#
"""A *project* stores all CO2MPAS files for a single vehicle, and tracks its sampling procedure. """

from collections import (defaultdict, OrderedDict, namedtuple)  # @UnusedImport
from datetime import datetime
import inspect
import io
import logging
import os
from pandalone import utils as pndlutils
import textwrap
from typing import (
    Any, List, Sequence, Iterable, Text, Tuple, Callable)  # @UnusedImport

import git  # From: pip install gitpython
from toolz import itertoolz as itz, dicttoolz as dtz
from traitlets.config import SingletonConfigurable

from co2mpas import __uri__  # @UnusedImport
from co2mpas import utils
from co2mpas._version import (__version__, __updated__, __file_version__,   # @UnusedImport
                              __input_file_version__, __copyright__, __license__)  # @UnusedImport
from co2mpas.sampling import baseapp, dice, report
from co2mpas.sampling.baseapp import convpath, ensure_dir_exists, where
import functools as fnt
import os.path as osp
import traitlets as trt

InvalidProjectState = baseapp.CmdException

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
    ## TODO: Move to dispatcher.

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
        kwds = self.kwds
        out = self.out
        fun = self.fun

        if not isinstance(out, (tuple, list)):
            out = (out, )
        else:
            pass

        inp = kwds.pop('inputs', None)
        if inp is None:
            inp = self.inspect_inputs()

        if not isinstance(inp, (tuple, list)):
            inp = (inp, )
        else:
            pass

        if 'description' not in kwds:
            kwds['function_id'] = '%s:%s%s --> %s' % (fun.__module__, fun.__name__, inp, out)

        return dsp.add_function(inputs=inp,
                                outputs=out,
                                function=fun,
                                **kwds)

    @classmethod
    def add_ufuns(cls, ufuns: Iterable, dsp):#: Dispatcher):
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
CommitMsg = namedtuple('CommitMsg', 'project state msg msg_version')

_PROJECTS_PREFIX = 'projects/'
_HEADS_PREFIX = 'refs/heads/'
_PROJECTS_FULL_PREFIX = _HEADS_PREFIX + _PROJECTS_PREFIX

def _is_proj_ref(ref: git.Reference) -> bool:
    return ref.path.startswith(_PROJECTS_FULL_PREFIX)

def _ref2project(ref: git.Reference) -> Text:
    return ref.path[len(_PROJECTS_FULL_PREFIX):]

def _project2ref_path(project: Text) -> Text:
    if project.startswith(_HEADS_PREFIX):
        pass
    elif not project.startswith('projects/'):
        project = '%s%s' % (_PROJECTS_FULL_PREFIX, project)
    return project

def _project2ref_name(project: Text) -> Text:
    if project.startswith(_HEADS_PREFIX):
        project = project[len(_HEADS_PREFIX):]
    elif not project.startswith('projects/'):
        project = '%s%s' % (_PROJECTS_PREFIX, project)
    return project

def _get_ref(refs, refname: Text, default: git.Reference=None) -> git.Reference:
    return refname and refname in refs and refs[refname] or default



class ProjectsDB(SingletonConfigurable, baseapp.Spec):
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

    def _setup_repo(self, repo_path):
        if self.__repo:
            if self.__repo.working_dir == repo_path:
                self.log.debug('Reusing repo %r...', repo_path)
                return
            else:
                ## Clean up old repo,
                #  or else... https://github.com/gitpython-developers/GitPython/issues/508
                self.__repo.git.clear_cache()

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
            self.log.info("...failed opening repo '%s',\n  initializing a new repo %r instead...",
                          ex, repo_path)
            self.__repo = git.Repo.init(repo_path)
            self._write_repo_configs()

    @trt.observe('repo_path')
    def _repo_path_changed(self, change):
        self.log.debug('CHANGE repo %r-->%r...', change['old'], change['new'])
        self._setup_repo(change['new'])

    @property
    def repo(self):
        if not self.__repo:
            self._setup_repo(self.repo_path)
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

    def read_git_settings(self, prefix: Text=None, config_level: Text=None):# -> List(Text):
        """
        :param prefix:
            prefix of all settings.key (without a dot).
        :param config_level:
            One of: ( system | global | repository )
            If None, all applicable levels will be merged.
            See :meth:`git.Repo.config_reader`.
        :return: a list with ``section.setting = value`` str lines
        """
        settings = defaultdict(); settings.default_factory = defaultdict
        sec = '<not-started>'
        cname = '<not-started>'
        try:
            with self.repo.config_reader(config_level) as conf_reader:
                for sec in conf_reader.sections():
                    for cname, citem in conf_reader.items(sec):
                        s = settings
                        if prefix:
                            s = s[prefix]
                        s[sec][cname] = citem
        except Exception as ex:
            self.log.info('Failed reading git-settings on %s.%s due to: %s',
                     sec, cname, ex, exc_info=1)
            raise
        return settings

    def repo_backup(self, folder: Text='.', repo_name: Text='co2mpas_repo',
                    force: bool=None) -> Text:
        """
        :param folder: The path to the folder to store the repo-archive in.
        :return: the path of the repo-archive
        """
        import tarfile

        if force is None:
            force = self.force

        now = datetime.now().strftime('%Y%m%d-%H%M%S%Z')
        repo_name = '%s-%s' % (now, repo_name)
        repo_name = pndlutils.ensure_file_ext(repo_name, '.txz')
        repo_name_no_ext = osp.splitext(repo_name)[0]
        archive_fpath = convpath(osp.join(folder, repo_name))
        basepath, _ = osp.split(archive_fpath)
        if not osp.isdir(basepath) and not force:
            raise FileNotFoundError(basepath)
        ensure_dir_exists(basepath)

        self.log.debug('Archiving repo into %r...', archive_fpath)
        with tarfile.open(archive_fpath, "w:xz") as tarfile:
            tarfile.add(self.repo.working_dir, repo_name_no_ext)

        return archive_fpath

    @fnt.lru_cache() # x6(!) faster!
    def _infos_dsp(self, fallback_value='<invalid>'):
        from co2mpas.dispatcher import Dispatcher

        ufuns = [
            UFun('repo',            lambda _infos: self.repo),
            UFun('git_cmds',        lambda _infos: where('git')),
            UFun('dirty',           lambda repo: repo.is_dirty()),
            UFun('untracked',       lambda repo: repo.untracked_files),
            UFun('wd_files',        lambda repo: os.listdir(repo.working_dir)),
            UFun('branch',          lambda repo, _inp_prj:
                                        _inp_prj and _get_ref(repo.heads, _project2ref_path(_inp_prj)) or repo.active_branch),
            UFun('head',            lambda repo: repo.head),
            UFun('heads_count',     lambda repo: len(repo.heads)),
            UFun('projects_count',  lambda repo: itz.count(self._yield_project_refs())),
            UFun('tags_count',      lambda repo: len(repo.tags)),
            UFun('git_version',     lambda repo: '.'.join(str(v) for v in repo.git.version_info)),
            UFun('git_settings',    lambda repo: self.read_git_settings()),

            UFun('head_ref',      lambda head: head.reference),
            UFun('head_valid',      lambda head: head.is_valid()),
            UFun('head_detached',   lambda head: head.is_detached),

            UFun('cmt',             lambda branch: branch.commit),
            UFun('head',            lambda branch: branch.path),
            UFun('branch_valid',    lambda branch: branch.is_valid()),
            UFun('branch_detached', lambda branch: branch.is_detached),

            UFun('tre',             lambda cmt: cmt.tree),
            UFun('author',          lambda cmt: '%s <%s>' % (cmt.author.name, cmt.author.email)),
            UFun('last_cdate',      lambda cmt: str(cmt.authored_datetime)),
            UFun('commit',          lambda cmt: cmt.hexsha),
            UFun('revs_count',      lambda cmt: itz.count(cmt.iter_parents())),
            UFun('cmsg',            lambda cmt: cmt.message),
            UFun('cmsg',            lambda cmt: '<invalid: %s>' % cmt.message, weight=10),

            UFun(['msg.%s' % f for f in CommitMsg._fields],
                                    lambda cmsg: self._parse_commit_msg(cmsg) or
                                    ('<invalid>', ) * len(CommitMsg._fields)),

            UFun('tree',            lambda tre: tre.hexsha),
            UFun('files_count',     lambda tre: itz.count(tre.list_traverse())),
        ]
        dsp = Dispatcher()
        UFun.add_ufuns(ufuns, dsp)
        return dsp

    @fnt.lru_cache()
    def _out_fields_by_verbose_level(self, level):
        """
        :param level:
            If ''> max-level'' then max-level assumed, negatives fetch no fields.
        """
        verbose_levels = {
            0:[
                'msg.project',
                'msg.state',
                'msg.msg',
                'revs_count',
                'files_count',
                'last_cdate',
                'author',
            ],
            1: [
                'infos',
                'cmsg',
                'head',
                'dirty',
                'commit',
                'tree',
                'repo',
            ],
            2: None,  ## null signifies "all fields".
        }
        max_level = max(verbose_levels.keys())
        if level > max_level:
            level = max_level
        fields = []
        for l  in range(level + 1):
            fs = verbose_levels[l]
            if not fs:
                return None
            fields.extend(fs)
        return fields

    def _infos_fields(self, project: Text=None, fields: Sequence[Text]=None, inv_value=None) -> List[Tuple[Text, Any]]:
        """Runs repo examination code returning all requested fields (even failed ones)."""
        dsp = self._infos_dsp()
        inputs = {'_infos': 'ok', '_inp_prj': project}
        infos = dsp.dispatch(inputs=inputs,
                             outputs=fields,
                             shrink=True)
        fallbacks = {d: inv_value for d in dsp.data_nodes.keys()}
        fallbacks.update(infos)
        infos = fallbacks

        infos = dict(utils.stack_nested_keys(infos))
        infos = dtz.keymap(lambda k: '.'.join(k), infos)
        if fields:
            infos = [(f, infos.get(f, inv_value))
                     for f in fields]
        else:
            infos = sorted((f, infos.get(f, inv_value))
                           for f in dsp.data_nodes.keys())

        return infos

    def proj_current(self) -> Text or None:
        """Returns the current project, or None if not exists yet."""
        # XXX: REWORK PROJECT VALIDATION
        project = None
        try:
            head = self.repo.active_branch
            project = _ref2project(head)
            self.is_project(project, validate=True)
        except Exception as ex:
            self.log.warning("Failure while getting current-project: %s",
                             ex, exc_info=1)
        return project

    def is_project(self, project: Text, validate=False):
        """
        :param project: some branch ref
        """
        # XXX: REWORK PROJECT VALIDATION
        repo = self.repo
        project = _project2ref_name(project)
        found = project in repo.heads
        if found and validate:
            ref = repo.heads[project]
            found = bool(self._parse_commit_msg(ref.commit.message))
        return found

    def _state(self, project: Text=None) -> Text:
        # XXX: REWORK PROJECT VALIDATION
        infos = self._infos_fields(project, fields=('msg.state', ))
        return dict(infos)['msg.state']

    def proj_examine(self, project=None, verbose=None, as_text=False, as_json=False):
        """
        :param project: use current branch if unspecified.
        :retun: text message with infos.
        """
        # XXX: REWORK PROJECT VALIDATION
        import json

        if verbose is None:
            verbose = self.verbose
        verbose_level = int(verbose)

        fields = self._out_fields_by_verbose_level(verbose_level)
        infos = self._infos_fields(project, fields)

        if as_text:
            if as_json:
                infos = json.dumps(dict(infos), indent=2, default=str)
            else:
                #import pandas as pd
                #infos = pd.Series(OrderedDict(infos))
                infos = baseapp.format_pairs(infos)

        return infos

    def _yield_project_refs(self, *projects):
        if projects:
            projects =  [_project2ref_path(p) for p in projects]
        for ref in self.repo.heads:
            if _is_proj_ref(ref) and not projects or ref.path in projects:
                yield ref

    def proj_list(self, *projects: str, verbose=None, as_text=False):
        """
        :param projects: some branch ref, or none for all
        :param verbose: return infos in a table with 3-4 coulmns per each project
        :retun: yield any match projects, or all if `projects` were empty.
        """
        import pandas as pd
        if verbose is None:
            verbose = self.verbose

        res = {}
        for ref in self._yield_project_refs(*projects):
            project = _ref2project(ref)
            infos = []
            if verbose:
                infos = OrderedDict(self._infos_fields(
                        project=project,
                        fields='msg.state revs_count files_count last_cdata author msg.msg'.split(),
                        inv_value='<invalid>'))
            res[project] = infos

        if not res:
            res = None
        else:
            ap = self.repo.active_branch
            ap = ap and ap.path
            if verbose:
                res = pd.DataFrame.from_dict(res, orient='index')
                res = res.sort_index()
                res.index = [('* %s' if _project2ref_path(r) == ap else '  %s') % r
                             for r in res.index]
                res.reset_index(level=0, inplace=True)
                renner = lambda c: c[len('msg.'):] if c.startswith('msg.') else c
                res = res.rename_axis(renner, axis='columns')
                res = res.rename_axis({
                    'index': 'project',
                    'revs_count': '#revs',
                    'files_count': '#files'
                }, axis='columns')
                if as_text:
                    res = res.to_string(index=False)
            else:
                res = [('* %s' if _project2ref_path(r) == ap else '  %s') % r
                for r in sorted(res)]

        return res

    def _make_commit_msg(self, project, state, msg):
        import json
        msg = '\n'.join(textwrap.wrap(msg, width=50))
        return json.dumps(CommitMsg(project, state, msg, PROJECT_VERSION)._asdict())

    def _parse_commit_msg(self, msg, scream=False):
        """
        :return: a :class:`CommitMsg` instance, or `None` if cannot parse.
        """
        import json

        try:
            return json.loads(msg,
                    object_hook=lambda seq: CommitMsg(**seq))
        except Exception as ex:
            if scream:
                raise
            else:
                self.log.warn('Found the non-project commit-msg in project-db'
                       ', due to: %s\n %s', ex, msg, exc_info=1)

    def _commit(self, index, project, state, msg):
        index.commit(self._make_commit_msg(project, state, msg))

    def _make_readme(self, project):
        return textwrap.dedent("""
        This is the CO2MPAS-project %r (see https://co2mpas.io/ for more).

        - created: %s
        """ %(project, datetime.now()))

    def proj_add(self, project: str):
        """
        :param project: some branch ref
        """
        self.log.info('Creating project %r...', project)
        repo = self.repo
        if self.is_project(project):
            raise baseapp.CmdException('Project %r already exists!' % project)
        if not project or not project.isidentifier():
            raise baseapp.CmdException('Invalid name %r for a project!' % project)

        ref_name = _project2ref_name(project)
        repo.git.checkout(ref_name, orphan=True)

        index = repo.index
        state_fpath = osp.join(repo.working_tree_dir, 'CO2MPAS')
        with io.open(state_fpath, 'wt') as fp:
            fp.write(self._make_readme(project))
        index.add([state_fpath])
        self._commit(index, project, 'empty', 'Project created.')

    def proj_open(self, project: Text):
        """
        :param project: some branch ref
        """
        if not self.is_project(project, validate=True):
            raise baseapp.CmdException('Project %r not found!' % project)
        self.repo.heads[_project2ref_name(project)].checkout()

    def iofiles_list(self) -> dice.IOFiles or None:
        """Works on current project."""
        repo = self.repo
        project = self.proj_current() # XXX: REWORK PROJECT VALIDATION
        def collect_io_files(io_kind):
            if io_kind:
                wd_fpath = osp.join(repo.working_tree_dir, io_kind)
                fpaths = os.listdir(wd_fpath) if osp.isdir(wd_fpath) else []
                return [osp.join(wd_fpath, f) for f in fpaths]

        iofpaths = [collect_io_files(io_kind) for io_kind in ('inp', 'out', None)]
        if any(iofpaths):
            return dice.IOFiles(*iofpaths)

    def iofiles_import(self, iofiles: dice.IOFiles, force=None):
        """Works on current project."""
        import shutil

        def raise_invalid_state(state, project):
            raise InvalidProjectState(
                    "Invalid state %r when importing input/output-files in project %r!"
                    "\n  Must be in one of: empty | stored-out | stored-inp (or `stored` when --force)."
                    % (state, project))

        if force is None:
            force = self.force

        repo = self.repo
        project = self.proj_current() # XXX: REWORK PROJECT VALIDATION
        state = self._state()
        if state not in ('empty', 'stored-out', 'stored-inp', 'stored'):
            raise_invalid_state(state, project)

        valid_io_kinds = []
        if state in ('empty', 'stored-out'):
            valid_io_kinds.append('inp')
        if state in ('empty', 'stored-inp'):
            valid_io_kinds.append('out')

        index = repo.index
        nimported = 0
        for io_kind, fpaths in iofiles._asdict().items():
            for fpath in fpaths:
                assert io_kind != 'other', "Other-files: %s" % iofiles.other
                assert fpath, "Import none as %s file!" % io_kind

                if not force and io_kind not in valid_io_kinds:
                    raise_invalid_state(state, project)
                fdir, fname = osp.split(fpath)
                wd_fpath = osp.join(repo.working_tree_dir, io_kind, fname)
                ensure_dir_exists(osp.split(wd_fpath)[0])
                shutil.copy(fpath, wd_fpath)
                index.add([wd_fpath])
                nimported += 1

        self._commit(index, project, state, 'Imported %d IO-files.' % nimported)



###################
##    Commands   ##
###################

class _PrjCmd(baseapp.Cmd):
    @property
    def projects_db(self):
        p = ProjectsDB.instance()
        p.config = self.config
        return p


class ProjectCmd(_PrjCmd):
    """
    Commands to administer the storage repo of TA *projects*.

    A *project* stores all CO2MPAS files for a single vehicle,
    and tracks its sampling procedure.
    """

    examples = trt.Unicode("""
        To get the list with the status of all existing projects, try:

            co2dice project list
        """)


    class ListCmd(_PrjCmd):
        """
        SYNTAX
            co2dice project list [<project-1>] ...
        DESCRIPTION
            List specified projects, or all, if none specified.
            Use --verbose to view more infos about the projects, or use the `examine` cmd
            to view even more details for a specific project.
        """
        def run(self, *args):
            self.log.info('Listing %s projects...', args or 'all')
            return self.projects_db.proj_list(*args)


    class CurrentCmd(_PrjCmd):
        """Prints the currently open project."""
        def run(self, *args):
            if len(args) != 0:
                raise baseapp.CmdException('Cmd %r takes no arguments, received %r!'
                                   % (self.name, args))
            project = self.projects_db.proj_current()
            if not project:
                raise baseapp.CmdException(
                        "No current-project exists yet!"
                        "\n  Use `co2mpas project add <project-name>` to create one.")
            return project


    class OpenCmd(_PrjCmd):
        """
        SYNTAX
            co2dice project open <project>
        DESCRIPTION
            Make an existing project as *current*.
        """
        def run(self, *args):
            self.log.info('Opening project %r...', args)
            if len(args) != 1:
                raise baseapp.CmdException("Cmd %r takes a SINGLE project-name as argument, received: %r!"
                                   % (self.name, args))
            return self.projects_db.proj_open(args[0])

    class AddCmd(_PrjCmd):
        """
        SYNTAX
            co2dice project add <project>
        DESCRIPTION
            Create a new project.
        """
        def run(self, *args):
            if len(args) != 1:
                raise baseapp.CmdException('Cmd %r takes a SINGLE project-name as argument, received %r!'
                                   % (self.name, args))
            return self.projects_db.proj_add(args[0])


    class AddReportCmd(_PrjCmd):
        """
        SYNTAX
            co2dice project add-report ( inp=<co2mpas-file-1> | out=<co2mpas-file-1> ) ...
        DESCRIPTION
            Import the specified input/output co2mpas files into the *current project*.

            The *report parameters* will be time-stamped and disseminated to
            TA authorities & oversight bodies with an email, to receive back
            the sampling decision.

            - One file from each kind (inp/out) may be given.
            - If an input/output is already present in the current project, use --force.

        """

        examples = trt.Unicode("""
            To import an INPUT co2mpas file, try:

                co2dice project add-report  inp=co2mpas_input.xlsx

            To import both INPUT and OUTPUT files, and overwrite any already imported try:

                co2dice project add-report --force inp=co2mpas_input.xlsx out=co2mpas_results.xlsx
            """)

        __report = None

        @property
        def report(self):
            if not self.__report:
                self.__report = report.Report(config=self.config)
            return self.__report

        def run(self, *args):
            self.log.info('Importing report files %s...', args)
            if len(args) < 1:
                raise baseapp.CmdException('Cmd %r takes at least one argument, received %d: %r!'
                                   % (self.name, len(args), args))
            rep = self.report
            iofiles = rep.parse_io_args(*args)
            if iofiles.other:
                raise baseapp.CmdException(
                    "Cmd %r filepaths must either start with 'inp=' or 'out=' prefix!\n%s"
                                       % (self.name, '\n'.join('  arg[%d]: %s' % i for i in iofiles.other.items())))

            ## Check extraction of report.
            #
            fpath = None
            try:
                for fpath in iofiles.inp:
                    rep.extract_input_params(fpath)

                for fpath in iofiles.out:
                    list(rep.extract_output_tables(fpath))
            except Exception as ex:
                msg = "Failed extracting report-parameters from file %r, due to: %s"
                self.log.debug(msg, fpath, ex, exc_info=1)
                raise baseapp.CmdException(msg % (fpath, ex))

            return self.projects_db.iofiles_import(iofiles)


    class ExamineCmd(_PrjCmd):
        """
        SYNTAX
            co2dice project examine [<project>]
        DESCRIPTION
            Print various information about the specified project, or the current-project,
            if none specified.
            Use --verbose to view more infos, including about the repository as a whole.
        """
        as_json = trt.Bool(False,
                help="Whether to return infos as JSON, instead of python-code."
                ).tag(config=True)

        def run(self, *args):
            if len(args) > 1:
                raise baseapp.CmdException('Cmd %r takes one optional argument, received %d: %r!'
                                   % (self.name, len(args), args))
            project = args and args[0] or None
            return self.projects_db.proj_examine(project, as_text=True, as_json=self.as_json)


    class BackupCmd(_PrjCmd):
        """
        SYNTAX
            co2dice project backup [<archive-path>]
        DESCRIPTION
            Backup projects repository into the archive filepath specified, or current-directory,
            if none specified.
        """
        def run(self, *args):
            self.log.info('Archiving repo into %r...', args)
            if len(args) > 1:
                raise baseapp.CmdException('Cmd %r takes one optional argument, received %d: %r!'
                                   % (self.name, len(args), args))
            archive_fpath = args and args[0] or None
            kwds = {}
            if archive_fpath:
                base, fname = osp.split(archive_fpath)
                if base:
                    kwds['folder'] = base
                if fname:
                    kwds['repo_name'] = fname
            try:
                return self.projects_db.repo_backup(**kwds)
            except FileNotFoundError as ex:
                raise baseapp.CmdException("Folder '%s' to store archive does not exist!"
                                   "\n  Use --force to create it." % ex)


    def __init__(self, **kwds):
        with self.hold_trait_notifications():
            dkwds = {
                'conf_classes': [ProjectsDB],
                'subcommands': baseapp.build_sub_cmds(*project_subcmds),
                #'default_subcmd': 'current', ## Does not help the user.
                'cmd_flags': {
                    'reset-git-settings': ({
                            'ProjectsDB': {'reset_settings': True},
                        }, ProjectsDB.reset_settings.help),
                    'as-json': ({
                            'ExamineCmd': {'as_json': True},
                        }, ProjectCmd.ExamineCmd.as_json.help),
                }
            }
            dkwds.update(kwds)
            super().__init__(**dkwds)

project_subcmds = (ProjectCmd.ListCmd, ProjectCmd.CurrentCmd, ProjectCmd.OpenCmd, ProjectCmd.AddCmd,
                   ProjectCmd.ExamineCmd, ProjectCmd.BackupCmd)

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
        [dice.MainCmd, ProjectCmd, ProjectCmd.ListCmd],
        config=c))#argv=['project_foo']))
