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
    mongo_find,
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
    elif ef_type == "if.else":
        condition = ef.get("condition")
        then_effects = ef.get("then_effects") or []
        else_effects = ef.get("else_effects") or []
        if not isinstance(then_effects, list):
            abort_json(400, "if.else requires then_effects array")
        if not isinstance(else_effects, list):
            abort_json(400, "if.else else_effects must be array")
        selected = then_effects if bool(condition) else else_effects
        any_changed = False
        for child in selected:
            if not isinstance(child, dict):
                abort_json(400, "if.else effects must be objects")
            changed, doc = _apply_effect_step(
                doc=doc,
                ef=child,
                actor_id=actor_id,
                payload=payload,
                local=local,
            )
            any_changed = any_changed or changed
        return any_changed, doc
    elif ef_type == "schedule.event":
        now = now_utc()
        contract_id = str(doc.get("_id") or "")
        key = str(ef.get("key") or "").strip()
        event_id = str(uuid.uuid4())
        event_name = str(ef.get("event_name") or "").strip()
        cron = str(ef.get("cron") or "").strip()
        if not key:
            abort_json(400, "schedule.event requires non-empty key")
        if not event_name:
            abort_json(400, "schedule.event requires non-empty event_name")
        if not cron:
            abort_json(400, "schedule.event requires non-empty cron")
        schedule_doc: Dict[str, Any] = {"event_name": event_name, "cron": cron}
        if "payload" in ef:
            schedule_doc["payload"] = ef.get("payload")
        if "actor_id" in ef and ef.get("actor_id") is not None:
            schedule_doc["actor_id"] = str(ef.get("actor_id"))
        mongo_update_one(
            _contracts_coll(),
            {"_id": contract_id},
            {
                "$set": {
                    f"scheduled_events.{event_id}": schedule_doc,
                    "updated_by": actor_id,
                    "updated_at": now,
                }
            },
        )
        local[key] = event_id
        doc = _get_contract(contract_id)
    elif ef_type == "unschedule.event":
        now = now_utc()
        contract_id = str(doc.get("_id") or "")
        event_id = str(ef.get("event_id") or "").strip()
        if not event_id:
            abort_json(400, "unschedule.event requires non-empty event_id")
        mongo_update_one(
            _contracts_coll(),
            {"_id": contract_id},
            {
                "$set": {
                    "updated_by": actor_id,
                    "updated_at": now,
                },
                "$unset": {
                    f"scheduled_events.{event_id}": "",
                    f"scheduled_runtime.{event_id}": "",
                },
            },
        )
        doc = _get_contract(contract_id)
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
        mongo_delete_one(coll, {"_id": ef["item_id"]})
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
            doc, f"definition.states.{doc.get('state')}.on_enter.effects", []
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

    selected_edef: Optional[Dict[str, Any]] = None
    selected_trigger: Optional[Dict[str, Any]] = None
    for _, candidate in sorted(events.items()):
        trigger = candidate.get("trigger")
        for t in trigger:
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
        return {"error": "Invalid payload", "details": schema_errors}, 422, doc

    local = {}
    for ef in edef.get("effects") or []:
        changed, doc = _apply_effect_step(
            doc=doc, ef=ef, payload=body_payload, actor_id=actor_id, local=local
        )
        if changed:
            break
    doc = _close_contract(doc)
    if resolve_response:
        ctx = {"local": local, "doc": doc, "user": actor_id, "payload": body_payload}
        return resolver(_src_get("response") or {"ok": True}, ctx), 200
    return {"ok": True}, 200


def _match_cron_field(field: str, value: int) -> bool:
    if field == "*":
        return True
    for part in field.split(","):
        part = part.strip()
        if not part:
            continue
        if part.startswith("*/"):
            step = int(part[2:])
            if step > 0 and value % step == 0:
                return True
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            if int(a) <= value <= int(b):
                return True
            continue
        if int(part) == value:
            return True
    return False


def _is_cron_due(expr: str, now_dt) -> bool:
    parts = expr.split()
    if len(parts) != 5:
        return False
    minute, hour, day, month, weekday = parts
    cron_weekday = (now_dt.weekday() + 1) % 7
    return (
            _match_cron_field(minute, now_dt.minute)
            and _match_cron_field(hour, now_dt.hour)
            and _match_cron_field(day, now_dt.day)
            and _match_cron_field(month, now_dt.month)
            and _match_cron_field(weekday, cron_weekday)
    )


def run_cron_triggers_tick(*, actor_id: str = "system:cron") -> Dict[str, Any]:
    now_dt = now_utc()
    minute_key = now_dt.strftime("%Y%m%d%H%M")
    fired = 0
    skipped = 0
    errors = 0
    error_messages: List[str] = []

    for doc in mongo_find(_contracts_coll(), {"status": "RUNNING"}):
        scheduled_events = doc.get("scheduled_events") or {}
        if isinstance(scheduled_events, dict):
            for sid, spec in scheduled_events.items():
                if not isinstance(spec, dict):
                    skipped += 1
                    continue
                expr = spec.get("cron")
                event_name = spec.get("event_name")
                if not isinstance(expr, str) or not expr.strip():
                    skipped += 1
                    continue
                if not isinstance(event_name, str) or not event_name.strip():
                    skipped += 1
                    continue
                fired_path = f"scheduled_runtime.{sid}.last_fired_minute"
                if pydash.get(doc, fired_path) == minute_key:
                    skipped += 1
                    continue
                if not _is_cron_due(expr, now_dt):
                    skipped += 1
                    continue
                try:
                    state = str(doc.get("state") or "")
                    events = (
                            pydash.get(doc, f"definition.states.{state}.events", {}) or {}
                    )
                    edef = events.get(event_name)
                    if not isinstance(edef, dict):
                        skipped += 1
                        continue
                    _process_selected_event(
                        doc=doc,
                        edef=edef,
                        selected_trigger={},
                        actor_id=str(spec.get("actor_id") or actor_id),
                        body_payload=spec.get("payload")
                        if isinstance(spec.get("payload"), dict)
                        else {},
                        resolve_response=False,
                    )
                    mongo_update_one(
                        _contracts_coll(),
                        {"_id": doc.get("_id")},
                        {"$set": {fired_path: minute_key}},
                    )
                    fired += 1
                except Exception as exc:
                    errors += 1
                    if len(error_messages) < 5:
                        error_messages.append(str(exc))

    return {
        "ok": True,
        "fired": fired,
        "skipped": skipped,
        "errors": errors,
        "error_messages": error_messages,
        "at": now_dt.isoformat(),
    }


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
