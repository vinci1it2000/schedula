#!/usr/bin/env python
#-*- coding: utf-8 -*-
#
# Copyright 2013-2014 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
# from wltp import model

from __future__ import division, print_function, unicode_literals

from collections import Counter
import logging
import sys
from textwrap import dedent
import threading
import traceback
from wltp import model
import wltp


try:
    from tkinter import ttk

    import tkinter as tk
    from tkinter import StringVar
except ImportError:
    import Tkinter as tk
    import ttk
    from Tkinter import StringVar



log = logging.getLogger(__name__)

_bw = 2
_pad = 2
_sunken = dict(relief=tk.SUNKEN, padx=_pad, pady=_pad, borderwidth=_bw)
_ridge = dict(relief=tk.RIDGE, padx=_pad, pady=_pad, borderwidth=_bw)



class LogPanel(tk.LabelFrame):
    """
    Instantiate only once(!), or logging and Tk's ex-handling will get borged.
    """
    LEVELS_MAP = sorted(logging._levelToName.items(), reverse=True)

    TAG_META = 'meta'
    TAG_LOGS     = 'logs'

    FORMATTER_SPECS = [
        dict(fmt='%(asctime)s:%(name)s:%(levelname)s:%(message)s\n', datefmt=None),
        dict(fmt='%(asctime)s:%(name)s:%(levelname)s:', datefmt=None)
    ]

    initted = False
    def __init__(self, master=None, cnf={}, log_threshold=logging.INFO, logger='', formatter_specs=None, **kw):
        """
        :param dict formatter_specs: A 2-element array of Formatter-args (note that python-2 has no `style` kw), 
                                    where the 2nd should print only the Metadata. 
                                    If missing, defaults to :attr:`LogPanel.FORMATTER_SPECS`
        :param logger: What logger to intercept to. If missing, defaults to root('') and DOES NOT change its threshold.
        """
        if LogPanel.initted:
            raise RuntimeError("I said instantiate me only ONCE!!!")
        LogPanel.inited = True
        
        tk.LabelFrame.__init__(self, master=master, cnf=cnf, **kw)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._log_text = _log_text=tk.Text(self,
                state=tk.DISABLED, wrap=tk.NONE,
                font="Courier 8",
                **_sunken
        )
        _log_text.grid(row=0, column=0, sticky=tk.N+tk.S+tk.E+tk.W)

        ## Setup scrollbars.
        #
        v_scrollbar = tk.Scrollbar(self)
        v_scrollbar.grid(row=0, column=1, sticky=tk.N+tk.S)
        h_scrollbar = tk.Scrollbar(self, orient=tk.HORIZONTAL)
        h_scrollbar.grid(row=1, column=0, sticky=tk.E+tk.W)
        self._log_text.config(yscrollcommand=v_scrollbar.set)
        v_scrollbar.config(command=self._log_text.yview)
        self._log_text.config(xscrollcommand=h_scrollbar.set)
        h_scrollbar.config(command=self._log_text.xview)

        ## Prepare Log-Tags
        #
        tags = [
            [LogPanel.TAG_LOGS, dict(lmargin2='+2c')],
            [LogPanel.TAG_META, dict(font="Courier 7")],
            
            [logging.CRITICAL,  dict(background="red", foreground="yellow")],
            [logging.ERROR,     dict(foreground="red")],
            [logging.WARNING,   dict(foreground="magenta")],
            [logging.INFO,      dict(foreground="blue")],
            [logging.DEBUG,     dict(foreground="grey")],
            [logging.NOTSET,    dict()],

        ]
        for tag, kws in tags:
            if isinstance(tag, int):
                tag = logging.getLevelName(tag)
            _log_text.tag_config(tag, **kws)

        self._log_counters = Counter()
        self._update_title()
        
        self._setup_logging_components(formatter_specs, log_threshold)
        
        self._setup_popup(self._log_text)
        
        self._intercept_logging(logger)
        self._intercept_tinker_exceptions()

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


    def _intercept_logging(self, logger):
        def show_error(tk_self,*args):
            ## Must not raise any errors, or infinite recursion here.
            log.critical('TkUI failed!', exc_info=True)

        self._original_tk_ex_handler = tk.Tk.report_callback_exception
        tk.Tk.report_callback_exception = show_error

        root_logger = logging.getLogger(logger)
        root_logger.addHandler(self._handler)

    def _intercept_tinker_exceptions(self):
        def show_error(tk_self,*args):
            ## Must not raise any errors, or infinite recursion here.
            log.critical('TkUI failed!', exc_info=True)

        self._original_tk_ex_handler = tk.Tk.report_callback_exception
        tk.Tk.report_callback_exception = show_error

    def _stop_intercepting_exceptions(self):
        root_logger = logging.getLogger()
        root_logger.removeHandler(self._handler)

    def destroy(self):
        self._stop_intercepting_exceptions()
        tk.Frame.destroy(self)

    def _setup_popup(self, target):
        levels_map = LogPanel.LEVELS_MAP
        
        ## Threshold sub-menu
        #
        def change_threshold():
            self.log_threshold = self.threshold_var.get()
        threshold_menu = tk.Menu(target, tearoff=0)
        for lno, lname in levels_map:
            threshold_menu.add_radiobutton(
                    label=lname, value=lno, 
                    variable = self.threshold_var, 
                    command=change_threshold
            )
        filters_menu = tk.Menu(target, tearoff=0)
        
        ## Filters sub-menu
        #
        self._filter_vars = [tk.BooleanVar(name=lname) for _, lname in levels_map]
        for i, (lno, lname) in enumerate(levels_map):
            filters_menu.add_checkbutton(
                    label=lname, 
                    variable = self._filter_vars[i], 
                    command=self._apply_filters
            )

        ## Popup menu
        #        
        self.log_popup = tk.Menu(target, tearoff=0)
        self.log_popup.add_cascade(label="Log threshold", menu=threshold_menu)
        self.log_popup.add_cascade(label="Filter levels", menu=filters_menu)
        self.log_popup.add_separator()
        self.log_popup.add_checkbutton(label="Wrap lines", command=self.toggle_text_wrapped)
        self.log_popup.add_separator()
        self.log_popup.add_command(label="Clear logs", command=self.clear_log)

        def popup(event):
            self.log_popup.post(event.x_root, event.y_root)
        target.bind("<Button-3>", popup)
    
    def _apply_filters(self):
        for level_var in self._filter_vars:
            self._log_text.tag_configure(level_var._name, elide=level_var.get())
    
    @property
    def log_threshold(self):
        return self._handler.level
    @log_threshold.setter
    def log_threshold(self, level):
        logging.getLogger().setLevel(level)
        self._handler.setLevel(level)
        self.threshold_var.set(level)

    def toggle_text_wrapped(self):
        self._log_text['wrap'] = tk.WORD if self._log_text['wrap'] == tk.NONE else tk.NONE

    def _update_title(self):
        levels = ['Totals'] + [lname for _, lname in LogPanel.LEVELS_MAP]
        levels_counted = [ (lname, self._log_counters[lname]) for lname in levels]
        self['text'] = 'Log (%s)' % ', '.join('%s: %i' % (lname, count) for lname, count in levels_counted if count)
    
    def clear_log(self):
        self._log_text['state'] = tk.NORMAL
        self._log_text.delete('1.0', tk.END)
        self._log_text['state'] = tk.DISABLED
        self._log_counters.clear()
        self._update_title()
    
    def _write_log_record(self, record):
        try:
            was_bottom = (self._log_text.yview()[1] == 1) ## Test FAILS on Python-2! Its ok.
            
            txt = self.formatter.format(record)
            txt_len = len(txt)+1 #+1 ??
            metadata_len = len(self.metadata_formatter.formatMessage(record))
            log_start = '%s-%ic'%(tk.END, txt_len)
            meta_end = '%s-%ic'%(tk.END, txt_len-metadata_len)

            self._log_text['state'] = tk.NORMAL
            self._log_text.insert(tk.END, txt, LogPanel.TAG_LOGS)#, LogPanel.TAG_LOGS)
            self._log_text.tag_add(record.levelname, log_start, tk.END)
            self._log_text.tag_add(LogPanel.TAG_META, log_start, meta_end)
            self._log_text['state'] = tk.DISABLED


            ## Scrolling to the bottom if
            #    log serious or log already at the bottom.
            #
            if record.levelno >= logging.ERROR or was_bottom:
                self._log_text.see(tk.END)
            
            self._log_counters.update(['Totals', record.levelname])
            self._update_title()
        except Exception:
            ## Must not raise any errors, or infinite recursion here.
            print("!!!!!!     Unexpected exception while logging exceptions(!): %s" % traceback.format_exc())


class _ModelPanel(tk.PanedWindow):
    MDLVAL = "Value"
    TITLE = "Title"
    DESC = "Description"
    SCHEMA = '_schema'

    SCHEMA = '_schema'

    COLUMNS = [MDLVAL, TITLE, DESC, SCHEMA]

    def __init__(self, parent, wltp_app, *args, **kwargs):
        tk.PanedWindow.__init__(self, parent, *args, **kwargs)
        self.configure(orient=tk.HORIZONTAL)

        self.model_tree = self._build_tree(self)
        self.add(self.model_tree)


        ## EDIT FRAME ##########################
        edit_frame = tk.LabelFrame(self, text='Modify model node', **_sunken)
        self.add(edit_frame)

        tk.Label(edit_frame, text="Node:", anchor=tk.E).grid(row=0)
        tk.Label(edit_frame, text="Title:", anchor=tk.E).grid(row=1)
        tk.Label(edit_frame, text="Value:", anchor=tk.E).grid(row=2)
        tk.Label(edit_frame, text="Desc:", anchor=tk.E).grid(row=3)

        self.node_name = tk.Label(edit_frame)#,  **_sunken)
        self.node_name.grid(row=0, column=1, sticky=tk.W+tk.E)
        self.node_title = tk.Label(edit_frame)#,  **_sunken)
        self.node_title.grid(row=1, column=1, sticky=tk.W+tk.E)

        self.node_value = StringVar()
        #self.node_value.trace('w',  lambda nm,  idx,  mode,  var=sv: validate_float(var))
        self.node_entry = tk.Entry(edit_frame,
                textvariable=self.node_value, state=tk.DISABLED,
#                validate=tk.ALL,
#                validatecommand=self._do_validate,
        )
        self.node_entry.grid(row=2, column=1, sticky=tk.W+tk.E+tk.N+tk.S)

        self.node_desc = tk.Label(edit_frame, justify=tk.LEFT, anchor=tk.NW, **_ridge)
        self.node_desc.grid(row=3, column=1, sticky=tk.W+tk.E+tk.N+tk.S)

        edit_frame.grid_columnconfigure(1, weight=1)
        edit_frame.grid_rowconfigure(2, weight=21)
        edit_frame.grid_rowconfigure(3, weight=13)


        self.buttons_frame = tk.Frame(edit_frame)
        self.buttons_frame.grid(row=0, column=3, rowspan=4, sticky=tk.W+tk.S, padx=4)

        self.run_btn = tk.Button(self.buttons_frame, text="Run", fg="green", command=wltp_app._do_run,
            padx=_pad, pady=_pad)
        self.run_btn.pack(side=tk.TOP, fill=tk.X)

        self.reset_btn = tk.Button(self.buttons_frame, text="Reset", fg="red", command=wltp_app._do_reset,
            padx=_pad, pady=_pad)
        self.reset_btn.pack(side=tk.TOP, fill=tk.X)

        about_btn = tk.Button(self.buttons_frame, text="About...", command=wltp_app._do_about,
            padx=_pad, pady=_pad)
        about_btn.pack(side=tk.TOP, fill=tk.X)
        ## EDIT FRAME ##########################


    def _build_tree(self, root):


        tree = ttk.Treeview(root, columns=_ModelPanel.COLUMNS, displaycolumns=(_ModelPanel.TITLE, _ModelPanel.MDLVAL))
        tree.column(_ModelPanel.MDLVAL)
        tree.column(_ModelPanel.TITLE, width=100)
        tree.heading(_ModelPanel.MDLVAL, text=_ModelPanel.MDLVAL)
        tree.heading(_ModelPanel.TITLE, text=_ModelPanel.TITLE)
        tree.heading(_ModelPanel.DESC, text=_ModelPanel.DESC)

        tree.insert("" , 0, iid='/', text="Model",  open=True)

        tree.bind('<<TreeviewSelect>>', self.do_node_selected)

        return tree

    def bind_model(self, data, schema):
        tree = self.model_tree
        id2 = tree.insert("/", 1, "dir2", text="Dir 2")
        tree.insert(id2, "end", "dir 2", text="sub dir 2", values=("2A", "BAR", "Al ot \nof test\n f2B", 5))

        tree.insert("/", 3, "dir3", text="Dir 3")
        tree.insert("dir3", 3, text=" sub dir 3", values=("3A", 'ttttt [rpm]', " 3B", 7))

    def do_node_selected(self, event):
        tree = self.model_tree
        sel = tree.selection()

        nsel = len(sel)
        mdlval = ''
        title = ''
        desc = ''
        self.node_entry['state'] = tk.DISABLED
        if nsel > 1:
            values = tree.item(sel[0], option='values')
            uniq_mdl_vals = len({tree.item(s[0], option='values') for s in sel if s})
            title = '<%selected %i (%i uniques)>' % (nsel, uniq_mdl_vals)
        elif nsel == 1:
            self.node_entry['state'] = tk.NORMAL
            values = tree.item(sel[0], option='values')
            if values:
                mdlval, title, desc = values[0:3]

        self.node_title['text'] = title
        self.node_value.set(mdlval)
        self.node_desc['text'] = desc
        print("Selected %s, %s!"%(title, mdlval))
        print(title)

    def do_update_node_value(self, event):
        tree = self.model_tree
        sel = tree.selection()

        for node in sel:
            tree

        print("Update %s!"%event)
        return False


class TkWltp:
    """
    A basic desktop UI to read and modify a WLTP model,  run an experiment,  and store the results.
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

        self._task_poll_delay = 70

        root.title("TkWltp")
        self.master = master = tk.PanedWindow(root, orient=tk.VERTICAL)
        self.master.pack(fill=tk.BOTH, expand=1)

        self.model_panel = _ModelPanel(master, self)
        master.add(self.model_panel)

        self.log_panel = LogPanel(master)
        master.add(self.log_panel)

        self.model_panel.bind_model(model._get_model_base(), model._get_model_schema())


    def _do_about(self):
        top = tk.Toplevel(self.master)
        top.title("About TkWltp")

        txt = dedent("""\
            %s: %s

            Version: %s (%s)
            Copyright: %s
            License: %s
            Python: %s
            """%(self.__class__.__name__, self.__doc__,
                wltp.__version__, wltp.__updated__, wltp.__copyright__, wltp.__license__,
                sys.version))
        log.info(txt)
        print(txt)
        msg = tk.Message(top, text=txt, anchor=tk.NW, justify=tk.LEFT)
        msg.pack(fill=tk.BOTH, expand=1)

    def _do_reset(self):
        logging.error('dfdsfdsfs ds asdfaswe qw fasd sdfasdfa fweef fasd fasdf weq fwef  ytukio;lsdra b , io pu7 t54qw asd fjmh gvsad v b \nthw erf ')
        print("Reset!")

    def _do_validate(self, event):
        print("Validate!")

    def _do_run(self):
        logging.info('dfdsfdsfs\n634\ntyutty')
        logging.debug('dfdsfdsfs')



    def mainloop(self):
        try:
            self.root.mainloop()
        finally:
            try:
                self.root.destroy()
            except tk.TclError:
                pass



if __name__ == '__main__':
    app = TkWltp()
    app.mainloop()

