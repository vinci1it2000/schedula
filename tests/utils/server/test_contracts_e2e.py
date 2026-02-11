# coding: utf-8
from __future__ import annotations

import contextlib
import datetime as dt
import os
import unittest
import uuid
from typing import Any, Dict
from unittest.mock import patch
from urllib.parse import urlsplit, urlunsplit

import httpx
from flask import Flask
from flask_security.utils import hash_password
from schedula.utils.form.server import basic_app
from schedula.utils.form.server.extensions import db as _db
from schedula.utils.form.server.security import User
from schedula.utils.form.server.security.casbin import get_enforcer
from schedula.utils.form.server.security.casbin.bootstrap import (
    bootstrap_user,
    set_system_admin,
)
from schedula.utils.form.server.security.casbin.helpers import ADMIN_DOMAIN, ANON_USER
from schedula.utils.form.server.security.casbin.models import Group
from schedula.utils.form.server.security.casbin.models import ensure_public_group
from tests.utils.server.conftest import DummySitemap


def _definition() -> Dict[str, Any]:
    return {
        "id": "contract-e2e",
        "version": "1.0",
        "initial_state": "S1",
        "states": {
            "S1": {
                "events": {
                    "Ping": {
                        "trigger": [
                            {
                                "type": "api",
                                "path": "ping",
                                "method": "POST",
                                "payload_schema": {"type": "object"},
                                "allow_principals": ["g:authenticated"],
                                "response": {"ok": True},
                            }
                        ],
                        "effects": [],
                    }
                }
            },
            "S_FINAL": {"final": True},
        },
    }


def _ctx(path: str) -> Dict[str, str]:
    return {"$ctx": path}


def _rider_seats(principal_ref: str) -> Dict[str, Any]:
    return {"$ifNull": [_ctx(f"doc.context.riders.{principal_ref}.seats"), 1]}


def _payload_seats_or_one() -> Dict[str, Any]:
    return {"$ifNull": ["$$ctx.payload.seats", 1]}


def _accepted_total_plus_increment() -> Dict[str, Any]:
    return {
        "$add": [
            {"$ifNull": ["$context.accepted_seats_total", 0]},
            "$local.accepted_increment",
        ]
    }


def _capacity_reached_from_increment() -> Dict[str, Any]:
    return {
        "$gte": [
            _accepted_total_plus_increment(),
            {"$ifNull": ["$context.capacity", 0]},
        ]
    }


def _accepted_total_after_subtract(local_key: str) -> Dict[str, Any]:
    delta = f"$local.{local_key}"
    current = {"$ifNull": ["$context.accepted_seats_total", 0]}
    return {
        "$cond": [
            {"$gte": [current, delta]},
            {"$subtract": [current, delta]},
            0,
        ]
    }


