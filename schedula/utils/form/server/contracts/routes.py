# coding=utf-8
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2026, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');

"""Contracts API service (JSON state-machine workflow)."""

from __future__ import annotations

import uuid
from contextvars import ContextVar
from datetime import datetime
from typing import Any, Dict, List

import pydash
from flask import Blueprint, jsonify, request
from jsonschema import Draft202012Validator

from .engine import (
    _process_event,
    _create_contract_from_template_doc,
    _templates_coll,
    _get_contract,
    _contracts_coll,
    get_definition
)
from ..security.casbin import (
    get_auth_sub,
    require_system_admin,
)
from ..utils import (
    abort_json,
    mongo_count_documents,
    mongo_find,
    mongo_find_one,
    mongo_insert_one,
    mongo_update_one,
    now_utc,
    parse_mq_arg,
    parse_pagination_args,
    parse_sort_arg,
    set_bp_error_handlers,
    RefResolver
)

bp = Blueprint("contracts", __name__)
set_bp_error_handlers(bp)

TEMPLATE_CREATE_SCHEMA = {
    "title": "ContractTemplateCreate",
    "description": "Schema for creating a contract template.",
    "type": "object",
    "properties": {
        "name": {
            "title": "Template Name",
            "description": "Template name.",
            "type": "string",
            "minLength": 1,
        },
        "description": {
            "title": "Template Description",
            "description": "Optional template description.",
            "type": "string",
        },
        "definition": {
            "title": "Workflow Definition",
            "description": "Template workflow definition.",
            "$ref": "#/$defs/definition",
        },
        "metadata": {
            "title": "Template Metadata",
            "description": "Arbitrary metadata associated with the template.",
            "type": "object",
        },
        "is_enabled": {
            "title": "Is Enabled",
            "description": "Enable or disable the template.",
            "type": "boolean",
        },
        "allowed_subjects": {
            "title": "Allowed Subjects",
            "description": "Subjects allowed to use the template.",
            "type": "array",
            "items": {"type": "string"},
        },
        "allowed_initial_states": {
            "title": "Allowed Initial States",
            "description": "Allowed initial states in addition to the definition default.",
            "type": "array",
            "items": {"type": "string", "minLength": 1},
        },
    },
    "required": ["name", "definition"],
    "additionalProperties": False,
    "$defs": {
        "effect": {
            "title": "Effect",
            "description": "Effect executed in event or on_enter.",
            "type": "object",
            "properties": {
                "type": {
                    "title": "Effect Type",
                    "description": "Supported effect type.",
                    "type": "string",
                    "enum": [
                        "create.item",
                        "delete.item",
                        "update.item",
                        "get.item",
                        "get.contract",
                        "execute.event",
                        "iter.effects",
                        "custom.function",
                        "create.group",
                        "update.group",
                        "update.contract",
                        "delete.contract",
                        "use.credits",
                        "charge.credits",
                        "transfers.credits",
                        "balance.credits",
                        "if.else",
                        "schedule.event",
                        "unschedule.event",
                        "http.request",
                        "notify",
                    ],
                },
                "title": {"type": "string"},
                "description": {"type": "string"},
                "projection": {"type": "object"},
                "update": {
                    "anyOf": [
                        {"$ref": "#/$defs/update_operation"},
                        {
                            "type": "array",
                            "items": {"$ref": "#/$defs/update_operation"},
                        },
                    ]
                },
                "updates": {
                    "anyOf": [
                        {
                            "type": "object",
                            "additionalProperties": {
                                "anyOf": [
                                    {"$ref": "#/$defs/update_operation"},
                                    {
                                        "type": "array",
                                        "items": {"$ref": "#/$defs/update_operation"},
                                    },
                                ]
                            },
                        },
                        {"$ref": "#/$defs/json_with_refs"},
                    ]
                },
                "request": {
                    "title": "HTTP Request",
                    "description": "Kwargs compatible with requests.request for http.request effects.",
                    "$ref": "#/$defs/request_kwargs",
                },
                "requests": {
                    "type": "object",
                    "additionalProperties": {"$ref": "#/$defs/request_kwargs"},
                },
                "item_id": {
                    "anyOf": [
                        {"type": "string"},
                        {"$ref": "#/$defs/json_with_refs"},
                        {
                            "type": "array",
                            "items": {
                                "anyOf": [
                                    {"type": "string"},
                                    {"$ref": "#/$defs/json_with_refs"},
                                ]
                            },
                        },
                    ]
                },
                "group_id": {
                    "anyOf": [
                        {"type": "string"},
                        {"$ref": "#/$defs/json_with_refs"},
                    ]
                },
                "sub": {
                    "anyOf": [
                        {"type": "string", "pattern": "^[gu]:[\\w\\d]+$"},
                        {"$ref": "#/$defs/json_with_refs"},
                    ]
                },
                "item": {"type": "object"},
                "items": {"type": "object", "additionalProperties": {"type": "object"}},
                "name": {"type": "string"},
                "group_type": {"type": "string"},
                "edit_members": {"$ref": "#/$defs/edit_members"},
                "notify": {"$ref": "#/$defs/notify_kwargs"},
                "key": {
                    "title": "Response Key",
                    "description": "Logical key used to track the HTTP response.",
                    "type": "string",
                    "minLength": 1,
                },
                "event_id": {
                    "title": "Scheduled Event Id",
                    "description": "Unique scheduled event identifier in contract document.",
                    "anyOf": [
                        {"type": "string", "minLength": 1},
                        {"$ref": "#/$defs/json_with_refs"},
                        {
                            "type": "array",
                            "minItems": 1,
                            "items": {
                                "anyOf": [
                                    {"type": "string", "minLength": 1},
                                    {"$ref": "#/$defs/json_with_refs"},
                                ]
                            },
                        },
                    ],
                },
                "contract_ids": {
                    "title": "Contract Ids",
                    "description": "Target contract ids for bulk contract updates.",
                    "anyOf": [
                        {"type": "string", "minLength": 1},
                        {
                            "type": "array",
                            "minItems": 1,
                            "items": {
                                "anyOf": [
                                    {"type": "string", "minLength": 1},
                                    {"$ref": "#/$defs/json_with_refs"},
                                ]
                            },
                        },
                        {"$ref": "#/$defs/json_with_refs"},
                    ],
                },
                "contract_id": {
                    "title": "Contract Id",
                    "description": "Target contract id(s) for get.contract effect.",
                    "anyOf": [
                        {"type": "string", "minLength": 1},
                        {"$ref": "#/$defs/json_with_refs"},
                        {
                            "type": "array",
                            "minItems": 1,
                            "items": {
                                "anyOf": [
                                    {"type": "string", "minLength": 1},
                                    {"$ref": "#/$defs/json_with_refs"},
                                ]
                            },
                        },
                    ],
                },
                "event": {"$ref": "#/$defs/schedule_event"},
                "events": {
                    "type": "object",
                    "additionalProperties": {"$ref": "#/$defs/schedule_event"},
                },
                "event_name": {
                    "title": "Event Name",
                    "description": "Target event name for execute.event effects.",
                    "anyOf": [
                        {"type": "string", "minLength": 1},
                        {"$ref": "#/$defs/json_with_refs"},
                    ],
                },
                "state": {
                    "title": "State",
                    "description": "Optional state scope used by execute.event.",
                    "anyOf": [
                        {"type": "string", "minLength": 1},
                        {"$ref": "#/$defs/json_with_refs"},
                    ],
                },
                "iter": {
                    "title": "Iter Items",
                    "description": "Iteration payload entries for iter.effects.",
                    "anyOf": [
                        {
                            "type": "array",
                            "items": {"type": "object"},
                        },
                        {"$ref": "#/$defs/json_with_refs"},
                    ],
                },
                "effects": {
                    "title": "Nested Effects",
                    "description": "Nested effects list used by iter.effects.",
                    "type": "array",
                    "items": {"$ref": "#/$defs/effect"},
                },
                "func": {
                    "title": "Function Name",
                    "description": "Registered function key for custom.function effects.",
                    "anyOf": [
                        {"type": "string", "minLength": 1},
                        {"$ref": "#/$defs/json_with_refs"},
                    ],
                },
                "args": {
                    "title": "Function Args",
                    "description": "Positional arguments for custom.function effects.",
                    "anyOf": [
                        {"type": "array"},
                        {"$ref": "#/$defs/json_with_refs"},
                    ],
                },
                "kwargs": {
                    "title": "Function Kwargs",
                    "description": "Keyword arguments for custom.function effects.",
                    "anyOf": [
                        {"type": "object"},
                        {"$ref": "#/$defs/json_with_refs"},
                    ],
                },
                "credit": {"$ref": "#/$defs/credit"},
                "credits": {
                    "anyOf": [
                        {
                            "type": "object",
                            "additionalProperties": {"$ref": "#/$defs/credit"},
                        },
                        {"$ref": "#/$defs/json_with_refs"},
                    ],
                },
                "condition": {
                    "title": "Branch Condition",
                    "description": "Condition value for if.else branching.",
                    "$ref": "#/$defs/json_with_refs",
                },
                "then_effects": {
                    "type": "array",
                    "items": {"$ref": "#/$defs/effect"},
                },
                "else_effects": {
                    "type": "array",
                    "items": {"$ref": "#/$defs/effect"},
                },
            },
            "required": ["type"],
            "additionalProperties": False,
            "allOf": [
                {
                    "if": {
                        "properties": {
                            "type": {
                                "enum": [
                                    "update.contract",
                                ]
                            }
                        }
                    },
                    "then": {
                        "anyOf": [
                            {"required": ["update"], "not": {"required": ["updates"]}},
                            {"required": ["updates"], "not": {"required": ["update"]}},
                        ]
                    },
                },
                {
                    "if": {
                        "properties": {
                            "type": {
                                "enum": [
                                    "update.item",
                                ]
                            }
                        }
                    },
                    "then": {
                        "anyOf": [
                            {
                                "required": ["item_id", "update"],
                                "not": {"required": ["item", "updates"]},
                            },
                            {
                                "required": ["updates"],
                                "not": {"required": ["item_id", "update"]},
                            },
                        ],
                    },
                },
                {
                    "if": {"properties": {"type": {"const": "use.credits"}}},
                    "then": {
                        "properties": {
                            "credit": {
                                "required": ["amount"],
                                "not": {"required": ["to_wallet_id", "to_user_id"]},
                            },
                            "credits": {
                                "anyOf": [
                                    {
                                        "type": "object",
                                        "additionalProperties": {
                                            "required": ["amount"],
                                            "not": {
                                                "required": [
                                                    "to_wallet_id",
                                                    "to_user_id",
                                                ]
                                            },
                                        },
                                    },
                                    {"$ref": "#/$defs/json_with_refs"},
                                ]
                            },
                        },
                        "anyOf": [
                            {
                                "required": ["credits"],
                                "not": {"required": ["credit", "key"]},
                            },
                            {
                                "required": ["credit"],
                                "not": {"required": ["credits", "key"]},
                            },
                        ],
                    },
                },
                {
                    "if": {"properties": {"type": {"const": "charge.credits"}}},
                    "then": {
                        "properties": {
                            "credit": {
                                "required": ["amount"],
                                "not": {"required": ["to_wallet_id", "to_user_id"]},
                            },
                            "credits": {
                                "anyOf": [
                                    {
                                        "type": "object",
                                        "additionalProperties": {
                                            "required": ["amount"],
                                            "not": {
                                                "required": [
                                                    "to_wallet_id",
                                                    "to_user_id",
                                                ]
                                            },
                                        },
                                    },
                                    {"$ref": "#/$defs/json_with_refs"},
                                ]
                            },
                        },
                        "anyOf": [
                            {
                                "required": ["credits"],
                                "not": {"required": ["credit", "key"]},
                            },
                            {
                                "required": ["credit"],
                                "not": {"required": ["credits", "key"]},
                            },
                        ],
                    },
                },
                {
                    "if": {"properties": {"type": {"const": "transfers.credits"}}},
                    "then": {
                        "properties": {
                            "credit": {
                                "anyOf": [
                                    {
                                        "required": ["amount", "to_wallet_id"],
                                        "not": {"required": ["to_user_id"]},
                                    },
                                    {
                                        "required": ["amount", "to_user_id"],
                                        "not": {"required": ["to_wallet_id"]},
                                    },
                                ]
                            },
                            "credits": {
                                "anyOf": [
                                    {
                                        "type": "object",
                                        "additionalProperties": {
                                            "anyOf": [
                                                {
                                                    "required": [
                                                        "amount",
                                                        "to_wallet_id",
                                                    ],
                                                    "not": {"required": ["to_user_id"]},
                                                },
                                                {
                                                    "required": [
                                                        "amount",
                                                        "to_user_id",
                                                    ],
                                                    "not": {
                                                        "required": ["to_wallet_id"]
                                                    },
                                                },
                                            ]
                                        },
                                    },
                                    {"$ref": "#/$defs/json_with_refs"},
                                ]
                            },
                        },
                        "anyOf": [
                            {
                                "required": ["credits"],
                                "not": {"required": ["credit", "key"]},
                            },
                            {
                                "required": ["credit"],
                                "not": {"required": ["credits", "key"]},
                            },
                        ],
                    },
                },
                {
                    "if": {"properties": {"type": {"const": "balance.credits"}}},
                    "then": {
                        "properties": {
                            "credit": {
                                "not": {
                                    "required": ["amount", "to_wallet_id", "to_user_id"]
                                }
                            },
                            "credits": {
                                "anyOf": [
                                    {
                                        "type": "object",
                                        "additionalProperties": {
                                            "not": {
                                                "required": [
                                                    "amount",
                                                    "to_wallet_id",
                                                    "to_user_id",
                                                ]
                                            }
                                        },
                                    },
                                    {"$ref": "#/$defs/json_with_refs"},
                                ]
                            },
                        },
                        "anyOf": [
                            {
                                "required": ["credits"],
                                "not": {"required": ["credit", "key"]},
                            },
                            {
                                "required": ["credit", "key"],
                                "not": {"required": ["credits"]},
                            },
                        ],
                    },
                },
                {
                    "if": {"properties": {"type": {"const": "execute.event"}}},
                    "then": {"required": ["event_name"]},
                },
                {
                    "if": {"properties": {"type": {"const": "iter.effects"}}},
                    "then": {"required": ["iter", "effects"]},
                },
                {
                    "if": {"properties": {"type": {"const": "custom.function"}}},
                    "then": {"required": ["func", "key"]},
                },
                {
                    "if": {"properties": {"type": {"const": "if.else"}}},
                    "then": {
                        "required": ["condition"],
                        "anyOf": [
                            {"required": ["then_effects"]},
                            {"required": ["else_effects"]},
                        ],
                    },
                },
                {
                    "if": {"properties": {"type": {"const": "schedule.event"}}},
                    "then": {
                        "anyOf": [
                            {
                                "required": ["event", "key"],
                                "not": {"required": ["events"]},
                            },
                            {
                                "required": ["events"],
                                "not": {"required": ["event", "key"]},
                            },
                        ]
                    },
                },
                {
                    "if": {"properties": {"type": {"const": "unschedule.event"}}},
                    "then": {"required": ["event_id"]},
                },
                {
                    "if": {"properties": {"type": {"const": "http.request"}}},
                    "then": {
                        "anyOf": [
                            {
                                "required": ["request", "key"],
                                "not": {"required": ["requests"]},
                            },
                            {
                                "required": ["requests"],
                                "not": {"required": ["request", "key"]},
                            },
                        ]
                    },
                },
                {
                    "if": {"properties": {"type": {"const": "create.item"}}},
                    "then": {
                        "anyOr": [
                            {
                                "required": ["item", "key"],
                                "not": {"required": ["items"]},
                            },
                            {
                                "required": ["items"],
                                "not": {"required": ["item", "key"]},
                            },
                        ]
                    },
                },
                {
                    "if": {"properties": {"type": {"const": "get.item"}}},
                    "then": {
                        "properties": {
                            "item_id": {
                                "anyOf": [
                                    {"type": "string"},
                                    {"$ref": "#/$defs/json_with_refs"},
                                    {
                                        "type": "array",
                                        "items": {
                                            "anyOf": [
                                                {"type": "string"},
                                                {"$ref": "#/$defs/json_with_refs"},
                                            ]
                                        },
                                    },
                                ]
                            }
                        },
                        "required": ["item_id", "key"],
                    },
                },
                {
                    "if": {"properties": {"type": {"const": "get.contract"}}},
                    "then": {
                        "properties": {
                            "contract_id": {
                                "anyOf": [
                                    {"type": "string"},
                                    {"$ref": "#/$defs/json_with_refs"},
                                    {
                                        "type": "array",
                                        "items": {
                                            "anyOf": [
                                                {"type": "string"},
                                                {"$ref": "#/$defs/json_with_refs"},
                                            ]
                                        },
                                    },
                                ]
                            }
                        },
                        "required": ["contract_id", "key"],
                    },
                },
                {
                    "if": {"properties": {"type": {"const": "delete.item"}}},
                    "then": {
                        "properties": {
                            "item_id": {
                                "anyOf": [
                                    {"type": "string"},
                                    {"$ref": "#/$defs/json_with_refs"},
                                    {
                                        "type": "array",
                                        "items": {
                                            "anyOf": [
                                                {"type": "string"},
                                                {"$ref": "#/$defs/json_with_refs"},
                                            ]
                                        },
                                    },
                                ]
                            }
                        },
                        "required": ["item_id"],
                    },
                },
                {
                    "if": {"properties": {"type": {"const": "create.group"}}},
                    "then": {"required": ["name", "key"]},
                },
                {
                    "if": {"properties": {"type": {"const": "update.group"}}},
                    "then": {
                        "required": ["group_id"],
                        "anyOf": [
                            {"required": ["edit_members"]},
                            {"required": ["group_type"]},
                            {"required": ["name"]},
                        ],
                    },
                },
                {
                    "if": {"properties": {"type": {"const": "notify"}}},
                    "then": {"required": ["notify"]},
                },
            ],
        },
        "credit": {
            "properties": {
                "wallet_id": {
                    "anyOf": [{"type": "integer"}, {"$ref": "#/$defs/json_with_refs"}],
                },
                "user_id": {
                    "anyOf": [{"type": "integer"}, {"$ref": "#/$defs/json_with_refs"}],
                },
                "to_wallet_id": {
                    "anyOf": [{"type": "integer"}, {"$ref": "#/$defs/json_with_refs"}],
                },
                "to_user_id": {
                    "anyOf": [{"type": "integer"}, {"$ref": "#/$defs/json_with_refs"}],
                },
                "negative": {
                    "anyOf": [
                        {"type": "boolean", "default": False},
                        {"$ref": "#/$defs/json_with_refs"},
                    ]
                },
                "product": {
                    "anyOf": [
                        {"type": "string", "minLength": 1},
                        {"$ref": "#/$defs/json_with_refs"},
                    ],
                },
                "amount": {
                    "anyOf": [
                        {"type": "integer", "minimum": 0},
                        {"$ref": "#/$defs/json_with_refs"},
                    ],
                },
            },
            "required": ["product"],
            "allOf": [
                {
                    "anyOf": [
                        {"required": ["wallet_id"], "not": {"required": ["user_id"]}},
                        {"required": ["user_id"], "not": {"required": ["wallet_id"]}},
                        {"required": [], "not": {"required": ["wallet_id", "user_id"]}},
                    ]
                },
                {
                    "anyOf": [
                        {"not": {"required": ["amount", "to_wallet_id", "to_user_id"]}},
                        {
                            "required": ["amount"],
                            "not": {"required": ["to_wallet_id", "to_user_id"]},
                        },
                        {
                            "required": ["amount", "to_wallet_id"],
                            "not": {"required": ["to_user_id"]},
                        },
                        {
                            "required": ["amount", "to_user_id"],
                            "not": {"required": ["to_wallet_id"]},
                        },
                    ]
                },
            ],
        },
        "edit_members": {
            "title": "Edit Members",
            "description": "Batch membership updates for update.group effects.",
            "type": "object",
            "properties": {
                "add_members": {
                    "anyOf": [
                        {
                            "type": "array",
                            "items": {
                                "anyOf": [
                                    {"type": "string", "pattern": "^[ug]:.+$"},
                                    {"$ref": "#/$defs/json_with_refs"},
                                ]
                            },
                        },
                        {"$ref": "#/$defs/json_with_refs"},
                    ],
                },
                "remove_members": {
                    "anyOf": [
                        {
                            "type": "array",
                            "items": {
                                "anyOf": [
                                    {"type": "string", "pattern": "^[ug]:.+$"},
                                    {"$ref": "#/$defs/json_with_refs"},
                                ]
                            },
                        },
                        {"$ref": "#/$defs/json_with_refs"},
                    ]
                },
                "promote_admins": {
                    "anyOf": [
                        {
                            "type": "array",
                            "items": {
                                "anyOf": [
                                    {"type": "string", "pattern": "^[ug]:.+$"},
                                    {"$ref": "#/$defs/json_with_refs"},
                                ]
                            },
                        },
                        {"$ref": "#/$defs/json_with_refs"},
                    ]
                },
                "demote_admins": {
                    "anyOf": [
                        {
                            "type": "array",
                            "items": {
                                "anyOf": [
                                    {"type": "string", "pattern": "^[ug]:.+$"},
                                    {"$ref": "#/$defs/json_with_refs"},
                                ]
                            },
                        },
                        {"$ref": "#/$defs/json_with_refs"},
                    ]
                },
                "ban_members": {
                    "anyOf": [
                        {
                            "type": "array",
                            "items": {
                                "anyOf": [
                                    {"type": "string", "pattern": "^[ug]:.+$"},
                                    {"$ref": "#/$defs/json_with_refs"},
                                ]
                            },
                        },
                        {"$ref": "#/$defs/json_with_refs"},
                    ]
                },
                "unban_members": {
                    "anyOf": [
                        {
                            "type": "array",
                            "items": {
                                "anyOf": [
                                    {"type": "string", "pattern": "^[ug]:.+$"},
                                    {"$ref": "#/$defs/json_with_refs"},
                                ]
                            },
                        },
                        {"$ref": "#/$defs/json_with_refs"},
                    ]
                },
            },
            "additionalProperties": False,
        },
        "notify_kwargs": {
            "title": "Notification Kwargs",
            "description": "Kwargs accepted by notifications.service.create_notification.",
            "type": "object",
            "properties": {
                "event": {
                    "type": "string",
                    "minLength": 1,
                    "description": "Notification event name.",
                },
                "targets": {
                    "description": "Map of principal -> channel list.",
                    "anyOf": [
                        {
                            "type": "object",
                            "additionalProperties": {
                                "type": "array",
                                "minItems": 1,
                                "items": {"type": "string", "minLength": 1},
                            },
                        },
                        {"$ref": "#/$defs/json_with_refs"},
                    ],
                },
                "created_by": {
                    "type": "string",
                    "description": "Creator principal.",
                },
                "payload": {
                    "type": "object",
                    "description": "Notification payload object.",
                    "additionalProperties": True,
                },
                "severity": {
                    "type": "string",
                    "enum": ["info", "warning", "error", "success"],
                    "description": "Notification severity.",
                },
                "persist": {
                    "oneOf": [
                        {"type": "boolean"},
                        {"type": "string"},
                        {"type": "number"},
                        {"type": "null"},
                    ],
                    "description": "Persistence flag (normalized at runtime).",
                },
                "sender_principal": {
                    "type": "string",
                    "description": "Sender principal.",
                },
            },
            "required": ["event", "targets"],
            "additionalProperties": False,
        },
        "schedule_event": {
            "type": "object",
            "properties": {
                "event_name": {
                    "title": "Scheduled Event Name",
                    "description": "State event name to fire on schedule.",
                    "type": "string",
                    "minLength": 1,
                },
                "at": {
                    "title": "Execution Datetime",
                    "description": "Datetime used to trigger the scheduled event.",
                    "anyOf": [
                        {"type": "string", "format": "date-time"},
                        {"$ref": "#/$defs/json_with_refs"},
                    ],
                },
                "cron": {
                    "title": "Cron Expression",
                    "description": "Cron expression for recurring scheduled events.",
                    "type": "string",
                    "minLength": 1,
                },
                "contract_id": {"type": "string"},
                "payload": {
                    "title": "Scheduled Payload",
                    "description": "Payload passed to the scheduled event when fired.",
                    "$ref": "#/$defs/json_with_refs",
                },
                "actor_id": {
                    "title": "Scheduled Actor",
                    "description": "Actor principal used to fire scheduled event.",
                    "type": "string",
                    "minLength": 1,
                },
            },
            "required": ["event_name"],
            "anyOf": [
                {"required": ["at"], "not": {"required": ["cron"]}},
                {"required": ["cron"], "not": {"required": ["at"]}},
            ],
        },
        "event": {
            "type": "object",
            "properties": {
                "trigger": {
                    "type": "array",
                    "minItems": 1,
                    "items": {"$ref": "#/$defs/event_trigger"},
                },
                "effects": {
                    "type": "array",
                    "items": {"$ref": "#/$defs/effect"},
                },
            },
            "additionalProperties": False,
        },
        "event_trigger": {
            "title": "Event Trigger",
            "description": "Event trigger source configuration.",
            "oneOf": [
                {
                    "type": "object",
                    "properties": {
                        "type": {"const": "api"},
                        "path": {"type": "string", "minLength": 1},
                        "method": {
                            "type": "string",
                            "enum": ["POST", "GET", "PUT", "PATCH", "DELETE"],
                        },
                        "payload_schema": {"type": "object"},
                        "allow_principals": {
                            "oneOf": [
                                {"type": "array", "items": {"type": "string"}},
                                {"type": "object"},
                            ]
                        },
                        "deny_principals": {
                            "oneOf": [
                                {"type": "array", "items": {"type": "string"}},
                                {"type": "object"},
                            ]
                        },
                        "allow_user_states": {
                            "type": "array",
                            "items": {"type": "string", "minLength": 1},
                        },
                        "deny_user_states": {
                            "type": "array",
                            "items": {"type": "string", "minLength": 1},
                        },
                        "response": {
                            "title": "API Trigger Response Template",
                            "description": "JSON response template for this API trigger.",
                            "$ref": "#/$defs/json_with_refs",
                        },
                    },
                    "required": ["type", "path"],
                    "additionalProperties": False,
                },
                {
                    "type": "object",
                    "properties": {
                        "type": {"const": "db"},
                        "collection": {"type": "string", "minLength": 1},
                        "operation": {
                            "type": "string",
                            "enum": ["insert", "update", "replace", "delete"],
                        },
                    },
                    "required": ["type", "collection", "operation"],
                    "additionalProperties": False,
                },
            ],
        },
        "json_with_refs": {
            "title": "JSON with Runtime References",
            "description": "Any JSON value where objects can include $ref and $ctx placeholders resolved by RefResolver.",
            "oneOf": [
                {"type": "string"},
                {"type": "number"},
                {"type": "integer"},
                {"type": "boolean"},
                {"type": "null"},
                {
                    "type": "array",
                    "items": {"$ref": "#/$defs/json_with_refs"},
                },
                {
                    "type": "object",
                    "properties": {
                        "$ref": {
                            "type": "string",
                            "pattern": "^/items(/[^/]+){2,3}$",
                        },
                        "$ctx": {
                            "type": "string",
                            "pattern": "^[^/]+$",
                        },
                    },
                    "additionalProperties": {"$ref": "#/$defs/json_with_refs"},
                },
            ],
        },
        "request_kwargs": {
            "title": "Requests Kwargs",
            "description": "Subset of kwargs supported by requests.request.",
            "type": "object",
            "properties": {
                "method": {
                    "title": "HTTP Method",
                    "description": "HTTP method.",
                    "type": "string",
                    "enum": [
                        "GET",
                        "POST",
                        "PUT",
                        "PATCH",
                        "DELETE",
                        "HEAD",
                        "OPTIONS",
                    ],
                },
                "url": {
                    "title": "Request URL",
                    "description": "Absolute request URL.",
                    "type": "string",
                    "minLength": 1,
                },
                "params": {
                    "title": "Query Params",
                    "description": "Query string parameters.",
                    "oneOf": [
                        {"type": "object"},
                        {"type": "array"},
                        {"type": "string"},
                    ],
                },
                "data": {
                    "title": "Request Data",
                    "description": "Raw/form request body.",
                    "oneOf": [
                        {"type": "object"},
                        {"type": "array"},
                        {"type": "string"},
                        {"type": "number"},
                        {"type": "boolean"},
                        {"type": "null"},
                    ],
                },
                "json": {
                    "title": "Request JSON",
                    "description": "JSON-serializable request body.",
                },
                "headers": {
                    "title": "Headers",
                    "description": "HTTP headers.",
                    "type": "object",
                    "additionalProperties": {
                        "oneOf": [{"type": "string"}, {"type": "null"}]
                    },
                },
                "cookies": {
                    "title": "Cookies",
                    "description": "Request cookies.",
                    "type": "object",
                    "additionalProperties": {"type": "string"},
                },
                "files": {
                    "title": "Files",
                    "description": "Files payload compatible with requests.",
                    "type": "object",
                    "additionalProperties": {},
                },
                "auth": {
                    "title": "Auth",
                    "description": "Basic auth credentials.",
                    "oneOf": [
                        {
                            "type": "array",
                            "minItems": 2,
                            "maxItems": 2,
                            "items": {"type": "string"},
                        },
                        {
                            "type": "object",
                            "properties": {
                                "username": {"type": "string"},
                                "password": {"type": "string"},
                            },
                            "required": ["username", "password"],
                            "additionalProperties": False,
                        },
                    ],
                },
                "timeout": {
                    "title": "Timeout",
                    "description": "Single timeout or pair (connect, read).",
                    "oneOf": [
                        {"type": "number"},
                        {
                            "type": "array",
                            "minItems": 2,
                            "maxItems": 2,
                            "items": {"type": "number"},
                        },
                    ],
                },
                "allow_redirects": {
                    "title": "Allow Redirects",
                    "description": "Follow HTTP redirects.",
                    "type": "boolean",
                },
                "proxies": {
                    "title": "Proxies",
                    "description": "Proxy mapping by scheme.",
                    "type": "object",
                    "additionalProperties": {"type": "string"},
                },
                "hooks": {
                    "title": "Hooks",
                    "description": "Optional requests hooks.",
                    "type": "object",
                },
                "stream": {
                    "title": "Stream",
                    "description": "Enable streaming response.",
                    "type": "boolean",
                },
                "verify": {
                    "title": "Verify TLS",
                    "description": "Verifica TLS (bool o path CA bundle).",
                    "oneOf": [
                        {"type": "boolean"},
                        {"type": "string"},
                    ],
                },
                "cert": {
                    "title": "Client Certificate",
                    "description": "Certificato client (path o coppia cert/key).",
                    "oneOf": [
                        {"type": "string"},
                        {
                            "type": "array",
                            "minItems": 2,
                            "maxItems": 2,
                            "items": {"type": "string"},
                        },
                    ],
                },
            },
            "required": ["url"],
            "additionalProperties": False,
        },
        "update_operation": {
            "title": "Update Payload",
            "description": "MongoDB/PyMongo update operation document (operator form).",
            "type": "object",
            "minProperties": 1,
            "maxProperties": 1,
            "propertyNames": {
                "pattern": "^\\$[A-Za-z][A-Za-z0-9_]*$",
                "description": "Mongo update operator name, e.g. $set, $unset, $inc, $push, $addToSet, $pull.",
            },
            "patternProperties": {
                "^\\$set$": {"type": "object"},
                "^\\$unset$": {
                    "anyOf": [
                        {"type": "string"},
                        {"type": "array", "items": {"type": "string"}},
                        {"type": "object"},
                    ]
                },
                "^\\$inc$": {"type": "object"},
                "^\\$push$": {"type": "object"},
                "^\\$addToSet$": {"type": "object"},
                "^\\$pull$": {"type": "object"},
                "^\\$rename$": {"type": "object"},
                "^\\$min$": {"type": "object"},
                "^\\$max$": {"type": "object"},
                "^\\$mul$": {"type": "object"},
                "^\\$currentDate$": {"type": "object"},
            },
            "additionalProperties": {"type": "object"},
        },
        "state": {
            "title": "State",
            "description": "Workflow state definition.",
            "type": "object",
            "properties": {
                "final": {"type": "boolean"},
                "on_enter": {
                    "type": "object",
                    "properties": {
                        "context_schema": {
                            "type": "object",
                            "description": "Optional JSON Schema for contract context when enter on this state.",
                        },
                        "effects": {
                            "type": "array",
                            "items": {"$ref": "#/$defs/effect"},
                        },
                    },
                    "additionalProperties": False,
                },
                "on_exit": {
                    "type": "object",
                    "properties": {
                        "context_schema": {
                            "type": "object",
                            "description": "Optional JSON Schema for contract context when exit from this state.",
                        },
                        "effects": {
                            "type": "array",
                            "items": {"$ref": "#/$defs/effect"},
                        },
                    },
                    "additionalProperties": False,
                },
                "events": {
                    "type": "object",
                    "additionalProperties": {"$ref": "#/$defs/event"},
                },
                "aggregate": {
                    "$ref": "#/$defs/json_with_refs"
                },
                "context_schema": {
                    "type": "object",
                    "description": "Optional JSON Schema for contract context when this state is modified.",
                },
            },
            "additionalProperties": False,
        },
        "definition": {
            "title": "Contract Definition",
            "description": "Complete contract workflow definition.",
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "version": {"type": "string"},
                "initial_state": {"type": "string", "minLength": 1},
                "states": {
                    "type": "object",
                    "minProperties": 1,
                    "additionalProperties": {"$ref": "#/$defs/state"},
                },
                "events": {
                    "type": "object",
                    "additionalProperties": {"$ref": "#/$defs/event"},
                },
                "aggregate": {
                    "$ref": "#/$defs/json_with_refs"
                }
            },
            "required": ["initial_state", "states"],
            "additionalProperties": False,
        },
    },
}

