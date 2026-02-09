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

from ..extensions import db
from ..security.casbin import (
    get_enforcer,
    acl_user,
    g,
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
    mongo_delete_one,
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


def _apply_effect_step(
        *,
        doc: Dict[str, Any],
        ef: Dict[str, Any],
        actor_id: str,
        payload: Dict[str, Any] = None,
        local: Dict[str, Any] = None,
) -> tuple[bool, Dict[str, Any]]:
    ef_type = str(ef.get("type") or "")
    if local is None:
        local = {}
    payload = payload or {}
    ctx = {
        "doc": doc,
        "user": actor_id,
        "payload": payload,
        "local": local,
    }
    initial_state = doc.get("state")
    ef = RefResolver(enforce_acl=False)(ef, ctx)

    if ef_type == "update.contract":
        now = now_utc()
        contract_id = str(doc.get("_id") or "")
        mongo_update_one(
            _contracts_coll(),
            {"_id": contract_id},
            [
                {"$set": {"updated_by": actor_id}},
                ef["update"],
                {"$set": {"updated_at": now}},
            ],
            let=ctx,
        )
        doc = _get_contract(contract_id)
    elif ef_type == "http.request":
        request_kw = {"method": "GET"}
        request_kw.update(ef["request"] or {})
        local[ef["key"]] = requests.request(**request_kw).json()
    elif ef_type == "notify":
        from ..notifications.service import create_notification
        notify_kw = {
            "created_by": actor_id,
            "sender_principal": actor_id,
        }
        notify_kw.update(ef["notify"] or {})
        create_notification(**notify_kw)
    elif ef_type == "create.group":
        from ..security.groups import Group
        from ..security.casbin import bootstrap_group
        name = ef.get("name")
        gtype = ef.get("group_type", "workspace")
        sub = ef.get("sub")
        if not isinstance(name, str) or not name.strip():
            abort_json(400, "create.group requires non-empty name")
        grp = Group(name=name.strip(), type=str(gtype or "workspace"))
        db.session.add(grp)
        db.session.flush()
        bootstrap_group(grp.id, str(sub or actor_id))
        db.session.commit()
        local[ef["key"]] = g(grp.id)
    elif ef_type == "update.group":
        from ..security.groups import Group
        group_id = str(ef.get("group_id") or "")
        if group_id.startswith("g:"):
            group_id = group_id[2:]
        grp = db.session.get(Group, group_id)
        if not grp:
            abort_json(404, "Group not found")

        if "name" in ef:
            grp.name = ef["name"]
        if "group_type" in ef:
            grp.type = ef["group_type"]

        edit_members = ef.get("edit_members")
        if edit_members is not None:
            if not isinstance(edit_members, dict):
                abort_json(400, "edit_members must be object")

            def _parse_subject(principal: Any) -> Tuple[str, str]:
                if not isinstance(principal, str) or ":" not in principal:
                    abort_json(400, f"invalid principal '{principal}'")
                t, sid = principal.split(":", 1)
                if t == "u":
                    return "user", sid
                if t == "g":
                    return "group", sid
                abort_json(400, f"invalid principal '{principal}'")

            def _iter_ops(key: str) -> List[Tuple[str, str]]:
                values = edit_members.get(key) or []
                if not isinstance(values, list):
                    abort_json(400, f"edit_members.{key} must be list")
                return [_parse_subject(v) for v in values]

            for t, sid in _iter_ops("add_members"):
                grp.add_member(sid, subject_type=t)
            for t, sid in _iter_ops("promote_admins"):
                grp.promote_admin(sid, subject_type=t)
            for t, sid in _iter_ops("demote_admins"):
                grp.demote_admin(sid, subject_type=t)
            for t, sid in _iter_ops("remove_members"):
                grp.remove_member(sid, subject_type=t)
            for t, sid in _iter_ops("ban_members"):
                grp.ban_member(sid, subject_type=t)
            for t, sid in _iter_ops("unban_members"):
                grp.unban_member(sid, subject_type=t)
        db.session.commit()
    elif ef_type == "create.item":
        coll = get_mongo(collection=config_get("ITEMS_COLLECTION", "items"))
        now = now_utc()
        item = {
            "data": {},
            "files": {},
            "acl_dom": acl_user(actor_id),
            "created_by": actor_id,
            "updated_by": actor_id,
            "created_at": now,
            "updated_at": now,
        }
        item.update(ef["item"] or {})
        res = mongo_insert_one(coll, item)
        local[ef["key"]] = res.inserted_id
    elif ef_type == "update.item":
        coll = get_mongo(collection=config_get("ITEMS_COLLECTION", "items"))
        now = now_utc()
        item_id = ef["item_id"]
        res = mongo_update_one(
            coll,
            {"_id": item_id},
            [
                {"$set": {"updated_by": actor_id}},
                ef["update"],
                {"$set": {"updated_at": now}},
            ],
            let=ctx,
        )
        if res.matched_count != 1:
            abort_json(404, "Item not found")
    elif ef_type == "delete.item":
        coll = get_mongo(collection=config_get("ITEMS_COLLECTION", "items"))
        mongo_delete_one(coll,{"_id": ef["item_id"]})
    else:
        abort_json(400, f"Unknown effect type: {ef_type}")

    if doc.get("state") != initial_state:
        return True, _apply_on_enter(doc=doc, actor_id=actor_id)
    return False, doc


def _close_contract(doc):
    if pydash.get(doc, f"definition.states.{doc.get('state')}.final", False):
        mongo_update_one(
            _contracts_coll(), {"_id": doc.get("_id")}, {"$set": {"status": "DONE"}}
        )
        return pydash.merge(doc, {"status": "DONE"})
    return doc


def _apply_on_enter(
        *,
        doc: dict[str, Any],
        actor_id: str,
) -> dict[str, Any]:
    local = {}
    for ef in pydash.get(
            doc, f"definition.states.{doc.get('state')}.onEnter.effects", []
    ):
        changed, doc = _apply_effect_step(
            doc=doc, ef=ef, actor_id=actor_id, local=local
        )
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
    events = pydash.get(doc, f"definition.states.{state}.events", {})
    for ename, edef in events.items():
        if edef.get("path") == dyn_path:
            break
    else:
        abort_json(409, "Event not available in this state")
    actor_state_before = pydash.get(doc, f"states.{actor_id}")
    resolver = RefResolver(enforce_acl=False)
    if (
            "allow_user_states" in edef
            and actor_state_before
            not in set(resolver(edef.get("allow_user_states"), doc) or [])
    ) or (
            "deny_user_states" in edef
            and actor_state_before in set(resolver(edef.get("deny_user_states"), doc) or [])
    ):
        abort_json(409, "Event not available for actor state")

    if "allow_principals" in edef or "deny_principals" in edef:
        enforcer = get_enforcer()
        roles = set(enforcer.get_roles_for_user(actor_id))
        roles.add(actor_id)
        if "allow_principals" in edef and not roles.intersection(
                set(resolver(edef.get("allow_principals"), doc) or [])
        ):
            abort_json(403, "Subject not allowed")
        if "deny_principals" in edef and roles.intersection(
                set(resolver(edef.get("deny_principals"), doc) or [])
        ):
            abort_json(403, "Subject denied")

    schema_errors = validate_payload(edef.get("payload_schema"), body_payload)
    if schema_errors:
        return {"error": "Invalid payload", "details": schema_errors}, 422
    local = {}
    for ef in edef.get("effects") or []:
        changed, doc = _apply_effect_step(
            doc=doc, ef=ef, payload=body_payload, actor_id=actor_id, local=local
        )
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
