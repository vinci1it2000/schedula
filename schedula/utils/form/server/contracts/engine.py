# coding=utf-8
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2026, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');

"""Contract workflow engine and validation helpers."""

from __future__ import annotations

import hashlib
import json
import uuid
from urllib.parse import urlparse
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from flask import current_app
import httpx
from jsonschema import Draft202012Validator

from ..utils import abort_json
from .registry import ActionRegistry


@dataclass
class ValidationResult:
    valid: bool
    errors: List[str]
    normalized: Dict[str, Any]


def _max_depth(obj: Any, level: int = 0) -> int:
    if isinstance(obj, dict):
        if not obj:
            return level
        return max(_max_depth(v, level + 1) for v in obj.values())
    if isinstance(obj, list):
        if not obj:
            return level
        return max(_max_depth(v, level + 1) for v in obj)
    return level


def _normalize_path(path: Optional[str]) -> str:
    p = (path or "").strip()
    if not p:
        return ""
    return p if p.startswith("/") else f"/{p}"


def _validate_condition(
    cond: Any, *, errors: List[str], path: str = "condition"
) -> None:
    if not isinstance(cond, dict):
        errors.append(f"{path}: must be object")
        return
    if not cond:
        errors.append(f"{path}: empty")
        return
    if len(cond) != 1:
        errors.append(f"{path}: must have single operator")
        return
    op, payload = next(iter(cond.items()))
    if op in {"eq", "neq", "gt", "gte", "lt", "lte", "in", "exists", "lengthGte"}:
        if not isinstance(payload, dict):
            errors.append(f"{path}.{op}: must be object")
            return
        if "var" not in payload or not isinstance(payload.get("var"), str):
            errors.append(f"{path}.{op}: missing var")
            return
        if op != "exists" and "value" not in payload:
            errors.append(f"{path}.{op}: missing value")
            return
        return
    if op in {"and", "or"}:
        if not isinstance(payload, list) or not payload:
            errors.append(f"{path}.{op}: must be non-empty list")
            return
        for i, child in enumerate(payload):
            _validate_condition(child, errors=errors, path=f"{path}.{op}[{i}]")
        return
    if op == "not":
        _validate_condition(payload, errors=errors, path=f"{path}.not")
        return
    errors.append(f"{path}: unsupported operator '{op}'")


