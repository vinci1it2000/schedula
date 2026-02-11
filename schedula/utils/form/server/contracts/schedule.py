import os
import socket
import time
import uuid
from datetime import timedelta, timezone, datetime

import pydash
from pymongo import ReturnDocument
from sqlalchemy_dlock import create_sadlock

from ..extensions import db
from ..utils import now_utc, get_mongo, config_get, mongo_delete_one

UTC = timezone.utc
OWNER = f"{socket.gethostname()}:{os.getpid()}"


def _queue_coll():
    return get_mongo(
        collection=config_get("CONTRACT_QUEUE_COLLECTION", "contract_queue")
    )


def _claim_job_now():  # For test cases
    return now_utc()


def claim_job(coll, lease_s=120):
    t = _claim_job_now()
    lease_until = t + timedelta(seconds=lease_s)

    return coll.find_one_and_update(
        filter={
            "status": "PENDING",
            "run_at": {"$lte": t},
            "$or": [
                {"locked_until": {"$exists": False}},
                {"locked_until": {"$lte": t}},
            ],
        },
        update={
            "$set": {
                "status": "RUNNING",
                "locked_until": lease_until,
                "locked_by": OWNER,
                "started_at": t,
                "updated_at": t,
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
        {"$set": s,
         "$unset": {"locked_until": "", "locked_by": ""}},
    )


def nack_retry(coll, job_id, err: Exception, delay_s=30):
    t = now_utc()
    coll.update_one(
        {"_id": job_id},
        {"$set": {
            "status": "PENDING",
            "run_at": t + timedelta(seconds=delay_s),
            "last_error": str(err),
            "updated_at": t,
        },
            "$unset": {"locked_until": "", "locked_by": ""}},
    )


def _worker_loop(coll, func, poll_interval_s=5):
    while True:
        job = claim_job(coll, batch_size=1)
        if not job:
            time.sleep(poll_interval_s)
            continue

        try:
            resp = func(**job["payload"])
            ack_done(coll, job["_id"], resp)
        except Exception as e:
            # retry in 30s
            nack_retry(coll, job["_id"], e, delay_s=10)


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


def schedule_event_at(when_local: datetime, payload: dict):
    return _schedule_event_at(_queue_coll(), when_local, payload)


def unschedule_event(job_id: str):
    mongo_delete_one(_queue_coll(), {"_id": job_id})


def _func(contract_id, event_name, payload, actor_id):
    from .routes import _get_contract
    from .engine import _run_event
    with create_sadlock(db.session, contract_id):
        doc = _get_contract(contract_id)
        if not doc:
            return {"status": "ERROR", "message": f"Contract not found: {contract_id}"}

        if doc.get("status") in ("DONE", "CANCELED"):
            return {"status": "SKIP", "message": f"Contract not accepting events"}

        state = str(doc.get("state") or "")
        events = dict(pydash.get(doc, f"definition.events", {}))
        events.update(pydash.get(doc, f"definition.states.{state}.events", {}))
        edef = events.get(event_name)
        if edef is None:
            return {"status": "SKIP", "message": f"Event not found: {event_name}"}
        _run_event(edef, doc, actor_id=actor_id, payload=payload)
    return {}


def worker_loop(poll_interval_s=5):
    return _worker_loop(_queue_coll(), _func, poll_interval_s)
