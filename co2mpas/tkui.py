#!/usr/bin/env/python
#-*- coding: utf-8 -*-
#
# Copyright 2013-2014 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
# from wltp import model
"""
Not Python-2 compatible!
"""

from collections import Counter, OrderedDict
import logging
import sys
from textwrap import dedent
try:
    from tkinter import StringVar
except ImportError:
    raise NotImplementedError("TkWltp is only supported on Python-3; not in Python-%s!" % sys.version_info[0])

from tkinter import ttk
import traceback
from wltp import model
import wltp

from PIL import Image, ImageTk

import pkg_resources as pkg
import tkinter as tk


log = logging.getLogger(__name__)

_bw = 2
_pad = 2
_sunken = dict(relief=tk.SUNKEN, padx=_pad, pady=_pad, borderwidth=_bw)
_ridge = dict(relief=tk.RIDGE, padx=_pad, pady=_pad, borderwidth=_bw)
_courier_font = "courier 8"


class LogPanel(tk.LabelFrame):
    """
    Instantiate only once(!), or logging and Tk's ex-handling will get borged.
    """
    LEVELS_MAP = sorted(logging._levelToName.items(), reverse=True)

    TAG_META = 'meta'
    TAG_LOGS     = 'logs'

    FORMATTER_SPECS = [
        dict(fmt='%(asctime)s:%(name)s:%(levelname)s:%(message)s', datefmt=None),
        dict(fmt='%(asctime)s:%(name)s:%(levelname)s:', datefmt=None)
    ]

    initted = False
    def __init__(self, master=None, cnf={}, log_threshold=logging.INFO, logger_name='', formatter_specs=None, **kw):
        """
        :param dict formatter_specs: A 2-element array of Formatter-args (note that python-2 has no `style` kw), 
                                    where the 2nd should print only the Metadata. 
                                    If missing, defaults to :attr:`LogPanel.FORMATTER_SPECS`
        :param logger_name: What logger to intercept to. If missing, defaults to root('') and DOES NOT change its threshold.
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
            ## Must not raise any errors, or infinite recursion here.
            log.critical('Unhandled TkUI exception:', exc_info=True)
            self._original_tk_ex_handler(*args)
            
        self._original_tk_ex_handler = tk.Tk.report_callback_exception
        tk.Tk.report_callback_exception = my_ex_interceptor

    def _stop_intercepting_exceptions(self, event):
        root_logger = logging.getLogger()
        root_logger.removeHandler(self._handler)

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
            log_text = self._log_text
            was_bottom = (log_text.yview()[1] == 1) ## Test FAILS on Python-2! Its ok.
            
            txt = self.formatter.format(record)
            txt_len = len(txt)+1 #+1 ??
            metadata_len = len(self.metadata_formatter.formatMessage(record))
            meta_end = '%s-%ic'%(tk.END, txt_len-metadata_len)

            log_text['state'] = tk.NORMAL
            self._log_text.mark_set('LE', tk.END)
            log_text.insert(tk.END, txt, LogPanel.TAG_LOGS)#, LogPanel.TAG_LOGS)
            log_text.tag_add(record.levelname, log_start, tk.END)
            log_text.tag_add(LogPanel.TAG_META, log_start, meta_end)
            log_text['state'] = tk.DISABLED


            ## Scrolling to the bottom if
            #    log serious or log already at the bottom.
            #
            if record.levelno >= logging.ERROR or was_bottom:
                log_text.see(tk.END)
            
            self._log_counters.update(['Total', record.levelname])
            self._update_title()
        except Exception:
            ## Must not raise any errors, or infinite recursion here.
            print("!!!!!!     Unexpected exception while logging exceptions(!): %s" % traceback.format_exc())


class PythonVar(tk.StringVar):
    """Value holder for python-code variables."""
    def get(self):
        code = tk.StringVar.get(self)
        return eval(code)



class _ModelPanel(tk.LabelFrame):
    MDLVAL = "Value"
    TITLE = "Title"
    DESC = "Description"
    SCHEMA = '_schema'

    TAG_ERROR       = 'err'
    TAG_MISSING     = 'mis'
    TAG_REQUIRED    = 'req'
    TAG_VIRTUAL     = 'vrt'
    TAG_EXTRA       = 'xtr'
    
    NODE_TYPES = OrderedDict([
        ('str',     dict(var=tk.StringVar,   btn_kws={})),
        ('int',     dict(var=tk.IntVar,      btn_kws={})),
        ('float',   dict(var=tk.DoubleVar,   btn_kws={})),
        ('bool',    dict(var=tk.BooleanVar,  btn_kws={})),
        ('<null>',  dict(var=None,           btn_kws={'fg': 'blue'})),
        ('<python>', dict(var=PythonVar,     btn_kws={'fg': 'blue'})),
    ])

    COLUMNS = [MDLVAL, TITLE, DESC, SCHEMA]

    def __init__(self, parent, *args, **kwargs):
        tk.LabelFrame.__init__(self, parent, *args, **kwargs)
        self['text']='Model path: TODO@@@'
        
        slider = tk.PanedWindow(self, orient=tk.HORIZONTAL)
        slider.pack(fill=tk.BOTH, expand=1)

        self.model_tree = self._build_tree(slider)
        slider.add(self.model_tree)

        ## EDIT FRAME ##########################
#        node_slider = tk.PanedWindow(self, orient=tk.VERTICAL, **_sunken)
        edit_frame = tk.Frame(slider, **_sunken)
        slider.add(edit_frame)
        edit_frame.grid_columnconfigure(0, weight=1)
        edit_frame.grid_rowconfigure(1, weight=13)
        edit_frame.grid_rowconfigure(4, weight=21)

        self.node_title = tk.Label(edit_frame)#,  **_sunken)
        self.node_title.grid(row=0, column=0, sticky=tk.W+tk.E)

        self.node_desc = tk.Label(edit_frame, justify=tk.LEFT, anchor=tk.NW, **_ridge)
        self.node_desc.grid(row=1, column=0, sticky=tk.W+tk.E+tk.N+tk.S)

        ## Types
        #
        menu1 = tk.Frame(edit_frame)  
        menu1.grid(row=2, column=0, sticky=tk.W+tk.E)
        
        menu2 = tk.Frame(edit_frame)        
        menu2.grid(row=3, column=0, sticky=tk.W)
#        menu2 = menu1        
        tk.Button(menu2, text='Delete...', fg='red', command=None).pack(side=tk.LEFT)
        tk.Button(menu2, text='Move...', command=None).pack(side=tk.LEFT)
        tk.Button(menu2, text='Clone...', command=None).pack(side=tk.LEFT)
        tk.Button(menu2, text='Load...', fg='blue', command=None).pack(side=tk.LEFT)
        
        #self.node_var.trace('w',  lambda nm,  idx,  mode,  var=sv: validate_float(var))
        self._node_entry = tk.Entry(edit_frame,
                state=tk.DISABLED,
#                validate=tk.ALL,
#                validatecommand=self._do_validate,
        )
        self._node_entry.grid(row=4, column=0, sticky=tk.W+tk.E+tk.N+tk.S)
        ## EDIT FRAME ##########################

        self._build_types_selector(menu1)

    def _build_tree(self, root):


        tree = ttk.Treeview(root, columns=_ModelPanel.COLUMNS, displaycolumns=(_ModelPanel.TITLE, _ModelPanel.MDLVAL))
        tree.column(_ModelPanel.MDLVAL)
        tree.column(_ModelPanel.TITLE, width=100)
        tree.heading(_ModelPanel.MDLVAL, text=_ModelPanel.MDLVAL)
        tree.heading(_ModelPanel.TITLE, text=_ModelPanel.TITLE)
        tree.heading(_ModelPanel.DESC, text=_ModelPanel.DESC)

        tree.insert("" , 0, iid='/', text="Model",  open=True)

        tree.bind('<<TreeviewSelect>>', self._do_node_selected)

        tags = [
            [_ModelPanel.TAG_ERROR,     dict(foreground="red")],
            [_ModelPanel.TAG_MISSING,   dict(background="grey")],
            [_ModelPanel.TAG_REQUIRED,  dict(font="underline")],
            [_ModelPanel.TAG_VIRTUAL,   dict(foreground="blue", font="italic")],
            [_ModelPanel.TAG_EXTRA,     dict(font="arial overstrike")],
        ]
        for tag, kws in tags:
            _log_text.tag_config(tag, **kws)
        _log_text.tag_raise(tk.SEL)

        
        return tree

    def bind_model(self, data, schema):
        tree = self.model_tree
        id2 = tree.insert("/", 1, "dir2", text="Dir 2")
        tree.insert(id2, "end", "dir 2", text="sub dir 2", values=("2A", "BAR", "Al ot \nof test\n f2B", 5))

        tree.insert("/", 3, "dir3", text="Dir 3")
        tree.insert("dir3", 3, text=" sub dir 3", values=("3A", 'ttttt [rpm]', " 3B", 7))

    def _set_edit_value(self, value):
        self._node_entry['textvariable'].set(value)

    def _get_tree_node(self):        
        tree = self.model_tree
        sel = tree.selection()

        nsel = len(sel)
        mdlval = ''
        title = ''
        desc = ''
        if nsel > 1:
            values = tree.item(sel[0], option='values')
            uniq_mdl_vals = len({tree.item(s[0], option='values') for s in sel if s})
            title = '<%selected %i (%i uniques)>' % (nsel, uniq_mdl_vals)
        elif nsel == 1:
            values = tree.item(sel[0], option='values')
            if values:
                mdlval, title, desc = values[0:3]

        return (nsel, mdlval, title, desc)
        
    def _do_node_selected(self, event):
        (nsel, mdlval, title, desc) = self._get_tree_node()

        self.node_title['text'] = title
        self._set_edit_value(mdlval)
        self.node_desc['text'] = desc
#        self._node_entry['state'] = tk.DISABLED
#        self._node_entry['state'] = tk.NORMAL
        print("Selected %s, %s!"%(title, mdlval))
        print(title)

    def _do_update_tree_node(self, event):
        tree = self.model_tree
        sel = tree.selection()

        for node in sel:
            tree

        print("Update %s!"%event)
        return False

    def _build_types_selector(self, parent):
        first_type = next(iter(_ModelPanel.NODE_TYPES.keys()))
        self._type_var = v = tk.StringVar(value=first_type)
        for k, v in _ModelPanel.NODE_TYPES.items():
            tk.Radiobutton(parent, text=k, font=_courier_font, 
                variable=v, value=k, 
                command=self._do_type_selected, **v['btn_kws']).pack(side=tk.LEFT)
#        self._do_type_selected() ## To install var in edit_entry.
                
    def _do_type_selected(self):
        typ = self._type_var.get()
        var = _ModelPanel.NODE_TYPES[typ]['var']()
        self._node_entry['textvariable'] = var
        (nsel, mdl_value) = self._get_tree_node()[:2]
        if nsel == 1:
            self._set_edit_value(mdl_value)

class TkWltp:
    """
    A basic desktop UI to read and modify a WLTP model, run experiment, and store its results.
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
        
        root.title("TkWltp-%s" % wltp.__version__)

        ## Menubar
        #
        menubar = tk.Menu(root)
        menubar.add_command(label="About TkWltp", command=self._do_about,)
        root['menu'] = menubar
        
        
        self.master = master = tk.PanedWindow(root, orient=tk.VERTICAL)
        self.master.pack(fill=tk.BOTH, expand=1)

        experiment_frame = tk.Frame()
        master.add(experiment_frame)

        self.model_panel = _ModelPanel(experiment_frame)
        self.model_panel.pack(side=tk.LEFT,fill=tk.BOTH, expand=1)
        

        
        self.log_panel = LogPanel(master)
        master.add(self.log_panel)



        self.buttons_frame = tk.Frame(experiment_frame)
        self.buttons_frame.pack(side=tk.RIGHT,fill=tk.Y)

        about_btn = tk.Button(self.buttons_frame, text="Store...", command=lambda:log.warning('Not Implemented!'),
            padx=_pad, pady=_pad)
        about_btn.pack(side=tk.BOTTOM, fill=tk.X)

        self.reset_btn = tk.Button(self.buttons_frame, text="Reset", fg="red", command=self._do_reset,
            padx=_pad, pady=_pad)
        self.reset_btn.pack(side=tk.BOTTOM, fill=tk.X)

        self.run_btn = tk.Button(self.buttons_frame, text="Run", fg="green", command=self._do_run,
            padx=_pad, pady=_pad)
        self.run_btn.pack(side=tk.BOTTOM, fill=tk.X)


        self.model_panel.bind_model(model._get_model_base(), model._get_model_schema())


    def _do_about(self):
        top = tk.Toplevel(self.master)
        top.title("About TkWltp")

        txt1 = '%s\n\n'%self.__doc__.strip()
        txt2 = dedent("""\n
            
            Version: %s (%s)
            Copyright: %s
            License: %s
            Python: %s
            """ %(wltp.__version__, wltp.__updated__, wltp.__copyright__, wltp.__license__,
                sys.version))
        txt = '%s\n\n%s' % (txt1, txt2)
        log.info(txt)
        print(txt)

        msg = tk.Text(top, wrap=tk.NONE)
        msg.pack(fill=tk.BOTH, expand=1)
        
        msg.insert(tk.INSERT, txt1)
        with pkg.resource_stream('wltp', '../docs/wltc_class3b.png') as fd: #@UndefinedVariable
            img = Image.open(fd)
            msg.photo = ImageTk.PhotoImage(img)  # Avoid GC.
            msg.image_create(tk.INSERT, image=msg.photo)
        msg.insert(tk.INSERT, txt2)

        msg.configure(state= tk.DISABLED, bg='LightBlue')

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


def main():
    app = TkWltp()
    app.mainloop()

if __name__ == '__main__':
    logging.getLogger().setLevel(logging.DEBUG)
    main()
