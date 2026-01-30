# coding=utf-8
# -*- coding: UTF-8 -*-
#
# Copyright 2015-2026, Vincenzo Arcidiacono;
# Licensed under the EUPL (the 'Licence');

"""Configuration helpers.

All configuration is read from Flask `current_app.config` and/or env vars that the
host application forwards into config.

Keys (with suggested defaults):

- NOTIF_COLLECTION: "notifications"
- NOTIF_REF_MAX_DEPTH: 3  (max depth for {$ref: ...} resolution)
- NOTIF_REF_ENFORCE_ACL: true  (enforce ACL checks while resolving refs)
- NOTIF_TEMPLATES_COLLECTION: "notification_templates"

- NOTIF_PERSIST_DEFAULT: "auto"  (auto|true|false)

- APPRISE_SMS_USER: ""
- APPRISE_SMS_PASS: ""
- APPRISE_WHATSAPP_TOKEN: ""
- APPRISE_WHATSAPP_FROM_PHONE_ID: ""
- APPRISE_WHATSAPP_TEMPLATE: "" (optional)
- APPRISE_TELEGRAM_BOT_TOKEN: ""
- APPRISE_FCM_API_KEY: ""

"""

import os
from dataclasses import dataclass

from flask import current_app


@dataclass(frozen=True)
class NotifConfig:
    """Typed notification configuration resolved from app config and env."""

    collection: str
    watchers_collection: str
    settings_collection: str
    templates_collection: str
    persist_default: str

    channels_default: str
    channels_mandatory: str

    ref_max_depth: int

    apprise_sms_user: str
    apprise_sms_pass: str
    apprise_whatsapp_token: str
    apprise_whatsapp_from_phone_id: str
    apprise_whatsapp_template: str
    apprise_telegram_bot_token: str
    apprise_fcm_api_key: str


def get_notif_config() -> NotifConfig:
    """Load notification configuration from current app and environment."""
    cfg = current_app.config

    def _c(key: str, default: str = "") -> str:
        v = cfg.get(key, os.environ.get(key))
        if v is None or v == "":
            return default
        return str(v)

    return NotifConfig(
        collection=_c("NOTIF_COLLECTION", "notifications"),
        watchers_collection=_c("NOTIF_WATCHERS_COLLECTION", "notification_watchers"),
        settings_collection=_c("NOTIF_SETTINGS_COLLECTION", "notification_settings"),
        templates_collection=_c("NOTIF_TEMPLATES_COLLECTION", "notification_templates"),
        persist_default=_c("NOTIF_PERSIST_DEFAULT", "auto"),
        channels_default=_c("NOTIF_CHANNELS_DEFAULT", "in_app"),
        channels_mandatory=_c("NOTIF_CHANNELS_MANDATORY", ""),
        ref_max_depth=int(_c("NOTIF_REF_MAX_DEPTH", "3")),
        apprise_sms_user=_c("APPRISE_SMS_USER", ""),
        apprise_sms_pass=_c("APPRISE_SMS_PASS", ""),
        apprise_whatsapp_token=_c("APPRISE_WHATSAPP_TOKEN", ""),
        apprise_whatsapp_from_phone_id=_c("APPRISE_WHATSAPP_FROM_PHONE_ID", ""),
        apprise_whatsapp_template=_c("APPRISE_WHATSAPP_TEMPLATE", ""),
        apprise_telegram_bot_token=_c("APPRISE_TELEGRAM_BOT_TOKEN", ""),
        apprise_fcm_api_key=_c("APPRISE_FCM_API_KEY", ""),
    )
