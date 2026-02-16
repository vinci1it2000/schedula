# coding=utf-8
# -*- coding: UTF-8 -*-

from __future__ import annotations

from typing import Dict

from .enforcer import get_enforcer
from .helpers import PUBLIC_DOMAIN, item_obj, PUBLIC_ROLE


def set_item_public_read(*, item_doc: Dict, enabled: bool = True) -> bool:
    """
    Publish or unpublish an item for public READ access.

    Semantics
    ---------
    - "Public" means readable by everyone (PUBLIC_ROLE), including:
        * anonymous users
        * authenticated users
      subject to deny rules in the same domain.

    - This function ONLY affects READ access.
      It NEVER grants write/share/manage/create permissions.

    - The item is identified using the composite object format:
        item:<category>:<item_id>

      which allows category-wide permissions via keyMatch
      (e.g. item:invoice:*).

    Required Model Assumptions
    --------------------------
    The Casbin model must include:
      - PUBLIC_ROLE as an audience role
      - keyMatch (or equivalent) in the matcher, e.g.:

        (r.obj == p.obj || keyMatch(r.obj, p.obj))

      - policy_effect that allows when no deny applies, e.g.:

        e = some(where (p.eft == allow)) && !some(where (p.eft == deny))

    Parameters
    ----------
    item_doc : Dict
        Item document containing at least:
          - "category": str
          - "_id" or "id": str

    enabled : bool, default True
        - True  -> make the item publicly readable
        - False -> revoke public read access

    Returns
    -------
    bool
        True if the policy was added/removed successfully.
        False if the policy already existed (on add) or was missing (on remove).

    Notes
    -----
    - Persistence depends on the Enforcer configuration:
        * AutoSave ON  -> persisted immediately
        * AutoSave OFF -> caller must ensure save_policy()

    - This function does NOT modify item metadata.
      If you need a cached "public" flag for listing performance,
      maintain it separately as derived state.
    """

    cat = item_doc.get("category")
    if not cat:
        raise ValueError("item_doc must contain 'category'")

    _id = item_doc.get("_id") or item_doc.get("id")
    if not _id:
        raise ValueError("item_doc must contain '_id' or 'id'")

    e = get_enforcer()
    obj = item_obj(cat, _id)
    params = PUBLIC_ROLE, PUBLIC_DOMAIN, obj, "read", "allow"

    if enabled:
        return e.add_policy(*params)
    return e.remove_policy(*params)


def authorize_item(*, sub: str, item_doc: Dict, act: str) -> bool:
    """
    Authorize a subject to perform an action on a specific item.

    This function is the canonical authorization check for item-level access.
    It evaluates permissions using Casbin with a single `enforce()` call,
    leveraging the composite object format:

        item:<category>:<item_id>

    This allows:
      - item-specific permissions (exact match)
      - category-wide permissions via wildcard (keyMatch)
      - public access via PUBLIC_ROLE
      - optional deny / public-wins semantics (depending on model)

    Parameters
    ----------
    sub : str
        The subject principal performing the request.
        Examples:
          - "u:<user_id>"
          - "g:<group_id>"
          - "r:public"
          - "u:anonymous"

    item_doc : Dict
        Item document containing the authorization context.
        Required fields:
          - "category": str
              Logical item category (e.g. "invoice", "report").
          - "_id" or "id": str
              Unique item identifier.
          - "acl_dom": str
              Authorization domain for the item
              (e.g. "acl:group:<gid>" or "acl:user:<uid>").

    act : str
        Action to authorize.
        Typical values:
          - "read"
          - "write"
          - "share"
          - "manage"
          - "create"

        The model may allow wildcard actions ("*") depending on matcher rules.

    Returns
    -------
    bool
        True  -> the subject is authorized
        False -> access is denied or the item context is incomplete

    Authorization Model Assumptions
    -------------------------------
    This function assumes the following Casbin model features:

    1) Composite object naming:
       - Request object: item:<category>:<item_id>
       - Policy objects may be:
           * exact: item:<category>:<item_id>
           * category-wide: item:<category>:*

    2) Matcher supports keyMatch for object wildcards:
       Example:
           (r.obj == p.obj || keyMatch(r.obj, p.obj))

    3) Public access (optional):
      - PUBLIC_ROLE is linked to anonymous and/or authenticated users
      - Public read policies may exist with eft="allow"

    4) Domains are strict:
       - Authorization is evaluated within item_doc["acl_dom"]
       - No implicit domain fallback unless explicitly modeled (e.g. acl:global)

    Notes
    -----
    - This function performs NO side effects.
    - It does NOT check item existence or visibility in storage.
    - It is safe to call multiple times per request (enforce is in-memory).
    - For large listings, prefer permission indexing instead of per-item enforce.

    Examples
    --------
    >>> authorize_item(
    ...     sub="u:7",
    ...     item_doc={
    ...         "category": "invoice",
    ...         "_id": "65a1f...",
    ...         "acl_dom": "acl:group:123",
    ...     },
    ...     act="write"
    ... )
    True
    """
    e = get_enforcer()

    cat = item_doc.get("category")
    _id = item_doc.get("_id") or item_doc.get("id")
    dom = item_doc.get("acl_dom")

    if not (cat and _id and dom):
        return False

    return e.enforce(sub, dom, item_obj(cat, _id), act)
