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
    DEBUG = False
    WTF_CSRF_CHECK_DEFAULT = False
    SCHEDULA_CSRF_ENABLED = True
    SECURITY_ENABLED = os.environ.get(
        "SECURITY_ENABLED", 'true'
    ).lower() == 'true'
    ADMIN_ENABLED = os.environ.get(
        "ADMIN_ENABLED", SECURITY_ENABLED and 'true' or 'false'
    ).lower() == 'true'
    CONTACT_ENABLED = os.environ.get(
        "CONTACT_ENABLED", 'true'
    ).lower() == 'true'
    ITEMS_STORAGE_ENABLED = os.environ.get(
        "ITEMS_STORAGE_ENABLED", 'true'
    ).lower() == 'true'
    SCHEDULA_CREDITS_ENABLED = os.environ.get(
        "SCHEDULA_CREDITS_ENABLED", 'false'
    ).lower() == 'true'
    SCHEDULA_LOCALE_ENABLED = os.environ.get(
        "SCHEDULA_LOCALE_ENABLED", 'true'
    ).lower() == 'true'

    # reCAPTCHA configuration
    RECAPTCHA_PUBLIC_KEY = os.environ.get(
        'RECAPTCHA_PUBLIC_KEY', '6LcsgJglAAAAAMm7ilxkhBRevaCAuxlpefYZmxHU'
    )
    RECAPTCHA_PRIVATE_KEY = os.environ.get(
        'RECAPTCHA_PRIVATE_KEY', '6LcsgJglAAAAAAbR3aHm2qJS_c3XsGqmC9O816eH'
    )

    # Generate a nice key using secrets.token_urlsafe()
    SECRET_KEY = os.environ.get("SECRET_KEY", secrets.token_urlsafe())

    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')
    MAIL_SERVER = os.environ.get('MAIL_HOST')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 465))
    MAIL_USE_SSL = True
    MAIL_USERNAME = os.environ.get('MAIL_USER')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')

    # Use an in-memory db
    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    # As of Flask-SQLAlchemy 2.4.0 it is easy to pass in options directly to the
    # underlying engine. This option makes sure that DB connections from the
    # pool are still valid. Important for entire application since
    # many DBaaS options automatically close idle connections.
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    SQLALCHEMY_TRACK_MODIFICATIONS = False
