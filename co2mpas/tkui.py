#!/usr/bin/env python
#-*- coding: utf-8 -*-
#
# Copyright 2013-2014 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
# from wltp import model


from textwrap import dedent

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


#__updated__ = "2014-10-10"

_bw = 2
_pad = 2
_sunken = dict(relief=tk.SUNKEN, padx=_pad, pady=_pad, borderwidth=_bw)
_ridge = dict(relief=tk.RIDGE, padx=_pad, pady=_pad, borderwidth=_bw)

class MPanel(object):
    MDLVAL  = "Value"
    TITLE   = "Title"
    DESC    = "Description"
    SCHEMA  = '_schema'
    
    COLUMNS = [MDLVAL, TITLE, DESC, SCHEMA]
    

        
class TkWltp:
    """
    A basic dektop UI to read and modify a WLTP model, run an experiment, and store the results.
    """

    def __init__(self, root=None):
        """
        
        Layout::
        
            ################################################
            # ____________(model_paned)___________________ #   
            #|                          || _(edit_frame)_ |#   
            #| *---model                ||| (node_title) ||#
            #| | +--tree                ||| (node_value) ||#
            #|   +--from             <slider>   ...      ||#
            #|     +--schema            |||______________||#
            #|__________________________|||_______________|#
            # _____________(buttons_frame)________________ #
            #|          (about_btn) (reset_btn) (run_btn) |#
            #|____________________________________________|#
            ################################################
        """
        
        if not root:
            root = tk.Tk()
        root.title("TkWltp")
        self.master = master = tk.Frame(root)
        self.master.pack(fill=tk.BOTH, expand=1)
        
        ## MODEL PANEL ##########################
        model_paned = tk.PanedWindow(master, orient=tk.HORIZONTAL)
        model_paned.pack(side=tk.TOP, fill=tk.BOTH, expand=1)
        
        self.model_tree = self._build_tree_from_schema(model_paned, model._get_model_schema())
        model_paned.add(self.model_tree)


        edit_frame = tk.Frame(model_paned, **_sunken)
        model_paned.add(edit_frame)
        
        tk.Label(edit_frame, text="Name:", anchor=tk.E).grid(row=0)
        tk.Label(edit_frame, text="Title:", anchor=tk.E).grid(row=1)
        tk.Label(edit_frame, text="Value:", anchor=tk.E).grid(row=2)
        tk.Label(edit_frame, text="Desc:", anchor=tk.E).grid(row=3)

        self.node_name = tk.Label(edit_frame)#, **_sunken)
        self.node_name.grid(row=0, column=1, sticky=tk.W+tk.E)
        self.node_title = tk.Label(edit_frame)#, **_sunken)
        self.node_title.grid(row=1, column=1, sticky=tk.W+tk.E)
        
        self.node_value = StringVar()
        #self.node_value.trace('w', lambda nm, idx, mode, var=sv: validate_float(var))
        self.node_entry = tk.Entry(edit_frame, 
                textvariable=self.node_value, state=tk.DISABLED,
#                validate=tk.ALL,
#                validatecommand=self.do_validate,
        )
        self.node_entry.grid(row=2, column=1, sticky=tk.W+tk.E+tk.N+tk.S)
        
        self.node_desc = tk.Label(edit_frame, justify=tk.LEFT, anchor=tk.NW, **_ridge)
        self.node_desc.grid(row=3, column=1, sticky=tk.W+tk.E+tk.N+tk.S)

        edit_frame.grid_columnconfigure(1, weight=1)
        edit_frame.grid_rowconfigure(2, weight=1)
        edit_frame.grid_rowconfigure(3, weight=1)
        ## MODEL PANEL ##########################
        
        
        self.buttons_frame = tk.Frame(master)
        self.buttons_frame.pack(side=tk.BOTTOM, fill=tk.X)

        self.run_btn = tk.Button(self.buttons_frame, text="Run", fg="green", command=self.do_run,
            padx=_pad, pady=_pad)
        self.run_btn.pack(side=tk.RIGHT)
        
        self.reset_btn = tk.Button(self.buttons_frame, text="Reset", fg="red", command=self.do_quit,
            padx=_pad, pady=_pad)
        self.reset_btn.pack(side=tk.RIGHT)
        
        about_btn = tk.Button(self.buttons_frame, text="About...", command=self.do_about,
            padx=_pad, pady=_pad)
        about_btn.pack(side=tk.RIGHT)



    def do_about(self):
        top = tk.Toplevel(self.master)
        top.title("About TkWltp")
        
        txt = dedent("""\
            %s: %s
            
            Version: %s (%s)
            Copyright: %s
            License: %s
        """ % (self.__class__.__name__, self.__doc__, wltp.__version__, wltp.__updated__, wltp.__copyright__, wltp.__license__, ))
        msg = tk.Message(top, text=txt, anchor=tk.NW, justify=tk.LEFT)
        msg.pack(fill=tk.BOTH, expand=1)        
        
    def do_reset(self):
        print("Reset!")

    def do_validate(self, event):
        print("Validate!")

    def do_run(self):
        print("RUN")

    def do_quit(self):
        self.master.quit

    def _build_tree_from_schema(self, root, schema):

        
        tree = ttk.Treeview(root, columns=MPanel.COLUMNS, displaycolumns=(MPanel.TITLE, MPanel.MDLVAL))
        tree.column(MPanel.MDLVAL)
        tree.column(MPanel.TITLE, width=100)
        tree.heading(MPanel.MDLVAL, text=MPanel.MDLVAL)
        tree.heading(MPanel.TITLE, text=MPanel.TITLE)
        tree.heading(MPanel.DESC, text=MPanel.DESC)

        tree.insert("" , 0, text="Line 1", values=("Some Value", "TgITLE", "fasdasdn sdf asdf \nasdf asd asd 1b", 3))

        id2 = tree.insert("", 1, "dir2", text="Dir 2")
        tree.insert(id2, "end", "dir 2", text="sub dir 2", values=("2A", "BAR", "Al ot \nof test\n f2B", 5))

        tree.insert("", 3, "dir3", text="Dir 3")
        tree.insert("dir3", 3, text=" sub dir 3", values=("3A", 'ttttt [rpm]', " 3B", 7))

        tree.bind('<<TreeviewSelect>>', self.do_node_selected)
        
        return tree

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

    def mainloop(self):
        self.master.mainloop()
        
if __name__ == '__main__':
    app = TkWltp()
    app.master.mainloop()