TEMPLATE_UPDATE_SCHEMA = {
    "type": "object",
    "properties": TEMPLATE_CREATE_SCHEMA["properties"],
    "minProperties": 1,
    "additionalProperties": False,
}

CONTRACT_CREATE_SCHEMA = {
    "type": "object",
    "properties": {
        "context": {"type": "object"},
        "initial_state": {"type": "string", "minLength": 1},
    },
    "required": ["context"],
    "additionalProperties": False,
}

_template_create_schema = ContextVar("template_create_schema", default=None)
_template_update_schema = ContextVar("template_update_schema", default=None)


def _TEMPLATE_CREATE_SCHEMA():
    schema = _template_create_schema.get()
    return TEMPLATE_CREATE_SCHEMA if schema is None else schema


def _TEMPLATE_UPDATE_SCHEMA():
    schema = _template_update_schema.get()
    return TEMPLATE_UPDATE_SCHEMA if schema is None else schema


def _ensure_indexes():
    contracts = _contracts_coll()
    templates = _templates_coll()
    contracts.create_index([("template_id", 1), ("created_at", -1)])
    contracts.create_index([("status", 1), ("updated_at", -1)])
    templates.create_index([("is_enabled", 1), ("updated_at", -1)])
    templates.create_index([("name", 1), ("updated_at", -1)])


