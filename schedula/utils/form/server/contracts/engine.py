# coding=utf-8
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2026, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');

"""Contract workflow engine and validation helpers."""

from __future__ import annotations

import datetime as dt
import uuid
from contextvars import ContextVar
from typing import Any, Dict, List, Optional, Tuple

import pydash
import requests
from pymongo import ReturnDocument
from sherlock import Lock

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
    mongo_find,
    mongo_insert_one,
    mongo_update_one,
    mongo_find_one_and_update,
    now_utc,
    mongo_delete_one,
    mongo_delete_many,
    validate_payload
)

_contracts_collection = ContextVar("contracts_collection", default=None)

_templates_collection = ContextVar("contract_templates_collection", default=None)


def _contracts_coll():
    collection = _contracts_collection.get()
    if collection is None:
        collection = config_get("CONTRACTS_COLLECTION", "contracts")
    return get_mongo(collection=collection)


def _templates_coll():
    collection = _templates_collection.get()
    if collection is None:
        collection = config_get("CONTRACT_TEMPLATES_COLLECTION", "contract_templates")
    return get_mongo(collection=collection)


REGISTERED_FUNCTIONS: Dict[str, Any] = {}


def register_function(name: str, func: Any):
    REGISTERED_FUNCTIONS[name] = func


def _get_contract(contract_id: str, **kwargs) -> Optional[Dict[str, Any]]:
    return mongo_find_one(_contracts_coll(), {"_id": contract_id, **kwargs})


def _get_wallet(wallet_id, user_id):
    from ..credits import Wallet, get_wallet

    if wallet_id:
        return db.session.get(Wallet, int(wallet_id))
    return get_wallet(u2id(user_id))


def _yield_wallets(ef, actor_id):
    if "credits" in ef:
        items = ef["credits"]
    else:
        items = {ef.get("key"): ef["credit"]}
    for k, v in items.items():
        if "wallet_id" in v:
            wallet = _get_wallet(v["wallet_id"], None)
        else:
            wallet = _get_wallet(None, v.get("user_id", actor_id))

        yield k, v, wallet


def _safe_local(obj):
    """
    Recursively wraps values of keys starting with '$'
    inside {"$literal": value}.
    """

    if isinstance(obj, dict):
        new_obj = {}

        for k, v in obj.items():
            if k.startswith("$"):
                # wrap the entire sub-object in $literal
                return {"$literal": obj}
            else:
                new_obj[k] = _safe_local(v)

        return new_obj

    elif isinstance(obj, list):
        return [_safe_local(i) for i in obj]

    return obj


