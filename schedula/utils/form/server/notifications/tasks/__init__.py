# -*- coding: UTF-8 -*-
#
# Copyright 2015-2026, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');

"""Delivery tasks and Apprise integration for notifications."""

from __future__ import annotations

import os
from typing import Dict, Any, cast, Generator
from urllib.parse import quote

import apprise
import pydash
from flask import current_app

from ..storage import list_push_tokens, delete_push_token
from ..templates import make_env
from ...security import User
from ...utils import mongo_find_one, mongo_update_one, get_mongo, now_utc, config_get


def _settings_for_user(user: User) -> Dict[str, Any]:
    """Extract notification settings subdocument from a user."""
    settings: Dict[str, Any] = {"email": quote(str(user.email)), "user": user}
    notifications = pydash.get(user, "settings.notifications", {})

    principal = f"u:{user.id}"
    settings.update(notifications)
    settings["push_device_ids"] = [
        d["token"] for d in list_push_tokens(user_id=principal)
    ]
    return settings


def get_apprise_default_channels(app=None) -> Dict[str, str]:
    """Return default APPRISE_CHANNELS templates with Jinja placeholders."""
    out: Dict[str, str] = {}
    if "email" not in out:
        username = config_get("MAIL_USERNAME", app=app)
        password = config_get("MAIL_PASSWORD", app=app)
        server = config_get("MAIL_SERVER", app=app)
        port = config_get("MAIL_PORT", app=app)
        default_sender = config_get("MAIL_DEFAULT_SENDER", app=app)
        if username and password and server:
            smtp = f"{server}:{port}" if port else str(server)
            from_value = default_sender or f"{username}"
            out["email"] = (
                f"mailtos://{quote(str(username))}:{quote(str(password))}@{server}"
                f"?smtp={quote(str(smtp))}&from={quote(str(from_value))}&to={{{{email}}}}"
            )
    if "sms" not in out:
        apprise_sms_user = config_get("APPRISE_SMS_USER", app=app)
        apprise_sms_pass = config_get("APPRISE_SMS_PASS", app=app)
        if apprise_sms_user and apprise_sms_pass:
            out["sms"] = (
                f"bulksms://{apprise_sms_user}:{apprise_sms_pass}@{{{{sms_phone}}}}"
            )
    if "push" not in out:
        apprise_fcm_api_key = config_get("APPRISE_FCM_API_KEY", app=app)
        if apprise_fcm_api_key:
            out["push"] = (
                f"fcm://{apprise_fcm_api_key}/{{{{ push_device_ids | join('/') }}}}"
            )
        else:
            apprise_fcm_project = config_get("APPRISE_FCM_PROJECT", app=app)
            apprise_fcm_keyfile = config_get("APPRISE_FCM_KEYFILE", app=app)
            if apprise_fcm_project and apprise_fcm_keyfile:
                out["push"] = (
                    f"fcm://{apprise_fcm_project}/{{{{ push_device_ids | join('/') }}}}?keyfile={apprise_fcm_keyfile}"
                )
    if "whatsapp" not in out:
        apprise_whatsapp_token = config_get("APPRISE_WHATSAPP_TOKEN", app=app)
        apprise_whatsapp_from_phone_id = config_get(
            "APPRISE_WHATSAPP_FROM_PHONE_ID", app=app
        )
        apprise_whatsapp_template = config_get("APPRISE_WHATSAPP_TEMPLATE", app=app)
        if apprise_whatsapp_token and apprise_whatsapp_from_phone_id:
            template_prefix = (
                f"{apprise_whatsapp_template}:" if apprise_whatsapp_template else ""
            )
            out["whatsapp"] = (
                f"whatsapp://{template_prefix}{apprise_whatsapp_token}"
                f"@{apprise_whatsapp_from_phone_id}/"
                "{{ whatsapp_targets | join(',') }}"
            )
    if "telegram" not in out:
        apprise_telegram_bot_token = config_get("APPRISE_TELEGRAM_BOT_TOKEN", app=app)
        if apprise_telegram_bot_token:
            out["telegram"] = (
                f"tgram://{apprise_telegram_bot_token}/"
                "{{ telegram_chat_id }}"
                "{% if telegram_topic %}:{{ telegram_topic }}{% endif %}/"
            )
    if "socket" not in out:
        out["socket"] = "socket://{{ user.id }}"
    return out