def _serialize_contract(doc: Dict[str, Any], definition=None) -> Dict[str, Any]:
    created_at = doc.get("created_at")
    updated_at = doc.get("updated_at")
    state = doc.get("state")
    sub = get_auth_sub()
    if definition is None:
        definition = get_definition(doc)

    ctx = {"doc": doc, "user": sub}

    if pydash.has(definition, f"states.{state}.aggregate"):
        aggregate = pydash.get(definition, f"states.{state}.aggregate", {})
    else:
        aggregate = dict(pydash.get(definition, f"aggregate", {}))

    return {
        "id": doc.get("_id"),
        "status": doc.get("status"),
        "state": state,
        "aggregate_state": RefResolver(enforce_acl=False)(aggregate, ctx),
        "user_state": pydash.get(doc, f"states.{sub}"),
        "created_at": created_at.isoformat() if isinstance(created_at, datetime) else None,
        "updated_at": updated_at.isoformat() if isinstance(updated_at, datetime) else None,
    }


def _parse_json_body() -> Dict[str, Any]:
    payload = request.get_json(force=True, silent=True) or {}
    if not isinstance(payload, dict):
        abort_json(400, "Invalid JSON payload")
    return payload


@bp.get("/")
def list_contracts_for_user():
    actor_sub = get_auth_sub()
    mq = parse_mq_arg(())
    query: Dict[str, Any] = {f"states.{actor_sub}": {"$exists": True}}
    if mq:
        query = {"$and": [query, mq]}

    limit, offset = parse_pagination_args(default_limit=50, max_limit=200)

    sort_field, sort_dir = parse_sort_arg(
        allowed_fields=("_id", "created_at", "updated_at", "state", "status"),
        default_field="updated_at",
    )
    if not (request.args.get("sort") or "").strip():
        sort_dir = -1

    total = mongo_count_documents(_contracts_coll(), query)
    docs = list(
        mongo_find(_contracts_coll(), query)
        .sort(sort_field, sort_dir)
        .skip(offset)
        .limit(limit)
    )

    next_offset = offset + len(docs)
    if next_offset >= total:
        next_offset = None

    return jsonify({
        "items": [_serialize_contract(d) for d in docs],
        "total": total,
        "limit": limit,
        "offset": offset,
        "next_offset": next_offset,
    })


