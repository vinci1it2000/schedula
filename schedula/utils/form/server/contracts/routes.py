# coding=utf-8
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2026, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');

"""Contracts API service (workflow JSON a stati)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, cast

from flask import Blueprint, current_app, jsonify, request
from jsonschema import Draft202012Validator

from .engine import (
    apply_context_update,
    available_actions,
    available_actions_actor,
    build_effect_payload,
    find_event_by_path,
    generate_event_id,
    set_context_value,
    hash_payload,
    is_final_state,
    normalize_event_path,
    pick_transition,
    resolve_on_enter_effects,
    resolve_on_enter_transition,
    validate_definition,
    validate_payload,
)
from .registry import get_registry
from ..security.casbin import (
    get_enforcer,
    require_system_admin,
    get_current_sub,
    enforce_or_403,
    get_auth_sub,
    is_system_admin,
)
from ..utils import (
    RefResolver,
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


def _timers_coll():
    return get_mongo(
        collection=config_get("CONTRACT_TIMERS_COLLECTION", "contract_timers")
    )


def _templates_coll():
    return get_mongo(
        collection=config_get("CONTRACT_TEMPLATES_COLLECTION", "contract_templates")
    )


def _ensure_indexes():
    contracts = _contracts_coll()
    events = _events_coll()
    effects = _effects_coll()
    timers = _timers_coll()

    if not current_app.config.get("CONTRACTS_DISABLE_IDEMPOTENCY_INDEX", False):
        contracts.create_index(
            [("owner_id", 1), ("idempotency_key", 1)], unique=True, sparse=True
        )
    events.create_index([("contract_id", 1), ("event_id", 1)], unique=True)
    if not current_app.config.get("CONTRACTS_DISABLE_IDEMPOTENCY_INDEX", False):
        events.create_index(
            [("contract_id", 1), ("idempotency_key", 1)], unique=True, sparse=True
        )
    effects.create_index([("contract_id", 1), ("status", 1)])
    timers.create_index(
        [("contract_id", 1), ("timer_name", 1)], unique=True, sparse=True
    )


def _serialize_contract(doc: Dict[str, Any]) -> Dict[str, Any]:
    actor_id = get_current_sub()
    actor_state = _actor_state(doc, actor_id)
    return {
        "id": doc.get("_id"),
        "status": doc.get("status"),
        "state": doc.get("state"),
        "version": doc.get("version"),
        "context": doc.get("context") or {},
        "states": doc.get("states") or {},
        "actorState": actor_state,
        "availableActionsGlobal": available_actions(
            doc.get("definition") or {}, str(doc.get("state") or "")
        ),
        "availableActionsActor": available_actions_actor(
            doc.get("definition") or {}, str(doc.get("state") or ""), actor_state
        ),
        "availableActions": available_actions_actor(
            doc.get("definition") or {}, str(doc.get("state") or ""), actor_state
        ),
        "lastError": doc.get("last_error"),
    }


def _security_enabled() -> bool:
    return bool(current_app.config.get("SECURITY_ENABLED", False))


def _enforce_template_create(template_doc: Dict[str, Any]) -> None:
    if not _security_enabled():
        return
    sub = get_auth_sub()
    if is_system_admin(sub):
        return
    if bool(template_doc.get("is_public", False)):
        enforce_or_403(sub, "acl:contracts", "contracts:template:public", "create")
        return
    allowed_subjects = template_doc.get("allowed_subjects") or []
    if isinstance(allowed_subjects, list) and sub in allowed_subjects:
        return
    enforce_or_403(
        sub,
        "acl:contracts",
        f"contracts:template:{template_doc.get('_id')}",
        "create",
    )


def _template_is_available(template_doc: Dict[str, Any], sub: Optional[str]) -> bool:
    if not bool(template_doc.get("is_enabled", False)):
        return False
    if not _security_enabled():
        return True
    if not sub:
        return False
    if is_system_admin(sub):
        return True
    if bool(template_doc.get("is_public", False)):
        e = get_enforcer()
        return e.enforce(sub, "acl:contracts", "contracts:template:public", "create")
    allowed_subjects = template_doc.get("allowed_subjects") or []
    if isinstance(allowed_subjects, list) and sub in allowed_subjects:
        return True
    e = get_enforcer()
    return e.enforce(
        sub,
        "acl:contracts",
        f"contracts:template:{template_doc.get('_id')}",
        "create",
    )


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


def _check_idempotency(
        contract_id: str, event_id: Optional[str], idem_key: Optional[str]
) -> Optional[Dict[str, Any]]:
    events = _events_coll()
    if event_id:
        doc = mongo_find_one(events, {"contract_id": contract_id, "event_id": event_id})
        if doc:
            return doc
    if idem_key:
        doc = mongo_find_one(
            events, {"contract_id": contract_id, "idempotency_key": idem_key}
        )
        if doc:
            return doc
    return None


def _idempotent_response(doc: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    current = _get_contract(str(doc.get("_id"))) or doc
    actor_id = get_current_sub()
    actor_state = _actor_state(current, actor_id)
    return (
        {
            "id": current.get("_id"),
            "status": current.get("status"),
            "state": current.get("state"),
            "version": current.get("version"),
            "context": current.get("context") or {},
            "states": current.get("states") or {},
            "actorState": actor_state,
            "effects": [],
            "availableActionsGlobal": available_actions(
                current.get("definition") or {},
                str(current.get("state") or ""),
            ),
            "availableActionsActor": available_actions_actor(
                current.get("definition") or {},
                str(current.get("state") or ""),
                actor_state,
            ),
            "availableActions": available_actions_actor(
                current.get("definition") or {},
                str(current.get("state") or ""),
                actor_state,
            ),
        },
        200,
    )


def _actor_state(doc: Dict[str, Any], actor_id: str) -> Optional[str]:
    states = doc.get("states") or {}
    item = states.get(actor_id)
    if isinstance(item, dict):
        item = item.get("state")
    if isinstance(item, str):
        return item
    return "UNKNOW"


def _execute_effect(effect_doc: Dict[str, Any]) -> Tuple[str, Optional[str]]:
    registry = get_registry()
    ef_type = str(effect_doc.get("effect_type") or "")
    payload = effect_doc.get("payload") or {}
    action = registry.get(ef_type)
    if not action:
        return "ERROR", f"Unknown effect type '{ef_type}'"
    try:
        result = action.handler(payload)
        save_response = effect_doc.get("save_response")
        if save_response and isinstance(save_response, dict):
            contract_id = effect_doc.get("contract_id")
            if contract_id:
                response_value = None
                select = save_response.get("select")
                if isinstance(select, dict) and "$ref" in select:
                    ref = select.get("$ref")
                    if isinstance(ref, str) and ref.startswith("/response/"):
                        response_value = _select_response_value(result, ref)
                if response_value is None:
                    response_value = result
                path = save_response.get("path")
                if isinstance(path, str) and path:
                    doc = _get_contract(str(contract_id))
                    if doc:
                        updated_ctx = set_context_value(
                            doc.get("context") or {}, path, response_value
                        )
                        mongo_update_one(
                            _contracts_coll(),
                            {"_id": contract_id},
                            {"$set": {"context": updated_ctx, "updated_at": now_utc()}},
                        )
        return "DONE", None
    except Exception as e:
        return "ERROR", str(e)


def _select_response_value(result: Any, ref: str) -> Any:
    data = None
    if isinstance(result, dict) and "response" in result:
        data = result.get("response")
    elif isinstance(result, dict):
        data = result
    if data is None:
        return None
    path = ref[len("/response/"):]
    parts = [p for p in path.split("/") if p]
    cur: Any = data
    for part in parts:
        if isinstance(cur, dict):
            if part not in cur:
                return None
            cur = cur.get(part)
        elif isinstance(cur, list):
            try:
                idx = int(part)
            except ValueError:
                return None
            if idx < 0 or idx >= len(cur):
                return None
            cur = cur[idx]
        else:
            return None
    return cur


def _run_effects(contract_id: str, effect_ids: List[str]) -> List[Dict[str, Any]]:
    effects = _effects_coll()
    output = []
    for eid in effect_ids:
        now = now_utc()
        mongo_update_one(
            effects,
            {"_id": eid},
            {"$set": {"status": "RUNNING", "updated_at": now}, "$inc": {"attempts": 1}},
        )
        doc = mongo_find_one(effects, {"_id": eid}) or {}
        status, err = _execute_effect(doc)
        update = {"status": status, "updated_at": now_utc()}
        if err:
            update["last_error"] = {"message": err, "at": now_utc().isoformat()}
        mongo_update_one(effects, {"_id": eid}, {"$set": update})
        output.append({"type": doc.get("effect_type"), "payload": doc.get("payload")})
    return output


def _apply_on_enter(
        definition: Dict[str, Any],
        state: str,
        *,
        context: Dict[str, Any],
        actor_id: str,
        event_id: str,
) -> Tuple[str, List[Dict[str, Any]], Dict[str, Any]]:
    effects: List[Dict[str, Any]] = []
    max_auto = int(config_get("CONTRACTS_MAX_AUTO_TRANSITIONS", 3))
    current = state
    seen = set()
    for _ in range(max_auto + 1):
        if current in seen:
            break
        seen.add(current)
        for ef in resolve_on_enter_effects(definition, current):
            ef_type = ef.get("type")
            if ef_type == "context.update":
                context = apply_context_update(
                    context,
                    ef.get("update") or {},
                    payload={},
                    actor_id=actor_id,
                    event_id=event_id,
                )
                continue
            effects.append(
                {
                    "type": ef_type,
                    "payload": build_effect_payload(
                        ef,
                        context=context,
                        payload={},
                        actor_id=actor_id,
                        event_id=event_id,
                    ),
                    "saveResponse": ef.get("saveResponse"),
                }
            )
        next_state = resolve_on_enter_transition(definition, current)
        if not next_state:
            break
        current = next_state
    return current, effects, context


def _process_event(
        *,
        contract_id: str,
        doc: Dict[str, Any],
        dyn_path: str,
        event_id: str,
        actor_id: str,
        body_payload: Dict[str, Any],
        idem_key: Optional[str],
        if_match: Optional[str],
) -> Tuple[Dict[str, Any], int]:
    if doc.get("status") in ("DONE", "CANCELED"):
        replay = _check_idempotency(contract_id, event_id, idem_key)
        if replay:
            return _idempotent_response(doc)
        abort_json(410, "Contract not accepting events")

    if if_match:
        try:
            if int(if_match) != int(doc.get("version", 0)):
                abort_json(409, "Version mismatch")
        except Exception:
            abort_json(409, "Invalid If-Match")

    state = str(doc.get("state") or "")
    ename, edef = find_event_by_path(doc.get("definition") or {}, state, dyn_path)
    if not edef:
        abort_json(409, "Event not available in this state")
    actor_state_before = _actor_state(doc, actor_id)
    context = doc.get("context") or {}
    resolver = RefResolver(context=context, enforce_acl=False)
    if (
            ("allowUserStates" in edef and actor_state_before not in set(resolver(edef.get("allowUserStates")) or []))
            or
            ("denyUserStates" in edef and actor_state_before in set(resolver(edef.get("denyUserStates")) or []))
    ):
        abort_json(409, "Event not available for actor state")
    if "allowedPrincipals" in edef or "denyPrincipals" in edef:
        enforcer = get_enforcer()
        roles = set(enforcer.get_roles_for_user(actor_id))
        if "allowedPrincipals" in edef and not roles.intersection(set(resolver(edef.get("allowedPrincipals")) or [])):
            abort_json(403, "Subject not allowed")
        if "denyPrincipals" in edef and roles.intersection(set(resolver(edef.get("denyPrincipals")) or [])):
            abort_json(403, "Subject denied")

    schema_errors = validate_payload(edef.get("payloadSchema"), body_payload)
    if schema_errors:
        return {"error": "Invalid payload", "details": schema_errors}, 422

    replay = _check_idempotency(contract_id, event_id, idem_key)
    if replay:
        abort_json(409, "Event replay")

    effects: List[Dict[str, Any]] = []
    for ef in edef.get("effects") or []:
        ef_type = ef.get("type")
        if ef_type == "context.update":
            context = apply_context_update(
                context,
                ef.get("update") or {},
                payload=body_payload,
                actor_id=actor_id,
                event_id=event_id,
            )
            continue
        effects.append(
            {
                "type": ef_type,
                "payload": build_effect_payload(
                    ef,
                    context=context,
                    payload=body_payload,
                    actor_id=actor_id,
                    event_id=event_id,
                ),
                "saveResponse": ef.get("saveResponse"),
            }
        )

    global_rule = {
        "transitions": edef.get("globalTransitions") or edef.get("transitions") or [],
        "defaultTarget": edef.get("defaultGlobalTarget")
        if "defaultGlobalTarget" in edef
        else edef.get("defaultTarget"),
    }
    next_state, reason = pick_transition(global_rule, context)
    state_before = state
    state_after = next_state or state_before

    user_rule = {
        "transitions": edef.get("userTransitions") or [],
        "defaultTarget": edef.get("defaultUserTarget"),
    }
    user_state_after, _ = pick_transition(user_rule, context)

    instance_states = dict(doc.get("states") or {})
    if user_state_after:
        instance_states[actor_id] = {
            "state": user_state_after,
            "updatedAt": now_utc().isoformat(),
            "lastEvent": ename,
        }

    if next_state:
        state_after, on_enter_effects, context = _apply_on_enter(
            doc.get("definition") or {},
            str(state_after or ""),
            context=context,
            actor_id=actor_id,
            event_id=event_id,
        )
        effects.extend(on_enter_effects)

    status = (
        "DONE"
        if is_final_state(doc.get("definition") or {}, str(state_after or ""))
        else "RUNNING"
    )

    new_version = int(doc.get("version", 0)) + 1
    now = now_utc()

    update_doc = {
        "state": state_after,
        "states": instance_states,
        "context": context,
        "version": new_version,
        "status": status,
        "updated_at": now,
    }

    res = mongo_update_one(
        _contracts_coll(),
        {"_id": contract_id, "version": doc.get("version")},
        {"$set": update_doc},
    )
    if res.matched_count != 1:
        abort_json(409, "Version mismatch")

    event_doc = {
        "_id": str(uuid.uuid4()),
        "contract_id": contract_id,
        "event_id": event_id,
        "path": normalize_event_path(edef),
        "event_name": ename,
        "actor_id": actor_id,
        "role": None,
        "payload": body_payload,
        "payload_hash": hash_payload(body_payload),
        "state_before": state_before,
        "state_after": state_after,
        "actor_state_before": actor_state_before,
        "actor_state_after": user_state_after,
        "transition_reason": reason,
        "created_at": now,
    }
    if idem_key:
        event_doc["idempotency_key"] = idem_key
    mongo_insert_one(_events_coll(), event_doc)

    effect_ids: List[str] = []
    for ef in effects:
        effect_id = str(uuid.uuid4())
        mongo_insert_one(
            _effects_coll(),
            {
                "_id": effect_id,
                "contract_id": contract_id,
                "effect_type": ef.get("type"),
                "payload": ef.get("payload") or {},
                "save_response": ef.get("saveResponse"),
                "status": "PENDING",
                "attempts": 0,
                "last_error": None,
                "created_at": now_utc(),
                "updated_at": now_utc(),
            },
        )
        effect_ids.append(effect_id)

    effect_results = _run_effects(contract_id, effect_ids)

    if config_get("CONTRACTS_FAIL_ON_EFFECT_ERROR", False):
        if any(
                e
                for e in _effects_coll().find(
                    {"_id": {"$in": effect_ids}, "status": "ERROR"}
                )
        ):
            mongo_update_one(
                _contracts_coll(),
                {"_id": contract_id},
                {
                    "$set": {
                        "status": "ERROR",
                        "last_error": {
                            "code": "effect_error",
                            "message": "Effect failed",
                            "at": now_utc().isoformat(),
                        },
                    }
                },
            )

    updated = _get_contract(contract_id) or {}
    actor_state = _actor_state(updated, actor_id)
    return (
        {
            "id": updated.get("_id"),
            "status": updated.get("status"),
            "state": updated.get("state"),
            "version": updated.get("version"),
            "context": updated.get("context") or {},
            "states": updated.get("states") or {},
            "actorState": actor_state,
            "effects": effect_results,
            "availableActionsGlobal": available_actions(
                updated.get("definition") or {}, str(updated.get("state") or "")
            ),
            "availableActionsActor": available_actions_actor(
                updated.get("definition") or {},
                str(updated.get("state") or ""),
                actor_state,
            ),
            "availableActions": available_actions_actor(
                updated.get("definition") or {},
                str(updated.get("state") or ""),
                actor_state,
            ),
        },
        200,
    )


@bp.get("/actions")
def list_actions():
    reg = get_registry()
    actions = [
        {"type": k, "schema": v.schema} for k, v in sorted(reg.list_types().items())
    ]
    return jsonify({"actions": actions}), 200


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

    if not name:
        abort_json(400, "name required")

    reg = get_registry()
    res = validate_definition(definition if isinstance(definition, dict) else {}, reg)
    if not res.valid:
        return jsonify({"valid": False, "errors": res.errors, "normalized": {}}), 422

    now = now_utc()
    doc = {
        "_id": str(uuid.uuid4()),
        "name": name,
        "description": description,
        "definition": res.normalized,
        "metadata": metadata,
        "is_enabled": is_enabled,
        "is_public": is_public,
        "allowed_subjects": allowed_subjects,
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


@bp.get("/contracts/templates/available")
def list_available_templates():
    docs = list(mongo_find(_templates_coll(), {}))
    sub = get_auth_sub() if _security_enabled() else None
    available = [_serialize_template(d) for d in docs if _template_is_available(d, sub)]
    return jsonify({"templates": available}), 200


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
    if "definition" in payload:
        reg = get_registry()
        definition = payload.get("definition")
        res = validate_definition(
            definition if isinstance(definition, dict) else {},
            reg,
        )
        if not res.valid:
            return jsonify(
                {"valid": False, "errors": res.errors, "normalized": {}}
            ), 422
        updates["definition"] = res.normalized

    if not updates:
        abort_json(400, "No updates provided")

    updates["updated_at"] = now_utc()
    res = mongo_update_one(_templates_coll(), {"_id": template_id}, {"$set": updates})
    if res.matched_count != 1:
        abort_json(404, "Template not found")
    doc = mongo_find_one(_templates_coll(), {"_id": template_id})
    return jsonify(_serialize_template(doc)), 200


@bp.post("/contracts/templates/<template_id>/contracts")
def create_contract_from_template(template_id: str):
    payload = _parse_json_body()
    context = payload.get("context") or {}
    metadata = payload.get("metadata") or {}

    if not isinstance(context, dict):
        abort_json(400, "context must be object")
    if not isinstance(metadata, dict):
        abort_json(400, "metadata must be object")

    template = mongo_find_one(_templates_coll(), {"_id": template_id})
    if not template:
        abort_json(404, "Template not found")
    if not bool(template.get("is_enabled", False)):
        abort_json(409, "Template disabled")

    _enforce_template_create(template)

    owner_id = get_auth_sub()

    idem_key = request.headers.get("Idempotency-Key")
    if idem_key:
        existing = mongo_find_one(
            _contracts_coll(), {"owner_id": owner_id, "idempotency_key": idem_key}
        )
        if existing:
            return jsonify(_serialize_contract(existing)), 200

    definition = template.get("definition")
    reg = get_registry()
    res = validate_definition(definition if isinstance(definition, dict) else {}, reg)
    if not res.valid:
        return jsonify({"valid": False, "errors": res.errors, "normalized": {}}), 422

    contract_id = str(uuid.uuid4())
    context["contractId"] = contract_id
    state = str(res.normalized.get("initialState") or "")
    status = "RUNNING"
    now = now_utc()

    state, on_enter_effects, context = _apply_on_enter(
        res.normalized,
        state,
        context=context,
        actor_id=str(owner_id),
        event_id=str(uuid.uuid4()),
    )
    if is_final_state(res.normalized, state):
        status = "DONE"

    doc = {
        "_id": contract_id,
        "owner_id": owner_id,
        "status": status,
        "state": state,
        "states": {},
        "version": 1,
        "context": context,
        "definition": res.normalized,
        "metadata": metadata,
        "created_at": now,
        "updated_at": now,
        "last_error": None,
        "template_id": template_id,
    }
    if idem_key:
        doc["idempotency_key"] = idem_key
    mongo_insert_one(_contracts_coll(), doc)

    effect_ids: List[str] = []
    for ef in on_enter_effects:
        effect_id = str(uuid.uuid4())
        mongo_insert_one(
            _effects_coll(),
            {
                "_id": effect_id,
                "contract_id": contract_id,
                "effect_type": ef.get("type"),
                "payload": ef.get("payload") or {},
                "save_response": ef.get("saveResponse"),
                "status": "PENDING",
                "attempts": 0,
                "last_error": None,
                "created_at": now_utc(),
                "updated_at": now_utc(),
            },
        )
        effect_ids.append(effect_id)

    _run_effects(contract_id, effect_ids)

    return jsonify(_serialize_contract(doc)), 201


@bp.post("/contracts/validate")
def validate_contract_definition():
    payload = _parse_json_body()
    definition = payload.get("definition")
    reg = get_registry()
    res = validate_definition(definition if isinstance(definition, dict) else {}, reg)
    return jsonify(
        {"valid": res.valid, "errors": res.errors, "normalized": res.normalized}
    ), 200


@bp.post("/contracts")
def create_contract():
    payload = _parse_json_body()
    definition = payload.get("definition")
    context = payload.get("context") or {}
    metadata = payload.get("metadata") or {}

    if not isinstance(context, dict):
        abort_json(400, "context must be object")
    if not isinstance(metadata, dict):
        abort_json(400, "metadata must be object")

    owner_id = get_auth_sub()

    reg = get_registry()
    res = validate_definition(definition if isinstance(definition, dict) else {}, reg)
    if not res.valid:
        return jsonify({"valid": False, "errors": res.errors, "normalized": {}}), 422

    idem_key = request.headers.get("Idempotency-Key")
    if idem_key:
        existing = mongo_find_one(
            _contracts_coll(), {"owner_id": owner_id, "idempotency_key": idem_key}
        )
        if existing:
            return jsonify(_serialize_contract(existing)), 200

    contract_id = str(uuid.uuid4())
    context["contractId"] = contract_id
    state = str(res.normalized.get("initialState") or "")
    status = "RUNNING"
    now = now_utc()

    state, on_enter_effects, context = _apply_on_enter(
        res.normalized,
        state,
        context=context,
        actor_id=str(owner_id),
        event_id=str(uuid.uuid4()),
    )
    if is_final_state(res.normalized, state):
        status = "DONE"

    doc = {
        "_id": contract_id,
        "owner_id": owner_id,
        "status": status,
        "state": state,
        "states": {},
        "version": 1,
        "context": context,
        "definition": res.normalized,
        "metadata": metadata,
        "created_at": now,
        "updated_at": now,
        "last_error": None,
    }
    if idem_key:
        doc["idempotency_key"] = idem_key
    mongo_insert_one(_contracts_coll(), doc)

    effect_ids: List[str] = []
    for ef in on_enter_effects:
        effect_id = str(uuid.uuid4())
        mongo_insert_one(
            _effects_coll(),
            {
                "_id": effect_id,
                "contract_id": contract_id,
                "effect_type": ef.get("type"),
                "payload": ef.get("payload") or {},
                "status": "PENDING",
                "attempts": 0,
                "last_error": None,
                "created_at": now_utc(),
                "updated_at": now_utc(),
            },
        )
        effect_ids.append(effect_id)

    _run_effects(contract_id, effect_ids)

    return jsonify(_serialize_contract(doc)), 201


@bp.get("/contracts/<contract_id>")
def get_contract(contract_id: str):
    doc = _get_contract(contract_id)
    if not doc:
        abort_json(404, "Contract not found")
    assert doc is not None
    doc_obj: Dict[str, Any] = cast(Dict[str, Any], doc)
    doc = cast(Dict[str, Any], doc)
    assert doc is not None
    doc = cast(Dict[str, Any], doc)
    return jsonify(_serialize_contract(doc)), 200


@bp.get("/contracts/<contract_id>/actions")
def get_contract_actions(contract_id: str):
    doc = _get_contract(contract_id)
    if not doc:
        abort_json(404, "Contract not found")
    assert doc is not None
    doc = cast(Dict[str, Any], doc)
    actor_id = get_current_sub()
    actor_state = _actor_state(doc, actor_id)
    return jsonify(
        {
            "id": doc.get("_id"),
            "state": doc.get("state"),
            "actorState": actor_state,
            "availableActionsGlobal": available_actions(
                doc.get("definition") or {}, str(doc.get("state") or "")
            ),
            "availableActionsActor": available_actions_actor(
                doc.get("definition") or {},
                str(doc.get("state") or ""),
                actor_state,
            ),
            "availableActions": available_actions_actor(
                doc.get("definition") or {},
                str(doc.get("state") or ""),
                actor_state,
            ),
        }
    ), 200


@bp.post("/contracts/<contract_id>/cancel")
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
    doc = cast(Dict[str, Any], doc)
    return jsonify(_serialize_contract(doc)), 200


@bp.post("/contracts/<contract_id>/<path:dyn_path>")
def post_contract_event(contract_id: str, dyn_path: str):
    payload = _parse_json_body()
    event_id = generate_event_id(payload.get("eventId"))
    actor_id = get_current_sub()
    body_payload = payload.get("payload") or {}

    if not isinstance(body_payload, dict):
        abort_json(400, "payload must be object")

    doc = _get_contract(contract_id)
    if not doc:
        abort_json(404, "Contract not found")

    result, status = _process_event(
        contract_id=contract_id,
        doc=doc,
        dyn_path=dyn_path,
        event_id=event_id,
        actor_id=actor_id,
        body_payload=body_payload,
        idem_key=request.headers.get("Idempotency-Key"),
        if_match=request.headers.get("If-Match"),
    )
    return jsonify(result), status


@bp.get("/contracts/<contract_id>/history")
def get_contract_history(contract_id: str):
    doc = _get_contract(contract_id)
    if not doc:
        abort_json(404, "Contract not found")
    doc_obj: Dict[str, Any] = cast(Dict[str, Any], doc)

    events = list(mongo_find(_events_coll(), {"contract_id": contract_id}))
    effects = list(mongo_find(_effects_coll(), {"contract_id": contract_id}))

    event_out = [
        {
            "eventId": e.get("event_id"),
            "path": e.get("path"),
            "event": e.get("event_name"),
            "actorId": e.get("actor_id"),
            "role": e.get("role"),
            "payloadHash": e.get("payload_hash"),
            "stateBefore": e.get("state_before"),
            "stateAfter": e.get("state_after"),
            "appliedAt": e.get("created_at").isoformat()
            if e.get("created_at")
            else None,
        }
        for e in events
    ]
    transitions = [
        {
            "from": e.get("state_before"),
            "to": e.get("state_after"),
            "reason": e.get("transition_reason"),
            "at": e.get("created_at").isoformat() if e.get("created_at") else None,
        }
        for e in events
        if e.get("state_before") != e.get("state_after")
    ]
    effects_out = [
        {
            "effectId": ef.get("_id"),
            "type": ef.get("effect_type"),
            "status": ef.get("status"),
            "attempts": ef.get("attempts"),
            "at": ef.get("updated_at").isoformat() if ef.get("updated_at") else None,
        }
        for ef in effects
    ]

    return jsonify(
        {
            "id": doc_obj.get("_id"),
            "events": event_out,
            "transitions": transitions,
            "effects": effects_out,
        }
    ), 200


@bp.get("/contracts/<contract_id>/effects")
def list_effects(contract_id: str):
    doc = _get_contract(contract_id)
    if not doc:
        abort_json(404, "Contract not found")
    effects = list(mongo_find(_effects_coll(), {"contract_id": contract_id}))
    return jsonify(
        {
            "id": contract_id,
            "effects": [
                {
                    "effectId": ef.get("_id"),
                    "type": ef.get("effect_type"),
                    "status": ef.get("status"),
                    "attempts": ef.get("attempts"),
                    "lastError": ef.get("last_error"),
                    "createdAt": ef.get("created_at").isoformat()
                    if ef.get("created_at")
                    else None,
                }
                for ef in effects
            ],
        }
    ), 200


@bp.post("/contracts/<contract_id>/retry")
def retry_effects(contract_id: str):
    doc = _get_contract(contract_id)
    if not doc:
        abort_json(404, "Contract not found")
    effects = list(
        mongo_find(_effects_coll(), {"contract_id": contract_id, "status": "ERROR"})
    )
    effect_ids = [ef.get("_id") for ef in effects]
    results = _run_effects(contract_id, effect_ids)
    return jsonify({"id": contract_id, "effects": results}), 200


@bp.get("/contracts/<contract_id>/timers")
def list_timers(contract_id: str):
    doc = _get_contract(contract_id)
    if not doc:
        abort_json(404, "Contract not found")
    timers = list(mongo_find(_timers_coll(), {"contract_id": contract_id}))
    return jsonify(
        {
            "id": contract_id,
            "timers": [
                {
                    "timerName": t.get("timer_name"),
                    "fireAt": t.get("fire_at").isoformat()
                    if t.get("fire_at")
                    else None,
                    "event": t.get("event_name"),
                    "status": t.get("status"),
                }
                for t in timers
            ],
        }
    ), 200


@bp.post("/contracts/<contract_id>/timers/<timer_name>/fire")
def fire_timer(contract_id: str, timer_name: str):
    doc = _get_contract(contract_id)
    if not doc:
        abort_json(404, "Contract not found")
    doc_obj: Dict[str, Any] = cast(Dict[str, Any], doc)
    timer = mongo_find_one(
        _timers_coll(), {"contract_id": contract_id, "timer_name": timer_name}
    )
    if not timer:
        abort_json(404, "Timer not found")
    timer_obj: Dict[str, Any] = cast(Dict[str, Any], timer)
    timer_path = timer_obj.get("path") or timer_obj.get("event_path")
    if not timer_path:
        abort_json(409, "Timer missing path")
    event_payload = timer_obj.get("payload") or {}
    mongo_update_one(
        _timers_coll(),
        {"_id": timer_obj.get("_id")},
        {"$set": {"status": "FIRED", "fired_at": now_utc()}},
    )
    result, status = _process_event(
        contract_id=contract_id,
        doc=doc_obj,
        dyn_path=str(timer_path),
        event_id=str(uuid.uuid4()),
        actor_id="system",
        body_payload=event_payload if isinstance(event_payload, dict) else {},
        idem_key=None,
        if_match=None,
    )
    return jsonify({"timerName": timer_name, "event": result}), status