def validate_definition(
    definition: Dict[str, Any], registry: ActionRegistry
) -> ValidationResult:
    errors: List[str] = []
    if not isinstance(definition, dict):
        return ValidationResult(False, ["definition must be object"], {})

    max_json_size = int(current_app.config.get("CONTRACTS_MAX_JSON_SIZE", 200000))
    max_depth = int(current_app.config.get("CONTRACTS_MAX_DEPTH", 20))
    max_states = int(current_app.config.get("CONTRACTS_MAX_STATES", 200))
    max_events = int(current_app.config.get("CONTRACTS_MAX_EVENTS_PER_STATE", 200))

    size = len(json.dumps(definition))
    if size > max_json_size:
        errors.append("definition too large")
    if _max_depth(definition) > max_depth:
        errors.append("definition too deep")

    init_state = definition.get("initialState")
    states = definition.get("states")
    if not isinstance(init_state, str) or not init_state.strip():
        errors.append("initialState required")
    if not isinstance(states, dict) or not states:
        errors.append("states required")
        return ValidationResult(False, errors, {})

    if len(states) > max_states:
        errors.append("too many states")

    normalized = {**definition, "states": {}}

    for sname, sdef in states.items():
        if not isinstance(sname, str) or not sname.strip():
            errors.append("state name must be string")
            continue
        if not isinstance(sdef, dict):
            errors.append(f"state '{sname}' must be object")
            continue

        events = sdef.get("events") or {}
        if not isinstance(events, dict):
            errors.append(f"state '{sname}'.events must be object")
            events = {}
        if len(events) > max_events:
            errors.append(f"state '{sname}' has too many events")

        seen_paths: set[str] = set()
        normalized_events: Dict[str, Any] = {}

        for ename, edef in events.items():
            if not isinstance(edef, dict):
                errors.append(f"event '{sname}.{ename}' must be object")
                continue
            path = _normalize_path(str(edef.get("path") or ""))
            if not path:
                errors.append(f"event '{sname}.{ename}' missing path")
            elif path in seen_paths:
                errors.append(f"event '{sname}.{ename}' path not unique in state")
            else:
                seen_paths.add(path)

            if edef.get("method") and str(edef.get("method")).upper() != "POST":
                errors.append(f"event '{sname}.{ename}' method must be POST")

            principals = edef.get("allowedPrincipals")
            if principals is not None and not isinstance(principals, (list, dict)):
                errors.append(
                    f"event '{sname}.{ename}' allowedPrincipals must be list or $ref"
                )
            if isinstance(principals, list):
                for r in principals:
                    if not isinstance(r, str) or not (
                        r.startswith("u:") or r.startswith("g:")
                    ):
                        errors.append(
                            f"event '{sname}.{ename}' allowedPrincipals entries must be 'u:' or 'g:'"
                        )
                        break
            if isinstance(principals, dict):
                ref = principals.get("$ref")
                if not isinstance(ref, str) or not ref:
                    errors.append(
                        f"event '{sname}.{ename}' allowedPrincipals $ref must be string"
                    )

            payload_schema = edef.get("payloadSchema")
            if payload_schema is not None and not isinstance(payload_schema, dict):
                errors.append(f"event '{sname}.{ename}' payloadSchema must be object")

            dedup_key = edef.get("dedupKey")
            if dedup_key is not None and not isinstance(dedup_key, str):
                errors.append(f"event '{sname}.{ename}' dedupKey must be string")

            transitions = edef.get("transitions") or []
            if transitions and not isinstance(transitions, list):
                errors.append(f"event '{sname}.{ename}' transitions must be list")
                transitions = []
            for i, tr in enumerate(transitions):
                if not isinstance(tr, dict):
                    errors.append(
                        f"event '{sname}.{ename}' transitions[{i}] must be object"
                    )
                    continue
                target = tr.get("target")
                if not isinstance(target, str) or not target.strip():
                    errors.append(
                        f"event '{sname}.{ename}' transitions[{i}] missing target"
                    )
                cond = tr.get("condition")
                if cond is not None:
                    _validate_condition(
                        cond,
                        errors=errors,
                        path=f"{sname}.{ename}.transitions[{i}].condition",
                    )

            default_target = edef.get("defaultTarget")
            if default_target is not None and not isinstance(default_target, str):
                errors.append(f"event '{sname}.{ename}' defaultTarget must be string")

            effects = edef.get("effects") or []
            if effects and not isinstance(effects, list):
                errors.append(f"event '{sname}.{ename}' effects must be list")
                effects = []
            for i, ef in enumerate(effects):
                if not isinstance(ef, dict):
                    errors.append(
                        f"event '{sname}.{ename}' effects[{i}] must be object"
                    )
                    continue
                ef_type = ef.get("type")
                if not isinstance(ef_type, str) or not ef_type.strip():
                    errors.append(f"event '{sname}.{ename}' effects[{i}] missing type")
                elif not registry.has(ef_type) and ef_type != "context.update":
                    errors.append(
                        f"event '{sname}.{ename}' effects[{i}] unknown type '{ef_type}'"
                    )
                if ef_type == "context.update":
                    update = ef.get("update")
                    if update is None or not isinstance(update, (dict, list)):
                        errors.append(
                            f"event '{sname}.{ename}' effects[{i}].update must be object or list"
                        )

            normalized_events[ename] = {
                **edef,
                "path": path,
                "method": "POST",
            }

        on_enter = sdef.get("onEnter") or {}
        if on_enter and not isinstance(on_enter, dict):
            errors.append(f"state '{sname}'.onEnter must be object")
            on_enter = {}
        oe_effects = on_enter.get("effects") or []
        if oe_effects and not isinstance(oe_effects, list):
            errors.append(f"state '{sname}'.onEnter.effects must be list")
            oe_effects = []
        for i, ef in enumerate(oe_effects):
            if not isinstance(ef, dict):
                errors.append(f"state '{sname}'.onEnter.effects[{i}] must be object")
                continue
            ef_type = ef.get("type")
            if not isinstance(ef_type, str) or not ef_type.strip():
                errors.append(f"state '{sname}'.onEnter.effects[{i}] missing type")
            elif not registry.has(ef_type) and ef_type != "context.update":
                errors.append(
                    f"state '{sname}'.onEnter.effects[{i}] unknown type '{ef_type}'"
                )
            if ef_type == "context.update":
                update = ef.get("update")
                if update is None or not isinstance(update, (dict, list)):
                    errors.append(
                        f"state '{sname}'.onEnter.effects[{i}].update must be object or list"
                    )

        normalized["states"][sname] = {
            **sdef,
            "events": normalized_events,
        }

    for sname, sdef in normalized["states"].items():
        if sname not in states:
            continue
        events = sdef.get("events") or {}
        for ename, edef in events.items():
            transitions = edef.get("transitions") or []
            for tr in transitions:
                target = tr.get("target")
                if target and target not in states:
                    errors.append(
                        f"event '{sname}.{ename}' target state '{target}' missing"
                    )
            default_target = edef.get("defaultTarget")
            if default_target and default_target not in states:
                errors.append(
                    f"event '{sname}.{ename}' defaultTarget '{default_target}' missing"
                )
        on_enter = sdef.get("onEnter") or {}
        target = on_enter.get("transition")
        if target and target not in states:
            errors.append(f"state '{sname}'.onEnter.transition '{target}' missing")

    if init_state and init_state not in states:
        errors.append("initialState not found in states")

    return ValidationResult(not errors, errors, normalized if not errors else {})