def _serialize_template(doc: Dict[str, Any]) -> Dict[str, Any]:
    created_at = doc.get("created_at")
    updated_at = doc.get("updated_at")
    created_at_str = (
        created_at.isoformat() if isinstance(created_at, datetime) else None
    )
    updated_at_str = (
        updated_at.isoformat() if isinstance(updated_at, datetime) else None
    )
    return {
        "id": doc.get("_id"),
        "name": doc.get("name"),
        "description": doc.get("description"),
        "is_enabled": bool(doc.get("is_enabled", False)),
        "allowed_subjects": doc.get("allowed_subjects") or [],
        "allowed_initial_states": doc.get("allowed_initial_states") or [],
        "definition": doc.get("definition") or {},
        "metadata": doc.get("metadata") or {},
        "created_at": created_at_str,
        "updated_at": updated_at_str,
    }


def _validate_schema(payload: Dict[str, Any], schema: Dict[str, Any]) -> List[str]:
    try:
        v = Draft202012Validator(schema)
        return [e.message for e in v.iter_errors(payload)]
    except Exception as e:
        return [str(e)]


def _validate_allowed_initial_states(
        definition: Dict[str, Any],
        allowed_initial_states: Any,
) -> List[str]:
    if allowed_initial_states is None:
        return []
    if not isinstance(allowed_initial_states, list):
        return ["allowed_initial_states must be array"]
    states = definition.get("states") or {}
    if not isinstance(states, dict):
        return ["definition.states must be object"]
    errors: List[str] = []
    for state in allowed_initial_states:
        if not isinstance(state, str) or not state.strip():
            errors.append("allowed_initial_states entries must be non-empty strings")
            continue
        if state not in states:
            errors.append(f"allowed_initial_states includes unknown state '{state}'")
    return errors


