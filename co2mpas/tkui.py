#!/usr/bin/env/python
#-*- coding: utf-8 -*-
#
# Copyright 2013-2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
"""
The launching GUI formCO2MPAS.

Layout::

    #####################################################
    #: _________(inputs)_____________                  :#
    #:|                              |                 :#
    #:|                              | [  Add files  ] :#
    #:|                              |                 :#
    #:|                              | [  Add folder ] :#
    #:|______________________________|                 :#
    #: ______________________________                  :#
    #:|______________________________| [ Set Out Dir ] :#
    #: ______________________________                  :#
    #:|______________________________| [Set Template]  :#
    #:                                                 :#
    #:[flag-1] [flag-2] [flag-3] [flag-4]              :#
    #:_________________(extra flags)___________  [Run] :#
    #:|________________________________________|       :#
    #'-------------------------------------------------:#
    # __________________(log_frame)____________________ #
    #|                                                 |#
    #|_________________________________________________|#
    #####################################################

"""
from collections import Counter
import datetime
import io
import logging
import webbrowser
import os
import sys
from textwrap import dedent
from threading import Thread
from tkinter import StringVar, ttk, filedialog, tix
import traceback

from PIL import Image, ImageTk
from toolz import dicttoolz as dtz

from co2mpas import (__version__, __updated__, __copyright__, __license__, __uri__)
from co2mpas.__main__ import init_logging, _main, __doc__ as main_help_doc
import functools as fnt
import os.path as osp
import pkg_resources as pkg
import tkinter as tk


log = logging.getLogger(__name__)

_bw = 2
_pad = 2
_sunken = dict(relief=tk.SUNKEN, padx=_pad, pady=_pad, borderwidth=_bw)
_raised = dict(relief=tk.RAISED, padx=_pad, pady=_pad, borderwidth=_bw)
_ridge = dict(relief=tk.RIDGE, padx=_pad, pady=_pad, borderwidth=_bw)
_courier_font = "courier 8"
app_name = 'co2mpas'

try:
    _levelsMap = logging._levelToName
except AttributeError:
    _levelsMap = {k: v for k, v
                  in logging._levelNames.items()  # @UndefinedVariable PY2-only
                  if isinstance(k, int)}


def labelize_str(s):
    if not s.endswith(':'):
        s += ':'
    return s.title()


def tree_apply_columns(tree, columns):
    tree['columns'] = tuple(c for c, _ in columns if not c.startswith('#'))
    for c, col_kwds in columns:

        h_col_kwds = dtz.keyfilter((lambda k: k in set('text image anchor command'.split())), col_kwds)
        text = h_col_kwds.pop('text', c.title())
        tree.heading(c, text=text, **h_col_kwds)

        c_col_kwds = dtz.keyfilter((lambda k: k in set('anchor minwidth stretch width'.split())), col_kwds)
        tree.column(c, **c_col_kwds)


def get_file_infos(fpath):
    s = os.stat(fpath)
    mtime = datetime.datetime.fromtimestamp(s.st_mtime)  # @UndefinedVariable
    return (s.st_size, mtime.isoformat())



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
            

