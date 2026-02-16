# coding: utf-8
from __future__ import annotations

import contextlib
import datetime as dt
import os
import unittest
import uuid
from typing import Any, Dict, List
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
                        "additionalProperties": False,
                    },
                    "effects": [
                        {
                            "title": "Load Driver Route",
                            "description": "Loads the driver route item so START can derive owner, trip geometry, and seat capacity.",
                            "type": "get.item",
                            "item_id": "$$ctx.doc.context.driver_trip_id",
                            "key": "driver_route",
                        },
                        {
                            "title": "Load Rider Routes",
                            "description": "Loads rider route items from the initial route id list to hydrate rider identities and trips.",
                            "type": "get.item",
                            "item_id": "$$ctx.doc.context.riders",
                            "key": "rider_routes",
                        },
                        {
                            "title": "Hydrate Route Inputs",
                            "description": "Derives driver, capacity, driver trip and rider map from loaded route items before branching.",
                            "type": "update.contract",
                            "update": [
                                {
                                    "$set": {
                                        "context.driver_route": {
                                            "accepted_seats": 0,
                                            "trip": {
                                                "origin": "$local.driver_route.data.origin",
                                                "destination": "$local.driver_route.data.destination",
                                            },
                                            "capacity": {
                                                "$ifNull": [
                                                    "$local.driver_route.data.capacity",
                                                    0,
                                                ]
                                            },
                                        },
                                        "context.driver": "$local.driver_route.data.user_id",
                                    }
                                },
                                {
                                    "$set": {
                                        "context.riders": {
                                            "$arrayToObject": {
                                                "$map": {
                                                    "input": {
                                                        "$filter": {
                                                            "input": "$local.rider_routes",
                                                            "as": "r",
                                                            "cond": {
                                                                "$and": [
                                                                    {
                                                                        "$ne": [
                                                                            "$$r",
                                                                            [],
                                                                        ]
                                                                    },
                                                                    {
                                                                        "$lte": [
                                                                            {
                                                                                "$ifNull": [
                                                                                    "$$r.data.seats",
                                                                                    1,
                                                                                ]
                                                                            },
                                                                            {
                                                                                "$ifNull": [
                                                                                    "$local.driver_route.data.capacity",
                                                                                    0,
                                                                                ]
                                                                            },
                                                                        ]
                                                                    },
                                                                    {
                                                                        "$ne": [
                                                                            "$$r.data.user_id",
                                                                            "$local.driver_route.data.user_id",
                                                                        ]
                                                                    },
                                                                ]
                                                            },
                                                        }
                                                    },
                                                    "as": "r",
                                                    "in": {
                                                        "k": {
                                                            "$toString": "$$r.data.user_id"
                                                        },
                                                        "v": {
                                                            "id": "$$r._id",
                                                            "cost": {
                                                                "$ifNull": [
                                                                    "$$r.data.cost",
                                                                    0,
                                                                ]
                                                            },
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
                                        }
                                    }
                                },
                            ],
                        },
                        {
                            "title": "Compute Start Context",
                            "description": "Determines whether START was initiated by the driver or by a rider request.",
                            "type": "update.contract",
                            "update": {
                                "$set": {
                                    "local.start_initiated_by_driver": {
                                        "$eq": ["$$ctx.user", "$context.driver"]
                                    }
                                }
                            },
                        },
                        {
                            "title": "Branch Start Flow",
                            "description": "Routes START initialization through driver-led or rider-led onboarding checks.",
                            "type": "if.else",
                            "condition": {"$ctx": "local.start_initiated_by_driver"},
                            "then_effects": [
                                {
                                    "title": "Mark Initial Riders Pending",
                                    "description": "Sets all initial riders to pending confirmation before onboarding begins.",
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
                                    "title": "Confirm Driver Participation",
                                    "description": "Marks the driver as active for the onboarding lifecycle.",
                                    "type": "update.contract",
                                    "update": {
                                        "$set": {
                                            "states.$$ctx.doc.context.driver": "DRIVER"
                                        }
                                    },
                                },
                                {
                                    "title": "Build Initial Invite Targets",
                                    "description": "Builds notification targets for riders included in the initial START context.",
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
                                                            "v": [
                                                                "in_app",
                                                                "push",
                                                            ],
                                                        },
                                                    }
                                                }
                                            }
                                        }
                                    },
                                },
                                {
                                    "title": "Notify Initial Riders",
                                    "description": "Sends invitation notifications to all initial riders.",
                                    "type": "notify",
                                    "notify": {
                                        "event": "contracts.user_invited",
                                        "targets": {
                                            "$ctx": "local.initial_invite_targets"
                                        },
                                        "payload": {"contract_id": {"$ctx": "doc._id"}},
                                    },
                                },
                                {
                                    "title": "Move To Onboarding",
                                    "description": "Transitions the contract to ONBOARDING when driver-initiated checks succeed.",
                                    "type": "update.contract",
                                    "update": {"$set": {"state": "ONBOARDING"}},
                                },
                            ],
                            "else_effects": [
                                {
                                    "title": "Load Rider Start Request",
                                    "description": "Loads the requesting rider route from context for balance and feasibility validation.",
                                    "type": "update.contract",
                                    "update": {
                                        "$set": {
                                            "local.route": "$context.riders.$$ctx.user",
                                        }
                                    },
                                },
                                {
                                    "title": "Validate Rider Presence",
                                    "description": "Continues only when the requesting rider route is present in START context.",
                                    "type": "if.else",
                                    "condition": {"$ctx": "local.route"},
                                    "then_effects": [
                                        {
                                            "title": "Read Requesting Rider Balance",
                                            "description": "Reads rider credits to validate the initial START reservation.",
                                            "type": "balance.credits",
                                            "key": "balance_credits",
                                            "credit": {"product": "coin"},
                                        },
                                        {
                                            "title": "Compute Rider Eligibility",
                                            "description": "Computes missing credits and validates rider affordability for START.",
                                            "type": "update.contract",
                                            "update": [
                                                {
                                                    "$set": {
                                                        "local.missing_credits": {
                                                            "$max": [
                                                                {
                                                                    "$subtract": [
                                                                        "$local.route.cost",
                                                                        {
                                                                            "$ifNull": [
                                                                                {
                                                                                    "$ref": "/items/route/$$ctx.local.route.id/data.reserved_credits"
                                                                                },
                                                                                0,
                                                                            ]
                                                                        },
                                                                    ]
                                                                },
                                                                0,
                                                            ]
                                                        },
                                                    }
                                                },
                                                {
                                                    "$set": {
                                                        "local.has_balance": {
                                                            "$gte": [
                                                                {
                                                                    "$ifNull": [
                                                                        "$local.balance_credits",
                                                                        0,
                                                                    ]
                                                                },
                                                                "$local.missing_credits",
                                                            ]
                                                        },
                                                    }
                                                },
                                            ],
                                        },
                                        {
                                            "title": "Evaluate Rider Start Feasibility",
                                            "description": "Admits rider-initiated START only when credit reservation constraints are satisfied.",
                                            "type": "if.else",
                                            "condition": {"$ctx": "local.has_balance"},
                                            "then_effects": [
                                                {
                                                    "title": "Reserve Rider Credits",
                                                    "description": "Reserves the missing rider credits required to enter onboarding.",
                                                    "type": "use.credits",
                                                    "credit": {
                                                        "product": "coin",
                                                        "amount": {
                                                            "$ctx": "local.missing_credits"
                                                        },
                                                    },
                                                },
                                                {
                                                    "title": "Persist Route Credit Hold and Link Contract To Initial Route",
                                                    "description": "Stores the retained START credits on the requester route item for reconciliation.",
                                                    "type": "update.item",
                                                    "item_id": {
                                                        "$ctx": "local.route.id"
                                                    },
                                                    "update": {
                                                        "$set": {
                                                            "data.reserved_credits": {
                                                                "$add": [
                                                                    {
                                                                        "$ifNull": [
                                                                            "$data.reserved_credits",
                                                                            0,
                                                                        ]
                                                                    },
                                                                    {
                                                                        "$ctx": "local.missing_credits"
                                                                    },
                                                                ]
                                                            },
                                                            "data.contract_ids": {
                                                                "$setUnion": [
                                                                    {
                                                                        "$ifNull": [
                                                                            "$data.contract_ids",
                                                                            [],
                                                                        ]
                                                                    },
                                                                    [
                                                                        {
                                                                            "$ctx": "doc._id"
                                                                        }
                                                                    ],
                                                                ]
                                                            },
                                                        }
                                                    },
                                                },
                                                {
                                                    "title": "Set Initial Participant States",
                                                    "description": "Sets rider to REQUESTING and driver to PENDING_DRIVER for onboarding.",
                                                    "type": "update.contract",
                                                    "update": [
                                                        {
                                                            "$set": {
                                                                "states.$$ctx.user": "REQUESTING",
                                                            }
                                                        },
                                                        {
                                                            "$set": {
                                                                "states.$$ctx.doc.context.driver": "PENDING_DRIVER"
                                                            }
                                                        },
                                                    ],
                                                },
                                                {
                                                    "title": "Notify Driver Of Start Request",
                                                    "description": "Notifies the driver that a rider requested to start onboarding.",
                                                    "type": "notify",
                                                    "notify": {
                                                        "event": "contracts.request_ride",
                                                        "targets": {
                                                            "$$ctx.doc.context.driver": [
                                                                "in_app",
                                                                "push",
                                                            ]
                                                        },
                                                        "payload": {
                                                            "contract_id": {
                                                                "$ctx": "doc._id"
                                                            }
                                                        },
                                                    },
                                                },
                                                {
                                                    "title": "Move To Onboarding",
                                                    "description": "Transitions the contract to ONBOARDING after rider-initiated checks succeed.",
                                                    "type": "update.contract",
                                                    "update": {
                                                        "$set": {"state": "ONBOARDING"}
                                                    },
                                                },
                                            ],
                                            "else_effects": [
                                                {
                                                    "title": "Delete Invalid Start Contract",
                                                    "description": "Deletes the contract when rider-initiated START checks fail.",
                                                    "type": "delete.contract",
                                                }
                                            ],
                                        },
                                    ],
                                    "else_effects": [
                                        {
                                            "title": "Delete Invalid Start Contract",
                                            "description": "Deletes the contract when START initialization constraints fail.",
                                            "type": "delete.contract",
                                        }
                                    ],
                                },
                            ],
                        },
                    ],
                },
            },
            "ONBOARDING": {
                "events": {
                    "JoinRequest": {
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
                                    "ok": "$$ctx.local.can_join_trip",
                                    "event": "request_join",
                                },
                            }
                        ],
                        "effects": [
                            {
                                "title": "Load Rider Join Route",
                                "description": "Loads the rider route from payload to evaluate join feasibility in onboarding.",
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "local.route": {
                                            "id": "$$ctx.payload.route_id",
                                            "cost": {
                                                "$ifNull": [
                                                    {
                                                        "$ref": "/items/route/$$ctx.payload.route_id/data.cost"
                                                    },
                                                    0,
                                                ]
                                            },
                                            "seats": {
                                                "$ifNull": [
                                                    {
                                                        "$ref": "/items/route/$$ctx.payload.route_id/data.seats"
                                                    },
                                                    1,
                                                ]
                                            },
                                            "trip": {
                                                "origin": {
                                                    "$ref": "/items/route/$$ctx.payload.route_id/data.origin"
                                                },
                                                "destination": {
                                                    "$ref": "/items/route/$$ctx.payload.route_id/data.destination"
                                                },
                                            },
                                        },
                                    }
                                },
                            },
                            {
                                "title": "Check Join Capacity",
                                "description": "Verifies that adding the rider seats does not exceed driver capacity.",
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "local.has_capacity_for_join": {
                                            "$lte": [
                                                {
                                                    "$add": [
                                                        "$context.driver_route.accepted_seats",
                                                        "$local.route.seats",
                                                    ]
                                                },
                                                "$context.driver_route.capacity",
                                            ]
                                        },
                                    }
                                },
                            },
                            {
                                "title": "Read Rider Credits",
                                "description": "Reads rider credits before evaluating onboarding join feasibility.",
                                "type": "balance.credits",
                                "credit": {"product": "coin"},
                                "key": "balance_credits",
                            },
                            {
                                "title": "Validate Join Prerequisites",
                                "description": "Combines capacity and credit checks to decide whether the join request can proceed.",
                                "type": "update.contract",
                                "update": [
                                    {
                                        "$set": {
                                            "local.missing_credits": {
                                                "$max": [
                                                    {
                                                        "$subtract": [
                                                            "$local.route.cost",
                                                            {
                                                                "$ifNull": [
                                                                    {
                                                                        "$ref": "/items/route/$$ctx.local.route.id/data.reserved_credits"
                                                                    },
                                                                    0,
                                                                ]
                                                            },
                                                        ]
                                                    },
                                                    0,
                                                ]
                                            },
                                        }
                                    },
                                    {
                                        "$set": {
                                            "local.has_balance": {
                                                "$gte": [
                                                    {
                                                        "$ifNull": [
                                                            "$local.balance_credits",
                                                            0,
                                                        ]
                                                    },
                                                    "$local.missing_credits",
                                                ]
                                            },
                                            "local.has_seats_availability": {
                                                "$lte": [
                                                    {
                                                        "$add": [
                                                            "$context.driver_route.accepted_seats",
                                                            "$local.route.seats",
                                                        ]
                                                    },
                                                    "$context.driver_route.capacity",
                                                ]
                                            },
                                        }
                                    },
                                    {
                                        "$set": {
                                            "local.can_join_trip": {
                                                "$and": [
                                                    "$local.has_balance",
                                                    "$local.has_seats_availability",
                                                ]
                                            },
                                        }
                                    },
                                ],
                            },
                            {
                                "title": "Evaluate Join Decision",
                                "description": "Executes join effects only when onboarding feasibility checks are satisfied.",
                                "type": "if.else",
                                "condition": {"$ctx": "local.can_join_trip"},
                                "then_effects": [
                                    {
                                        "title": "Reserve Join Credits",
                                        "description": "Reserves the missing rider credits needed for this join request.",
                                        "type": "use.credits",
                                        "credit": {
                                            "product": "coin",
                                            "amount": {"$ctx": "local.missing_credits"},
                                        },
                                    },
                                    {
                                        "title": "Persist Route Hold And Contract Link",
                                        "description": "Stores reserved credits and links this contract on the rider route item.",
                                        "type": "update.item",
                                        "item_id": {"$ctx": "local.route.id"},
                                        "update": {
                                            "$set": {
                                                "data.reserved_credits": {
                                                    "$add": [
                                                        {
                                                            "$ifNull": [
                                                                "$data.reserved_credits",
                                                                0,
                                                            ]
                                                        },
                                                        {
                                                            "$ctx": "local.missing_credits"
                                                        },
                                                    ]
                                                },
                                                "data.contract_ids": {
                                                    "$setUnion": [
                                                        {
                                                            "$ifNull": [
                                                                "$data.contract_ids",
                                                                [],
                                                            ]
                                                        },
                                                        [{"$ctx": "doc._id"}],
                                                    ]
                                                },
                                            }
                                        },
                                    },
                                    {
                                        "title": "Set Rider Requesting State",
                                        "description": "Marks the rider as REQUESTING while awaiting driver action.",
                                        "type": "update.contract",
                                        "update": [
                                            {
                                                "$set": {
                                                    "states.$$ctx.user": "REQUESTING"
                                                }
                                            },
                                        ],
                                    },
                                    {
                                        "title": "Store Rider Route Snapshot",
                                        "description": "Stores route snapshot details for the requesting rider in contract context.",
                                        "type": "update.contract",
                                        "update": {
                                            "$set": {
                                                "states.$$ctx.user": "REQUESTING",
                                                "context.riders.$$ctx.user.id": "$local.route.id",
                                                "context.riders.$$ctx.user.cost": "$local.route.cost",
                                                "context.riders.$$ctx.user.seats": "$local.route.seats",
                                                "context.riders.$$ctx.user.trip": "$local.route.trip",
                                            }
                                        },
                                    },
                                    {
                                        "title": "Notify Driver Of Join Request",
                                        "description": "Notifies the driver that a new rider requested to join.",
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
                                                "contract_id": {"$ctx": "doc._id"}
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
                                "title": "Capture Rider Route Snapshot",
                                "description": "Captures the rider route before removing REQUESTING state and links.",
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "local.route": {
                                            "$ctx": "doc.context.riders.$$ctx.user"
                                        }
                                    }
                                },
                            },
                            {
                                "title": "Unlink Contract From Rider Route",
                                "description": "Removes this contract id from the rider route item linkage list.",
                                "type": "update.item",
                                "item_id": {"$ctx": "local.route.id"},
                                "update": {
                                    "$set": {
                                        "data.contract_ids": {
                                            "$setDifference": [
                                                {"$ifNull": ["$data.contract_ids", []]},
                                                [{"$ctx": "doc._id"}],
                                            ]
                                        }
                                    }
                                },
                            },
                            {
                                "title": "Clear Rider Join Context",
                                "description": "Removes rider state and route context after join cancellation.",
                                "type": "update.contract",
                                "update": {
                                    "$unset": [
                                        "states.$$ctx.user",
                                        "context.riders.$$ctx.user",
                                    ]
                                },
                            },
                            {
                                "title": "Compute Cancellation Refund Eligibility",
                                "description": "Determines whether reserved credits can be refunded based on remaining route links.",
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "local.has_cancel_refund": {
                                            "$eq": [
                                                {
                                                    "$size": {
                                                        "$ifNull": [
                                                            {
                                                                "$ref": "/items/route/$$ctx.local.route.id/data.contract_ids"
                                                            },
                                                            [],
                                                        ]
                                                    }
                                                },
                                                0,
                                            ]
                                        }
                                    }
                                },
                            },
                            {
                                "title": "Refund Cancelling Rider",
                                "description": "Refunds reserved credits when the cancelling rider has no remaining linked contracts.",
                                "type": "if.else",
                                "condition": {"$ctx": "local.has_cancel_refund"},
                                "then_effects": [
                                    {
                                        "title": "Apply Rider Refund",
                                        "description": "Applies the computed credit refund to the cancelling rider wallet.",
                                        "type": "charge.credits",
                                        "credit": {
                                            "product": "coin",
                                            "amount": {
                                                "$ref": "/items/route/$$ctx.local.route.id/data.reserved_credits"
                                            },
                                        },
                                    },
                                    {
                                        "title": "Clear Route Reserved Credits",
                                        "description": "Clears retained route credits after refunding the final linked request.",
                                        "type": "update.item",
                                        "item_id": {"$ctx": "local.route.id"},
                                        "update": {
                                            "$set": {"data.reserved_credits": 0}
                                        },
                                    },
                                ],
                            },
                            {
                                "title": "Check Remaining Interested Riders",
                                "description": "Checks whether any riders are still interested after cancellation.",
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
                                "title": "Evaluate Driver Re-Notification",
                                "description": "Notifies the driver again when no interested riders remain.",
                                "type": "if.else",
                                "condition": {"$ctx": "local.has_interested_users"},
                                "else_effects": [
                                    {
                                        "title": "Notify Driver Of Empty Queue",
                                        "description": "Notifies the driver that no rider requests remain after cancellation.",
                                        "type": "notify",
                                        "notify": {
                                            "event": "contracts.request_ride",
                                            "targets": {
                                                "$$ctx.doc.context.driver": [
                                                    "in_app",
                                                    "push",
                                                ]
                                            },
                                            "payload": {
                                                "contract_id": {"$ctx": "doc._id"}
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
                                "path": "driver-accept-start",
                                "method": "POST",
                                "payload_schema": {
                                    "type": "object",
                                    "required": ["rider"],
                                    "properties": {
                                        "rider": {
                                            "type": "string",
                                            "pattern": "^u:.+$",
                                        },
                                    },
                                    "additionalProperties": False,
                                },
                                "allow_principals": ["$$ctx.doc.context.driver"],
                                "response": {
                                    "ok": {"$ctx": "doc.local.can_accept_start"},
                                    "event": "driver_accept_start",
                                },
                            }
                        ],
                        "effects": [
                            {
                                "title": "Validate Driver Acceptance",
                                "description": "Validates rider state and seat capacity before driver acceptance.",
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "local.can_accept_start": {
                                            "$and": [
                                                {
                                                    "$eq": [
                                                        {
                                                            "$ctx": "doc.states.$$ctx.payload.rider"
                                                        },
                                                        "REQUESTING",
                                                    ]
                                                },
                                                {
                                                    "$lte": [
                                                        {
                                                            "$add": [
                                                                "$context.driver_route.accepted_seats",
                                                                {
                                                                    "$ifNull": [
                                                                        {
                                                                            "$ctx": "doc.context.riders.$$ctx.payload.rider.seats"
                                                                        },
                                                                        1,
                                                                    ]
                                                                },
                                                            ]
                                                        },
                                                        "$context.driver_route.capacity",
                                                    ]
                                                },
                                            ]
                                        }
                                    }
                                },
                            },
                            {
                                "title": "Evaluate Driver Acceptance",
                                "type": "if.else",
                                "condition": {"$ctx": "doc.local.can_accept_start"},
                                "then_effects": [
                                    {
                                        "title": "Set Rider Accepted",
                                        "description": "Marks the selected rider as accepted and prepares direct rider notification targets.",
                                        "type": "update.contract",
                                        "update": {
                                            "$set": {
                                                "states.$$ctx.payload.rider": "ACCEPTED",
                                                "local.rider_targets": {
                                                    "$arrayToObject": {
                                                        "$map": {
                                                            "input": [
                                                                "$$payload.rider"
                                                            ],
                                                            "as": "p",
                                                            "in": {
                                                                "k": "$$p",
                                                                "v": [
                                                                    "in_app",
                                                                    "push",
                                                                ],
                                                            },
                                                        }
                                                    }
                                                },
                                            }
                                        },
                                    },
                                    {
                                        "title": "Load Accepted Rider Route",
                                        "description": "Loads the accepted rider route to identify related contracts.",
                                        "type": "get.item",
                                        "item_id": {
                                            "$ctx": "doc.context.riders.$$ctx.payload.rider.id"
                                        },
                                        "key": "accepted_rider_route",
                                    },
                                    {
                                        "title": "Prepare Cross-Contract Rider Removal",
                                        "description": "Builds updates to remove the accepted rider from other contracts sharing the route.",
                                        "type": "update.contract",
                                        "update": {
                                            "$set": {
                                                "local.remove_rider_other_contracts": {
                                                    "$arrayToObject": {
                                                        "$map": {
                                                            "input": {
                                                                "$filter": {
                                                                    "input": {
                                                                        "$ifNull": [
                                                                            "$local.accepted_rider_route.data.contract_ids",
                                                                            [],
                                                                        ]
                                                                    },
                                                                    "as": "cid",
                                                                    "cond": {
                                                                        "$ne": [
                                                                            "$$cid",
                                                                            "$_id",
                                                                        ]
                                                                    },
                                                                }
                                                            },
                                                            "as": "cid",
                                                            "in": {
                                                                "k": "$$cid",
                                                                "v": [
                                                                    {
                                                                        "$literal": {
                                                                            "$unset": [
                                                                                "context.riders.$$ctx.payload.rider",
                                                                                "states.$$ctx.payload.rider",
                                                                            ]
                                                                        }
                                                                    },
                                                                ],
                                                            },
                                                        }
                                                    }
                                                }
                                            }
                                        },
                                    },
                                    {
                                        "title": "Apply Rider Removal To Other Contracts",
                                        "description": "Applies cross-contract updates that remove the accepted rider from competing contracts.",
                                        "type": "update.contract",
                                        "updates": {
                                            "$ctx": "local.remove_rider_other_contracts"
                                        },
                                    },
                                    {
                                        "title": "Load Related Contracts",
                                        "description": "Loads contracts linked by the accepted rider route to collect affected driver principals.",
                                        "type": "update.contract",
                                        "update": {
                                            "$set": {
                                                "local.accepted_rider_contract_ids": {
                                                    "$ifNull": [
                                                        "$local.accepted_rider_route.data.contract_ids",
                                                        [],
                                                    ]
                                                }
                                            }
                                        },
                                    },
                                    {
                                        "title": "Load Related Contracts",
                                        "description": "Loads contracts linked by the accepted rider route to collect affected driver principals.",
                                        "type": "get.contract",
                                        "contract_id": {
                                            "$ctx": "local.accepted_rider_contract_ids"
                                        },
                                        "key": "accepted_rider_contracts",
                                    },
                                    {
                                        "title": "Persist Winning Contract Link",
                                        "description": "Persists the winning contract id on the accepted rider route item.",
                                        "type": "update.item",
                                        "item_id": {
                                            "$ctx": "doc.context.riders.$$ctx.payload.rider.id"
                                        },
                                        "update": {
                                            "$set": {
                                                "data.contract_ids": [
                                                    {"$ctx": "doc._id"}
                                                ],
                                            }
                                        },
                                    },
                                    {
                                        "title": "Build Other Driver Targets",
                                        "description": "Builds notification targets for drivers of contracts that lost the rider.",
                                        "type": "update.contract",
                                        "update": {
                                            "$set": {
                                                "local.other_contract_driver_targets": {
                                                    "$arrayToObject": {
                                                        "$map": {
                                                            "input": {
                                                                "$filter": {
                                                                    "input": {
                                                                        "$ifNull": [
                                                                            "$local.accepted_rider_contracts",
                                                                            [],
                                                                        ]
                                                                    },
                                                                    "as": "c",
                                                                    "cond": {
                                                                        "$ne": [
                                                                            "$$c._id",
                                                                            "$_id",
                                                                        ]
                                                                    },
                                                                }
                                                            },
                                                            "as": "c",
                                                            "in": {
                                                                "k": "$$c.context.driver",
                                                                "v": ["in_app", "push"],
                                                            },
                                                        }
                                                    }
                                                },
                                                "local.has_other_contract_driver_targets": {
                                                    "$gt": [
                                                        {
                                                            "$size": {
                                                                "$objectToArray": {
                                                                    "$ifNull": [
                                                                        "$local.other_contract_driver_targets",
                                                                        {},
                                                                    ]
                                                                }
                                                            }
                                                        },
                                                        0,
                                                    ]
                                                },
                                            }
                                        },
                                    },
                                    {
                                        "title": "Notify Other Drivers",
                                        "description": "Notifies affected drivers that the accepted rider is no longer available.",
                                        "type": "if.else",
                                        "condition": {
                                            "$ctx": "doc.local.has_other_contract_driver_targets"
                                        },
                                        "then_effects": [
                                            {
                                                "title": "Dispatch Rider Unavailable",
                                                "description": "Sends rider unavailable notifications to affected drivers.",
                                                "type": "notify",
                                                "notify": {
                                                    "event": "contracts.rider_unavailable",
                                                    "targets": {
                                                        "$ctx": "local.other_contract_driver_targets"
                                                    },
                                                    "payload": {
                                                        "contract_id": {
                                                            "$ctx": "doc._id"
                                                        },
                                                        "principal": "$$ctx.payload.rider",
                                                    },
                                                },
                                            },
                                        ],
                                    },
                                    {
                                        "title": "Notify Accepted Rider",
                                        "description": "Notifies the selected rider that the join request was accepted.",
                                        "type": "notify",
                                        "notify": {
                                            "event": "contracts.accepted_request",
                                            "targets": {"$ctx": "local.rider_targets"},
                                            "payload": {
                                                "contract_id": {"$ctx": "doc._id"}
                                            },
                                        },
                                    },
                                    {
                                        "title": "Finalize Driver Acceptance",
                                        "description": "Confirms driver status and updates accepted seat totals after acceptance.",
                                        "type": "update.contract",
                                        "update": [
                                            {
                                                "$set": {
                                                    "states.$$ctx.doc.context.driver": "DRIVER"
                                                }
                                            },
                                            {
                                                "$set": {
                                                    "context.accepted_seats_total": {
                                                        "$add": [
                                                            {
                                                                "$ifNull": [
                                                                    "$context.accepted_seats_total",
                                                                    0,
                                                                ]
                                                            },
                                                            {
                                                                "$ifNull": [
                                                                    {
                                                                        "$ctx": "doc.context.riders.$$ctx.payload.rider.seats"
                                                                    },
                                                                    1,
                                                                ]
                                                            },
                                                        ]
                                                    }
                                                }
                                            },
                                        ],
                                    },
                                    {
                                        "title": "Compute Over-Capacity Riders",
                                        "description": "Finds pending or requesting riders that no longer fit remaining capacity after acceptance.",
                                        "type": "update.contract",
                                        "update": {
                                            "$set": {
                                                "local.over_capacity_principals": {
                                                    "$filter": {
                                                        "input": {
                                                            "$map": {
                                                                "input": {
                                                                    "$objectToArray": "$states"
                                                                },
                                                                "as": "kv",
                                                                "in": "$$kv.k",
                                                            }
                                                        },
                                                        "as": "principal",
                                                        "cond": {
                                                            "$and": [
                                                                {
                                                                    "$ne": [
                                                                        "$$principal",
                                                                        "$$payload.rider",
                                                                    ]
                                                                },
                                                                {
                                                                    "$in": [
                                                                        {
                                                                            "$arrayElemAt": [
                                                                                {
                                                                                    "$map": {
                                                                                        "input": {
                                                                                            "$filter": {
                                                                                                "input": {
                                                                                                    "$objectToArray": "$states"
                                                                                                },
                                                                                                "as": "kv",
                                                                                                "cond": {
                                                                                                    "$eq": [
                                                                                                        "$$kv.k",
                                                                                                        "$$principal",
                                                                                                    ]
                                                                                                },
                                                                                            }
                                                                                        },
                                                                                        "as": "kv",
                                                                                        "in": "$$kv.v",
                                                                                    }
                                                                                },
                                                                                0,
                                                                            ]
                                                                        },
                                                                        [
                                                                            "REQUESTING",
                                                                            "PENDING",
                                                                        ],
                                                                    ]
                                                                },
                                                                {
                                                                    "$gt": [
                                                                        {
                                                                            "$ifNull": [
                                                                                {
                                                                                    "$arrayElemAt": [
                                                                                        {
                                                                                            "$map": {
                                                                                                "input": {
                                                                                                    "$filter": {
                                                                                                        "input": {
                                                                                                            "$objectToArray": {
                                                                                                                "$ifNull": [
                                                                                                                    "$context.riders",
                                                                                                                    {},
                                                                                                                ]
                                                                                                            }
                                                                                                        },
                                                                                                        "as": "rv",
                                                                                                        "cond": {
                                                                                                            "$eq": [
                                                                                                                "$$rv.k",
                                                                                                                "$$principal",
                                                                                                            ]
                                                                                                        },
                                                                                                    }
                                                                                                },
                                                                                                "as": "rv",
                                                                                                "in": "$$rv.v.seats",
                                                                                            }
                                                                                        },
                                                                                        0,
                                                                                    ]
                                                                                },
                                                                                1,
                                                                            ]
                                                                        },
                                                                        {
                                                                            "$max": [
                                                                                {
                                                                                    "$subtract": [
                                                                                        {
                                                                                            "$ifNull": [
                                                                                                "$context.driver_route.capacity",
                                                                                                0,
                                                                                            ]
                                                                                        },
                                                                                        {
                                                                                            "$ifNull": [
                                                                                                "$context.accepted_seats_total",
                                                                                                0,
                                                                                            ]
                                                                                        },
                                                                                    ]
                                                                                },
                                                                                0,
                                                                            ]
                                                                        },
                                                                    ]
                                                                },
                                                            ]
                                                        },
                                                    }
                                                }
                                            }
                                        },
                                    },
                                    {
                                        "title": "Prepare Over-Capacity Targets",
                                        "description": "Builds notification targets and guards for riders removed by capacity constraints.",
                                        "type": "update.contract",
                                        "update": {
                                            "$set": {
                                                "local.over_capacity_targets": {
                                                    "$arrayToObject": {
                                                        "$map": {
                                                            "input": {
                                                                "$ifNull": [
                                                                    "$local.over_capacity_principals",
                                                                    [],
                                                                ]
                                                            },
                                                            "as": "principal",
                                                            "in": {
                                                                "k": "$$principal",
                                                                "v": ["in_app", "push"],
                                                            },
                                                        }
                                                    }
                                                },
                                                "local.has_over_capacity_riders": {
                                                    "$gt": [
                                                        {
                                                            "$size": {
                                                                "$ifNull": [
                                                                    "$local.over_capacity_principals",
                                                                    [],
                                                                ]
                                                            }
                                                        },
                                                        0,
                                                    ]
                                                },
                                            }
                                        },
                                    },
                                    {
                                        "title": "Apply Capacity Pruning",
                                        "description": "Rejects and notifies riders that cannot fit the remaining trip capacity.",
                                        "type": "if.else",
                                        "condition": {
                                            "$ctx": "doc.local.has_over_capacity_riders"
                                        },
                                        "then_effects": [
                                            {
                                                "title": "Collect Pruned Route Ids",
                                                "description": "Collects route ids for riders removed due to capacity pruning.",
                                                "type": "update.contract",
                                                "update": {
                                                    "$set": {
                                                        "local.over_capacity_route_ids": {
                                                            "$setUnion": [
                                                                {
                                                                    "$map": {
                                                                        "input": {
                                                                            "$filter": {
                                                                                "input": {
                                                                                    "$objectToArray": {
                                                                                        "$ifNull": [
                                                                                            "$context.riders",
                                                                                            {},
                                                                                        ]
                                                                                    }
                                                                                },
                                                                                "as": "rv",
                                                                                "cond": {
                                                                                    "$in": [
                                                                                        "$$rv.k",
                                                                                        {
                                                                                            "$ifNull": [
                                                                                                "$local.over_capacity_principals",
                                                                                                [],
                                                                                            ]
                                                                                        },
                                                                                    ]
                                                                                },
                                                                            }
                                                                        },
                                                                        "as": "rv",
                                                                        "in": "$$rv.v.id",
                                                                    }
                                                                },
                                                                [],
                                                            ]
                                                        },
                                                        "local.over_capacity_route_unlink_updates": {
                                                            "$arrayToObject": {
                                                                "$map": {
                                                                    "input": {
                                                                        "$ifNull": [
                                                                            "$local.over_capacity_route_ids",
                                                                            [],
                                                                        ]
                                                                    },
                                                                    "as": "rid",
                                                                    "in": {
                                                                        "k": "$$rid",
                                                                        "v": {
                                                                            "$literal": {
                                                                                "$set": {
                                                                                    "data.contract_ids": {
                                                                                        "$setDifference": [
                                                                                            {
                                                                                                "$ifNull": [
                                                                                                    "$data.contract_ids",
                                                                                                    [],
                                                                                                ]
                                                                                            },
                                                                                            [
                                                                                                {
                                                                                                    "$ctx": "doc._id"
                                                                                                }
                                                                                            ],
                                                                                        ]
                                                                                    }
                                                                                }
                                                                            }
                                                                        },
                                                                    },
                                                                }
                                                            }
                                                        },
                                                    }
                                                },
                                            },
                                            {
                                                "title": "Unlink Contract From Pruned Routes",
                                                "description": "Removes this contract from route linkage lists for pruned riders.",
                                                "type": "update.item",
                                                "updates": {
                                                    "$ctx": "local.over_capacity_route_unlink_updates"
                                                },
                                            },
                                            {
                                                "title": "Load Pruned Routes",
                                                "description": "Loads pruned route documents after unlink to compute refund eligibility.",
                                                "type": "get.item",
                                                "item_id": {
                                                    "$ctx": "local.over_capacity_route_ids"
                                                },
                                                "key": "over_capacity_routes_after_unlink",
                                            },
                                            {
                                                "title": "Compute Pruning Refunds",
                                                "description": "Computes rider refunds and route resets when pruned routes have no linked contracts.",
                                                "type": "update.contract",
                                                "update": {
                                                    "$set": {
                                                        "local.over_capacity_refunds": {
                                                            "$arrayToObject": {
                                                                "$map": {
                                                                    "input": {
                                                                        "$filter": {
                                                                            "input": {
                                                                                "$ifNull": [
                                                                                    "$local.over_capacity_routes_after_unlink",
                                                                                    [],
                                                                                ]
                                                                            },
                                                                            "as": "rt",
                                                                            "cond": {
                                                                                "$eq": [
                                                                                    {
                                                                                        "$size": {
                                                                                            "$ifNull": [
                                                                                                "$$rt.data.contract_ids",
                                                                                                [],
                                                                                            ]
                                                                                        }
                                                                                    },
                                                                                    0,
                                                                                ]
                                                                            },
                                                                        }
                                                                    },
                                                                    "as": "rt",
                                                                    "in": {
                                                                        "k": {
                                                                            "$arrayElemAt": [
                                                                                {
                                                                                    "$map": {
                                                                                        "input": {
                                                                                            "$filter": {
                                                                                                "input": {
                                                                                                    "$objectToArray": {
                                                                                                        "$ifNull": [
                                                                                                            "$context.riders",
                                                                                                            {},
                                                                                                        ]
                                                                                                    }
                                                                                                },
                                                                                                "as": "rv",
                                                                                                "cond": {
                                                                                                    "$and": [
                                                                                                        {
                                                                                                            "$in": [
                                                                                                                "$$rv.k",
                                                                                                                {
                                                                                                                    "$ifNull": [
                                                                                                                        "$local.over_capacity_principals",
                                                                                                                        [],
                                                                                                                    ]
                                                                                                                },
                                                                                                            ]
                                                                                                        },
                                                                                                        {
                                                                                                            "$eq": [
                                                                                                                "$$rv.v.id",
                                                                                                                "$$rt._id",
                                                                                                            ]
                                                                                                        },
                                                                                                    ]
                                                                                                },
                                                                                            }
                                                                                        },
                                                                                        "as": "rv",
                                                                                        "in": "$$rv.k",
                                                                                    }
                                                                                },
                                                                                0,
                                                                            ]
                                                                        },
                                                                        "v": {
                                                                            "product": "coin",
                                                                            "user_id": {
                                                                                "$arrayElemAt": [
                                                                                    {
                                                                                        "$map": {
                                                                                            "input": {
                                                                                                "$filter": {
                                                                                                    "input": {
                                                                                                        "$objectToArray": {
                                                                                                            "$ifNull": [
                                                                                                                "$context.riders",
                                                                                                                {},
                                                                                                            ]
                                                                                                        }
                                                                                                    },
                                                                                                    "as": "rv",
                                                                                                    "cond": {
                                                                                                        "$and": [
                                                                                                            {
                                                                                                                "$in": [
                                                                                                                    "$$rv.k",
                                                                                                                    {
                                                                                                                        "$ifNull": [
                                                                                                                            "$local.over_capacity_principals",
                                                                                                                            [],
                                                                                                                        ]
                                                                                                                    },
                                                                                                                ]
                                                                                                            },
                                                                                                            {
                                                                                                                "$eq": [
                                                                                                                    "$$rv.v.id",
                                                                                                                    "$$rt._id",
                                                                                                                ]
                                                                                                            },
                                                                                                        ]
                                                                                                    },
                                                                                                }
                                                                                            },
                                                                                            "as": "rv",
                                                                                            "in": "$$rv.k",
                                                                                        }
                                                                                    },
                                                                                    0,
                                                                                ]
                                                                            },
                                                                            "amount": {
                                                                                "$ifNull": [
                                                                                    "$$rt.data.reserved_credits",
                                                                                    0,
                                                                                ]
                                                                            },
                                                                        },
                                                                    },
                                                                }
                                                            }
                                                        },
                                                        "local.over_capacity_reset_route_updates": {
                                                            "$arrayToObject": {
                                                                "$map": {
                                                                    "input": {
                                                                        "$filter": {
                                                                            "input": {
                                                                                "$ifNull": [
                                                                                    "$local.over_capacity_routes_after_unlink",
                                                                                    [],
                                                                                ]
                                                                            },
                                                                            "as": "rt",
                                                                            "cond": {
                                                                                "$eq": [
                                                                                    {
                                                                                        "$size": {
                                                                                            "$ifNull": [
                                                                                                "$$rt.data.contract_ids",
                                                                                                [],
                                                                                            ]
                                                                                        }
                                                                                    },
                                                                                    0,
                                                                                ]
                                                                            },
                                                                        }
                                                                    },
                                                                    "as": "rt",
                                                                    "in": {
                                                                        "k": "$$rt._id",
                                                                        "v": {
                                                                            "$literal": {
                                                                                "$set": {
                                                                                    "data.reserved_credits": 0
                                                                                }
                                                                            }
                                                                        },
                                                                    },
                                                                }
                                                            }
                                                        },
                                                        "local.has_over_capacity_refunds": {
                                                            "$gt": [
                                                                {
                                                                    "$size": {
                                                                        "$objectToArray": {
                                                                            "$ifNull": [
                                                                                "$local.over_capacity_refunds",
                                                                                {},
                                                                            ]
                                                                        }
                                                                    }
                                                                },
                                                                0,
                                                            ]
                                                        },
                                                    }
                                                },
                                            },
                                            {
                                                "title": "Mark Pruning Refund Requirement",
                                                "description": "Flags whether any pruned riders now qualify for refund after route unlink.",
                                                "type": "update.contract",
                                                "update": {
                                                    "$set": {
                                                        "local.over_capacity_refund_required": {
                                                            "$ctx": "local.has_over_capacity_refunds"
                                                        }
                                                    }
                                                },
                                            },
                                            {
                                                "title": "Apply Rejections",
                                                "description": "Marks over-capacity riders as rejected and removes them from rider context.",
                                                "type": "update.contract",
                                                "update": [
                                                    {
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
                                                                                        "$in": [
                                                                                            "$$kv.k",
                                                                                            {
                                                                                                "$ifNull": [
                                                                                                    "$local.over_capacity_principals",
                                                                                                    [],
                                                                                                ]
                                                                                            },
                                                                                        ]
                                                                                    },
                                                                                    "REJECTED",
                                                                                    "$$kv.v",
                                                                                ]
                                                                            },
                                                                        },
                                                                    }
                                                                }
                                                            }
                                                        }
                                                    },
                                                    {
                                                        "$set": {
                                                            "context.riders": {
                                                                "$arrayToObject": {
                                                                    "$filter": {
                                                                        "input": {
                                                                            "$objectToArray": {
                                                                                "$ifNull": [
                                                                                    "$context.riders",
                                                                                    {},
                                                                                ]
                                                                            }
                                                                        },
                                                                        "as": "rv",
                                                                        "cond": {
                                                                            "$not": [
                                                                                {
                                                                                    "$in": [
                                                                                        "$$rv.k",
                                                                                        {
                                                                                            "$ifNull": [
                                                                                                "$local.over_capacity_principals",
                                                                                                [],
                                                                                            ]
                                                                                        },
                                                                                    ]
                                                                                }
                                                                            ]
                                                                        },
                                                                    }
                                                                }
                                                            }
                                                        }
                                                    },
                                                ],
                                            },
                                            {
                                                "title": "Notify Pruned Riders",
                                                "description": "Notifies removed riders that they can no longer be admitted due to capacity.",
                                                "type": "notify",
                                                "notify": {
                                                    "event": "contracts.rider_rejected_capacity",
                                                    "targets": {
                                                        "$ctx": "local.over_capacity_targets"
                                                    },
                                                    "payload": {
                                                        "contract_id": {
                                                            "$ctx": "doc._id"
                                                        }
                                                    },
                                                },
                                            },
                                        ],
                                    },
                                ],
                            },
                        ],
                    },
                    "DriverRejectJoinRequest": {
                        "trigger": [
                            {
                                "type": "api",
                                "path": "driver-reject-start",
                                "method": "POST",
                                "payload_schema": {
                                    "type": "object",
                                    "required": ["rider"],
                                    "properties": {
                                        "rider": {
                                            "type": "string",
                                            "pattern": "^u:.+$",
                                        }
                                    },
                                    "additionalProperties": False,
                                },
                                "allow_principals": ["$$ctx.doc.context.driver"],
                                "response": {
                                    "ok": {"$ctx": "doc.local.can_reject_join"},
                                    "event": "driver_reject_start",
                                },
                            }
                        ],
                        "effects": [
                            {
                                "title": "Validate Driver Rejection",
                                "description": "Validates that the selected rider is currently REQUESTING before rejection.",
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "local.can_reject_join": {
                                            "$eq": [
                                                {
                                                    "$ctx": "doc.states.$$ctx.payload.rider"
                                                },
                                                "REQUESTING",
                                            ]
                                        },
                                        "local.reject_route_id": {
                                            "$ctx": "doc.context.riders.$$ctx.payload.rider.id"
                                        },
                                    }
                                },
                            },
                            {
                                "title": "Apply Driver Rejection",
                                "description": "Rejects the selected rider, releases route hold when eligible, and notifies the rider.",
                                "type": "if.else",
                                "condition": {"$ctx": "doc.local.can_reject_join"},
                                "then_effects": [
                                    {
                                        "title": "Unlink Contract From Rider Route",
                                        "description": "Removes this contract id from the rejected rider route item.",
                                        "type": "update.item",
                                        "item_id": {"$ctx": "local.reject_route_id"},
                                        "update": {
                                            "$set": {
                                                "data.contract_ids": {
                                                    "$setDifference": [
                                                        {
                                                            "$ifNull": [
                                                                "$data.contract_ids",
                                                                [],
                                                            ]
                                                        },
                                                        [{"$ctx": "doc._id"}],
                                                    ]
                                                }
                                            }
                                        },
                                    },
                                    {
                                        "title": "Reload Rider Route",
                                        "description": "Reloads route item to compute refund eligibility after unlinking.",
                                        "type": "get.item",
                                        "item_id": {"$ctx": "local.reject_route_id"},
                                        "key": "reject_route_after",
                                    },
                                    {
                                        "title": "Compute Rejection Refund",
                                        "description": "Refunds reserved credits only when no contract remains linked to the route.",
                                        "type": "update.contract",
                                        "update": [
                                            {
                                                "$set": {
                                                    "local.reject_refund": {
                                                        "$cond": [
                                                            {
                                                                "$eq": [
                                                                    {
                                                                        "$size": {
                                                                            "$ifNull": [
                                                                                "$local.reject_route_after.data.contract_ids",
                                                                                [],
                                                                            ]
                                                                        }
                                                                    },
                                                                    0,
                                                                ]
                                                            },
                                                            {
                                                                "$ifNull": [
                                                                    "$local.reject_route_after.data.reserved_credits",
                                                                    0,
                                                                ]
                                                            },
                                                            0,
                                                        ]
                                                    },
                                                }
                                            },
                                            {
                                                "$set": {
                                                    "local.has_reject_refund": {
                                                        "$gt": [
                                                            {
                                                                "$ifNull": [
                                                                    "$local.reject_refund",
                                                                    0,
                                                                ]
                                                            },
                                                            0,
                                                        ]
                                                    },
                                                }
                                            },
                                        ],
                                    },
                                    {
                                        "title": "Clear Route Reserved Credits",
                                        "description": "Clears retained route credits when refund is applied.",
                                        "type": "if.else",
                                        "condition": {
                                            "$ctx": "doc.local.has_reject_refund"
                                        },
                                        "then_effects": [
                                            {
                                                "title": "Refund Rejected Rider",
                                                "description": "Refunds rider credits associated with the rejected request.",
                                                "type": "charge.credits",
                                                "credit": {
                                                    "product": "coin",
                                                    "user_id": "$$ctx.payload.rider",
                                                    "amount": {
                                                        "$ctx": "local.reject_refund"
                                                    },
                                                },
                                            },
                                            {
                                                "title": "Reset Route Hold",
                                                "description": "Resets route reserved credits after rider refund.",
                                                "type": "update.item",
                                                "item_id": {
                                                    "$ctx": "local.reject_route_id"
                                                },
                                                "update": {
                                                    "$set": {"data.reserved_credits": 0}
                                                },
                                            },
                                        ],
                                    },
                                    {
                                        "title": "Set Rider Rejected",
                                        "description": "Sets rider to REJECTED and removes rider route snapshot from context.",
                                        "type": "update.contract",
                                        "update": [
                                            {
                                                "$set": {
                                                    "states.$$ctx.payload.rider": "REJECTED"
                                                }
                                            },
                                        ],
                                    },
                                    {
                                        "title": "Notify Rejected Rider",
                                        "description": "Notifies the rider that the driver rejected the join request.",
                                        "type": "notify",
                                        "notify": {
                                            "event": "contracts.driver_rejected_start",
                                            "targets": {
                                                "$$ctx.payload.rider": [
                                                    "in_app",
                                                    "push",
                                                ]
                                            },
                                            "payload": {
                                                "contract_id": {"$ctx": "doc._id"}
                                            },
                                        },
                                    },
                                ],
                            },
                        ],
                    },
                    "DriverInviteUser": {
                        "trigger": [
                            {
                                "type": "api",
                                "path": "invite-user",
                                "method": "POST",
                                "allow_principals": ["$$ctx.doc.context.driver"],
                                "payload_schema": {
                                    "type": "object",
                                    "required": ["route_id"],
                                    "properties": {
                                        "route_id": {"type": "string", "minLength": 1}
                                    },
                                    "additionalProperties": False,
                                },
                                "response": {
                                    "ok": {"$ctx": "doc.local.can_invite_user"},
                                    "event": "invite_user",
                                },
                            }
                        ],
                        "effects": [
                            {
                                "title": "Load Invite Route",
                                "description": "Loads route data used to evaluate driver invitation feasibility.",
                                "type": "get.item",
                                "item_id": "$$ctx.payload.route_id",
                                "key": "invite_route_item",
                            },
                            {
                                "title": "Derive Invite Inputs",
                                "description": "Derives invite principal, seats, trip, and reserved credits from route data.",
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "local.invite_route": {
                                            "id": "$$ctx.payload.route_id",
                                            "principal": "$local.invite_route_item.data.user_id",
                                            "cost": {
                                                "$ifNull": [
                                                    "$local.invite_route_item.data.cost",
                                                    0,
                                                ]
                                            },
                                            "seats": {
                                                "$ifNull": [
                                                    "$local.invite_route_item.data.seats",
                                                    1,
                                                ]
                                            },
                                            "trip": {
                                                "origin": "$local.invite_route_item.data.origin",
                                                "destination": "$local.invite_route_item.data.destination",
                                            },
                                            "reserved_credits": {
                                                "$ifNull": [
                                                    "$local.invite_route_item.data.reserved_credits",
                                                    0,
                                                ]
                                            },
                                        }
                                    }
                                },
                            },
                            {
                                "title": "Read Invitee Credits",
                                "description": "Reads invitee credits to validate additional reservation requirements.",
                                "type": "balance.credits",
                                "key": "invite_balance_credits",
                                "credit": {
                                    "product": "coin",
                                    "user_id": {"$ctx": "local.invite_route.principal"},
                                },
                            },
                            {
                                "title": "Compute Invite Eligibility",
                                "description": "Validates capacity, credit coverage, and rider state before invitation.",
                                "type": "update.contract",
                                "update": [
                                    {
                                        "$set": {
                                            "local.invite_missing_credits": {
                                                "$max": [
                                                    {
                                                        "$subtract": [
                                                            {
                                                                "$ifNull": [
                                                                    "$local.invite_route.cost",
                                                                    0,
                                                                ]
                                                            },
                                                            {
                                                                "$ifNull": [
                                                                    "$local.invite_route.reserved_credits",
                                                                    0,
                                                                ]
                                                            },
                                                        ]
                                                    },
                                                    0,
                                                ]
                                            },
                                        }
                                    },
                                    {
                                        "$set": {
                                            "local.invite_has_balance": {
                                                "$gte": [
                                                    {
                                                        "$ifNull": [
                                                            "$local.invite_balance_credits",
                                                            0,
                                                        ]
                                                    },
                                                    "$local.invite_missing_credits",
                                                ]
                                            },
                                            "local.invite_has_capacity": {
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
                                                                    "$local.invite_route.seats",
                                                                    1,
                                                                ]
                                                            },
                                                        ]
                                                    },
                                                    {
                                                        "$ifNull": [
                                                            "$context.driver_route.capacity",
                                                            0,
                                                        ]
                                                    },
                                                ]
                                            },
                                            "local.invite_current_state": {
                                                "$ifNull": [
                                                    {
                                                        "$getField": {
                                                            "field": "$$ctx.local.invite_route.principal",
                                                            "input": "$states",
                                                        }
                                                    },
                                                    "",
                                                ]
                                            },
                                        }
                                    },
                                    {
                                        "$set": {
                                            "local.can_invite_user": {
                                                "$and": [
                                                    {
                                                        "$ne": [
                                                            "$local.invite_route.principal",
                                                            "$context.driver",
                                                        ]
                                                    },
                                                    {
                                                        "$in": [
                                                            "$local.invite_current_state",
                                                            [""],
                                                        ]
                                                    },
                                                    "$local.invite_has_capacity",
                                                    "$local.invite_has_balance",
                                                ]
                                            },
                                        }
                                    },
                                ],
                            },
                            {
                                "title": "Apply Driver Invite",
                                "description": "Applies invitation side effects only when eligibility checks pass.",
                                "type": "if.else",
                                "condition": {"$ctx": "doc.local.can_invite_user"},
                                "then_effects": [
                                    {
                                        "title": "Reserve Invite Credits",
                                        "description": "Reserves only missing credits needed by the invite route.",
                                        "type": "use.credits",
                                        "credit": {
                                            "product": "coin",
                                            "user_id": {
                                                "$ctx": "local.invite_route.principal"
                                            },
                                            "amount": {
                                                "$ctx": "local.invite_missing_credits"
                                            },
                                        },
                                    },
                                    {
                                        "title": "Persist Invite Route Hold",
                                        "description": "Persists reserved credits and contract linkage on invite route item.",
                                        "type": "update.item",
                                        "item_id": "$$ctx.payload.route_id",
                                        "update": {
                                            "$set": {
                                                "data.reserved_credits": {
                                                    "$add": [
                                                        {
                                                            "$ifNull": [
                                                                "$data.reserved_credits",
                                                                0,
                                                            ]
                                                        },
                                                        {
                                                            "$ifNull": [
                                                                {
                                                                    "$ctx": "local.invite_missing_credits"
                                                                },
                                                                0,
                                                            ]
                                                        },
                                                    ]
                                                },
                                                "data.contract_ids": {
                                                    "$setUnion": [
                                                        {
                                                            "$ifNull": [
                                                                "$data.contract_ids",
                                                                [],
                                                            ]
                                                        },
                                                        [{"$ctx": "doc._id"}],
                                                    ]
                                                },
                                            }
                                        },
                                    },
                                    {
                                        "title": "Set Pending Invite State",
                                        "description": "Marks invitee as pending and stores route snapshot for follow-up events.",
                                        "type": "update.contract",
                                        "update": {
                                            "$set": {
                                                "states.$$ctx.local.invite_route.principal": "PENDING",
                                                "context.riders.$$ctx.local.invite_route.principal.id": {
                                                    "$ctx": "local.invite_route.id"
                                                },
                                                "context.riders.$$ctx.local.invite_route.principal.cost": {
                                                    "$ctx": "local.invite_route.cost"
                                                },
                                                "context.riders.$$ctx.local.invite_route.principal.seats": {
                                                    "$ctx": "local.invite_route.seats"
                                                },
                                                "context.riders.$$ctx.local.invite_route.principal.trip": {
                                                    "$ctx": "local.invite_route.trip"
                                                },
                                                "local.is_driver_pending": {
                                                    "$eq": [
                                                        {
                                                            "$ctx": "doc.states.$$ctx.doc.context.driver"
                                                        },
                                                        "PENDING_DRIVER",
                                                    ]
                                                },
                                            }
                                        },
                                    },
                                    {
                                        "title": "Notify Stakeholders",
                                        "description": "Sends contracts.user_invited to the invited rider.",
                                        "type": "notify",
                                        "notify": {
                                            "event": "contracts.user_invited",
                                            "targets": {
                                                "$$ctx.local.invite_route.principal": [
                                                    "in_app",
                                                    "push",
                                                ]
                                            },
                                            "payload": {
                                                "contract_id": {"$ctx": "doc._id"}
                                            },
                                        },
                                    },
                                    {
                                        "title": "Confirm Driver If Pending",
                                        "description": "Confirms driver when invitation is the first onboarding action.",
                                        "type": "if.else",
                                        "condition": {
                                            "$ctx": "doc.local.is_driver_pending"
                                        },
                                        "then_effects": [
                                            {
                                                "title": "Set Driver Confirmed",
                                                "description": "Marks driver as DRIVER.",
                                                "type": "update.contract",
                                                "update": {
                                                    "$set": {
                                                        "states.$$ctx.doc.context.driver": "DRIVER",
                                                        "context.accepted_seats_total": {
                                                            "$ifNull": [
                                                                "$context.accepted_seats_total",
                                                                0,
                                                            ]
                                                        },
                                                    }
                                                },
                                            }
                                        ],
                                    },
                                ],
                            },
                        ],
                    },
                    "DriverCancelInviteUser": {
                        "trigger": [
                            {
                                "type": "api",
                                "path": "driver-cancel-invite-user",
                                "method": "POST",
                                "payload_schema": {
                                    "type": "object",
                                    "required": ["route_id"],
                                    "properties": {
                                        "route_id": {"type": "string", "minLength": 1}
                                    },
                                    "additionalProperties": False,
                                },
                                "allow_principals": ["$$ctx.doc.context.driver"],
                                "response": {
                                    "ok": {"$ctx": "doc.local.can_cancel_invite_user"},
                                    "event": "driver_cancel_invite_user",
                                },
                            }
                        ],
                        "effects": [
                            {
                                "title": "Load Invite Route",
                                "description": "Loads invite route to resolve principal and route hold for cancellation.",
                                "type": "get.item",
                                "item_id": "$$ctx.payload.route_id",
                                "key": "cancel_invite_route_item",
                            },
                            {
                                "title": "Compute Cancel Invite Eligibility",
                                "description": "Allows cancellation only when the target rider is currently pending.",
                                "type": "update.contract",
                                "update": [
                                    {
                                        "$set": {
                                            "local.cancel_invite_principal": {
                                                "$ifNull": [
                                                    "$local.cancel_invite_route_item.data.user_id",
                                                    "",
                                                ]
                                            }
                                        }
                                    },
                                    {
                                        "$set": {
                                            "local.can_cancel_invite_user": {
                                                "$gt": [
                                                    {
                                                        "$size": {
                                                            "$filter": {
                                                                "input": {
                                                                    "$objectToArray": "$states"
                                                                },
                                                                "as": "kv",
                                                                "cond": {
                                                                    "$and": [
                                                                        {
                                                                            "$eq": [
                                                                                "$$kv.k",
                                                                                "$local.cancel_invite_principal",
                                                                            ]
                                                                        },
                                                                        {
                                                                            "$eq": [
                                                                                "$$kv.v",
                                                                                "PENDING",
                                                                            ]
                                                                        },
                                                                    ]
                                                                },
                                                            }
                                                        }
                                                    },
                                                    0,
                                                ]
                                            }
                                        }
                                    },
                                ],
                            },
                            {
                                "title": "Cancel Pending Invite",
                                "description": "Cancels pending invite, releases route hold, and refunds rider when eligible.",
                                "type": "if.else",
                                "condition": {
                                    "$ctx": "doc.local.can_cancel_invite_user"
                                },
                                "then_effects": [
                                    {
                                        "title": "Unlink Contract From Invite Route",
                                        "description": "Removes this contract id from the invite route linkage list.",
                                        "type": "update.item",
                                        "item_id": "$$ctx.payload.route_id",
                                        "update": {
                                            "$set": {
                                                "data.contract_ids": {
                                                    "$setDifference": [
                                                        {
                                                            "$ifNull": [
                                                                "$data.contract_ids",
                                                                [],
                                                            ]
                                                        },
                                                        [{"$ctx": "doc._id"}],
                                                    ]
                                                }
                                            }
                                        },
                                    },
                                    {
                                        "title": "Reload Invite Route",
                                        "description": "Reloads route item after unlink to compute refund eligibility.",
                                        "type": "get.item",
                                        "item_id": "$$ctx.payload.route_id",
                                        "key": "cancel_invite_route_after",
                                    },
                                    {
                                        "title": "Compute Invite Refund",
                                        "description": "Refunds reserved credits only when route has no remaining contract links.",
                                        "type": "update.contract",
                                        "update": [
                                            {
                                                "$set": {
                                                    "local.cancel_invite_refund": {
                                                        "$cond": [
                                                            {
                                                                "$eq": [
                                                                    {
                                                                        "$size": {
                                                                            "$ifNull": [
                                                                                "$local.cancel_invite_route_after.data.contract_ids",
                                                                                [],
                                                                            ]
                                                                        }
                                                                    },
                                                                    0,
                                                                ]
                                                            },
                                                            {
                                                                "$ifNull": [
                                                                    "$local.cancel_invite_route_after.data.reserved_credits",
                                                                    0,
                                                                ]
                                                            },
                                                            0,
                                                        ]
                                                    },
                                                }
                                            },
                                            {
                                                "$set": {
                                                    "local.has_cancel_invite_refund": {
                                                        "$gt": [
                                                            {
                                                                "$ifNull": [
                                                                    "$local.cancel_invite_refund",
                                                                    0,
                                                                ]
                                                            },
                                                            0,
                                                        ]
                                                    },
                                                }
                                            },
                                        ],
                                    },
                                    {
                                        "title": "Reset Route Hold",
                                        "description": "Clears route retained credits when invite refund is applied.",
                                        "type": "if.else",
                                        "condition": {
                                            "$ctx": "doc.local.has_cancel_invite_refund"
                                        },
                                        "then_effects": [
                                            {
                                                "title": "Refund Invitee",
                                                "description": "Refunds rider credits associated with the cancelled pending invite.",
                                                "type": "charge.credits",
                                                "credit": {
                                                    "product": "coin",
                                                    "user_id": {
                                                        "$ctx": "local.cancel_invite_principal"
                                                    },
                                                    "amount": {
                                                        "$ctx": "local.cancel_invite_refund"
                                                    },
                                                },
                                            },
                                            {
                                                "title": "Clear Route Reserved Credits",
                                                "description": "Clears retained credits on route item after invite cancellation refund.",
                                                "type": "update.item",
                                                "item_id": "$$ctx.payload.route_id",
                                                "update": {
                                                    "$set": {"data.reserved_credits": 0}
                                                },
                                            },
                                        ],
                                    },
                                    {
                                        "title": "Clear Rider State",
                                        "description": "Resets pending rider state and removes rider context snapshot.",
                                        "type": "update.contract",
                                        "update": [
                                            {
                                                "$unset": [
                                                    "states.$$ctx.doc.local.cancel_invite_principal",
                                                    "context.riders.$$ctx.doc.local.cancel_invite_principal",
                                                ]
                                            },
                                        ],
                                    },
                                    {
                                        "title": "Notify Invitee",
                                        "description": "Notifies rider that the pending invite was cancelled by the driver.",
                                        "type": "notify",
                                        "notify": {
                                            "event": "contracts.driver_cancelled_invite",
                                            "targets": {
                                                "$$ctx.doc.local.cancel_invite_principal": [
                                                    "in_app",
                                                    "push",
                                                ]
                                            },
                                            "payload": {
                                                "contract_id": {"$ctx": "doc._id"}
                                            },
                                        },
                                    },
                                ],
                            },
                        ],
                    },
                    "UserAcceptInvite": {
                        "trigger": [
                            {
                                "type": "api",
                                "path": "accept-user",
                                "method": "POST",
                                "allow_user_states": ["PENDING"],
                                "response": {
                                    "ok": {"$ctx": "doc.local.can_accept_invite"},
                                    "event": "accept_user",
                                },
                            }
                        ],
                        "effects": [
                            {
                                "title": "Validate Invite Acceptance",
                                "description": "Validates pending state and remaining capacity before accepting invite.",
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "local.can_accept_invite": {
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
                                                                "$context.riders.$$ctx.user.seats",
                                                                1,
                                                            ]
                                                        },
                                                    ]
                                                },
                                                {
                                                    "$ifNull": [
                                                        "$context.driver_route.capacity",
                                                        0,
                                                    ]
                                                },
                                            ]
                                        },
                                    }
                                },
                            },
                            {
                                "title": "Apply Invite Acceptance",
                                "description": "Applies acceptance side effects only when invite acceptance is still feasible.",
                                "type": "if.else",
                                "condition": {"$ctx": "doc.local.can_accept_invite"},
                                "then_effects": [
                                    {
                                        "title": "Set Rider Accepted",
                                        "description": "Marks rider as accepted and increments occupied seats.",
                                        "type": "update.contract",
                                        "update": {
                                            "$set": {
                                                "states.$$ctx.user": "ACCEPTED",
                                                "context.accepted_seats_total": {
                                                    "$add": [
                                                        {
                                                            "$ifNull": [
                                                                "$context.accepted_seats_total",
                                                                0,
                                                            ]
                                                        },
                                                        {
                                                            "$ifNull": [
                                                                "$context.riders.$$ctx.user.seats",
                                                                1,
                                                            ]
                                                        },
                                                    ]
                                                },
                                            }
                                        },
                                    },
                                    {
                                        "title": "Load Accepted Rider Route",
                                        "description": "Loads accepted rider route to remove rider from competing contracts.",
                                        "type": "get.item",
                                        "item_id": {
                                            "$ctx": "doc.context.riders.$$ctx.user.id"
                                        },
                                        "key": "accepted_invite_route",
                                    },
                                    {
                                        "title": "Confirm Winning Contract Link",
                                        "description": "Keeps only current contract linked on the accepted rider route item.",
                                        "type": "update.item",
                                        "item_id": {
                                            "$ctx": "doc.context.riders.$$ctx.user.id"
                                        },
                                        "update": {
                                            "$set": {
                                                "data.contract_ids": [
                                                    {"$ctx": "doc._id"}
                                                ]
                                            }
                                        },
                                    },
                                    {
                                        "title": "Compute Over-Capacity Riders",
                                        "description": "Finds pending or requesting riders that no longer fit remaining capacity after invite acceptance.",
                                        "type": "update.contract",
                                        "update": {
                                            "$set": {
                                                "local.over_capacity_principals": {
                                                    "$map": {
                                                        "input": {
                                                            "$filter": {
                                                                "input": {
                                                                    "$objectToArray": "$states"
                                                                },
                                                                "as": "kv",
                                                                "cond": {
                                                                    "$and": [
                                                                        {
                                                                            "$ne": [
                                                                                "$$kv.k",
                                                                                "$$ctx.user",
                                                                            ]
                                                                        },
                                                                        {
                                                                            "$in": [
                                                                                "$$kv.v",
                                                                                [
                                                                                    "REQUESTING",
                                                                                    "PENDING",
                                                                                ],
                                                                            ]
                                                                        },
                                                                        {
                                                                            "$gt": [
                                                                                {
                                                                                    "$ifNull": [
                                                                                        {
                                                                                            "$arrayElemAt": [
                                                                                                {
                                                                                                    "$map": {
                                                                                                        "input": {
                                                                                                            "$filter": {
                                                                                                                "input": {
                                                                                                                    "$objectToArray": {
                                                                                                                        "$ifNull": [
                                                                                                                            "$context.riders",
                                                                                                                            {},
                                                                                                                        ]
                                                                                                                    }
                                                                                                                },
                                                                                                                "as": "rv",
                                                                                                                "cond": {
                                                                                                                    "$eq": [
                                                                                                                        "$$rv.k",
                                                                                                                        "$$kv.k",
                                                                                                                    ]
                                                                                                                },
                                                                                                            }
                                                                                                        },
                                                                                                        "as": "rv",
                                                                                                        "in": "$$rv.v.seats",
                                                                                                    }
                                                                                                },
                                                                                                0,
                                                                                            ]
                                                                                        },
                                                                                        1,
                                                                                    ]
                                                                                },
                                                                                {
                                                                                    "$max": [
                                                                                        {
                                                                                            "$subtract": [
                                                                                                {
                                                                                                    "$ifNull": [
                                                                                                        "$context.driver_route.capacity",
                                                                                                        0,
                                                                                                    ]
                                                                                                },
                                                                                                {
                                                                                                    "$ifNull": [
                                                                                                        "$context.accepted_seats_total",
                                                                                                        0,
                                                                                                    ]
                                                                                                },
                                                                                            ]
                                                                                        },
                                                                                        0,
                                                                                    ]
                                                                                },
                                                                            ]
                                                                        },
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
                                        "title": "Prepare Over-Capacity Targets",
                                        "description": "Builds notification targets for riders removed by capacity constraints.",
                                        "type": "update.contract",
                                        "update": {
                                            "$set": {
                                                "local.over_capacity_targets": {
                                                    "$arrayToObject": {
                                                        "$map": {
                                                            "input": {
                                                                "$ifNull": [
                                                                    "$local.over_capacity_principals",
                                                                    [],
                                                                ]
                                                            },
                                                            "as": "principal",
                                                            "in": {
                                                                "k": "$$principal",
                                                                "v": ["in_app", "push"],
                                                            },
                                                        }
                                                    }
                                                },
                                                "local.has_over_capacity_riders": {
                                                    "$gt": [
                                                        {
                                                            "$size": {
                                                                "$ifNull": [
                                                                    "$local.over_capacity_principals",
                                                                    [],
                                                                ]
                                                            }
                                                        },
                                                        0,
                                                    ]
                                                },
                                            }
                                        },
                                    },
                                    {
                                        "title": "Apply Capacity Pruning",
                                        "description": "Rejects and notifies riders that cannot fit remaining seats after acceptance.",
                                        "type": "if.else",
                                        "condition": {
                                            "$ctx": "doc.local.has_over_capacity_riders"
                                        },
                                        "then_effects": [
                                            {
                                                "title": "Collect Pruned Route Ids",
                                                "description": "Collects route ids for riders removed due to capacity pruning.",
                                                "type": "update.contract",
                                                "update": {
                                                    "$set": {
                                                        "local.over_capacity_route_ids": {
                                                            "$setUnion": [
                                                                {
                                                                    "$map": {
                                                                        "input": {
                                                                            "$filter": {
                                                                                "input": {
                                                                                    "$objectToArray": {
                                                                                        "$ifNull": [
                                                                                            "$context.riders",
                                                                                            {},
                                                                                        ]
                                                                                    }
                                                                                },
                                                                                "as": "rv",
                                                                                "cond": {
                                                                                    "$in": [
                                                                                        "$$rv.k",
                                                                                        {
                                                                                            "$ifNull": [
                                                                                                "$local.over_capacity_principals",
                                                                                                [],
                                                                                            ]
                                                                                        },
                                                                                    ]
                                                                                },
                                                                            }
                                                                        },
                                                                        "as": "rv",
                                                                        "in": "$$rv.v.id",
                                                                    }
                                                                },
                                                                [],
                                                            ]
                                                        },
                                                        "local.over_capacity_route_unlink_updates": {
                                                            "$arrayToObject": {
                                                                "$map": {
                                                                    "input": {
                                                                        "$ifNull": [
                                                                            "$local.over_capacity_route_ids",
                                                                            [],
                                                                        ]
                                                                    },
                                                                    "as": "rid",
                                                                    "in": {
                                                                        "k": "$$rid",
                                                                        "v": {
                                                                            "$literal": {
                                                                                "$set": {
                                                                                    "data.contract_ids": {
                                                                                        "$setDifference": [
                                                                                            {
                                                                                                "$ifNull": [
                                                                                                    "$data.contract_ids",
                                                                                                    [],
                                                                                                ]
                                                                                            },
                                                                                            [
                                                                                                {
                                                                                                    "$ctx": "doc._id"
                                                                                                }
                                                                                            ],
                                                                                        ]
                                                                                    }
                                                                                }
                                                                            }
                                                                        },
                                                                    },
                                                                }
                                                            }
                                                        },
                                                    }
                                                },
                                            },
                                            {
                                                "title": "Unlink Contract From Pruned Routes",
                                                "description": "Removes this contract from route linkage lists for pruned riders.",
                                                "type": "update.item",
                                                "updates": {
                                                    "$ctx": "local.over_capacity_route_unlink_updates"
                                                },
                                            },
                                            {
                                                "title": "Load Pruned Routes",
                                                "description": "Loads pruned route documents after unlink to compute refund eligibility.",
                                                "type": "get.item",
                                                "item_id": {
                                                    "$ctx": "local.over_capacity_route_ids"
                                                },
                                                "key": "over_capacity_routes_after_unlink",
                                            },
                                            {
                                                "title": "Compute Pruning Refunds",
                                                "description": "Computes rider refunds and route resets when pruned routes have no linked contracts.",
                                                "type": "update.contract",
                                                "update": {
                                                    "$set": {
                                                        "local.over_capacity_refunds": {
                                                            "$arrayToObject": {
                                                                "$map": {
                                                                    "input": {
                                                                        "$filter": {
                                                                            "input": {
                                                                                "$ifNull": [
                                                                                    "$local.over_capacity_routes_after_unlink",
                                                                                    [],
                                                                                ]
                                                                            },
                                                                            "as": "rt",
                                                                            "cond": {
                                                                                "$eq": [
                                                                                    {
                                                                                        "$size": {
                                                                                            "$ifNull": [
                                                                                                "$$rt.data.contract_ids",
                                                                                                [],
                                                                                            ]
                                                                                        }
                                                                                    },
                                                                                    0,
                                                                                ]
                                                                            },
                                                                        }
                                                                    },
                                                                    "as": "rt",
                                                                    "in": {
                                                                        "k": {
                                                                            "$arrayElemAt": [
                                                                                {
                                                                                    "$map": {
                                                                                        "input": {
                                                                                            "$filter": {
                                                                                                "input": {
                                                                                                    "$objectToArray": {
                                                                                                        "$ifNull": [
                                                                                                            "$context.riders",
                                                                                                            {},
                                                                                                        ]
                                                                                                    }
                                                                                                },
                                                                                                "as": "rv",
                                                                                                "cond": {
                                                                                                    "$and": [
                                                                                                        {
                                                                                                            "$in": [
                                                                                                                "$$rv.k",
                                                                                                                {
                                                                                                                    "$ifNull": [
                                                                                                                        "$local.over_capacity_principals",
                                                                                                                        [],
                                                                                                                    ]
                                                                                                                },
                                                                                                            ]
                                                                                                        },
                                                                                                        {
                                                                                                            "$eq": [
                                                                                                                "$$rv.v.id",
                                                                                                                "$$rt._id",
                                                                                                            ]
                                                                                                        },
                                                                                                    ]
                                                                                                },
                                                                                            }
                                                                                        },
                                                                                        "as": "rv",
                                                                                        "in": "$$rv.k",
                                                                                    }
                                                                                },
                                                                                0,
                                                                            ]
                                                                        },
                                                                        "v": {
                                                                            "product": "coin",
                                                                            "user_id": {
                                                                                "$arrayElemAt": [
                                                                                    {
                                                                                        "$map": {
                                                                                            "input": {
                                                                                                "$filter": {
                                                                                                    "input": {
                                                                                                        "$objectToArray": {
                                                                                                            "$ifNull": [
                                                                                                                "$context.riders",
                                                                                                                {},
                                                                                                            ]
                                                                                                        }
                                                                                                    },
                                                                                                    "as": "rv",
                                                                                                    "cond": {
                                                                                                        "$and": [
                                                                                                            {
                                                                                                                "$in": [
                                                                                                                    "$$rv.k",
                                                                                                                    {
                                                                                                                        "$ifNull": [
                                                                                                                            "$local.over_capacity_principals",
                                                                                                                            [],
                                                                                                                        ]
                                                                                                                    },
                                                                                                                ]
                                                                                                            },
                                                                                                            {
                                                                                                                "$eq": [
                                                                                                                    "$$rv.v.id",
                                                                                                                    "$$rt._id",
                                                                                                                ]
                                                                                                            },
                                                                                                        ]
                                                                                                    },
                                                                                                }
                                                                                            },
                                                                                            "as": "rv",
                                                                                            "in": "$$rv.k",
                                                                                        }
                                                                                    },
                                                                                    0,
                                                                                ]
                                                                            },
                                                                            "amount": {
                                                                                "$ifNull": [
                                                                                    "$$rt.data.reserved_credits",
                                                                                    0,
                                                                                ]
                                                                            },
                                                                        },
                                                                    },
                                                                }
                                                            }
                                                        },
                                                        "local.over_capacity_reset_route_updates": {
                                                            "$arrayToObject": {
                                                                "$map": {
                                                                    "input": {
                                                                        "$filter": {
                                                                            "input": {
                                                                                "$ifNull": [
                                                                                    "$local.over_capacity_routes_after_unlink",
                                                                                    [],
                                                                                ]
                                                                            },
                                                                            "as": "rt",
                                                                            "cond": {
                                                                                "$eq": [
                                                                                    {
                                                                                        "$size": {
                                                                                            "$ifNull": [
                                                                                                "$$rt.data.contract_ids",
                                                                                                [],
                                                                                            ]
                                                                                        }
                                                                                    },
                                                                                    0,
                                                                                ]
                                                                            },
                                                                        }
                                                                    },
                                                                    "as": "rt",
                                                                    "in": {
                                                                        "k": "$$rt._id",
                                                                        "v": {
                                                                            "$literal": {
                                                                                "$set": {
                                                                                    "data.reserved_credits": 0
                                                                                }
                                                                            }
                                                                        },
                                                                    },
                                                                }
                                                            }
                                                        },
                                                        "local.has_over_capacity_refunds": {
                                                            "$gt": [
                                                                {
                                                                    "$size": {
                                                                        "$objectToArray": {
                                                                            "$ifNull": [
                                                                                "$local.over_capacity_refunds",
                                                                                {},
                                                                            ]
                                                                        }
                                                                    }
                                                                },
                                                                0,
                                                            ]
                                                        },
                                                    }
                                                },
                                            },
                                            {
                                                "title": "Mark Pruning Refund Requirement",
                                                "description": "Flags whether any pruned riders now qualify for refund after route unlink.",
                                                "type": "update.contract",
                                                "update": {
                                                    "$set": {
                                                        "local.over_capacity_refund_required": {
                                                            "$ctx": "local.has_over_capacity_refunds"
                                                        }
                                                    }
                                                },
                                            },
                                            {
                                                "title": "Reject Over-Capacity Riders",
                                                "description": "Marks over-capacity riders as rejected and removes them from rider context.",
                                                "type": "update.contract",
                                                "update": [
                                                    {
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
                                                                                        "$in": [
                                                                                            "$$kv.k",
                                                                                            {
                                                                                                "$ifNull": [
                                                                                                    "$local.over_capacity_principals",
                                                                                                    [],
                                                                                                ]
                                                                                            },
                                                                                        ]
                                                                                    },
                                                                                    "REJECTED",
                                                                                    "$$kv.v",
                                                                                ]
                                                                            },
                                                                        },
                                                                    }
                                                                }
                                                            }
                                                        }
                                                    },
                                                    {
                                                        "$set": {
                                                            "context.riders": {
                                                                "$arrayToObject": {
                                                                    "$filter": {
                                                                        "input": {
                                                                            "$objectToArray": {
                                                                                "$ifNull": [
                                                                                    "$context.riders",
                                                                                    {},
                                                                                ]
                                                                            }
                                                                        },
                                                                        "as": "rv",
                                                                        "cond": {
                                                                            "$not": [
                                                                                {
                                                                                    "$in": [
                                                                                        "$$rv.k",
                                                                                        {
                                                                                            "$ifNull": [
                                                                                                "$local.over_capacity_principals",
                                                                                                [],
                                                                                            ]
                                                                                        },
                                                                                    ]
                                                                                }
                                                                            ]
                                                                        },
                                                                    }
                                                                }
                                                            }
                                                        }
                                                    },
                                                ],
                                            },
                                            {
                                                "title": "Notify Pruned Riders",
                                                "description": "Notifies removed riders that they are no longer admissible due to capacity.",
                                                "type": "notify",
                                                "notify": {
                                                    "event": "contracts.rider_rejected_capacity",
                                                    "targets": {
                                                        "$ctx": "local.over_capacity_targets"
                                                    },
                                                    "payload": {
                                                        "contract_id": {
                                                            "$ctx": "doc._id"
                                                        }
                                                    },
                                                },
                                            },
                                        ],
                                    },
                                ],
                            },
                        ],
                    },
                    "UserRejectInvite": {
                        "trigger": [
                            {
                                "type": "api",
                                "path": "reject-user",
                                "method": "POST",
                                "allow_user_states": ["PENDING"],
                                "response": {
                                    "ok": True,
                                    "event": "reject_user",
                                },
                            }
                        ],
                        "effects": [
                            {
                                "title": "Capture Reject Invite Route",
                                "description": "Captures rider route id used for invite hold cleanup and refund checks.",
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "local.reject_invite_route_id": {
                                            "$ctx": "doc.context.riders.$$ctx.user.id"
                                        }
                                    }
                                },
                            },
                            {
                                "title": "Unlink Contract From Invite Route",
                                "description": "Removes this contract from route link list before refund calculation.",
                                "type": "update.item",
                                "item_id": {"$ctx": "local.reject_invite_route_id"},
                                "update": {
                                    "$set": {
                                        "data.contract_ids": {
                                            "$setDifference": [
                                                {"$ifNull": ["$data.contract_ids", []]},
                                                [{"$ctx": "doc._id"}],
                                            ]
                                        }
                                    }
                                },
                            },
                            {
                                "title": "Reload Invite Route",
                                "description": "Reloads route data to compute rejection refund eligibility.",
                                "type": "get.item",
                                "item_id": {"$ctx": "local.reject_invite_route_id"},
                                "key": "reject_invite_route_after",
                            },
                            {
                                "title": "Compute Reject Invite Refund",
                                "description": "Refunds reserved credits only when route has no remaining contract links.",
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "local.reject_invite_refund": {
                                            "$cond": [
                                                {
                                                    "$eq": [
                                                        {
                                                            "$size": {
                                                                "$ifNull": [
                                                                    "$local.reject_invite_route_after.data.contract_ids",
                                                                    [],
                                                                ]
                                                            }
                                                        },
                                                        0,
                                                    ]
                                                },
                                                {
                                                    "$ifNull": [
                                                        "$local.reject_invite_route_after.data.reserved_credits",
                                                        0,
                                                    ]
                                                },
                                                0,
                                            ]
                                        },
                                        "local.has_reject_invite_refund": {
                                            "$gt": [
                                                {
                                                    "$ifNull": [
                                                        "$local.reject_invite_refund",
                                                        0,
                                                    ]
                                                },
                                                0,
                                            ]
                                        },
                                    }
                                },
                            },
                            {
                                "title": "Refund Rejecting Rider",
                                "description": "Refunds rider credits reserved for the rejected invite.",
                                "type": "charge.credits",
                                "credit": {
                                    "product": "coin",
                                    "amount": {"$ctx": "local.reject_invite_refund"},
                                },
                            },
                            {
                                "title": "Reset Route Hold",
                                "description": "Clears retained route credits when invite rejection refund is applied.",
                                "type": "if.else",
                                "condition": {
                                    "$ctx": "doc.local.has_reject_invite_refund"
                                },
                                "then_effects": [
                                    {
                                        "title": "Clear Route Reserved Credits",
                                        "description": "Resets route reserved credits after invite rejection refund.",
                                        "type": "update.item",
                                        "item_id": {
                                            "$ctx": "local.reject_invite_route_id"
                                        },
                                        "update": {
                                            "$set": {"data.reserved_credits": 0}
                                        },
                                    }
                                ],
                            },
                            {
                                "title": "Clear Rider Invite State",
                                "description": "Removes rider pending state and route snapshot after invite rejection.",
                                "type": "update.contract",
                                "update": {
                                    "$unset": [
                                        "states.$$ctx.user",
                                        "context.riders.$$ctx.user",
                                    ]
                                },
                            },
                            {
                                "title": "Notify Driver",
                                "description": "Notifies driver when invited rider rejects during onboarding.",
                                "type": "notify",
                                "notify": {
                                    "event": "contracts.user_rejected",
                                    "targets": {
                                        "$$ctx.doc.context.driver": ["in_app", "push"]
                                    },
                                    "payload": {"contract_id": {"$ctx": "doc._id"}},
                                },
                            },
                        ],
                    },
                    "DriverRemoveUser": {
                        "trigger": [
                            {
                                "type": "api",
                                "path": "driver-reject-user",
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
                                    "ok": {"$ctx": "doc.local.can_driver_reject_user"},
                                    "event": "driver_reject_user",
                                },
                            }
                        ],
                        "effects": [
                            {
                                "title": "Compute Reject Eligibility",
                                "description": "Allows driver rejection only for active recruiting user states.",
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "local.target_state": {
                                            "$ifNull": [
                                                {
                                                    "$ctx": "doc.states.$$ctx.payload.principal"
                                                },
                                                "",
                                            ]
                                        },
                                        "local.can_driver_reject_user": {
                                            "$in": [
                                                {
                                                    "$ifNull": [
                                                        {
                                                            "$ctx": "doc.states.$$ctx.payload.principal"
                                                        },
                                                        "",
                                                    ]
                                                },
                                                ["REQUESTING", "PENDING", "ACCEPTED"],
                                            ]
                                        },
                                        "local.is_target_accepted": {
                                            "$eq": ["$local.target_state", "ACCEPTED"]
                                        },
                                        "local.target_route_id": {
                                            "$ctx": "doc.context.riders.$$ctx.payload.principal.id"
                                        },
                                        "local.target_principal": "$$ctx.payload.principal",
                                    }
                                },
                            },
                            {
                                "title": "Apply Driver Rejection",
                                "description": "Marks target as rejected and updates occupancy when needed.",
                                "type": "if.else",
                                "condition": {
                                    "$ctx": "doc.local.can_driver_reject_user"
                                },
                                "then_effects": [
                                    {
                                        "title": "Adjust Accepted Seats",
                                        "description": "Subtracts seats only when an accepted user is rejected.",
                                        "type": "if.else",
                                        "condition": {
                                            "$ctx": "doc.local.is_target_accepted"
                                        },
                                        "then_effects": [
                                            {
                                                "title": "Decrement Occupancy",
                                                "description": "Recalculates accepted seats total after driver rejection.",
                                                "type": "update.contract",
                                                "update": {
                                                    "$set": {
                                                        "context.accepted_seats_total": {
                                                            "$max": [
                                                                {
                                                                    "$subtract": [
                                                                        {
                                                                            "$ifNull": [
                                                                                "$context.accepted_seats_total",
                                                                                0,
                                                                            ]
                                                                        },
                                                                        {
                                                                            "$ifNull": [
                                                                                {
                                                                                    "$ctx": "doc.context.riders.$$ctx.payload.principal.seats"
                                                                                },
                                                                                1,
                                                                            ]
                                                                        },
                                                                    ]
                                                                },
                                                                0,
                                                            ]
                                                        }
                                                    }
                                                },
                                            }
                                        ],
                                    },
                                    {
                                        "title": "Set Rejected User",
                                        "description": "Sets user state to rejected and clears rider context.",
                                        "type": "update.contract",
                                        "update": {
                                            "$set": {
                                                "states.$$ctx.payload.principal": "REJECTED"
                                            }
                                        },
                                    },
                                    {
                                        "title": "Unlink Contract From Rider Route",
                                        "description": "Removes this contract from the rejected rider route linkage list.",
                                        "type": "update.item",
                                        "item_id": {"$ctx": "local.target_route_id"},
                                        "update": {
                                            "$set": {
                                                "data.contract_ids": {
                                                    "$setDifference": [
                                                        {
                                                            "$ifNull": [
                                                                "$data.contract_ids",
                                                                [],
                                                            ]
                                                        },
                                                        [{"$ctx": "doc._id"}],
                                                    ]
                                                }
                                            }
                                        },
                                    },
                                    {
                                        "title": "Reload Target Route",
                                        "description": "Reloads rider route after unlink to evaluate refund eligibility.",
                                        "type": "get.item",
                                        "item_id": {"$ctx": "local.target_route_id"},
                                        "key": "driver_reject_route_after",
                                    },
                                    {
                                        "title": "Compute Driver Reject Refund",
                                        "description": "Refunds held credits only when rider route has no remaining links.",
                                        "type": "update.contract",
                                        "update": {
                                            "$set": {
                                                "local.driver_reject_refund": {
                                                    "$cond": [
                                                        {
                                                            "$eq": [
                                                                {
                                                                    "$size": {
                                                                        "$ifNull": [
                                                                            "$local.driver_reject_route_after.data.contract_ids",
                                                                            [],
                                                                        ]
                                                                    }
                                                                },
                                                                0,
                                                            ]
                                                        },
                                                        {
                                                            "$ifNull": [
                                                                "$local.driver_reject_route_after.data.reserved_credits",
                                                                0,
                                                            ]
                                                        },
                                                        0,
                                                    ]
                                                },
                                                "local.has_driver_reject_refund": {
                                                    "$gt": [
                                                        {
                                                            "$ifNull": [
                                                                "$local.driver_reject_refund",
                                                                0,
                                                            ]
                                                        },
                                                        0,
                                                    ]
                                                },
                                            }
                                        },
                                    },
                                    {
                                        "title": "Apply Driver Reject Refund",
                                        "description": "Refunds rider and resets retained credits when rejection unlinks final route.",
                                        "type": "if.else",
                                        "condition": {
                                            "$ctx": "doc.local.has_driver_reject_refund"
                                        },
                                        "then_effects": [
                                            {
                                                "title": "Refund Rider",
                                                "description": "Returns credits retained for the rejected rider.",
                                                "type": "charge.credits",
                                                "credit": {
                                                    "product": "coin",
                                                    "user_id": {
                                                        "$ctx": "local.target_principal"
                                                    },
                                                    "amount": {
                                                        "$ctx": "local.driver_reject_refund"
                                                    },
                                                },
                                            },
                                            {
                                                "title": "Clear Route Reserved Credits",
                                                "description": "Clears retained credits on rider route after driver rejection refund.",
                                                "type": "update.item",
                                                "item_id": {
                                                    "$ctx": "local.target_route_id"
                                                },
                                                "update": {
                                                    "$set": {"data.reserved_credits": 0}
                                                },
                                            },
                                        ],
                                    },
                                    {
                                        "title": "Clear Rider Context",
                                        "description": "Removes rider context snapshot after driver rejection.",
                                        "type": "update.contract",
                                        "update": {
                                            "$unset": [
                                                "context.riders.$$ctx.payload.principal"
                                            ]
                                        },
                                    },
                                    {
                                        "title": "Notify Rejected User",
                                        "description": "Notifies user that the driver rejected their ride participation.",
                                        "type": "notify",
                                        "notify": {
                                            "event": "contracts.user_rejected_by_driver",
                                            "targets": {
                                                "$$ctx.payload.principal": [
                                                    "in_app",
                                                    "push",
                                                ]
                                            },
                                            "payload": {
                                                "contract_id": {"$ctx": "doc._id"}
                                            },
                                        },
                                    },
                                ],
                            },
                        ],
                    },
                    "UserCancelRide": {
                        "trigger": [
                            {
                                "type": "api",
                                "path": "cancel-user",
                                "method": "POST",
                                "allow_user_states": [
                                    "REQUESTING",
                                    "PENDING",
                                    "ACCEPTED",
                                ],
                                "response": {
                                    "ok": True,
                                    "event": "cancel_user",
                                },
                            }
                        ],
                        "effects": [
                            {
                                "title": "Capture Cancel Inputs",
                                "description": "Captures current user state, route id and seats for recruiting cancellation.",
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "local.cancel_route_id": {
                                            "$ctx": "doc.context.riders.$$ctx.user.id"
                                        },
                                        "local.cancel_user_seats": {
                                            "$ifNull": [
                                                {
                                                    "$ctx": "doc.context.riders.$$ctx.user.seats"
                                                },
                                                1,
                                            ]
                                        },
                                        "local.is_target_accepted": {
                                            "$eq": [
                                                {"$ctx": "doc.states.$$ctx.user"},
                                                "ACCEPTED",
                                            ]
                                        },
                                    }
                                },
                            },
                            {
                                "title": "Adjust Occupancy If Accepted",
                                "description": "Subtracts seats when an accepted rider cancels during recruiting.",
                                "type": "if.else",
                                "condition": {"$ctx": "doc.local.is_target_accepted"},
                                "then_effects": [
                                    {
                                        "title": "Decrement Accepted Seats",
                                        "description": "Updates accepted seats after accepted rider cancellation.",
                                        "type": "update.contract",
                                        "update": {
                                            "$set": {
                                                "context.accepted_seats_total": {
                                                    "$max": [
                                                        {
                                                            "$subtract": [
                                                                {
                                                                    "$ifNull": [
                                                                        "$context.accepted_seats_total",
                                                                        0,
                                                                    ]
                                                                },
                                                                "$local.cancel_user_seats",
                                                            ]
                                                        },
                                                        0,
                                                    ]
                                                }
                                            }
                                        },
                                    }
                                ],
                            },
                            {
                                "title": "Unlink Contract From Route",
                                "description": "Removes this contract id from rider route hold tracking.",
                                "type": "update.item",
                                "item_id": {"$ctx": "local.cancel_route_id"},
                                "update": {
                                    "$set": {
                                        "data.contract_ids": {
                                            "$setDifference": [
                                                {"$ifNull": ["$data.contract_ids", []]},
                                                [{"$ctx": "doc._id"}],
                                            ]
                                        }
                                    }
                                },
                            },
                            {
                                "title": "Reload Cancel Route",
                                "description": "Reloads rider route after unlink to determine if hold refund is needed.",
                                "type": "get.item",
                                "item_id": {"$ctx": "local.cancel_route_id"},
                                "key": "cancel_route_after",
                            },
                            {
                                "title": "Compute Cancel Refund",
                                "description": "Refunds held rider credits only when route has no remaining linked contracts.",
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "local.cancel_refund": {
                                            "$cond": [
                                                {
                                                    "$eq": [
                                                        {
                                                            "$size": {
                                                                "$ifNull": [
                                                                    "$local.cancel_route_after.data.contract_ids",
                                                                    [],
                                                                ]
                                                            }
                                                        },
                                                        0,
                                                    ]
                                                },
                                                {
                                                    "$ifNull": [
                                                        "$local.cancel_route_after.data.reserved_credits",
                                                        0,
                                                    ]
                                                },
                                                0,
                                            ]
                                        },
                                        "local.has_cancel_refund": {
                                            "$gt": [
                                                {
                                                    "$ifNull": [
                                                        "$local.cancel_refund",
                                                        0,
                                                    ]
                                                },
                                                0,
                                            ]
                                        },
                                    }
                                },
                            },
                            {
                                "title": "Apply Cancel Refund",
                                "description": "Refunds rider and clears route retained credits when cancellation unlinks final contract.",
                                "type": "if.else",
                                "condition": {"$ctx": "doc.local.has_cancel_refund"},
                                "then_effects": [
                                    {
                                        "title": "Refund Cancelling Rider",
                                        "description": "Returns retained credits to rider after cancellation.",
                                        "type": "charge.credits",
                                        "credit": {
                                            "product": "coin",
                                            "amount": {"$ctx": "local.cancel_refund"},
                                        },
                                    },
                                    {
                                        "title": "Clear Cancel Route Reserved Credits",
                                        "description": "Clears retained credits on route after cancel refund.",
                                        "type": "update.item",
                                        "item_id": {"$ctx": "local.cancel_route_id"},
                                        "update": {
                                            "$set": {"data.reserved_credits": 0}
                                        },
                                    },
                                ],
                            },
                            {
                                "title": "Mark User Cancelled",
                                "description": "Marks user as cancelled and removes rider context from recruiting roster.",
                                "type": "update.contract",
                                "update": [
                                    {"$set": {"states.$$ctx.user": "CANCELLED"}},
                                    {"$unset": ["context.riders.$$ctx.user"]},
                                ],
                            },
                            {
                                "title": "Notify Driver",
                                "description": "Notifies driver when user cancels ride during recruiting.",
                                "type": "notify",
                                "notify": {
                                    "event": "contracts.user_cancelled",
                                    "targets": {
                                        "$$ctx.doc.context.driver": ["in_app", "push"]
                                    },
                                    "payload": {
                                        "contract_id": {"$ctx": "doc._id"},
                                        "principal": "$$ctx.user",
                                    },
                                },
                            },
                        ],
                    },
                    "DriverCancelTrip": {
                        "trigger": [
                            {
                                "type": "api",
                                "path": "driver-reject-trip",
                                "method": "POST",
                                "allow_principals": ["$$ctx.doc.context.driver"],
                                "response": {
                                    "ok": True,
                                    "event": "driver_reject_trip",
                                },
                            }
                        ],
                        "effects": [
                            {
                                "title": "Collect Active Riders",
                                "description": "Collects active rider principals and route ids for trip cancellation pruning.",
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "local.trip_cancel_riders": {
                                            "$map": {
                                                "input": {
                                                    "$objectToArray": {
                                                        "$ifNull": [
                                                            "$context.riders",
                                                            {},
                                                        ]
                                                    }
                                                },
                                                "as": "rv",
                                                "in": {
                                                    "principal": "$$rv.k",
                                                    "route_id": "$$rv.v.id",
                                                },
                                            }
                                        }
                                    }
                                },
                            },
                            {
                                "title": "Build Trip Cancel Route Unlinks",
                                "description": "Builds route update map to unlink this contract from every active rider route.",
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "local.trip_cancel_route_updates": {
                                            "$arrayToObject": {
                                                "$map": {
                                                    "input": {
                                                        "$ifNull": [
                                                            "$local.trip_cancel_riders",
                                                            [],
                                                        ]
                                                    },
                                                    "as": "r",
                                                    "in": {
                                                        "k": "$$r.route_id",
                                                        "v": {
                                                            "$literal": {
                                                                "$set": {
                                                                    "data.contract_ids": {
                                                                        "$setDifference": [
                                                                            {
                                                                                "$ifNull": [
                                                                                    "$data.contract_ids",
                                                                                    [],
                                                                                ]
                                                                            },
                                                                            [
                                                                                {
                                                                                    "$ctx": "doc._id"
                                                                                }
                                                                            ],
                                                                        ]
                                                                    }
                                                                }
                                                            }
                                                        },
                                                    },
                                                }
                                            }
                                        },
                                        "local.trip_cancel_route_ids": {
                                            "$setUnion": [
                                                {
                                                    "$map": {
                                                        "input": {
                                                            "$ifNull": [
                                                                "$local.trip_cancel_riders",
                                                                [],
                                                            ]
                                                        },
                                                        "as": "r",
                                                        "in": "$$r.route_id",
                                                    }
                                                },
                                                [],
                                            ]
                                        },
                                    }
                                },
                            },
                            {
                                "title": "Unlink Trip Routes",
                                "description": "Removes this contract id from all active rider routes.",
                                "type": "update.item",
                                "updates": {"$ctx": "local.trip_cancel_route_updates"},
                            },
                            {
                                "title": "Reload Trip Routes",
                                "description": "Loads rider routes after unlink to compute cancellation refunds.",
                                "type": "get.item",
                                "item_id": {"$ctx": "local.trip_cancel_route_ids"},
                                "key": "trip_cancel_routes_after",
                            },
                            {
                                "title": "Compute Trip Cancel Refunds",
                                "description": "Builds reset maps for routes with no remaining contract links.",
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "local.trip_cancel_reset_route_updates": {
                                            "$arrayToObject": {
                                                "$map": {
                                                    "input": {
                                                        "$filter": {
                                                            "input": {
                                                                "$ifNull": [
                                                                    "$local.trip_cancel_routes_after",
                                                                    [],
                                                                ]
                                                            },
                                                            "as": "rt",
                                                            "cond": {
                                                                "$eq": [
                                                                    {
                                                                        "$size": {
                                                                            "$ifNull": [
                                                                                "$$rt.data.contract_ids",
                                                                                [],
                                                                            ]
                                                                        }
                                                                    },
                                                                    0,
                                                                ]
                                                            },
                                                        }
                                                    },
                                                    "as": "rt",
                                                    "in": {
                                                        "k": "$$rt._id",
                                                        "v": {
                                                            "$literal": {
                                                                "$set": {
                                                                    "data.reserved_credits": 0
                                                                }
                                                            }
                                                        },
                                                    },
                                                }
                                            }
                                        },
                                        "local.trip_cancel_targets": {
                                            "$arrayToObject": {
                                                "$map": {
                                                    "input": {
                                                        "$ifNull": [
                                                            "$local.trip_cancel_riders",
                                                            [],
                                                        ]
                                                    },
                                                    "as": "r",
                                                    "in": {
                                                        "k": "$$r.principal",
                                                        "v": ["in_app", "push"],
                                                    },
                                                }
                                            }
                                        },
                                        "local.has_trip_cancel_targets": {
                                            "$gt": [
                                                {
                                                    "$size": {
                                                        "$objectToArray": {
                                                            "$ifNull": [
                                                                "$local.trip_cancel_targets",
                                                                {},
                                                            ]
                                                        }
                                                    }
                                                },
                                                0,
                                            ]
                                        },
                                    }
                                },
                            },
                            {
                                "title": "Clear Trip Route Reserved Credits",
                                "description": "Resets retained route credits for routes left without contract links.",
                                "type": "update.item",
                                "updates": {
                                    "$ctx": "local.trip_cancel_reset_route_updates"
                                },
                            },
                            {
                                "title": "Notify Trip Riders",
                                "description": "Notifies all active riders that the driver cancelled the trip.",
                                "type": "if.else",
                                "condition": {
                                    "$ctx": "doc.local.has_trip_cancel_targets"
                                },
                                "then_effects": [
                                    {
                                        "title": "Dispatch Driver Cancelled Trip",
                                        "description": "Delivers driver cancelled trip notification to all affected riders.",
                                        "type": "notify",
                                        "notify": {
                                            "event": "contracts.driver_cancelled_trip",
                                            "targets": {
                                                "$ctx": "local.trip_cancel_targets"
                                            },
                                            "payload": {
                                                "contract_id": {"$ctx": "doc._id"}
                                            },
                                        },
                                    }
                                ],
                            },
                            {
                                "title": "Close Trip As Rejected",
                                "description": "Closes the trip as rejected by the driver and updates all rider statuses consistently.",
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
                                                                    "$in": [
                                                                        "$$kv.v",
                                                                        [
                                                                            "REQUESTING",
                                                                            "PENDING",
                                                                            "ACCEPTED",
                                                                            "PENDING_DRIVER",
                                                                            "DRIVER",
                                                                        ],
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
            "CONFIRMING": {
                "on_enter": {
                    "effects": [
                        {
                            "title": "Create Group",
                            "description": "Creates the coordination group for active riders.",
                            "type": "create.group",
                            "name": "trip-$$ctx.doc._id",
                            "sub": "$$ctx.doc.context.driver",
                            "key": "group_ref",
                        },
                        {
                            "title": "Link Coordination Group",
                            "description": "Stores group linkage for roster synchronization.",
                            "type": "update.contract",
                            "update": {
                                "$set": {
                                    "context.group_id": {"$ctx": "local.group_ref"}
                                }
                            },
                        },
                        {
                            "title": "Store Context",
                            "description": "Stores lifecycle context needed to collect rider confirmations.",
                            "type": "update.contract",
                            "update": {
                                "$set": {
                                    "local.accepted_riders": {
                                        "$map": {
                                            "input": {
                                                "$filter": {
                                                    "input": {
                                                        "$objectToArray": "$states"
                                                    },
                                                    "as": "kv",
                                                    "cond": {
                                                        "$eq": ["$$kv.v", "ACCEPTED"]
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
                            "title": "Sync Group",
                            "description": "Synchronizes group membership with current trip roster.",
                            "type": "update.group",
                            "group_id": {"$ctx": "doc.context.group_id"},
                            "edit_members": {
                                "add_members": "$$ctx.local.accepted_riders"
                            },
                        },
                        {
                            "title": "Move State",
                            "description": "Moves the contract state to support collect rider confirmations.",
                            "type": "update.contract",
                            "update": {"$set": {"state": "ONBOARDING"}},
                        },
                    ]
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
                                                {
                                                    "$ctx": "doc.context.riders.$$ctx.user.seats"
                                                },
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
                                            "state": "ONBOARDING",
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
                                    "targets": {
                                        "$$ctx.doc.context.driver": ["in_app", "push"]
                                    },
                                    "payload": {
                                        "principal": "$$ctx.user",
                                        "contract_id": {"$ctx": "doc._id"},
                                    },
                                },
                            },
                        ],
                    },
                    "DriverSetOnboarding": {
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
                                "update": {"$set": {"state": "ONBOARDING"}},
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
                                "type": "schedule.event",
                                "key": "riders_pickup_check_id",
                                "event": {
                                    "event_name": "RidersPickupCheckTimed",
                                    "at": {"$ctx": "doc.context.driver_trip.origin.at"},
                                    "actor_id": "system:cron",
                                },
                            },
                            {
                                "title": "Store Context",
                                "description": "Stores lifecycle context needed to start trip execution.",
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
                                "title": "Evaluate Branch",
                                "description": "Selects the branch that matches current trip conditions.",
                                "type": "if.else",
                                "condition": {"$ctx": "local.target_is_accepted"},
                                "then_effects": [
                                    {
                                        "title": "Sync Group",
                                        "description": "Synchronizes group membership with current trip roster.",
                                        "type": "update.group",
                                        "group_id": {"$ctx": "doc.context.group_id"},
                                        "edit_members": {
                                            "remove_members": [
                                                "$$ctx.payload.principal"
                                            ]
                                        },
                                    },
                                    {
                                        "title": "Persist Progress",
                                        "description": "Persists transition data to keep the process deterministic.",
                                        "type": "update.contract",
                                        "update": {
                                            "$set": {
                                                "local.remove_seats": {
                                                    "$ifNull": [
                                                        {
                                                            "$ctx": "doc.context.riders.$$ctx.payload.principal.seats"
                                                        },
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
                                            {
                                                "$unset": "context.riders.$$ctx.payload.principal.seats"
                                            },
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
                                            "payload": {
                                                "contract_id": {"$ctx": "doc._id"}
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
                                "update": {
                                    "$set": {"status": "CANCELED", "state": "CANCELED"}
                                },
                            },
                            {
                                "title": "Notify Stakeholders",
                                "description": "Sends contracts.trip_cancelled_by_driver so stakeholders can act at the right time.",
                                "type": "notify",
                                "notify": {
                                    "event": "contracts.trip_cancelled_by_driver",
                                    "targets": "$$ctx.local.cancel_trip_targets",
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
                                "update": {
                                    "$set": {"context.driver_in_pickup_zone": True}
                                },
                            },
                            {
                                "title": "Cancel Schedule",
                                "description": "Cancels timers that are no longer relevant on this path.",
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
                                "title": "Store Context",
                                "description": "Stores lifecycle context needed to record rider pickup arrival.",
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
                                "title": "Evaluate Branch",
                                "description": "Selects the branch that matches current trip conditions.",
                                "type": "if.else",
                                "condition": {"$ctx": "local.can_pick_user"},
                                "then_effects": [
                                    {
                                        "title": "Persist Progress",
                                        "description": "Persists transition data to keep the process deterministic.",
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
                                            "payload": {
                                                "contract_id": {"$ctx": "doc._id"}
                                            },
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
                                "condition": {"$ctx": "local.all_riders_picked_up"},
                                "then_effects": [
                                    {
                                        "title": "Cancel Schedule",
                                        "description": "Cancels timers that are no longer relevant on this path.",
                                        "type": "unschedule.event",
                                        "event_id": {
                                            "$ctx": "doc.context.riders_pickup_check_id"
                                        },
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
                                                {
                                                    "$ctx": "doc.context.riders.$$ctx.user.seats"
                                                },
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
                                    "targets": {
                                        "$$ctx.doc.context.driver": ["in_app", "push"]
                                    },
                                    "payload": {
                                        "principal": "$$ctx.user",
                                        "contract_id": {"$ctx": "doc._id"},
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
                                "title": "Persist Progress",
                                "description": "Persists transition data to keep the process deterministic.",
                                "type": "update.contract",
                                "update": {
                                    "$set": {
                                        "local.driver_not_in_pickup_zone": {
                                            "$eq": [
                                                {
                                                    "$ifNull": [
                                                        "$context.driver_in_pickup_zone",
                                                        False,
                                                    ]
                                                },
                                                False,
                                            ]
                                        }
                                    }
                                },
                            },
                            {
                                "title": "Evaluate Branch",
                                "description": "Selects the branch that matches current trip conditions.",
                                "type": "if.else",
                                "condition": {
                                    "$ctx": "docl.local.driver_not_in_pickup_zone"
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
                                            "payload": {
                                                "contract_id": {"$ctx": "doc._id"}
                                            },
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                    "RidersPickupCheckTimed": {
                        "trigger": [
                            {"type": "api", "path": "riders-pickup-check-timeout"}
                        ],
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
                                "condition": {"$ctx": "local.has_pending_pickups"},
                                "then_effects": [
                                    {
                                        "title": "Notify Stakeholders",
                                        "description": "Sends contracts.rider_pickup_check so stakeholders can act at the right time.",
                                        "type": "notify",
                                        "notify": {
                                            "event": "contracts.rider_pickup_check",
                                            "targets": "$$ctx.doc.context.pending_pickup_targets",
                                            "payload": {
                                                "contract_id": {"$ctx": "doc._id"}
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
                                "update": {
                                    "$set": {"status": "CANCELED", "state": "CANCELED"}
                                },
                            },
                            {
                                "title": "Notify Stakeholders",
                                "description": "Sends contracts.trip_cancelled_by_driver so stakeholders can act at the right time.",
                                "type": "notify",
                                "notify": {
                                    "event": "contracts.trip_cancelled_by_driver",
                                    "targets": "$$ctx.local.cancel_trip_targets",
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
            CONTRACTS_ENABLED=True,
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

            from schedula.utils.form.server.credits import get_wallet

            self.route_by_principal: Dict[str, str] = {}
            items_coll = self.app.config["MONGO_DB"]["items"]
            for uid in self.user_ids.values():
                principal = f"u:{uid}"
                route_id = str(uuid.uuid4())
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
                        "_id": route_id,
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
                wallet.charge(product="coin", credits=100)

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
            self, template_id: str, context: Dict[str, Any], actor="owner-1", **extra: Any
    ) -> httpx.Response:
        body = {"context": context}
        body.update(extra)
        return self.httpx.post(
            f"/contracts/{template_id}",
            json=body,
            headers=self._headers(actor),
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
            payload = {"rider": f"u:{self.user_ids['p1']}"}
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
            return int(
                coll.count_documents(
                    {"event": event, f"targets.{principal}": {"$exists": True}}
                )
            )

    def _list_notifications(self, actor: str) -> List[Dict[str, Any]]:
        resp = self.httpx.get("/notification", headers=self._headers(actor))
        self.assertEqual(resp.status_code, 200, msg=resp.text)
        data = resp.json() or {}
        return list(data.get("notifications") or [])

    def _count_notification_event_api(self, actor: str, event: str) -> int:
        notes = self._list_notifications(actor)
        return sum(1 for n in notes if n.get("event") == event)

    def _get_route(self, actor: str, route_id: str) -> Dict[str, Any]:
        resp = self.httpx.get(f"/item/route/{route_id}", headers=self._headers(actor))
        self.assertEqual(resp.status_code, 200, msg=resp.text)
        return resp.json() or {}

    def _create_route(self, actor: str, **updates: Any) -> str:
        principal = f"u:{self.user_ids[actor]}"
        data = {
            "cost": 10,
            "capacity": 3,
            "seats": 1,
            "user_id": principal,
            "origin": {"lat": 45.0, "lng": 9.0, "at": "1970-01-01T00:00:00+00:00"},
            "destination": {"lat": 45.1, "lng": 9.1},
        }
        data.update(updates)
        resp = self.httpx.post(
            "/item/route",
            json={"data": data},
            headers=self._headers(actor),
        )
        self.assertEqual(resp.status_code, 201, msg=resp.text)
        body = resp.json() or {}
        return str(body.get("id"))

    def _patch_route_data(
            self, actor: str, route_id: str, **updates: Any
    ) -> Dict[str, Any]:
        current = self._get_route(actor, route_id)
        data = dict(current.get("data") or {})
        data.update(updates)
        resp = self.httpx.patch(
            f"/item/route/{route_id}",
            json={"data": data},
            headers=self._headers(actor),
        )
        self.assertEqual(resp.status_code, 200, msg=resp.text)
        return resp.json() or {}

    def _gherkin_context_for(self, driver: str, riders: List[str]) -> Dict[str, Any]:
        driver_principal = f"u:{self.user_ids[driver]}"
        rider_ids = [f"u:{self.user_ids[r]}" for r in riders]
        rider_route_ids = [
            self.route_by_principal[principal] for principal in rider_ids
        ]
        return {
            "driver_trip_id": self.route_by_principal[driver_principal],
            "riders": rider_route_ids,
        }

    def _gherkin_context(self, initial_state: str = "START") -> Dict[str, Any]:
        driver_uid = self.user_ids["d1"]
        p1_uid = self.user_ids["p1"]
        rider_ids = [f"u:{p1_uid}"]
        driver_principal = f"u:{driver_uid}"
        rider_route_ids = [
            self.route_by_principal[principal] for principal in rider_ids
        ]
        return {
            "driver_trip_id": self.route_by_principal[driver_principal],
            "riders": rider_route_ids,
        }

    def _create_gherkin_contract(self, initial_state: str = "START", actor="p1") -> str:
        definition = _gherkin_definition()
        template_id = self._create_template(
            definition,
            allowed_initial_states=["START"],
        )
        created = self._create_contract(
            template_id,
            self._gherkin_context(initial_state=initial_state),
            initial_state=initial_state,
            actor=actor,
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
        self.assertEqual(c["state"], "ONBOARDING")
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
                payload={
                    "route_id": self.route_by_principal[f"u:{self.user_ids['p2']}"]
                },
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
                payload={
                    "route_id": self.route_by_principal[f"u:{self.user_ids['p3']}"]
                },
            ).status_code,
            200,
        )
        self.assertEqual(
            self._post_event(cid, "accept-user", actor="p3").status_code, 200
        )
        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        self.assertEqual(c["state"], "READY")
        return gid

    def test_start_user_initiated_sets_pending_driver_and_requesting_rider(
            self,
    ) -> None:
        cid = self._create_gherkin_contract(initial_state="START", actor="p1")
        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()

        self.assertEqual(c["state"], "ONBOARDING")
        self.assertEqual(self._user_state(c, self.user_ids["d1"]), "PENDING_DRIVER")
        self.assertEqual(self._user_state(c, self.user_ids["p1"]), "REQUESTING")

    def test_start_driver_accept_start_uses_payload_riders_only(self) -> None:
        cid = self._create_gherkin_contract(initial_state="START", actor="p1")

        self.assertEqual(
            self._post_event(cid, "request-join", actor="p4").status_code, 200
        )

        self.assertEqual(
            self._post_event(
                cid,
                "driver-accept-start",
                actor="d1",
                payload={"rider": f"u:{self.user_ids['p1']}"},
            ).status_code,
            200,
        )

        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        self.assertEqual(c["state"], "ONBOARDING")
        self.assertEqual(self._user_state(c, self.user_ids["d1"]), "DRIVER")
        self.assertEqual(self._user_state(c, self.user_ids["p1"]), "ACCEPTED")
        self.assertEqual(self._user_state(c, self.user_ids["p4"]), "REQUESTING")

    def test_start_driver_accept_start_sets_accepted_seats_total_from_rider(
            self,
    ) -> None:
        p1_principal = f"u:{self.user_ids['p1']}"
        route_id = self.route_by_principal[p1_principal]
        with self.app.app_context():
            self.app.config["MONGO_DB"]["items"].update_one(
                {"_id": route_id}, {"$set": {"data.seats": 2}}
            )

        cid = self._create_gherkin_contract(initial_state="START", actor="p1")
        r = self._post_event(
            cid,
            "driver-accept-start",
            actor="d1",
            payload={"rider": p1_principal},
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json().get("ok"))

        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        self.assertEqual(c["state"], "ONBOARDING")
        self.assertEqual((c.get("context") or {}).get("accepted_seats_total"), 2)

    def test_start_driver_accept_start_returns_ok_false_for_non_requesting_rider(
            self,
    ) -> None:
        cid = self._create_gherkin_contract(initial_state="START", actor="p1")
        p4_principal = f"u:{self.user_ids['p4']}"

        r = self._post_event(
            cid,
            "driver-accept-start",
            actor="d1",
            payload={"rider": p4_principal},
        )
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json().get("ok"))

        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        self.assertEqual(c["state"], "ONBOARDING")
        self.assertEqual(self._user_state(c, self.user_ids["d1"]), "PENDING_DRIVER")
        self.assertEqual(self._user_state(c, self.user_ids["p1"]), "REQUESTING")
        self.assertEqual(self._user_state(c, self.user_ids["p4"]), "")

    def test_start_driver_cancel_invite_user_clears_pending_state(self) -> None:
        cid = self._create_gherkin_contract(initial_state="START", actor="p1")
        p2_principal = f"u:{self.user_ids['p2']}"
        p2_route_id = self.route_by_principal[p2_principal]

        with self.app.app_context():
            self.app.config["MONGO_DB"]["contracts"].update_one(
                {"_id": cid},
                {
                    "$set": {
                        f"states.{p2_principal}": "PENDING",
                        f"context.riders.{p2_principal}": {
                            "id": p2_route_id,
                            "seats": 1,
                            "trip": {},
                        },
                    }
                },
            )

        cancel = self._post_event(
            cid,
            "driver-cancel-invite-user",
            actor="d1",
            payload={"route_id": p2_route_id},
        )
        self.assertEqual(cancel.status_code, 200)
        self.assertTrue(cancel.json().get("ok"))

        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        self.assertEqual(c["state"], "ONBOARDING")
        self.assertEqual(self._user_state(c, self.user_ids["p2"]), "")

    def test_start_user_accept_invite_moves_to_confirming(self) -> None:
        cid = self._create_gherkin_contract(initial_state="START", actor="p1")
        p2_principal = f"u:{self.user_ids['p2']}"
        p2_route_id = self.route_by_principal[p2_principal]

        with self.app.app_context():
            self.app.config["MONGO_DB"]["contracts"].update_one(
                {"_id": cid},
                {
                    "$set": {
                        f"states.{p2_principal}": "PENDING",
                        f"context.riders.{p2_principal}": {
                            "id": p2_route_id,
                            "seats": 2,
                            "trip": {},
                        },
                    }
                },
            )

        accepted = self._post_event(cid, "accept-user", actor="p2")
        self.assertEqual(accepted.status_code, 200)
        self.assertTrue(accepted.json().get("ok"))

        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        self.assertEqual(c["state"], "ONBOARDING")
        self.assertEqual(self._user_state(c, self.user_ids["p2"]), "ACCEPTED")
        self.assertEqual((c.get("context") or {}).get("accepted_seats_total"), 2)

    def test_start_user_reject_invite_clears_pending_rider(self) -> None:
        cid = self._create_gherkin_contract(initial_state="START", actor="p1")
        p2_principal = f"u:{self.user_ids['p2']}"
        p2_route_id = self.route_by_principal[p2_principal]

        with self.app.app_context():
            self.app.config["MONGO_DB"]["contracts"].update_one(
                {"_id": cid},
                {
                    "$set": {
                        f"states.{p2_principal}": "PENDING",
                        f"context.riders.{p2_principal}": {
                            "id": p2_route_id,
                            "seats": 1,
                            "trip": {},
                        },
                    }
                },
            )

        rejected = self._post_event(cid, "reject-user", actor="p2")
        self.assertEqual(rejected.status_code, 200)
        self.assertTrue(rejected.json().get("ok"))

        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        self.assertEqual(c["state"], "ONBOARDING")
        self.assertEqual(self._user_state(c, self.user_ids["p2"]), "")

    def test_recruiting_driver_reject_user_marks_target_rejected(self) -> None:
        cid = self._create_gherkin_contract(initial_state="START", actor="p1")
        p1_principal = f"u:{self.user_ids['p1']}"

        r = self._post_event(
            cid,
            "driver-reject-user",
            actor="d1",
            payload={"principal": p1_principal},
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json().get("ok"))

        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        self.assertEqual(c["state"], "ONBOARDING")
        self.assertEqual(self._user_state(c, self.user_ids["p1"]), "REJECTED")

    def test_recruiting_user_cancel_ride_marks_user_cancelled(self) -> None:
        cid = self._create_gherkin_contract(initial_state="START", actor="p1")

        r = self._post_event(cid, "cancel-user", actor="p1")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json().get("ok"))

        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        self.assertEqual(c["state"], "ONBOARDING")
        self.assertEqual(self._user_state(c, self.user_ids["p1"]), "CANCELLED")

    def test_start_request_join_adds_requesting_user_when_capacity_and_credits_ok(
            self,
    ) -> None:
        driver_principal = f"u:{self.user_ids['d1']}"
        before = self._count_notifications_for(
            driver_principal, "contracts.join_requested"
        )

        cid = self._create_gherkin_contract(initial_state="START")
        r = self._post_event(cid, "request-join", actor="p4")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json().get("ok"))

        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        self.assertEqual(c["state"], "ONBOARDING")
        self.assertEqual(self._user_state(c, self.user_ids["p4"]), "REQUESTING")

        after = self._count_notifications_for(
            driver_principal, "contracts.join_requested"
        )
        self.assertEqual(after, before + 1)

    def test_start_request_join_denies_when_user_has_insufficient_credits(self) -> None:
        cid = self._create_gherkin_contract(initial_state="START")
        p4_principal = f"u:{self.user_ids['p4']}"
        route_id = self.route_by_principal[p4_principal]

        with self.app.app_context():
            self.app.config["MONGO_DB"]["items"].update_one(
                {"_id": route_id}, {"$set": {"data.cost": 1000}}
            )

        r = self._post_event(cid, "request-join", actor="p4")
        self.assertEqual(r.status_code, 200)

        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        self.assertEqual(self._user_state(c, self.user_ids["p4"]), "")

    def test_start_cancel_join_request_last_user_re_notifies_driver(self) -> None:
        driver_principal = f"u:{self.user_ids['d1']}"
        before = self._count_notifications_for(
            driver_principal, "contracts.request_ride"
        )

        cid = self._create_gherkin_contract(initial_state="START", actor="p1")
        after_create = self._count_notifications_for(
            driver_principal, "contracts.request_ride"
        )
        self.assertEqual(after_create, before + 1)

        self.assertEqual(
            self._post_event(cid, "cancel-join-request", actor="p1").status_code, 200
        )

        c = self.httpx.get(f"/contracts/{cid}", headers=self._headers("owner-1")).json()
        self.assertEqual(c["state"], "ONBOARDING")
        self.assertIn((c.get("context") or {}).get("riders_map"), ({}, None))

        after_cancel = self._count_notifications_for(
            driver_principal, "contracts.request_ride"
        )
        self.assertEqual(after_cancel, before + 2)

    def test_onboarding_full_journey_all_apis_with_negatives_and_pruning(self) -> None:
        definition = _gherkin_definition()
        template_id = self._create_template(
            definition,
            allowed_initial_states=["START"],
        )

        p1_principal = f"u:{self.user_ids['p1']}"
        p2_principal = f"u:{self.user_ids['p2']}"
        p4_principal = f"u:{self.user_ids['p4']}"
        p2_route_id = self._create_route("p2", cost=10, seats=1)
        p2_route_low_credit = self._create_route("p2", cost=1000, seats=1)
        p2_route_over_seats = self._create_route("p2", cost=10, seats=9)
        p3_route_id = self._create_route("p3", cost=10, seats=1)
        p4_route_id = self._create_route("p4", cost=10, seats=1)
        p4_route_low_credit = self._create_route("p4", cost=1000, seats=1)
        p4_route_over_seats = self._create_route("p4", cost=10, seats=9)
        d1_route_id = self._create_route("d1")

        created_a = self._create_contract(
            template_id,
            self._gherkin_context_for("d1", ["p1"]),
            initial_state="START",
            actor="p1",
        )
        self.assertEqual(created_a.status_code, 201, msg=created_a.text)
        contract_a = str(created_a.json()["id"])

        contract_a_doc = self.httpx.get(
            f"/contracts/{contract_a}", headers=self._headers("owner-1")
        ).json()
        self.assertEqual(contract_a_doc["state"], "ONBOARDING")
        self.assertEqual(
            self._user_state(contract_a_doc, self.user_ids["d1"]), "PENDING_DRIVER"
        )
        self.assertEqual(
            self._user_state(contract_a_doc, self.user_ids["p1"]), "REQUESTING"
        )

        # Negative: accept-start with non-requesting rider.
        bad_accept = self._post_event(
            contract_a,
            "driver-accept-start",
            actor="d1",
            payload={"rider": p4_principal},
        )
        self.assertEqual(bad_accept.status_code, 200)
        self.assertFalse(bad_accept.json().get("ok"))

        # Negative request-join: driver cannot request join.
        driver_join = self._post_event(
            contract_a,
            "request-join",
            actor="d1",
            payload={"route_id": d1_route_id},
        )
        self.assertEqual(driver_join.status_code, 403)

        # request-join / cancel-join-request exercised on a dedicated contract.
        created_req = self._create_contract(
            template_id,
            self._gherkin_context_for("d1", ["p1"]),
            initial_state="START",
            actor="p1",
        )
        self.assertEqual(created_req.status_code, 201, msg=created_req.text)
        contract_req = str(created_req.json()["id"])

        good_join = self._post_event(
            contract_req,
            "request-join",
            actor="p4",
            payload={"route_id": p4_route_id},
        )
        self.assertEqual(good_join.status_code, 200)
        self.assertTrue(good_join.json().get("ok"))

        join_p3 = self._post_event(contract_req, "request-join", actor="p3")
        self.assertEqual(join_p3.status_code, 200)
        self.assertTrue(join_p3.json().get("ok"))
        cancel_p3 = self._post_event(contract_req, "cancel-join-request", actor="p3")
        self.assertEqual(cancel_p3.status_code, 200)
        self.assertTrue(cancel_p3.json().get("ok"))

        # invite-user negatives.
        bad_invite_self = self._post_event(
            contract_a,
            "invite-user",
            actor="d1",
            payload={"route_id": d1_route_id},
        )
        self.assertEqual(bad_invite_self.status_code, 200)
        self.assertFalse(bad_invite_self.json().get("ok"))

        bad_invite_low_credits = self._post_event(
            contract_a,
            "invite-user",
            actor="d1",
            payload={"route_id": p2_route_low_credit},
        )
        self.assertEqual(bad_invite_low_credits.status_code, 200)
        self.assertFalse(bad_invite_low_credits.json().get("ok"))

        bad_invite_over_seats = self._post_event(
            contract_a,
            "invite-user",
            actor="d1",
            payload={"route_id": p2_route_over_seats},
        )
        self.assertEqual(bad_invite_over_seats.status_code, 200)
        self.assertFalse(bad_invite_over_seats.json().get("ok"))

        # invite-user positives + driver-cancel-invite-user + reject-user.
        invite_p2 = self._post_event(
            contract_a,
            "invite-user",
            actor="d1",
            payload={"route_id": p2_route_id},
        )
        self.assertEqual(invite_p2.status_code, 200)
        self.assertTrue(invite_p2.json().get("ok"))

        invite_p3 = self._post_event(
            contract_a,
            "invite-user",
            actor="d1",
            payload={"route_id": p3_route_id},
        )
        self.assertEqual(invite_p3.status_code, 200)
        self.assertTrue(invite_p3.json().get("ok"))

        cancel_invite_p3 = self._post_event(
            contract_a,
            "driver-cancel-invite-user",
            actor="d1",
            payload={"route_id": p3_route_id},
        )
        self.assertEqual(cancel_invite_p3.status_code, 200)
        self.assertTrue(cancel_invite_p3.json().get("ok"))

        invite_p3_again = self._post_event(
            contract_a,
            "invite-user",
            actor="d1",
            payload={"route_id": p3_route_id},
        )
        self.assertEqual(invite_p3_again.status_code, 200)
        self.assertTrue(invite_p3_again.json().get("ok"))
        reject_invite_p3 = self._post_event(contract_a, "reject-user", actor="p3")
        self.assertEqual(reject_invite_p3.status_code, 200)
        self.assertTrue(reject_invite_p3.json().get("ok"))

        # Competitor contract used to verify pruning after user accept on contract A.
        created_c = self._create_contract(
            template_id,
            self._gherkin_context_for("p3", ["p2"]),
            initial_state="START",
            actor="p2",
        )
        self.assertEqual(created_c.status_code, 201, msg=created_c.text)
        contract_c = str(created_c.json()["id"])

        before_rider_unavailable_c = self._count_notifications_for(
            f"u:{self.user_ids['p3']}", "contracts.rider_unavailable"
        )
        accept_invite_p2 = self._post_event(contract_a, "accept-user", actor="p2")
        self.assertEqual(accept_invite_p2.status_code, 200)
        self.assertTrue(accept_invite_p2.json().get("ok"))

        contract_c_doc = self.httpx.get(
            f"/contracts/{contract_c}", headers=self._headers("owner-1")
        ).json()
        self.assertEqual(
            self._user_state(contract_c_doc, self.user_ids["p2"]), "REJECTED"
        )
        after_rider_unavailable_c = self._count_notifications_for(
            f"u:{self.user_ids['p3']}", "contracts.rider_unavailable"
        )
        self.assertGreaterEqual(
            after_rider_unavailable_c, before_rider_unavailable_c + 1
        )

        # Driver remove accepted user and rider cancel flows.
        driver_remove_p2 = self._post_event(
            contract_a,
            "driver-reject-user",
            actor="d1",
            payload={"principal": p2_principal},
        )
        self.assertEqual(driver_remove_p2.status_code, 200)
        self.assertTrue(driver_remove_p2.json().get("ok"))

        rider_cancel_p1 = self._post_event(contract_a, "cancel-user", actor="p1")
        self.assertEqual(rider_cancel_p1.status_code, 200)
        self.assertTrue(rider_cancel_p1.json().get("ok"))

        contract_a_doc = self.httpx.get(
            f"/contracts/{contract_a}", headers=self._headers("owner-1")
        ).json()
        self.assertEqual(
            self._user_state(contract_a_doc, self.user_ids["p2"]), "REJECTED"
        )
        self.assertEqual(
            self._user_state(contract_a_doc, self.user_ids["p1"]), "CANCELLED"
        )

        # ONBOARDING terminal events tested in same journey on dedicated contracts.
        created_ready = self._create_contract(
            template_id,
            self._gherkin_context_for("d1", ["p4"]),
            initial_state="START",
            actor="p4",
        )
        self.assertEqual(created_ready.status_code, 201, msg=created_ready.text)
        contract_ready = str(created_ready.json()["id"])
        set_ready = self._post_event(contract_ready, "set-ready", actor="d1")
        self.assertEqual(set_ready.status_code, 200)
        self.assertTrue(set_ready.json().get("ok"))
        ready_doc = self.httpx.get(
            f"/contracts/{contract_ready}", headers=self._headers("owner-1")
        ).json()
        self.assertEqual(ready_doc["state"], "READY")

        created_cancel_trip = self._create_contract(
            template_id,
            self._gherkin_context_for("d1", ["p4"]),
            initial_state="START",
            actor="p4",
        )
        self.assertEqual(
            created_cancel_trip.status_code, 201, msg=created_cancel_trip.text
        )
        contract_cancel_trip = str(created_cancel_trip.json()["id"])
        cancel_trip = self._post_event(
            contract_cancel_trip,
            "driver-reject-trip",
            actor="d1",
        )
        self.assertEqual(cancel_trip.status_code, 200)
        self.assertTrue(cancel_trip.json().get("ok"))
        cancelled_trip_doc = self.httpx.get(
            f"/contracts/{contract_cancel_trip}", headers=self._headers("owner-1")
        ).json()
        self.assertEqual(cancelled_trip_doc["state"], "REJECTED")

    def test_update_contract_effect_updates_another_contract(self) -> None:
        definition = {
            "id": "contract-bulk-update",
            "version": "1.0",
            "initial_state": "S1",
            "states": {
                "S1": {
                    "events": {
                        "UpdateOthers": {
                            "trigger": [
                                {
                                    "type": "api",
                                    "path": "update-others",
                                    "method": "POST",
                                    "payload_schema": {
                                        "type": "object",
                                        "required": ["target_contract", "value"],
                                        "properties": {
                                            "target_contract": {
                                                "type": "string",
                                                "minLength": 1,
                                            },
                                            "value": {"type": "string", "minLength": 1},
                                        },
                                        "additionalProperties": False,
                                    },
                                }
                            ],
                            "effects": [
                                {
                                    "title": "Bulk Update Contracts",
                                    "description": "Updates target contracts with a propagated marker from the source event.",
                                    "type": "update.contract",
                                    "updates": {
                                        "$$ctx.payload.target_contract": {
                                            "$set": {
                                                "context.bulk_marker": "$$ctx.payload.value"
                                            }
                                        }
                                    },
                                }
                            ],
                        }
                    }
                }
            },
        }

        template_id = self._create_template(definition)
        c1 = self._create_contract(template_id, {"seed": 1})
        c2 = self._create_contract(template_id, {"seed": 2})
        self.assertEqual(c1.status_code, 201)
        self.assertEqual(c2.status_code, 201)

        cid1 = c1.json()["id"]
        cid2 = c2.json()["id"]
        r = self._post_event(
            cid1,
            "update-others",
            actor="u1",
            payload={"target_contract": cid2, "value": "propagated"},
        )
        self.assertEqual(r.status_code, 200)

        got2 = self.httpx.get(f"/contracts/{cid2}", headers=self._headers("owner-1"))
        self.assertEqual(got2.status_code, 200)
        self.assertEqual(
            (got2.json().get("context") or {}).get("bulk_marker"), "propagated"
        )

    def test_update_contract_effect_supports_update_pipeline_in_updates(self) -> None:
        definition = {
            "id": "contract-bulk-update-updates",
            "version": "1.0",
            "initial_state": "S1",
            "states": {
                "S1": {
                    "events": {
                        "UpdateBatch": {
                            "trigger": [
                                {
                                    "type": "api",
                                    "path": "update-batch",
                                    "method": "POST",
                                    "payload_schema": {
                                        "type": "object",
                                        "required": ["target_contract", "value"],
                                        "properties": {
                                            "target_contract": {
                                                "type": "string",
                                                "minLength": 1,
                                            },
                                            "value": {"type": "string", "minLength": 1},
                                        },
                                        "additionalProperties": False,
                                    },
                                }
                            ],
                            "effects": [
                                {
                                    "title": "Bulk Update Contracts",
                                    "description": "Updates target contracts with a uniform update list.",
                                    "type": "update.contract",
                                    "updates": {
                                        "$$ctx.payload.target_contract": [
                                            {
                                                "$set": {
                                                    "context.bulk_marker": "$$ctx.payload.value"
                                                }
                                            }
                                        ]
                                    },
                                }
                            ],
                        }
                    }
                }
            },
        }

        template_id = self._create_template(definition)
        c1 = self._create_contract(template_id, {"seed": 1})
        c2 = self._create_contract(template_id, {"seed": 2})
        self.assertEqual(c1.status_code, 201)
        self.assertEqual(c2.status_code, 201)

        cid1 = c1.json()["id"]
        cid2 = c2.json()["id"]
        r = self._post_event(
            cid1,
            "update-batch",
            actor="u1",
            payload={"target_contract": cid2, "value": "uniform"},
        )
        self.assertEqual(r.status_code, 200)

        got2 = self.httpx.get(f"/contracts/{cid2}", headers=self._headers("owner-1"))
        self.assertEqual(got2.status_code, 200)
        self.assertEqual(
            (got2.json().get("context") or {}).get("bulk_marker"), "uniform"
        )
