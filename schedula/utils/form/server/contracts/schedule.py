import os
import socket
import time
import uuid
from datetime import timedelta, timezone, datetime
from typing import Any, Dict, List

import pydash
from pymongo import ReturnDocument
from sherlock import Lock

from ..utils import now_utc, get_mongo, config_get, mongo_delete_many

UTC = timezone.utc
OWNER = f"{socket.gethostname()}:{os.getpid()}"


def _queue_coll():
    return get_mongo(
        collection=config_get("CONTRACT_QUEUE_COLLECTION", "contract_queue")
    )


def _claim_job_now():  # For test cases
    return now_utc()


def _cron_slot(now_dt: datetime) -> str:
    t = now_dt.astimezone(UTC).replace(second=0, microsecond=0)
    return t.isoformat()


def _expand_cron_field(
        field: str, min_v: int, max_v: int, *, allow_7_as_0: bool = False
) -> List[int]:
    values: set[int] = set()
    for chunk in field.split(","):
        part = chunk.strip()
        if not part:
            raise ValueError("invalid cron field")
        if part == "*":
            values.update(range(min_v, max_v + 1))
            continue

        step = 1
        base = part
        if "/" in part:
            base, step_raw = part.split("/", 1)
            step = int(step_raw)
            if step <= 0:
                raise ValueError("invalid cron step")

        if base == "*":
            start, end = min_v, max_v
        elif "-" in base:
            start_raw, end_raw = base.split("-", 1)
            start, end = int(start_raw), int(end_raw)
        else:
            start = end = int(base)

        if allow_7_as_0:
            if start == 7:
                start = 0
            if end == 7:
                end = 0
            if start == 0 and end == 0 and base in {"7", "0", "7-7", "0-0"}:
                values.add(0)
                continue

        if start < min_v or end > max_v or start > end:
            raise ValueError("cron field out of range")
        values.update(range(start, end + 1, step))

    return sorted(values)


def explode_cron(cron_expr: str) -> Dict[str, Any]:
    parts = [p for p in str(cron_expr or "").split() if p]
    if len(parts) != 5:
        raise ValueError("cron must have 5 fields")

    minute_s, hour_s, dom_s, month_s, dow_s = parts
    minutes = _expand_cron_field(minute_s, 0, 59)
    hours = _expand_cron_field(hour_s, 0, 23)
    dom = _expand_cron_field(dom_s, 1, 31)
    months = _expand_cron_field(month_s, 1, 12)
    dow = _expand_cron_field(dow_s, 0, 6, allow_7_as_0=True)
    return {
        "minutes": minutes,
        "hours": hours,
        "dom": dom,
        "months": months,
        "dow": dow,
        "dom_any": dom_s == "*",
        "dow_any": dow_s == "*",
    }


def _cron_match_filter(now_dt: datetime) -> Dict[str, Any]:
    t = now_dt.astimezone(UTC)
    cron_dow = (t.weekday() + 1) % 7
    dom_match = {"cron.dom": t.day}
    dow_match = {"cron.dow": cron_dow}
    return {
        "kind": "cron",
        "cron.minutes": t.minute,
        "cron.hours": t.hour,
        "cron.months": t.month,
        "$or": [
            {"cron.dom_any": True, "cron.dow_any": True},
            {"cron.dom_any": True, "cron.dow_any": False, **dow_match},
            {"cron.dom_any": False, "cron.dow_any": True, **dom_match},
            {
                "cron.dom_any": False,
                "cron.dow_any": False,
                "$or": [dom_match, dow_match],
            },
        ],
        "$and": [
            {
                "$or": [
                    {"last_claim_slot": {"$exists": False}},
                    {"last_claim_slot": {"$ne": _cron_slot(t)}},
                ]
            },
            {
                "$or": [
                    {"run_at": {"$exists": False}},
                    {"run_at": {"$lte": t}},
                ]
            },
        ],
    }


def claim_job(coll, lease_s=120):
    t = _claim_job_now().astimezone(UTC)
    lease_until = t + timedelta(seconds=lease_s)
    slot = _cron_slot(t)

    return coll.find_one_and_update(
        filter={
            "status": "PENDING",
            "$or": [
                {
                    "kind": {"$ne": "cron"},
                    "run_at": {"$lte": t},
                },
                _cron_match_filter(t),
            ],
            "$and": [
                {
                    "$or": [
                        {"locked_until": {"$exists": False}},
                        {"locked_until": {"$lte": t}},
                    ]
                },
            ],
        },
        update={
            "$set": {
                "status": "RUNNING",
                "locked_until": lease_until,
                "locked_by": OWNER,
                "started_at": t,
                "updated_at": t,
                "last_claim_slot": slot,
            },
            "$inc": {"attempts": 1},
        },
        sort=[("run_at", 1)],
        return_document=ReturnDocument.AFTER,
    )


