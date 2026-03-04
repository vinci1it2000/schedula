from __future__ import annotations

import importlib.util
import os
import unittest


def ensure_server_test_env() -> None:
    extras = os.environ.get("EXTRAS", "all")
    if extras not in ("all", "form"):
        raise unittest.SkipTest("Not for extra %s." % extras)

    required_modules = (
        "flask",
        "flask_security",
        "mongomock",
        "casbin",
        "apprise",
        "yaml",
        "schemathesis",
        "stripe",
        "flask_socketio",
    )
    missing = [
        name for name in required_modules if importlib.util.find_spec(name) is None
    ]
    if missing:
        raise unittest.SkipTest(
            "Server tests skipped: missing optional dependencies: %s"
            % ", ".join(sorted(missing))
        )
