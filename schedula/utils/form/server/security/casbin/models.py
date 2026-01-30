# models/group.py
# coding=utf-8
# -*- coding: UTF-8 -*-

import datetime as dt
import uuid
from typing import Iterable, Literal, Dict, Any

from flask_security import current_user as cu
from flask_security.core import AnonymousUser

from . import bootstrap_group
from .bootstrap import bootstrap_platform, set_subject_banned_in_group
from .helpers import (
    u,
    g,
    g_admin,
    get_enforcer,
    ANON_USER,
    PUBLIC_ROLE,
    SYSTEM_ADMIN_ROLE,
)
from .. import User
from ...extensions import db

PrincipalKind = Literal["user", "group", "other"]
OutputMode = Literal["principal", "ids", "models", "mixed"]


def set_subject_to_group(
        group_id: str,
        subject_id: str | int,
        subject_type: str = "user",  # "user" | "group"
        *,
        admin: bool = False,
        enabled: bool = True,
):
    e = get_enforcer()

    sid = str(subject_id)
    if subject_type == "user":
        sub = u(sid)
    elif subject_type == "group":
        if sid == group_id:
            raise ValueError("A group cannot be a member of itself")
        sub = g_admin(sid) if admin else g(sid)
    else:
        raise ValueError("subject_type must be 'user' or 'group'")

    if enabled:
        role = g_admin(group_id) if admin else g(group_id)
        e.add_grouping_policy(sub, role)
    else:
        admin_role = g_admin(group_id)
        admins = e.get_users_for_role(admin_role)
        if sub in admins and len(admins) <= 1:
            raise ValueError("Cannot remove the last group admin")
        member_role = g(group_id)
        if admin:  # move to member
            e.remove_grouping_policy(sub, admin_role)
            e.add_grouping_policy(sub, member_role)
        else:
            e.remove_grouping_policy(sub, admin_role)
            e.remove_grouping_policy(sub, member_role)


def add_models(principals: Iterable[str], public: bool = False):
    users = set()
    groups = set()
    for d in principals:
        p = d["id"]
        if ANON_USER == p:
            continue
        elif p.startswith("u:"):
            users.add(int(p.split(":")[1]))
        elif p.startswith("g:"):
            groups.add(p.split(":")[1])

    if users:
        users = {v.id: v for v in User.query.filter(User.id.in_(sorted(users))).all()}
    if groups:
        groups = {
            v.id: v for v in Group.query.filter(Group.id.in_(sorted(groups))).all()
        }

    for d in principals:
        p = d["id"]
        if ANON_USER == p:
            d["model"] = None if public else AnonymousUser()
            continue
        if p.startswith("u:"):
            mdl = users[int(p.split(":")[1])]
        elif p.startswith("g:"):
            mdl = groups[p.split(":")[1]]
        else:
            raise ValueError("Unknown principal type")
        if public:
            mdl = mdl.public_json()
        d["model"] = mdl
    return principals


def ensure_public_group():
    _id = PUBLIC_ROLE.split(":")[1]
    if not db.session.get(Group, _id):
        grp = Group(id=_id, name="public")
        db.session.add(grp)
        db.session.flush()
        bootstrap_platform()
        bootstrap_group(grp.id, SYSTEM_ADMIN_ROLE)


class Group(db.Model):
    __tablename__ = "groups"

    id = db.Column(
        db.String(32), primary_key=True, default=lambda: str(uuid.uuid4().hex)
    )

    name = db.Column(db.String(255), nullable=False)
    type = db.Column(db.String(64), nullable=False, default="workspace")

    created_by = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=True,
        default=lambda: getattr(cu, "id", None),
    )
    updated_by = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=True,
        onupdate=lambda: getattr(cu, "id", None),
    )
    created_at = db.Column(db.DateTime, nullable=False, default=dt.datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=dt.datetime.utcnow,
        onupdate=dt.datetime.utcnow,
    )

    __table_args__ = (db.Index("ix_groups_type", "type"),)

    def member_role(self) -> str:
        return g(str(self.id))  # "g:<gid>"

    def admin_role(self) -> str:
        return g_admin(str(self.id))  # "g:<gid>:admin"

    def members(self, *, models: bool = False, public=True):
        e = get_enforcer()
        members = set(e.get_users_for_role(self.member_role()) or [])
        admins = set(e.get_users_for_role(self.admin_role()) or [])
        principals = [{"id": p, "is_admin": p in admins} for p in members.union(admins)]

        if models:
            principals = add_models(principals, public)
        return principals

    def add_member(self, subject_id: str | int, *, subject_type: str = "user"):
        """
        Add subject as member.
        Uses set_subject_to_group (single source of truth).
        """
        set_subject_to_group(
            group_id=str(self.id),
            subject_id=subject_id,
            subject_type=subject_type,
            admin=False,
            enabled=True,
        )

    def remove_member(self, subject_id: str | int, *, subject_type: str = "user"):
        """
        Remove subject from group entirely (member + admin).
        Uses set_subject_to_group (enforces 'cannot remove last admin').
        """
        set_subject_to_group(
            group_id=str(self.id),
            subject_id=subject_id,
            subject_type=subject_type,
            admin=False,
            enabled=False,
        )

    def promote_admin(self, subject_id: str | int, *, subject_type: str = "user"):
        """
        Promote to admin.
        """
        set_subject_to_group(
            group_id=str(self.id),
            subject_id=subject_id,
            subject_type=subject_type,
            admin=True,
            enabled=True,
        )

    def demote_admin(self, subject_id: str | int, *, subject_type: str = "user"):
        """
        Demote admin -> member.
        """
        set_subject_to_group(
            group_id=str(self.id),
            subject_id=subject_id,
            subject_type=subject_type,
            admin=True,
            enabled=False,
        )

    def ban_member(self, subject_id: str | int, *, subject_type: str = "user"):
        """
        Ban subject (member and admin roles) from this group.
        """
        set_subject_banned_in_group(
            group_id=str(self.id),
            subject_id=subject_id,
            subject_type=subject_type,
            enabled=True,
        )

    def unban_member(self, subject_id: str | int, *, subject_type: str = "user"):
        """
        Unban subject from this group.
        """
        set_subject_banned_in_group(
            group_id=str(self.id),
            subject_id=subject_id,
            subject_type=subject_type,
            enabled=False,
        )

    def public_json(
            self, include_members=False, include_models=False
    ) -> Dict[str, Any]:
        out = {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if include_members:
            out["members"] = self.members(models=include_models)
        return out

    def __repr__(self):
        return f"<Group {self.id} ({self.name},{self.type})>"