class LogPanel(tk.LabelFrame):

    """
    Instantiate only once(!), or logging and Tk's ex-handling will get borged.
    """

    LEVELS_MAP = sorted(_levelsMap.items(), reverse=True)

    TAG_META = 'meta'
    TAG_LOGS = 'logs'

    FORMATTER_SPECS = [
        dict(
            fmt='%(asctime)s:%(name)s:%(levelname)s:%(message)s', datefmt=None),
        dict(fmt='%(asctime)s:%(name)s:%(levelname)s:', datefmt=None)
    ]

    initted = False

    def __init__(self, master=None, cnf={}, log_threshold=logging.INFO, logger_name='', formatter_specs=None, **kw):
        """
        :param dict formatter_specs:
            A 2-element array of Formatter-args (note that python-2 has no `style` kw),
            where the 2nd should print only the Metadata.
            If missing, defaults to :attr:`LogPanel.FORMATTER_SPECS`
        :param logger_name:
            What logger to intercept to.
            If missing, defaults to root('') and DOES NOT change its threshold.
        """
        if LogPanel.initted:
            raise RuntimeError("I said instantiate me only ONCE!!!")
        LogPanel.inited = True

        tk.LabelFrame.__init__(self, master=master, cnf=cnf, **kw)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._log_text = _log_text = tk.Text(self,
                                             state=tk.DISABLED, wrap=tk.NONE,
                                             font="Courier 8",
                                             **_sunken
                                             )
        _log_text.grid(row=0, column=0, sticky=(tk.N, tk.S, tk.E, tk.W))

        # Setup scrollbars.
        #
        v_scrollbar = tk.Scrollbar(self)
        v_scrollbar.grid(row=0, column=1, sticky=tk.N + tk.S)
        h_scrollbar = tk.Scrollbar(self, orient=tk.HORIZONTAL)
        h_scrollbar.grid(row=1, column=0, sticky=tk.E + tk.W)
        self._log_text.config(yscrollcommand=v_scrollbar.set)
        v_scrollbar.config(command=self._log_text.yview)
        self._log_text.config(xscrollcommand=h_scrollbar.set)
        h_scrollbar.config(command=self._log_text.xview)

        # Prepare Log-Tags
        #
        tags = [
            [LogPanel.TAG_LOGS, dict(lmargin2='+2c')],
            [LogPanel.TAG_META, dict(font="Courier 7")],

            [logging.CRITICAL, dict(background="red", foreground="yellow")],
            [logging.ERROR, dict(foreground="red")],
            [logging.WARNING, dict(foreground="magenta")],
            [logging.INFO, dict(foreground="blue")],
            [logging.DEBUG, dict(foreground="grey")],
            [logging.NOTSET, dict()],

        ]
        for tag, kws in tags:
            if isinstance(tag, int):
                tag = logging.getLevelName(tag)
            _log_text.tag_config(tag, **kws)
        _log_text.tag_raise(tk.SEL)

        self._log_counters = Counter()
        self._update_title()

        self._setup_logging_components(formatter_specs, log_threshold)

        self._setup_popup(self._log_text)

        self._intercept_logging(logger_name)
        self._intercept_tinker_exceptions()
        self.bind('<Destroy>', self._stop_intercepting_exceptions)

    def _setup_logging_components(self, formatter_specs, log_threshold):
        class MyHandler(logging.Handler):

            def __init__(self2, **kws):  # @NoSelf
                logging.Handler.__init__(self2, **kws)

            def emit(self2, record):  # @NoSelf
                try:
                    self.after_idle(lambda: self._write_log_record(record))
                except Exception:
                    self2.handleError(record)

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
            # Must not raise any errors, or infinite recursion here.
            log.critical('Unhandled TkUI exception:', exc_info=True)
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
            self.log_threshold = self.threshold_var.get()

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
        self.log_popup = tk.Menu(target, tearoff=0)
        self.log_popup.add_cascade(label="Log threshold", menu=threshold_menu)
        self.log_popup.add_cascade(label="Filter levels", menu=filters_menu)
        self.log_popup.add_checkbutton(
            label="Wrap lines", command=self.toggle_text_wrapped)
        self.log_popup.add_separator()
        self.log_popup.add_command(label="Save as...", command=self.save_log)
        self.log_popup.add_separator()
        self.log_popup.add_command(label="Clear logs", command=self.clear_log)

        def popup(event):
            self.log_popup.post(event.x_root, event.y_root)
        target.bind("<Button-3>", popup)

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
        self['text'] = 'Log (%s)' % ', '.join(
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
        try:
            log_text = self._log_text
            # Test FAILS on Python-2! Its ok.
            was_bottom = (log_text.yview()[1] == 1)

            txt = self.formatter.format(record)
            if txt[-1] != '\n':
                txt += '\n'
            txt_len = len(txt) + 1  # +1 ??
            log_start = '%s-%ic' % (tk.END, txt_len)
            metadata_len = len(self.metadata_formatter.formatMessage(record))
            meta_end = '%s-%ic' % (tk.END, txt_len - metadata_len)

            log_text['state'] = tk.NORMAL
            self._log_text.mark_set('LE', tk.END)
            # , LogPanel.TAG_LOGS)
            log_text.insert(tk.END, txt, LogPanel.TAG_LOGS)
            log_text.tag_add(record.levelname, log_start, tk.END)
            log_text.tag_add(LogPanel.TAG_META, log_start, meta_end)
            log_text['state'] = tk.DISABLED

            # Scrolling to the bottom if
            #    log serious or log already at the bottom.
            #
            if record.levelno >= logging.ERROR or was_bottom:
                log_text.see(tk.END)

            self._log_counters.update(['Total', record.levelname])
            self._update_title()
        except Exception:
            # Must not raise any errors, or infinite recursion here.
            print("!!!!!!     Unexpected exception while logging exceptions(!): %s" %
                  traceback.format_exc())


class _MainPanel(tk.Frame):
    def __init__(self, parent, *args, **kwargs):
        tk.Frame.__init__(self, parent, *args, **kwargs)

        slider = tk.PanedWindow(self, orient=tk.HORIZONTAL)
        slider.pack(fill=tk.BOTH, expand=1, padx=4, pady=4)

        main = tk.Frame(slider, **_sunken)
        main.pack(fill=tk.BOTH, expand=1)

        files_frame = self._make_files_frame(main)
        files_frame.pack(fill=tk.X, expand=1)

        buttons_frame = self._make_buttons_frame(main)
        buttons_frame.pack(fill=tk.X, expand=1)

        main.rowconfigure(0, weight=1)

    def _make_files_frame(self, parent):
        frame = tk.Frame(parent)

        kwds = dict(padx=_pad, pady=2 * _pad)
        
        (inp_label, tree, add_files_btn, add_folder_btn) = self._make_inputs_tree(frame)
        inp_label.grid(column=0, row=0, sticky=(tk.W, tk.S))
        tree.grid(column=0, row=1, rowspan=2, sticky=(tk.N, tk.W, tk.E, tk.S), **kwds)
        add_files_btn.grid(column=1, row=1, sticky=(tk.N, tk.E, tk.S), **kwds)
        add_folder_btn.grid(column=1, row=2, sticky=(tk.N, tk.E, tk.S), **kwds)
        self.inputs_tree = tree

        (out_label, out_entry, out_btn, out_var) = self._make_output_folder(frame)
        out_label.grid(column=0, row=4, sticky=(tk.N, tk.W, tk.S))
        out_entry.grid(column=0, row=5, sticky=(tk.N, tk.W, tk.E, tk.S), **kwds)
        out_btn.grid(column=1, row=5, sticky=(tk.N, tk.E, tk.S), **kwds)
        self.out_folder_var = out_var

        (tmpl_label, tmpl_entry, tmpl_btn, tmpl_var) = self._make_template_file(frame)
        tmpl_label.grid(column=0, row=8, sticky=(tk.N, tk.W, tk.S))
        tmpl_entry.grid(column=0, row=9, sticky=(tk.N, tk.W, tk.E, tk.S), **kwds)
        tmpl_btn.grid(column=1, row=9, sticky=(tk.N, tk.E, tk.S), **kwds)
        self.tmpl_folder_var = tmpl_var

        frame.rowconfigure(1, weight=1)
        frame.rowconfigure(2, weight=1)
        frame.columnconfigure(0, weight=1)

        return frame

    def _make_inputs_tree(self, frame):
        inp_label = tk.Label(frame, text='Inputs:')
        tree = ttk.Treeview(frame)
        columns = (
            ('#0', {
                'text': 'Filename',
                'anchor': tk.W,
                'stretch': True,
                'minwidth': 96,
                'width': 264}),
            ('type', {'anchor': tk.W, 'width': 38, 'stretch': False}),
            ('size', {'anchor': tk.E, 'width': 56, 'stretch': False}),
            ('modified', {'anchor': tk.W, 'width': 164, 'stretch': False}),
        )
        tree_apply_columns(tree, columns)

        def ask_input_files():
            files = tix.filedialog.askopenfilenames(
                title='Select CO2MPAS Input file(s)',
                initialdir=os.getcwd(),
                multiple=True,
                filetypes=(('Excel files', '.xlsx .xlsm'),
                           ('All files', '*'),
                           ))
            for fpath in files:
                try:
                    finfos = get_file_infos(fpath)
                    tree.insert('', 'end', fpath, text=fpath, values=('FILE', *finfos))
                except Exception as ex:
                    log.warning("Cannot add file %r due to: %s", fpath, ex)

        def ask_input_folder():
            folder = tix.filedialog.askdirectory(
                title='Select CO2MPAS Input folder',
                initialdir=os.getcwd())
            try:
                finfos = get_file_infos(folder)
                tree.insert('', 'end', folder, text='%s%s' % (folder, osp.sep),
                            values=('FOLDER', *finfos))
            except Exception as ex:
                log.warning("Cannot add folder %r due to: %s", folder, ex)

        files_btn = ttk.Button(frame, text="Add File(s)...", command=ask_input_files)
        folder_btn = ttk.Button(frame, text="Add Folder...", command=ask_input_folder)

        def del_input_file(ev):
            if ev.keysym == 'Delete':
                for item_id in tree.selection():
                    tree.delete(item_id)

        tree.bind("<Key>", del_input_file)

        return (inp_label, tree, files_btn, folder_btn)

    def _make_output_folder(self, frame):
        title = 'Output Folder'
        label = tk.Label(frame, text=labelize_str(title))

        var = StringVar()
        entry = ttk.Entry(frame, textvariable=var)

        def ask_output_folder():
            folder = tix.filedialog.askdirectory(title="Select %s" % title)
            if folder:
                var.set(folder)

        btn = ttk.Button(frame, text="...", command=ask_output_folder)

        return label, entry, btn, var

    def _make_template_file(self, frame):
        title = 'Output Template file'
        label = tk.Label(frame, text=labelize_str(title))

        var = StringVar()
        entry = ttk.Entry(frame, textvariable=var)

        def ask_template_file():
            file = tix.filedialog.askopenfilenames(
                title='Select %s' % title,
                initialdir=os.getcwd(),
                filetypes=(('Excel files', '.xlsx .xlsm'),
                           ('All files', '*'),
                           ))
            if file:
                var.set(file)

        btn = ttk.Button(frame, text="...", command=ask_template_file)

        return label, entry, btn, var

    def _make_buttons_frame(self, parent):
        frame = tk.Frame(parent)
        flags_frame = tk.Frame(frame)
        flags_frame.grid(column=0, row=0, columnspan=3, sticky=(tk.N, tk.W, tk.E, tk.S))

        def make_flag(name):
            var = tk.BooleanVar()
            btn = tk.Checkbutton(flags_frame, text=labelize_str(name.replace('_', ' ')),
                                 variable=var,
                                 padx=_pad, pady=4 * _pad)
            btn.pack(side=tk.LEFT, ipadx=4 * _pad)
            
            return name, var

        flags = (
            'engineering_mode',
            'run_plan',
            'soft_validation',
            'only_summary',
            'plot_workflow',
        )
        self.flag_vars = [make_flag(f) for f in flags]
        
        label = tk.Label(frame, text=labelize_str("Extra Options and Flags"))
        label.grid(column=0, row=2, columnspan=3, sticky=(tk.W, tk.S))
        self.extra_opts_var = StringVar()
        entry = ttk.Entry(frame, textvariable=self.extra_opts_var)
        entry.grid(column=0, row=3, columnspan=3, sticky=(tk.N, tk.W, tk.E, tk.S), ipady=4 * _pad)

        btn = tk.Button(frame, text="Help", fg="green",
                        command=fnt.partial(log.info, '%s', main_help_doc),
                        padx=_pad, pady=_pad)
        btn.grid(column=0, row=4, sticky=(tk.N, tk.W, tk.E, tk.S), ipadx=4 * _pad, ipady=4 * _pad)

        btn = tk.Button(frame, text="Run Normal",
                        command=fnt.partial(self._do_run, is_ta=False),
                        padx=_pad, pady=_pad)
        btn.grid(column=1, row=4, sticky=(tk.N, tk.W, tk.E, tk.S), ipadx=4 * _pad, ipady=4 * _pad)

        btn = tk.Button(frame, text="Run TA", fg="blue",
                        command=fnt.partial(self._do_run, is_ta=True),
                        padx=_pad, pady=_pad)
        btn.grid(column=2, row=4, sticky=(tk.N, tk.W, tk.E, tk.S), ipadx=4 * _pad, ipady=4 * _pad)

        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=2)
        frame.columnconfigure(2, weight=1)
        return frame

    def prepare_args_from_gui(self, is_ta):
        cmd_args = ['ta' if is_ta else 'batch']
        
        cmd_args += self.extra_opts_var.get().split()

        out_folder = self.out_folder_var.get()
        if out_folder:
            cmd_args += ['-O', out_folder]
            
        tmpl_folder = self.tmpl_folder_var.get()
        if tmpl_folder:
            cmd_args += ['-D', 'flag.output_template', tmpl_folder]
            
        for name, flg in self.flag_vars:
            flg = flg.get()
            if flg is not None:
                cmd_args += ['-D', 'flag.%s=%s' % (name, str(flg).lower())]

        inputs = self.inputs_tree.get_children()
        if not inputs:
            cwd = os.getcwd()
            log.warning("No inputs specified; assuming current directory: %s", cwd)
            cmd_args += cwd
        else:
            cmd_args += inputs
            
        return cmd_args
    
    def _do_run(self, is_ta):
        cmd_args = self.prepare_args_from_gui(is_ta)
        
        logging.info('Launching CO2MPAS command:\n  %s', cmd_args)
        t = Thread(target=_main, args=cmd_args, daemon=True)
        t.start()
        
         