@bp.post("/templates")
@require_system_admin("contracts:templates", "manage")
def create_template():
    payload = _parse_json_body()
    schema_errors = _validate_schema(payload, _TEMPLATE_CREATE_SCHEMA())
    if schema_errors:
        return jsonify({"error": "Invalid payload", "details": schema_errors}), 422

    name = str(payload.get("name") or "").strip()
    description = payload.get("description")
    definition = payload.get("definition")
    if not isinstance(definition, dict):
        abort_json(400, "definition must be object")

    metadata = payload.get("metadata") or {}
    is_enabled = payload.get("is_enabled", True)
    allowed_subjects = payload.get("allowed_subjects") or []
    allowed_initial_states = payload.get("allowed_initial_states") or []

    if not name:
        abort_json(400, "name required")

    initial_state_errors = _validate_allowed_initial_states(
        definition, allowed_initial_states
    )
    if initial_state_errors:
        return (
            jsonify({"error": "Invalid payload", "details": initial_state_errors}),
            422,
        )

    now = now_utc()
    doc = {
        "_id": str(uuid.uuid4()),
        "name": name,
        "description": description,
        "definition": definition,
        "metadata": metadata,
        "is_enabled": is_enabled,
        "allowed_subjects": allowed_subjects,
        "allowed_initial_states": allowed_initial_states,
        "created_at": now,
        "updated_at": now,
    }
    mongo_insert_one(_templates_coll(), doc)
    return jsonify(_serialize_template(doc)), 201


