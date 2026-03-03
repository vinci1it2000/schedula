# coding=utf-8
# -*- coding: UTF-8 -*-

from __future__ import annotations

import logging

from sqlalchemy.exc import OperationalError

from .enforcer import get_enforcer
from .helpers import (
    SYSTEM_ADMIN_ROLE,
    AUTHENTICATED_ROLE,
    ADMIN_DOMAIN,
    PUBLIC_ROLE,
    ANON_USER,
    u,
    g,
    g_admin,
    acl_user,
    acl_group,
)

log = logging.getLogger(__name__)


def bootstrap_platform():
    """Create platform-wide roles/policies.

    - SYSTEM_ADMIN_ROLE is used to protect Casbin editor routes.
    """
    # nothing to add in p by default; system admin checks are via grouping to SYSTEM_ADMIN_ROLE
    # Ensure the role exists by adding a self grouping (optional, harmless)
    try:
        e = get_enforcer()
    except OperationalError:
        e = get_enforcer()
    e.add_grouping_policy(ANON_USER, PUBLIC_ROLE)

    # Platform-wide admin permissions.
    # IMPORTANT: Casbin remains the only source of truth. These are baseline
    # policies for a fresh deployment; you can modify them later via the Casbin
    # admin panel.

    policies = [
        # Allow system admins to manage Casbin policies via the editor/admin panel.
        [
            SYSTEM_ADMIN_ROLE,
            ADMIN_DOMAIN,
            "casbin:policy",
            "manage",
            "allow",
        ],
        # Allow system admins to manage contract templates.
        [
            SYSTEM_ADMIN_ROLE,
            ADMIN_DOMAIN,
            "contracts:templates",
            "manage",
            "allow",
        ],
        # Allow system admins to manage Stripe checkout session definitions.
        [
            SYSTEM_ADMIN_ROLE,
            ADMIN_DOMAIN,
            "stripe:checkout-sessions",
            "manage",
            "allow",
        ],
        # Allow authenticated users to create contracts from public templates.
        [
            AUTHENTICATED_ROLE,
            "acl:contracts",
            "contracts:template:public",
            "create",
            "allow",
        ],
        # Allow system admins to manage Items schemas via the editor/admin panel.
        [
            SYSTEM_ADMIN_ROLE,
            ADMIN_DOMAIN,
            "schema:items",
            "manage",
            "allow",
        ],
        # Allow authenticated users to create groups (workspaces).
        [
            AUTHENTICATED_ROLE,
            ADMIN_DOMAIN,
            "group",
            "create",
            "allow",
        ],
    ]

    for act in ("create", "read", "write", "manage"):
        policies.extend(
            [
                # Allow system admins to manage groups platform-wide.
                [
                    SYSTEM_ADMIN_ROLE,
                    ADMIN_DOMAIN,
                    "group",
                    act,
                    "allow",
                ],
                # Allow system admins to manage ItemSchema / category definitions.
                [
                    SYSTEM_ADMIN_ROLE,
                    ADMIN_DOMAIN,
                    "item",
                    act,
                    "allow",
                ],
            ]
        )

    e.add_policies(policies)


def bootstrap_user(user_id: str | int):
    """Ensure the user's personal domain and basic permissions exist."""
    uid = str(user_id)
    sub = u(uid)
    dom = acl_user(uid)
    e = get_enforcer()
    # Audience role for authenticated users
    rules = [[sub, AUTHENTICATED_ROLE], [sub, PUBLIC_ROLE]]
    if len(e.get_users_for_role(SYSTEM_ADMIN_ROLE)) == 0:
        rules.append([sub, SYSTEM_ADMIN_ROLE])
        log.info(f"User ({user_id}) added as first system admin")
    e.add_grouping_policies(rules)

    e.add_policies(
        [
            [sub, dom, "item:*", act, "allow"]
            for act in ("create", "read", "write", "manage", "notify")
        ]
    )


def bootstrap_group(group_id: str, creator_id: str):
    """Ensure group roles and baseline permissions exist."""
    gid = str(group_id)
    dom = acl_group(gid)

    member = g(gid)
    admin = g_admin(gid)

    e = get_enforcer()
    e.add_grouping_policies(
        [
            # admin inherits member
            [admin, member],
            # creator is admin
            [creator_id, admin],
        ]
    )

    # baseline: members can read/create/notify items; admins can read/write/share/manage/create/notify
    policies = [
        [member, dom, "item:*", "read", "allow"],
        [member, dom, "item:*", "create", "allow"],
        [member, dom, "item:*", "notify", "allow"],
    ]
    policies.extend(
        [
            [admin, dom, "item:*", act, "allow"]
            for act in ("create", "read", "write", "share", "manage", "notify")
        ]
    )

    policies.append([member, dom, "group", "read", "allow"])
    policies.extend(
        [[admin, dom, "group", act, "allow"] for act in ("read", "write", "manage")]
    )
    e.add_policies(policies)


def set_system_admin(user_id: str | int, enabled: bool = True):
    e = get_enforcer()
    sub = u(str(user_id))
    if enabled:
        e.add_grouping_policy(sub, SYSTEM_ADMIN_ROLE)
    else:
        admins = e.get_users_for_role(SYSTEM_ADMIN_ROLE)

        if len(admins) <= 1:
            raise ValueError("Cannot remove the last system admin")
        e.remove_grouping_policy(sub, SYSTEM_ADMIN_ROLE)


def set_subject_banned_in_group(
        group_id: str,
        subject_id: str | int,
        subject_type: str = "user",  # "user" | "group"
        obj_any: str = "item:*",
        *,
        enabled: bool = True,
        act_any: str = "*",
):
    """
    Ban/unban a subject (user or group) from a group domain.

    Ban wins: a banned subject must not access group resources even if public.

    This assumes your matcher supports:
      - p.obj == "item:*" (as "all items")
      - p.act == "*" (as "all actions")

    It writes a DENY policy in the group domain:
      p, <subject>, acl:group:<gid>, item:*, *, deny

    Notes:
    - For `subject_type="group"`, this bans the group principal itself
      (member and admin roles), not each member individually.
    - `reason` is not stored in Casbin (Casbin policies don't have metadata);
      you can log it or store it elsewhere if needed.
    """
    e = get_enforcer()

    gid = str(group_id)
    dom = acl_group(gid)

    sid = str(subject_id)
    if subject_type == "user":
        subs = [u(sid)]
    elif subject_type == "group":
        if sid == gid:
            raise ValueError("A group cannot ban itself")
        subs = [g(sid), g_admin(sid)]
    else:
        raise ValueError("subject_type must be 'user' or 'group'")

    eft = "deny"
    for sub in subs:
        if enabled:
            e.add_policy(sub, dom, obj_any, act_any, eft)
        else:
            e.remove_policy(sub, dom, obj_any, act_any, eft)
