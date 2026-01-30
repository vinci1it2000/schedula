# coding=utf-8
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2026, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');

"""
Minimal OpenAPI + Swagger UI integration (no heavy deps).

- GET /openapi.json  -> OpenAPI 3.0 document (JSON)
- GET /docs          -> Swagger UI (uses CDN by default)

Note:
If you need an air‑gapped deployment, vendor swagger-ui-dist and point
SWAGGER_UI_DIST_URL to your local static path.
"""
from __future__ import annotations

import os.path as osp
from dataclasses import dataclass

import yaml
from flask import Blueprint, current_app, jsonify, Response, send_file, request

OPENAPI_YAML_PATH = osp.join(
    osp.dirname(__file__),
    "openapi",
    "openapi.yaml"
)


def _swagger_ui_html(openapi_url: str) -> str:
    # Default to CDN. You can override via config to point to a local static.
    dist = current_app.config.get("SWAGGER_UI_DIST_URL",
                                  "https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js")
    css = current_app.config.get("SWAGGER_UI_CSS_URL",
                                 "https://unpkg.com/swagger-ui-dist@5/swagger-ui.css")

    return f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>Schedula API Docs</title>
    <link rel="stylesheet" href="{css}">
    <style>body{{margin:0;padding:0}}</style>
  </head>
  <body>
    <div id="swagger-ui"></div>
    <script src="{dist}"></script>
    <script>
      window.ui = SwaggerUIBundle({{
        url: "{openapi_url}",
        dom_id: '#swagger-ui',
        presets: [SwaggerUIBundle.presets.apis],
        layout: "BaseLayout"
      }});
    </script>
  </body>
</html>"""


def get_blueprint_prefix():
    bp_name = request.blueprint
    if not bp_name:
        return ""
    bp = current_app.blueprints[bp_name]
    return bp.url_prefix or ""


bp = Blueprint("openapi", __name__)


@bp.get("/docs")
def swagger_ui():
    prefix = get_blueprint_prefix()
    html = _swagger_ui_html(openapi_url=f"{prefix}/openapi.yaml")
    return Response(html, mimetype="text/html")


@bp.get("/openapi.yaml")
def openapi_yaml():
    return send_file(
        OPENAPI_YAML_PATH,
        mimetype="text/yaml"
    )


@bp.get("/openapi.json")
def openapi_json():
    with open(OPENAPI_YAML_PATH, "r", encoding="utf-8") as f:
        spec = yaml.safe_load(f)

    return jsonify(spec)


@dataclass
class OpenAPI:
    """Register minimal OpenAPI endpoints."""
    url_prefix: str = ""

    def __init__(self, app=None, url_prefix: str = ""):
        self.url_prefix = url_prefix
        if app is not None:
            self.init_app(app, url_prefix=url_prefix)

    def init_app(self, app, url_prefix: str = ""):
        app.register_blueprint(bp, url_prefix=url_prefix)
        app.extensions["openapi"] = self
