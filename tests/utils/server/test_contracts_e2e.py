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
from bson import ObjectId
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
                        "required": ["driver_trip_id", "riders"],
                        "properties": {
                            "driver_trip_id": {"type": "string", "minLength": 1},
                            "riders": {
                                "type": "array",
                                "minItems": 1,
                                "items": {
                                    "type": "string",
                                    "minLength": 1,
                                },
                            },
                        },
                        "additionalProperties": True,
                    },
                    "effects": [
                        {
                            "title": "Load Driver Route",
                            "description": "Loads the driver route item so START can derive owner, trip geometry, and seat capacity.",
                            "type": "get.item",
                            "item_id": "$$ctx.doc.context.driver_trip_id",
                            "key": "driver_route_items",
                        },
                        {
                            "title": "Load Rider Routes",
                            "description": "Loads rider route items from the initial route id list to hydrate rider identities and trips.",
                            "type": "get.item",
                            "item_id": "$$ctx.doc.context.riders",
                            "key": "rider_route_items",
                        },
                        {
                            "title": "Hydrate Route Inputs",
                            "description": "Derives driver, capacity, driver trip and rider map from loaded route items before branching.",
                            "type": "update.contract",
                            "update": {
                                "$set": {
                                    "context.driver_trip": {
                                        "$ref": "/items/route/$$ctx.doc.context.driver_trip_id/data"
                                    },
                                    "context.driver": {
                                        "$ref": "/items/route/$$ctx.doc.context.driver_trip_id/data.user_id"
                                    },
                                    "context.capacity": {
                                        "$ref": "/items/route/$$ctx.doc.context.driver_trip_id/data.capacity"
                                    },
                                    "context.riders": {
                                        "$arrayToObject": {
                                            "$map": {
                                                "input": "$local.rider_route_items",
                                                "as": "r",
                                                "in": {
                                                    "k": "$$r.data.user_id",
                                                    "v": {
                                                        "seats": {
                                                            "$ifNull": [
                                                                "$$r.data.seats",
                                                                1,
                                                            ]
                                                        },
                                                        "trip": {
                                                            "origin": "$$r.data.origin",
                                                            "destination": "$$r.data.destination",
                                                        },
                                                    },
                                                },
                                            }
                                        }
                                    },
                                }
                            },
                        },
                        {
                            "title": "Persist Progress",
                            "description": "Persists transition data to keep the process deterministic.",
                            "type": "update.contract",
                            "update": {
                                "$set": {"local.start_initiated_by_driver": {"$eq": ["$created_by", "$context.driver"]}}
                            },
                        },
                        {
                            "title": "Evaluate Branch",
                            "description": "Selects the branch that matches current trip conditions.",
                            "type": "if.else",
                            "condition": {"$ctx": "doc.local.start_initiated_by_driver"},
                            "then_effects": [
                                {
                                    "title": "Set Pending Riders",
                                    "description": "Marks initial riders as pending confirmation before moving to the confirming phase.",
                                    "type": "update.contract",
                                    "update": {
                                        "$set": {
                                            "states": {
                                                "$arrayToObject": {
                                                    "$map": {
                                                        "input": {"$objectToArray": "$context.riders"},
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
                                    "title": "Set Driver Committed",
                                    "description": "Marks the driver as committed and resets accepted occupancy for confirmation-driven onboarding.",
                                    "type": "update.contract",
                                    "update": {
                                        "$set": {
                                            "states.$$ctx.doc.context.driver": "DRIVER",
                                            "context.accepted_seats_total": 0,
                                        }
                                    },
                                },
                                {
                                    "title": "Prepare Invite Targets",
                                    "description": "Builds recipient targets for initial rider notifications based on current rider principals.",
                                    "type": "update.contract",
                                    "update": {
                                        "$set": {
                                            "local.initial_invite_targets": {
                                                "$arrayToObject": {
                                                    "$map": {
                                                        "input": {"$objectToArray": "$context.riders"},
                                                        "as": "p",
                                                        "in": {
                                                            "k": "$$p.k",
                                                            "v": ["in_app", "push"],
                                                        },
                                                    }
                                                }
                                            }
                                        }
                                    },
                                },
                                {
                                    "title": "Notify Stakeholders",
                                    "description": "Sends initial invitation notifications to riders so each invited user can explicitly confirm participation.",
                                    "type": "notify",
                                    "notify": {
                                        "event": "contracts.user_invited",
                                        "targets": {"$ctx": "doc.local.initial_invite_targets"},
                                        "payload": {"contract_id": {"$ctx": "doc._id"}},
                                    },
                                },
                                {
                                    "title": "Move State",
                                    "description": "Moves the contract state to support stabilize initial trip intent.",
                                    "type": "update.contract",
                                    "update": {"$set": {"state": "CONFIRMING"}},
                                },
                            ],
                            "else_effects": [
                                {
                                    "title": "Set initial Rider and Driver Statuses",
                                    "description": "Aligns rider and driver statuses for stabilize initial trip intent.",
                                    "type": "update.contract",
                                    "update": [
                                        {
                                            "$set": {
                                                "states": {
                                                    "$arrayToObject": {
                                                        "$map": {
                                                            "input": {"$objectToArray": "$context.riders"},
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
                                        {"$set": {"states.$$ctx.doc.context.driver": "PENDING_DRIVER"}},
                                    ],
                                },
                                {
                                    "title": "Notify Stakeholders",
                                    "description": "Send ride request to driver.",
                                    "type": "notify",
                                    "notify": {
                                        "event": "contracts.request_ride",
                                        "targets": {
                                            "$$ctx.doc.context.driver": [
                                                "in_app",
                                                "push",
                                            ]
                                        },
                                        "payload": {"contract_id": {"$ctx": "doc._id"}},
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
                                    "required": ["route_id"],
                                    "properties": {
                                        "route_id": {"type": "string", "minLength": 1},
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
                                ],
                                "response": {
                                    "ok": "$$ctx.doc.local.can_join",
                                    "event": "request_join",
                                },
                            }
                        ],
                        "effects": [
                            {
                                "title": "Establish whether the driver has sufficient capacity",
                                "description": "Checks if seats requests is within driver capacity.",
                                "type": "update.contract",
                                "update": [
                                    {
                                        "$set": {
                                            "local.route_cost": {
                                                "$ref": "/items/route/$$ctx.payload.route_id/data.cost"},
                                            "local.route_seats": {
                                                "$ref": "/items/route/$$ctx.payload.route_id/data.seats"},
                                            "local.route_origin": {
                                                "$ref": "/items/route/$$ctx.payload.route_id/data.origin"
                                            },
                                            "local.route_destination": {
                                                "$ref": "/items/route/$$ctx.payload.route_id/data.destination"
                                            }
                                        }
                                    },
                                    {
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
                                                            {
                                                                "$ifNull": [
                                                                    "$local.route_seats",
                                                                    1,
                                                                ]
                                                            },
                                                        ]
                                                    },
                                                    {"$ifNull": ["$context.capacity", 0]},
                                                ]
                                            },
                                        }
                                    }
                                ],
                            },
                            {
                                "title": "Read Rider Credits",
                                "description": "Reads rider credit balance before evaluating join feasibility in START.",
                                "type": "balance.credits",
                                "user_id": "$$ctx.user",
                                "product": "trip",
                                "key": "available_credits",
                            },
                            {
                                "title": "Validate Join Prerequisites",
                                "description": "Combines seat capacity and rider credits to decide whether START join can proceed.",
                                "type": "update.contract",
                                "update":[
                                    {
                                        "$set": {
                                            "local.has_sufficient_credits": {
                                                "$gte": [
                                                    {
                                                        "$ifNull": [
                                                            "$local.available_credits",
                                                            0,
                                                        ]
                                                    },
                                                    {"$ifNull": ["$local.route_cost", 0]},
                                                ]
                                            },
                                        }
                                    },
                                    {
                                        "$set": {
                                            "local.can_join": {
                                                "$and": [
                                                    "$local.has_capacity_for_join",
                                                    "$local.has_sufficient_credits"
                                                ]
                                            },
                                        }
                                    }
                                ],
                            },
                            {
                                "title": "Evaluate Branch",
                                "description": "Selects the branch that matches current trip conditions.",
                                "type": "if.else",
                                "condition": {"$ctx": "local.can_join"},
                                "then_effects": [
                                    {
                                        "title": "Reserve Join Credits",
                                        "description": "Consumes route credits at join time so only financially valid requests enter START queue.",
                                        "type": "use.credits",
                                        "user_id": "$$ctx.user",
                                        "product": "trip",
                                        "credits": {"$ctx": "local.route_cost"},
                                    },
                                    {
                                        "title": "Update Rider Statuses",
                                        "description": "Aligns rider and driver statuses for capture a join request.",
                                        "type": "update.contract",
                                        "update": {
                                            "$set": {
                                                "states.$$ctx.user": "REQUESTING",
                                                "context.riders.$$ctx.user.seats": {
                                                    "$ifNull": [
                                                        "$local.route_seats",
                                                        1,
                                                    ]
                                                },
                                                "context.riders.$$ctx.user.trip": {
                                                    "origin": {"$ctx": "local.route_origin"},
                                                    "destination": {"$ctx": "local.route_destination"},
                                                },
                                            }
                                        },
                                    },
                                    {
                                        "title": "Notify Driver new Join Request",
                                        "type": "notify",
                                        "notify": {
                                            "event": "contracts.join_requested",
                                            "targets": {
                                                "$$ctx.doc.context.driver": [
                                                    "in_app",
                                                    "push",
                                                ]
                                            },
                                            "payload": {
                                                "principal": "$$ctx.user",
                                                "contract_id": {"$ctx": "doc._id"},
                                            },
                                        },
                                    },
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
                                "payload_schema": {
                                    "type": "object",
                                    "required": ["riders"],
                                    "properties": {
                                        "riders": {
                                            "type": "array",
                                            "items": {
                                                "type": "string",
                                                "pattern": "^u:.+$",
                                            },
                                            "minItems": 1,
                                        }
                                    },
                                    "additionalProperties": False,
                                },
                                "allow_principals": ["$$ctx.doc.context.driver"],
                                "response": {
                                    "ok": True,
                                    "event": "driver_accept_start",
                                },
                            }
                        ],
                        "effects": [
                            {
                                "title": "Prepare Invite Targets",
                                "description": "Builds recipient targets from payload.riders so the driver can choose exactly who must confirm now.",
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "local.initial_invite_targets": {
                                            "$arrayToObject": {
                                                "$map": {
                                                    "input": "$$payload.riders",
                                                    "as": "p",
                                                    "in": {
                                                        "k": "$$p",
                                                        "v": ["in_app", "push"],
                                                    },
                                                }
                                            }
                                        }
                                    }
                                },
                            },
                            {
                                "title": "Notify Stakeholders",
                                "description": "Notifies all current riders that the driver accepted the trip and now awaits their confirmations.",
                                "type": "notify",
                                "notify": {
                                    "event": "contracts.user_invited",
                                    "targets": {"$ctx": "doc.local.initial_invite_targets"},
                                    "payload": {"contract_id": {"$ctx": "doc._id"}},
                                },
                            },
                            {
                                "title": "Promote Pending Riders",
                                "description": "Promotes only payload.riders to pending confirmations and marks driver commitment before CONFIRMING.",
                                "type": "update.contract",
                                "update": [
                                    {"$set": {"states.$$ctx.doc.context.driver": "DRIVER"}},
                                    {
                                        "$set": {
                                            "states": {
                                                "$arrayToObject": {
                                                    "$map": {
                                                        "input": {"$objectToArray": "$states"},
                                                        "as": "kv",
                                                        "in": {
                                                            "k": "$$kv.k",
                                                            "v": {
                                                                "$cond": [
                                                                    {
                                                                        "$in": [
                                                                            "$$kv.k",
                                                                            "$$payload.riders",
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
                                ],
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
                                "title": "Move State",
                                "description": "Moves the contract state to support close the declined request.",
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "state": "REJECTED",
                                        "states": {
                                            "$arrayToObject": {
                                                "$map": {
                                                    "input": {"$objectToArray": "$states"},
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
                            }
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
                                "title": "Clear Context",
                                "description": "Clears obsolete lifecycle fields after this decision.",
                                "type": "update.contract",
                                "update": {
                                    "$unset": [
                                        "states.$$ctx.user",
                                        "context.riders.$$ctx.user",
                                    ]
                                },
                            },
                            {
                                "title": "Persist Progress",
                                "description": "Persists transition data to keep the process deterministic.",
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
                                "title": "Evaluate Branch",
                                "description": "Selects the branch that matches current trip conditions.",
                                "type": "if.else",
                                "condition": {"$ctx": "doc.local.has_interested_users"},
                                "then_effects": [],
                                "else_effects": [
                                    {
                                        "title": "Notify Stakeholders",
                                        "description": "Sends contracts.request_ride so stakeholders can act at the right time.",
                                        "type": "notify",
                                        "notify": {
                                            "event": "contracts.request_ride",
                                            "targets": {
                                                "$$ctx.doc.context.driver": [
                                                    "in_app",
                                                    "push",
                                                ]
                                            },
                                            "payload": {"contract_id": {"$ctx": "doc._id"}},
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
                            "title": "Create Group",
                            "description": "Creates the coordination group for active riders.",
                            "type": "create.group",
                            "name": "contract-c-001",
                            "sub": "$$ctx.doc.context.driver",
                            "key": "group_ref",
                        },
                        {
                            "title": "Link Coordination Group",
                            "description": "Stores group linkage for roster synchronization.",
                            "type": "update.contract",
                            "update": {"$set": {"context.group_id": {"$ctx": "local.group_ref"}}},
                        },
                        {
                            "title": "Store Context",
                            "description": "Stores lifecycle context needed to collect rider confirmations.",
                            "type": "update.contract",
                            "update": {
                                "$set": {
                                    "context.accepted_riders": {
                                        "$map": {
                                            "input": {
                                                "$filter": {
                                                    "input": {"$objectToArray": "$states"},
                                                    "as": "kv",
                                                    "cond": {"$eq": ["$$kv.v", "ACCEPTED"]},
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
                            "title": "Sync Group",
                            "description": "Synchronizes group membership with current trip roster.",
                            "type": "update.group",
                            "group_id": {"$ctx": "doc.context.group_id"},
                            "edit_members": {"add_members": "$$ctx.doc.context.accepted_riders"},
                        },
                        {
                            "title": "Clear Context",
                            "description": "Clears obsolete lifecycle fields after this decision.",
                            "type": "update.contract",
                            "update": {"$unset": "context.accepted_riders"},
                        },
                        {
                            "title": "Move State",
                            "description": "Moves the contract state to support collect rider confirmations.",
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
                                        "route_id": {
                                            "type": "string",
                                            "minLength": 1,
                                        },
                                        "seats": {"type": "integer", "minimum": 1},
                                        "origin": {
                                            "type": "object",
                                            "required": ["lat", "lng", "at"],
                                            "properties": {
                                                "lat": {"type": "number"},
                                                "lng": {"type": "number"},
                                                "at": {
                                                    "type": "string",
                                                    "format": "date-time",
                                                },
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
                                "title": "Persist Progress",
                                "description": "Persists transition data to keep the process deterministic.",
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
                                "title": "Evaluate Branch",
                                "description": "Selects the branch that matches current trip conditions.",
                                "type": "if.else",
                                "condition": {"$ctx": "local.has_capacity_for_join"},
                                "then_effects": [
                                    {
                                        "title": "Align Rider Statuses",
                                        "description": "Aligns rider and driver statuses for capture a join request.",
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
                                        "title": "Notify Stakeholders",
                                        "description": "Sends contracts.join_requested so stakeholders can act at the right time.",
                                        "type": "notify",
                                        "notify": {
                                            "event": "contracts.join_requested",
                                            "targets": {
                                                "$$ctx.doc.context.driver": [
                                                    "in_app",
                                                    "push",
                                                ]
                                            },
                                            "payload": {
                                                "principal": "$$ctx.user",
                                                "contract_id": {"$ctx": "doc._id"},
                                            },
                                        },
                                    },
                                ],
                                "else_effects": [
                                    {
                                        "title": "Notify Stakeholders",
                                        "description": "Sends contracts.join_request_rejected_capacity so stakeholders can act at the right time.",
                                        "type": "notify",
                                        "notify": {
                                            "event": "contracts.join_request_rejected_capacity",
                                            "targets": {"$$ctx.user": ["in_app", "push"]},
                                            "payload": {"contract_id": {"$ctx": "doc._id"}},
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
                                "title": "Persist Progress",
                                "description": "Persists transition data to keep the process deterministic.",
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "local.target_is_requesting": {
                                            "$eq": [
                                                {
                                                    "$ifNull": [
                                                        {"$ctx": "doc.states.$$ctx.payload.principal"},
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
                                "title": "Evaluate Branch",
                                "description": "Selects the branch that matches current trip conditions.",
                                "type": "if.else",
                                "condition": {"$ctx": "doc.local.target_is_requesting"},
                                "then_effects": [
                                    {
                                        "title": "Align Rider Statuses",
                                        "description": "Aligns rider and driver statuses for approve a queued request.",
                                        "type": "update.contract",
                                        "update": {"$set": {"states.$$ctx.payload.principal": "ACCEPTED"}},
                                    },
                                    {
                                        "title": "Sync Group",
                                        "description": "Synchronizes group membership with current trip roster.",
                                        "type": "update.group",
                                        "group_id": {"$ctx": "doc.context.group_id"},
                                        "edit_members": {"add_members": ["$$ctx.payload.principal"]},
                                    },
                                    {
                                        "title": "Persist Progress",
                                        "description": "Persists transition data to keep the process deterministic.",
                                        "type": "update.contract",
                                        "update": {
                                            "$set": {
                                                "local.accepted_increment": {
                                                    "$ifNull": [
                                                        {"$ctx": "doc.context.riders.$$ctx.payload.principal.seats"},
                                                        1,
                                                    ]
                                                }
                                            }
                                        },
                                    },
                                    {
                                        "title": "Recalculate Occupancy",
                                        "description": "Updates accepted occupancy for accurate capacity checks.",
                                        "type": "update.contract",
                                        "update": {
                                            "$set": {
                                                "context.accepted_seats_total": {
                                                    "$add": [
                                                        {
                                                            "$ifNull": [
                                                                "$context.accepted_seats_total",
                                                                0,
                                                            ]
                                                        },
                                                        "$local.accepted_increment",
                                                    ]
                                                },
                                                "local.capacity_reached": {
                                                    "$gte": [
                                                        {
                                                            "$add": [
                                                                {
                                                                    "$ifNull": [
                                                                        "$context.accepted_seats_total",
                                                                        0,
                                                                    ]
                                                                },
                                                                "$local.accepted_increment",
                                                            ]
                                                        },
                                                        {
                                                            "$ifNull": [
                                                                "$context.capacity",
                                                                0,
                                                            ]
                                                        },
                                                    ]
                                                },
                                            }
                                        },
                                    },
                                    {
                                        "title": "Evaluate Branch",
                                        "description": "Selects the branch that matches current trip conditions.",
                                        "type": "if.else",
                                        "condition": {"$ctx": "doc.local.capacity_reached"},
                                        "then_effects": [
                                            {
                                                "title": "Move State",
                                                "description": "Moves the contract state to support approve a queued request. "
                                                               "(then)",
                                                "type": "update.contract",
                                                "update": {"$set": {"state": "READY"}},
                                            }
                                        ],
                                        "else_effects": [
                                            {
                                                "title": "Move State",
                                                "description": "Moves the contract state to support approve a queued request. "
                                                               "(else)",
                                                "type": "update.contract",
                                                "update": {"$set": {"state": "RECRUITING"}},
                                            }
                                        ],
                                    },
                                    {
                                        "title": "Notify Stakeholders",
                                        "description": "Sends contracts.join_request_accepted so stakeholders can act at the right time. "
                                                       "(then)",
                                        "type": "notify",
                                        "notify": {
                                            "event": "contracts.join_request_accepted",
                                            "targets": {
                                                "$$ctx.payload.principal": [
                                                    "in_app",
                                                    "push",
                                                ]
                                            },
                                            "payload": {"contract_id": {"$ctx": "doc._id"}},
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
                                "title": "Persist Progress",
                                "description": "Persists transition data to keep the process deterministic.",
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "local.target_is_requesting": {
                                            "$eq": [
                                                {
                                                    "$ifNull": [
                                                        {"$ctx": "doc.states.$$ctx.payload.principal"},
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
                                "title": "Evaluate Branch",
                                "description": "Selects the branch that matches current trip conditions.",
                                "type": "if.else",
                                "condition": {"$ctx": "doc.local.target_is_requesting"},
                                "then_effects": [
                                    {
                                        "title": "Align Rider Statuses",
                                        "description": "Aligns rider and driver statuses for decline a queued request.",
                                        "type": "update.contract",
                                        "update": {"$set": {"states.$$ctx.payload.principal": "REJECTED"}},
                                    },
                                    {
                                        "title": "Notify Stakeholders",
                                        "description": "Sends contracts.join_request_rejected so stakeholders can act at the right time. "
                                                       "(then)",
                                        "type": "notify",
                                        "notify": {
                                            "event": "contracts.join_request_rejected",
                                            "targets": {
                                                "$$ctx.payload.principal": [
                                                    "in_app",
                                                    "push",
                                                ]
                                            },
                                            "payload": {"contract_id": {"$ctx": "doc._id"}},
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
                                "title": "Clear Context",
                                "description": "Clears obsolete lifecycle fields after this decision.",
                                "type": "update.contract",
                                "update": {
                                    "$unset": [
                                        "states.$$ctx.user",
                                        "context.riders.$$ctx.user.seats",
                                    ]
                                },
                            },
                            {
                                "title": "Notify Stakeholders",
                                "description": "Sends contracts.join_request_cancelled so stakeholders can act at the right time.",
                                "type": "notify",
                                "notify": {
                                    "event": "contracts.join_request_cancelled",
                                    "targets": {"$$ctx.doc.context.driver": ["in_app", "push"]},
                                    "payload": {
                                        "principal": "$$ctx.user",
                                        "contract_id": {"$ctx": "doc._id"},
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
                                "title": "Align Rider Statuses",
                                "description": "Aligns rider and driver statuses for invite a rider to confirm.",
                                "type": "update.contract",
                                "update": {"$set": {"states.$$ctx.payload.principal": "PENDING"}},
                            },
                            {
                                "title": "Schedule Timed Step",
                                "description": "Schedules InviteUserTimedOut as a timed lifecycle checkpoint.",
                                "type": "schedule.event_at",
                                "key": "invite_timeout_id",
                                "event_name": "InviteUserTimedOut",
                                "at": {"$ctx": "doc.context.driver_trip.origin.at"},
                                "actor_id": "system:cron",
                                "payload": {"principal": "$$ctx.payload.principal"},
                            },
                            {
                                "title": "Store Context",
                                "description": "Tracks invite ownership and timeout linkage.",
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
                                "title": "Notify Stakeholders",
                                "description": "Sends contracts.user_invited so stakeholders can act at the right time.",
                                "type": "notify",
                                "notify": {
                                    "event": "contracts.user_invited",
                                    "targets": {"$$ctx.payload.principal": ["in_app", "push"]},
                                    "payload": {"contract_id": {"$ctx": "doc._id"}},
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
                                            "required": ["lat", "lng", "at"],
                                            "properties": {
                                                "lat": {"type": "number"},
                                                "lng": {"type": "number"},
                                                "at": {
                                                    "type": "string",
                                                    "format": "date-time",
                                                },
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
                                "title": "Persist Progress",
                                "description": "Persists transition data to keep the process deterministic.",
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
                                "title": "Evaluate Branch",
                                "description": "Selects the branch that matches current trip conditions.",
                                "type": "if.else",
                                "condition": {"$ctx": "doc.local.pending_invite_event_id"},
                                "then_effects": [
                                    {
                                        "title": "Cancel Schedule",
                                        "description": "Cancels timers that are no longer relevant on this path.",
                                        "type": "unschedule.event_at",
                                        "event_id": {"$ctx": "doc.local.pending_invite_event_id"},
                                    }
                                ],
                                "else_effects": [],
                            },
                            {
                                "title": "Clear Context",
                                "description": "Clears obsolete lifecycle fields after this decision.",
                                "type": "update.contract",
                                "update": {"$unset": "context.pending_invites.$$ctx.user"},
                            },
                            {
                                "title": "Align Rider Statuses",
                                "description": "Aligns rider and driver statuses for confirm a rider seat.",
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
                                "title": "Sync Group",
                                "description": "Synchronizes group membership with current trip roster.",
                                "type": "update.group",
                                "group_id": {"$ctx": "doc.context.group_id"},
                                "edit_members": {"add_members": ["$$ctx.user"]},
                            },
                            {
                                "title": "Persist Progress",
                                "description": "Persists transition data to keep the process deterministic.",
                                "type": "update.contract",
                                "update": {
                                    "$set": {"local.accepted_increment": {"$ifNull": ["$$ctx.payload.seats", 1]}}
                                },
                            },
                            {
                                "title": "Recalculate Occupancy",
                                "description": "Updates accepted occupancy for accurate capacity checks.",
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "context.accepted_seats_total": {
                                            "$add": [
                                                {
                                                    "$ifNull": [
                                                        "$context.accepted_seats_total",
                                                        0,
                                                    ]
                                                },
                                                "$local.accepted_increment",
                                            ]
                                        },
                                        "local.capacity_reached": {
                                            "$gte": [
                                                {
                                                    "$add": [
                                                        {
                                                            "$ifNull": [
                                                                "$context.accepted_seats_total",
                                                                0,
                                                            ]
                                                        },
                                                        "$local.accepted_increment",
                                                    ]
                                                },
                                                {"$ifNull": ["$context.capacity", 0]},
                                            ]
                                        },
                                    }
                                },
                            },
                            {
                                "title": "Evaluate Branch",
                                "description": "Selects the branch that matches current trip conditions.",
                                "type": "if.else",
                                "condition": {"$ctx": "doc.local.capacity_reached"},
                                "then_effects": [
                                    {
                                        "title": "Move State",
                                        "description": "Moves the contract state to support confirm a rider seat.",
                                        "type": "update.contract",
                                        "update": {"$set": {"state": "READY"}},
                                    }
                                ],
                                "else_effects": [
                                    {
                                        "title": "Move State",
                                        "description": "Moves the contract state to support confirm a rider seat.",
                                        "type": "update.contract",
                                        "update": {"$set": {"state": "RECRUITING"}},
                                    }
                                ],
                            },
                            {
                                "title": "Notify Stakeholders",
                                "description": "Sends contracts.user_accepted so stakeholders can act at the right time.",
                                "type": "notify",
                                "notify": {
                                    "event": "contracts.user_accepted",
                                    "targets": {"$$ctx.doc.context.driver": ["in_app", "push"]},
                                    "payload": {
                                        "principal": "$$ctx.user",
                                        "contract_id": {"$ctx": "doc._id"},
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
                                "title": "Persist Progress",
                                "description": "Persists transition data to keep the process deterministic.",
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
                                "title": "Evaluate Branch",
                                "description": "Selects the branch that matches current trip conditions.",
                                "type": "if.else",
                                "condition": {"$ctx": "doc.local.pending_invite_event_id"},
                                "then_effects": [
                                    {
                                        "title": "Cancel Schedule",
                                        "description": "Cancels timers that are no longer relevant on this path.",
                                        "type": "unschedule.event_at",
                                        "event_id": {"$ctx": "doc.local.pending_invite_event_id"},
                                    }
                                ],
                                "else_effects": [],
                            },
                            {
                                "title": "Clear Context",
                                "description": "Clears obsolete lifecycle fields after this decision.",
                                "type": "update.contract",
                                "update": {"$unset": "context.pending_invites.$$ctx.user"},
                            },
                            {
                                "title": "Align Rider Statuses",
                                "description": "Aligns rider and driver statuses for record rider refusal.",
                                "type": "update.contract",
                                "update": {"$set": {"states.$$ctx.user": "REJECTED"}},
                            },
                            {
                                "title": "Notify Stakeholders",
                                "description": "Sends contracts.user_rejected so stakeholders can act at the right time.",
                                "type": "notify",
                                "notify": {
                                    "event": "contracts.user_rejected",
                                    "targets": {"$$ctx.doc.context.driver": ["in_app", "push"]},
                                    "payload": {
                                        "principal": "$$ctx.user",
                                        "contract_id": {"$ctx": "doc._id"},
                                    },
                                },
                            },
                        ],
                    },
                    "InviteUserTimedOut": {
                        "trigger": [{"type": "api", "path": "invite-user-timeout"}],
                        "effects": [
                            {
                                "title": "Align Rider Statuses",
                                "description": "Aligns rider and driver statuses for expire an unanswered invite.",
                                "type": "update.contract",
                                "update": {"$set": {"states.$$ctx.payload.principal": "EXPIRED"}},
                            },
                            {
                                "title": "Clear Context",
                                "description": "Clears obsolete lifecycle fields after this decision.",
                                "type": "update.contract",
                                "update": {"$unset": "context.pending_invites.$$ctx.payload.principal"},
                            },
                            {
                                "title": "Notify Stakeholders",
                                "description": "Sends contracts.invite_timed_out so stakeholders can act at the right time.",
                                "type": "notify",
                                "notify": {
                                    "event": "contracts.invite_timed_out",
                                    "targets": {"$$ctx.doc.context.driver": ["in_app", "push"]},
                                    "payload": {"contract_id": {"$ctx": "doc._id"}},
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
                                "title": "Persist Progress",
                                "description": "Persists transition data to keep the process deterministic.",
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "local.target_is_pending_invite": {
                                            "$eq": [
                                                {
                                                    "$ifNull": [
                                                        {"$ctx": "doc.states.$$ctx.payload.principal"},
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
                                "title": "Evaluate Branch",
                                "description": "Selects the branch that matches current trip conditions.",
                                "type": "if.else",
                                "condition": {"$ctx": "doc.local.target_is_pending_invite"},
                                "then_effects": [
                                    {
                                        "title": "Cancel Schedule",
                                        "description": "Cancels timers that are no longer relevant on this path.",
                                        "type": "unschedule.event_at",
                                        "event_id": {"$ctx": "doc.context.pending_invites.$$ctx.payload.principal"},
                                    },
                                    {
                                        "title": "Persist Progress",
                                        "description": "Persists transition data to keep the process deterministic.",
                                        "type": "update.contract",
                                        "update": [
                                            {"$set": {"states.$$ctx.payload.principal": "CANCELLED"}},
                                            {"$unset": "context.pending_invites.$$ctx.payload.principal"},
                                        ],
                                    },
                                    {
                                        "title": "Notify Stakeholders",
                                        "description": "Sends contracts.invite_cancelled_by_driver so stakeholders can act at the right time. "
                                                       "(then)",
                                        "type": "notify",
                                        "notify": {
                                            "event": "contracts.invite_cancelled_by_driver",
                                            "targets": {
                                                "$$ctx.payload.principal": [
                                                    "in_app",
                                                    "push",
                                                ]
                                            },
                                            "payload": {"contract_id": {"$ctx": "doc._id"}},
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
                                "title": "Sync Group",
                                "description": "Synchronizes group membership with current trip roster.",
                                "type": "update.group",
                                "group_id": {"$ctx": "doc.context.group_id"},
                                "edit_members": {"remove_members": ["$$ctx.user"]},
                            },
                            {
                                "title": "Persist Progress",
                                "description": "Persists transition data to keep the process deterministic.",
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "local.cancel_seats": {
                                            "$ifNull": [
                                                {"$ctx": "doc.context.riders.$$ctx.user.seats"},
                                                1,
                                            ]
                                        }
                                    }
                                },
                            },
                            {
                                "title": "Persist Progress",
                                "description": "Persists transition data to keep the process deterministic.",
                                "type": "update.contract",
                                "update": [
                                    {
                                        "$set": {
                                            "context.accepted_seats_total": {
                                                "$cond": [
                                                    {
                                                        "$gte": [
                                                            {
                                                                "$ifNull": [
                                                                    "$context.accepted_seats_total",
                                                                    0,
                                                                ]
                                                            },
                                                            "$local.cancel_seats",
                                                        ]
                                                    },
                                                    {
                                                        "$subtract": [
                                                            {
                                                                "$ifNull": [
                                                                    "$context.accepted_seats_total",
                                                                    0,
                                                                ]
                                                            },
                                                            "$local.cancel_seats",
                                                        ]
                                                    },
                                                    0,
                                                ]
                                            },
                                            "states.$$ctx.user": "CANCELLED",
                                        }
                                    },
                                    {"$unset": "context.riders.$$ctx.user.seats"},
                                ],
                            },
                            {
                                "title": "Notify Stakeholders",
                                "description": "Sends contracts.user_cancelled so stakeholders can act at the right time.",
                                "type": "notify",
                                "notify": {
                                    "event": "contracts.user_cancelled",
                                    "targets": {"$$ctx.doc.context.driver": ["in_app", "push"]},
                                    "payload": {
                                        "principal": "$$ctx.user",
                                        "contract_id": {"$ctx": "doc._id"},
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
                                "title": "Persist Progress",
                                "description": "Persists transition data to keep the process deterministic.",
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "local.target_is_accepted": {
                                            "$eq": [
                                                {
                                                    "$ifNull": [
                                                        {"$ctx": "doc.states.$$ctx.payload.principal"},
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
                                "title": "Evaluate Branch",
                                "description": "Selects the branch that matches current trip conditions.",
                                "type": "if.else",
                                "condition": {"$ctx": "doc.local.target_is_accepted"},
                                "then_effects": [
                                    {
                                        "title": "Sync Group",
                                        "description": "Synchronizes group membership with current trip roster.",
                                        "type": "update.group",
                                        "group_id": {"$ctx": "doc.context.group_id"},
                                        "edit_members": {"remove_members": ["$$ctx.payload.principal"]},
                                    },
                                    {
                                        "title": "Persist Progress",
                                        "description": "Persists transition data to keep the process deterministic.",
                                        "type": "update.contract",
                                        "update": {
                                            "$set": {
                                                "local.remove_seats": {
                                                    "$ifNull": [
                                                        {"$ctx": "doc.context.riders.$$ctx.payload.principal.seats"},
                                                        1,
                                                    ]
                                                }
                                            }
                                        },
                                    },
                                    {
                                        "title": "Persist Progress",
                                        "description": "Persists transition data to keep the process deterministic.",
                                        "type": "update.contract",
                                        "update": [
                                            {
                                                "$set": {
                                                    "context.accepted_seats_total": {
                                                        "$cond": [
                                                            {
                                                                "$gte": [
                                                                    {
                                                                        "$ifNull": [
                                                                            "$context.accepted_seats_total",
                                                                            0,
                                                                        ]
                                                                    },
                                                                    "$local.remove_seats",
                                                                ]
                                                            },
                                                            {
                                                                "$subtract": [
                                                                    {
                                                                        "$ifNull": [
                                                                            "$context.accepted_seats_total",
                                                                            0,
                                                                        ]
                                                                    },
                                                                    "$local.remove_seats",
                                                                ]
                                                            },
                                                            0,
                                                        ]
                                                    },
                                                    "states.$$ctx.payload.principal": "CANCELLED",
                                                }
                                            },
                                            {"$unset": "context.riders.$$ctx.payload.principal.seats"},
                                        ],
                                    },
                                    {
                                        "title": "Notify Stakeholders",
                                        "description": "Sends contracts.user_removed_by_driver so stakeholders can act at the right time.",
                                        "type": "notify",
                                        "notify": {
                                            "event": "contracts.user_removed_by_driver",
                                            "targets": {
                                                "$$ctx.payload.principal": [
                                                    "in_app",
                                                    "push",
                                                ]
                                            },
                                            "payload": {"contract_id": {"$ctx": "doc._id"}},
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
                                "title": "Persist Progress",
                                "description": "Persists transition data to keep the process deterministic.",
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "local.cancel_trip_targets": {
                                            "$arrayToObject": {
                                                "$map": {
                                                    "input": {
                                                        "$filter": {
                                                            "input": {"$objectToArray": "$states"},
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
                                                        "v": ["in_app", "push"],
                                                    },
                                                }
                                            }
                                        }
                                    }
                                },
                            },
                            {
                                "title": "Move State",
                                "description": "Moves the contract state to support cancel the active trip.",
                                "type": "update.contract",
                                "update": {"$set": {"status": "CANCELED", "state": "CANCELED"}},
                            },
                            {
                                "title": "Notify Stakeholders",
                                "description": "Sends contracts.trip_cancelled_by_driver so stakeholders can act at the right time.",
                                "type": "notify",
                                "notify": {
                                    "event": "contracts.trip_cancelled_by_driver",
                                    "targets": "$$ctx.doc.local.cancel_trip_targets",
                                    "payload": {"contract_id": {"$ctx": "doc._id"}},
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
                                "title": "Move State",
                                "description": "Moves the contract state to support close recruiting and lock roster.",
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
                                "title": "Sync Group",
                                "description": "Synchronizes group membership with current trip roster.",
                                "type": "update.group",
                                "group_id": {"$ctx": "doc.context.group_id"},
                                "edit_members": {"remove_members": ["$$ctx.user"]},
                            },
                            {
                                "title": "Persist Progress",
                                "description": "Persists transition data to keep the process deterministic.",
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "local.cancel_seats": {
                                            "$ifNull": [
                                                {"$ctx": "doc.context.riders.$$ctx.user.seats"},
                                                1,
                                            ]
                                        }
                                    }
                                },
                            },
                            {
                                "title": "Persist Progress",
                                "description": "Persists transition data to keep the process deterministic.",
                                "type": "update.contract",
                                "update": [
                                    {
                                        "$set": {
                                            "context.accepted_seats_total": {
                                                "$cond": [
                                                    {
                                                        "$gte": [
                                                            {
                                                                "$ifNull": [
                                                                    "$context.accepted_seats_total",
                                                                    0,
                                                                ]
                                                            },
                                                            "$local.cancel_seats",
                                                        ]
                                                    },
                                                    {
                                                        "$subtract": [
                                                            {
                                                                "$ifNull": [
                                                                    "$context.accepted_seats_total",
                                                                    0,
                                                                ]
                                                            },
                                                            "$local.cancel_seats",
                                                        ]
                                                    },
                                                    0,
                                                ]
                                            },
                                            "states.$$ctx.user": "CANCELLED",
                                            "state": "RECRUITING",
                                        }
                                    },
                                    {"$unset": "context.riders.$$ctx.user.seats"},
                                ],
                            },
                            {
                                "title": "Notify Stakeholders",
                                "description": "Sends contracts.user_cancelled so stakeholders can act at the right time.",
                                "type": "notify",
                                "notify": {
                                    "event": "contracts.user_cancelled",
                                    "targets": {"$$ctx.doc.context.driver": ["in_app", "push"]},
                                    "payload": {
                                        "principal": "$$ctx.user",
                                        "contract_id": {"$ctx": "doc._id"},
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
                                "title": "Move State",
                                "description": "Moves the contract state to support reopen recruiting after ready.",
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
                                "title": "Schedule Timed Step",
                                "description": "Schedules RidersPickupCheckTimed as a timed lifecycle checkpoint.",
                                "type": "schedule.event_at",
                                "key": "riders_pickup_check_id",
                                "event_name": "RidersPickupCheckTimed",
                                "at": {"$ctx": "doc.context.driver_trip.origin.at"},
                                "actor_id": "system:cron",
                            },
                            {
                                "title": "Store Context",
                                "description": "Stores lifecycle context needed to start trip execution.",
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "context.riders_pickup_check_id": {"$ctx": "local.riders_pickup_check_id"},
                                        "context.driver_in_pickup_zone": False,
                                        "context.riders_picked_up": {},
                                        "context.pending_pickup_targets": {
                                            "$arrayToObject": {
                                                "$map": {
                                                    "input": {
                                                        "$filter": {
                                                            "input": {"$objectToArray": "$states"},
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
                                                        "v": ["in_app", "push"],
                                                    },
                                                }
                                            }
                                        },
                                    }
                                },
                            },
                            {
                                "title": "Move State",
                                "description": "Moves the contract state to support start trip execution.",
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
                                "title": "Persist Progress",
                                "description": "Persists transition data to keep the process deterministic.",
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "local.target_is_accepted": {
                                            "$eq": [
                                                {
                                                    "$ifNull": [
                                                        {"$ctx": "doc.states.$$ctx.payload.principal"},
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
                                "title": "Evaluate Branch",
                                "description": "Selects the branch that matches current trip conditions.",
                                "type": "if.else",
                                "condition": {"$ctx": "doc.local.target_is_accepted"},
                                "then_effects": [
                                    {
                                        "title": "Sync Group",
                                        "description": "Synchronizes group membership with current trip roster.",
                                        "type": "update.group",
                                        "group_id": {"$ctx": "doc.context.group_id"},
                                        "edit_members": {"remove_members": ["$$ctx.payload.principal"]},
                                    },
                                    {
                                        "title": "Persist Progress",
                                        "description": "Persists transition data to keep the process deterministic.",
                                        "type": "update.contract",
                                        "update": {
                                            "$set": {
                                                "local.remove_seats": {
                                                    "$ifNull": [
                                                        {"$ctx": "doc.context.riders.$$ctx.payload.principal.seats"},
                                                        1,
                                                    ]
                                                }
                                            }
                                        },
                                    },
                                    {
                                        "title": "Persist Progress",
                                        "description": "Persists transition data to keep the process deterministic.",
                                        "type": "update.contract",
                                        "update": [
                                            {
                                                "$set": {
                                                    "context.accepted_seats_total": {
                                                        "$cond": [
                                                            {
                                                                "$gte": [
                                                                    {
                                                                        "$ifNull": [
                                                                            "$context.accepted_seats_total",
                                                                            0,
                                                                        ]
                                                                    },
                                                                    "$local.remove_seats",
                                                                ]
                                                            },
                                                            {
                                                                "$subtract": [
                                                                    {
                                                                        "$ifNull": [
                                                                            "$context.accepted_seats_total",
                                                                            0,
                                                                        ]
                                                                    },
                                                                    "$local.remove_seats",
                                                                ]
                                                            },
                                                            0,
                                                        ]
                                                    },
                                                    "states.$$ctx.payload.principal": "CANCELLED",
                                                }
                                            },
                                            {"$unset": "context.riders.$$ctx.payload.principal.seats"},
                                        ],
                                    },
                                    {
                                        "title": "Notify Stakeholders",
                                        "description": "Sends contracts.user_removed_by_driver so stakeholders can act at the right time.",
                                        "type": "notify",
                                        "notify": {
                                            "event": "contracts.user_removed_by_driver",
                                            "targets": {
                                                "$$ctx.payload.principal": [
                                                    "in_app",
                                                    "push",
                                                ]
                                            },
                                            "payload": {"contract_id": {"$ctx": "doc._id"}},
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
                                "title": "Persist Progress",
                                "description": "Persists transition data to keep the process deterministic.",
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "local.cancel_trip_targets": {
                                            "$arrayToObject": {
                                                "$map": {
                                                    "input": {
                                                        "$filter": {
                                                            "input": {"$objectToArray": "$states"},
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
                                                        "v": ["in_app", "push"],
                                                    },
                                                }
                                            }
                                        }
                                    }
                                },
                            },
                            {
                                "title": "Move State",
                                "description": "Moves the contract state to support cancel the active trip.",
                                "type": "update.contract",
                                "update": {"$set": {"status": "CANCELED", "state": "CANCELED"}},
                            },
                            {
                                "title": "Notify Stakeholders",
                                "description": "Sends contracts.trip_cancelled_by_driver so stakeholders can act at the right time.",
                                "type": "notify",
                                "notify": {
                                    "event": "contracts.trip_cancelled_by_driver",
                                    "targets": "$$ctx.doc.local.cancel_trip_targets",
                                    "payload": {"contract_id": {"$ctx": "doc._id"}},
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
                                "title": "Store Context",
                                "description": "Stores lifecycle context needed to record driver pickup arrival.",
                                "type": "update.contract",
                                "update": {"$set": {"context.driver_in_pickup_zone": True}},
                            },
                            {
                                "title": "Cancel Schedule",
                                "description": "Cancels timers that are no longer relevant on this path.",
                                "type": "unschedule.event_at",
                                "event_id": {"$ctx": "doc.context.driver_pickup_check_id"},
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
                                "title": "Store Context",
                                "description": "Stores lifecycle context needed to record rider pickup arrival.",
                                "type": "update.contract",
                                "update": {"$set": {"context.riders_in_pickup_zone.$$ctx.user": True}},
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
                                "title": "Persist Progress",
                                "description": "Persists transition data to keep the process deterministic.",
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "local.can_pick_user": {
                                            "$and": [
                                                {
                                                    "$eq": [
                                                        {
                                                            "$ifNull": [
                                                                {"$ctx": "doc.states.$$ctx.payload.principal"},
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
                                "title": "Evaluate Branch",
                                "description": "Selects the branch that matches current trip conditions.",
                                "type": "if.else",
                                "condition": {"$ctx": "doc.local.can_pick_user"},
                                "then_effects": [
                                    {
                                        "title": "Persist Progress",
                                        "description": "Persists transition data to keep the process deterministic.",
                                        "type": "update.contract",
                                        "update": [
                                            {"$set": {"context.riders_picked_up.$$ctx.payload.principal": True}},
                                            {"$unset": "context.pending_pickup_targets.$$ctx.payload.principal"},
                                        ],
                                    },
                                    {
                                        "title": "Notify Stakeholders",
                                        "description": "Sends contracts.user_picked_up so stakeholders can act at the right time.",
                                        "type": "notify",
                                        "notify": {
                                            "event": "contracts.user_picked_up",
                                            "targets": {
                                                "$$ctx.payload.principal": [
                                                    "in_app",
                                                    "push",
                                                ]
                                            },
                                            "payload": {"contract_id": {"$ctx": "doc._id"}},
                                        },
                                    },
                                ],
                            },
                            {
                                "title": "Persist Progress",
                                "description": "Persists transition data to keep the process deterministic.",
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
                                "title": "Evaluate Branch",
                                "description": "Selects the branch that matches current trip conditions.",
                                "type": "if.else",
                                "condition": {"$ctx": "doc.local.all_riders_picked_up"},
                                "then_effects": [
                                    {
                                        "title": "Cancel Schedule",
                                        "description": "Cancels timers that are no longer relevant on this path.",
                                        "type": "unschedule.event_at",
                                        "event_id": {"$ctx": "doc.context.riders_pickup_check_id"},
                                    },
                                    {
                                        "title": "Move State",
                                        "description": "Moves the contract state to support confirm a rider pickup.",
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
                                        "title": "Move State",
                                        "description": "Moves the contract state to support confirm a rider pickup.",
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
                                "title": "Sync Group",
                                "description": "Synchronizes group membership with current trip roster.",
                                "type": "update.group",
                                "group_id": {"$ctx": "doc.context.group_id"},
                                "edit_members": {"remove_members": ["$$ctx.user"]},
                            },
                            {
                                "title": "Persist Progress",
                                "description": "Persists transition data to keep the process deterministic.",
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "local.cancel_seats": {
                                            "$ifNull": [
                                                {"$ctx": "doc.context.riders.$$ctx.user.seats"},
                                                1,
                                            ]
                                        }
                                    }
                                },
                            },
                            {
                                "title": "Persist Progress",
                                "description": "Persists transition data to keep the process deterministic.",
                                "type": "update.contract",
                                "update": [
                                    {
                                        "$set": {
                                            "context.accepted_seats_total": {
                                                "$cond": [
                                                    {
                                                        "$gte": [
                                                            {
                                                                "$ifNull": [
                                                                    "$context.accepted_seats_total",
                                                                    0,
                                                                ]
                                                            },
                                                            "$local.cancel_seats",
                                                        ]
                                                    },
                                                    {
                                                        "$subtract": [
                                                            {
                                                                "$ifNull": [
                                                                    "$context.accepted_seats_total",
                                                                    0,
                                                                ]
                                                            },
                                                            "$local.cancel_seats",
                                                        ]
                                                    },
                                                    0,
                                                ]
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
                                "title": "Notify Stakeholders",
                                "description": "Sends contracts.user_cancelled so stakeholders can act at the right time.",
                                "type": "notify",
                                "notify": {
                                    "event": "contracts.user_cancelled",
                                    "targets": {"$$ctx.doc.context.driver": ["in_app", "push"]},
                                    "payload": {
                                        "principal": "$$ctx.user",
                                        "contract_id": {"$ctx": "doc._id"},
                                    },
                                },
                            },
                        ],
                    },
                    "DriverPickupCheckTimed": {
                        "trigger": [{"type": "api", "path": "driver-pickup-check-timeout"}],
                        "effects": [
                            {
                                "title": "Evaluate Branch",
                                "description": "Selects the branch that matches current trip conditions.",
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
                                        "title": "Notify Stakeholders",
                                        "description": "Sends contracts.driver_pickup_check so stakeholders can act at the right time.",
                                        "type": "notify",
                                        "notify": {
                                            "event": "contracts.driver_pickup_check",
                                            "targets": {
                                                "$$ctx.doc.context.driver": [
                                                    "in_app",
                                                    "push",
                                                ]
                                            },
                                            "payload": {"contract_id": {"$ctx": "doc._id"}},
                                        },
                                    }
                                ],
                            }
                        ],
                    },
                    "RidersPickupCheckTimed": {
                        "trigger": [{"type": "api", "path": "riders-pickup-check-timeout"}],
                        "effects": [
                            {
                                "title": "Persist Progress",
                                "description": "Persists transition data to keep the process deterministic.",
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
                                "title": "Evaluate Branch",
                                "description": "Selects the branch that matches current trip conditions.",
                                "type": "if.else",
                                "condition": {"$ctx": "doc.local.has_pending_pickups"},
                                "then_effects": [
                                    {
                                        "title": "Notify Stakeholders",
                                        "description": "Sends contracts.rider_pickup_check so stakeholders can act at the right time.",
                                        "type": "notify",
                                        "notify": {
                                            "event": "contracts.rider_pickup_check",
                                            "targets": "$$ctx.doc.context.pending_pickup_targets",
                                            "payload": {"contract_id": {"$ctx": "doc._id"}},
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
                                "title": "Persist Progress",
                                "description": "Persists transition data to keep the process deterministic.",
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "local.cancel_trip_targets": {
                                            "$arrayToObject": {
                                                "$map": {
                                                    "input": {
                                                        "$filter": {
                                                            "input": {"$objectToArray": "$states"},
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
                                                        "v": ["in_app", "push"],
                                                    },
                                                }
                                            }
                                        }
                                    }
                                },
                            },
                            {
                                "title": "Move State",
                                "description": "Moves the contract state to support cancel the active trip.",
                                "type": "update.contract",
                                "update": {"$set": {"status": "CANCELED", "state": "CANCELED"}},
                            },
                            {
                                "title": "Notify Stakeholders",
                                "description": "Sends contracts.trip_cancelled_by_driver so stakeholders can act at the right time.",
                                "type": "notify",
                                "notify": {
                                    "event": "contracts.trip_cancelled_by_driver",
                                    "targets": "$$ctx.doc.local.cancel_trip_targets",
                                    "payload": {"contract_id": {"$ctx": "doc._id"}},
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
        desktop_sock = os.path.join(os.path.expanduser("~"), ".docker", "run", "docker.sock")
        if not os.environ.get("DOCKER_HOST") and os.path.exists(desktop_sock):
            os.environ["DOCKER_HOST"] = f"unix://{desktop_sock}"
        try:
            from testcontainers.mongodb import MongoDbContainer
        except Exception as ex:  # pragma: no cover - environment dependent
            raise unittest.SkipTest("contracts e2e requires testcontainers[mongodb]") from ex

        try:
            cls._mongo_container = MongoDbContainer("mongo:7.0")
            cls._mongo_container.start()
            cls._mongo_base_uri = str(cls._mongo_container.get_connection_url())
        except Exception as ex:  # pragma: no cover - environment dependent
            raise unittest.SkipTest("contracts e2e requires Docker with a runnable MongoDB container") from ex

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
            ),
            patch(
                "schedula.utils.form.server.contracts.engine.create_sadlock",
                new=lambda *_args, **_kwargs: contextlib.nullcontext(),
            ),
            patch(
                "schedula.utils.form.server.contracts.schedule.create_sadlock",
                new=lambda *_args, **_kwargs: contextlib.nullcontext(),
            ),
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
            enforcer.add_policy([ANON_USER, ADMIN_DOMAIN, "contracts:templates", "manage", "allow"])
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

            from schedula.utils.form.server.credits import get_wallet

            self.route_by_principal: Dict[str, str] = {}
            items_coll = self.app.config["MONGO_DB"]["items"]
            for uid in self.user_ids.values():
                principal = f"u:{uid}"
                route_id = str(ObjectId())
                route_doc = {
                    "cost": 10,
                    "capacity": 3,
                    "user_id": principal,
                    "origin": {
                        "lat": 45.0,
                        "lng": 9.0,
                        "at": "1970-01-01T00:00:00+00:00",
                    },
                    "destination": {"lat": 45.1, "lng": 9.1},
                }
                items_coll.insert_one(
                    {
                        "_id": ObjectId(route_id),
                        "category": "route",
                        "data": route_doc,
                        "created_by": principal,
                        "updated_by": principal,
                        "created_at": dt.datetime.utcnow(),
                        "updated_at": dt.datetime.utcnow(),
                    }
                )
                self.route_by_principal[principal] = route_id

                wallet = get_wallet(uid)
                wallet.charge(product="trip", credits=100)

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
        resp = self.client.post("/user/login", json={"email": email, "password": "UserPass123!"})
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
        resp = self.httpx.post("/contracts/templates", json=body, headers=self._headers("admin"))
        self.assertEqual(resp.status_code, 201, msg=resp.text)
        return str(resp.json()["id"])

    def _create_contract(self, template_id: str, context: Dict[str, Any], **extra: Any) -> httpx.Response:
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
        if payload is None and path == "accept-user":
            payload = {
                "seats": 1,
                "origin": {
                    "lat": 45.0,
                    "lng": 9.0,
                    "at": "1970-01-01T00:00:00+00:00",
                },
                "destination": {"lat": 45.1, "lng": 9.1},
            }
        if payload is None and path == "request-join":
            actor_principal = f"u:{self.user_ids[actor]}"
            payload = {
                "route_id": self.route_by_principal[actor_principal],
            }
        if payload is None and path == "driver-accept-start":
            payload = {"riders": [f"u:{self.user_ids['p1']}"]}
        return self.httpx.post(
            f"/contracts/{contract_id}/{path}",
            json={"payload": payload or {}},
            headers=self._headers(actor),
        )

    def _run_worker_once(self, *, now: dt.datetime | None = None) -> bool:
        from schedula.utils.form.server.contracts.schedule import (
            _func,
            _queue_coll,
            ack_done,
            claim_job,
            nack_retry,
            now_utc,
        )

        now = now or dt.datetime.now(dt.timezone.utc)
        with patch(
                "schedula.utils.form.server.contracts.schedule._claim_job_now",
                return_value=now,
        ):
            with self.app.app_context():
                coll = _queue_coll()
                job = claim_job(coll)
                if not job:
                    return False
                try:
                    resp = _func(**(job.get("payload") or {}))
                    if job.get("kind") == "cron":
                        coll.update_one(
                            {"_id": job["_id"]},
                            {
                                "$set": {
                                    "status": "PENDING",
                                    "run_at": now_utc() + dt.timedelta(seconds=10),
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
                except Exception as ex:
                    nack_retry(coll, job["_id"], ex, delay_s=0)
                    raise
        return True

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
            return int(coll.count_documents({"event": event, f"targets.{principal}": {"$exists": True}}))

    def _gherkin_context(self, initial_state: str = "START") -> Dict[str, Any]:
        driver_uid = self.user_ids["d1"]
        p1_uid = self.user_ids["p1"]
        rider_ids = [f"u:{p1_uid}"]
        driver_principal = f"u:{driver_uid}"
        rider_route_ids = [self.route_by_principal[principal] for principal in rider_ids]
        return {
            "contract_id": "C-001",
            "driver_trip_id": self.route_by_principal[driver_principal],
            "riders": rider_route_ids,
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
        self.assertEqual(self._post_event(cid, "accept-user", actor="p1").status_code, 200)
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
        self.assertEqual(self._post_event(cid, "accept-user", actor="p2").status_code, 200)
        self.assertEqual(
            self._post_event(
                cid,
                "invite-user",
                actor="d1",
                payload={"principal": f"u:{self.user_ids['p3']}"},
            ).status_code,
            200,
        )
        self.assertEqual(self._post_event(cid, "accept-user", actor="p3").status_code, 200)
        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        self.assertEqual(c["state"], "READY")
        return gid

    def test_start_user_initiated_sets_pending_driver_and_requesting_rider(
            self,
    ) -> None:
        cid = self._create_gherkin_contract(initial_state="START")
        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()

        self.assertEqual(c["state"], "START")
        self.assertEqual(self._user_state(c, self.user_ids["d1"]), "PENDING_DRIVER")
        self.assertEqual(self._user_state(c, self.user_ids["p1"]), "REQUESTING")

    def test_start_driver_accept_start_uses_payload_riders_only(self) -> None:
        cid = self._create_gherkin_contract(initial_state="START")

        self.assertEqual(self._post_event(cid, "request-join", actor="p4").status_code, 200)

        self.assertEqual(
            self._post_event(
                cid,
                "driver-accept-start",
                actor="d1",
                payload={"riders": [f"u:{self.user_ids['p1']}"]},
            ).status_code,
            200,
        )

        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        self.assertEqual(c["state"], "RECRUITING")
        self.assertEqual(self._user_state(c, self.user_ids["d1"]), "DRIVER")
        self.assertEqual(self._user_state(c, self.user_ids["p1"]), "PENDING")
        self.assertEqual(self._user_state(c, self.user_ids["p4"]), "REQUESTING")

    def test_start_request_join_adds_requesting_user_when_capacity_and_credits_ok(
            self,
    ) -> None:
        driver_principal = f"u:{self.user_ids['d1']}"
        before = self._count_notifications_for(driver_principal, "contracts.join_requested")

        cid = self._create_gherkin_contract(initial_state="START")
        r = self._post_event(cid, "request-join", actor="p4")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json().get("ok"))

        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        self.assertEqual(c["state"], "START")
        self.assertEqual(self._user_state(c, self.user_ids["p4"]), "REQUESTING")

        after = self._count_notifications_for(driver_principal, "contracts.join_requested")
        self.assertEqual(after, before + 1)

    def test_start_request_join_denies_when_user_has_insufficient_credits(self) -> None:
        cid = self._create_gherkin_contract(initial_state="START")
        p4_principal = f"u:{self.user_ids['p4']}"
        route_id = self.route_by_principal[p4_principal]

        with self.app.app_context():
            self.app.config["MONGO_DB"]["items"].update_one({"_id": ObjectId(route_id)}, {"$set": {"data.cost": 1000}})

        r = self._post_event(cid, "request-join", actor="p4")
        self.assertEqual(r.status_code, 200)

        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        self.assertEqual(self._user_state(c, self.user_ids["p4"]), "")

    def test_start_cancel_join_request_last_user_re_notifies_driver(self) -> None:
        driver_principal = f"u:{self.user_ids['d1']}"
        before = self._count_notifications_for(driver_principal, "contracts.request_ride")

        cid = self._create_gherkin_contract(initial_state="START")
        after_create = self._count_notifications_for(driver_principal, "contracts.request_ride")
        self.assertEqual(after_create, before + 1)

        self.assertEqual(self._post_event(cid, "cancel-join-request", actor="p1").status_code, 200)

        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        self.assertEqual(c["state"], "START")
        self.assertEqual((c.get("context") or {}).get("riders"), {})

        after_cancel = self._count_notifications_for(driver_principal, "contracts.request_ride")
        self.assertEqual(after_cancel, before + 2)
