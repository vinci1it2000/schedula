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
import os
import functools
import os.path as osp
from flask_babel import Babel, Domain
from werkzeug.exceptions import NotFound
from werkzeug.datastructures.accept import LanguageAccept
from flask import (
    jsonify, current_app, request, session, Blueprint, send_from_directory
)

bp = Blueprint('locales', __name__)


@functools.lru_cache()
def get_domain(domain):
    return Domain(domain=domain)


def lazy_gettext(*args, domain=None, **kwargs):
    return get_domain(domain).lazy_gettext(*args, **kwargs)


@bp.route('/<language>/<namespace>', methods=['GET'])
def locales(language, namespace):
    for d in current_app.extensions['babel'].translation_directories:
        try:
            return send_from_directory(
                d, f'{osp.join(language, "LC_MESSAGES", namespace)}.po',
                as_attachment=True
            )
        except NotFound:
            pass
    raise NotFound()


@bp.route('', methods=['GET'])
@bp.route('/', methods=['GET'])
def get_locales():
    return jsonify(current_app.config.get('BABEL_LANGUAGES'))


@bp.route('/<lang>', methods=['POST'])
def set_locale(lang):
    languages = LanguageAccept([(lang, 2)] + request.accept_languages)
    session['locale'] = locale = languages.best_match(
        current_app.config.get('BABEL_LANGUAGES')
    )
    return jsonify({"language": locale})


@bp.route('/<lang>', methods=['GET'])
def get_locale(lang):
    locale = session.get('locale')
    if not locale:
        return set_locale(lang)
    return jsonify({"language": locale})


def _get_locale():
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

    def init_app(self, app, *args, locale_selector=_get_locale, **kwargs):
        app.extensions = getattr(app, 'extensions', {})
        app.config['BABEL_DEFAULT_LOCALE'] = app.config.get(
            'BABEL_DEFAULT_LOCALE', os.environ.get(
                'BABEL_DEFAULT_LOCALE', 'en_US'
            )
        )
        app.config['BABEL_LANGUAGES'] = app.config.get(
            'BABEL_LANGUAGES', {
                'af_ZA': {"icon": "🇿🇦", "label": "Afrikaans"},
                'ca_ES': {"icon": "🇪🇸", "label": "Català"},
                'da_DK': {"icon": "🇩🇰", "label": "Dansk"},
                'de_DE': {"icon": "🇩🇪", "label": "Deutsch"},
                'en_US': {"icon": "🇺🇸", "label": "English"},
                'es_ES': {"icon": "🇪🇸", "label": "Español"},
                'eu_ES': {"icon": "🇪🇸", "label": "Euskara"},
                'fr_FR': {"icon": "🇫🇷", "label": "Français"},
                'hu_HU': {"icon": "🇭🇺", "label": "Magyar"},
                'hy_AM': {"icon": "🇦🇲", "label": "Հայերեն"},
                'is_IS': {"icon": "🇮🇸", "label": "Íslenska"},
                'it_IT': {"icon": "🇮🇹", "label": "Italiano"},
                'ja_JP': {"icon": "🇯🇵", "label": "日本語"},
                'nl_NL': {"icon": "🇳🇱", "label": "Nederlands"},
                'pl_PL': {"icon": "🇵🇱", "label": "Polski"},
                'pt_BR': {"icon": "🇧🇷", "label": "Português (Brasil)"},
                'pt_PT': {"icon": "🇵🇹", "label": "Português (Portugal)"},
                'ru_RU': {"icon": "🇷🇺", "label": "Русский"},
                'tr_TR': {"icon": "🇹🇷", "label": "Türkçe"},
                'zh_Hans_CN': {"icon": "🇨🇳", "label": "中文（简体）"}
            }
        )
        directories = []
        it = app.config.get(
            'BABEL_TRANSLATION_DIRECTORIES',
            os.environ.get('BABEL_TRANSLATION_DIRECTORIES', 'translations')
        )
        if isinstance(it, str):
            it = [it]
        for k in it:
            directories.extend(k.split(';'))
        if not directories:
            directories.append('translations')
        tdir = osp.join(osp.dirname(__file__), 'translations')
        if tdir not in directories:
            directories.append(tdir)
        app.config['BABEL_TRANSLATION_DIRECTORIES'] = ';'.join(directories)
        Babel(app, *args, locale_selector=locale_selector, **kwargs)
        app.register_blueprint(bp, url_prefix='/locales')
        app.extensions['locates'] = self
