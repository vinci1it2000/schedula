# coding=utf-8
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2024, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides functions to build the contact service.
"""
import os
import rst2txt
import logging
import datetime
import schedula as sh
from flask import render_template
from docutils.core import publish_string
from flask_security import current_user as cu
from flask_mail import Message, Mail as _Mail
from werkzeug.datastructures import MultiDict
from flask_wtf.recaptcha import RecaptchaField
from flask_babel import get_locale
from flask import flash, Blueprint, redirect, request, current_app as ca
from flask_security.utils import (
    base_render_json, suppress_form_csrf, get_post_action_redirect
)
from flask_security.forms import Required, StringField, Form, EmailField
from .locale import lazy_gettext

log = logging.getLogger(__name__)
bp = Blueprint('contact', __name__)


def prepare_message(boby, subject, recipients, reply_to=None, **kwargs):
    body = publish_string(boby, writer=rst2txt.Writer()).decode()
    html = publish_string(boby, writer_name='html').decode()
    return Message(
        body=body, html=html, subject=subject, recipients=recipients,
        reply_to=reply_to, **kwargs
    )


def _render_template(*paths, **data):
    from jinja2.exceptions import TemplateNotFound
    for path in paths:
        try:
            return render_template(path, **data)
        except TemplateNotFound:
            continue
    raise TemplateNotFound


class Mail(_Mail):
    def send_rst(
            self, to, data, rst=None, reply_to=None, body=None, subject=None,
            language=None, **kwargs):
        from tabulate import tabulate
        if language is None:
            locale = get_locale()
            language = f"{locale.language}_{locale.territory}"
        body = body or _render_template(
            f'schedula/email/{rst}/body/{language}.rst',
            f'schedula/email/{rst}/body.rst',
            tabulate=tabulate, **data
        )
        subject = subject or _render_template(
            f'schedula/email/{rst}/subject/{language}.rst',
            f'schedula/email/{rst}/subject.rst',
            tabulate=tabulate, **data
        )
        recipients = list(sh.stlp(os.environ.get('LOCAL', to)))
        message = prepare_message(
            body, subject, recipients, reply_to=reply_to, **kwargs
        )
        return self.send(message)


class ContactForm(Form):
    name = StringField('name', [Required()])
    email = EmailField('email', [Required()])
    subject = StringField('subject', [Required()])
    message = StringField('message', [Required()])
    recaptcha = RecaptchaField('g-recaptcha-response')


def get_post_contact_redirect():
    return get_post_action_redirect("SCHEDULA_POST_CONTACT_VIEW", request.form)


@bp.route('/contact', methods=['POST'])
def contact():
    data = MultiDict(
        request.get_json()
    ) if request.is_json else request.form
    if cu.is_authenticated:
        if 'email' not in data:
            data['email'] = cu.email
        if 'name' not in data:
            data['name'] = f'{cu.firstname} {cu.lastname}'
    form = ContactForm(data, meta=suppress_form_csrf())
    if form.validate_on_submit():
        try:
            ca.extensions['schedula_mail'].send_rst(
                to=[form.data['email'], ca.config.get('MAIL_DEFAULT_SENDER')],
                rst='contact', reply_to=form.data['email'], data={
                    'user': cu, 'data': data,
                    'created': datetime.datetime.now().strftime(
                        "%d/%m/%Y-%H:%M:%S")
                }
            )
            flash(str(lazy_gettext(
                'Your message has been successfully sent!',
                domain='contact'
            )), 'success')
        except Exception as ex:
            flash(str(lazy_gettext(
                "A system error has occurred. Please try again later. "
                "If the problem persists, contact technical support.",
                domain='contact'
            )), 'error')
            return redirect(request.referrer or '/')

    if ca.extensions["security"]._want_json(request):
        return base_render_json(form)
    return redirect(get_post_contact_redirect())


class Contact(Mail):
    def __init__(self, app):
        super().__init__(app)

    def init_app(self, app):
        super().init_app(app)
        app.config['SCHEDULA_POST_CONTACT_VIEW'] = app.config.get(
            'SCHEDULA_POST_CONTACT_VIEW', os.environ.get(
                'SCHEDULA_POST_CONTACT_VIEW', app.config.get(
                    "APPLICATION_ROOT", "/"
                )
            )
        )

        app.register_blueprint(bp, url_prefix='/mail')
        app.extensions['schedula_mail'] = self
