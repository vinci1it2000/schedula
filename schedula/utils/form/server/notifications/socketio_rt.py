# -*- coding: UTF-8 -*-
#
# Copyright 2015-2026, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');

"""Socket.IO realtime delivery for notifications."""

from __future__ import annotations

from typing import Any, Dict

from apprise import NotifyType
from apprise.plugins import NotificationManager, NotifyBase
from flask import current_app

from ..security.casbin import get_auth_sub
from ..utils import config_get

DEFAULT_NAMESPACE = "/socket.io"
EVENT_NOTIFICATION_CREATED = "notification.created"
_SOCKET_APPRISE_PLUGIN_REGISTERED = False


def _register_socket_apprise_plugin() -> None:
    global _SOCKET_APPRISE_PLUGIN_REGISTERED
    if _SOCKET_APPRISE_PLUGIN_REGISTERED:
        return

    class NotifySocketIO(NotifyBase):
        service_name = "Socket.IO"
        protocol = "socket"
        secure_protocol = "socket"
        request_rate_per_sec = 0
        templates = ("{schema}://{host}",)
        template_tokens = dict(
            NotifyBase.template_tokens,
            **{
                "host": {
                    "name": "User",
                    "type": "string",
                    "required": True,
                },
            },
        )

        @staticmethod
        def parse_url(url):
            return NotifyBase.parse_url(url, verify_host=False)

        def _build_send_calls(self, body, **kwargs):
            return super()._build_send_calls(body or " ", **kwargs)

        def send(
                self,
                body: str,
                title: str = "",
                notify_type: NotifyType = NotifyType.INFO,
                **kwargs,
        ) -> bool:
            principal = f"u:{self.host}"
            payload = {
                "title": str(title or ""),
                "body": str(body or ""),
                "channel": "socket",
                "target": principal,
                "notify_type": str(
                    getattr(notify_type, "value", notify_type) or "info"
                ),
                "body_format": str(kwargs.get("body_format") or "text"),
            }
            emit_payload(principal, payload)
            return True

    NotificationManager().add(NotifySocketIO, schemas="socket")

    _SOCKET_APPRISE_PLUGIN_REGISTERED = True


def init_socketio(app):
    from flask_socketio import Namespace, SocketIO, join_room

    _register_socket_apprise_plugin()

    app.extensions = getattr(app, "extensions", {})
    if app.extensions.get("notifications_socketio") is not None:
        return app.extensions["notifications_socketio"]

    namespace = config_get("NOTIF_SOCKET_NAMESPACE", DEFAULT_NAMESPACE, app=app)
    socketio = app.extensions.get("socketio")
    if socketio is None:
        async_mode = config_get("NOTIF_SOCKET_ASYNC_MODE", "threading", app=app)
        cors_allowed_origins = config_get(
            "NOTIF_SOCKET_CORS_ALLOWED_ORIGINS", "*", app=app
        )
        socketio = SocketIO(
            app,
            async_mode=async_mode,
            cors_allowed_origins=cors_allowed_origins,
        )

    class NotificationNamespace(Namespace):
        def on_connect(self, auth):
            try:
                principal = get_auth_sub()
            except Exception:
                return False
            join_room(principal)
            return True

    socketio.on_namespace(NotificationNamespace(namespace))
    app.extensions["notifications_socketio"] = socketio
    current_app_logger = getattr(app, "logger", None)
    if current_app_logger:
        current_app_logger.info("Notifications socket namespace enabled: %s", namespace)
    return socketio


def emit_payload(
        principal: str, payload: Dict[str, Any], event: str = EVENT_NOTIFICATION_CREATED
) -> None:
    socketio = current_app.extensions.get("notifications_socketio")
    if socketio is None:
        return
    socketio.emit(
        event,
        payload,
        to=principal,
        namespace=config_get("NOTIF_SOCKET_NAMESPACE", DEFAULT_NAMESPACE),
    )
