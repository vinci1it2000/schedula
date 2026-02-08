# coding=utf-8
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2026, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');

"""Contract workflow engine and validation helpers."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional, Tuple

import pydash
import requests
from jsonschema import Draft202012Validator

from ..security.casbin import (
    get_enforcer,
)
from ..utils import (
    RefResolver,
    abort_json,
    config_get,
    get_mongo,
    mongo_find_one,
    mongo_insert_one,
    mongo_update_one,
    now_utc,
)


def _contracts_coll():
    return get_mongo(collection=config_get("CONTRACTS_COLLECTION", "contracts"))


def _templates_coll():
    return get_mongo(
        collection=config_get("CONTRACT_TEMPLATES_COLLECTION", "contract_templates")
    )


def _get_contract(contract_id: str) -> Optional[Dict[str, Any]]:
    return mongo_find_one(_contracts_coll(), {"_id": contract_id})


def validate_payload(
        payload_schema: Optional[Dict[str, Any]], payload: Any
) -> List[str]:
    if payload_schema is None:
        return []
    try:
        v = Draft202012Validator(payload_schema)
        return [e.message for e in v.iter_errors(payload)]
    except Exception as e:
        return [str(e)]


def find_event_by_path(
        definition: Dict[str, Any], state: str, path: str
) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    st = (definition.get("states") or {}).get(state) or {}
    events = st.get("events") or {}
    for ename, edef in events.items():
        if edef.get("path") == path:
            return ename, edef
    return None, None


def _apply_effect_step(
        *,
        doc: Dict[str, Any],
        ef: Dict[str, Any],
        actor_id: str,
        payload: Dict[str, Any] = None,
) -> tuple[bool, Dict[str, Any]]:
    ef_type = str(ef.get("type") or "")
    contract_id = str(doc.get("_id") or "")
    responses = {}
    payload = payload or {}
    resolver = RefResolver(enforce_acl=False)
    initial_state = doc.get("state")
    if ef_type in ("update.context", "update.state", "update.states"):
        what = ef_type.split(".")[1]
        mongo_update_one(
            _contracts_coll(),
            {"_id": contract_id},
            [{"$set": {
                f"{what}": {
                    "$mergeObjects": [
                        f"${what}",
                        resolver(ef["update"], doc)
                    ]
                },
                "updated_at": "$$NOW"
            }}],
            let={
                "doc": doc,
                "user": actor_id,
                "payload": payload,
                "responses": responses
            },
        )
        doc = _get_contract(contract_id)
    elif ef_type == "http.request":
        request_kw = {"method": "GET"}
        request_kw.update(resolver(ef.get("request"), doc) or {})
        responses[ef["key"]] = requests.request(**request_kw).json()
    elif ef_type == "notify":
        from ..notifications.service import create_notification
        notify_kw = {
            "event": "",
            "created_by": actor_id,
            "sender_principal": actor_id,
        }
        create_notification(**notify_kw)
    elif ef_type == "update.item":
        pass  # TODO: implement update.item effects
    else:
        abort_json(400, f"Unknown effect type: {ef_type}")

    if doc.get("state") != initial_state:
        return True, _apply_on_enter(doc=doc, actor_id=actor_id)
    return False, doc


def _close_contract(doc):
    if pydash.get(doc, f"definition.states.{doc.get('state')}.final", False):
        mongo_update_one(_contracts_coll(), {"_id": doc.get('_id')}, {"$set": {"status": "DONE"}})
        return pydash.merge(doc, {"status": "DONE"})
    return doc


def _apply_on_enter(
        *,
        doc: dict[str, Any],
        actor_id: str,
) -> dict[str, Any]:
    for ef in pydash.get(doc, f"definition.states.{doc.get('state')}.onEnter.effects", []):
        changed, doc = _apply_effect_step(doc=doc, ef=ef, actor_id=actor_id)
        if changed:
            return doc
    return doc


def _process_event(
        *,
        doc: Dict[str, Any],
        dyn_path: str,
        actor_id: str,
        body_payload: Dict[str, Any],
) -> Tuple[Dict[str, Any], int]:
    if doc.get("status") in ("DONE", "CANCELED"):
        abort_json(410, "Contract not accepting events")

    state = str(doc.get("state") or "")
    ename, edef = find_event_by_path(doc.get("definition") or {}, state, dyn_path)
    if not edef:
        abort_json(409, "Event not available in this state")
    actor_state_before = pydash.get(doc, f"states.{actor_id}")
    resolver = RefResolver(enforce_acl=False)
    if (
            "allowUserStates" in edef
            and actor_state_before not in set(resolver(edef.get("allowUserStates"), doc) or [])
    ) or (
            "denyUserStates" in edef
            and actor_state_before in set(resolver(edef.get("denyUserStates"), doc) or [])
    ):
        abort_json(409, "Event not available for actor state")

    if "allowPrincipals" in edef or "denyPrincipals" in edef:
        enforcer = get_enforcer()
        roles = set(enforcer.get_roles_for_user(actor_id))
        roles.add(actor_id)
        if "allowPrincipals" in edef and not roles.intersection(
                set(resolver(edef.get("allowPrincipals"), doc) or [])
        ):
            abort_json(403, "Subject not allowed")
        if "denyPrincipals" in edef and roles.intersection(
                set(resolver(edef.get("denyPrincipals"), doc) or [])
        ):
            abort_json(403, "Subject denied")

    schema_errors = validate_payload(edef.get("payloadSchema"), body_payload)
    if schema_errors:
        return {"error": "Invalid payload", "details": schema_errors}, 422

    for ef in edef.get("effects") or []:
        changed, doc = _apply_effect_step(doc=doc, ef=ef, payload=body_payload, actor_id=actor_id)
        if changed:
            break
    doc = _close_contract(doc)
    return resolver(edef.get("response") or {"ok": True}, doc), 200


def _create_contract_from_template_doc(
        *,
        template: Dict[str, Any],
        template_id: str,
        context: Dict[str, Any],
        owner_id: str,
        initial_state: Optional[str] = None,
) -> Dict[str, Any]:
    if not bool(template.get("is_enabled", False)):
        abort_json(409, "Template disabled")

    definition = template["definition"]

    contract_id = str(uuid.uuid4())
    context["contract_id"] = contract_id
    default_initial_state = str(definition.get("initial_state") or "")
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

    return _apply_on_enter(doc=_get_contract(contract_id), actor_id=str(owner_id))