@bp.get("/templates")
@require_system_admin("contracts:templates", "manage")
def list_templates():
    docs = list(mongo_find(_templates_coll(), {}))
    return jsonify({"templates": [_serialize_template(d) for d in docs]}), 200


@bp.get("/templates/<template_id>")
@require_system_admin("contracts:templates", "manage")
def get_template(template_id: str):
    doc = mongo_find_one(_templates_coll(), {"_id": template_id})
    if not doc:
        abort_json(404, "Template not found")
    return jsonify(_serialize_template(doc)), 200


@bp.put("/templates/<template_id>")
@require_system_admin("contracts:templates", "manage")
def update_template(template_id: str):
    payload = _parse_json_body()
    schema_errors = _validate_schema(payload, _TEMPLATE_UPDATE_SCHEMA())
    if schema_errors:
        return jsonify({"error": "Invalid payload", "details": schema_errors}), 422
    existing = mongo_find_one(_templates_coll(), {"_id": template_id})
    if not existing:
        abort_json(404, "Template not found")

    updates: Dict[str, Any] = dict(payload)

    updates["updated_at"] = now_utc()
    res = mongo_update_one(_templates_coll(), {"_id": template_id}, {"$set": updates})
    if res.matched_count != 1:
        abort_json(404, "Template not found")
    doc = mongo_find_one(_templates_coll(), {"_id": template_id})
    return jsonify(_serialize_template(doc)), 200