def ack_done(coll, job_id, resp=None):
    s = {"status": "DONE", "finished_at": now_utc(), "updated_at": now_utc()}
    s.update(resp or {})
    coll.update_one(
        {"_id": job_id},
        {"$set": s, "$unset": {"locked_until": "", "locked_by": ""}},
    )


def nack_retry(coll, job_id, err: Exception, delay_s=30):
    t = now_utc()
    coll.update_one(
        {"_id": job_id},
        {
            "$set": {
                "status": "PENDING",
                "run_at": t + timedelta(seconds=delay_s),
                "last_error": str(err),
                "updated_at": t,
            },
            "$unset": {"locked_until": "", "locked_by": ""},
        },
    )


def loop_once(coll, func):
    job = claim_job(coll)
    if job:
        try:
            resp = func(**job["payload"])
            if job.get("kind") == "cron":
                coll.update_one(
                    {"_id": job["_id"]},
                    {
                        "$set": {
                            "status": "PENDING",
                            "run_at": now_utc() + timedelta(seconds=10),
                            "updated_at": now_utc(),
                        },
                        "$unset": {
                            "locked_until": "",
                            "locked_by": "",
                            "started_at": "",
                        },
                    },
                )
            else:
                ack_done(coll, job["_id"], resp)
        except Exception as e:
            nack_retry(coll, job["_id"], e, delay_s=10)


def _worker_loop(app, coll, func, poll_interval_s=5):
    while True:
        with app.app_context():
            loop_once(coll, func)
        time.sleep(poll_interval_s)


def _schedule_event_at(coll, when_local: datetime, payload: dict):
    job_id = str(uuid.uuid4())
    doc = {
        "_id": job_id,
        "status": "PENDING",
        "run_at": when_local.astimezone(timezone.utc),
        "payload": payload,
        "attempts": 0,
        "created_at": now_utc(),
        "updated_at": now_utc(),
    }
    coll.insert_one(doc)
    return job_id


def _schedule_event_cron(coll, cron_expr: str, payload: dict):
    job_id = str(uuid.uuid4())
    cron = explode_cron(cron_expr)
    doc = {
        "_id": job_id,
        "kind": "cron",
        "status": "PENDING",
        "run_at": now_utc(),
        "cron_expr": cron_expr,
        "cron": cron,
        "payload": payload,
        "attempts": 0,
        "created_at": now_utc(),
        "updated_at": now_utc(),
    }
    coll.insert_one(doc)
    return job_id


def schedule_event_at(when_local: datetime, payload: dict):
    return _schedule_event_at(_queue_coll(), when_local, payload)


def schedule_event_cron(cron_expr: str, payload: dict):
    return _schedule_event_cron(_queue_coll(), cron_expr, payload)


def unschedule_events(job_ids: list[str]):
    mongo_delete_many(_queue_coll(), {"_id": {"$in": job_ids}})


def _func(contract_id, event_name, payload, actor_id):
    from .routes import _get_contract
    from .engine import _run_event, get_definition

    with Lock(contract_id):
        doc = _get_contract(contract_id)
        if not doc:
            return {"status": "ERROR", "message": f"Contract not found: {contract_id}"}
        definition = get_definition(doc)
        if doc.get("status") in ("DONE", "CANCELED"):
            return {"status": "SKIP", "message": f"Contract not accepting events"}

        state = str(doc.get("state") or "")
        events = dict(pydash.get(definition, f"events", {}))
        events.update(pydash.get(definition, f"states.{state}.events", {}))
        edef = events.get(event_name)
        if edef is None:
            return {"status": "SKIP", "message": f"Event not found: {event_name}"}
        _run_event(edef, doc, actor_id=actor_id, payload=payload, definition=definition)
    return {}


def worker_loop(app, poll_interval_s=5):
    with app.app_context():
        coll = _queue_coll()
    return _worker_loop(app, coll, _func, poll_interval_s)
