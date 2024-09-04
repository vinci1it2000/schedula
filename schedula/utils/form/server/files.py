# coding=utf-8
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2024, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides functions to build the item storage service.
"""
import hashlib
import datetime
import schedula as sh
from .extensions import db
from .security import is_admin
from flask import (
    after_this_request, request, jsonify, Blueprint, url_for, current_app as ca,
    send_file, abort
)
from sqlalchemy import (
    Column, String, Integer, DateTime, ForeignKey, JSON, and_
)
from flask_security.utils import view_commit
from flask_security import current_user as cu, auth_required
from sqlalchemy.orm import validates
from sqlalchemy_file import File as SQLFile, FileField
from sqlalchemy_file.storage import StorageManager
from libcloud.storage.drivers.local import LocalStorageDriver
from libcloud.storage.types import ObjectDoesNotExistError
from urllib.parse import urlparse, parse_qs
from itsdangerous import URLSafeTimedSerializer

bp = Blueprint('files', __name__)


def serve_file(path, filename):
    try:
        file = StorageManager.get_file(path)
        if isinstance(file.object.driver, LocalStorageDriver):
            """If file is stored in local storage, just return a
            FileResponse with the fill full path."""
            return send_file(
                file.get_cdn_url(),
                mimetype=file.content_type,
                download_name=filename,
            )
        elif file.get_cdn_url() is not None:
            """If file has public url, redirect to this url"""
            return ca.redirect(file.get_cdn_url())
        else:
            """Otherwise, return a streaming response"""
            return ca.response_class(
                file.object.as_stream(),
                mimetype=file.content_type,
                headers={
                    "Content-Disposition": f"attachment;filename={filename}"
                },
            )
    except ObjectDoesNotExistError:
        abort(404)


def calculate_meta(ctx):
    return ca.file_meta_handler(ctx)


def calculate_default_hash(ctx):
    params = ctx if isinstance(ctx, dict) else ctx.get_current_parameters()
    if not params.get('hash'):
        return calculate_hash(ctx)
    return params['hash']


def calculate_hash(ctx):
    params = ctx if isinstance(ctx, dict) else ctx.get_current_parameters()
    import base64
    file = params['data']
    b64 = base64.b64encode(StorageManager.get_file(file.path).read())
    return hashlib.sha512(
        f'data:{file.content_type};{b64}'.encode('utf-8')
    ).hexdigest()


class File(db.Model):
    __tablename__ = 'file'

    id = Column(Integer, primary_key=True)
    hash = Column(
        String(128), unique=True, nullable=False, onupdate=calculate_hash,
        default=calculate_default_hash
    )
    data = Column(FileField(upload_storage='files'))
    created_at = Column(DateTime(), default=datetime.datetime.utcnow)
    updated_at = Column(DateTime(), onupdate=datetime.datetime.utcnow)

    def payload(self, data=False):
        res = {
            'id': self.id,
            'hash': self.hash,
            'meta': self.meta,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
        for k in ('created_at', 'updated_at'):
            if res[k]:
                res[k] = res[k].isoformat()

        if data:
            res['data'] = self.data
        return res

    def __repr__(self):
        return f'File({self.id}) {self.hash}'


class AskFile(Exception):
    pass


def get_file(url, session=db.session, secret_key=None):
    if secret_key is None:
        secret_key = ca.secret_key
    serializer = URLSafeTimedSerializer(secret_key, salt='file-token')
    item = session.get(FileName, serializer.loads(
        parse_qs(urlparse(url).query)['file_token'][0]
    ))
    file = StorageManager.get_file(item.file.data.path)
    file.filename = item.name
    return file


class FileName(db.Model):
    __tablename__ = 'file_name'
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    category = Column(String(255))
    file_id = Column(Integer, ForeignKey('file.id'))
    file = db.relationship('File', foreign_keys=[file_id])
    meta = Column(
        'meta', JSON, default=calculate_meta, onupdate=calculate_meta
    )
    user_id = Column(Integer, ForeignKey('user.id'))
    user = db.relationship('User', foreign_keys=[user_id])
    created_at = Column(DateTime(), default=datetime.datetime.utcnow)
    updated_at = Column(DateTime(), onupdate=datetime.datetime.utcnow)

    @validates("file", include_backrefs=False)
    def validate_file(self, key, file):
        if isinstance(file, File):
            return file
        hash = None
        content_type = None
        if 'file' in file:
            kw = {}
            for v in file['file'].split(';'):
                if v.startswith('data:'):
                    kw['data'] = v
                    content_type = v[5:]
                elif v.startswith('base64,'):
                    kw['base64'] = v
                if len(kw) == 2:
                    break
            file['file'] = '{data};{base64}'.format(**kw)
            hash = hashlib.sha512(file['file'].encode('utf-8')).hexdigest()
        elif 'hash' in file:
            hash = file['hash']

        if hash:
            file_ = File.query.filter(File.hash == hash).one_or_none()
            if file_:
                return file_
            elif 'file' in file:
                from urllib.request import urlopen
                with urlopen(file['file'], 'rb') as f:
                    file_ = File(hash=hash, data=SQLFile(
                        content=f, content_type=content_type
                    ))
                    db.session.add(file_)
                    db.session.commit()
                return file_
            else:
                raise AskFile()
        raise ValueError("Invalid file type")

    def payload(self, data=False):
        serializer = URLSafeTimedSerializer(ca.secret_key, salt='file-token')
        res = {
            'id': self.id,
            'name': self.name,
            'url': url_for(
                '.file', category=self.category, id_item=self.id,
                name=self.name, file_token=serializer.dumps(self.id)
            ),
            'meta': self.meta,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
        for k in ('created_at', 'updated_at'):
            if res[k]:
                res[k] = res[k].isoformat()

        if data:
            res['file'] = self.file.data
        return res

    def __repr__(self):
        return f'File({self.id}) {self.category} - {self.name}'


@bp.route('/<category>', methods=['GET', 'POST'])
@bp.route('/<category>/<int:id_item>', methods=[
    'GET', 'PUT', 'PATCH', 'DELETE'
])
@auth_required()
def file(category, id_item=None):
    args = request.args
    method = request.method
    is_get = method == 'GET'

    kw = {'category': category, 'user_id': cu.id}
    if not is_get:
        kw['file'] = request.get_json()
        kw['name'] = kw['file']['filename']
    elif id_item is None and 'id_item' in args:
        id_item = args.get("id_item", type=str)
    if 'name' in args:
        kw['name'] = args.get("name", type=str)

    by = {'category': category, 'user_id': cu.id}
    if id_item is not None:
        by['id'] = kw['id'] = id_item
    if is_admin():
        by.pop('user_id')
    if method == 'POST':  # Create.
        try:
            item = FileName(**kw)
        except AskFile:
            return jsonify({'sendfile': True})
        item = FileName.query.filter(and_(
            FileName.name == item.name,
            FileName.category == item.category,
            FileName.file_id == item.file.id,
            FileName.user_id == item.user_id,
        )).one_or_none() or item
        db.session.add(item)
        db.session.flush()
        payload = item.payload()
    else:  # Read, Delete, Update/Modify, Update/Replace.
        query = FileName.query.filter_by(**by)
        if id_item is None:  # GET
            query = query.order_by(FileName.id)
            if 'page' in args and 'per_page' in args:
                pag = db.paginate(
                    query,
                    page=args.get("page", type=int),
                    max_per_page=args.get("per_page", type=int),
                    count=True, error_out=False
                )
                items = [item.payload() for item in pag.items]
                payload = {'page': pag.page, 'items': items,
                           'total': pag.total}
            else:
                items = [item.payload() for item in query.all()]
                payload = {'items': items, 'total': len(items)}
        else:
            item = query.first()
            if method == 'DELETE':
                db.session.delete(item)
            elif method in ('PATCH', 'PUT'):
                if method == 'PATCH':
                    kw['data'] = sh.combine_nested_dicts(
                        item.data, kw['data']
                    )
                for k, v in kw.items():
                    setattr(item, k, v)
                db.session.add(item)
                db.session.flush()
            if is_get:
                return serve_file(item.file.data.path, item.name)
            payload = item.payload()
    is_get or after_this_request(view_commit)
    return jsonify(payload)


class Files:
    def __init__(self, app, *args, **kwargs):
        if app is not None:
            self.init_app(app, *args, **kwargs)

    def init_app(self, app, sitemap, *args, **kwargs):
        app.file_meta_handler = sitemap.file_meta_handler or (lambda ctx: None)

        if 'files' not in StorageManager._storages:
            import os
            import os.path as osp
            upload_dir = osp.abspath(osp.join('.', "upload_dir"))
            os.makedirs(
                osp.join(upload_dir, 'files'), 0o777, exist_ok=True
            )
            container = LocalStorageDriver(upload_dir).get_container(
                "files"
            )
            StorageManager.add_storage("files", container)
        app.extensions = getattr(app, 'extensions', {})
        app.register_blueprint(bp, url_prefix='/file')
        app.extensions['file_storage'] = self
        if 'schedula_admin' in app.extensions:
            admin = app.extensions['schedula_admin']
            for v in (FileName, File):
                admin.add_model(v, category="Files")
