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

    admin
    contact
    credits
    csrf
    export
    extensions
    files
    gdpr
    items
    locale
    security
"""
import logging
import schedula as sh

log = logging.getLogger(__name__)


def default_get_form_context():
    from flask import current_app
    from flask_security import current_user as cu
    return {
        'reCAPTCHA': current_app.config.get('RECAPTCHA_PUBLIC_KEY'),
        'stripeKey': current_app.config.get('STRIPE_PUBLISHABLE_KEY'),
        'userInfo': sh.combine_dicts(*(
            getattr(cu, k, lambda: {})()
            for k in ("get_security_payload",)
        )),
    }


def basic_app(sitemap, app):
    from ..config import Config
    from .extensions import db
    app.config.from_object(Config())
    if getattr(sitemap, 'basic_app_config'):
        app.config.from_object(sitemap.basic_app_config)

    # Create database connection object
    db.init_app(app)

    if app.config['SCHEDULA_LOCALE_ENABLED']:
        from .locale import Locales
        Locales(app)

    if app.config['SCHEDULA_CSRF_ENABLED']:
        from .csrf import csrf
        csrf.init_app(app)

    if app.config['SECURITY_ENABLED']:
        from .security import Security
        Security(app)

    if app.config.get('ADMIN_ENABLED'):
        from .admin import Admin
        Admin(app)

    if app.config.get('SCHEDULA_CREDITS_ENABLED'):
        from .credits import Credits
        Credits(app, sitemap)

    if app.config.get('CONTACT_ENABLED'):
        from .contact import Contact
        Contact(app)

    if app.config.get('ITEMS_STORAGE_ENABLED'):
        from .items import Items
        Items(app, sitemap)

    if app.config.get('FILES_STORAGE_ENABLED'):
        from .files import Files
        Files(app, sitemap)

    if app.config['SCHEDULA_GDPR_ENABLED']:
        from .gdpr import GDPR
        GDPR(app, sitemap)

    if app.config['SCHEDULA_EXPORT_FORM_ENABLED']:
        from .export import ExportForm
        ExportForm(app, sitemap)

    @app.context_processor
    def inject_application_root():
        return dict(app_root=app.config.get('APPLICATION_ROOT', ''))

    return app
