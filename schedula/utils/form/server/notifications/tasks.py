# -*- coding: UTF-8 -*-
#
# Copyright 2015-2026, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');

"""Delivery tasks and Apprise integration for notifications."""

from __future__ import annotations

from typing import Dict, Any
from urllib.parse import quote

import apprise
from celery import Celery, shared_task
from flask import current_app

from .templates import make_env
from ..security import User
from ..utils import mongo_find_one, mongo_update_one, get_mongo, now_utc, config_get


def _settings_for_user(user: User) -> dict:
    """Extract notification settings subdocument from a user."""
    settings = {"email": quote(str(user.email))}
    settings.update((user.settings or {}).get("notifications", {}))
    return settings


def _mail_url(user: User) -> str | None:
    """Build an Apprise mail URL for a user."""
    username = config_get("MAIL_USERNAME")
    password = config_get("MAIL_PASSWORD")
    server = config_get("MAIL_SERVER")
    port = config_get("MAIL_PORT")
    default_sender = config_get("MAIL_DEFAULT_SENDER")
    if not (username and password and server and user.email):
        return None
    smtp = f"{server}:{port}" if port else str(server)
    from_value = default_sender or f"{username}"
    from_value = quote(str(from_value))
    to_value = quote(str(user.email))
    return (
        f"mailtos://{quote(str(username))}:{quote(str(password))}@{server}"
        f"?smtp={quote(str(smtp))}&from={from_value}&to={to_value}"
    )


def _sms_url(notif_settings: dict) -> str | None:
    """Build an Apprise SMS URL from settings."""
    phone = _get_target_value(notif_settings, "sms_phone")
    apprise_sms_user = config_get("APPRISE_SMS_USER")
    apprise_sms_pass = config_get("APPRISE_SMS_PASS")
    if not (apprise_sms_user and apprise_sms_pass and phone):
        return None
    return f"bulksms://{apprise_sms_user}:{apprise_sms_pass}@{{phone}}"


def _push_url(notif_settings: dict) -> str | None:
    """Build an Apprise FCM push URL from settings."""
    device_ids = _get_target_value(notif_settings, "push_device_ids")
    if not isinstance(device_ids, list):
        return None
    device_ids = [d for d in device_ids if isinstance(d, str) and d.strip()]
    apprise_fcm_api_key = config_get("APPRISE_FCM_API_KEY")
    if not (apprise_fcm_api_key and device_ids):
        return None
    devices = "/".join(device_ids)
    return f"fcm://{apprise_fcm_api_key}/{devices}"


def _whatsapp_url(notif_settings: dict) -> str | None:
    """Build an Apprise WhatsApp URL from settings."""
    targets = _get_target_value(notif_settings, "whatsapp_targets")
    if isinstance(targets, list):
        targets = ",".join([t for t in targets if isinstance(t, str) and t.strip()])
    apprise_whatsapp_token = config_get("APPRISE_WHATSAPP_TOKEN")
    apprise_whatsapp_from_phone_id = config_get("APPRISE_WHATSAPP_FROM_PHONE_ID")
    if not (apprise_whatsapp_token and apprise_whatsapp_from_phone_id and targets):
        return None
    template = config_get("APPRISE_WHATSAPP_TEMPLATE")
    if template:
        return (
            f"whatsapp://{template}:{apprise_whatsapp_token}"
            f"@{apprise_whatsapp_from_phone_id}/{targets}"
        )
    return (
        f"whatsapp://{apprise_whatsapp_token}"
        f"@{apprise_whatsapp_from_phone_id}/{targets}"
    )


def _telegram_url(notif_settings: dict) -> str | None:
    """Build an Apprise Telegram URL from settings."""
    chat_id = _get_target_value(notif_settings, "telegram_chat_id")
    topic = _get_target_value(notif_settings, "telegram_topic")
    apprise_telegram_bot_token = config_get("APPRISE_TELEGRAM_BOT_TOKEN")
    if not (apprise_telegram_bot_token and chat_id):
        return None
    if topic:
        return f"tgram://{apprise_telegram_bot_token}/{chat_id}:{topic}/"
    return f"tgram://{apprise_telegram_bot_token}/{chat_id}/"


def _build_urls(user: User, channels: list[str]) -> set[str]:
    """Build Apprise URLs for a user and channel list."""
    notif_settings = _settings_for_user(user)
    urls: dict[str] = {}
    apprise_channels = config_get("APPRISE_CHANNELS", {})
    env = make_env(None, None, False)
    for ch in set(channels):
        try:
            urls[ch] = env.from_string(str(apprise_channels.get(ch, ""))).render(**notif_settings)
        except Exception as exe:
            current_app.logger.warning(f"Error rendering Apprise URL for {ch} and user {user.id}: {exe}")
    return urls


def deliver_apprise_sync(notification: str | Dict[str, Any]):
    """Deliver a notification via Apprise in-process."""
    if isinstance(notification, str):
        coll = get_mongo(collection=config_get("NOTIF_COLLECTION", "notifications"))
        n = mongo_find_one(coll, {"_id": notification})
    else:
        n = notification

    if not n:
        return

    targets = n.get("targets")
    if not targets:
        if n.get("persist"):
            coll = get_mongo(collection=config_get("NOTIF_COLLECTION", "notifications"))
            mongo_update_one(
                coll,
                {"_id": notification}, {"$set": {
                    "status.apprise": {
                        "state": "skipped_no_targets",
                        "ts": now_utc(),
                    }
                }},
            )
        return

    results = []
    ok_all = True

    rendered = n.get("rendered", {})
    user_ids = set(int(p.split(":", 1)[1]) for p in targets)
    users: Dict[str, User] = {
        f"u:{u.id}": u for u in User.query.filter(User.id.in_(user_ids)).all()
    }

    for principal, channels in targets.items():
        user = users.get(principal)
        if not user:
            results.append(
                {"target": principal, "state": "skipped_missing_user", "ts": now_utc()}
            )
            continue
        if not channels:
            results.append(
                {"target": principal, "state": "skipped_no_channels", "ts": now_utc()}
            )
            continue

        rendered_target = rendered.get(principal, {})
        for ch, url in _build_urls(user, channels):
            if not url:
                results.append({
                    "target": principal,
                    "channel": ch,
                    "state": "skipped_no_urls",
                    "ts": now_utc(),
                })
                continue
            rendered_ch = rendered_target.get(ch, {})
            title = rendered_ch.get("title", "")
            body = rendered_ch.get("body", "")
            apobj = apprise.Apprise()
            apobj.add(url)
            ok = apobj.notify(body=body, title=title)
            ok_all = ok_all and ok
            results.append({"target": principal, "channel": ch, "ok": ok, "ts": now_utc()})

    if n.get("persist"):
        coll = get_mongo(collection=config_get("NOTIF_COLLECTION", "notifications"))
        mongo_update_one(
            coll,
            {"_id": notification},
            {
                "$set": {
                    "status.apprise": {
                        "state": "sent" if ok_all else "partial",
                        "results": results,
                        "ts": now_utc(),
                    }
                }
            },
        )


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 8},
)
def deliver_apprise_task(self, notification: str | Dict[str, Any]):
    """Celery task wrapper for Apprise delivery."""
    return deliver_apprise_sync(notification)


def make_celery(flask_app):
    """Create and configure a Celery app bound to Flask context."""
    celery = Celery(
        flask_app.import_name,
        broker=flask_app.config.get("CELERY_BROKER_URL"),
        backend=flask_app.config.get("CELERY_RESULT_BACKEND"),
    )
    celery.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
    )

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with flask_app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery
