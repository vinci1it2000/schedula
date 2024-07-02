# coding=utf-8
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2024, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides functions to build the credit application services.
"""
import uuid
import datetime
from .extensions import db
from flask_security.utils import view_commit
from flask_security import current_user as cu
from sqlalchemy import Column, String, DateTime, JSON
from flask import request, jsonify, Blueprint, after_this_request, current_app

bp = Blueprint('schedula_gdpr', __name__)


class Consent(db.Model):
    __tablename__ = 'consents'
    id = Column(String(36), default=lambda: str(uuid.uuid4()), primary_key=True)
    consents = Column(JSON(), nullable=False)
    created_at = Column(
        DateTime(), nullable=False, default=datetime.datetime.utcnow
    )
    updated_at = Column(
        DateTime(), nullable=True, onupdate=datetime.datetime.utcnow
    )
    created_by = db.Column(
        db.Integer, db.ForeignKey('user.id'), nullable=True,
        default=lambda: getattr(cu, 'id', None)
    )
    updated_by = db.Column(
        db.Integer, db.ForeignKey('user.id'), nullable=True,
        onupdate=lambda: getattr(cu, 'id', None)
    )

    def payload(self):
        return {
            'id': self.id,
            'consents': self.consents
        }

    def __repr__(self):
        return f'Consent - {self.id}'


@bp.route('/consent', methods=['POST'])
def consent():
    data = request.json
    consent_id = data.get('id')
    consents = data.get('consents')

    record = consent_id and Consent.query.get(consent_id)
    if record:
        record.consents = consents
    else:
        record = Consent(id=consent_id or None, consents=consents)
    db.session.add(record)
    db.session.flush()
    after_this_request(view_commit)
    return jsonify(record.payload())


@bp.route('/consent/<consent_id>', methods=['GET'])
def check_consent(consent_id):
    consent = Consent.query.get(consent_id)
    return jsonify(consent and consent.payload())


@bp.route('/files/terms-conditions', methods=['GET'])
@bp.route('/files/cookies-policy', methods=['GET'])
def gdpr_files():
    path = request.path.split('/')[-1]
    return current_app.send_static_file(f'gdpr/{path}.pdf')


class GDPR:
    def __init__(self, app, sitemap, *args, **kwargs):
        if app is not None:
            self.init_app(app, sitemap, *args, **kwargs)

    def init_app(self, app, sitemap, *args, **kwargs):
        app.extensions = getattr(app, 'extensions', {})
        app.register_blueprint(bp, url_prefix='/gdpr')
        app.extensions['schedula_gdpr'] = self
        if 'schedula_admin' in app.extensions:
            admin = app.extensions['schedula_admin']
            for v in (Consent,):
                admin.add_model(v, category="GDPR")
