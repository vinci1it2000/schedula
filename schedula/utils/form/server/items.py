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
import datetime
import schedula as sh
from .extensions import db
from .security import is_admin
from flask import after_this_request, request, jsonify, Blueprint
from sqlalchemy import (
    Column, String, Integer, DateTime, ForeignKey, JSON
)
from flask_security.utils import view_commit
from flask_security import current_user as cu, auth_required

bp = Blueprint('items', __name__)


def default_name(context):
    return f'Item {context.get_current_parameters()["id"]}'



class Item(db.Model):
    __tablename__ = 'item'
    id = Column(Integer, primary_key=True)
    name = Column(String(255), default=default_name)
    category = Column(String(255))
    data = Column('data', JSON)
    user_id = Column(Integer, ForeignKey('user.id'))
    user = db.relationship('User', foreign_keys=[user_id])
    created_at = Column(DateTime(), default=datetime.datetime.utcnow)
    updated_at = Column(DateTime(), onupdate=datetime.datetime.utcnow)

    def payload(self, data=False):
        res = {
            'id': self.id,
            'name': self.name,
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
        return f'Item({self.id}) {self.category} - {self.user.name}'


@bp.route('/<category>', methods=['GET', 'POST'])
@bp.route('/<category>/<int:id_item>', methods=[
    'GET', 'PUT', 'PATCH', 'DELETE'
])
@auth_required()
def item(category, id_item=None):
    args = request.args
    method = request.method
    is_get = method == 'GET'
    kw = {'category': category, 'user_id': cu.id}
    if not is_get:
        kw['data'] = request.get_json()
    if 'name' in args:
        kw['name'] = args.get("name", type=str)

    by = {'category': category, 'user_id': cu.id}
    if id_item is not None:
        by['id'] = kw['id'] = id_item
    if is_admin():
        by.pop('user_id')
    if method == 'POST':  # Create.
        item = Item(**kw)
        db.session.add(item)
        db.session.flush()
        payload = item.payload()
    else:  # Read, Delete, Update/Modify, Update/Replace.
        query = Item.query.filter_by(**by)
        if id_item is None:  # GET
            query = query.order_by(Item.id)
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
            payload = item.payload(data=is_get)
    is_get or after_this_request(view_commit)
    return jsonify(payload)


class Items:
    def __init__(self, app, *args, **kwargs):
        if app is not None:
            self.init_app(app, *args, **kwargs)

    def init_app(self, app, *args, **kwargs):
        app.extensions = getattr(app, 'extensions', {})
        app.register_blueprint(bp, url_prefix='/item')
        app.extensions['item_storage'] = self
        if 'schedula_admin' in app.extensions:
            admin = app.extensions['schedula_admin']
            for v in (Item,):
                admin.add_model(v, category="Items")