class TkUI(object):

    """
    CO2MPAS UI for predicting NEDC CO2 emissions from WLTP for type-approval purposes.
    """
    def __init__(self, root=None):
        if not root:
            root = tk.Tk()
        self.root = root

        root.title("%s-%s" % (app_name, __version__))

        # Menubar
        #
        menubar = tk.Menu(root)
        menubar.add_command(label="About %r" % app_name, command=self._do_about,)
        root['menu'] = menubar

        self.master = master = tk.PanedWindow(root, orient=tk.VERTICAL)
        self.master.pack(fill=tk.BOTH, expand=1)

        experiment_frame = tk.Frame()
        master.add(experiment_frame)

        self.model_panel = _MainPanel(experiment_frame)
        self.model_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)

        self.log_panel = LogPanel(master)
        master.add(self.log_panel, height=240)
        
        s = ttk.Sizegrip(root)
        s.pack(side=tk.RIGHT)
        
    def open_url(self, url):
        webbrowser.open_new(url)
        
    def _do_about(self):
        top = tk.Toplevel(self.master)
        top.title("About %s" % app_name)

        txt1 = '%s\n\n' % self.__doc__.strip()
        txt2 = dedent("""\n

            Version: %s (%s)
            Copyright: %s
            License: %s
            Python: %s
            """ % (__version__, __updated__, __copyright__, __license__, sys.version))
        txt = '%s\n\n%s' % (txt1, txt2)
        log.info(txt)
        print(txt)

        msg = tk.Text(top, wrap=tk.NONE)
        msg.pack(fill=tk.BOTH, expand=1)
        linkman = HyperlinkManager(msg)

        msg.insert(tk.INSERT, txt1)
        with pkg.resource_stream('co2mpas', 'CO2MPAS_logo.png') as fd:  # @UndefinedVariable
            img = Image.open(fd)
            msg.photo = ImageTk.PhotoImage(img)  # Avoid GC.
            msg.image_create(tk.INSERT, image=msg.photo)
        msg.insert(tk.INSERT, txt2)
        msg.insert(tk.INSERT, 'Home: %s' % __uri__,
                   linkman.add(fnt.partial(self.open_url, __uri__)))

        msg.configure(state=tk.DISABLED, bg='LightBlue')

    def mainloop(self):
        try:
            self.root.mainloop()
        finally:
            try:
                self.root.destroy()
            except tk.TclError:
                pass


def main():
    init_logging(verbose=None)
    app = TkUI()
    app.mainloop()

if __name__ == '__main__':
    if __package__ is None:
        __package__ = "co2mpas"  # @ReservedAssignment
    main()
