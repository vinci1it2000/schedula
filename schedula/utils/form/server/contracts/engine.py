# coding=utf-8
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2026, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');

"""Contract workflow engine and validation helpers."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any, Dict, List, Optional, Tuple

import pydash
import requests
from jsonschema import Draft202012Validator
from sqlalchemy_dlock import create_sadlock

from ..extensions import db
from ..security.casbin import (
    get_enforcer,
    acl_user,
    g,
    u2id,
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
    raw_ef = ef
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
        contract_id = doc["_id"]
        update = [ef["update"]] if isinstance(ef["update"], dict) else ef["update"]
        mongo_update_one(
            _contracts_coll(),
            {"_id": contract_id},
            [
                {"$set": {"local": local, "updated_by": actor_id}},
                *update,
                {"$set": {"updated_at": now}},
            ],
            let={"user": actor_id, "payload": payload, "local": local},
        )
        doc = _get_contract(contract_id)
        local.update(doc.get("local") or {})
    elif ef_type in {
        "use.credits",
        "charge.credits",
        "transfer_to.credits",
        "balance.credits",
    }:
        from ..credits import Wallet, get_wallet

        if "wallet_id" in ef:
            wallet = db.session.get(Wallet, int(ef["wallet_id"]))
        else:
            wallet = get_wallet(u2id(ef["user_id"]))

        product = ef["product"]

        if ef_type == "balance.credits":
            local[ef["key"]] = wallet.balance(product=product, session=db.session)
        elif ef_type == "use.credits":
            wallet.use(product=product, credits=ef["credits"])
        elif ef_type == "charge.credits":
            wallet.charge(product=product, credits=ef["credits"])
        else:  # transfer_to.credits
            if "to_wallet_id" in ef:
                to_wallet = db.session.get(Wallet, int(ef["to_wallet_id"]))
            else:
                to_wallet = get_wallet(u2id(ef["to_user_id"]))
            wallet.transfer_to(
                product=product,
                credits=ef["credits"],
                to_wallet=to_wallet.id,
            )
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
    elif ef_type == "if.else":
        condition = ef.get("condition")
        then_effects = raw_ef.get("then_effects") or []
        else_effects = raw_ef.get("else_effects") or []
        if not isinstance(then_effects, list):
            abort_json(400, "if.else requires then_effects array")
        if not isinstance(else_effects, list):
            abort_json(400, "if.else else_effects must be array")
        selected = then_effects if bool(condition) else else_effects
        return _apply_effects(
            {"effects": selected},
            doc,
            actor_id,
            payload=payload,
            local=local,
            validate_schema=False,
        )
    elif ef_type == "schedule.event_at":
        contract_id = str(doc.get("_id") or "")
        key = str(ef.get("key") or "").strip()
        at = ef.get("at")
        if isinstance(at, str):
            at = dt.datetime.fromisoformat(at)
        if not isinstance(at, dt.datetime):
            abort_json(400, "schedule.event_at requires datetime 'at'")
        job: Dict[str, Any] = {
            "contract_id": contract_id,
            "event_name": ef.get("event_name"),
            "payload": ef.get("payload") or {},
            "actor_id": ef.get("actor_id", actor_id),
        }
        from .schedule import schedule_event_at

        local[key] = schedule_event_at(at, job)
    elif ef_type == "schedule.event_cron":
        contract_id = str(doc.get("_id") or "")
        key = str(ef.get("key") or "").strip()
        cron = str(ef.get("cron") or "").strip()
        if not cron:
            abort_json(400, "schedule.event_cron requires non-empty cron")
        job: Dict[str, Any] = {
            "contract_id": contract_id,
            "event_name": ef.get("event_name"),
            "payload": ef.get("payload") or {},
            "actor_id": ef.get("actor_id", actor_id),
        }
        from .schedule import schedule_event_cron

        local[key] = schedule_event_cron(cron, job)
    elif ef_type == "unschedule.event_at":
        event_id = str(ef.get("event_id") or "").strip()
        if not event_id:
            abort_json(400, "unschedule.event requires non-empty event_id")
        from .schedule import unschedule_event

        unschedule_event(event_id)
    elif ef_type == "unschedule.event_cron":
        event_id = str(ef.get("event_id") or "").strip()
        if not event_id:
            abort_json(400, "unschedule.event_cron requires non-empty event_id")
        from .schedule import unschedule_event

        unschedule_event(event_id)
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
        update = [ef["update"]] if isinstance(ef["update"], dict) else ef["update"]
        res = mongo_update_one(
            coll,
            {"_id": item_id},
            [
                {"$set": {"updated_by": actor_id}},
                *update,
                {"$set": {"updated_at": now}},
            ],
            let={
                "user": actor_id,
                "payload": payload,
                "local": local,
            },
        )
        if res.matched_count != 1:
            abort_json(404, "Item not found")
    elif ef_type == "delete.item":
        coll = get_mongo(collection=config_get("ITEMS_COLLECTION", "items"))
        mongo_delete_one(coll, {"_id": ef["item_id"]})
    else:
        abort_json(400, f"Unknown effect type: {ef_type}")

    if doc.get("state") != initial_state:
        return True, _apply_on_enter(
            doc=doc,
            actor_id=actor_id,
            prev_state=initial_state,
            local=local,
            payload=payload,
        )
    return False, doc


def _close_contract(doc):
    if pydash.get(doc, f"definition.states.{doc.get('state')}.final", False):
        mongo_update_one(
            _contracts_coll(),
            {"_id": doc.get("_id")},
            {"$set": {"status": "DONE"}, "$unset": {"local": ""}},
        )
        return pydash.merge(doc, {"status": "DONE"})
    return doc


def validate_context_schema(doc, state):
    if "context_schema" in state:
        from .routes import _validate_schema

        schema_errors = _validate_schema(doc["context"], state["context_schema"])
        if schema_errors:
            abort_json(422, "Invalid context schema")


def _apply_effects(
    state, doc, actor_id, payload=None, local=None, validate_schema=True
):
    for ef in state.get("effects", []):
        changed, doc = _apply_effect_step(
            doc=doc, ef=ef, payload=payload, actor_id=actor_id, local=local
        )
        if changed:
            doc = _close_contract(doc)
            return changed, doc
    if validate_schema:
        validate_context_schema(doc, state)
    return False, doc


def _apply_on_enter(
    *,
    doc: dict[str, Any],
    actor_id: str,
    prev_state=None,
    payload=None,
    local=None,
) -> dict[str, Any]:
    if payload is None:
        payload = {}
    if local is None:
        local = {}

    if prev_state:
        on_exit = pydash.get(doc, f"definition.states.{doc.get('state')}.on_exit", {})
        changed, doc = _apply_effects(
            on_exit, doc, actor_id=actor_id, payload=payload, local=local
        )
        if changed:
            return doc
        validate_context_schema(doc, on_exit)

    on_enter = pydash.get(doc, f"definition.states.{doc.get('state')}.on_enter", {})
    validate_context_schema(doc, on_enter)
    _, doc = _apply_effects(on_enter, doc, actor_id, local=local)
    return doc


def _process_event(
    *,
    contract_id: str,
    dyn_path: str,
    actor_id: str,
    body_payload: Dict[str, Any],
) -> Tuple[Dict[str, Any], int]:
    with create_sadlock(db.session, contract_id):
        doc = _get_contract(contract_id)
        if not doc:
            abort_json(404, "Contract not found")

        if doc.get("status") in ("DONE", "CANCELED"):
            abort_json(410, "Contract not accepting events")

        state = str(doc.get("state") or "")
        events = dict(pydash.get(doc, f"definition.events", {}))
        events.update(pydash.get(doc, f"definition.states.{state}.events", {}))

        selected_edef: Optional[Dict[str, Any]] = None
        selected_trigger: Optional[Dict[str, Any]] = None
        for _, candidate in sorted(events.items()):
            if "trigger" in candidate:
                for t in candidate["trigger"]:
                    if str(t.get("type") or "") != "api":
                        continue
                    path = t.get("path")
                    if isinstance(path, str) and path == dyn_path:
                        selected_edef = candidate
                        selected_trigger = t
                        break
                if selected_edef is not None:
                    break
        if selected_edef is None or selected_trigger is None:
            abort_json(409, "Event not available in this state")
        return _process_selected_event(
            doc=doc,
            edef=selected_edef,
            selected_trigger=selected_trigger,
            actor_id=actor_id,
            body_payload=body_payload,
        )


def _run_event(edef, doc, actor_id, payload):
    local = {}
    changed, doc = _apply_effects(edef, doc, actor_id, payload=payload, local=local)
    doc = _close_contract(doc)
    return changed, doc, local


def _process_selected_event(
    *,
    doc: Dict[str, Any],
    edef: Dict[str, Any],
    selected_trigger: Dict[str, Any],
    actor_id: str,
    body_payload: Dict[str, Any],
    resolve_response: bool = True,
) -> Tuple[Dict[str, Any], int]:
    def _src_get(key: str) -> Any:
        if key in selected_trigger:
            return selected_trigger.get(key)
        return edef.get(key)

    actor_state_before = pydash.get(doc, f"states.{actor_id}")
    resolver = RefResolver(enforce_acl=False)
    ctx = {"doc": doc, "user": actor_id, "payload": body_payload}
    if (
        _src_get("allow_user_states") is not None
        and actor_state_before
        not in set(resolver(_src_get("allow_user_states"), ctx) or [])
    ) or (
        _src_get("deny_user_states") is not None
        and actor_state_before in set(resolver(_src_get("deny_user_states"), ctx) or [])
    ):
        abort_json(409, "Event not available for actor state")

    if (
        _src_get("allow_principals") is not None
        or _src_get("deny_principals") is not None
    ):
        enforcer = get_enforcer()
        roles = set(enforcer.get_roles_for_user(actor_id))
        roles.add(actor_id)
        if _src_get("allow_principals") is not None and not roles.intersection(
            set(resolver(_src_get("allow_principals"), ctx) or [])
        ):
            abort_json(403, "Subject not allowed")
        if _src_get("deny_principals") is not None and roles.intersection(
            set(resolver(_src_get("deny_principals"), ctx) or [])
        ):
            abort_json(403, "Subject denied")

    schema_errors = validate_payload(_src_get("payload_schema"), body_payload)
    if schema_errors:
        return {"error": "Invalid payload", "details": schema_errors}, 422

    changed, doc, local = _run_event(edef, doc, actor_id, body_payload)

    if resolve_response:
        ctx = {"local": local, "doc": doc, "user": actor_id, "payload": body_payload}
        return resolver(_src_get("response") or {"ok": True}, ctx), 200
    return {"ok": True}, 200


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

    doc = {
        "_id": contract_id,
        "status": "RUNNING",
        "state": state,
        "states": {},
        "context": context,
        "definition": definition,
        "metadata": template.get("metadata") or {},
        "scheduled_events": {},
        "created_by": owner_id,
        "created_at": now,
        "updated_at": now,
        "template_id": template_id,
    }
    mongo_insert_one(_contracts_coll(), doc)

    return _apply_on_enter(doc=_get_contract(contract_id), actor_id=str(owner_id))
