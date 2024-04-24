# coding=utf-8
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2024, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides the default Flask App config file.
"""
import os
import secrets
import inspect
import os.path as osp

try:
    import flask_security
except ImportError:
    flask_security = None


class Config:
    DEBUG = True
    WTF_CSRF_CHECK_DEFAULT = False

    # reCAPTCHA configuration
    RECAPTCHA_PUBLIC_KEY = os.environ.get(
        'RECAPTCHA_PUBLIC_KEY', '6LcsgJglAAAAAMm7ilxkhBRevaCAuxlpefYZmxHU'
    )
    RECAPTCHA_PRIVATE_KEY = os.environ.get(
        'RECAPTCHA_PRIVATE_KEY', '6LcsgJglAAAAAAbR3aHm2qJS_c3XsGqmC9O816eH'
    )

    # Generate a nice key using secrets.token_urlsafe()
    SECRET_KEY = os.environ.get("SECRET_KEY", secrets.token_urlsafe())
    # Bcrypt is set as default SECURITY_PASSWORD_HASH, which requires a salt
    # Generate a good salt using: secrets.SystemRandom().getrandbits(128)
    SECURITY_PASSWORD_SALT = os.environ.get(
        "SECURITY_PASSWORD_SALT", f'{secrets.SystemRandom().getrandbits(128)}'
    )
    SECURITY_BLUEPRINT_NAME = os.environ.get(
        "SECURITY_BLUEPRINT_NAME", 'security'
    )
    SECURITY_URL_PREFIX = os.environ.get("SECURITY_URL_PREFIX", '/user')
    SECURITY_CONFIRMABLE = os.environ.get(
        "SECURITY_CONFIRMABLE", 'true'
    ).lower() == 'true'
    SECURITY_AUTO_LOGIN_AFTER_CONFIRM = os.environ.get(
        "SECURITY_AUTO_LOGIN_AFTER_CONFIRM", 'false'
    ).lower() == 'true'
    SECURITY_POST_CONFIRM_VIEW = os.environ.get(
        "SECURITY_POST_CONFIRM_VIEW", '/#login'
    )
    SECURITY_CONFIRM_ERROR_VIEW = os.environ.get(
        "SECURITY_CONFIRM_ERROR_VIEW", '/#login'
    )
    SECURITY_REGISTERABLE = os.environ.get(
        "SECURITY_REGISTERABLE", 'true'
    ).lower() == 'true'
    SECURITY_SEND_REGISTER_EMAIL = os.environ.get(
        "SECURITY_SEND_REGISTER_EMAIL", 'true'
    ).lower() == 'true'
    SECURITY_RECOVERABLE = os.environ.get(
        "SECURITY_RECOVERABLE", 'true'
    ).lower() == 'true'
    SECURITY_RESET_VIEW = os.environ.get("SECURITY_RESET_VIEW", '/#reset')
    SECURITY_RESET_ERROR_VIEW = os.environ.get(
        "SECURITY_RESET_ERROR_VIEW", '/#login'
    )
    SECURITY_REDIRECT_BEHAVIOR = os.environ.get(
        "SECURITY_REDIRECT_BEHAVIOR", 'spa'
    )

    SECURITY_TRACKABLE = os.environ.get(
        "SECURITY_TRACKABLE", 'true'
    ).lower() == 'true'

    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')
    MAIL_SERVER = os.environ.get('MAIL_HOST')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 465))
    MAIL_USE_SSL = True
    MAIL_USERNAME = os.environ.get('MAIL_USER')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')

    SECURITY_I18N_DIRNAME = [
        "translations",
        os.environ.get('SECURITY_I18N_DIRNAME', 'translations'),
        osp.join(osp.dirname(osp.dirname(__file__)), 'translations')
    ]
    if flask_security is not None:
        SECURITY_I18N_DIRNAME.append(osp.join(
            osp.dirname(inspect.getfile(flask_security)), 'translations'
        ))

    SCHEDULA_I18N_DIRNAME = [
        "translations",
        os.environ.get('SCHEDULA_I18N_DIRNAME', 'translations'),
        osp.join(osp.dirname(__file__), 'translations'),
    ]

    BABEL_DEFAULT_LOCALE = 'en_US'
    BABEL_LANGUAGES = {
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

    # have session and remember cookie be samesite (flask/flask_login)
    REMEMBER_COOKIE_SAMESITE = "strict"
    SESSION_COOKIE_SAMESITE = "strict"

    # Use an in-memory db
    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    # As of Flask-SQLAlchemy 2.4.0 it is easy to pass in options directly to the
    # underlying engine. This option makes sure that DB connections from the
    # pool are still valid. Important for entire application since
    # many DBaaS options automatically close idle connections.
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY")
    STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY")
    STRIPE_WEBHOOK_SECRET_KEY = os.environ.get("STRIPE_WEBHOOK_SECRET_KEY")
