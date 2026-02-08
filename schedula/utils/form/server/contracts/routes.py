# coding=utf-8
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2026, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');

"""Contracts API service (workflow JSON a stati)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pydash
from flask import Blueprint, jsonify, request
from jsonschema import Draft202012Validator

from .engine import (
    _apply_on_enter,
    _process_event,
)
from ..security.casbin import (
    get_auth_sub,
    get_current_sub,
    require_system_admin,
)
from ..utils import (
    abort_json,
    config_get,
    get_mongo,
    mongo_find,
    mongo_find_one,
    mongo_insert_one,
    mongo_update_one,
    now_utc,
    set_bp_error_handlers,
)

bp = Blueprint("contracts", __name__)
set_bp_error_handlers(bp)

MAX_AUTO_TRANSITIONS = 100

TEMPLATE_CREATE_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "minLength": 1},
        "description": {"type": "string"},
        "definition": {"type": "object"},
        "metadata": {"type": "object"},
        "isEnabled": {"type": "boolean"},
        "isPublic": {"type": "boolean"},
        "allowedSubjects": {
            "type": "array",
            "items": {"type": "string"},
        },
        "allowedInitialStates": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
        },
    },
    "required": ["name", "definition"],
    "additionalProperties": False,
}

TEMPLATE_UPDATE_SCHEMA = {
    "type": "object",
    "properties": TEMPLATE_CREATE_SCHEMA["properties"],
    "additionalProperties": False,
}


def _contracts_coll():
    return get_mongo(collection=config_get("CONTRACTS_COLLECTION", "contracts"))


def _events_coll():
    return get_mongo(
        collection=config_get("CONTRACT_EVENTS_COLLECTION", "contract_events")
    )


def _effects_coll():
    return get_mongo(
        collection=config_get("CONTRACT_EFFECTS_COLLECTION", "outbox_effects")
    )


def _templates_coll():
    return get_mongo(
        collection=config_get("CONTRACT_TEMPLATES_COLLECTION", "contract_templates")
    )


def _ensure_indexes():
    contracts = _contracts_coll()
    templates = _templates_coll()
    contracts.create_index([("template_id", 1), ("created_at", -1)])
    contracts.create_index([("status", 1), ("updated_at", -1)])
    templates.create_index([("is_enabled", 1), ("is_public", 1), ("updated_at", -1)])
    templates.create_index([("name", 1), ("updated_at", -1)])


def _serialize_contract(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": doc.get("_id"),
        "status": doc.get("status"),
        "state": doc.get("state"),
        "version": doc.get("version"),
        "context": doc.get("context") or {},
        "states": doc.get("states") or {},
        "userState": pydash.get(doc, f"states.{get_current_sub()}"),
        "lastError": doc.get("last_error"),
    }


def _parse_json_body() -> Dict[str, Any]:
    payload = request.get_json(force=True, silent=True) or {}
    if not isinstance(payload, dict):
        abort_json(400, "Invalid JSON payload")
    return payload


def _get_contract(contract_id: str) -> Optional[Dict[str, Any]]:
    return mongo_find_one(_contracts_coll(), {"_id": contract_id})


def _serialize_template(doc: Dict[str, Any]) -> Dict[str, Any]:
    created_at = doc.get("created_at")
    updated_at = doc.get("updated_at")
    created_at_str = (
        created_at.isoformat() if isinstance(created_at, datetime) else None
    )
    updated_at_str = (
        updated_at.isoformat() if isinstance(updated_at, datetime) else None
    )
    return {
        "id": doc.get("_id"),
        "name": doc.get("name"),
        "description": doc.get("description"),
        "isEnabled": bool(doc.get("is_enabled", False)),
        "isPublic": bool(doc.get("is_public", False)),
        "allowedSubjects": doc.get("allowed_subjects") or [],
        "allowedInitialStates": doc.get("allowed_initial_states") or [],
        "definition": doc.get("definition") or {},
        "metadata": doc.get("metadata") or {},
        "createdAt": created_at_str,
        "updatedAt": updated_at_str,
    }


def _validate_schema(payload: Dict[str, Any], schema: Dict[str, Any]) -> List[str]:
    try:
        v = Draft202012Validator(schema)
        return [e.message for e in v.iter_errors(payload)]
    except Exception as e:
        return [str(e)]


def _validate_allowed_initial_states(
        definition: Dict[str, Any],
        allowed_initial_states: Any,
) -> List[str]:
    if allowed_initial_states is None:
        return []
    if not isinstance(allowed_initial_states, list):
        return ["allowedInitialStates must be array"]
    states = definition.get("states") or {}
    if not isinstance(states, dict):
        return ["definition.states must be object"]
    errors: List[str] = []
    for state in allowed_initial_states:
        if not isinstance(state, str) or not state.strip():
            errors.append("allowedInitialStates entries must be non-empty strings")
            continue
        if state not in states:
            errors.append(f"allowedInitialStates includes unknown state '{state}'")
    return errors


def _create_contract_from_template_doc(
        *,
        template: Dict[str, Any],
        template_id: str,
        context: Dict[str, Any],
        owner_id: str,
        initial_state: Optional[str] = None,
) -> Tuple[Dict[str, Any], int]:
    if not bool(template.get("is_enabled", False)):
        abort_json(409, "Template disabled")

    definition = template["definition"]

    contract_id = str(uuid.uuid4())
    context["contractId"] = contract_id
    default_initial_state = str(definition.get("initialState") or "")
    allowed_initial_states = set(template.get("allowed_initial_states", []))
    allowed_initial_states.add(default_initial_state)
    state = initial_state or default_initial_state
    if state not in allowed_initial_states:
        abort_json(409, f"Initial state '{state}' not allowed by template")
    now = now_utc()

    metadata = template.get("metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}

    doc = {
        "_id": contract_id,
        "status": "RUNNING",
        "state": state,
        "states": {},
        "context": context,
        "definition": definition,
        "metadata": metadata,
        "created_by": owner_id,
        "created_at": now,
        "updated_at": now,
        "template_id": template_id,
    }
    mongo_insert_one(_contracts_coll(), doc)

    doc = _apply_on_enter(doc=_get_contract(contract_id), actor_id=str(owner_id))

    return _serialize_contract(doc), 201


@bp.post("/contracts/templates")
@require_system_admin("contracts:templates", "manage")
def create_template():
    payload = _parse_json_body()
    schema_errors = _validate_schema(payload, TEMPLATE_CREATE_SCHEMA)
    if schema_errors:
        return jsonify({"error": "Invalid payload", "details": schema_errors}), 422

    name = str(payload.get("name") or "").strip()
    description = payload.get("description")
    definition = payload.get("definition")
    metadata = payload.get("metadata") or {}
    is_enabled = payload.get("isEnabled", True)
    is_public = payload.get("isPublic", False)
    allowed_subjects = payload.get("allowedSubjects") or []
    allowed_initial_states = payload.get("allowedInitialStates") or []

    if not name:
        abort_json(400, "name required")

    initial_state_errors = _validate_allowed_initial_states(
        definition, allowed_initial_states
    )
    if initial_state_errors:
        return jsonify(
            {"error": "Invalid payload", "details": initial_state_errors}
        ), 422

    now = now_utc()
    doc = {
        "_id": str(uuid.uuid4()),
        "name": name,
        "description": description,
        "definition": definition,
        "metadata": metadata,
        "is_enabled": is_enabled,
        "is_public": is_public,
        "allowed_subjects": allowed_subjects,
        "allowed_initial_states": allowed_initial_states,
        "created_at": now,
        "updated_at": now,
    }
    mongo_insert_one(_templates_coll(), doc)
    return jsonify(_serialize_template(doc)), 201


@bp.get("/contracts/templates")
@require_system_admin("contracts:templates", "manage")
def list_templates():
    docs = list(mongo_find(_templates_coll(), {}))
    return jsonify({"templates": [_serialize_template(d) for d in docs]}), 200


@bp.get("/contracts/templates/<template_id>")
@require_system_admin("contracts:templates", "manage")
def get_template(template_id: str):
    doc = mongo_find_one(_templates_coll(), {"_id": template_id})
    if not doc:
        abort_json(404, "Template not found")
    return jsonify(_serialize_template(doc)), 200


@bp.put("/contracts/templates/<template_id>")
@require_system_admin("contracts:templates", "manage")
def update_template(template_id: str):
    payload = _parse_json_body()
    schema_errors = _validate_schema(payload, TEMPLATE_UPDATE_SCHEMA)
    if schema_errors:
        return jsonify({"error": "Invalid payload", "details": schema_errors}), 422
    updates: Dict[str, Any] = {}
    if "name" in payload:
        name_value = payload.get("name")
        if not isinstance(name_value, str):
            abort_json(400, "name required")
        name = str(name_value or "").strip()
        if not name:
            abort_json(400, "name required")
        updates["name"] = name
    if "description" in payload:
        updates["description"] = payload.get("description")
    if "metadata" in payload:
        if not isinstance(payload.get("metadata"), dict):
            abort_json(400, "metadata must be object")
        updates["metadata"] = payload.get("metadata")
    if "isEnabled" in payload:
        if not isinstance(payload.get("isEnabled"), bool):
            abort_json(400, "isEnabled must be boolean")
        updates["is_enabled"] = payload.get("isEnabled")
    if "isPublic" in payload:
        if not isinstance(payload.get("isPublic"), bool):
            abort_json(400, "isPublic must be boolean")
        updates["is_public"] = payload.get("isPublic")
    if "allowedSubjects" in payload:
        allowed_subjects = payload.get("allowedSubjects")
        if allowed_subjects and not isinstance(allowed_subjects, list):
            abort_json(400, "allowedSubjects must be list")
        updates["allowed_subjects"] = allowed_subjects or []
    if "allowedInitialStates" in payload:
        allowed_initial_states = payload.get("allowedInitialStates")
        if allowed_initial_states and not isinstance(allowed_initial_states, list):
            abort_json(400, "allowedInitialStates must be list")
        updates["allowed_initial_states"] = allowed_initial_states or []
    if "definition" in payload:
        updates["definition"] = payload.get("definition")

    existing = mongo_find_one(_templates_coll(), {"_id": template_id})
    if not existing:
        abort_json(404, "Template not found")
    next_definition = updates.get("definition") or existing.get("definition") or {}
    next_allowed_initial_states = (
        updates.get("allowed_initial_states")
        if "allowed_initial_states" in updates
        else existing.get("allowed_initial_states")
    )
    initial_state_errors = _validate_allowed_initial_states(
        next_definition,
        next_allowed_initial_states,
    )
    if initial_state_errors:
        return jsonify(
            {"error": "Invalid payload", "details": initial_state_errors}
        ), 422

    if not updates:
        abort_json(400, "No updates provided")

    updates["updated_at"] = now_utc()
    res = mongo_update_one(_templates_coll(), {"_id": template_id}, {"$set": updates})
    if res.matched_count != 1:
        abort_json(404, "Template not found")
    doc = mongo_find_one(_templates_coll(), {"_id": template_id})
    return jsonify(_serialize_template(doc)), 200


@bp.post("/contracts/<template_id>")
def create_contract(template_id: str):
    payload = _parse_json_body()
    unexpected_keys = set(payload.keys()) - {"context", "initialState"}
    if unexpected_keys:
        abort_json(400, "Only context and initialState are allowed")
    context = payload.get("context") or {}
    if not isinstance(context, dict):
        abort_json(400, "context must be object")
    initial_state = None
    if "initialState" in payload:
        initial_state = payload.get("initialState")
        initial_state = (
            initial_state.strip() if isinstance(initial_state, str) else None
        )
        if not initial_state:
            abort_json(400, "initialState must be non-empty string")

    owner_id = get_auth_sub()
    template = mongo_find_one(_templates_coll(), {"_id": template_id})
    if not template:
        abort_json(404, "Template not found")
    result, status = _create_contract_from_template_doc(
        template=template,
        template_id=template_id,
        context=context,
        owner_id=owner_id,
        initial_state=initial_state,
    )
    return jsonify(result), status


@bp.get("/contracts/<contract_id>")
def get_contract(contract_id: str):
    doc = _get_contract(contract_id)
    if not doc:
        abort_json(404, "Contract not found")
    return jsonify(_serialize_contract(doc)), 200


@bp.delete("/contracts/<contract_id>")
def cancel_contract(contract_id: str):
    now = now_utc()
    res = mongo_update_one(
        _contracts_coll(),
        {"_id": contract_id, "status": {"$ne": "CANCELED"}},
        {"$set": {"status": "CANCELED", "updated_at": now}},
    )
    if res.matched_count != 1:
        abort_json(404, "Contract not found")
    doc = _get_contract(contract_id)
    if not doc:
        abort_json(404, "Contract not found")
    assert doc is not None
    return jsonify(_serialize_contract(doc)), 200


@bp.route("/contracts/<contract_id>/<path:dyn_path>", methods=["POST", "GET"])
def contract_api_event(contract_id: str, dyn_path: str):
    payload = _parse_json_body()
    actor_id = get_current_sub()
    body_payload = payload.get("payload") or {}

    if not isinstance(body_payload, dict):
        abort_json(400, "payload must be object")

    doc = _get_contract(contract_id)
    if not doc:
        abort_json(404, "Contract not found")

    result, status = _process_event(
        doc=doc,
        dyn_path=dyn_path,
        actor_id=actor_id,
        body_payload=body_payload,
    )
    return jsonify(result), status