def available_actions(definition: Dict[str, Any], state: str) -> List[Dict[str, Any]]:
    st = (definition.get("states") or {}).get(state) or {}
    events = st.get("events") or {}
    out: List[Dict[str, Any]] = []
    for ename, edef in events.items():
        path = _normalize_path(str(edef.get("path") or ""))
        if not path:
            continue
        out.append(
            {
                "method": "POST",
                "path": path,
                "event": ename,
                "roles": edef.get("allowedPrincipals") or [],
                "schema": edef.get("payloadSchema") or {},
            }
        )
    return out


def _normalize_ctx_var(var: Optional[str]) -> str:
    v = (var or "").strip()
    if v.startswith("/ctx/"):
        return v[len("/ctx/") :]
    if v.startswith("/context/"):
        return v[len("/context/") :]
    if v.startswith("$ctx."):
        return v[len("$ctx.") :]
    if v.startswith("ctx."):
        return v[len("ctx.") :]
    if v.startswith("context."):
        return v[len("context.") :]
    return v


def _get_var(context: Dict[str, Any], var: str) -> Any:
    cur: Any = context
    for part in _normalize_ctx_var(var).split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur.get(part)
    return cur


def get_context_value(context: Dict[str, Any], path: str) -> Any:
    return _get_var(context, path)


def set_context_value(context: Dict[str, Any], path: str, value: Any) -> Dict[str, Any]:
    out = dict(context)
    raw = (path or "").strip()
    if raw.startswith("/ctx/"):
        raw = raw[len("/ctx/") :]
    elif raw.startswith("/context/"):
        raw = raw[len("/context/") :]
    if "/" in raw:
        parts = [p for p in raw.split("/") if p]
    else:
        parts = [p for p in raw.split(".") if p]
    if not parts:
        return out
    cur = out
    for part in parts[:-1]:
        nxt = cur.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[part] = nxt
        cur = nxt
    cur[parts[-1]] = value
    return out


def _resolve_template(
    value: Any,
    *,
    context: Dict[str, Any],
    payload: Dict[str, Any],
    actor_id: str,
    event_id: str,
) -> Any:
    if isinstance(value, dict) and "$ref" in value:
        ref = value.get("$ref")
        if isinstance(ref, str):
            if ref.startswith("/ctx/") or ref.startswith("/context/"):
                return _get_var(context, ref)
            if ref.startswith("/payload/"):
                return _get_var(payload, ref[len("/payload/") :])
            if ref.startswith("http://") or ref.startswith("https://"):
                return _fetch_json_ref(ref)
        return value
    if not isinstance(value, str):
        return value
    if value.startswith("${") and value.endswith("}"):
        ref = value[2:-1].strip()
        if ref == "actorId":
            return actor_id
        if ref == "eventId":
            return event_id
        if ref.startswith("payload."):
            return _get_var(payload, ref[len("payload.") :])
        if (
            ref.startswith("context.")
            or ref.startswith("ctx.")
            or ref.startswith("$ctx.")
        ):
            return _get_var(context, ref)
    return value