@bp.post("/<template_id>")
def create_contract(template_id: str):
    payload = _parse_json_body()
    schema_errors = _validate_schema(payload, CONTRACT_CREATE_SCHEMA)
    if schema_errors:
        return jsonify({"error": "Invalid payload", "details": schema_errors}), 422

    context = payload.get("context")
    initial_state = payload.get("initial_state")

    owner_id = get_auth_sub()
    template = mongo_find_one(
        _templates_coll(), {"_id": template_id, "is_enabled": True}
    )
    if not template:
        abort_json(404, "Template not found")

    doc = _create_contract_from_template_doc(
        template=template,
        template_id=template_id,
        context=context,
        owner_id=owner_id,
        initial_state=initial_state,
    )
    return jsonify(_serialize_contract(doc, template["definition"])), 201


@bp.get("/<contract_id>")
def get_contract(contract_id: str):
    query = {f"states.{get_auth_sub()}": {"$exists": True}}
    doc = _get_contract(contract_id, **query)
    if not doc:
        abort_json(404, "Contract not found")
    return jsonify(_serialize_contract(doc)), 200


@bp.route("/<contract_id>/<path:dyn_path>", methods=["POST", "GET", "PUT", "PATCH", "DELETE"])
def contract_api_event(contract_id: str, dyn_path: str):
    payload = _parse_json_body()
    actor_id = get_auth_sub()

    result, status = _process_event(
        contract_id=contract_id,
        dyn_path=dyn_path,
        actor_id=actor_id,
        body_payload=payload,
    )
    return jsonify(result), status
