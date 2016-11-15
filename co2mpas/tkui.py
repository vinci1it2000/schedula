#!/usr/bin/env/python
#-*- coding: utf-8 -*-
#
# Copyright 2013-2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
"""
CO2MPAS UI: predict NEDC CO2 emissions from WLTP for Vehicle Type-Approval.

Layout::

    ######################################################################################################
    #:  ______________________________               :  ______________________________                  :#
    #: |                              |              : |_________(Output dir)_________| [ Set Out Dir ] :#
    #: |                              | [Add files ] :  ______________________________                  :#
    #: |                              |              : |________(Template file________| [Set Template ] :#
    #: |                              | [Add folder] :                                                  :#
    #: |                              |              : [flag-1] [flag-2] [flag-3] [flag-4]              :#
    #: |                              | [ Del item ] :  ______________________________________________  :#
    #: |___________(inputs)___________|              : |_________________(extra flags)________________| :#
    #:                                               :                                                  :#
    #: [ Help ]     [ Run-1 ]  ...             [ Run-2]
    #: [ PROGRESS BAR ...]
    #+--------------------------------------------------------------------------------------------------:#
    #:  ______________________________________________________________________________________________  :#
    #: |                                                                                              | :#
    #: |                                                                                              | :#
    #: |________________________________________(log_frame)___________________________________________| :#
    ######################################################################################################

"""
## TODO: 5-Nov-2016
#  - Add popup-menus on filelists (copy).
#  - Co2mpas tab:    1: add [gen-input template] button
#                    2: link to sync-tab
#                    3: rest
#  - Datasync frame:
#        [gen-file] [sync-temple-entry][sel]
#        [   help   ] [        run         ]
#  - Improve extra-options parsing...

## Help (apart from PY-site):
#  - http://effbot.org/tkinterbook/tkinter-index.htm
#  - http://www.tkdocs.com/
#  - http://infohost.nmt.edu/tcc/help/pubs/tkinter/web/index.html

## Icons from:
#    - http://www.iconsdb.com/red-icons/red-play-icons.html
#    - https://material.io/icons/#

from collections import Counter, OrderedDict, namedtuple, ChainMap
import datetime
from idlelib.ToolTip import ToolTip
import io
import logging
import os
from pandalone import utils as putils
from queue import Queue
import random
import re
import sys
from textwrap import dedent, indent
from threading import Thread
from tkinter import StringVar, ttk, filedialog
import traceback
from typing import Any, Union, Mapping, Text  # @UnusedImport
import weakref
import webbrowser

from PIL import Image, ImageTk
import docopt
from toolz import dicttoolz as dtz
import yaml

from co2mpas import (__main__ as cmain, __version__,
                     __updated__, __copyright__, __license__, __uri__)  # @UnusedImport
from co2mpas import datasync
import co2mpas.batch as cbatch
from co2mpas.utils import stds_redirected, parse_key_value_pair
import functools as fnt
import os.path as osp
import pkg_resources as pkg
import tkinter as tk


log = logging.getLogger('tkui')

app_name = 'co2mpas'
user_guidelines_url = 'https://co2mpas.io'
MOTDs = dedent("""\
    Select Input files/folders and run them.  Read tooltips for help.
    Double-click on file-paths to open them (as explained in it's tooltip).
    [Ctrl-A]: select all files in a list;  [Delete]: delete selected all files in list.
    Try the `Run` button first and check the results;  then `Run TA` and re-check them.
    Use [Tab] to navigate to the next field/button; [Space] clicks buttons.
    You cannot `Run TA` when the `Advanced` options are active.
    User mouse's [Right button] to clear the log messages from the popup-menu.
    You may view more log-messages by Right-cliking on them and setting "Log Threshold | Debug".
    Ensure you run the latest CO2MPAS;\
  click the `About CO2MPAS` menu-item and compare its version with the site's.
    Synchronized *appropriately* the time-series before launching CO2MPAS.
""")[:-1].split('\n')


@fnt.lru_cache()
def define_tooltips():
    all_tooltips = """
        inp_files_tree: |-
            Populate this list with CO2MPAS Input files & folders using the buttons to the right.
            - Double-click on each file/folder to open it.
        download_tmpl_file_btn: |-
            Opens a File-dialog to save a new Input Template file,
            to be added into the Inputs-list to the left.
        add_inp_files_btn: |-
            Opens a File-dialog to select existing CO2MPAS Excel Input file(s)
            to be added into the Inputs-list to the left.
        add_inp_folder_btn: |-
            Opens a Folder-dialog to select a Folder with CO2MPAS Input files,
            to be added into the Inputs-list to the left.
        del_inp_btn: |-
            Deletes selected items from the list o Input files & folders to the left.
            - Pressing [Delete] key on selected items also removes them from the list.

        out_folder_entry: |-
            Select the folder to write the Output files using the button to the right.
            - CO2MPAS will save there results with the date and time appended in their filenames.
            - If feld is not empty, double-click to open and inspect the specified folder.
        sel_out_folder_btn: |-
            Opens a Folder-dialog to select the Output Folder for the field to the left.

        advanced_link: |-
            Options and flags incompatible with DECLARATION mode (started with the Run TA button).
            These may be useful for engineering and experimentation purposes, and for facilitating running batches.
        out_template_entry: |-
            Select a pre-populated Excel file to clone and append CO2MPAS results into it.
            By default, results are appended into an empty excel-file.
            - If field is not empty, double-click to open the specified folder.
            - Use a dash('-') to have CO2MPAS clone the Input-file and use it as template;
        sel_tmpl_file_btn: |-
            Opens a File-dialog to select an existing Excel Output Template file
            for the field to the left.

        help_btn: |-
            Opens the CO2MPAS site in a browser.
        run_batch_btn: |-
            Launches the CO2MPAS BATCH command.
            - Populate the "Inputs" list with (at least one) files & folders;
            - Compatible with all flags and options (including ENGINEERING/DECLARATION mode);
            - The output-folder cannot be empty.
        run_ta_btn: |-
            Runs the CO2MPAS TA command for a single file in DECLARATION mode.
            - Incompatible with any other flags and options;
            - The output-folder cannot be empty;
        stop_job_btn: |-
            Aborts a "job" that has started with the Run or Run TA buttons.

        extra_options_entry: |-
            A space-separated list of key-value pair options.
            - Values are "typed"; use the following assignment symbols to demarcate them:
                +=: INTEGER
                *=: FLOAT
                ?=: BOOLEAN: (1, yes, true, on) ==> True, (0, no, false, off) ==> False
                :=: JSON expression
                @=: PYTHON expression
                = : STRING
            - example:
                flag.engineering?=on  flag.plot_workflow?=yes  flag.output_template=some_file.xlsx

        engineering_mode: |-
            the model uses all the available input data (not only the declaration inputs),
            and it is possible to override various model parameters.
        plot_workflow: |-
            Open workflow-plot in browser, after the run has finished.
        soft_validation: |-
            Relax some Input-data validations in order to facilitate experimentation.
        only_summary: |-
            Do not save vehicle outputs, just the summary; should be faster.
        use_selector: |-
            Select internally the best model to predict both NEDC H/L cycles.

        out_files_tree: |-
            A CO2MPAS run populates this list with all Excel result files.
            - Double-click on each file to open it.

        inp_sync_entry: |-
            The input Excel file to the Synchronization utility.
            - Double-click to open it.
        out_sync_btn: |-
            The Excel file generated by the Synchronization utility.
            - Double-click to open it.
        download_sync_tmpl_file_btn: |-
            Opens a Save-File dialog to specify where to create an empty "Sync Excel file".
            - Choose a cycle to enable it.
        sel_sync_file_btn: |-
            Opens an Open-File dialog to specify an existing Input "Sync Excel file".
        run_sync_btn: |-
            Runs the Synchronization utility.

        sel_demo_folder_btn: |-
            Opens an Select-folder dialog to specify where to store the IPython-notebook(`.ipynb`) files.
        demo_folder_btn: |-
            The folder where the IPython-notebook(`.ipynb`) files have been stored.
            - Double-click to open it.

        sel_ipython_folder_btn: |-
            Opens an Select-folder dialog to specify where to store the demo CO2MPAS Input files.
        ipython_folder_btn: |-
            The folder where the demo CO2MPAS Input files have been stored.
            - Double-click to open it.

    """

    return yaml.load(all_tooltips)