def _fetch_json_ref(url: str) -> Any:
    if not current_app.config.get("CONTRACTS_HTTP_REF_ENABLED", False):
        return None
    allowlist = current_app.config.get("CONTRACTS_HTTP_REF_ALLOWLIST") or []
    if isinstance(allowlist, str):
        allowlist = [x.strip() for x in allowlist.split(",") if x.strip()]
    if allowlist:
        host = urlparse(url).netloc
        if host not in allowlist:
            return None
    timeout = float(current_app.config.get("CONTRACTS_HTTP_REF_TIMEOUT", 5))
    try:
        resp = httpx.get(url, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        if current_app.config.get("CONTRACTS_HTTP_REF_STRICT", False):
            raise
        return None


def resolve_template(
    value: Any,
    *,
    context: Dict[str, Any],
    payload: Dict[str, Any],
    actor_id: str,
    event_id: str,
) -> Any:
    return _resolve_template(
        value,
        context=context,
        payload=payload,
        actor_id=actor_id,
        event_id=event_id,
    )


def _select_update_case(
    update: Dict[str, Any],
    *,
    context: Dict[str, Any],
    payload: Dict[str, Any],
    actor_id: str,
    event_id: str,
) -> Dict[str, Any]:
    by_value = update.get("byValue")
    if isinstance(by_value, dict):
        raw_value = by_value.get("value")
        cases = by_value.get("cases") or {}
        default_case = by_value.get("default") or {}
        val = _resolve_template(
            raw_value,
            context=context,
            payload=payload,
            actor_id=actor_id,
            event_id=event_id,
        )
        if isinstance(cases, dict) and val in cases:
            chosen = cases.get(val)
            return chosen if isinstance(chosen, dict) else {}
        return default_case if isinstance(default_case, dict) else {}
    return update


def apply_context_update(
    context: Dict[str, Any],
    update: Dict[str, Any],
    *,
    payload: Dict[str, Any],
    actor_id: str,
    event_id: str,
) -> Dict[str, Any]:
    if isinstance(update, list):
        out = dict(context)
        for stage in update:
            if not isinstance(stage, dict):
                continue
            out = _apply_mongo_update(
                out,
                stage,
                payload=payload,
                actor_id=actor_id,
                event_id=event_id,
            )
        return out
    if not isinstance(update, dict):
        return context
    update = _select_update_case(
        update, context=context, payload=payload, actor_id=actor_id, event_id=event_id
    )
    if not isinstance(update, dict):
        return context
    if any(isinstance(k, str) and k.startswith("$") for k in update.keys()):
        return _apply_mongo_update(
            context,
            update,
            payload=payload,
            actor_id=actor_id,
            event_id=event_id,
        )
    out = dict(context)
    setters = update.get("set") or {}
    for k, v in setters.items():
        out[k] = _resolve_template(
            v, context=out, payload=payload, actor_id=actor_id, event_id=event_id
        )

    increments = update.get("inc") or {}
    for k, v in increments.items():
        cur = out.get(k, 0)
        try:
            inc = _resolve_template(
                v, context=out, payload=payload, actor_id=actor_id, event_id=event_id
            )
            out[k] = (cur or 0) + (inc or 0)
        except Exception:
            out[k] = cur

    push_unique = update.get("pushUnique") or {}
    for k, v in push_unique.items():
        val = _resolve_template(
            v, context=out, payload=payload, actor_id=actor_id, event_id=event_id
        )
        arr = out.get(k)
        if not isinstance(arr, list):
            arr = []
        if val not in arr:
            arr.append(val)
        out[k] = arr

    merges = update.get("merge") or {}
    for k, v in merges.items():
        val = _resolve_template(
            v, context=out, payload=payload, actor_id=actor_id, event_id=event_id
        )
        if not isinstance(val, dict):
            continue
        cur = out.get(k)
        if not isinstance(cur, dict):
            cur = {}
        cur.update(val)
        out[k] = cur
    return out


def _apply_mongo_update(
    context: Dict[str, Any],
    update: Dict[str, Any],
    *,
    payload: Dict[str, Any],
    actor_id: str,
    event_id: str,
) -> Dict[str, Any]:
    out = dict(context)

    setters = update.get("$set") or {}
    if isinstance(setters, dict):
        for k, v in setters.items():
            out[k] = _resolve_template(
                v, context=out, payload=payload, actor_id=actor_id, event_id=event_id
            )

    increments = update.get("$inc") or {}
    if isinstance(increments, dict):
        for k, v in increments.items():
            cur = out.get(k, 0)
            try:
                inc = _resolve_template(
                    v,
                    context=out,
                    payload=payload,
                    actor_id=actor_id,
                    event_id=event_id,
                )
                out[k] = (cur or 0) + (inc or 0)
            except Exception:
                out[k] = cur

    pushes = update.get("$push") or {}
    if isinstance(pushes, dict):
        for k, v in pushes.items():
            val = _resolve_template(
                v, context=out, payload=payload, actor_id=actor_id, event_id=event_id
            )
            arr = out.get(k)
            if not isinstance(arr, list):
                arr = []
            arr.append(val)
            out[k] = arr

    add_to_set = update.get("$addToSet") or {}
    if isinstance(add_to_set, dict):
        for k, v in add_to_set.items():
            val = _resolve_template(
                v, context=out, payload=payload, actor_id=actor_id, event_id=event_id
            )
            arr = out.get(k)
            if not isinstance(arr, list):
                arr = []
            if val not in arr:
                arr.append(val)
            out[k] = arr

    merges = update.get("$merge") or {}
    if isinstance(merges, dict):
        for k, v in merges.items():
            val = _resolve_template(
                v, context=out, payload=payload, actor_id=actor_id, event_id=event_id
            )
            if not isinstance(val, dict):
                continue
            cur = out.get(k)
            if not isinstance(cur, dict):
                cur = {}
            cur.update(val)
            out[k] = cur

    unsets = update.get("$unset") or {}
    if isinstance(unsets, dict):
        for k in unsets.keys():
            out.pop(k, None)
    return out


def eval_condition(cond: Dict[str, Any], context: Dict[str, Any]) -> bool:
    if not isinstance(cond, dict) or not cond:
        return False
    op, payload = next(iter(cond.items()))
    if op == "and":
        return all(eval_condition(c, context) for c in (payload or []))
    if op == "or":
        return any(eval_condition(c, context) for c in (payload or []))
    if op == "not":
        return not eval_condition(payload, context)

    if not isinstance(payload, dict):
        return False
    var = payload.get("var")
    value = payload.get("value")
    cur = _get_var(context, var) if isinstance(var, str) else None

    if op == "exists":
        return cur is not None
    if op == "eq":
        return cur == value
    if op == "neq":
        return cur != value
    if op == "gt":
        return cur is not None and cur > value
    if op == "gte":
        return cur is not None and cur >= value
    if op == "lt":
        return cur is not None and cur < value
    if op == "lte":
        return cur is not None and cur <= value
    if op == "in":
        try:
            return cur in (value or [])
        except Exception:
            return False
    if op == "lengthGte":
        if value is None:
            return False
        try:
            target = int(value)
        except (TypeError, ValueError):
            return False
        return isinstance(cur, list) and len(cur) >= target
    return False


def pick_transition(
    edef: Dict[str, Any], context: Dict[str, Any]
) -> Tuple[Optional[str], Optional[str]]:
    transitions = edef.get("transitions") or []
    for tr in transitions:
        cond = tr.get("condition")
        if cond is None or eval_condition(cond, context):
            return tr.get("target"), json.dumps(cond) if cond is not None else ""
    default_target = edef.get("defaultTarget")
    if default_target:
        return default_target, "default"
    return None, None


def hash_payload(payload: Any) -> str:
    try:
        raw = json.dumps(payload, sort_keys=True).encode("utf-8")
    except Exception:
        raw = str(payload).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


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


def build_effect_payload(
    ef: Dict[str, Any],
    *,
    context: Dict[str, Any],
    payload: Dict[str, Any],
    actor_id: str,
    event_id: str,
) -> Dict[str, Any]:
    args = ef.get("args") or {}
    args_mapping = ef.get("argsMapping") or {}
    out: Dict[str, Any] = {}
    if isinstance(args, dict):
        out.update(args)
    if isinstance(args_mapping, dict):
        for k, v in args_mapping.items():
            out[k] = _resolve_template(
                v,
                context=context,
                payload=payload,
                actor_id=actor_id,
                event_id=event_id,
            )
    return out


def normalize_event_path(edef: Dict[str, Any]) -> str:
    return _normalize_path(str(edef.get("path") or ""))


def find_event_by_path(
    definition: Dict[str, Any], state: str, path: str
) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    st = (definition.get("states") or {}).get(state) or {}
    events = st.get("events") or {}
    path_norm = _normalize_path(path)
    for ename, edef in events.items():
        if normalize_event_path(edef) == path_norm:
            return ename, edef
    return None, None


def is_final_state(definition: Dict[str, Any], state: str) -> bool:
    st = (definition.get("states") or {}).get(state) or {}
    return bool(st.get("final", False))


def resolve_on_enter_transition(
    definition: Dict[str, Any], state: str
) -> Optional[str]:
    st = (definition.get("states") or {}).get(state) or {}
    on_enter = st.get("onEnter") or {}
    target = on_enter.get("transition")
    if isinstance(target, str) and target.strip():
        return target
    return None


def resolve_on_enter_effects(
    definition: Dict[str, Any], state: str
) -> List[Dict[str, Any]]:
    st = (definition.get("states") or {}).get(state) or {}
    on_enter = st.get("onEnter") or {}
    effects = on_enter.get("effects") or []
    return effects if isinstance(effects, list) else []


def generate_event_id(value: Optional[str]) -> str:
    v = (value or "").strip()
    return v if v else str(uuid.uuid4())