def _gherkin_definition() -> Dict[str, Any]:
    return {
        "id": "contract-lifecycle-group-sync",
        "version": "1.0",
        "initial_state": "START",
        "states": {
            "START": {
                "on_enter": {
                    "context_schema": {
                        "type": "object",
                        "required": [
                            "capacity",
                            "driver",
                            "driver_trip",
                            "riders",
                        ],
                        "properties": {
                            "capacity": {"type": "integer", "minimum": 1},
                            "driver": {"type": "string", "pattern": "^u:.+$"},
                            "driver_trip": {
                                "type": "object",
                                "required": ["origin", "destination"],
                                "properties": {
                                    "origin": {
                                        "type": "object",
                                        "required": ["lat", "lng"],
                                        "properties": {
                                            "lat": {"type": "number"},
                                            "lng": {"type": "number"},
                                        },
                                        "additionalProperties": False,
                                    },
                                    "destination": {
                                        "type": "object",
                                        "required": ["lat", "lng"],
                                        "properties": {
                                            "lat": {"type": "number"},
                                            "lng": {"type": "number"},
                                        },
                                        "additionalProperties": False,
                                    },
                                },
                                "additionalProperties": False,
                            },
                            "riders": {
                                "type": "object",
                                "minProperties": 1,
                                "additionalProperties": {
                                    "type": "object",
                                    "required": ["seats", "trip"],
                                    "properties": {
                                        "seats": {"type": "integer", "minimum": 1},
                                        "trip": {
                                            "type": "object",
                                            "required": ["origin", "destination"],
                                            "properties": {
                                                "origin": {
                                                    "type": "object",
                                                    "required": ["lat", "lng"],
                                                    "properties": {
                                                        "lat": {"type": "number"},
                                                        "lng": {"type": "number"},
                                                    },
                                                    "additionalProperties": False,
                                                },
                                                "destination": {
                                                    "type": "object",
                                                    "required": ["lat", "lng"],
                                                    "properties": {
                                                        "lat": {"type": "number"},
                                                        "lng": {"type": "number"},
                                                    },
                                                    "additionalProperties": False,
                                                },
                                            },
                                            "additionalProperties": False,
                                        },
                                    },
                                    "additionalProperties": False,
                                },
                            },
                        },
                        "additionalProperties": True,
                    },
                    "effects": [
                        {
                            "type": "update.contract",
                            "update": {
                                "$set": {
                                    "local.start_initiated_by_driver": {
                                        "$eq": ["$created_by", "$context.driver"]
                                    }
                                }
                            },
                        },
                        {
                            "type": "if.else",
                            "condition": {
                                "$ctx": "doc.local.start_initiated_by_driver"
                            },
                            "then_effects": [
                                {
                                    "type": "schedule.event",
                                    "key": "driver_pickup_check_id",
                                    "event_name": "DriverPickupCheckTimed",
                                    "cron": "* * * * *",
                                    "actor_id": "system:cron",
                                },
                                {
                                    "type": "update.contract",
                                    "update": {
                                        "$set": {
                                            "context.driver_pickup_check_id": {
                                                "$ctx": "local.driver_pickup_check_id"
                                            }
                                        }
                                    },
                                },
                                {
                                    "type": "update.contract",
                                    "update": {
                                        "$set": {
                                            "states": {
                                                "$arrayToObject": {
                                                    "$map": {
                                                        "input": {
                                                            "$objectToArray": "$context.riders"
                                                        },
                                                        "as": "p",
                                                        "in": {
                                                            "k": "$$p.k",
                                                            "v": "PENDING",
                                                        },
                                                    }
                                                }
                                            }
                                        }
                                    },
                                },
                                {
                                    "type": "update.contract",
                                    "update": {
                                        "$set": {
                                            "states.$$ctx.doc.context.driver": "DRIVER",
                                            "context.accepted_seats_total": 0,
                                        }
                                    },
                                },
                                {
                                    "type": "update.contract",
                                    "update": {
                                        "$set": {
                                            "context.initial_invite_targets": {
                                                "$arrayToObject": {
                                                    "$map": {
                                                        "input": {
                                                            "$objectToArray": "$context.riders"
                                                        },
                                                        "as": "p",
                                                        "in": {
                                                            "k": "$$p.k",
                                                            "v": ["in_app"],
                                                        },
                                                    }
                                                }
                                            }
                                        }
                                    },
                                },
                                {
                                    "type": "notify",
                                    "notify": {
                                        "event": "contracts.user_invited",
                                        "targets": {
                                            "$ctx": "doc.context.initial_invite_targets"
                                        },
                                        "payload": {
                                            "contract_code": {
                                                "$ctx": "doc.context.contract_code"
                                            }
                                        },
                                    },
                                },
                                {
                                    "type": "update.contract",
                                    "update": {
                                        "$unset": "context.initial_invite_targets"
                                    },
                                },
                                {
                                    "type": "update.contract",
                                    "update": {"$set": {"state": "CONFIRMING"}},
                                },
                            ],
                            "else_effects": [
                                {
                                    "type": "update.contract",
                                    "update": {
                                        "$set": {
                                            "states": {
                                                "$arrayToObject": {
                                                    "$map": {
                                                        "input": {
                                                            "$objectToArray": "$context.riders"
                                                        },
                                                        "as": "p",
                                                        "in": {
                                                            "k": "$$p.k",
                                                            "v": "REQUESTING",
                                                        },
                                                    }
                                                }
                                            }
                                        }
                                    },
                                },
                                {
                                    "type": "update.contract",
                                    "update": {
                                        "$set": {
                                            "states.$$ctx.doc.context.driver": "PENDING_DRIVER"
                                        }
                                    },
                                },
                                {
                                    "type": "notify",
                                    "notify": {
                                        "event": "contracts.request_ride",
                                        "targets": {
                                            "$$ctx.doc.context.driver": ["in_app"]
                                        },
                                        "payload": {
                                            "contract_code": {
                                                "$ctx": "doc.context.contract_code"
                                            }
                                        },
                                    },
                                },
                            ],
                        },
                    ],
                },
                "events": {
                    "RequestJoin": {
                        "trigger": [
                            {
                                "type": "api",
                                "path": "request-join",
                                "method": "POST",
                                "payload_schema": {
                                    "type": "object",
                                    "required": ["seats", "origin", "destination"],
                                    "properties": {
                                        "seats": {"type": "integer", "minimum": 1},
                                        "origin": {
                                            "type": "object",
                                            "required": ["lat", "lng"],
                                            "properties": {
                                                "lat": {"type": "number"},
                                                "lng": {"type": "number"},
                                            },
                                            "additionalProperties": False,
                                        },
                                        "destination": {
                                            "type": "object",
                                            "required": ["lat", "lng"],
                                            "properties": {
                                                "lat": {"type": "number"},
                                                "lng": {"type": "number"},
                                            },
                                            "additionalProperties": False,
                                        },
                                    },
                                    "additionalProperties": False,
                                },
                                "deny_principals": ["$$ctx.doc.context.driver"],
                                "deny_user_states": [
                                    "REQUESTING",
                                    "PENDING",
                                    "ACCEPTED",
                                    "REJECTED",
                                    "CANCELLED",
                                    "EXPIRED",
                                ],
                                "response": {"ok": True, "event": "request_join"},
                            }
                        ],
                        "effects": [
                            {
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "local.has_capacity_for_join": {
                                            "$lte": [
                                                {
                                                    "$add": [
                                                        {
                                                            "$ifNull": [
                                                                "$context.accepted_seats_total",
                                                                0,
                                                            ]
                                                        },
                                                        "$$ctx.payload.seats",
                                                    ]
                                                },
                                                {"$ifNull": ["$context.capacity", 0]},
                                            ]
                                        }
                                    }
                                },
                            },
                            {
                                "type": "if.else",
                                "condition": {"$ctx": "local.has_capacity_for_join"},
                                "then_effects": [
                                    {
                                        "type": "update.contract",
                                        "update": {
                                            "$set": {
                                                "states.$$ctx.user": "REQUESTING",
                                                "context.riders.$$ctx.user.seats": "$$ctx.payload.seats",
                                                "context.riders.$$ctx.user.trip": {
                                                    "origin": "$$ctx.payload.origin",
                                                    "destination": "$$ctx.payload.destination",
                                                },
                                            }
                                        },
                                    },
                                    {
                                        "type": "notify",
                                        "notify": {
                                            "event": "contracts.join_requested",
                                            "targets": {
                                                "$$ctx.doc.context.driver": ["in_app"]
                                            },
                                            "payload": {
                                                "principal": "$$ctx.user",
                                                "contract_code": {
                                                    "$ctx": "doc.context.contract_code"
                                                },
                                            },
                                        },
                                    },
                                ],
                                "else_effects": [
                                    {
                                        "type": "notify",
                                        "notify": {
                                            "event": "contracts.join_request_rejected_capacity",
                                            "targets": {"$$ctx.user": ["in_app"]},
                                            "payload": {
                                                "contract_code": {
                                                    "$ctx": "doc.context.contract_code"
                                                }
                                            },
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                    "DriverAcceptStart": {
                        "trigger": [
                            {
                                "type": "api",
                                "path": "driver-accept-start",
                                "method": "POST",
                                "allow_principals": ["$$ctx.doc.context.driver"],
                                "response": {
                                    "ok": True,
                                    "event": "driver_accept_start",
                                },
                            }
                        ],
                        "effects": [
                            {
                                "type": "schedule.event",
                                "key": "driver_pickup_check_id",
                                "event_name": "DriverPickupCheckTimed",
                                "cron": "* * * * *",
                                "actor_id": "system:cron",
                            },
                            {
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "context.driver_pickup_check_id": {
                                            "$ctx": "local.driver_pickup_check_id"
                                        }
                                    }
                                },
                            },
                            {
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "states": {
                                            "$arrayToObject": {
                                                "$map": {
                                                    "input": {
                                                        "$objectToArray": "$states"
                                                    },
                                                    "as": "kv",
                                                    "in": {
                                                        "k": "$$kv.k",
                                                        "v": {
                                                            "$cond": [
                                                                {
                                                                    "$eq": [
                                                                        "$$kv.v",
                                                                        "REQUESTING",
                                                                    ]
                                                                },
                                                                "PENDING",
                                                                "$$kv.v",
                                                            ]
                                                        },
                                                    },
                                                }
                                            }
                                        },
                                        "context.accepted_seats_total": 0,
                                        "state": "CONFIRMING",
                                    }
                                },
                            },
                            {
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "states.$$ctx.doc.context.driver": "DRIVER"
                                    }
                                },
                            },
                            {
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "local.initial_invite_targets": {
                                            "$arrayToObject": {
                                                "$map": {
                                                    "input": {
                                                        "$objectToArray": "$context.riders"
                                                    },
                                                    "as": "p",
                                                    "in": {
                                                        "k": "$$p.k",
                                                        "v": ["in_app"],
                                                    },
                                                }
                                            }
                                        }
                                    }
                                },
                            },
                            {
                                "type": "notify",
                                "notify": {
                                    "event": "contracts.user_invited",
                                    "targets": {
                                        "$ctx": "doc.local.initial_invite_targets"
                                    },
                                    "payload": {
                                        "contract_code": {
                                            "$ctx": "doc.context.contract_code"
                                        }
                                    },
                                },
                            },
                        ],
                    },
                    "DriverRejectStart": {
                        "trigger": [
                            {
                                "type": "api",
                                "path": "driver-reject-start",
                                "method": "POST",
                                "response": {
                                    "ok": True,
                                    "event": "driver_reject_start",
                                },
                            }
                        ],
                        "effects": [
                            {
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "state": "REJECTED",
                                        "states": {
                                            "$arrayToObject": {
                                                "$map": {
                                                    "input": {
                                                        "$objectToArray": "$states"
                                                    },
                                                    "as": "kv",
                                                    "in": {
                                                        "k": "$$kv.k",
                                                        "v": {
                                                            "$cond": [
                                                                {
                                                                    "$eq": [
                                                                        "$$kv.v",
                                                                        "REQUESTING",
                                                                    ]
                                                                },
                                                                "REJECTED",
                                                                "$$kv.v",
                                                            ]
                                                        },
                                                    },
                                                }
                                            }
                                        },
                                    }
                                },
                            },
                        ],
                    },
                    "CancelJoinRequest": {
                        "trigger": [
                            {
                                "type": "api",
                                "path": "cancel-join-request",
                                "method": "POST",
                                "allow_user_states": ["REQUESTING"],
                                "response": {
                                    "ok": True,
                                    "event": "cancel_join_request",
                                },
                            }
                        ],
                        "effects": [
                            {
                                "type": "update.contract",
                                "update": {
                                    "$unset": [
                                        "states.$$ctx.user",
                                        "context.riders.$$ctx.user",
                                    ]
                                },
                            },
                            {
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "local.has_interested_users": {
                                            "$gt": [
                                                {
                                                    "$size": {
                                                        "$objectToArray": {
                                                            "$ifNull": [
                                                                "$context.riders",
                                                                {},
                                                            ]
                                                        }
                                                    }
                                                },
                                                0,
                                            ]
                                        }
                                    }
                                },
                            },
                            {
                                "type": "if.else",
                                "condition": {"$ctx": "doc.local.has_interested_users"},
                                "then_effects": [],
                                "else_effects": [
                                    {
                                        "type": "notify",
                                        "notify": {
                                            "event": "contracts.request_ride",
                                            "targets": {
                                                "$$ctx.doc.context.driver": ["in_app"]
                                            },
                                            "payload": {
                                                "contract_code": {
                                                    "$ctx": "doc.context.contract_code"
                                                }
                                            },
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                },
            },
            "CONFIRMING": {
                "on_enter": {
                    "effects": [
                        {
                            "type": "create.group",
                            "name": "contract-c-001",
                            "sub": "$$ctx.doc.context.driver",
                            "key": "group_ref",
                        },
                        {
                            "type": "update.contract",
                            "update": {
                                "$set": {
                                    "context.group_id": {"$ctx": "local.group_ref"}
                                }
                            },
                        },
                        {
                            "type": "update.contract",
                            "update": {
                                "$set": {
                                    "context.accepted_riders": {
                                        "$map": {
                                            "input": {
                                                "$filter": {
                                                    "input": {
                                                        "$objectToArray": "$states"
                                                    },
                                                    "as": "kv",
                                                    "cond": {
                                                        "$eq": [
                                                            "$$kv.v",
                                                            "ACCEPTED",
                                                        ]
                                                    },
                                                }
                                            },
                                            "as": "kv",
                                            "in": "$$kv.k",
                                        }
                                    }
                                }
                            },
                        },
                        {
                            "type": "update.group",
                            "group_id": {"$ctx": "doc.context.group_id"},
                            "edit_members": {
                                "add_members": "$$ctx.doc.context.accepted_riders"
                            },
                        },
                        {
                            "type": "update.contract",
                            "update": {"$unset": "context.accepted_riders"},
                        },
                        {
                            "type": "update.contract",
                            "update": {"$set": {"state": "RECRUITING"}},
                        },
                    ]
                }
            },
            "RECRUITING": {
                "events": {
                    "RequestJoin": {
                        "trigger": [
                            {
                                "type": "api",
                                "path": "request-join",
                                "method": "POST",
                                "payload_schema": {
                                    "type": "object",
                                    "required": ["seats", "origin", "destination"],
                                    "properties": {
                                        "seats": {"type": "integer", "minimum": 1},
                                        "origin": {
                                            "type": "object",
                                            "required": ["lat", "lng"],
                                            "properties": {
                                                "lat": {"type": "number"},
                                                "lng": {"type": "number"},
                                            },
                                            "additionalProperties": False,
                                        },
                                        "destination": {
                                            "type": "object",
                                            "required": ["lat", "lng"],
                                            "properties": {
                                                "lat": {"type": "number"},
                                                "lng": {"type": "number"},
                                            },
                                            "additionalProperties": False,
                                        },
                                    },
                                    "additionalProperties": False,
                                },
                                "deny_principals": ["$$ctx.doc.context.driver"],
                                "deny_user_states": [
                                    "REQUESTING",
                                    "PENDING",
                                    "ACCEPTED",
                                    "REJECTED",
                                    "CANCELLED",
                                    "EXPIRED",
                                ],
                                "response": {"ok": True, "event": "request_join"},
                            }
                        ],
                        "effects": [
                            {
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "local.has_capacity_for_join": {
                                            "$lte": [
                                                {
                                                    "$add": [
                                                        {
                                                            "$ifNull": [
                                                                "$context.accepted_seats_total",
                                                                0,
                                                            ]
                                                        },
                                                        "$$ctx.payload.seats",
                                                    ]
                                                },
                                                {"$ifNull": ["$context.capacity", 0]},
                                            ]
                                        }
                                    }
                                },
                            },
                            {
                                "type": "if.else",
                                "condition": {"$ctx": "local.has_capacity_for_join"},
                                "then_effects": [
                                    {
                                        "type": "update.contract",
                                        "update": {
                                            "$set": {
                                                "states.$$ctx.user": "REQUESTING",
                                                "context.riders.$$ctx.user.seats": "$$ctx.payload.seats",
                                                "context.riders.$$ctx.user.trip": {
                                                    "origin": "$$ctx.payload.origin",
                                                    "destination": "$$ctx.payload.destination",
                                                },
                                            }
                                        },
                                    },
                                    {
                                        "type": "notify",
                                        "notify": {
                                            "event": "contracts.join_requested",
                                            "targets": {
                                                "$$ctx.doc.context.driver": ["in_app"]
                                            },
                                            "payload": {
                                                "principal": "$$ctx.user",
                                                "contract_code": {
                                                    "$ctx": "doc.context.contract_code"
                                                },
                                            },
                                        },
                                    },
                                ],
                                "else_effects": [
                                    {
                                        "type": "notify",
                                        "notify": {
                                            "event": "contracts.join_request_rejected_capacity",
                                            "targets": {"$$ctx.user": ["in_app"]},
                                            "payload": {
                                                "contract_code": {
                                                    "$ctx": "doc.context.contract_code"
                                                }
                                            },
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                    "DriverAcceptJoinRequest": {
                        "trigger": [
                            {
                                "type": "api",
                                "path": "accept-join-request",
                                "method": "POST",
                                "allow_principals": ["$$ctx.doc.context.driver"],
                                "payload_schema": {
                                    "type": "object",
                                    "required": ["principal"],
                                    "properties": {
                                        "principal": {
                                            "type": "string",
                                            "pattern": "^u:.+$",
                                        }
                                    },
                                    "additionalProperties": False,
                                },
                                "response": {
                                    "ok": True,
                                    "event": "accept_join_request",
                                },
                            }
                        ],
                        "effects": [
                            {
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "local.target_is_requesting": {
                                            "$eq": [
                                                {
                                                    "$ifNull": [
                                                        {
                                                            "$ctx": "doc.states.$$ctx.payload.principal"
                                                        },
                                                        "",
                                                    ]
                                                },
                                                "REQUESTING",
                                            ]
                                        }
                                    }
                                },
                            },
                            {
                                "type": "if.else",
                                "condition": {"$ctx": "doc.local.target_is_requesting"},
                                "then_effects": [
                                    {
                                        "type": "update.contract",
                                        "update": {
                                            "$set": {
                                                "states.$$ctx.payload.principal": "ACCEPTED"
                                            }
                                        },
                                    },
                                    {
                                        "type": "update.group",
                                        "group_id": {"$ctx": "doc.context.group_id"},
                                        "edit_members": {
                                            "add_members": ["$$ctx.payload.principal"]
                                        },
                                    },
                                    {
                                        "type": "update.contract",
                                        "update": {
                                            "$set": {
                                                "local.accepted_increment": {
                                                    **_rider_seats(
                                                        "$$ctx.payload.principal"
                                                    )
                                                }
                                            }
                                        },
                                    },
                                    {
                                        "type": "update.contract",
                                        "update": {
                                            "$set": {
                                                "context.accepted_seats_total": {
                                                    **_accepted_total_plus_increment()
                                                },
                                                "local.capacity_reached": {
                                                    **_capacity_reached_from_increment()
                                                },
                                            }
                                        },
                                    },
                                    {
                                        "type": "if.else",
                                        "condition": {
                                            "$ctx": "doc.local.capacity_reached"
                                        },
                                        "then_effects": [
                                            {
                                                "type": "update.contract",
                                                "update": {"$set": {"state": "READY"}},
                                            }
                                        ],
                                        "else_effects": [
                                            {
                                                "type": "update.contract",
                                                "update": {
                                                    "$set": {"state": "RECRUITING"}
                                                },
                                            }
                                        ],
                                    },
                                    {
                                        "type": "notify",
                                        "notify": {
                                            "event": "contracts.join_request_accepted",
                                            "targets": {
                                                "$$ctx.payload.principal": ["in_app"]
                                            },
                                            "payload": {
                                                "contract_code": {
                                                    "$ctx": "doc.context.contract_code"
                                                }
                                            },
                                        },
                                    },
                                ],
                            },
                        ],
                    },
                    "DriverRejectJoinRequest": {
                        "trigger": [
                            {
                                "type": "api",
                                "path": "reject-join-request",
                                "method": "POST",
                                "allow_principals": ["$$ctx.doc.context.driver"],
                                "payload_schema": {
                                    "type": "object",
                                    "required": ["principal"],
                                    "properties": {
                                        "principal": {
                                            "type": "string",
                                            "pattern": "^u:.+$",
                                        }
                                    },
                                    "additionalProperties": False,
                                },
                                "response": {
                                    "ok": True,
                                    "event": "reject_join_request",
                                },
                            }
                        ],
                        "effects": [
                            {
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "local.target_is_requesting": {
                                            "$eq": [
                                                {
                                                    "$ifNull": [
                                                        {
                                                            "$ctx": "doc.states.$$ctx.payload.principal"
                                                        },
                                                        "",
                                                    ]
                                                },
                                                "REQUESTING",
                                            ]
                                        }
                                    }
                                },
                            },
                            {
                                "type": "if.else",
                                "condition": {"$ctx": "doc.local.target_is_requesting"},
                                "then_effects": [
                                    {
                                        "type": "update.contract",
                                        "update": {
                                            "$set": {
                                                "states.$$ctx.payload.principal": "REJECTED"
                                            }
                                        },
                                    },
                                    {
                                        "type": "notify",
                                        "notify": {
                                            "event": "contracts.join_request_rejected",
                                            "targets": {
                                                "$$ctx.payload.principal": ["in_app"]
                                            },
                                            "payload": {
                                                "contract_code": {
                                                    "$ctx": "doc.context.contract_code"
                                                }
                                            },
                                        },
                                    },
                                ],
                            },
                        ],
                    },
                    "CancelJoinRequest": {
                        "trigger": [
                            {
                                "type": "api",
                                "path": "cancel-join-request",
                                "method": "POST",
                                "allow_user_states": ["REQUESTING"],
                                "response": {
                                    "ok": True,
                                    "event": "cancel_join_request",
                                },
                            }
                        ],
                        "effects": [
                            {
                                "type": "update.contract",
                                "update": {
                                    "$unset": [
                                        "states.$$ctx.user",
                                        "context.riders.$$ctx.user.seats",
                                    ]
                                },
                            },
                            {
                                "type": "notify",
                                "notify": {
                                    "event": "contracts.join_request_cancelled",
                                    "targets": {"$$ctx.doc.context.driver": ["in_app"]},
                                    "payload": {
                                        "principal": "$$ctx.user",
                                        "contract_code": {
                                            "$ctx": "doc.context.contract_code"
                                        },
                                    },
                                },
                            },
                        ],
                    },
                    "InviteUser": {
                        "trigger": [
                            {
                                "type": "api",
                                "path": "invite-user",
                                "method": "POST",
                                "allow_principals": ["$$ctx.doc.context.driver"],
                                "payload_schema": {
                                    "type": "object",
                                    "required": ["principal"],
                                    "properties": {
                                        "principal": {
                                            "type": "string",
                                            "pattern": "^u:.+$",
                                        }
                                    },
                                    "additionalProperties": False,
                                },
                                "response": {"ok": True, "event": "invite_user"},
                            }
                        ],
                        "effects": [
                            {
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "states.$$ctx.payload.principal": "PENDING"
                                    }
                                },
                            },
                            {
                                "type": "schedule.event",
                                "key": "invite_timeout_id",
                                "event_name": "InviteUserTimedOut",
                                "cron": "* * * * *",
                                "actor_id": "system:cron",
                                "payload": {"principal": "$$ctx.payload.principal"},
                            },
                            {
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "context.pending_invites.$$ctx.payload.principal": {
                                            "$ctx": "local.invite_timeout_id"
                                        }
                                    }
                                },
                            },
                            {
                                "type": "notify",
                                "notify": {
                                    "event": "contracts.user_invited",
                                    "targets": {"$$ctx.payload.principal": ["in_app"]},
                                    "payload": {
                                        "contract_code": {
                                            "$ctx": "doc.context.contract_code"
                                        }
                                    },
                                },
                            },
                        ],
                    },
                    "AcceptUser": {
                        "trigger": [
                            {
                                "type": "api",
                                "path": "accept-user",
                                "method": "POST",
                                "allow_user_states": ["PENDING"],
                                "payload_schema": {
                                    "type": "object",
                                    "required": ["seats", "origin", "destination"],
                                    "properties": {
                                        "seats": {"type": "integer", "minimum": 1},
                                        "origin": {
                                            "type": "object",
                                            "required": ["lat", "lng"],
                                            "properties": {
                                                "lat": {"type": "number"},
                                                "lng": {"type": "number"},
                                            },
                                            "additionalProperties": False,
                                        },
                                        "destination": {
                                            "type": "object",
                                            "required": ["lat", "lng"],
                                            "properties": {
                                                "lat": {"type": "number"},
                                                "lng": {"type": "number"},
                                            },
                                            "additionalProperties": False,
                                        },
                                    },
                                    "additionalProperties": False,
                                },
                                "response": {"ok": True, "event": "accept_user"},
                            }
                        ],
                        "effects": [
                            {
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "local.pending_invite_event_id": {
                                            "$ctx": "doc.context.pending_invites.$$ctx.user"
                                        }
                                    }
                                },
                            },
                            {
                                "type": "if.else",
                                "condition": {
                                    "$ctx": "doc.local.pending_invite_event_id"
                                },
                                "then_effects": [
                                    {
                                        "type": "unschedule.event",
                                        "event_id": {
                                            "$ctx": "doc.local.pending_invite_event_id"
                                        },
                                    }
                                ],
                                "else_effects": [],
                            },
                            {
                                "type": "update.contract",
                                "update": {
                                    "$unset": "context.pending_invites.$$ctx.user"
                                },
                            },
                            {
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "states.$$ctx.user": "ACCEPTED",
                                        "context.riders.$$ctx.user.seats": "$$ctx.payload.seats",
                                        "context.riders.$$ctx.user.trip": {
                                            "origin": "$$ctx.payload.origin",
                                            "destination": "$$ctx.payload.destination",
                                        },
                                    }
                                },
                            },
                            {
                                "type": "update.group",
                                "group_id": {"$ctx": "doc.context.group_id"},
                                "edit_members": {"add_members": ["$$ctx.user"]},
                            },
                            {
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "local.accepted_increment": {
                                            **_payload_seats_or_one()
                                        }
                                    }
                                },
                            },
                            {
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "context.accepted_seats_total": {
                                            **_accepted_total_plus_increment()
                                        },
                                        "local.capacity_reached": {
                                            **_capacity_reached_from_increment()
                                        },
                                    }
                                },
                            },
                            {
                                "type": "if.else",
                                "condition": {"$ctx": "doc.local.capacity_reached"},
                                "then_effects": [
                                    {
                                        "type": "update.contract",
                                        "update": {"$set": {"state": "READY"}},
                                    }
                                ],
                                "else_effects": [
                                    {
                                        "type": "update.contract",
                                        "update": {"$set": {"state": "RECRUITING"}},
                                    }
                                ],
                            },
                            {
                                "type": "notify",
                                "notify": {
                                    "event": "contracts.user_accepted",
                                    "targets": {"$$ctx.doc.context.driver": ["in_app"]},
                                    "payload": {
                                        "principal": "$$ctx.user",
                                        "contract_code": {
                                            "$ctx": "doc.context.contract_code"
                                        },
                                    },
                                },
                            },
                        ],
                    },
                    "RejectUser": {
                        "trigger": [
                            {
                                "type": "api",
                                "path": "reject-user",
                                "method": "POST",
                                "allow_user_states": ["PENDING"],
                                "response": {"ok": True, "event": "reject_user"},
                            }
                        ],
                        "effects": [
                            {
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "local.pending_invite_event_id": {
                                            "$ctx": "doc.context.pending_invites.$$ctx.user"
                                        }
                                    }
                                },
                            },
                            {
                                "type": "if.else",
                                "condition": {
                                    "$ctx": "doc.local.pending_invite_event_id"
                                },
                                "then_effects": [
                                    {
                                        "type": "unschedule.event",
                                        "event_id": {
                                            "$ctx": "doc.local.pending_invite_event_id"
                                        },
                                    }
                                ],
                                "else_effects": [],
                            },
                            {
                                "type": "update.contract",
                                "update": {
                                    "$unset": "context.pending_invites.$$ctx.user"
                                },
                            },
                            {
                                "type": "update.contract",
                                "update": {"$set": {"states.$$ctx.user": "REJECTED"}},
                            },
                            {
                                "type": "notify",
                                "notify": {
                                    "event": "contracts.user_rejected",
                                    "targets": {"$$ctx.doc.context.driver": ["in_app"]},
                                    "payload": {
                                        "principal": "$$ctx.user",
                                        "contract_code": {
                                            "$ctx": "doc.context.contract_code"
                                        },
                                    },
                                },
                            },
                        ],
                    },
                    "InviteUserTimedOut": {
                        "trigger": [{"type": "api", "path": "invite-user-timeout"}],
                        "effects": [
                            {
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "states.$$ctx.payload.principal": "EXPIRED"
                                    }
                                },
                            },
                            {
                                "type": "update.contract",
                                "update": {
                                    "$unset": "context.pending_invites.$$ctx.payload.principal"
                                },
                            },
                            {
                                "type": "notify",
                                "notify": {
                                    "event": "contracts.invite_timed_out",
                                    "targets": {"$$ctx.doc.context.driver": ["in_app"]},
                                    "payload": {
                                        "contract_code": {
                                            "$ctx": "doc.context.contract_code"
                                        }
                                    },
                                },
                            },
                        ],
                    },
                    "DriverCancelInvite": {
                        "trigger": [
                            {
                                "type": "api",
                                "path": "driver-cancel-invite",
                                "method": "POST",
                                "allow_principals": ["$$ctx.doc.context.driver"],
                                "payload_schema": {
                                    "type": "object",
                                    "required": ["principal"],
                                    "properties": {
                                        "principal": {
                                            "type": "string",
                                            "pattern": "^u:.+$",
                                        }
                                    },
                                    "additionalProperties": False,
                                },
                                "response": {
                                    "ok": True,
                                    "event": "driver_cancel_invite",
                                },
                            }
                        ],
                        "effects": [
                            {
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "local.target_is_pending_invite": {
                                            "$eq": [
                                                {
                                                    "$ifNull": [
                                                        {
                                                            "$ctx": "doc.states.$$ctx.payload.principal"
                                                        },
                                                        "",
                                                    ]
                                                },
                                                "PENDING",
                                            ]
                                        }
                                    }
                                },
                            },
                            {
                                "type": "if.else",
                                "condition": {
                                    "$ctx": "doc.local.target_is_pending_invite"
                                },
                                "then_effects": [
                                    {
                                        "type": "unschedule.event",
                                        "event_id": {
                                            "$ctx": "doc.context.pending_invites.$$ctx.payload.principal"
                                        },
                                    },
                                    {
                                        "type": "update.contract",
                                        "update": [
                                            {
                                                "$set": {
                                                    "states.$$ctx.payload.principal": "CANCELLED"
                                                }
                                            },
                                            {
                                                "$unset": "context.pending_invites.$$ctx.payload.principal"
                                            },
                                        ],
                                    },
                                    {
                                        "type": "notify",
                                        "notify": {
                                            "event": "contracts.invite_cancelled_by_driver",
                                            "targets": {
                                                "$$ctx.payload.principal": ["in_app"]
                                            },
                                            "payload": {
                                                "contract_code": {
                                                    "$ctx": "doc.context.contract_code"
                                                }
                                            },
                                        },
                                    },
                                ],
                            },
                        ],
                    },
                    "CancelUser": {
                        "trigger": [
                            {
                                "type": "api",
                                "path": "cancel-user",
                                "method": "POST",
                                "allow_user_states": ["ACCEPTED"],
                                "response": {"ok": True, "event": "cancel_user"},
                            }
                        ],
                        "effects": [
                            {
                                "type": "update.group",
                                "group_id": {"$ctx": "doc.context.group_id"},
                                "edit_members": {"remove_members": ["$$ctx.user"]},
                            },
                            {
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "local.cancel_seats": {
                                            **_rider_seats("$$ctx.user")
                                        }
                                    }
                                },
                            },
                            {
                                "type": "update.contract",
                                "update": [
                                    {
                                        "$set": {
                                            "context.accepted_seats_total": {
                                                **_accepted_total_after_subtract(
                                                    "cancel_seats"
                                                )
                                            },
                                            "states.$$ctx.user": "CANCELLED",
                                        }
                                    },
                                    {"$unset": "context.riders.$$ctx.user.seats"},
                                ],
                            },
                            {
                                "type": "notify",
                                "notify": {
                                    "event": "contracts.user_cancelled",
                                    "targets": {"$$ctx.doc.context.driver": ["in_app"]},
                                    "payload": {
                                        "principal": "$$ctx.user",
                                        "contract_code": {
                                            "$ctx": "doc.context.contract_code"
                                        },
                                    },
                                },
                            },
                        ],
                    },
                    "DriverRemoveUser": {
                        "trigger": [
                            {
                                "type": "api",
                                "path": "driver-remove-user",
                                "method": "POST",
                                "allow_principals": ["$$ctx.doc.context.driver"],
                                "payload_schema": {
                                    "type": "object",
                                    "required": ["principal"],
                                    "properties": {
                                        "principal": {
                                            "type": "string",
                                            "pattern": "^u:.+$",
                                        }
                                    },
                                    "additionalProperties": False,
                                },
                                "response": {"ok": True, "event": "driver_remove_user"},
                            }
                        ],
                        "effects": [
                            {
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "local.target_is_accepted": {
                                            "$eq": [
                                                {
                                                    "$ifNull": [
                                                        {
                                                            "$ctx": "doc.states.$$ctx.payload.principal"
                                                        },
                                                        "",
                                                    ]
                                                },
                                                "ACCEPTED",
                                            ]
                                        }
                                    }
                                },
                            },
                            {
                                "type": "if.else",
                                "condition": {"$ctx": "doc.local.target_is_accepted"},
                                "then_effects": [
                                    {
                                        "type": "update.group",
                                        "group_id": {"$ctx": "doc.context.group_id"},
                                        "edit_members": {
                                            "remove_members": [
                                                "$$ctx.payload.principal"
                                            ]
                                        },
                                    },
                                    {
                                        "type": "update.contract",
                                        "update": {
                                            "$set": {
                                                "local.remove_seats": {
                                                    **_rider_seats(
                                                        "$$ctx.payload.principal"
                                                    )
                                                }
                                            }
                                        },
                                    },
                                    {
                                        "type": "update.contract",
                                        "update": [
                                            {
                                                "$set": {
                                                    "context.accepted_seats_total": {
                                                        **_accepted_total_after_subtract(
                                                            "remove_seats"
                                                        )
                                                    },
                                                    "states.$$ctx.payload.principal": "CANCELLED",
                                                }
                                            },
                                            {
                                                "$unset": "context.riders.$$ctx.payload.principal.seats"
                                            },
                                        ],
                                    },
                                    {
                                        "type": "notify",
                                        "notify": {
                                            "event": "contracts.user_removed_by_driver",
                                            "targets": {
                                                "$$ctx.payload.principal": ["in_app"]
                                            },
                                            "payload": {
                                                "contract_code": {
                                                    "$ctx": "doc.context.contract_code"
                                                }
                                            },
                                        },
                                    },
                                ],
                            },
                        ],
                    },
                    "DriverCancelTrip": {
                        "trigger": [
                            {
                                "type": "api",
                                "path": "driver-cancel-trip",
                                "method": "POST",
                                "allow_principals": ["$$ctx.doc.context.driver"],
                                "response": {"ok": True, "event": "driver_cancel_trip"},
                            }
                        ],
                        "effects": [
                            {
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "local.cancel_trip_targets": {
                                            "$arrayToObject": {
                                                "$map": {
                                                    "input": {
                                                        "$filter": {
                                                            "input": {
                                                                "$objectToArray": "$states"
                                                            },
                                                            "as": "kv",
                                                            "cond": {
                                                                "$eq": [
                                                                    "$$kv.v",
                                                                    "ACCEPTED",
                                                                ]
                                                            },
                                                        }
                                                    },
                                                    "as": "kv",
                                                    "in": {
                                                        "k": "$$kv.k",
                                                        "v": ["in_app"],
                                                    },
                                                }
                                            }
                                        }
                                    }
                                },
                            },
                            {
                                "type": "update.contract",
                                "update": {
                                    "$set": {"status": "CANCELED", "state": "CANCELED"}
                                },
                            },
                            {
                                "type": "notify",
                                "notify": {
                                    "event": "contracts.trip_cancelled_by_driver",
                                    "targets": "$$ctx.doc.local.cancel_trip_targets",
                                    "payload": {
                                        "contract_code": {
                                            "$ctx": "doc.context.contract_code"
                                        }
                                    },
                                },
                            },
                        ],
                    },
                    "DriverSetReady": {
                        "trigger": [
                            {
                                "type": "api",
                                "path": "set-ready",
                                "method": "POST",
                                "response": {"ok": True, "event": "set_ready"},
                            }
                        ],
                        "effects": [
                            {
                                "type": "update.contract",
                                "update": {"$set": {"state": "READY"}},
                            }
                        ],
                    },
                }
            },
            "READY": {
                "events": {
                    "CancelUser": {
                        "trigger": [
                            {
                                "type": "api",
                                "path": "cancel-user",
                                "method": "POST",
                                "allow_user_states": ["ACCEPTED"],
                                "response": {"ok": True, "event": "cancel_user"},
                            }
                        ],
                        "effects": [
                            {
                                "type": "update.group",
                                "group_id": {"$ctx": "doc.context.group_id"},
                                "edit_members": {"remove_members": ["$$ctx.user"]},
                            },
                            {
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "local.cancel_seats": {
                                            **_rider_seats("$$ctx.user")
                                        }
                                    }
                                },
                            },
                            {
                                "type": "update.contract",
                                "update": [
                                    {
                                        "$set": {
                                            "context.accepted_seats_total": {
                                                **_accepted_total_after_subtract(
                                                    "cancel_seats"
                                                )
                                            },
                                            "states.$$ctx.user": "CANCELLED",
                                            "state": "RECRUITING",
                                        }
                                    },
                                    {"$unset": "context.riders.$$ctx.user.seats"},
                                ],
                            },
                            {
                                "type": "notify",
                                "notify": {
                                    "event": "contracts.user_cancelled",
                                    "targets": {"$$ctx.doc.context.driver": ["in_app"]},
                                    "payload": {
                                        "principal": "$$ctx.user",
                                        "contract_code": {
                                            "$ctx": "doc.context.contract_code"
                                        },
                                    },
                                },
                            },
                        ],
                    },
                    "DriverSetRecruiting": {
                        "trigger": [
                            {
                                "type": "api",
                                "path": "set-recruiting",
                                "method": "POST",
                                "response": {"ok": True, "event": "set_recruiting"},
                            }
                        ],
                        "effects": [
                            {
                                "type": "update.contract",
                                "update": {"$set": {"state": "RECRUITING"}},
                            }
                        ],
                    },
                    "DriverStartTrip": {
                        "trigger": [
                            {
                                "type": "api",
                                "path": "start-trip",
                                "method": "POST",
                                "allow_principals": ["$$ctx.doc.context.driver"],
                                "response": {"ok": True, "event": "start_trip"},
                            }
                        ],
                        "effects": [
                            {
                                "type": "schedule.event",
                                "key": "riders_pickup_check_id",
                                "event_name": "RidersPickupCheckTimed",
                                "cron": "* * * * *",
                                "actor_id": "system:cron",
                            },
                            {
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "context.riders_pickup_check_id": {
                                            "$ctx": "local.riders_pickup_check_id"
                                        },
                                        "context.driver_in_pickup_zone": False,
                                        "context.riders_picked_up": {},
                                        "context.pending_pickup_targets": {
                                            "$arrayToObject": {
                                                "$map": {
                                                    "input": {
                                                        "$filter": {
                                                            "input": {
                                                                "$objectToArray": "$states"
                                                            },
                                                            "as": "kv",
                                                            "cond": {
                                                                "$eq": [
                                                                    "$$kv.v",
                                                                    "ACCEPTED",
                                                                ]
                                                            },
                                                        }
                                                    },
                                                    "as": "kv",
                                                    "in": {
                                                        "k": "$$kv.k",
                                                        "v": ["in_app"],
                                                    },
                                                }
                                            }
                                        },
                                    }
                                },
                            },
                            {
                                "type": "update.contract",
                                "update": {"$set": {"state": "IN_PROGRESS"}},
                            },
                        ],
                    },
                    "DriverRemoveUser": {
                        "trigger": [
                            {
                                "type": "api",
                                "path": "driver-remove-user",
                                "method": "POST",
                                "allow_principals": ["$$ctx.doc.context.driver"],
                                "payload_schema": {
                                    "type": "object",
                                    "required": ["principal"],
                                    "properties": {
                                        "principal": {
                                            "type": "string",
                                            "pattern": "^u:.+$",
                                        }
                                    },
                                    "additionalProperties": False,
                                },
                                "response": {"ok": True, "event": "driver_remove_user"},
                            }
                        ],
                        "effects": [
                            {
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "local.target_is_accepted": {
                                            "$eq": [
                                                {
                                                    "$ifNull": [
                                                        {
                                                            "$ctx": "doc.states.$$ctx.payload.principal"
                                                        },
                                                        "",
                                                    ]
                                                },
                                                "ACCEPTED",
                                            ]
                                        }
                                    }
                                },
                            },
                            {
                                "type": "if.else",
                                "condition": {"$ctx": "doc.local.target_is_accepted"},
                                "then_effects": [
                                    {
                                        "type": "update.group",
                                        "group_id": {"$ctx": "doc.context.group_id"},
                                        "edit_members": {
                                            "remove_members": [
                                                "$$ctx.payload.principal"
                                            ]
                                        },
                                    },
                                    {
                                        "type": "update.contract",
                                        "update": {
                                            "$set": {
                                                "local.remove_seats": {
                                                    **_rider_seats(
                                                        "$$ctx.payload.principal"
                                                    )
                                                }
                                            }
                                        },
                                    },
                                    {
                                        "type": "update.contract",
                                        "update": [
                                            {
                                                "$set": {
                                                    "context.accepted_seats_total": {
                                                        **_accepted_total_after_subtract(
                                                            "remove_seats"
                                                        )
                                                    },
                                                    "states.$$ctx.payload.principal": "CANCELLED",
                                                }
                                            },
                                            {
                                                "$unset": "context.riders.$$ctx.payload.principal.seats"
                                            },
                                        ],
                                    },
                                    {
                                        "type": "notify",
                                        "notify": {
                                            "event": "contracts.user_removed_by_driver",
                                            "targets": {
                                                "$$ctx.payload.principal": ["in_app"]
                                            },
                                            "payload": {
                                                "contract_code": {
                                                    "$ctx": "doc.context.contract_code"
                                                }
                                            },
                                        },
                                    },
                                ],
                            },
                        ],
                    },
                    "DriverCancelTrip": {
                        "trigger": [
                            {
                                "type": "api",
                                "path": "driver-cancel-trip",
                                "method": "POST",
                                "allow_principals": ["$$ctx.doc.context.driver"],
                                "response": {"ok": True, "event": "driver_cancel_trip"},
                            }
                        ],
                        "effects": [
                            {
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "local.cancel_trip_targets": {
                                            "$arrayToObject": {
                                                "$map": {
                                                    "input": {
                                                        "$filter": {
                                                            "input": {
                                                                "$objectToArray": "$states"
                                                            },
                                                            "as": "kv",
                                                            "cond": {
                                                                "$eq": [
                                                                    "$$kv.v",
                                                                    "ACCEPTED",
                                                                ]
                                                            },
                                                        }
                                                    },
                                                    "as": "kv",
                                                    "in": {
                                                        "k": "$$kv.k",
                                                        "v": ["in_app"],
                                                    },
                                                }
                                            }
                                        }
                                    }
                                },
                            },
                            {
                                "type": "update.contract",
                                "update": {
                                    "$set": {"status": "CANCELED", "state": "CANCELED"}
                                },
                            },
                            {
                                "type": "notify",
                                "notify": {
                                    "event": "contracts.trip_cancelled_by_driver",
                                    "targets": "$$ctx.doc.local.cancel_trip_targets",
                                    "payload": {
                                        "contract_code": {
                                            "$ctx": "doc.context.contract_code"
                                        }
                                    },
                                },
                            },
                        ],
                    },
                }
            },
            "IN_PROGRESS": {
                "events": {
                    "DriverAtPickup": {
                        "trigger": [
                            {
                                "type": "api",
                                "path": "driver-at-pickup",
                                "method": "POST",
                                "allow_principals": ["$$ctx.doc.context.driver"],
                                "response": {"ok": True, "event": "driver_at_pickup"},
                            }
                        ],
                        "effects": [
                            {
                                "type": "update.contract",
                                "update": {
                                    "$set": {"context.driver_in_pickup_zone": True}
                                },
                            },
                            {
                                "type": "unschedule.event",
                                "event_id": {
                                    "$ctx": "doc.context.driver_pickup_check_id"
                                },
                            },
                        ],
                    },
                    "RiderAtPickup": {
                        "trigger": [
                            {
                                "type": "api",
                                "path": "rider-at-pickup",
                                "method": "POST",
                                "allow_user_states": ["ACCEPTED"],
                                "response": {"ok": True, "event": "rider_at_pickup"},
                            }
                        ],
                        "effects": [
                            {
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "context.riders_in_pickup_zone.$$ctx.user": True
                                    }
                                },
                            }
                        ],
                    },
                    "DriverMarkPickedUp": {
                        "trigger": [
                            {
                                "type": "api",
                                "path": "driver-mark-picked-up",
                                "method": "POST",
                                "allow_principals": ["$$ctx.doc.context.driver"],
                                "payload_schema": {
                                    "type": "object",
                                    "required": ["principal"],
                                    "properties": {
                                        "principal": {
                                            "type": "string",
                                            "pattern": "^u:.+$",
                                        }
                                    },
                                    "additionalProperties": False,
                                },
                                "response": {
                                    "ok": True,
                                    "event": "driver_mark_picked_up",
                                },
                            }
                        ],
                        "effects": [
                            {
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "local.can_pick_user": {
                                            "$and": [
                                                {
                                                    "$eq": [
                                                        {
                                                            "$ifNull": [
                                                                {
                                                                    "$ctx": "doc.states.$$ctx.payload.principal"
                                                                },
                                                                "",
                                                            ]
                                                        },
                                                        "ACCEPTED",
                                                    ]
                                                },
                                                {
                                                    "$eq": [
                                                        {
                                                            "$ifNull": [
                                                                {
                                                                    "$ctx": "doc.context.riders_in_pickup_zone.$$ctx.payload.principal"
                                                                },
                                                                False,
                                                            ]
                                                        },
                                                        True,
                                                    ]
                                                },
                                            ]
                                        }
                                    }
                                },
                            },
                            {
                                "type": "if.else",
                                "condition": {"$ctx": "doc.local.can_pick_user"},
                                "then_effects": [
                                    {
                                        "type": "update.contract",
                                        "update": [
                                            {
                                                "$set": {
                                                    "context.riders_picked_up.$$ctx.payload.principal": True
                                                }
                                            },
                                            {
                                                "$unset": "context.pending_pickup_targets.$$ctx.payload.principal"
                                            },
                                        ],
                                    },
                                    {
                                        "type": "notify",
                                        "notify": {
                                            "event": "contracts.user_picked_up",
                                            "targets": {
                                                "$$ctx.payload.principal": ["in_app"]
                                            },
                                            "payload": {
                                                "contract_code": {
                                                    "$ctx": "doc.context.contract_code"
                                                }
                                            },
                                        },
                                    },
                                ],
                            },
                            {
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "local.all_riders_picked_up": {
                                            "$eq": [
                                                {
                                                    "$size": {
                                                        "$objectToArray": {
                                                            "$ifNull": [
                                                                "$context.pending_pickup_targets",
                                                                {},
                                                            ]
                                                        }
                                                    }
                                                },
                                                0,
                                            ]
                                        }
                                    }
                                },
                            },
                            {
                                "type": "if.else",
                                "condition": {"$ctx": "doc.local.all_riders_picked_up"},
                                "then_effects": [
                                    {
                                        "type": "unschedule.event",
                                        "event_id": {
                                            "$ctx": "doc.context.riders_pickup_check_id"
                                        },
                                    },
                                    {
                                        "type": "update.contract",
                                        "update": {
                                            "$set": {
                                                "state": "COMPLETED",
                                                "status": "COMPLETED",
                                            }
                                        },
                                    },
                                ],
                                "else_effects": [
                                    {
                                        "type": "update.contract",
                                        "update": {"$set": {"state": "IN_PROGRESS"}},
                                    }
                                ],
                            },
                        ],
                    },
                    "CancelUser": {
                        "trigger": [
                            {
                                "type": "api",
                                "path": "cancel-user",
                                "method": "POST",
                                "allow_user_states": ["ACCEPTED"],
                                "response": {"ok": True, "event": "cancel_user"},
                            }
                        ],
                        "effects": [
                            {
                                "type": "update.group",
                                "group_id": {"$ctx": "doc.context.group_id"},
                                "edit_members": {"remove_members": ["$$ctx.user"]},
                            },
                            {
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "local.cancel_seats": {
                                            **_rider_seats("$$ctx.user")
                                        }
                                    }
                                },
                            },
                            {
                                "type": "update.contract",
                                "update": [
                                    {
                                        "$set": {
                                            "context.accepted_seats_total": {
                                                **_accepted_total_after_subtract(
                                                    "cancel_seats"
                                                )
                                            },
                                            "states.$$ctx.user": "CANCELLED",
                                        }
                                    },
                                    {
                                        "$unset": [
                                            "context.riders.$$ctx.user.seats",
                                            "context.pending_pickup_targets.$$ctx.user",
                                            "context.riders_in_pickup_zone.$$ctx.user",
                                            "context.riders_picked_up.$$ctx.user",
                                        ]
                                    },
                                ],
                            },
                            {
                                "type": "notify",
                                "notify": {
                                    "event": "contracts.user_cancelled",
                                    "targets": {"$$ctx.doc.context.driver": ["in_app"]},
                                    "payload": {
                                        "principal": "$$ctx.user",
                                        "contract_code": {
                                            "$ctx": "doc.context.contract_code"
                                        },
                                    },
                                },
                            },
                        ],
                    },
                    "DriverPickupCheckTimed": {
                        "trigger": [
                            {"type": "api", "path": "driver-pickup-check-timeout"}
                        ],
                        "effects": [
                            {
                                "type": "if.else",
                                "condition": {
                                    "$eq": [
                                        {
                                            "$ifNull": [
                                                "$context.driver_in_pickup_zone",
                                                False,
                                            ]
                                        },
                                        False,
                                    ]
                                },
                                "then_effects": [
                                    {
                                        "type": "notify",
                                        "notify": {
                                            "event": "contracts.driver_pickup_check",
                                            "targets": {
                                                "$$ctx.doc.context.driver": ["in_app"]
                                            },
                                            "payload": {
                                                "contract_code": {
                                                    "$ctx": "doc.context.contract_code"
                                                }
                                            },
                                        },
                                    }
                                ],
                            }
                        ],
                    },
                    "RidersPickupCheckTimed": {
                        "trigger": [
                            {"type": "api", "path": "riders-pickup-check-timeout"}
                        ],
                        "effects": [
                            {
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "local.has_pending_pickups": {
                                            "$gt": [
                                                {
                                                    "$size": {
                                                        "$objectToArray": {
                                                            "$ifNull": [
                                                                "$context.pending_pickup_targets",
                                                                {},
                                                            ]
                                                        }
                                                    }
                                                },
                                                0,
                                            ]
                                        }
                                    }
                                },
                            },
                            {
                                "type": "if.else",
                                "condition": {"$ctx": "doc.local.has_pending_pickups"},
                                "then_effects": [
                                    {
                                        "type": "notify",
                                        "notify": {
                                            "event": "contracts.rider_pickup_check",
                                            "targets": "$$ctx.doc.context.pending_pickup_targets",
                                            "payload": {
                                                "contract_code": {
                                                    "$ctx": "doc.context.contract_code"
                                                }
                                            },
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                    "DriverCancelTrip": {
                        "trigger": [
                            {
                                "type": "api",
                                "path": "driver-cancel-trip",
                                "method": "POST",
                                "allow_principals": ["$$ctx.doc.context.driver"],
                                "response": {"ok": True, "event": "driver_cancel_trip"},
                            }
                        ],
                        "effects": [
                            {
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "local.cancel_trip_targets": {
                                            "$arrayToObject": {
                                                "$map": {
                                                    "input": {
                                                        "$filter": {
                                                            "input": {
                                                                "$objectToArray": "$states"
                                                            },
                                                            "as": "kv",
                                                            "cond": {
                                                                "$eq": [
                                                                    "$$kv.v",
                                                                    "ACCEPTED",
                                                                ]
                                                            },
                                                        }
                                                    },
                                                    "as": "kv",
                                                    "in": {
                                                        "k": "$$kv.k",
                                                        "v": ["in_app"],
                                                    },
                                                }
                                            }
                                        }
                                    }
                                },
                            },
                            {
                                "type": "update.contract",
                                "update": {
                                    "$set": {"status": "CANCELED", "state": "CANCELED"}
                                },
                            },
                            {
                                "type": "notify",
                                "notify": {
                                    "event": "contracts.trip_cancelled_by_driver",
                                    "targets": "$$ctx.doc.local.cancel_trip_targets",
                                    "payload": {
                                        "contract_code": {
                                            "$ctx": "doc.context.contract_code"
                                        }
                                    },
                                },
                            },
                        ],
                    },
                }
            },
            "REJECTED": {"final": True},
            "EXPIRED": {"final": True},
            "COMPLETED": {"final": True},
        },
    }


