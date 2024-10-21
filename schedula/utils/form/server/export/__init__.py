# coding=utf-8
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2024, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');
# You may not use this work except in compliance with the Licence.
# You may obtain a copy of the Licence at: http://ec.europa.eu/idabc/eupl

"""
It provides functions to build the export page services.
"""
import io
import glob
import gzip
import json
import zipfile
import os.path as osp
from flask import request, send_file, Blueprint, current_app as ca, url_for

bp = Blueprint('schedula_export', __name__)


def custom_url_for(endpoint, **values):
    """Prepend the configured public path for static files."""
    url = url_for(endpoint, **values)
    if url.startswith('/'):
        url = url[1:]
    return url


@bp.route('/<path:form>', methods=['GET', 'POST'])
def export(form):
    data = request.json
    from ... import static_dir
    files = {}
    for folder in (static_dir, ca.static_folder):
        for fp in glob.glob(osp.join(folder, '**', '*'), recursive=True):
            if osp.isdir(fp) or fp.endswith('.map'):
                continue
            arcname = osp.relpath(fp, folder).replace("\\", "/")
            if arcname.startswith('schedula/forms') and not arcname.startswith(
                    f'schedula/forms/{form}-'
            ):
                continue
            files[f'/static/{arcname}'] = fp
    if 'babel' in ca.extensions:
        for folder in ca.extensions['babel'].translation_directories[::-1]:
            for fp in glob.glob(osp.join(folder, '*', "LC_MESSAGES", '*.po')):
                arcname = fp.replace("\\", "/")[:-3].split('/')
                files[f'/locales/{arcname[-3]}/{arcname[-1]}'] = fp

    output_zip = io.BytesIO()
    with zipfile.ZipFile(output_zip, 'w') as zipf:
        zipf.writestr(f'index.html', ca.render_form(form, ctx={
            'url_for': custom_url_for,
            'is_static': 'true'
        }))
        for arcname, fp in files.items():
            if fp.endswith('.gz'):
                with gzip.GzipFile(fp) as gz_file:
                    zipf.writestr(arcname[:-3], gz_file.read())
            else:
                zipf.write(fp, arcname)

        zipf.writestr(
            f'/static/schedula/forms/{form}-data.json', json.dumps(data)
        )
        zipf.writestr(
            f'/locales/languages.json', json.dumps(ca.config.get('BABEL_LANGUAGES'))
        )
        zipf.write(osp.join(osp.dirname(__file__), 'start.py'), '/start.py')
    output_zip.seek(0)

    return send_file(
        output_zip, mimetype='application/zip', as_attachment=True,
        download_name=f'{form}.zip'
    )


class ExportForm:
    def __init__(self, app, sitemap, *args, **kwargs):
        if app is not None:
            self.init_app(app, sitemap, *args, **kwargs)

    def init_app(self, app, sitemap, *args, **kwargs):
        app.render_form = sitemap.render_form
        app.extensions = getattr(app, 'extensions', {})
        app.register_blueprint(bp, url_prefix='/export-form')
        app.extensions['schedula_export_form'] = self
