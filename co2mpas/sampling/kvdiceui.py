#!/usr/bin/env python
#
# Copyright 2014-2015 European Commission (JRC);
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl
#
# if __name__ == "__main__" and __package__ is None:
#     __package__ = "co2mpas"  # @ReservedAssignment PEP366: fix relative imports

import os, os.path as osp, sys

from kivy.app import App
import string
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.treeview import TreeView, TreeViewLabel, TreeViewNode
from kivy.factory import Factory
from kivy.properties import ObjectProperty, StringProperty
from kivy.uix.popup import Popup
from kivy.storage import jsonstore
from co2mpas.sampling import dice


def store_get(section_key, dic_key, default=None):
    store = App.get_running_app().store
    value = None
    try:
        value = store.get(section_key)
        if dic_key is not None:
            value = value[dic_key]
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


class LoadDialog(FloatLayout):
    load = ObjectProperty(None)
    cancel = ObjectProperty(None)


class SaveDialog(FloatLayout):
    save = ObjectProperty(None)
    text_input = ObjectProperty(None)
    cancel = ObjectProperty(None)

class FolderView(TreeView):
    def __init__(self, **kwds):
        hide_root = kwds.pop('hide_root', True)
        super().__init__(hide_root=hide_root, **kwds)

        drives = ['%s:' % d for d in string.ascii_uppercase if os.path.exists('%s:' % d)]
        for d in drives:
            self.add_node(TreeViewLabel(text=d), self.root)


class Root(FloatLayout):
    loadfile = ObjectProperty(None)
    savefile = ObjectProperty(None)
    text_input = ObjectProperty(None)
    def dismiss_popup(self):
        self._popup.dismiss()

    def show_load(self):
        content = LoadDialog(load=self.load, cancel=self.dismiss_popup)
        start_path = store_get('filechooser', 'load_path', os.getcwd())
        content.ids['filechooser'].path = start_path
        self._popup = Popup(title="Load file", content=content,
                            size_hint=(0.9, 0.9))
        self._popup.open()

    def show_save(self):
        content = SaveDialog(save=self.save, cancel=self.dismiss_popup)
        start_path = store_get('filechooser', 'save_path', os.getcwd())
        content.ids['filechooser'].path = start_path
        self._popup = Popup(title="Save file", content=content,
                            size_hint=(0.9, 0.9))
        self._popup.open()

    def load(self, path, filename):
        with open(os.path.join(path, filename[0])) as stream:
            txt = stream.read()
        self.text_input.text = txt
        try:
            self.ids['rendered'].text = txt
        except Exception as ex:
            print(ex)
        if store_get('filechooser', 'load_path') != path:
            store_put('filechooser', 'load_path', path)
        self.dismiss_popup()

    def save(self, path, filename):
        with open(os.path.join(path, filename), 'w') as stream:
            stream.write(self.text_input.text)

        self.dismiss_popup()


class KvDiceUIApp(App):

    def build(self):
        self.store = jsonstore.JsonStore('hello.json')

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