def get_apprise_channels(app=None) -> Dict[str, str]:
    """Return default APPRISE_CHANNELS templates with Jinja placeholders."""
    cfg = (app or current_app).config
    if "APPRISE_CHANNELS" in cfg:
        return cfg["APPRISE_CHANNELS"]
    elif "APPRISE_CHANNELS" in os.environ:
        return config_get("APPRISE_CHANNELS", {})
    cfg["APPRISE_CHANNELS"] = get_apprise_default_channels(app=app)
    return cfg["APPRISE_CHANNELS"]


def _yield_urls(user: User, channels: list[str] | set[str]) -> Generator[tuple[str, str | None, dict[str, Any]]]:
    """Build Apprise URLs for a user and channel list."""
    notif_settings = _settings_for_user(user)
    apprise_channels = get_apprise_channels()
    env = make_env(None, None, True)
    for ch in set(channels):
        try:
            string = apprise_channels.get(ch, "")
            if "push_device_id" in string:
                if "push_device_ids" not in string and "push_device_id" not in notif_settings:
                    for token in notif_settings["push_device_ids"]:
                        yield ch, env.from_string(string).render(push_device_id=token, **notif_settings), {
                            "push_device_ids": [token]
                        }
                else:
                    yield ch, env.from_string(string).render(**notif_settings), {
                        "push_device_ids": notif_settings["push_device_ids"]
                    }
            else:
                yield ch, env.from_string(string).render(**notif_settings), {}
        except Exception as exe:
            current_app.logger.warning(
                f"Error rendering Apprise URL for {ch} and user {user.id}: {exe}"
            )
            yield ch, None, {}


def deliver_apprise_sync(notification: str | Dict[str, Any]):
    """Deliver a notification via Apprise in-process."""
    if isinstance(notification, str):
        coll = get_mongo(collection=config_get("NOTIF_COLLECTION", "notifications"))
        n = mongo_find_one(coll, {"_id": notification})
    else:
        n = notification

    if not n:
        return

    targets = n["targets"]
    results = []
    ok_all = True

    rendered = n.get("rendered", {})
    user_ids = set(int(p.split(":", 1)[1]) for p in targets)
    user_id_col = cast(Any, getattr(User, "id"))
    user_query = User.query.filter(user_id_col.in_(user_ids))
    users: Dict[str, User] = {f"u:{u.id}": u for u in user_query.all()}

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
        for ch, url, ctx in _yield_urls(user, channels):
            if not url:
                results.append(
                    {
                        "target": principal,
                        "channel": ch,
                        "state": "skipped_no_urls",
                        "ts": now_utc(),
                    }
                )
                continue
            rendered_ch = rendered_target.get(ch, {})
            notify_kw = {
                "body": rendered_ch.get("body", ""), "title": rendered_ch.get("title", "")
            }
            if "body_format" in rendered_ch:
                notify_kw["body_format"] = rendered_ch["body_format"]
            if "attach" in rendered_ch:
                notify_kw["attach"] = rendered_ch["attach"]
            apobj = apprise.Apprise()
            apobj.add(url)
            res = {
                "target": principal,
                "channel": ch,
                "url": url,
                "ts": now_utc(),
            }
            try:
                res["ok"] = apobj.notify(**notify_kw)
            except Exception as exc:
                res["ok"] = False
                res["error"] = str(exc)
                for token in ctx.get("push_device_ids", []):
                    delete_push_token(token=token)
            ok_all = ok_all and res["ok"]
            results.append(res)

    if n.get("persist"):
        coll = get_mongo(collection=config_get("NOTIF_COLLECTION", "notifications"))
        mongo_update_one(
            coll,
            {"_id": notification},
            {
                "$set": {
                    "status": {
                        "state": "sent" if ok_all else "partial",
                        "results": results,
                        "ts": now_utc(),
                    }
                }
            },
        )
