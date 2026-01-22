# coding: utf-8
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import yaml


@dataclass(frozen=True)
class OperationRef:
    method: str
    path: str
    operation: Dict[str, Any]


def load_openapi(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def iter_operations(spec: Dict[str, Any]) -> Iterable[OperationRef]:
    for path, ops in (spec.get("paths") or {}).items():
        for method, op in (ops or {}).items():
            if method.startswith("x-"):
                continue
            yield OperationRef(method=method.upper(), path=path, operation=op or {})


def response_statuses(operation: Dict[str, Any]) -> Set[int]:
    out: Set[int] = set()
    responses = operation.get("responses") or {}
    for code in responses.keys():
        if isinstance(code, int):
            out.add(code)
            continue
        if not isinstance(code, str):
            continue
        if code.isdigit():
            out.add(int(code))
            continue
        # ignore ranges like "2XX"
    return out


def is_multipart(operation: Dict[str, Any]) -> bool:
    rb = operation.get("requestBody") or {}
    content = (rb.get("content") or {})
    return "multipart/form-data" in content


def likely_requires_auth(op: OperationRef) -> bool:
    """
    Heuristic: treat '401' or '403' declared responses as auth-related.
    """
    rs = response_statuses(op.operation)
    return 401 in rs or 403 in rs
