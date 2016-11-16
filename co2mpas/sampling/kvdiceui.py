#!/usr/bin/env python
#
# Copyright 2014-2016 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
#
# if __name__ == "__main__" and __package__ is None:
#     __package__ = "co2mpas"  # @ReservedAssignment PEP366: fix relative imports

import os, os.path as osp, sys

from kivy.app import App
import string
from kivy import logger
from boltons.setutils import IndexedSet
from kivy.clock import wraps
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.stacklayout import StackLayout
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.listview import ListView
from kivy.factory import Factory
from kivy.properties import ObjectProperty, StringProperty, ListProperty
from kivy.uix.popup import Popup
from kivy.storage import jsonstore
from co2mpas.sampling import dice

mydir = osp.dirname(__file__)

def store_get(section_key, dic_key, default=None):
    store = App.get_running_app().store
    value = None
    try:
        dval = store.get(section_key)
        if dic_key is None:
            value = dval
        else:
            value = dval[dic_key]
    except:
        pass
    return value or default

def store_put(section_key, dic_key, value):
    """If dic_key is None, value must be a dict."""
    store = App.get_running_app().store
    if dic_key is None:
        sect_val = value
    else:
        sect_val = store_get(section_key, None, default={})
        sect_val[dic_key] = value
    value = store.put(section_key, **sect_val)


class FileDialog(FloatLayout):
    stkey_last_path = StringProperty('filechooser.last_path')
    stkey_paths_hist = StringProperty('filechooser.paths_history')
    path = StringProperty()
    onok = ObjectProperty(None)
    oncancel = ObjectProperty(None)

    def __init__(self, **kwds):
        super(FileDialog, self).__init__(**kwds)
        start_path = self.path
        if not start_path and self.stkey_last_path:
            sect, key = self.stkey_last_path.split('.')
            self.path = store_get(sect, key, os.getcwd())

    def store_selection(self):
        """Remember to call it on "ok", to persist history of selected paths."""
        print("Storing selection...")
        if self.stkey_last_path:
            sect, key = self.stkey_last_path.split('.')
            store_put(sect, key, self.path)
        if self.stkey_paths_hist:
            sect, key = self.stkey_paths_hist.split('.')
            try:
                paths_hist = IndexedSet(store_get(sect, key, []))
                paths_hist.add(self.path)
                paths_hist = list(reversed(paths_hist)) # earlier elements at list-head
            except:
                paths_hist = [self.path]
            store_put(sect, key, paths_hist)


class FileDialogShortcut(Button):
    pass

class FileBrowser(FileBrowser):
    #drives = ListProperty(baseclass='str')
    file_dialog = ObjectProperty()
    shortcut = StringProperty()

    def __init__(self, **kwds):
        drives = ['%s:\\' % d for d in string.ascii_uppercase if os.path.exists('%s:' % d)]
        drives = kwds.pop('drives', drives)
        #super(self, FileDialogBar).__init__(drives=drives, **kwds)
        super(FileDialogBar, self).__init__(**kwds)
        for d in drives:
            self._add_path_shortcut(d, font_size=14)

    def on_file_dialog(self, *args):
        stkey_paths_hist = self.file_dialog.stkey_paths_hist
        if stkey_paths_hist:
            try:
                sect, key = stkey_paths_hist.split('.')
                paths_hist = store_get(sect, key, [])
                for p in paths_hist:
                    self._add_path_shortcut(p)
            except:
                print("DDDDD")

    def _add_path_shortcut(self, path, can_delete=False, font_size=12):
        import math
        w = Label()
        w.halign
        nchars = 2 + 5 * math.exp(1/(10 * len(path)))
        btn = FileDialogShortcut(text=path, on_release=self._do_shortcut,
                                 size_hint=(None, None),
                                 #width='%dsp' % (font_size * nchars,
                                 width='12sp',
                                 height='40dsp',
                                 #font_size='%dsp' % font_size,
                                 #size_hint=(None, 0.1),
        )
        self.add_widget(btn)

    def _do_shortcut(self, btn):
        self.shortcut = btn.text

class LoadDialog(FileDialog):
    pass

class SaveDialog(FileDialog):
    text_input = ObjectProperty(None)


class Root(FloatLayout):

    def dismiss_popup(self):
        self._popup.dismiss()

    def show_load(self):
        content = LoadDialog(onok=self.do_load, oncancel=self.dismiss_popup,
                             stkey_last_path='filechooser.load_path')
        self._popup = Popup(title="Load file", content=content, size_hint=(0.9, 0.9))
        self._popup.open()

    def do_load(self, path, filename):
        print("Doing load...")
        with open(os.path.join(path, filename[0])) as stream:
            txt = stream.read()
        self.text_input.text = txt
        try:
            self.ids['rendered'].text = txt
        except Exception as ex:
            print(ex)
        self.dismiss_popup()

    def show_save(self):
        content = SaveDialog(onok=self.do_save, oncancel=self.dismiss_popup)
        start_path = store_get('filechooser', 'save_path', os.getcwd())
        content.ids['filechooser'].path = start_path
        self._popup = Popup(title="Save file", content=content, size_hint=(0.9, 0.9))
        self._popup.open()

    def do_save(self, path, filename):
        with open(os.path.join(path, filename), 'w') as stream:
            stream.write(self.text_input.text)

        self.dismiss_popup()


class KvDiceUIApp(App):

    def build(self):
        self.store = jsonstore.JsonStore(osp.join(mydir, 'hello.json'))

    def build_config(self, config):
        config.setdefaults('filechooser', {
            'load': None,
            'save': None,
        })
Factory.register('Root', cls=Root)
Factory.register('LoadDialog', cls=LoadDialog)
Factory.register('SaveDialog', cls=SaveDialog)


if __name__ == '__main__':
    KvDiceUIApp().run()