about_txt = """
    {intro}

    [img:CO2MPAS logo](icons/CO2MPAS_banner2.png)

    Home     : [{__uri__}]({__uri__})
    Version  : {__version__} ({__updated__})
    Python   : {pyversion}
    Copyright: {__copyright__}
    License  : {__license__}

    {extra}
"""


def show_about(root, about_txt=about_txt, verbose=False):
    root.title("About %s" % app_name)

    textarea = tk.Text(root, wrap=tk.WORD,
                       background='SystemButtonFace',
                       cursor='arrow')
    textarea.pack(fill=tk.BOTH, expand=1)

    if verbose:
        extra = 'Verbose versions: \n%s' % indent(cmain.build_version_string(verbose=True), '    ')
    else:
        extra = ''
    fields = dict(
        intro='%s\n\n' % ''.join(__doc__.split('\n')[:2]).strip(),
        extra=extra,
        pyversion=sys.version,
    )
    txt = dedent(about_txt).format_map(ChainMap(fields, locals(), globals()))

    log.info(txt)
    add_makdownd_text(textarea, txt)

    textarea.configure(state=tk.DISABLED)


_bw = 2
_pad = 2
olive_color = '#556b2f'
yellow_color = '#f1c232'  # saffron yellow
_sunken = dict(relief=tk.SUNKEN, padx=_pad, pady=_pad, borderwidth=_bw)


def define_ttk_styles():
    style = ttk.Style()
    style.configure('None.TButton', background='SystemButtonFace')
    style.configure('True.TButton', foreground='green')
    style.configure('False.TButton', foreground='red')
    style.configure('TFrame', relief=tk.RAISED, padding=_pad)
    style.configure('TLabelframe', relief=tk.RAISED,)
    style.configure('Flipper.TLabelframe', relief=tk.RAISED)
    style.configure('TA.TButton', foreground='orange')
    style.configure('Logo.TLabel')
    style.configure('Filepath.TButton', anchor='w')
    style.configure('RO.Treeview', background='SystemButtonFace')  # NO, tags only


LOGGING_TAGS = OrderedDict((
    (logging.CRITICAL, {'background': "red", 'foreground': "yellow"}),
    (logging.ERROR, {'foreground': "red"}),
    (logging.WARNING, {'foreground': "magenta"}),
    (logging.INFO, {'foreground': "blue"}),
    (logging.DEBUG, {'foreground': "grey"}),
    (logging.NOTSET, {}),
    ('help', {'foreground': yellow_color, 'background': olive_color}),
))


def config_text_tags(text, tags):
    for tag, kws in tags.items():
        if isinstance(tag, int):
            tag = logging.getLevelName(tag)
        text.tag_config(tag, **kws)


def bang(cond):
    """ Returns a "!" if cond is true - used for ttk-states."""
    return cond and '!' or ''


def labelize_str(s):
    if not s.endswith(':'):
        s += ':'
    return s.title()


def open_file_with_os(fpath):
    if fpath.strip():
        log.info("Opening file %r...", fpath)
        try:
            putils.open_file_with_os(fpath.strip())
        except Exception as ex:
            log.error("Failed opening %r due to: %s", fpath, ex)


def attach_open_file_popup(widget, var):
    popup = tk.Menu(widget, tearoff=0)
    popup.add_command(label="Open...", command=lambda: open_file_with_os(var.get()))

    def do_popup(event):
        popup.post(event.x_root, event.y_root)
    widget.bind("<Button-3>", do_popup)


def open_url(url):
    webbrowser.open_new(url)


def find_longest_valid_dir(path, default=None):
    while path and not osp.isdir(path):
        path = osp.dirname(path)

    if not path:
        path = default

    return path


def get_file_infos(fpath):
    try:
        s = os.stat(fpath)
        mtime = datetime.datetime.fromtimestamp(s.st_mtime)  # @UndefinedVariable
        res = (s.st_size, mtime.isoformat())
    except:
        res = ('', '')
    return res


def run_python_job(job_name, function, cmd_args, cmd_kwds, stdout=None, stderr=None, on_finish=None):
    """
    Redirects stdout/stderr to logging, and notifies when finished.

    Suitable to be run within a thread.
    """
    ## Numpy error-config is on per-thread basis:
    #    https://docs.scipy.org/doc/numpy/reference/ufuncs.html#error-handling
    #  So replicate :func:`cmain.init_logging()` logic also here.
    #
    cmain._set_numpy_logging()

    ex = None
    with stds_redirected(stdout, stderr) as (stdout, stderr):
        try:
            function(*cmd_args, **cmd_kwds)
        except (SystemExit, Exception) as ex1:
            log.error("Job %s failed due to: %s", job_name, ex1, exc_info=1)
            ex = ex1

    if on_finish:
        try:
            on_finish(stdout, stderr, ex)
        except Exception as ex:
            ## Have to log as CRITICAL because outside event-loop and
            #  will be logged and collected by the log panel as a normal ERROR.
            log.critical("GUI failed while ending job due to: %s", ex, exc_info=1)
    else:
        if ex:
            log.error("Job %s failed due to: %s", job_name, ex, exc_info=1)
        stdout = stdout.getvalue()
        if stdout:
            log.info("Job %s stdout: %s", job_name, stdout)

        stderr = stderr.getvalue()
        if stderr:
            log.error("Job %s stderr: %s", job_name, stderr)


_loaded_icons = weakref.WeakValueDictionary()


def read_image(fpath):
    icon = _loaded_icons.get(fpath)
    if not icon:
        with pkg.resource_stream('co2mpas', fpath) as fd:  # @UndefinedVariable
            img = Image.open(fd)
            icon = ImageTk.PhotoImage(img)
        _loaded_icons[fpath] = icon

    return icon


def add_icon(btn, icon_path):
    image = read_image(icon_path)
    btn['image'] = image
    btn.image = image  # Avoid GC.
    if btn['text']:
        btn['compound'] = tk.TOP


def tree_apply_columns(tree, columns):
    tree['columns'] = tuple(c for c, _ in columns if not c.startswith('#'))
    for c, col_kwds in columns:

        h_col_kwds = dtz.keyfilter((lambda k: k in set('text image anchor command'.split())), col_kwds)
        text = h_col_kwds.pop('text', c.title())
        tree.heading(c, text=text, **h_col_kwds)

        c_col_kwds = dtz.keyfilter((lambda k: k in set('anchor minwidth stretch width'.split())), col_kwds)
        tree.column(c, **c_col_kwds)


def make_file_tree(frame, **tree_kwds):
    frame.grid_rowconfigure(0, weight=1)
    frame.grid_columnconfigure(0, weight=1)

    tree = ttk.Treeview(frame, **tree_kwds)
    tree.grid(row=0, column=0, sticky='nswe')

    # Setup scrollbars.
    #
    v_scrollbar = ttk.Scrollbar(frame, command=tree.yview)
    h_scrollbar = ttk.Scrollbar(frame, orient=tk.HORIZONTAL, command=tree.xview)
    tree.config(xscrollcommand=h_scrollbar.set, yscrollcommand=v_scrollbar.set)
    v_scrollbar.grid(row=0, column=1, sticky='ns')
    h_scrollbar.grid(row=1, column=0, sticky='ew')

    columns = (
        ('#0', {
            'text': 'Filepath',
            'anchor': tk.W,
            'stretch': True,
            'minwidth': 96,
            'width': 362}),
        ('type', {'anchor': tk.W, 'width': 56, 'stretch': False}),
        ('size', {'anchor': tk.E, 'width': 64, 'stretch': False}),
        ('modified', {'anchor': tk.W, 'width': 164, 'stretch': False}),
    )
    tree_apply_columns(tree, columns)

    ## Attach onto tree not to be GCed.
    tree.excel_icon = read_image('icons/excel-olive-16.png')
    tree.file_icon = read_image('icons/file-olive-16.png')
    tree.folder_icon = read_image('icons/folder-olive-16.png')

    def insert_path(path, is_folder=False, **kwds):
        try:
            if is_folder:
                ftype = 'FOLDER'
                path += '/'
                icon = tree.folder_icon
            else:
                ftype = 'FILE'
                icon = tree.excel_icon if re.search(r'\.xl\w\w$', path) else tree.file_icon
            finfos = get_file_infos(path)
            tree.insert('', 'end', path, text=path,
                        values=(ftype, *finfos), image=icon, **kwds)
        except Exception as ex:
            log.warning("Cannot add input file %r due to: %s", path, ex)

    tree.insert_path = insert_path
    tree.clear = lambda: tree.delete(*tree.get_children())

    def on_double_click(ev):
        item = tree.identify('item', ev.x, ev.y)
        open_file_with_os(item)

    tree.bind("<Double-1>", on_double_click)

    return tree