class ContractsE2ETest(unittest.TestCase):
    _mongo_container: Any = None
    _mongo_base_uri: str = ""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        desktop_sock = os.path.join(
            os.path.expanduser("~"), ".docker", "run", "docker.sock"
        )
        if not os.environ.get("DOCKER_HOST") and os.path.exists(desktop_sock):
            os.environ["DOCKER_HOST"] = f"unix://{desktop_sock}"
        try:
            from testcontainers.mongodb import MongoDbContainer
        except Exception as ex:  # pragma: no cover - environment dependent
            raise unittest.SkipTest(
                "contracts e2e requires testcontainers[mongodb]"
            ) from ex

        try:
            cls._mongo_container = MongoDbContainer("mongo:7.0")
            cls._mongo_container.start()
            cls._mongo_base_uri = str(cls._mongo_container.get_connection_url())
        except Exception as ex:  # pragma: no cover - environment dependent
            raise unittest.SkipTest(
                "contracts e2e requires Docker with a runnable MongoDB container"
            ) from ex

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            if cls._mongo_container is not None:
                cls._mongo_container.stop()
        finally:
            cls._mongo_container = None
            cls._mongo_base_uri = ""
            super().tearDownClass()

    def _test_mongo_uri(self) -> str:
        self.mongo_db_name = f"schedula_contracts_{uuid.uuid4().hex}"
        parts = urlsplit(self.__class__._mongo_base_uri)
        query = parts.query
        if "authSource=" not in query:
            query = f"{query}&authSource=admin" if query else "authSource=admin"
        return urlunsplit(
            (
                parts.scheme,
                parts.netloc,
                f"/{self.mongo_db_name}",
                query,
                parts.fragment,
            )
        )

    def setUp(self) -> None:
        os.environ.pop("MONGO_URI", None)
        self.app = Flask("contracts_test")
        self.mongo_uri = self._test_mongo_uri()
        from pymongo import MongoClient

        self.mongo_client = MongoClient(self.mongo_uri)
        config = dict(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI="sqlite+pysqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            SECURITY_ENABLED=True,
            SECURITY_REGISTERABLE=True,
            SECURITY_SEND_REGISTER_EMAIL=False,
            SECURITY_CONFIRMABLE=True,
            SECURITY_RECOVERABLE=True,
            SECURITY_CHANGEABLE=True,
            SECURITY_LOGIN_AFTER_REGISTER=False,
            SECURITY_URL_PREFIX="/user",
            WTF_CSRF_ENABLED=False,
            SCHEDULA_CSRF_ENABLED=False,
            ITEMS_STORAGE_ENABLED=True,
            FILES_STORAGE_ENABLED=False,
            S3_ITEMS_FILE_STORAGE=False,
            CONTACT_ENABLED=False,
            SCHEDULA_CREDITS_ENABLED=True,
            SCHEDULA_EXPORT_FORM_ENABLED=False,
            SCHEDULA_GDPR_ENABLED=False,
            SCHEDULA_LOCALE_ENABLED=False,
            SCHEDULA_SECRETS_ENABLED=False,
            OPENAPI_ENABLED=False,
            CASBIN_ADMIN_ENABLED=False,
            STRIPE_SECRET_KEY="sk_test_dummy",
            STRIPE_PUBLISHABLE_KEY="pk_test_dummy",
            STRIPE_WEBHOOK_SECRET_KEY="whsec_dummy",
            MONGO_URI=self.mongo_uri,
        )
        sitemap = DummySitemap()
        setattr(sitemap, "stripe_event_handler", staticmethod(lambda _event: None))
        basic_app(sitemap, self.app, config)

        self._patchers = [
            patch(
                "schedula.utils.form.server.credits.Lock",
                new=lambda *_args, **_kwargs: contextlib.nullcontext(),
            )
        ]
        for patcher in self._patchers:
            patcher.start()

        with self.app.app_context():
            _db.create_all()
            ensure_public_group()
            owner = self._create_user("owner-1@gmail.com")
            user = self._create_user("u1@gmail.com")
            admin = self._create_user("admin@gmail.com")
            d1 = self._create_user("d1@gmail.com")
            p1 = self._create_user("p1@gmail.com")
            p2 = self._create_user("p2@gmail.com")
            p3 = self._create_user("p3@gmail.com")
            p4 = self._create_user("p4@gmail.com")
            for u in (owner, user, admin, d1, p1, p2, p3, p4):
                bootstrap_user(u.id)
            set_system_admin(admin.id, enabled=True)
            enforcer = get_enforcer()
            enforcer.add_policy(
                [ANON_USER, ADMIN_DOMAIN, "contracts:templates", "manage", "allow"]
            )
            self.user_ids = {
                "owner-1": owner.id,
                "u1": user.id,
                "admin": admin.id,
                "d1": d1.id,
                "p1": p1.id,
                "p2": p2.id,
                "p3": p3.id,
                "p4": p4.id,
            }

        self.httpx = httpx.Client(
            transport=httpx.WSGITransport(app=self.app),
            base_url="http://test",
        )
        self.client = self.app.test_client(use_cookies=False)
        self.tokens = {
            "owner-1": self._login_token("owner-1@gmail.com"),
            "u1": self._login_token("u1@gmail.com"),
            "admin": self._login_token("admin@gmail.com"),
            "d1": self._login_token("d1@gmail.com"),
            "p1": self._login_token("p1@gmail.com"),
            "p2": self._login_token("p2@gmail.com"),
            "p3": self._login_token("p3@gmail.com"),
            "p4": self._login_token("p4@gmail.com"),
        }

    def tearDown(self) -> None:
        try:
            self.httpx.close()
        except Exception:
            pass
        with self.app.app_context():
            _db.session.remove()
            _db.drop_all()
        for patcher in getattr(self, "_patchers", []):
            patcher.stop()
        try:
            from pymongo import MongoClient

            client = MongoClient(self.mongo_uri)
            client.drop_database(self.mongo_db_name)
            client.close()
        except Exception:
            pass
        try:
            self.mongo_client.close()
        except Exception:
            pass

    def _create_user(self, email: str) -> User:
        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(
                email=email,
                password=hash_password("UserPass123!"),
                active=True,
                fs_uniquifier=str(uuid.uuid4()),
            )
            _db.session.add(user)
        user.confirmed_at = dt.datetime.utcnow()
        _db.session.commit()
        return user

    def _login_token(self, email: str) -> str:
        resp = self.client.post(
            "/user/login", json={"email": email, "password": "UserPass123!"}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json(silent=True) or {}
        token = data.get("response", {}).get("user", {}).get("token")
        self.assertIsNotNone(token)
        return str(token)

    def _headers(self, actor: str) -> Dict[str, str]:
        return {"Authentication-Token": self.tokens[actor]}

    def _create_template(self, definition: Dict[str, Any], **extra: Any) -> str:
        body = {
            "name": f"tpl-{uuid.uuid4()}",
            "definition": definition,
            "is_enabled": True,
        }
        body.update(extra)
        resp = self.httpx.post(
            "/contracts/templates", json=body, headers=self._headers("admin")
        )
        self.assertEqual(resp.status_code, 201, msg=resp.text)
        return str(resp.json()["id"])

    def _create_contract(
        self, template_id: str, context: Dict[str, Any], **extra: Any
    ) -> httpx.Response:
        body = {"context": context}
        body.update(extra)
        return self.httpx.post(
            f"/contracts/{template_id}",
            json=body,
            headers=self._headers("owner-1"),
        )

    def _post_event(
        self,
        contract_id: str,
        path: str,
        *,
        actor: str,
        payload: Dict[str, Any] | None = None,
    ) -> httpx.Response:
        if payload is None and path in {"accept-user", "request-join"}:
            payload = {
                "seats": 1,
                "origin": {"lat": 45.0, "lng": 9.0},
                "destination": {"lat": 45.1, "lng": 9.1},
            }
        return self.httpx.post(
            f"/contracts/{contract_id}/{path}",
            json={"payload": payload or {}},
            headers=self._headers(actor),
        )

    def _group_member_ids(self, gid: str) -> set[str]:
        raw_gid = gid[2:] if gid.startswith("g:") else gid
        with self.app.app_context():
            grp = _db.session.get(Group, raw_gid)
            self.assertIsNotNone(grp)
            assert grp is not None
            members = grp.members(models=False)
            out: set[str] = set()
            for m in members:
                if not isinstance(m, dict):
                    continue
                mid = m.get("id")
                if isinstance(mid, str) and mid.startswith("u:"):
                    out.add(mid)
            return out

    def _user_state(self, contract: Dict[str, Any], user_id: int) -> str:
        return str((contract.get("states") or {}).get(f"u:{user_id}") or "")

    def _count_notifications_for(self, principal: str, event: str) -> int:
        with self.app.app_context():
            coll = self.app.config["MONGO_DB"]["notifications"]
            return int(
                coll.count_documents(
                    {"event": event, f"targets.{principal}": {"$exists": True}}
                )
            )

    def _gherkin_context(self, initial_state: str = "START") -> Dict[str, Any]:
        driver_uid = self.user_ids["d1"]
        p1_uid = self.user_ids["p1"]
        rider_ids = [f"u:{p1_uid}"]
        riders = {
            principal: {
                "seats": 1,
                "trip": {
                    "origin": {"lat": 45.0, "lng": 9.0},
                    "destination": {"lat": 45.1, "lng": 9.1},
                },
            }
            for principal in rider_ids
        }
        return {
            "contract_code": "C-001",
            "capacity": 3,
            "driver": f"u:{driver_uid}",
            "driver_trip": {
                "origin": {"lat": 45.2, "lng": 9.2},
                "destination": {"lat": 45.3, "lng": 9.3},
            },
            "riders": riders,
        }

    def _create_gherkin_contract(self, initial_state: str = "START") -> str:
        definition = _gherkin_definition()
        template_id = self._create_template(
            definition,
            allowed_initial_states=["START"],
        )
        created = self._create_contract(
            template_id,
            self._gherkin_context(initial_state=initial_state),
            initial_state=initial_state,
        )
        self.assertEqual(created.status_code, 201)
        return str(created.json()["id"])

    def _to_recruiting(self, cid: str) -> str:
        self.assertEqual(
            self._post_event(cid, "driver-accept-start", actor="d1").status_code,
            200,
        )
        self.assertEqual(
            self._post_event(cid, "accept-user", actor="p1").status_code, 200
        )
        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        self.assertEqual(c["state"], "RECRUITING")
        gid = str((c.get("context") or {}).get("group_id") or "")
        self.assertTrue(gid)
        return gid

    def _to_ready(self, cid: str) -> str:
        gid = self._to_recruiting(cid)
        self.assertEqual(
            self._post_event(
                cid,
                "invite-user",
                actor="d1",
                payload={"principal": f"u:{self.user_ids['p2']}"},
            ).status_code,
            200,
        )
        self.assertEqual(
            self._post_event(cid, "accept-user", actor="p2").status_code, 200
        )
        self.assertEqual(
            self._post_event(
                cid,
                "invite-user",
                actor="d1",
                payload={"principal": f"u:{self.user_ids['p3']}"},
            ).status_code,
            200,
        )
        self.assertEqual(
            self._post_event(cid, "accept-user", actor="p3").status_code, 200
        )
        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        self.assertEqual(c["state"], "READY")
        return gid

    def test_template_create_list_get_update(self) -> None:
        template_id = self._create_template(_definition())
        listed = self.httpx.get("/contracts/templates", headers=self._headers("admin"))
        self.assertEqual(listed.status_code, 200)
        self.assertIn(
            template_id, [t["id"] for t in listed.json().get("templates", [])]
        )

        one = self.httpx.get(
            f"/contracts/templates/{template_id}", headers=self._headers("admin")
        )
        self.assertEqual(one.status_code, 200)
        self.assertEqual(one.json()["id"], template_id)

        upd = self.httpx.put(
            f"/contracts/templates/{template_id}",
            json={"is_enabled": False},
            headers=self._headers("admin"),
        )
        self.assertEqual(upd.status_code, 200)
        self.assertFalse(upd.json()["is_enabled"])

    def test_create_contract_and_initial_state_guard(self) -> None:
        template_id = self._create_template(
            _definition(),
            allowed_initial_states=["S1"],
        )
        ok = self._create_contract(template_id, {"owner": "x"})
        self.assertEqual(ok.status_code, 201)

        bad = self._create_contract(template_id, {"owner": "x"}, initial_state="S999")
        self.assertEqual(bad.status_code, 409)

    def test_context_validation_by_initial_state(self) -> None:
        definition = {
            "id": "context-by-initial-state",
            "version": "1.0",
            "initial_state": "S1",
            "states": {
                "S1": {
                    "on_enter": {
                        "context_schema": {
                            "type": "object",
                            "required": ["requester"],
                            "properties": {
                                "requester": {"type": "string", "pattern": "^u:.+$"}
                            },
                            "additionalProperties": True,
                        }
                    },
                    "events": {},
                },
                "S2": {
                    "on_enter": {
                        "context_schema": {
                            "type": "object",
                            "required": ["driver"],
                            "properties": {
                                "driver": {"type": "string", "pattern": "^u:.+$"}
                            },
                            "additionalProperties": True,
                        }
                    },
                    "events": {},
                },
            },
        }
        template_id = self._create_template(definition, allowed_initial_states=["S2"])

        invalid = self._create_contract(template_id, {"driver": "u:1"})
        self.assertEqual(invalid.status_code, 422)

        valid = self._create_contract(
            template_id,
            {"driver": "u:1"},
            initial_state="S2",
        )
        self.assertEqual(valid.status_code, 201)

    def test_event_ping_returns_200(self) -> None:
        template_id = self._create_template(_definition())
        created = self._create_contract(template_id, {"seed": 1})
        self.assertEqual(created.status_code, 201)
        cid = created.json()["id"]

        event = self.httpx.post(
            f"/contracts/{cid}/ping",
            json={"payload": {}},
            headers=self._headers("u1"),
        )
        self.assertEqual(event.status_code, 200)

    def test_cancel_contract_blocks_events(self) -> None:
        template_id = self._create_template(_definition())
        created = self._create_contract(template_id, {"seed": 1})
        cid = created.json()["id"]

        cancel = self.httpx.delete(
            f"/contracts/{cid}", headers=self._headers("owner-1")
        )
        self.assertEqual(cancel.status_code, 200)
        self.assertEqual(cancel.json().get("status"), "CANCELED")

        event = self.httpx.post(
            f"/contracts/{cid}/ping",
            json={"payload": {}},
            headers=self._headers("u1"),
        )
        self.assertEqual(event.status_code, 410)

    def test_history_and_effects_endpoints_removed(self) -> None:
        template_id = self._create_template(_definition())
        created = self._create_contract(template_id, {"seed": 1})
        cid = created.json()["id"]

        history = self.httpx.get(
            f"/contracts/{cid}/history", headers=self._headers("owner-1")
        )
        self.assertIn(history.status_code, (404, 405, 409))

        effects = self.httpx.get(
            f"/contracts/{cid}/effects", headers=self._headers("owner-1")
        )
        self.assertIn(effects.status_code, (404, 405, 409))

    def test_cron_tick_fires_due_event(self) -> None:
        definition = {
            "id": "contract-cron",
            "version": "1.0",
            "initial_state": "S1",
            "states": {
                "S1": {
                    "events": {
                        "ScheduleClose": {
                            "trigger": [{"type": "api", "path": "schedule-close"}],
                            "effects": [
                                {
                                    "type": "schedule.event",
                                    "key": "close_event_id",
                                    "event_name": "CloseNow",
                                    "cron": "* * * * *",
                                },
                                {
                                    "type": "update.contract",
                                    "update": {
                                        "$set": {
                                            "context.close_event_id": {
                                                "$ctx": "local.close_event_id"
                                            }
                                        }
                                    },
                                },
                            ],
                        },
                        "CloseNow": {
                            "trigger": [{"type": "api", "path": "close-now"}],
                            "effects": [
                                {
                                    "type": "update.contract",
                                    "update": {"$set": {"state": "S_FINAL"}},
                                }
                            ],
                        },
                    }
                },
                "S_FINAL": {"final": True},
            },
        }
        template_id = self._create_template(definition)
        created = self._create_contract(template_id, {"seed": 1})
        self.assertEqual(created.status_code, 201)
        cid = created.json()["id"]

        scheduled = self._post_event(cid, "schedule-close", actor="u1")
        self.assertEqual(scheduled.status_code, 200)

        tick = self.httpx.post(
            "/contracts/cron/tick",
            headers=self._headers("admin"),
        )
        self.assertEqual(tick.status_code, 200)
        self.assertGreaterEqual(int(tick.json().get("fired", 0)), 1)

        got = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1"))
        self.assertEqual(got.status_code, 200)
        self.assertEqual(got.json().get("state"), "S_FINAL")

    def test_schedule_event_effect_creates_and_fires_scheduled_entry(self) -> None:
        definition = {
            "id": "contract-schedule-event",
            "version": "1.0",
            "initial_state": "S1",
            "states": {
                "S1": {
                    "events": {
                        "ScheduleClose": {
                            "trigger": [{"type": "api", "path": "schedule-close"}],
                            "effects": [
                                {
                                    "type": "schedule.event",
                                    "key": "scheduled_close_id",
                                    "event_name": "CloseNow",
                                    "cron": "* * * * *",
                                    "actor_id": "system:cron",
                                },
                                {
                                    "type": "update.contract",
                                    "update": {
                                        "$set": {
                                            "context.scheduled_close_id": {
                                                "$ctx": "local.scheduled_close_id"
                                            }
                                        }
                                    },
                                },
                            ],
                        },
                        "CloseNow": {
                            "trigger": [{"type": "api", "path": "close-now"}],
                            "effects": [
                                {
                                    "type": "update.contract",
                                    "update": {"$set": {"state": "S_FINAL"}},
                                }
                            ],
                        },
                    }
                },
                "S_FINAL": {"final": True},
            },
        }
        template_id = self._create_template(definition)
        created = self._create_contract(template_id, {"seed": 1})
        self.assertEqual(created.status_code, 201)
        cid = created.json()["id"]

        schedule = self._post_event(cid, "schedule-close", actor="u1")
        self.assertEqual(schedule.status_code, 200)
        with self.app.app_context():
            raw = self.app.config["MONGO_DB"]["contracts"].find_one({"_id": cid}) or {}
        scheduled_id = str((raw.get("context") or {}).get("scheduled_close_id") or "")
        self.assertTrue(scheduled_id)
        close_1 = (raw.get("scheduled_events") or {}).get(scheduled_id) or {}
        self.assertEqual(close_1.get("event_name"), "CloseNow")
        self.assertEqual(close_1.get("cron"), "* * * * *")

        tick = self.httpx.post("/contracts/cron/tick", headers=self._headers("admin"))
        self.assertEqual(tick.status_code, 200)
        got = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1"))
        self.assertEqual(got.status_code, 200)
        self.assertEqual(got.json().get("state"), "S_FINAL")

    def test_unschedule_event_effect_removes_scheduled_entry(self) -> None:
        definition = {
            "id": "contract-unschedule-event",
            "version": "1.0",
            "initial_state": "S1",
            "states": {
                "S1": {
                    "events": {
                        "ScheduleClose": {
                            "trigger": [{"type": "api", "path": "schedule-close"}],
                            "effects": [
                                {
                                    "type": "schedule.event",
                                    "key": "scheduled_close_id",
                                    "event_name": "CloseNow",
                                    "cron": "* * * * *",
                                },
                                {
                                    "type": "update.contract",
                                    "update": {
                                        "$set": {
                                            "context.scheduled_close_id": {
                                                "$ctx": "local.scheduled_close_id"
                                            }
                                        }
                                    },
                                },
                            ],
                        },
                        "UnscheduleClose": {
                            "trigger": [{"type": "api", "path": "unschedule-close"}],
                            "effects": [
                                {
                                    "type": "unschedule.event",
                                    "event_id": {
                                        "$ctx": "doc.context.scheduled_close_id"
                                    },
                                }
                            ],
                        },
                        "CloseNow": {
                            "trigger": [{"type": "api", "path": "close-now"}],
                            "effects": [
                                {
                                    "type": "update.contract",
                                    "update": {"$set": {"state": "S_FINAL"}},
                                }
                            ],
                        },
                    }
                },
                "S_FINAL": {"final": True},
            },
        }
        template_id = self._create_template(definition)
        created = self._create_contract(template_id, {"seed": 1})
        self.assertEqual(created.status_code, 201)
        cid = created.json()["id"]

        self.assertEqual(
            self._post_event(cid, "schedule-close", actor="u1").status_code,
            200,
        )
        self.assertEqual(
            self._post_event(cid, "unschedule-close", actor="u1").status_code,
            200,
        )
        with self.app.app_context():
            raw = self.app.config["MONGO_DB"]["contracts"].find_one({"_id": cid}) or {}
        scheduled_id = str((raw.get("context") or {}).get("scheduled_close_id") or "")
        self.assertTrue(scheduled_id)
        self.assertNotIn(scheduled_id, (raw.get("scheduled_events") or {}))

        tick = self.httpx.post("/contracts/cron/tick", headers=self._headers("admin"))
        self.assertEqual(tick.status_code, 200)
        got = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1"))
        self.assertEqual(got.status_code, 200)
        self.assertEqual(got.json().get("state"), "S1")

    def test_if_else_effect_selects_chain_by_condition(self) -> None:
        definition = {
            "id": "contract-if-else",
            "version": "1.0",
            "initial_state": "S1",
            "states": {
                "S1": {
                    "events": {
                        "Decide": {
                            "trigger": [{"type": "api", "path": "decide"}],
                            "effects": [
                                {
                                    "type": "if.else",
                                    "condition": {"$ctx": "doc.context.auto_ready"},
                                    "then_effects": [
                                        {
                                            "type": "update.contract",
                                            "update": {"$set": {"state": "READY"}},
                                        }
                                    ],
                                    "else_effects": [
                                        {
                                            "type": "update.contract",
                                            "update": {"$set": {"state": "RECRUITING"}},
                                        }
                                    ],
                                }
                            ],
                        }
                    }
                },
                "RECRUITING": {"events": {}},
                "READY": {"events": {}},
            },
        }
        template_id = self._create_template(definition)

        c1 = self._create_contract(template_id, {"auto_ready": True})
        self.assertEqual(c1.status_code, 201)
        cid1 = c1.json()["id"]
        self.assertEqual(self._post_event(cid1, "decide", actor="u1").status_code, 200)
        got1 = self.httpx.get(f"/contracts/{cid1}", headers=self._headers("owner-1"))
        self.assertEqual(got1.status_code, 200)
        self.assertEqual(got1.json().get("state"), "READY")

        c2 = self._create_contract(template_id, {"auto_ready": False})
        self.assertEqual(c2.status_code, 201)
        cid2 = c2.json()["id"]
        self.assertEqual(self._post_event(cid2, "decide", actor="u1").status_code, 200)
        got2 = self.httpx.get(f"/contracts/{cid2}", headers=self._headers("owner-1"))
        self.assertEqual(got2.status_code, 200)
        self.assertEqual(got2.json().get("state"), "RECRUITING")

    def test_contract_lifecycle_group_sync_via_api_template(self) -> None:
        driver_uid = self.user_ids["d1"]
        p1_uid = self.user_ids["p1"]
        p2_uid = self.user_ids["p2"]
        p3_uid = self.user_ids["p3"]

        context = self._gherkin_context(initial_state="START")

        definition = _gherkin_definition()

        template_id = self._create_template(
            definition,
            allowed_initial_states=["START"],
        )
        created = self._create_contract(
            template_id,
            context,
            initial_state="START",
        )
        self.assertEqual(created.status_code, 201)
        cid = created.json()["id"]

        c1 = self.httpx.get(
            f"/contracts/{cid}", headers=self._headers("owner-1")
        ).json()
        self.assertEqual(c1["state"], "START")
        self.assertIsNone((c1["context"] or {}).get("group_id"))

        r2 = self._post_event(cid, "driver-accept-start", actor="d1")
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(
            self._post_event(cid, "accept-user", actor="p1").status_code, 200
        )
        c2 = self.httpx.get(
            f"/contracts/{cid}", headers=self._headers("owner-1")
        ).json()
        self.assertEqual(c2["state"], "RECRUITING")
        gid = str((c2["context"] or {}).get("group_id") or "")
        self.assertTrue(gid)
        self.assertSetEqual(
            self._group_member_ids(gid),
            {f"u:{driver_uid}", f"u:{p1_uid}"},
        )

        self.assertEqual(
            self._post_event(
                cid,
                "invite-user",
                actor="d1",
                payload={"principal": f"u:{p2_uid}"},
            ).status_code,
            200,
        )
        c3 = self.httpx.get(
            f"/contracts/{cid}", headers=self._headers("owner-1")
        ).json()
        self.assertEqual(self._user_state(c3, p2_uid), "PENDING")
        self.assertSetEqual(
            self._group_member_ids(gid),
            {f"u:{driver_uid}", f"u:{p1_uid}"},
        )

        self.assertEqual(
            self._post_event(cid, "accept-user", actor="p2").status_code, 200
        )
        c4 = self.httpx.get(
            f"/contracts/{cid}", headers=self._headers("owner-1")
        ).json()
        self.assertEqual(self._user_state(c4, p2_uid), "ACCEPTED")
        self.assertSetEqual(
            self._group_member_ids(gid),
            {f"u:{driver_uid}", f"u:{p1_uid}", f"u:{p2_uid}"},
        )

        self.assertEqual(
            self._post_event(
                cid,
                "invite-user",
                actor="d1",
                payload={"principal": f"u:{p3_uid}"},
            ).status_code,
            200,
        )
        self.assertEqual(
            self._post_event(cid, "accept-user", actor="p3").status_code, 200
        )
        c5 = self.httpx.get(
            f"/contracts/{cid}", headers=self._headers("owner-1")
        ).json()
        self.assertEqual(c5["state"], "READY")
        self.assertEqual(self._user_state(c5, p3_uid), "ACCEPTED")
        self.assertSetEqual(
            self._group_member_ids(gid),
            {f"u:{driver_uid}", f"u:{p1_uid}", f"u:{p2_uid}", f"u:{p3_uid}"},
        )

        self.assertEqual(
            self._post_event(cid, "set-recruiting", actor="d1").status_code, 200
        )
        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        self.assertEqual(c["state"], "RECRUITING")
        self.assertSetEqual(
            self._group_member_ids(gid),
            {f"u:{driver_uid}", f"u:{p1_uid}", f"u:{p2_uid}", f"u:{p3_uid}"},
        )

        self.assertEqual(
            self._post_event(cid, "set-ready", actor="d1").status_code, 200
        )
        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        self.assertEqual(c["state"], "READY")
        self.assertSetEqual(
            self._group_member_ids(gid),
            {f"u:{driver_uid}", f"u:{p1_uid}", f"u:{p2_uid}", f"u:{p3_uid}"},
        )

        self.assertEqual(
            self._post_event(cid, "cancel-user", actor="p2").status_code, 200
        )
        c6 = self.httpx.get(
            f"/contracts/{cid}", headers=self._headers("owner-1")
        ).json()
        self.assertEqual(c6["state"], "RECRUITING")
        self.assertEqual(self._user_state(c6, p2_uid), "CANCELLED")
        self.assertSetEqual(
            self._group_member_ids(gid),
            {f"u:{driver_uid}", f"u:{p1_uid}", f"u:{p3_uid}"},
        )

    def test_wf1_happy_path_reaches_ready_with_group_sync(self) -> None:
        driver_uid = self.user_ids["d1"]
        p1_uid = self.user_ids["p1"]
        p2_uid = self.user_ids["p2"]
        p3_uid = self.user_ids["p3"]
        cid = self._create_gherkin_contract()

        gid = self._to_ready(cid)
        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        self.assertEqual(c["state"], "READY")
        self.assertEqual(self._user_state(c, p1_uid), "ACCEPTED")
        self.assertEqual(self._user_state(c, p2_uid), "ACCEPTED")
        self.assertEqual(self._user_state(c, p3_uid), "ACCEPTED")
        self.assertSetEqual(
            self._group_member_ids(gid),
            {f"u:{driver_uid}", f"u:{p1_uid}", f"u:{p2_uid}", f"u:{p3_uid}"},
        )

    def test_wf1_request_ride_notifies_driver(self) -> None:
        driver_uid = self.user_ids["d1"]
        driver_principal = f"u:{driver_uid}"
        p1_uid = self.user_ids["p1"]
        event = "contracts.request_ride"

        before = self._count_notifications_for(driver_principal, event)
        cid = self._create_gherkin_contract(initial_state="START")
        after = self._count_notifications_for(driver_principal, event)

        self.assertEqual(after, before + 1)
        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        self.assertEqual(c["state"], "START")
        self.assertEqual(self._user_state(c, driver_uid), "PENDING_DRIVER")
        self.assertEqual(self._user_state(c, p1_uid), "REQUESTING")

    def test_start_driver_initiated_sets_driver_and_pending_users(self) -> None:
        owner_uid = self.user_ids["owner-1"]
        p2_uid = self.user_ids["p2"]
        p2_principal = f"u:{p2_uid}"
        invited_event = "contracts.user_invited"
        before = self._count_notifications_for(p2_principal, invited_event)

        context = self._gherkin_context(initial_state="START")
        context["driver"] = f"u:{owner_uid}"
        context["riders"] = {
            p2_principal: {
                "seats": 1,
                "trip": {
                    "origin": {"lat": 45.0, "lng": 9.0},
                    "destination": {"lat": 45.1, "lng": 9.1},
                },
            }
        }

        definition = _gherkin_definition()
        template_id = self._create_template(
            definition, allowed_initial_states=["START"]
        )
        created = self._create_contract(template_id, context, initial_state="START")
        self.assertEqual(created.status_code, 201)
        cid = str(created.json()["id"])

        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        self.assertEqual(c["state"], "RECRUITING")
        self.assertEqual(self._user_state(c, owner_uid), "DRIVER")
        self.assertEqual(self._user_state(c, p2_uid), "PENDING")

        after = self._count_notifications_for(p2_principal, invited_event)
        self.assertEqual(after, before + 1)

    def test_start_driver_accept_then_rider_must_confirm(self) -> None:
        cid = self._create_gherkin_contract(initial_state="START")
        p1_uid = self.user_ids["p1"]

        self.assertEqual(
            self._post_event(cid, "driver-accept-start", actor="d1").status_code,
            200,
        )
        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        self.assertEqual(c["state"], "RECRUITING")
        self.assertEqual(self._user_state(c, p1_uid), "PENDING")

        self.assertEqual(
            self._post_event(cid, "accept-user", actor="p1").status_code, 200
        )
        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        self.assertEqual(c["state"], "RECRUITING")
        self.assertEqual(self._user_state(c, p1_uid), "ACCEPTED")

    def test_start_cancel_last_requester_re_notifies_driver(self) -> None:
        driver_principal = f"u:{self.user_ids['d1']}"
        event = "contracts.request_ride"
        before = self._count_notifications_for(driver_principal, event)

        cid = self._create_gherkin_contract(initial_state="START")
        after_create = self._count_notifications_for(driver_principal, event)
        self.assertEqual(after_create, before + 1)

        self.assertEqual(
            self._post_event(cid, "cancel-join-request", actor="p1").status_code,
            200,
        )

        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        self.assertEqual(c["state"], "START")
        self.assertFalse((c.get("context") or {}).get("riders"))

        after_cancel = self._count_notifications_for(driver_principal, event)
        self.assertEqual(after_cancel, before + 2)

    def test_start_request_join_sets_requesting_and_notifies_driver(self) -> None:
        driver_principal = f"u:{self.user_ids['d1']}"
        event = "contracts.join_requested"
        before = self._count_notifications_for(driver_principal, event)

        cid = self._create_gherkin_contract(initial_state="START")
        self.assertEqual(
            self._post_event(cid, "request-join", actor="p4").status_code, 200
        )

        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        self.assertEqual(c["state"], "START")
        self.assertEqual(self._user_state(c, self.user_ids["p4"]), "REQUESTING")

        after = self._count_notifications_for(driver_principal, event)
        self.assertEqual(after, before + 1)

    def test_wf2_first_request_rejected_no_group(self) -> None:
        p1 = self.user_ids["p1"]
        definition = _gherkin_definition()
        template_id = self._create_template(
            definition,
            allowed_initial_states=["START"],
        )
        created = self._create_contract(
            template_id,
            self._gherkin_context(initial_state="START"),
            initial_state="START",
        )
        cid = created.json()["id"]
        self.assertEqual(
            self._post_event(cid, "driver-reject-start", actor="d1").status_code,
            200,
        )
        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        self.assertEqual(c["state"], "REJECTED")
        self.assertIsNone((c.get("context") or {}).get("group_id"))

    def test_wf3_start_has_no_timeout_via_cron(self) -> None:
        p1 = self.user_ids["p1"]
        definition = _gherkin_definition()
        template_id = self._create_template(
            definition,
            allowed_initial_states=["START"],
        )
        created = self._create_contract(
            template_id,
            self._gherkin_context(initial_state="START"),
            initial_state="START",
        )
        cid = created.json()["id"]
        tick = self.httpx.post("/contracts/cron/tick", headers=self._headers("admin"))
        self.assertEqual(tick.status_code, 200)
        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        self.assertEqual(c["state"], "START")
        self.assertEqual(self._user_state(c, p1), "REQUESTING")
        self.assertIsNone((c.get("context") or {}).get("group_id"))

    def test_wf4_invite_timeout_expires_p2_and_keeps_group(self) -> None:
        driver_uid = self.user_ids["d1"]
        p1_uid = self.user_ids["p1"]
        p2_uid = self.user_ids["p2"]
        definition = _gherkin_definition()
        template_id = self._create_template(
            definition,
            allowed_initial_states=["START"],
        )
        created = self._create_contract(
            template_id,
            self._gherkin_context(initial_state="START"),
            initial_state="START",
        )
        cid = created.json()["id"]
        self.assertEqual(
            self._post_event(cid, "driver-accept-start", actor="d1").status_code,
            200,
        )
        self.assertEqual(
            self._post_event(cid, "accept-user", actor="p1").status_code, 200
        )
        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        gid = str((c.get("context") or {}).get("group_id") or "")
        self.assertTrue(gid)

        self.assertEqual(
            self._post_event(
                cid,
                "invite-user",
                actor="d1",
                payload={"principal": f"u:{p2_uid}"},
            ).status_code,
            200,
        )
        tick = self.httpx.post("/contracts/cron/tick", headers=self._headers("admin"))
        self.assertEqual(tick.status_code, 200)

        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        self.assertEqual(c["state"], "RECRUITING")
        self.assertEqual(self._user_state(c, p2_uid), "EXPIRED")
        self.assertSetEqual(
            self._group_member_ids(gid), {f"u:{driver_uid}", f"u:{p1_uid}"}
        )
        self.assertNotIn(f"u:{p2_uid}", self._group_member_ids(gid))

    def test_wf5_invite_reject_sets_p2_rejected_and_keeps_group(self) -> None:
        driver_uid = self.user_ids["d1"]
        p1_uid = self.user_ids["p1"]
        p2_uid = self.user_ids["p2"]
        definition = _gherkin_definition()
        template_id = self._create_template(
            definition,
            allowed_initial_states=["START"],
        )
        created = self._create_contract(
            template_id,
            self._gherkin_context(initial_state="START"),
            initial_state="START",
        )
        cid = created.json()["id"]
        self.assertEqual(
            self._post_event(cid, "driver-accept-start", actor="d1").status_code,
            200,
        )
        self.assertEqual(
            self._post_event(cid, "accept-user", actor="p1").status_code, 200
        )
        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        gid = str((c.get("context") or {}).get("group_id") or "")
        self.assertTrue(gid)

        self.assertEqual(
            self._post_event(
                cid,
                "invite-user",
                actor="d1",
                payload={"principal": f"u:{p2_uid}"},
            ).status_code,
            200,
        )
        self.assertEqual(
            self._post_event(cid, "reject-user", actor="p2").status_code, 200
        )

        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        self.assertEqual(c["state"], "RECRUITING")
        self.assertEqual(self._user_state(c, p2_uid), "REJECTED")
        self.assertSetEqual(
            self._group_member_ids(gid), {f"u:{driver_uid}", f"u:{p1_uid}"}
        )
        self.assertNotIn(f"u:{p2_uid}", self._group_member_ids(gid))

    def test_wf6_driver_ready_recruiting_toggle_keeps_group(self) -> None:
        driver_uid = self.user_ids["d1"]
        p1_uid = self.user_ids["p1"]
        p2_uid = self.user_ids["p2"]
        p3_uid = self.user_ids["p3"]
        definition = _gherkin_definition()
        template_id = self._create_template(
            definition,
            allowed_initial_states=["START"],
        )
        created = self._create_contract(
            template_id,
            self._gherkin_context(initial_state="START"),
            initial_state="START",
        )
        cid = created.json()["id"]
        self.assertEqual(
            self._post_event(cid, "driver-accept-start", actor="d1").status_code,
            200,
        )
        self.assertEqual(
            self._post_event(cid, "accept-user", actor="p1").status_code, 200
        )
        self.assertEqual(
            self._post_event(
                cid,
                "invite-user",
                actor="d1",
                payload={"principal": f"u:{p2_uid}"},
            ).status_code,
            200,
        )
        self.assertEqual(
            self._post_event(cid, "accept-user", actor="p2").status_code, 200
        )
        self.assertEqual(
            self._post_event(
                cid,
                "invite-user",
                actor="d1",
                payload={"principal": f"u:{p3_uid}"},
            ).status_code,
            200,
        )
        self.assertEqual(
            self._post_event(cid, "accept-user", actor="p3").status_code, 200
        )

        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        self.assertEqual(c["state"], "READY")
        gid = str((c.get("context") or {}).get("group_id") or "")
        self.assertSetEqual(
            self._group_member_ids(gid),
            {f"u:{driver_uid}", f"u:{p1_uid}", f"u:{p2_uid}", f"u:{p3_uid}"},
        )

    def test_accept_user_moves_to_ready_when_seat_capacity_reached(self) -> None:
        driver_uid = self.user_ids["d1"]
        p1_uid = self.user_ids["p1"]
        p2_uid = self.user_ids["p2"]
        cid = self._create_gherkin_contract(initial_state="START")

        with self.app.app_context():
            self.app.config["MONGO_DB"]["contracts"].update_one(
                {"_id": cid},
                {
                    "$set": {
                        "context.capacity": 4,
                        "context.riders": {
                            f"u:{p1_uid}": {"seats": 1},
                            f"u:{p2_uid}": {"seats": 3},
                        },
                    }
                },
            )

        gid = self._to_recruiting(cid)
        self.assertEqual(
            self._post_event(
                cid,
                "invite-user",
                actor="d1",
                payload={"principal": f"u:{p2_uid}"},
            ).status_code,
            200,
        )
        self.assertEqual(
            self._post_event(
                cid,
                "accept-user",
                actor="p2",
                payload={
                    "seats": 3,
                    "origin": {"lat": 45.0, "lng": 9.0},
                    "destination": {"lat": 45.1, "lng": 9.1},
                },
            ).status_code,
            200,
        )

        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        self.assertEqual(c["state"], "READY")
        self.assertSetEqual(
            self._group_member_ids(gid),
            {f"u:{driver_uid}", f"u:{p1_uid}", f"u:{p2_uid}"},
        )

    def test_recruiting_cancel_user_is_allowed_and_updates_group(self) -> None:
        driver_uid = self.user_ids["d1"]
        p1_uid = self.user_ids["p1"]
        p2_uid = self.user_ids["p2"]
        cid = self._create_gherkin_contract(initial_state="START")
        gid = self._to_recruiting(cid)

        self.assertEqual(
            self._post_event(
                cid,
                "invite-user",
                actor="d1",
                payload={"principal": f"u:{p2_uid}"},
            ).status_code,
            200,
        )
        self.assertEqual(
            self._post_event(cid, "accept-user", actor="p2").status_code,
            200,
        )
        self.assertEqual(
            self._post_event(cid, "cancel-user", actor="p2").status_code, 200
        )

        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        self.assertEqual(c["state"], "RECRUITING")
        self.assertEqual(self._user_state(c, p2_uid), "CANCELLED")
        seats = (c.get("context") or {}).get("seats") or {}
        self.assertNotIn(f"u:{p2_uid}", seats)
        self.assertSetEqual(
            self._group_member_ids(gid),
            {f"u:{driver_uid}", f"u:{p1_uid}"},
        )

    def test_driver_can_cancel_pending_invite_in_recruiting(self) -> None:
        cid = self._create_gherkin_contract(initial_state="START")
        _ = self._to_recruiting(cid)
        p2_uid = self.user_ids["p2"]

        self.assertEqual(
            self._post_event(
                cid,
                "invite-user",
                actor="d1",
                payload={"principal": f"u:{p2_uid}"},
            ).status_code,
            200,
        )
        self.assertEqual(
            self._post_event(
                cid,
                "driver-cancel-invite",
                actor="d1",
                payload={"principal": f"u:{p2_uid}"},
            ).status_code,
            200,
        )

        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        self.assertEqual(self._user_state(c, p2_uid), "CANCELLED")
        pending_invites = (c.get("context") or {}).get("pending_invites") or {}
        self.assertNotIn(f"u:{p2_uid}", pending_invites)

    def test_driver_can_remove_passenger_in_recruiting(self) -> None:
        driver_uid = self.user_ids["d1"]
        p1_uid = self.user_ids["p1"]
        p2_uid = self.user_ids["p2"]
        cid = self._create_gherkin_contract(initial_state="START")
        gid = self._to_recruiting(cid)

        self.assertEqual(
            self._post_event(
                cid,
                "invite-user",
                actor="d1",
                payload={"principal": f"u:{p2_uid}"},
            ).status_code,
            200,
        )
        self.assertEqual(
            self._post_event(cid, "accept-user", actor="p2").status_code,
            200,
        )
        self.assertEqual(
            self._post_event(
                cid,
                "driver-remove-user",
                actor="d1",
                payload={"principal": f"u:{p2_uid}"},
            ).status_code,
            200,
        )

        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        self.assertEqual(c["state"], "RECRUITING")
        self.assertEqual(self._user_state(c, p2_uid), "CANCELLED")
        self.assertSetEqual(
            self._group_member_ids(gid),
            {f"u:{driver_uid}", f"u:{p1_uid}"},
        )

    def test_driver_can_cancel_trip_in_recruiting_and_ready(self) -> None:
        cid_r = self._create_gherkin_contract(initial_state="START")
        _ = self._to_recruiting(cid_r)
        self.assertEqual(
            self._post_event(cid_r, "driver-cancel-trip", actor="d1").status_code,
            200,
        )
        denied_r = self._post_event(
            cid_r,
            "invite-user",
            actor="d1",
            payload={"principal": f"u:{self.user_ids['p2']}"},
        )
        self.assertEqual(denied_r.status_code, 410)

        cid_ready = self._create_gherkin_contract(initial_state="START")
        _ = self._to_ready(cid_ready)
        self.assertEqual(
            self._post_event(cid_ready, "driver-cancel-trip", actor="d1").status_code,
            200,
        )
        denied_ready = self._post_event(cid_ready, "set-recruiting", actor="d1")
        self.assertEqual(denied_ready.status_code, 410)

    def test_in_progress_pickup_flow_with_timed_checks(self) -> None:
        cid = self._create_gherkin_contract(initial_state="START")
        _ = self._to_ready(cid)

        self.assertEqual(
            self._post_event(cid, "start-trip", actor="d1").status_code,
            200,
        )
        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        self.assertEqual(c["state"], "IN_PROGRESS")

        driver_principal = f"u:{self.user_ids['d1']}"
        before_driver = self._count_notifications_for(
            driver_principal, "contracts.driver_pickup_check"
        )
        tick = self.httpx.post("/contracts/cron/tick", headers=self._headers("admin"))
        self.assertEqual(tick.status_code, 200)
        after_driver = self._count_notifications_for(
            driver_principal, "contracts.driver_pickup_check"
        )
        self.assertEqual(after_driver, before_driver + 1)

        self.assertEqual(
            self._post_event(cid, "driver-at-pickup", actor="d1").status_code,
            200,
        )
        self.assertEqual(
            self._post_event(cid, "rider-at-pickup", actor="p2").status_code,
            200,
        )
        self.assertEqual(
            self._post_event(
                cid,
                "driver-mark-picked-up",
                actor="d1",
                payload={"principal": f"u:{self.user_ids['p2']}"},
            ).status_code,
            200,
        )
        c2 = self.httpx.get(
            f"/contracts/{cid}", headers=self._headers("owner-1")
        ).json()
        picked = (c2.get("context") or {}).get("riders_picked_up") or {}
        self.assertTrue(bool(picked.get(f"u:{self.user_ids['p2']}")))

    def test_in_progress_rider_can_cancel(self) -> None:
        driver_uid = self.user_ids["d1"]
        p1_uid = self.user_ids["p1"]
        p2_uid = self.user_ids["p2"]
        p3_uid = self.user_ids["p3"]
        cid = self._create_gherkin_contract(initial_state="START")
        gid = self._to_ready(cid)

        self.assertEqual(
            self._post_event(cid, "start-trip", actor="d1").status_code,
            200,
        )
        self.assertEqual(
            self._post_event(cid, "cancel-user", actor="p2").status_code, 200
        )

        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        self.assertEqual(c["state"], "IN_PROGRESS")
        self.assertEqual(self._user_state(c, p2_uid), "CANCELLED")
        seats = (c.get("context") or {}).get("seats") or {}
        self.assertNotIn(f"u:{p2_uid}", seats)
        self.assertSetEqual(
            self._group_member_ids(gid),
            {f"u:{driver_uid}", f"u:{p1_uid}", f"u:{p3_uid}"},
        )

    def test_in_progress_completes_when_all_riders_picked(self) -> None:
        cid = self._create_gherkin_contract(initial_state="START")
        _ = self._to_ready(cid)

        self.assertEqual(
            self._post_event(cid, "start-trip", actor="d1").status_code, 200
        )
        self.assertEqual(
            self._post_event(cid, "driver-at-pickup", actor="d1").status_code,
            200,
        )

        for rider in ["p1", "p2", "p3"]:
            principal = f"u:{self.user_ids[rider]}"
            self.assertEqual(
                self._post_event(cid, "rider-at-pickup", actor=rider).status_code,
                200,
            )
            self.assertEqual(
                self._post_event(
                    cid,
                    "driver-mark-picked-up",
                    actor="d1",
                    payload={"principal": principal},
                ).status_code,
                200,
            )

        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        self.assertEqual(c["state"], "COMPLETED")
        self.assertEqual(c["status"], "DONE")

    def test_wf7_cancel_early_stops_contract_and_blocks_events(self) -> None:
        cid = self._create_gherkin_contract()
        _ = self._to_recruiting(cid)

        cancel = self.httpx.delete(
            f"/contracts/{cid}", headers=self._headers("owner-1")
        )
        self.assertEqual(cancel.status_code, 200)
        self.assertEqual(cancel.json().get("status"), "CANCELED")

        denied = self._post_event(
            cid,
            "invite-user",
            actor="d1",
            payload={"principal": f"u:{self.user_ids['p2']}"},
        )
        self.assertEqual(denied.status_code, 410)

    def test_wf8_cancel_late_stops_contract_and_blocks_events(self) -> None:
        cid = self._create_gherkin_contract()
        _ = self._to_ready(cid)

        cancel = self.httpx.delete(
            f"/contracts/{cid}", headers=self._headers("owner-1")
        )
        self.assertEqual(cancel.status_code, 200)
        self.assertEqual(cancel.json().get("status"), "CANCELED")

        denied = self._post_event(cid, "set-recruiting", actor="d1")
        self.assertEqual(denied.status_code, 410)

    def test_unauthorized_actor_cannot_accept_p2(self) -> None:
        cid = self._create_gherkin_contract()
        _ = self._to_recruiting(cid)
        self.assertEqual(
            self._post_event(
                cid,
                "invite-user",
                actor="d1",
                payload={"principal": f"u:{self.user_ids['p2']}"},
            ).status_code,
            200,
        )

        denied = self._post_event(cid, "accept-user", actor="p4")
        self.assertEqual(denied.status_code, 409)

    def test_duplicate_accept_p2_is_rejected_by_user_state_guard(self) -> None:
        cid = self._create_gherkin_contract()
        _ = self._to_recruiting(cid)
        self.assertEqual(
            self._post_event(
                cid,
                "invite-user",
                actor="d1",
                payload={"principal": f"u:{self.user_ids['p2']}"},
            ).status_code,
            200,
        )
        self.assertEqual(
            self._post_event(cid, "accept-user", actor="p2").status_code, 200
        )

        duplicate = self._post_event(cid, "accept-user", actor="p2")
        self.assertEqual(duplicate.status_code, 409)

    def test_recruiting_user_can_request_join_and_driver_accepts(self) -> None:
        cid = self._create_gherkin_contract()
        _ = self._to_recruiting(cid)
        p4 = f"u:{self.user_ids['p4']}"

        self.assertEqual(
            self._post_event(cid, "request-join", actor="p4").status_code,
            200,
        )
        c_req = self.httpx.get(
            f"/contracts/{cid}", headers=self._headers("owner-1")
        ).json()
        self.assertEqual(self._user_state(c_req, self.user_ids["p4"]), "REQUESTING")
        self.assertEqual(
            self._post_event(
                cid,
                "accept-join-request",
                actor="d1",
                payload={"principal": p4},
            ).status_code,
            200,
        )

        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        self.assertEqual(self._user_state(c, self.user_ids["p4"]), "ACCEPTED")

    def test_recruiting_user_can_request_join_and_driver_rejects(self) -> None:
        cid = self._create_gherkin_contract()
        _ = self._to_recruiting(cid)
        p4 = f"u:{self.user_ids['p4']}"

        self.assertEqual(
            self._post_event(cid, "request-join", actor="p4").status_code,
            200,
        )
        c_req = self.httpx.get(
            f"/contracts/{cid}", headers=self._headers("owner-1")
        ).json()
        self.assertEqual(self._user_state(c_req, self.user_ids["p4"]), "REQUESTING")
        self.assertEqual(
            self._post_event(
                cid,
                "reject-join-request",
                actor="d1",
                payload={"principal": p4},
            ).status_code,
            200,
        )

        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        self.assertEqual(self._user_state(c, self.user_ids["p4"]), "REJECTED")

    def test_request_join_is_blocked_when_no_capacity(self) -> None:
        cid = self._create_gherkin_contract()
        _ = self._to_recruiting(cid)

        with self.app.app_context():
            self.app.config["MONGO_DB"]["contracts"].update_one(
                {"_id": cid},
                {"$set": {"context.capacity": 1}},
            )

        self.assertEqual(
            self._post_event(cid, "request-join", actor="p4").status_code,
            200,
        )
        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        self.assertEqual(self._user_state(c, self.user_ids["p4"]), "")

    def test_request_join_denies_driver_and_confirmed_users(self) -> None:
        cid = self._create_gherkin_contract()
        _ = self._to_recruiting(cid)

        denied_driver = self._post_event(cid, "request-join", actor="d1")
        self.assertEqual(denied_driver.status_code, 403)

        denied_confirmed = self._post_event(cid, "request-join", actor="p1")
        self.assertEqual(denied_confirmed.status_code, 409)

    def test_request_join_can_be_cancelled_before_driver_decision(self) -> None:
        cid = self._create_gherkin_contract()
        _ = self._to_recruiting(cid)

        self.assertEqual(
            self._post_event(
                cid,
                "request-join",
                actor="p4",
                payload={
                    "seats": 2,
                    "origin": {"lat": 45.0, "lng": 9.0},
                    "destination": {"lat": 45.1, "lng": 9.1},
                },
            ).status_code,
            200,
        )
        self.assertEqual(
            self._post_event(cid, "cancel-join-request", actor="p4").status_code,
            200,
        )

        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        self.assertEqual(self._user_state(c, self.user_ids["p4"]), "")
        seats = (c.get("context") or {}).get("seats") or {}
        self.assertNotIn(f"u:{self.user_ids['p4']}", seats)

    def test_driver_join_decision_requires_requesting_state(self) -> None:
        cid = self._create_gherkin_contract()
        _ = self._to_recruiting(cid)
        p4 = f"u:{self.user_ids['p4']}"

        self.assertEqual(
            self._post_event(
                cid,
                "accept-join-request",
                actor="d1",
                payload={"principal": p4},
            ).status_code,
            200,
        )
        c0 = self.httpx.get(
            f"/contracts/{cid}", headers=self._headers("owner-1")
        ).json()
        self.assertEqual(self._user_state(c0, self.user_ids["p4"]), "")

        self.assertEqual(
            self._post_event(
                cid,
                "reject-join-request",
                actor="d1",
                payload={"principal": p4},
            ).status_code,
            200,
        )
        c1 = self.httpx.get(
            f"/contracts/{cid}", headers=self._headers("owner-1")
        ).json()
        self.assertEqual(self._user_state(c1, self.user_ids["p4"]), "")

    def test_accept_p3_without_invite_is_rejected(self) -> None:
        cid = self._create_gherkin_contract()
        _ = self._to_recruiting(cid)

        denied = self._post_event(cid, "accept-user", actor="p3")
        self.assertEqual(denied.status_code, 409)
