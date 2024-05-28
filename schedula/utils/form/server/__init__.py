# coding=utf-8
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2024, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides functions to build the base form flask app.

Sub-Modules:

.. currentmodule:: schedula.utils.form.server

.. autosummary::
    :nosignatures:
    :toctree: form/

    contact
    credits
    extensions
    items
    locale
    security
"""
import logging
from .extensions import db
from ..config import Config
from flask import current_app
from flask_security import current_user as cu

log = logging.getLogger(__name__)


def default_get_form_context():
    return {
        'userInfo': getattr(cu, "get_security_payload", lambda: {})(),
        'reCAPTCHA': current_app.config.get('RECAPTCHA_PUBLIC_KEY'),
        'stripeKey': current_app.config.get('STRIPE_PUBLISHABLE_KEY')
    }


def basic_app(sitemap, app):
    app.config.from_object(Config)
    if getattr(sitemap, 'basic_app_config'):
        app.config.from_object(sitemap.basic_app_config)

    # Create database connection object
    db.init_app(app)

    if app.config['SCHEDULA_I18N_DIRNAME']:
        from .locale import Locales
        Locales(app)

    if app.config['SECURITY_ENABLED']:
        from .security import Security
        Security(app, sitemap)

    if app.config.get('STRIPE_SECRET_KEY'):
        from .credits import Credits
        Credits(app, sitemap)

    if app.config.get('CONTACT_ENABLED'):
        from .contact import Contact
        Contact(app, sitemap)

    if app.config.get('ITEMS_STORAGE_ENABLED'):
        from .items import Items
        Items(app, sitemap)

    return app