def add_tooltip(widget, key, allow_misses=False, no_lookup=False):
    """
    :param no_lookup:
        If true, uses the `key` as tooltip text.
    """
    if no_lookup:
        tooltip_text = key
    else:
        tooltips = define_tooltips()
        tooltip_text = tooltips.get(key)
        if tooltip_text is None:
            if not allow_misses:
                raise AssertionError('Tooltip %r not in %s!' % (key, list(tooltips)))
            return

    tooltip_text = dedent(tooltip_text.strip())
    ToolTip(widget, tooltip_text)

_img_in_txt_regex = re.compile(
    r'''
        (?<!\\)\[
                \ * (?P<obj>(?:img|wdg):)?
                \ * (?P<alt>[^\]\n]+?) \ *
        \]
        (?:\(
            \ * (?P<url>[^)\n]+?) \ *
        \))?
    ''',
    re.IGNORECASE | re.VERBOSE)


def add_makdownd_text(text_widget, text, widgets: Mapping[str, tk.Widget]=None, *tags):
    """
    Support a limited Markdown for inserting text into :class:`tk.Text`.

    Supported formats:

    - Links: ``[<alt-text>](<url>)`` is replaced with a :class:`HyperlinkManager` link.
    - Images: ``[img:<alt-text>](<filename>)`` is replaced with the image loaded from ``<filename>``.
    - Widgets: ``[wdg:<alt-text>](<widget-key>)`` where ``<widget-key>`` is use to retrieve the widget
      from the `widgets` mapping passed as argument (must exist).

    Example::

        msg = "[Einstein](https://en.wikipedia.org/wiki/Einstein) on the [img:beach](images/keratokampos.png).")
        add_makdownd_text(text, msg)

    :param widgets:
        Maps ``{url --> Widget-instances}`` to be used by ``[wdg:studd]``
    """
    linkman = None

    def get_linkman():
        nonlocal linkman

        if linkman is None:
            linkman = HyperlinkManager(text_widget)
        return linkman

    last_endp = 0
    for m in _img_in_txt_regex.finditer(text):
        try:
            s, e = m.span(0)
            text_widget.insert(tk.INSERT, text[last_endp:s], *tags)

            obj, alt, url = m.groups()
            if not url:
                url = alt

            if obj == 'img:':
                img = read_image(url)
                #add_tooltip(img, alt, no_lookup=True)
                text_widget.image_create(tk.INSERT, image=img)

                ## Do not GC image.
                #
                imgs = getattr(text_widget, 'imgs', [])
                if not widgets:
                    text_widget.imgs = imgs
                imgs.append(img)

            elif obj == 'wdg:':
                w = widgets[url]
                #add_tooltip(w, alt, allow_misses=True)
                text_widget.window_create(tk.INSERT, window=w)
            elif alt:
                lm = get_linkman()
                tag = lm.add(fnt.partial(open_url, url))
                text_widget.insert(tk.INSERT, alt, tag, *tags)
            else:
                raise AssertionError(text, s, e, obj, alt, url, m.groupdict())
        except Exception as ex:
            raise ValueError("Makdown syntax-error %r at (line.column) %s: %s"
                             "\n  obj: %s, alt: %s, url: %s" %
                             (m.group(0), text_widget.index(tk.INSERT), ex, obj, alt, url)) from ex
        last_endp = e
    text_widget.insert(tk.INSERT, text[last_endp:], *tags)


class HyperlinkManager:
    ## From http://effbot.org/zone/tkinter-text-hyperlink.htm
    def __init__(self, text):

        self.text = text

        self.text.tag_config("hyper", foreground="blue", underline=1)

        self.text.tag_bind("hyper", "<Enter>", self._enter)
        self.text.tag_bind("hyper", "<Leave>", self._leave)
        self.text.tag_bind("hyper", "<Button-1>", self._click)

        self.reset()

    def reset(self):
        self.links = {}

    def add(self, action):
        # add an action to the manager.  returns tags to use in
        # associated text widget
        tag = "hyper-%d" % len(self.links)
        self.links[tag] = action
        return "hyper", tag

    def _enter(self, event):
        self.text.config(cursor="hand2")

    def _leave(self, event):
        self.text.config(cursor="")

    def _click(self, event):
        for tag in self.text.tag_names(tk.CURRENT):
            if tag[:6] == "hyper-":
                self.links[tag]()
                return


class FlagButton(ttk.Button):
    """A button switching flag-states when clicked; 3-state by default: ``'', 'true', 'false'``.

    :ivar flag_styles:
        An ordered-dict ``{state --> ttk-style}``.
    :ivar flag_var:
        A :class:`t.Variable` holding the flag, which is a key in the `flag_syles`.
        Also provided on constructor as ``'variable'`` kwd.
    :ivar flag_name:
        The flag-name, extracted from the ``'text'`` option on construction; you may
        modify it attr later.

    """

    flag_styles = OrderedDict([
        ('', 'None.TButton'),
        ('true', 'True.TButton'),
        ('false', 'False.TButton'),
    ])

    def __init__(self, *args, variable=None, command=None, **kwds):
        def clicked():
            self.next_flag()
            if self._orig_command:
                self._orig_command()

        kwds['command'] = clicked
        super().__init__(*args, **kwds)
        self._orig_command = command
        self.flag_var = variable or tk.Variable()
        self.flag_name = kwds.get('text', '')

        ## Begin from 1st flag.
        #
        self._flag_ix = -1
        self.next_flag()

    @property
    def flag(self):
        return self.flag_var.get()

    def _format_text(self, flag):
        """Override to modify the button text's among flags."""
        #return '%s: %s' % (self.flag_name, flag)
        return self.flag_name

    def next_flag(self):
        self._flag_ix = (self._flag_ix + 1) % len(self.flag_styles)
        flag = list(self.flag_styles)[self._flag_ix]
        flag_style = self.flag_styles[flag]

        self.flag_var.set(flag)
        self.configure(text=self._format_text(flag), style=flag_style)
        self.state((bang(not flag) + 'pressed',))


FlipSpec = namedtuple('FlipSpec', 'show_func hide_func')


class WidgetFlipper:
    """Given a parent widget and a list of children, keeps always one child visible"""

    def __init__(self, parent, *flip_children, flip_cb=None):
        """
        :param flip_children:
            A list of :class:`FlipSpec` or compatible tuples.
        """
        self.flip_specs = [isinstance(fspec, FlipSpec) and fspec or FlipSpec(*fspec)
                           for fspec in flip_children]
        self._flip_cb = flip_cb

        self.flip_ix = -1  # So that flipping kicks-in below.
        self.flip(0, dont_invoke_cb=True)

    def flip(self, flip_ix=None, dont_invoke_cb=False):
        flip_specs = self.flip_specs
        old_ix = self.flip_ix

        if flip_ix is None:
            flip_ix = (self.flip_ix + 1) % len(self.flip_specs)

        if flip_ix != old_ix:
            if old_ix is not None:
                flip_specs[old_ix].hide_func()
            flip_specs[flip_ix].show_func()
            self.flip_ix = flip_ix

            if not dont_invoke_cb and self._flip_cb:
                self._flip_cb((self, old_ix, flip_ix))