def _apply_effect_step(
        *,
        doc: Dict[str, Any],
        definition: Dict[str, Any],
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
        if "update" in ef:
            updates = {contract_id: ef["update"]}
        else:
            updates = ef["updates"] or {}
        sft_local = _safe_local(local)

        find_one_and_update_opts = {"return_document": ReturnDocument.AFTER}
        if ef.get("projection"):
            find_one_and_update_opts["projection"] = ef["projection"]
        docs = {}
        for k, update in updates.items():
            update = [update] if isinstance(update, dict) else update
            docs[k] = mongo_find_one_and_update(
                _contracts_coll(),
                {"_id": k},
                [
                    {"$set": {"local": sft_local, "updated_by": actor_id}},
                    *update,
                    {"$set": {"updated_at": now}},
                ],
                **find_one_and_update_opts,
                let={"user": actor_id, "payload": payload, "local": sft_local},
            )
        if contract_id in updates:
            doc = _get_contract(contract_id)
            local.update(doc.get("local") or {})
        if "key" in ef:
            if "update" in ef:
                docs = docs[contract_id]
            local[ef["key"]] = docs
    elif ef_type == "delete.contract":
        contract_id = doc["_id"]
        mongo_delete_one(_contracts_coll(), {"_id": contract_id})
        return True, doc
    elif ef_type == "balance.credits":
        for k, v, wallet in _yield_wallets(ef, actor_id):
            local[k] = wallet.balance(product=v["product"], session=db.session)
    elif ef_type == "use.credits":
        for _, v, wallet in _yield_wallets(ef, actor_id):
            wallet.use(product=v["product"], credits=v["amount"], session=db.session)
    elif ef_type == "charge.credits":
        for _, v, wallet in _yield_wallets(ef, actor_id):
            wallet.charge(product=v["product"], credits=v["amount"], session=db.session)
    elif ef_type == "transfers.credits":
        for _, v, wallet in _yield_wallets(ef, actor_id):
            if "to_wallet_id" in v:
                to_wallet = _get_wallet(v["to_wallet_id"], None)
            else:
                to_wallet = _get_wallet(None, ef["to_user_id"])
            wallet.transfer_to(
                product=v["product"],
                credits=v["amount"],
                to_wallet=to_wallet.id,
                session=db.session,
            )
    elif ef_type == "http.request":
        if "requests" in ef:
            rqs = ef["requests"]
        else:
            rqs = {ef["key"]: ef["request"]}
        for k, rq in rqs.items():
            request_kw = {"method": "GET"}
            request_kw.update(rq or {})
            local[k] = requests.request(**request_kw).json()
    elif ef_type == "notify":
        from ..notifications.service import create_notification

        notify_kw = {
            "created_by": actor_id,
            "sender_principal": actor_id,
        }
        notify_kw.update(ef["notify"] or {})
        if notify_kw["targets"]:
            create_notification(**notify_kw)
    elif ef_type == "if.else":
        condition = ef.get("condition")
        then_effects = raw_ef.get("then_effects") or []
        else_effects = raw_ef.get("else_effects") or []
        selected = then_effects if bool(condition) else else_effects
        return _apply_effects(
            {"effects": selected},
            doc,
            definition,
            actor_id,
            payload=payload,
            local=local,
            validate_schema=False,
        )
    elif ef_type == "execute.event":
        contract_id = doc["_id"]
        event = ef["event_name"]
        if ef.get("contract_id", contract_id) != contract_id:
            _process_event(
                contract_id=ef["contract_id"], dyn_path="", actor_id=actor_id, body_payload=payload, event_name=event
            )
        else:
            events = dict(pydash.get(definition, f"events", {}))
            events.update(pydash.get(definition, f"states.{ef.get('state', initial_state)}.events", {}))
            if event in events:
                return _apply_effects(
                    events[event], doc, definition, actor_id, payload=payload, local=local, validate_schema=False
                )
            abort_json(409, "Event not available in this state")
    elif ef_type == "iter.effects":
        effects = raw_ef["effects"] or []
        for d in ef.get("iter", []):
            changed, doc = _apply_effects(
                {"effects": effects}, doc, definition,
                actor_id=d.get("actor_id", actor_id),
                payload=d.get("payload", payload),
                local=d.get("local", local),
                validate_schema=False
            )
            if changed:
                return changed, doc
    elif ef_type == "schedule.event":
        from .schedule import schedule_event_at, schedule_event_cron

        contract_id = str(doc.get("_id") or "")
        if "events" in ef:
            events = ef["events"]
        else:
            events = {ef["key"]: ef["event"]}
        for key, ef in events.items():
            if "at" in ef:
                func = schedule_event_at
                what = ef["at"]
                if isinstance(what, str):
                    what = dt.datetime.fromisoformat(what)
                if not isinstance(what, dt.datetime):
                    abort_json(400, "schedule.event_at requires datetime 'at'")
            else:
                func = schedule_event_cron
                what = ef["cron"]
            job: Dict[str, Any] = {
                "contract_id": ef.get("contract_id", contract_id),
                "event_name": ef["event_name"],
                "payload": ef.get("payload") or {},
                "actor_id": ef.get("actor_id", actor_id),
            }
            local[key] = func(what, job)
    elif ef_type == "unschedule.event":
        event_id = ef.get("event_id")
        if isinstance(event_id, str):
            events = [event_id]
        elif isinstance(event_id, list):
            events = event_id
        else:
            events = []
        from .schedule import unschedule_events

        if events:
            unschedule_events(events)
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
        if "items" in ef:
            items = ef["items"]
        else:
            items = {ef["key"]: ef["item"]}
        now = now_utc()
        base_item = {
            "data": {},
            "files": {},
            "acl_dom": acl_user(actor_id),
            "created_by": actor_id,
            "updated_by": actor_id,
            "created_at": now,
            "updated_at": now,
        }
        for k, v in items.items():
            item = dict(base_item)
            item.update(v)
            local[k] = str(mongo_insert_one(coll, item).inserted_id)
    elif ef_type == "update.item":
        coll = get_mongo(collection=config_get("ITEMS_COLLECTION", "items"))
        now = now_utc()
        out_key = None
        find_one_and_update_opts = {"return_document": ReturnDocument.AFTER}
        if ef.get("projection"):
            find_one_and_update_opts["projection"] = ef["projection"]
        if "updates" in ef:
            updates = ef["updates"]
        else:
            item_id = ef["item_id"]
            if isinstance(item_id, list):
                updates = {k: ef["update"] for k in item_id}
            else:
                out_key = item_id
                updates = {item_id: ef["update"]}
        sft_local = _safe_local(local)
        docs = {}
        for k, update in updates.items():
            update = [update] if isinstance(update, dict) else update
            docs[k] = mongo_find_one_and_update(
                coll,
                {"_id": k},
                [
                    {"$set": {"updated_by": actor_id}},
                    *update,
                    {"$set": {"updated_at": now}},
                ],
                **find_one_and_update_opts,
                let={
                    "user": actor_id,
                    "payload": payload,
                    "local": sft_local,
                },
            )

        if "key" in ef:
            if out_key is not None:
                docs = docs[out_key]
            local[ef["key"]] = docs
    elif ef_type == "delete.item":
        coll = get_mongo(collection=config_get("ITEMS_COLLECTION", "items"))
        item_ids = ef["item_id"]
        if isinstance(ef["item_id"], str):
            item_ids = [ef["item_id"]]
        mongo_delete_many(coll, {"_id": {"$in": item_ids}})
    elif ef_type == "get.item":
        coll = get_mongo(collection=config_get("ITEMS_COLLECTION", "items"))
        item_ids = ef["item_id"]
        if isinstance(ef["item_id"], str):
            item_ids = [ef["item_id"]]
        docs = list(
            mongo_find(
                coll, {"_id": {"$in": item_ids}}, projection=ef.get("projection", {})
            )
        )

        found_ids = {doc["_id"] for doc in docs}
        requested_ids = set(item_ids)

        if found_ids != requested_ids:
            missing = requested_ids - found_ids
            abort_json(404, f"Items not found: {[str(x) for x in missing]}")

        if isinstance(ef["item_id"], str):
            docs = docs[0] if docs else None
        else:
            docs = {doc["_id"]: doc for doc in docs}
        local[ef["key"]] = docs
    elif ef_type == "get.contract":
        contract_ids = ef["contract_id"]
        if isinstance(ef["contract_id"], str):
            contract_ids = [ef["contract_id"]]
        docs = list(
            mongo_find(
                _contracts_coll(),
                {"_id": {"$in": contract_ids}},
                projection=ef.get("projection", {}),
            )
        )

        found_ids = {doc["_id"] for doc in docs}
        requested_ids = set(contract_ids)

        if found_ids != requested_ids:
            missing = requested_ids - found_ids
            abort_json(404, f"Contracts not found: {[str(x) for x in missing]}")

        if isinstance(ef["contract_id"], str):
            docs = docs[0] if docs else None
        local[ef["key"]] = docs
    elif ef_type == "custom.function":
        func = REGISTERED_FUNCTIONS[ef["func"]]
        local[ef["key"]] = func(*ef.get("args", ()), **ef.get("kwargs", {}))
    else:
        abort_json(400, f"Unknown effect type: {ef_type}")

    if doc.get("state") != initial_state:
        return True, _apply_on_enter(
            doc=doc,
            actor_id=actor_id,
            definition=definition,
            prev_state=initial_state,
            local=local,
            payload=payload,
        )
    return False, doc


def _close_contract(doc, definition):
    if pydash.get(definition, f"states.{doc.get('state')}.final", False):
        mongo_update_one(
            _contracts_coll(),
            {"_id": doc.get("_id")},
            {"$set": {"status": "DONE"}, "$unset": {"local": ""}},
        )
        return pydash.merge(doc, {"status": "DONE"})
    return doc


def validate_context_schema(doc, state):
    if state and "context_schema" in state:
        from .routes import _validate_schema

        schema_errors = _validate_schema(doc["context"], state["context_schema"])
        if schema_errors:
            abort_json(422, "Invalid context schema")


def _apply_effects(
        event, doc, definition, actor_id, payload=None, local=None, validate_schema=True
):
    for ef in event.get("effects", []):
        changed, doc = _apply_effect_step(
            doc=doc, ef=ef, payload=payload, actor_id=actor_id, local=local, definition=definition
        )
        if changed:
            doc = _close_contract(doc, definition)
            return changed, doc
    if validate_schema:
        validate_context_schema(
            doc, pydash.get(definition, f"states.{doc['state']}")
        )
    return False, doc


def _apply_on_enter(
        *,
        doc: dict[str, Any],
        actor_id: str,
        definition: dict[str, Any],
        prev_state=None,
        payload=None,
        local=None,
) -> dict[str, Any]:
    if payload is None:
        payload = {}
    if local is None:
        local = {}

    if prev_state:
        on_exit = pydash.get(definition, f"states.{doc.get('state')}.on_exit", {})
        changed, doc = _apply_effects(
            on_exit,
            doc,
            definition,
            actor_id=actor_id,
            payload=payload,
            local=local,
            validate_schema=False,
        )
        if changed:
            return doc
        validate_context_schema(doc, on_exit)

    on_enter = pydash.get(definition, f"states.{doc.get('state')}.on_enter", {})
    validate_context_schema(doc, on_enter)
    _, doc = _apply_effects(on_enter, doc, definition, actor_id, local=local, validate_schema=True)
    if not _get_contract(str(doc.get("_id") or "")):
        abort_json(422, "Contract rejected by on_enter controls")
    return doc


def _process_event(
        *,
        contract_id: str,
        dyn_path: str,
        actor_id: str,
        body_payload: Dict[str, Any],
        event_name: Optional[str] = None,
) -> Tuple[Dict[str, Any], int]:
    with Lock(contract_id):
        doc = _get_contract(contract_id)
        if not doc:
            abort_json(404, "Contract not found")
        definition = get_definition(doc)
        if doc.get("status") in ("DONE", "CANCELED"):
            abort_json(410, "Contract not accepting events")

        state = str(doc.get("state") or "")
        events = dict(pydash.get(definition, f"events", {}))
        events.update(pydash.get(definition, f"states.{state}.events", {}))
        selected_edef: Optional[Dict[str, Any]] = None
        selected_trigger: Optional[Dict[str, Any]] = None
        if event_name is None:
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
        else:
            selected_edef = events.get(event_name)
            if selected_edef is None:
                abort_json(409, "Event not available in this state")
            selected_trigger = {}
        return _process_selected_event(
            doc=doc,
            definition=definition,
            edef=selected_edef,
            selected_trigger=selected_trigger,
            actor_id=actor_id,
            body_payload=body_payload,
        )


def _run_event(edef, doc, actor_id, payload, definition):
    local = {}
    changed, doc = _apply_effects(edef, doc, definition, actor_id, payload=payload, local=local)
    doc = _close_contract(doc, definition)
    return changed, doc, local


def _process_selected_event(
        *,
        doc: Dict[str, Any],
        definition: Dict[str, Any],
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
    allow_principals = _src_get("allow_principals")
    deny_principals = _src_get("deny_principals")
    if allow_principals is not None or deny_principals is not None:
        enforcer = get_enforcer()
        roles = set(enforcer.get_roles_for_user(actor_id))
        roles.add(actor_id)
        if allow_principals is not None and not roles.intersection(set(resolver(allow_principals, ctx) or [])):
            abort_json(403, "Subject not allowed")
        if deny_principals is not None and roles.intersection(set(resolver(deny_principals, ctx) or [])):
            abort_json(403, "Subject denied")
    allow_user_states = _src_get("allow_user_states")
    deny_user_states = _src_get("deny_user_states")
    if (
            allow_user_states is not None and actor_state_before not in set(resolver(allow_user_states, ctx) or [])
    ) or (
            deny_user_states is not None and actor_state_before in set(resolver(deny_user_states, ctx) or [])
    ):
        abort_json(409, "Event not available for actor state")
    schema_errors = validate_payload(_src_get("payload_schema"), body_payload)
    if schema_errors:
        return {"error": "Invalid payload", "details": schema_errors}, 422

    changed, doc, local = _run_event(edef, doc, actor_id, body_payload, definition)

    if resolve_response:
        ctx = {"local": local, "doc": doc, "user": actor_id, "payload": body_payload}
        return resolver(_src_get("response") or {"ok": True}, ctx), 200
    return {"ok": True}, 200


def get_definition(doc):
    return mongo_find_one(_templates_coll(), {"_id": doc["template_id"]})["definition"]


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
        "metadata": template.get("metadata") or {},
        "created_by": owner_id,
        "created_at": now,
        "updated_at": now,
        "template_id": template_id,
    }
    mongo_insert_one(_contracts_coll(), doc)

    return _apply_on_enter(doc=_get_contract(contract_id), actor_id=str(owner_id), definition=definition)
