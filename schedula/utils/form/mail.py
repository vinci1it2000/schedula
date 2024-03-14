# coding=utf-8
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2024, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides functions to send mails with Flask.
"""
import os
import rst2txt
import schedula as sh
from flask import render_template
from flask_mail import Message, Mail as _Mail
from docutils.core import publish_string
from flask_babel import get_locale


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
            return render_template(
                path, **data
            )
        except TemplateNotFound:
            continue
    raise TemplateNotFound


class Mail(_Mail):
    def send_rst(self, to, rst=None, reply_to=None, body=None, subject=None,
                 **data):
        from tabulate import tabulate
        language = get_locale().language
        body = body or _render_template(
            f'schedula/email/{rst}-body-{language}.rst',
            f'schedula/email/{rst}-body.rst',
            tabulate=tabulate, **data
        )
        subject = subject or _render_template(
            f'schedula/email/{rst}-subject-{language}.rst',
            f'schedula/email/{rst}-subject.rst',
            tabulate=tabulate, **data
        )
        recipients = list(sh.stlp(os.environ.get('LOCAL', to)))
        message = prepare_message(body, subject, recipients, reply_to=reply_to)
        return self.send(message)