class LogPanel(ttk.Labelframe):

    """
    Instantiate only once(!), or logging and Tk's ex-handling will get borged.
    """

    LEVELS_MAP = sorted(logging._levelToName.items(), reverse=True)

    TAG_META = 'meta'
    TAG_LOGS = 'logs'

    FORMATTER_SPECS = [
        dict(
            fmt='%(asctime)s:%(name)s:%(levelname)s:%(message)s', datefmt=None),
        dict(fmt='%(asctime)s:%(name)s:%(levelname)s:', datefmt=None)
    ]

    initted = False

    def __init__(self, master, app, *args,
                 log_threshold=logging.INFO, logger_name='', formatter_specs=None,
                 log_level_cb=None, **kw):
        """
        :param dict formatter_specs:
            A 2-element array of Formatter-args (note that python-2 has no `style` kw),
            where the 2nd should print only the Metadata.
            If missing, defaults to :attr:`LogPanel.FORMATTER_SPECS`
        :param logger_name:
            What logger to intercept to.
            If missing, defaults to root('') and DOES NOT change its threshold,
            unless modified by the `log_level_cb` of the popup-menu (see next param).
        :param log_level_cb:
            An optional ``func(level)`` invoked when log-threshold is modified from popup-menu.
        """
        self.app = app
        self._log_level_cb = log_level_cb
        if LogPanel.initted:
            raise RuntimeError("I said instantiate me only ONCE!!!")
        LogPanel.inited = True

        super().__init__(master, *args, **kw)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._log_text = _log_text = tk.Text(self,
                                             state=tk.DISABLED, wrap=tk.NONE,
                                             font="Courier 8",
                                             **_sunken
                                             )
        _log_text.grid(row=0, column=0, sticky='nswe')

        # Setup scrollbars.
        #
        v_scrollbar = ttk.Scrollbar(self, command=self._log_text.yview)
        h_scrollbar = ttk.Scrollbar(self, command=self._log_text.xview, orient=tk.HORIZONTAL)
        self._log_text.config(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        v_scrollbar.grid(row=0, column=1, sticky='ns')
        h_scrollbar.grid(row=1, column=0, sticky='ew')

        # Prepare Log-Tags
        #
        tags = OrderedDict((
            (LogPanel.TAG_LOGS, dict(lmargin2='+2c')),
            (LogPanel.TAG_META, dict(font="Courier 7")),
        ))
        tags.update(LOGGING_TAGS)
        config_text_tags(_log_text, tags)
        _log_text.tag_raise(tk.SEL)

        self._log_counters = Counter()
        self._update_title()

        self._setup_logging_components(formatter_specs, log_threshold)

        self._setup_popup(self._log_text)

        self._intercept_logging(logger_name)
        self._intercept_tinker_exceptions()
        self.bind('<Destroy>', self._stop_intercepting_exceptions)

    def _setup_logging_components(self, formatter_specs, log_threshold):
        log_panel = self
        log_textarea = self._log_text

        class MyHandler(logging.Handler):
            refresh_delay_ms = 140

            def __init__(self, **kws):
                logging.Handler.__init__(self, **kws)
                self.lrq = Queue()
                self.reschedule()

            def emit(self, record):
                self.lrq.put(record)

            def reschedule(self):
                self.gui_cb_id = log_textarea.after(self.refresh_delay_ms,
                                                    self.pump_logqueue_into_gui)
                
            def pump_logqueue_into_gui(self):
                lrq = self.lrq

                if not lrq.empty():
                    try:
                        log_textarea.update()
                        was_bottom = (log_textarea.yview()[1] == 1)
                        log_textarea['state'] = tk.NORMAL

                        while not lrq.empty():
                            try:
                                record = lrq.get()
                                log_panel._write_log_record(record)
                            except Exception:
                                ## Must not raise any errors, or
                                #  infinite recursion here.
                                print("Failed emitting log into UI: %s" %
                                      traceback.format_exc(), file=sys.stderr)

                        log_textarea['state'] = tk.DISABLED
                        # Scroll to the bottom, if
                        #    log serious or log was already at the bottom.
                        #
                        if record.levelno >= logging.ERROR or was_bottom:
                            log_textarea.see(tk.END)

                        log_panel._log_counters.update(['Total', record.levelname])
                        log_panel._update_title()
                    except Exception:
                        self.handleError(record)

                self.reschedule()

        self._handler = MyHandler()

        if not formatter_specs:
            formatter_specs = LogPanel.FORMATTER_SPECS
        self.formatter = logging.Formatter(**formatter_specs[0])
        self.metadata_formatter = logging.Formatter(**formatter_specs[1])

        self.threshold_var = tk.IntVar()
        self.log_threshold = log_threshold

    def _intercept_logging(self, logger_name):
        logger = logging.getLogger(logger_name)
        logger.addHandler(self._handler)

    def _intercept_tinker_exceptions(self):
        def my_ex_interceptor(*args):
            log.critical('Unhandled TkUI exception:', exc_info=True)
            try:
                self.app.cstatus('Unhandled TkUI exception: %s', args, delay=0)
            except:
                # Must not raise any errors, or infinite recursion here.
                pass
            self._original_tk_ex_handler(*args)

        self._original_tk_ex_handler = tk.Tk.report_callback_exception
        tk.Tk.report_callback_exception = my_ex_interceptor

    def _stop_intercepting_exceptions(self, event):
        root_logger = logging.getLogger()
        root_logger.removeHandler(self._handler)

    def _setup_popup(self, target):
        levels_map = LogPanel.LEVELS_MAP

        # Threshold sub-menu
        #
        def change_threshold():
            level = self.threshold_var.get()
            self.log_threshold = level
            if self._log_level_cb:
                self._log_level_cb(level)

        threshold_menu = tk.Menu(target, tearoff=0)
        for lno, lname in levels_map:
            threshold_menu.add_radiobutton(
                label=lname, value=lno,
                variable=self.threshold_var,
                command=change_threshold
            )
        filters_menu = tk.Menu(target, tearoff=0)

        # Filters sub-menu
        #
        self._filter_vars = [
            tk.BooleanVar(name=lname) for _, lname in levels_map]
        for i, (lno, lname) in enumerate(levels_map):
            filters_menu.add_checkbutton(
                label=lname,
                variable=self._filter_vars[i],
                command=self._apply_filters
            )

        # Popup menu
        #
        popup = tk.Menu(target, tearoff=0)
        popup.add_cascade(label="Log threshold", menu=threshold_menu)
        popup.add_cascade(label="Filter levels", menu=filters_menu)
        popup.add_checkbutton(
            label="Wrap lines", command=self.toggle_text_wrapped)
        popup.add_separator()
        popup.add_command(label="Save as...", command=self.save_log)
        popup.add_separator()
        popup.add_command(label="Clear logs", command=self.clear_log)

        def do_popup(event):
            popup.post(event.x_root, event.y_root)
        target.bind("<Button-3>", do_popup)

    def _apply_filters(self):
        for level_var in self._filter_vars:
            self._log_text.tag_configure(
                level_var._name, elide=level_var.get())

    @property
    def log_threshold(self):
        return self._handler.level

    @log_threshold.setter
    def log_threshold(self, level):
        self._handler.setLevel(level)
        self.threshold_var.set(level)

    def toggle_text_wrapped(self):
        self._log_text['wrap'] = tk.WORD if self._log_text[
            'wrap'] == tk.NONE else tk.NONE

    def _update_title(self):
        levels = ['Totals'] + [lname for _, lname in LogPanel.LEVELS_MAP]
        levels_counted = [(lname, self._log_counters[lname])
                          for lname in levels]
        self['text'] = 'Log messages (%s)' % ', '.join(
            '%s: %i' % (lname, count) for lname, count in levels_counted if count)

    def clear_log(self):
        self._log_text['state'] = tk.NORMAL
        self._log_text.delete('1.0', tk.END)
        self._log_text['state'] = tk.DISABLED
        self._log_counters.clear()
        self._update_title()

    def save_log(self):
        now = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        fname = 'co2dice-%s.log' % now
        fname = filedialog.SaveAs(
            parent=self,
            title='Select filename to save the Log',
            initialfile=fname,
            defaultextension='.log',
            filetypes=[('log', '*.log'), ('txt', '*.txt'), ('*', '*')],
        ).show()
        if fname:
            txt = self._log_text.get(1.0, tk.END)
            with io.open(fname, 'wt+') as fd:
                fd.write(txt)

    def _write_log_record(self, record):
        """The textarea must be writtable."""
        log_text = self._log_text

        txt = self.formatter.format(record)
        if txt[-1] != '\n':
            txt += '\n'
        txt_len = len(txt) + 1  # +1 ??
        log_start = '%s-%ic' % (tk.END, txt_len)
        metadata_len = len(self.metadata_formatter.formatMessage(record))
        meta_end = '%s-%ic' % (tk.END, txt_len - metadata_len)

        self._log_text.mark_set('LE', tk.END)
        # , LogPanel.TAG_LOGS)
        log_text.insert(tk.END, txt, LogPanel.TAG_LOGS)
        log_text.tag_add(record.levelname, log_start, tk.END)
        log_text.tag_add(LogPanel.TAG_META, log_start, meta_end)


class SimulatePanel(ttk.Frame):
    """
    The state of all widgets is controlled by :meth:`mediate_guistate()`.
    """
    def __init__(self, parent, app, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.app = app

        w = self._make_inputs_frame(self)
        w.grid(column=0, row=0, rowspan=2, sticky='nswe')

        w, var = self._make_output_folder(self)
        w.grid(column=1, row=0, sticky='nswe')
        self.out_folder_var = var

        w, flipper = self._make_advanced_flipper(self)
        w.grid(column=1, row=1, sticky='nswe')
        self.advanced_flipper = flipper

        w = self._make_buttons_frame(self)
        w.grid(column=0, row=3, columnspan=2, sticky='nswe')

        w = self._make_output_tree(self)
        w.grid(column=0, row=4, columnspan=2, sticky='nswe')

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(4, weight=1)

        self.mediate_guistate()

    def _make_inputs_frame(self, parent):
        frame = ttk.Labelframe(parent, text='Inputs')

        (tree, add_files_btn, add_folder_btn, save_templ_btn, del_btn) = self._build_inputs_tree(frame)
        tree.grid(column=0, row=0, rowspan=4, sticky='nswe')
        add_files_btn.grid(column=1, row=0, sticky='nswe')
        add_folder_btn.grid(column=1, row=1, sticky='nswe')
        save_templ_btn.grid(column=1, row=2, sticky='nswe')
        del_btn.grid(column=1, row=3, sticky='nswe')

        frame.columnconfigure(0, weight=1)
        for r in range(4):
            frame.rowconfigure(r, weight=1)

        return frame

    def _build_inputs_tree(self, parent):
        tframe = ttk.Frame(parent, style='FrameTree.TFrame', height=260)

        tree = make_file_tree(tframe, height=3)
        self.inputs_tree = tree

        def ask_input_files():
            files = filedialog.askopenfilenames(
                parent=self,
                title='Select CO2MPAS Input file(s)',
                multiple=True,
                filetypes=(('Excel files', '.xlsx .xlsm'),
                           ('All files', '*'),
                           ))
            if files:
                for fpath in files:
                    tree.insert_path(fpath, is_folder=False)
                self.mediate_guistate()
        files_btn = btn = ttk.Button(parent, command=ask_input_files)
        add_icon(btn, 'icons/add_file-olive-32.png')
        add_tooltip(btn, 'add_inp_files_btn')

        def ask_input_folder():
            folder = filedialog.askdirectory(
                parent=self,
                title='Select CO2MPAS Input folder')
            if folder:
                tree.insert_path(folder, is_folder=True)
                self.mediate_guistate()
        folder_btn = btn = ttk.Button(parent, command=ask_input_folder)
        add_icon(btn, 'icons/add_folder-olive-32.png')
        add_tooltip(btn, 'add_inp_folder_btn')

        def ask_save_template_file():
            file = filedialog.asksaveasfilename(
                parent=self,
                title='Save "sample" Input CO2MPAS file',
                defaultextension='xlsx',
                filetypes=(('Excel files', '.xlsx .xlsm'),))
            if file:
                cmain.save_template((file,), force=True)
                tree.insert_path(file, is_folder=False)
                self.mediate_guistate()

        save_btn = btn = ttk.Button(parent, command=ask_save_template_file)
        add_icon(btn, 'icons/download-olive-32.png')
        add_tooltip(btn, 'download_tmpl_file_btn')

        del_btn = btn = ttk.Button(parent, state=tk.DISABLED)  # Its state maintained internally in this method.
        add_icon(btn, 'icons/trash-olive-32.png')
        add_tooltip(btn, 'del_inp_btn')

        ## Tree events:
        #
        def do_del_items():
            for item in tree.selection():
                try:
                    tree.delete(item)
                except Exception as ex:
                    log.warning("Cannot delete %r due to: %s", item, ex)
            del_btn.state((tk.DISABLED,))  # tk-BUG: Selection-vent is not fired.
            self.mediate_guistate()

        def key_handler(ev=None):
            if ev.keysym == 'Delete':
                do_del_items()
                #self.mediate_guistate() Already in `do-del()`.
            elif ev.keysym.lower() == 'a':
                tree.selection_set(tree.get_children())
                self.mediate_guistate()

        def tree_selection_changed(ev):
            del_btn.state((bang(tree.selection()) + tk.DISABLED,))

        tree.bind("<Key>", key_handler)
        del_btn['command'] = do_del_items
        tree.bind('<<TreeviewSelect>>', tree_selection_changed)
        add_tooltip(tree, 'inp_files_tree')

        return (tframe, files_btn, folder_btn, save_btn, del_btn)

    def _make_output_tree(self, parent):
        frame = ttk.Labelframe(parent, text="Output Result Files",
                               style='FileTree.TFrame', height=260)

        tree = make_file_tree(frame, selectmode='none', height=3)
        tree.tag_configure('ro', background='SystemButtonFace')
        self.outputs_tree = tree
        add_tooltip(tree, 'out_files_tree')

        return frame

    def _make_output_folder(self, parent):
        title = 'Output Folder'
        frame = ttk.Labelframe(parent, text=labelize_str(title))

        var = StringVar(value=os.getcwd())
        entry = ttk.Entry(frame, textvariable=var)
        entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        attach_open_file_popup(entry, var)
        entry.bind("<Double-1>", lambda ev: open_file_with_os(var.get()))
        add_tooltip(entry, 'out_folder_entry')

        def ask_output_folder():
            initialdir = find_longest_valid_dir(var.get().strip())
            folder = filedialog.askdirectory(
                parent=self,
                title="Select %s" % title,
                initialdir=initialdir)
            if folder:
                var.set(folder + '/')
                self.mediate_guistate()

        btn = ttk.Button(frame, command=ask_output_folder)
        btn.pack(side=tk.LEFT, fill=tk.BOTH,)
        add_icon(btn, 'icons/download_dir-olive-32.png')
        add_tooltip(btn, 'sel_out_folder_btn')

        entry.bind("<KeyRelease>", lambda ev: self.mediate_guistate())

        return frame, var

    def _make_advanced_flipper(self, parent):
        frame = ttk.Labelframe(parent, text='Advanced...',
                               style='Flipper.TLabelframe')
        add_tooltip(frame, 'advanced_link')

        logo = ttk.Label(frame, style='Logo.TLabel')
        add_icon(logo, 'icons/CO2MPAS_banner2.png')

        def show_logo():
            logo.grid(column=1, row=1, rowspan=2, sticky='nswe')

        def hide_logo():
            logo.grid_forget()

        frame1, var = self._make_out_template_file(frame)
        self.tmpl_folder_var = var

        frame2, var = self._make_flags_frame(frame)
        self.extra_opts_var = var

        def show_advanced():
            frame1.grid(column=1, row=1, sticky='nswe')
            frame2.grid(column=1, row=2, sticky='nswe')

        def hide_advanced():
            frame1.grid_forget()
            frame2.grid_forget()

        flipper = WidgetFlipper(frame,
                                (show_logo, hide_logo),
                                (show_advanced, hide_advanced),
                                flip_cb=lambda ev: self.mediate_guistate())
        frame.bind('<Button-1>', lambda ev: flipper.flip())

        frame.columnconfigure(1, weight=1)

        return frame, flipper

    def _make_out_template_file(self, parent):
        title = 'Output Template file'
        frame = ttk.Labelframe(parent, text=labelize_str(title))

        var = StringVar()
        entry = ttk.Entry(frame, textvariable=var)
        entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        attach_open_file_popup(entry, var)
        entry.bind("<Double-1>", lambda ev: open_file_with_os(var.get()))
        add_tooltip(entry, 'out_template_entry')

        def ask_template_file():
            initialdir = find_longest_valid_dir(var.get().strip())
            file = filedialog.askopenfilename(
                parent=self,
                title='Select %s' % title,
                initialdir=initialdir,
                filetypes=(('Excel files', '.xlsx .xlsm'),
                           ('All files', '*'),
                           ))
            if file:
                var.set(file)
                self.mediate_guistate()

        btn = ttk.Button(frame, command=ask_template_file)
        btn.pack(side=tk.LEFT, fill=tk.BOTH)
        add_icon(btn, 'icons/excel-olive-32.png')
        add_tooltip(btn, 'sel_tmpl_file_btn')

        entry.bind("<KeyRelease>", lambda ev: self.mediate_guistate())

        return frame, var

    def _make_flags_frame(self, parent):
        frame = ttk.Labelframe(parent, text='Flags and Options')
        flags_frame = ttk.Frame(frame)
        flags_frame.pack(fill=tk.X)

        def make_flag(flag):
            flag_name = flag.replace('_', ' ').title()
            btn = FlagButton(flags_frame, text=flag_name,
                             command=self.mediate_guistate,
                             padding=_pad)
            btn.pack(side=tk.LEFT, ipadx=4 * _pad)
            add_tooltip(btn, flag)

            return flag, btn.flag_var

        flags = (
            'engineering_mode',
            'plot_workflow',
            'only_summary',
            'soft_validation',
            'use_selector',
        )
        self.flag_vars = [make_flag(f) for f in flags]

        label = ttk.Label(frame, text=labelize_str("Extra key-value pairs"))
        label.pack(anchor=tk.W)

        var = StringVar()
        entry = ttk.Entry(frame, textvariable=var)
        entry.pack(fill=tk.BOTH, expand=1, ipady=2 * _pad)
        add_tooltip(entry, 'extra_options_entry')

        entry.bind("<KeyRelease>", lambda ev: self.mediate_guistate())

        return frame, var

    def _make_buttons_frame(self, parent):
        frame = ttk.Labelframe(parent, text='Launch Job')
        btn = ttk.Button(frame, text="Help",
                         command=fnt.partial(open_url, user_guidelines_url))
        add_icon(btn, 'icons/help-olive-32.png')
        btn.grid(column=0, row=4, sticky='nswe')
        add_tooltip(btn, 'help_btn')

        self._run_batch_btn = btn = ttk.Button(frame, text="Run",
                                               command=fnt.partial(self._do_run_job, is_ta=False))
        add_icon(btn, 'icons/play-olive-32.png')
        btn.grid(column=1, row=4, sticky='nswe')
        add_tooltip(btn, 'run_batch_btn')

        self._run_ta_btn = btn = ttk.Button(frame,
                                            text="Run TA", style='TA.TButton',
                                            command=fnt.partial(self._do_run_job, is_ta=True))
        add_icon(btn, 'icons/play_doc-orange-32.png')
        btn.grid(column=2, row=4, sticky='nswe')
        add_tooltip(btn, 'run_ta_btn')

        def stop_job_clicked():
            self.app.signal_job_to_stop()
            self.mediate_guistate()
        self._stop_job_btn = btn = ttk.Button(frame, text="Stop", command=stop_job_clicked)
        add_icon(btn, 'icons/hand-red-32.png')
        btn.grid(column=3, row=4, sticky='nswe')
        add_tooltip(btn, 'stop_job_btn')

        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=2)
        frame.columnconfigure(2, weight=1)

        return frame

    def mediate_guistate(self, msg=None, *args,
                         level=None,
                         static_msg: Union[bool, Text]=None,
                         progr_step=None, progr_max=None,
                         new_out_file=None):
        """
        Handler of states for all panel's widgets and progressbar/status.

        :param static_msg:
            if true, message becomes the new static-status message,
            if a string, that string becomes the "static" message
            (usefull to set a temporary status-msg and clear the "static" one).
        """
        ## Update progress/status bars.
        #
        if msg is not None:
            delay = None
            if isinstance(static_msg, str):
                self.app.lstatus(static_msg, level=level, delay=0)
            else:
                delay = 0 if static_msg else None
            self.app.lstatus(msg, *args, level=level, delay=delay)
        if progr_step is not None or progr_max is not None:
            self.app.progress(progr_step, progr_max)

        ## Update Stop-button.
        #
        job_alive = self.app.is_job_alive()
        stop_requested = job_alive and self.app.is_stop_job_signaled()
        self._stop_job_btn.state((
            bang(job_alive) + tk.DISABLED,
            bang(not stop_requested) + 'pressed',
        ))

        ## Update Run-button.
        #
        is_run_batch_btn_enabled = not job_alive and self.out_folder_var.get()
        self._run_batch_btn.state((bang(is_run_batch_btn_enabled) + tk.DISABLED,))

        ## Update Run-TA-button.
        #
        is_run_ta_enabled = is_run_batch_btn_enabled and self.advanced_flipper.flip_ix == 0
        self._run_ta_btn.state((bang(is_run_ta_enabled) + tk.DISABLED,))

        if new_out_file:
            self.outputs_tree.insert_path(new_out_file, tags=['ro'])

        self.update()

    def reconstruct_cmd_args_from_gui(self):
        cmd_kwds = OrderedDict()

        out_folder = self.out_folder_var.get()

        if self.advanced_flipper.flip_ix > 0:
            variation = OrderedDict()

            tmpl_folder = self.tmpl_folder_var.get()
            if tmpl_folder:
                variation['flag.output_template'] = tmpl_folder

            args = self.extra_opts_var.get().strip().split()
            for kvpair in args:
                k, v = parse_key_value_pair(kvpair)
                variation[k] = v

            for flag, flag_var in self.flag_vars:
                flag_value = flag_var.get()
                if flag_value:
                    variation['flag.%s' % flag] = putils.str2bool(flag_value)
            if variation:
                cmd_kwds['variation'] = variation

        inp_paths = self.inputs_tree.get_children()

        return inp_paths, out_folder, cmd_kwds

    def _do_run_job(self, is_ta):
        app = self.app
        job_name = "CO2MPAS-TA" if is_ta else "CO2MPAS"

        assert app._job_thread is None, (app._job_thread, job_name)

        inp_paths, out_folder, cmd_kwds = self.reconstruct_cmd_args_from_gui()

        inp_paths = cmain.file_finder(inp_paths)
        if not inp_paths:
            app.estatus("No inputs specified!  Please add files & folders in the Inputs list at the top-left.")
            return

        mediate_guistate = self.mediate_guistate

        class ProgressUpdater:
            """
            A *tqdm* replacement that cooperates with :func:`run_python_job` to pump stdout/stderr when iterated.

            :ivar i:
                Enumarates progress calls.
            :ivar out_i:
                Tracks till where we have read and logged from the stdout StringIO stream.
            :ivar err_i:
                Tracks till where we have read and logged from the stderr StringIO stream.
            """
            def __init__(self):
                self.stdout = io.StringIO()
                self.stderr = io.StringIO()
                self.out_i = self.err_i = 0

            def __iter__(self):
                return self

            def __next__(self):
                cur_step, item = next(self.it)
                try:
                    ## Report stdout/err collected from previous step.
                    #
                    new_out, new_err = self.pump_std_streams()
                    if new_out or new_err:
                        log.info("Job %s %s of %s. %s%s",
                                 job_name, cur_step - 1, self.len, new_out, new_err)

                    if app.is_stop_job_signaled():
                        log.warning("Canceled %s job before %s of %s",
                                    job_name, cur_step, self.len)
                        raise StopIteration()
                finally:
                    msg = 'Job %s %s of %s: %r...'
                    mediate_guistate(msg, job_name, cur_step, self.len, item,
                                     static_msg=True, progr_step=-cur_step)

                return item

            def result_generated(self, result_tuple):
                fpath, _ = result_tuple
                mediate_guistate('Job %s generated file: %s', job_name, fpath,
                                 level=logging.debug, new_out_file=fpath)

            def pump_std_streams(self):
                new_out = self.stdout.getvalue()[self.out_i:]
                new_err = self.stderr.getvalue()[self.err_i:]
                self.out_i += len(new_out)
                self.err_i += len(new_err)
                if new_out:
                    new_out = '\n  stdout: %s' % indent(new_out, '  ')
                if new_err:
                    new_err = '\n  stderr: %s' % indent(new_err, '  ')

                return new_out, new_err

            def tqdm_replacement(self, iterable, *args, **kwds):

                self.len = len(iterable)
                self.it = iter(enumerate(iterable, 1))
                mediate_guistate(progr_step=-1, progr_max=self.len + 1)  # +1 finalization job-work.
                return self

            def on_finish(self, out, err, ex):
                app._job_thread = None
                args = [job_name]
                if ex:
                    msg = "Failed job %s due to: %s %s%s"
                    args.append(ex)
                    ## Status a "permanent" failure msg.
                    #
                    static_msg = True
                    level = logging.ERROR
                else:
                    msg = "Finished job %s. %s%s"
                    ## Status a temporary success msg.
                    #
                    static_msg = ''
                    level = None
                try:
                    args.extend(self.pump_std_streams())
                finally:
                    mediate_guistate(msg, *args,
                                     static_msg=static_msg, level=level,
                                     progr_max=0)

        updater = ProgressUpdater()
        user_cmd_kwds = cmd_kwds.copy()
        cmd_kwds.update({
            'type_approval_mode': is_ta,
            'overwrite_cache': True,
            'result_listener': updater.result_generated,
            # FIXME: Why `job_must_stop` flag appears True!??
            #'model': cbatch.vehicle_processing_model(),
        })
        t = Thread(
            target=run_python_job,
            args=(job_name,
                  cbatch.process_folder_files, (inp_paths, out_folder), cmd_kwds,
                  updater.stdout, updater.stderr, updater.on_finish),
            daemon=True,  # May corrupt output-files, but prefferably UI closes cleanly.
        )

        ## Monkeypatch *tqdm* on co2mpas-batcher.
        cbatch._custom_tqdm = updater.tqdm_replacement
        self.outputs_tree.clear()
        app.start_job(t, updater.result_generated)

        msg = 'Launched %s job: %s'
        self.mediate_guistate(msg, job_name,
                              ', '.join('%s: %s' % (k, v) for k, v in user_cmd_kwds.items()),
                              static_msg=True, progr_step=0, progr_max=-1)


class SyncronizePanel(ttk.Frame):

    def __init__(self, parent, app, **kw):
        super().__init__(parent, **kw)
        self.app = app
        widgets = {}  # To register widgets embeded in makdown-text.

        help_msg = dedent("""
        1) EITHER choose a Theoretical Velocity-profile, \
click the [img:icons/download-olive-32.png] button to create an empty "Sync Excel file",
               and populate its `dyno` and `obd` sheets with your raw data:
           OR click the [img:icons/excel-olive-32.png] button to load an existing "Sync Excel file":
        [wdg:inp-file]

        2) THEN run synchronization by clicking the [img:icons/align_center-olive-32.png] button, \
and double-click on the result file to open it,
           and copy paste the synchronized signals into your CO2MPAS Input File:
        [wdg:out-file]
        """)
        textarea = tk.Text(self, font='TkDefaultFont',
                           background='SystemButtonFace',
                           foreground='olive',
                           cursor='arrow')
        textarea.pack(fill=tk.BOTH, expand=1)

        frame = ttk.Frame(textarea, style='InpFile.TFrame')
        widgets['inp-file'] = frame

        rb_frame = ttk.Frame(frame, style='CycleRadios.TFrame')
        rb_frame.grid(column=0, row=0, sticky='nswe')
        cycles = (
            'nedc.manual',
            'nedc.automatic',
            'wltp.class1',
            'wltp.class2',
            'wltp.class3a',
            'wltp.class3b',
        )
        self.rb_var = rb_var = tk.StringVar()
        for c in cycles:
            rb = ttk.Radiobutton(rb_frame, text=c, value=c, variable=rb_var,
                                 command=self.mediate_guistate)
            rb.pack(side=tk.LEFT)
            add_tooltip(rb,
                        'The new template file will work with measured time series for a %r cycle.' % c,
                        no_lookup=True)

        def ask_save_template_file():
            file = filedialog.asksaveasfilename(
                parent=self,
                title='Save Synchronization Template File',
                defaultextension='xlsx',
                initialfile='datasync.xlsx',
                filetypes=(('Excel files', '.xlsx .xlsm'),))
            if file:
                opts = docopt.Dict()
                opts['<excel-file-path>'] = [file]
                opts['--force'] = True
                opts['--cycle'] = rb_var.get()
                datasync._cmd_template(opts)

                self.inp_var.set(file)
                self.mediate_guistate()

        self.save_tmpl_btn = btn = ttk.Button(frame, command=ask_save_template_file)
        btn.grid(column=1, row=0, sticky='nswe')
        add_icon(btn, 'icons/download-olive-32.png')
        add_tooltip(btn, 'download_sync_tmpl_file_btn')

        self.inp_var = var = StringVar()
        entry = ttk.Entry(frame, textvariable=var, width=60)
        entry.grid(column=0, row=1, sticky='nswe')
        add_tooltip(entry, 'inp_sync_entry')
        entry.bind("<Double-1>", lambda ev: open_file_with_os(var.get()))
        attach_open_file_popup(entry, var)

        def ask_sync_file():
            path = var.get().strip()
            file = filedialog.askopenfilename(
                parent=self,
                title='Select Synchronization File',
                initialdir=path and find_longest_valid_dir(path) or None,
                filetypes=(('Excel files', '.xlsx .xlsm'),
                           ('All files', '*'),
                           ))
            if file:
                self.inp_var.set(file)
                self.mediate_guistate()

        btn = ttk.Button(frame, command=ask_sync_file, width=60)
        btn.grid(column=1, row=1, sticky='nswe')
        add_icon(btn, 'icons/excel-olive-32.png')
        add_tooltip(btn, 'sel_sync_file_btn')

        frame = ttk.Frame(textarea, style='OutFile.TFrame')
        widgets['out-file'] = frame

        def run_sync():
            inp_file = self.inp_var.get()
            if not osp.isfile(inp_file):
                raise ValueError('File %r does not exist!' % inp_file)

            out_file = datasync.do_datasync('times', 'velocities',
                                            inp_file, out_path=osp.dirname(inp_file),
                                            force=True)

            self.out_var.set(out_file)
            self.mediate_guistate()

        self.run_btn = btn = ttk.Button(frame, command=run_sync)
        btn.grid(column=0, row=0, sticky='nswe')
        add_icon(btn, 'icons/align_center-olive-32.png')

        self.out_var = var = StringVar()
        btn = ttk.Button(frame, textvariable=var, width=87,  # In line with embeded-frame above.
                         #command=lambda: open_file_with_os(self.out_var.get()),
                         style='Filepath.TButton')
        btn.grid(column=1, row=0, sticky='nsw')
        add_tooltip(btn, 'out_sync_btn')
        btn.bind("<Double-1>", lambda ev: open_file_with_os(self.out_var.get()))
        attach_open_file_popup(btn, var)

        add_makdownd_text(textarea, help_msg.strip(), widgets)
        textarea['state'] = tk.DISABLED

        self.mediate_guistate()

    def mediate_guistate(self):
        self.run_btn.state((bang(self.inp_var.get()) + tk.DISABLED,))
        self.save_tmpl_btn.state((bang(self.rb_var.get()) + tk.DISABLED,))


class TemplatesPanel(ttk.Frame):

    def __init__(self, parent, app, **kw):
        super().__init__(parent, **kw)
        self.app = app
        widgets = {}  # To register widgets embeded in makdown-text.

        help_msg = dedent("""
        - Opens a Select-folder dialog for storing DEMO INPUT  files:
        [wdg:demo-files]

        - Opens a Select-folder dialog for storing IPYTHON NOTEBOOKS that may also run CO2MPAS and generate reports:
        [wdg:ipython-files]
        """)
        textarea = tk.Text(self, font='TkDefaultFont',
                           background='SystemButtonFace',
                           foreground='olive',
                           cursor='arrow')

        textarea.pack(fill=tk.BOTH, expand=1)

        def store_demos(folder):
            opts = docopt.Dict()
            opts['--force'] = True
            opts['<output-folder>'] = folder
            cmain._cmd_demo(opts)

        frame = self._make_download_panel(textarea, title='CO2MPAS DEMO Input-files',
                                          action_func=store_demos, tooltip_key='demo')
        widgets['demo-files'] = frame

        def store_ipythons(folder):
            opts = docopt.Dict()
            opts['--force'] = True
            opts['<output-folder>'] = folder
            cmain._cmd_ipynb(opts)

        frame = self._make_download_panel(textarea, title='CO2MPAS IPython files',
                                          action_func=store_ipythons, tooltip_key='ipython')
        widgets['ipython-files'] = frame

        add_makdownd_text(textarea, help_msg.strip(), widgets, 'default')
        textarea['state'] = tk.DISABLED

    def _make_download_panel(self, textarea, title, action_func, tooltip_key):
        frame = ttk.Frame(textarea, style='IPythonFiles.TFrame')
        frame.grid_columnconfigure(1, weight=1)

        var = StringVar()

        def ask_output_folder(title):
            initialdir = find_longest_valid_dir(var.get().strip())
            folder = filedialog.askdirectory(
                parent=self,
                title="Select Folder to store %s" % title,
                initialdir=initialdir)
            if folder:
                action_func(folder)
                var.set(folder + '/')

        btn = ttk.Button(frame, command=fnt.partial(ask_output_folder, title))
        btn.grid(column=0, row=0, sticky='nswe')
        add_icon(btn, 'icons/download_dir-olive-32.png')
        add_tooltip(btn, 'sel_%s_folder_btn' % tooltip_key)

        btn = ttk.Button(frame, textvariable=var, width=87,  # In line with embeded-frame above.
                         style='Filepath.TButton')
        btn.grid(column=1, row=0, sticky='nsw')
        add_tooltip(btn, '%s_folder_btn' % tooltip_key)
        btn.bind("<Double-1>", lambda ev: open_file_with_os(var.get()))
        attach_open_file_popup(btn, var)

        return frame


class TkUI(object):
    """
    :ivar _job_thread:
        semaphore armed when the "red" button pressed

    """

    _job_thread = None

    def __init__(self, root=None):
        if not root:
            root = tk.Tk()
        self.root = root
        root.title("%s-%s" % (app_name, __version__))

        define_ttk_styles()

        self._status_text = status = self._make_status(root)
        status.grid(row=1, column=0, sticky='nswe')
        self.show_motd(7 * 1000, 0)

        self._progr_var = var = tk.IntVar(value=0)
        self._progr_bar = ttk.Progressbar(root, orient=tk.HORIZONTAL, variable=var)

        ttk.Sizegrip(root).grid(row=1, column=1, sticky='e')

        slider = ttk.PanedWindow(root, orient=tk.VERTICAL)
        slider.grid(row=0, column=0, columnspan=3, sticky='nswe')

        nb = ttk.Notebook(slider, height=460)
        slider.add(nb, weight=1)

        tab = SimulatePanel(nb, app=self)
        nb.add(tab, text='Simulate', sticky='nswe')

        tab = SyncronizePanel(nb, app=self)
        nb.add(tab, text='Synchronize', sticky='nwse')

        tab = TemplatesPanel(nb, app=self)
        nb.add(tab, text='Templates & Samples', sticky='nwse')

        frame = LogPanel(slider, self, height=-260, log_level_cb=cmain.init_logging)
        slider.add(frame, weight=3)

        root.columnconfigure(0, weight=1)
        root.columnconfigure(0, weight=2)
        root.rowconfigure(0, weight=1)

        # Menubar
        #
        menubar = tk.Menu(root)
        menubar.add_command(label="About %r" % app_name, command=fnt.partial(self.show_about_window, slider))
        
        def open_console():
            homdedir = os.environ['HOME']
            console_xml = osp.join(homdedir, '..', 'Apps', 'Console', 'console.xml')
            import subprocess as subp
            subp.Popen(['Console.exe', '-c', console_xml, '-t', 'cmd'])
        menubar.add_command(label="Launch console...", command=open_console)
        root['menu'] = menubar

        ## Last, or it shows the empty-root momentarily.
        self._add_window_icon(root)

    def start_job(self, thread, result_listener):
        self._job_thread = thread

        from co2mpas.dispatcher import Dispatcher
        Dispatcher.stopper.clear()

        #: Cludge for GUI to receive Plan's output filenames.
        from co2mpas import plan
        plan.plan_listener = result_listener

        thread.start()

    def signal_job_to_stop(self):
        from co2mpas.dispatcher import Dispatcher
        Dispatcher.stopper.set()

        #: Cludge for GUI to receive Plan's output filenames.
        from co2mpas import plan
        plan.plan_listener = None

    def is_job_alive(self):
        return self._job_thread and self._job_thread.is_alive()

    def is_stop_job_signaled(self):
        """Returns true if signaled, but job might be already dead; check also :meth:`is_job_alive()`."""
        from co2mpas.dispatcher import Dispatcher
        return self._job_thread and Dispatcher.stopper.is_set()

    def _add_window_icon(self, win):
        win.tk.call('wm', 'iconphoto', win._w, read_image('icons/CO2MPAS_icon-64.png'))

    def _make_status(self, parent):
        status = tk.Text(parent, wrap=tk.NONE, height=1, relief=tk.FLAT,
                         state=tk.DISABLED, background='SystemButtonFace')
        config_text_tags(status, LOGGING_TAGS)

        return status

    def lstatus(self, msg, *args, level=None, delay=None, **kwds):
        self.status(msg, *args, level=level, delay=delay, **kwds)

    def dstatus(self, msg, *args, delay=None, **kwds):
        self.status(msg, *args, level=logging.DEBUG, delay=delay, **kwds)

    def istatus(self, msg, *args, delay=None, **kwds):
        self.status(msg, *args, level=logging.INFO, delay=delay, **kwds)

    def wstatus(self, msg, *args, delay=None, **kwds):
        self.status(msg, *args, level=logging.WARNING, delay=delay, **kwds)

    def estatus(self, msg, *args, delay=None, **kwds):
        self.status(msg, *args, level=logging.ERROR, delay=delay, **kwds)

    def cstatus(self, msg, *args, delay=None, **kwds):
        self.status(msg, *args, level=logging.CRITICAL, delay=delay, **kwds)

    _status_static_msg = ('', None)
    _clear_cb_id = None
    _motd_cb_id = None

    def status(self, msg, *args, level: Union[Text, int]=None, delay=None, kwds={}):
        """
        :param level:
            logging-level(int) or tag(str), if None, defaults to INFO.
        :param delay:
            If None, defaults to 7sec, if 0, "static message", can be cleared
            only with ``msg='', delay=0``.
        """
        if msg is None:  # A '' msg clears the 'static" status.
            return

        if delay is None:
            delay = 7 * 1000

        status = self._status_text
        if self._clear_cb_id:
            status.after_cancel(self._clear_cb_id)
            self._clear_cb_id = None
        if self._motd_cb_id:
            status.after_cancel(self._motd_cb_id)
            self._motd_cb_id = None
            self.show_motd()  # Re-schedule motd.

        if level is None:
            level = logging.INFO

        ##  Translate the level --> tag.
        #
        tag = logging.getLevelName(level)
        if tag.startswith('Level'):  # unknown level
            tag = level

        ## Static message, are not colored as INFOs.
        #
        if delay == 0 and level == logging.INFO:
            tag = None

        if isinstance(level, int) and (msg or args):  # Do not log empty static-cleaning msgs.
            log.log(level, msg, *args, **kwds)

        msg = msg % args

        ## Set static message as "clear" text.
        #
        if not delay:
            self._status_static_msg = (msg, tag)

        status['state'] = tk.NORMAL
        status.delete('1.0', tk.END)
        status.insert('1.0', msg, tag)
        status['state'] = tk.DISABLED
        if delay:
            self._clear_cb_id = status.after(delay, self.clear_status)
        status.update()

    def clear_status(self):
        """Actually prints the "static" message, if any."""
        status = self._status_text

        status.after_cancel(self._clear_cb_id)
        status['state'] = tk.NORMAL
        status.delete('1.0', tk.END)
        status.insert('1.0', *self._status_static_msg)
        status['state'] = tk.DISABLED
        status.update()

    def show_motd(self, delay=21 * 1000, motd_ix=None):
        def show():
            # Do not hide static msgs; reschedule in case they leave.
            #
            if not self._status_static_msg[0]:
                if motd_ix is not None:
                    msg = MOTDs[motd_ix]
                else:
                    msg = random.choice(MOTDs)
                self.status('Tip: %s', msg, level='help')

            self.show_motd()  # Re-schedule motd.

        self._motd_cb_id = self._status_text.after(delay, show)

    def progress(self, step=None, maximum=None):
        """
        :param step:
            Positives, increment step, <=0, set absolute step, None ignored
        :param maximum:
            0 disables progressbar, negatives, set `indeterminate` mode, None ignored.
        """
        progr_bar = self._progr_bar
        progr_var = self._progr_var

        if maximum is not None:
            if maximum == 0:
                progr_bar.grid_forget()
            else:
                mode = 'determinate' if maximum > 0 else 'indeterminate'
                progr_bar.configure(mode=mode, maximum=maximum)
                progr_bar.grid(column=1, row=1, sticky='nswe')

        if step is not None:
            if step < 0:
                progr_var.set(-step)
            else:
                progr_var.set(progr_var.get() + step)

    def get_progress(self):
        progr_bar = self._progr_bar
        return self._progr_var.get(), progr_bar['maximum']

    _about_top_wind = None

    def show_about_window(self, root):
        if self._about_top_wind:
            self._about_top_wind.lift()
            return

        def close_win():
            self._about_top_wind.destroy()
            self._about_top_wind = None

        self._about_top_wind = top = tk.Toplevel(self.root)
        top.transient()
        self._add_window_icon(top)

        top.protocol("WM_DELETE_WINDOW", close_win)
        verbose = logging.getLogger().level <= logging.DEBUG
        show_about(top, verbose=verbose)

    def mainloop(self):
        try:
            self.root.mainloop()
        finally:
            try:
                self.root.destroy()
            except tk.TclError:
                pass


def main():
    app = TkUI()
    app.mainloop()

if __name__ == '__main__':
    if __package__ is None:
        __package__ = "co2mpas"  # @ReservedAssignment
    cmain.init_logging()

    if sys.version_info < (3, 5):
        sys.exit("Sorry, Python >= 3.5 is required,"
                 " but found: {}".format(sys.version_info))
    main()
