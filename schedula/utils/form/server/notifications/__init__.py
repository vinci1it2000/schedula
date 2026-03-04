"""Notifications subsystem for Schedula Items.

Package layout:
- api: User-facing notification routes
- admin_api: Admin-only routes (settings + templates)
- service: Core notification logic + rendering
- storage: Mongo helpers + schema
- tasks: Celery tasks for external delivery channels
"""

from flask import current_app

from ..utils import config_get, get_mongo, mongo_command


class Notifications:
    """Flask extension that wires notification blueprints and Celery."""

    def __init__(self, app, *args, **kwargs):
        if app is not None:
            self.init_app(app, *args, **kwargs)

    def init_app(self, app, *args, **kwargs):
        app.extensions = getattr(app, "extensions", {})
        from .api import bp  # Flask Blueprint
        from .admin_api import admin_bp  # Admin-only settings API blueprint
        from .admin_api import templates_bp  # Admin-only templates API blueprint
        from .storage import (
            _settings_validator,
            _watchers_validator,
            _templates_validator,
            _push_tokens_validator,
            _notifications_validator,
        )

        mongo = get_mongo(app=app)

        settings_coll_id = config_get(
            "NOTIF_SETTINGS_COLLECTION", "notification_settings", app=app
        )

        mongo_command(
            mongo,
            settings_coll_id,
            validator=_settings_validator()
        )

        watchers_coll_id = config_get(
            "NOTIF_WATCHERS_COLLECTION", "notification_watchers", app=app
        )

        mongo_command(
            mongo,
            watchers_coll_id,
            validator=_watchers_validator()
        )

        templates_coll_id = config_get(
            "NOTIF_TEMPLATES_COLLECTION", "notification_templates", app=app
        )

        mongo_command(
            mongo,
            templates_coll_id,
            validator=_templates_validator(),
        )

        push_tokens_coll_id = config_get(
            "NOTIF_PUSH_TOKENS_COLLECTION", "notification_push_tokens", app=app
        )

        mongo_command(
            mongo,
            push_tokens_coll_id,
            validator=_push_tokens_validator(),
        )

        notifications_coll_id = config_get(
            "NOTIF_COLLECTION", "notifications", app=app
        )

        mongo_command(
            mongo,
            notifications_coll_id,
            validator=_notifications_validator(),
        )

        push_tokens_coll = get_mongo(
            app=app,
            collection=push_tokens_coll_id,
        )
        push_tokens_coll.create_index("user_id")
        push_tokens_coll.create_index("updated_at")
        push_tokens_coll.create_index("token", unique=True)

        settings_coll = get_mongo(
            app=app,
            collection=settings_coll_id,
        )
        settings_coll.create_index("scope.category")
        settings_coll.create_index("scope.dom")
        settings_coll.create_index([("scope.category", 1), ("scope.dom", 1)])
        settings_coll.create_index("enabled")

        watchers_coll = get_mongo(
            app=app,
            collection=watchers_coll_id,
        )
        watchers_coll.create_index("user_id")
        watchers_coll.create_index(
            [
                ("user_id", 1),
                ("event", 1),
                ("category", 1),
                ("object_id", 1),
                ("dom", 1),
            ]
        )

        templates_coll = get_mongo(
            app=app,
            collection=templates_coll_id,
        )
        templates_coll.create_index("event")
        templates_coll.create_index("updated_at")
        templates_coll.create_index([("event", 1), ("enabled", 1), ("updated_at", -1)])

        notifications_coll = get_mongo(
            app=app,
            collection=notifications_coll_id,
        )
        notifications_coll.create_index("created_at")
        notifications_coll.create_index("event")
        notifications_coll.create_index("persist")
        notifications_coll.create_index([("event", 1), ("created_at", -1)])
        notifications_coll.create_index([("persist", 1), ("created_at", -1)])

        app.register_blueprint(bp, url_prefix="/notification")
        app.register_blueprint(admin_bp, url_prefix="/admin/notification")
        app.register_blueprint(templates_bp, url_prefix="/admin/notification/templates")

        if app.config.get("NOTIF_SOCKET_ENABLED"):
            from .socketio_rt import init_socketio
            init_socketio(app)

        if app.config.get("NOTIF_CELERY_ENABLED") and "celery" not in app.extensions:
            try:
                from .tasks.task import make_celery

                app.extensions["celery"] = make_celery(app)
            except ImportError:
                pass


def notify_item_event_safe(*, event: str, item_doc: dict) -> None:
    """Safely dispatch item notifications when enabled."""
    if not current_app or not current_app.config.get("NOTIF_ENABLED"):
        return
    from .service import notify_item_event
    from ..security.casbin import get_current_sub

    try:
        notify_item_event(
            event=event,
            item_doc=item_doc,
            created_by=get_current_sub(),
        )
    except Exception as exc:
        current_app.logger.exception(exc)
