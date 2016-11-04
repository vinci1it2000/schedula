#!/usr/bin/env/python
#-*- coding: utf-8 -*-
#
# Copyright 2013-2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
from collections import Counter, OrderedDict
import io
import logging
import pprint
import sys
from textwrap import dedent
from tkinter import StringVar, ttk, filedialog, tix
import traceback

from PIL import Image, ImageTk

from co2mpas import (__version__, __updated__, __copyright__, __license__)
from co2mpas.__main__ import init_logging
from co2mpas.sampling import dice
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
        _log_text.grid(row=0, column=0, sticky=tk.N + tk.S + tk.E + tk.W)

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
        import datetime
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


class PythonVar(tk.StringVar):

    """Value holder for python-code variables."""

    def get(self):
        code = tk.StringVar.get(self)
        return eval(code)


class _MainPanel(tk.Frame):
    def __init__(self, parent, *args, **kwargs):
        tk.Frame.__init__(self, parent, *args, **kwargs)

        slider = tk.PanedWindow(self, orient=tk.HORIZONTAL)
        slider.pack(fill=tk.BOTH, expand=1)

        nb = ttk.Notebook(slider)
        nb.pack(fill=tk.BOTH, expand=1)

        main = tk.Frame(nb, **_sunken)
        self.buttons_frame = tk.Frame(main)
        self.buttons_frame.pack(side=tk.RIGHT, fill=tk.Y)

        self.store_btn = tk.Button(self.buttons_frame, text="Store...",
                                   command=lambda: log.warning('Not Implemented!'),
                                   padx=_pad, pady=_pad)
        self.store_btn.pack(side=tk.BOTTOM, fill=tk.X)
 
        self.reset_btn = tk.Button(self.buttons_frame, text="Reset", fg="red",
                                   command=self._do_reset,
                                   padx=_pad, pady=_pad)
        self.reset_btn.pack(side=tk.BOTTOM, fill=tk.X)
 
        self.run_btn = tk.Button(self.buttons_frame, text="Run", fg="green",
                                 command=self._do_run,
                                 padx=_pad, pady=_pad)
        self.run_btn.pack(side=tk.BOTTOM, fill=tk.X)

        nb.add(main, text='main')
        #prefs = self._make_prefs(nb)
        #nb.add(prefs, text='Preferences')

    def _make_prefs(self, nb):
        prefs = tk.Frame(nb, **_raised)
        lb = tk.Listbox(prefs, font=("Consolas", 8,))

        lb.pack(side=tk.LEFT, fill=tk.X, expand=1)

        return prefs

    def _do_reset(self):
        logging.error(
            'dfdsfdsfs ds asdfaswe qw fasd sdfasdfa fweef fasd fasdf weq fwef  ytukio;lsdra b , io pu7 t54qw asd fjmh gvsad v b \nthw erf ')
        print("Reset!")

    def _do_validate(self, event):
        print("Validate!")

    def _do_run(self):
        logging.info('dfdsfdsfs\n634\ntyutty')
        logging.debug('dfdsfdsfs')


class TkUI(object):

    """
    CO2MPAS UI for predicting NEDC CO2 emissions from WLTP for type-approval purposes.
    """

    def __init__(self, root=None):
        """

        Layout::

            ############################################################
            #.-------------(model_paned)------------------------------.#
            #: _________________  : _________(edit_frame)____________ :#
            #:| *---model       |:| [node_title]    _(action_frame)_ |:#
            #:| | +--tree       |:| [node_value]   |   [run_btn]    ||:#
            #:|   +--from       |:|     ...        |   [rest_btn]   ||:#
            #:|     +--schema <slider>             |________________||:#
            #:|_________________|:|__________________________________|:#
            #'--------------------------------------------------------'#
            # __________________(log_frame)___________________________ #
            #|                                                        |#
            #|________________________________________________________|#
            ############################################################
        """
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

        msg.insert(tk.INSERT, txt1)
        with pkg.resource_stream('co2mpas', 'CO2MPAS_logo.png') as fd:  # @UndefinedVariable
            img = Image.open(fd)
            msg.photo = ImageTk.PhotoImage(img)  # Avoid GC.
            msg.image_create(tk.INSERT, image=msg.photo)
        msg.insert(tk.INSERT, txt2)

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
