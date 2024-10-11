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

try:
    import flask_security
except ImportError:
    flask_security = None


class Config:
    def __init__(self):
        self.DEBUG = False
        self.WTF_CSRF_CHECK_DEFAULT = os.environ.get(
            "WTF_CSRF_CHECK_DEFAULT", 'false'
        ).lower() == 'true'
        self.SCHEDULA_CSRF_ENABLED = os.environ.get(
            "SCHEDULA_CSRF_ENABLED", 'true'
        ).lower() == 'true'
        self.SCHEDULA_GDPR_ENABLED = os.environ.get(
            "SCHEDULA_GDPR_ENABLED", 'true'
        ).lower() == 'true'
        self.SECURITY_ENABLED = os.environ.get(
            "SECURITY_ENABLED", 'true'
        ).lower() == 'true'
        self.ADMIN_ENABLED = os.environ.get(
            "ADMIN_ENABLED", self.SECURITY_ENABLED and 'true' or 'false'
        ).lower() == 'true'
        self.CONTACT_ENABLED = os.environ.get(
            "CONTACT_ENABLED", 'true'
        ).lower() == 'true'
        self.ITEMS_STORAGE_ENABLED = os.environ.get(
            "ITEMS_STORAGE_ENABLED", 'true'
        ).lower() == 'true'
        self.FILES_STORAGE_ENABLED = os.environ.get(
            "FILES_STORAGE_ENABLED", 'true'
        ).lower() == 'true'
        self.SCHEDULA_CREDITS_ENABLED = os.environ.get(
            "SCHEDULA_CREDITS_ENABLED", 'false'
        ).lower() == 'true'
        self.SCHEDULA_LOCALE_ENABLED = os.environ.get(
            "SCHEDULA_LOCALE_ENABLED", 'true'
        ).lower() == 'true'
        self.SCHEDULA_EXPORT_FORM_ENABLED = os.environ.get(
            "SCHEDULA_EXPORT_FORM_ENABLED", 'false'
        ).lower() == 'true'

        # reCAPTCHA configuration
        self.RECAPTCHA_PUBLIC_KEY = os.environ.get(
            'RECAPTCHA_PUBLIC_KEY', '6LcsgJglAAAAAMm7ilxkhBRevaCAuxlpefYZmxHU'
        )
        self.RECAPTCHA_PRIVATE_KEY = os.environ.get(
            'RECAPTCHA_PRIVATE_KEY', '6LcsgJglAAAAAAbR3aHm2qJS_c3XsGqmC9O816eH'
        )

        # Generate a nice key using secrets.token_urlsafe()
        self.SECRET_KEY = os.environ.get("SECRET_KEY", secrets.token_urlsafe())

        self.MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')
        self.MAIL_SERVER = os.environ.get('MAIL_HOST')
        self.MAIL_PORT = int(os.environ.get('MAIL_PORT', 465))
        self.MAIL_USE_SSL = os.environ.get(
            'MAIL_USE_SSL', 'true'
        ).lower() == 'true'
        self.MAIL_USERNAME = os.environ.get('MAIL_USER')
        self.MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
        self.DB_DIALECT = os.environ.get('DB_DIALECT', 'sqlite')
        self.DB_USER = os.environ.get('DB_USER', '')
        self.DB_PASSWORD = os.environ.get('DB_PASSWORD', '')
        self.DB_HOST = os.environ.get('DB_HOST', '')
        self.DB_PORT = os.environ.get('DB_PORT', '')
        self.DB_DATABASE = os.environ.get('DB_DATABASE', 'database.db')
        self.DB_SERVER = (
                self.DB_USER and f'{self.DB_USER}:{self.DB_PASSWORD}@' or ''
        )
        self.DB_SERVER += (
                self.DB_HOST and f'{self.DB_HOST}:{self.DB_PORT}' or ''
        )
        self.SQLALCHEMY_DATABASE_URI = os.environ.get(
            'SQLALCHEMY_DATABASE_URI',
            f'{self.DB_DIALECT}://{self.DB_SERVER}/{self.DB_DATABASE}'
        )
        # As of Flask-SQLAlchemy 2.4.0 it is easy to pass in options directly to the
        # underlying engine. This option makes sure that DB connections from the
        # pool are still valid. Important for entire application since
        # many DBaaS options automatically close idle connections.
        self.SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
        self.SQLALCHEMY_TRACK_MODIFICATIONS = os.environ.get(
            'SQLALCHEMY_TRACK_MODIFICATIONS', 'false'
        ).lower() == 'true'
