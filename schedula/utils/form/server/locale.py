# coding=utf-8
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2024, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides functions to build the language service.
"""
import os.path as osp
from flask_babel import Babel
from werkzeug.exceptions import NotFound
from flask import (
    jsonify, current_app, request, session, Blueprint, send_from_directory
)

bp = Blueprint('locales', __name__)


@bp.route('/<language>/<namespace>', methods=['GET'])
def locales(language, namespace):
    for d in current_app.config['SCHEDULA_I18N_DIRNAME']:
        try:
            return send_from_directory(
                d, f'{osp.join(language, "LC_MESSAGES", namespace)}.po',
                as_attachment=True
            )
        except NotFound:
            pass
    raise NotFound()


@bp.route('/', methods=['GET'])
def get_locales():
    return jsonify(current_app.config.get('BABEL_LANGUAGES'))


def get_locale():
    locale = session.get('locale')
    if not locale:
        session['locale'] = locale = request.accept_languages.best_match(
            current_app.config.get('BABEL_LANGUAGES')
        )
    return locale


class Locales:
    def __init__(self, app, *args, **kwargs):
        if app is not None:
            self.init_app(app, *args, **kwargs)

    def init_app(self, app, *args, locale_selector=get_locale, **kwargs):
        app.extensions = getattr(app, 'extensions', {})
        Babel(app, *args, locale_selector=locale_selector, **kwargs)
        app.register_blueprint(bp, url_prefix='/locales')
        app.extensions['locates'] = self
