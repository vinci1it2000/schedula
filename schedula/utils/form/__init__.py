# coding=utf-8
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2022, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides functions to build a form flask app from a dispatcher.
"""
import json
import os.path as osp
from ..web import WebMap
from flask import render_template, Blueprint
from jinja2 import TemplateNotFound

__author__ = 'Vincenzo Arcidiacono <vinci1it2000@gmail.com>'

static_dir = osp.join(osp.dirname(__file__), 'static')

with open(osp.join(static_dir, 'asset-manifest.json')) as f:
    main_js = '/'.join(json.load(f)['files']['main.js'].split('/')[2:])


class FormMap(WebMap):
    _view = None

    def render_form(self, form='index'):
        template = f'schedula/{form}.html'
        try:
            return render_template(
                template, name=form, form_id=form, main_js=main_js
            )
        except TemplateNotFound:
            return render_template(
                'schedula/base.html', name=form, form_id=form, main_js=main_js
            )

    @staticmethod
    def send_static_file(filename):
        from flask import current_app, send_from_directory
        from werkzeug.exceptions import NotFound
        filename = osp.join('schedula', filename)
        try:
            return current_app.send_static_file(filename)
        except NotFound:
            return send_from_directory(static_dir, filename)

    def app(self, root_path=None, depth=1, mute=False, blueprint_name=None,
            **kwargs):
        app = super(FormMap, self).app(
            root_path=root_path, depth=depth, mute=mute,
            blueprint_name=blueprint_name, **kwargs
        )
        bp = Blueprint('schedula', __name__, template_folder='templates')
        bp.add_url_rule(
            '/', 'render-form', self.render_form, methods=['GET']
        )
        bp.add_url_rule(
            '/form/<form>', 'render-form', self.render_form, methods=['GET']
        )
        bp.add_url_rule(
            '/static/schedula/<path:filename>', 'static', self.send_static_file,
            methods=['GET']
        )
        app.register_blueprint(bp)
        return app
