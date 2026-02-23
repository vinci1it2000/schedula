# coding: utf-8
from __future__ import annotations

import importlib.resources as ir
from typing import Dict, Set

import pytest
from schemathesis.openapi import from_path

from tests.utils.server.utils.openapi import is_multipart


def _allowed_statuses(operation) -> Set[int]:
    raw = getattr(getattr(operation, "definition", None), "raw", None) or {}
    responses = raw.get("responses") or {}
    out: Set[int] = set()
    for code in responses.keys():
        if isinstance(code, int):
            out.add(code)
        elif isinstance(code, str) and code.isdigit():
            out.add(int(code))
    return out


# 🔑 Recupera openapi.yaml dal package schedula
def _openapi_resource():
    """
    Returns the OpenAPI resource handle for the package.
    """
    return ir.files("schedula.utils.form.server.openapi") / "openapi.yaml"


with ir.as_file(_openapi_resource()) as _schema_path:
    SCHEMA = from_path(_schema_path)


@SCHEMA.parametrize()
def test_openapi_contract_all_routes(case, app, auth_headers):
    """
    Contract test: for each OpenAPI operation, execute a request against the
    in-process WSGI app and validate:
      - HTTP status code ∈ declared OpenAPI responses
      - response body conforms to schema
    """
    if case.operation and case.operation.definition:
        raw = case.operation.definition.raw
        if is_multipart(raw):
            pytest.skip("multipart/form-data operation covered elsewhere")

    headers: Dict[str, str] = {}
    allowed = _allowed_statuses(case.operation)

    if not allowed:
        allowed = {200, 201, 202, 204, 400, 401, 403, 404, 405, 409, 422, 500}

    if 200 in allowed or 201 in allowed:
        headers = auth_headers("admin") or auth_headers("user") or {}

    response = case.call_wsgi(app, headers=headers)

    assert response.status_code in allowed, (
        response.status_code,
        sorted(allowed),
        case.method,
        case.path,
    )

    case.validate_response(response)
