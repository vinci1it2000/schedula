"""Notifications subsystem for Schedula Items.

Package layout:
- api: User-facing notification routes
- admin_api: Admin-only routes (settings + templates)
- service: Core notification logic + rendering
- storage: Mongo helpers + schema
- tasks: Celery tasks for external delivery channels
"""

from flask import current_app
from utils.form.server.security.casbin.helpers import get_current_sub


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

        app.register_blueprint(bp, url_prefix="/notification")
        app.register_blueprint(admin_bp, url_prefix="/admin/notification")
        app.register_blueprint(templates_bp, url_prefix="/admin/notification/templates")

        if app.config.get("NOTIF_CELERY_ENABLED") and "celery" not in app.extensions:
            from .tasks import make_celery

            app.extensions["celery"] = make_celery(app)


def notify_item_event_safe(*, event: str, item_doc: dict) -> None:
    """Safely dispatch item notifications when enabled."""
    if not current_app or not current_app.config.get("NOTIF_ENABLED"):
        return
    from .service import notify_item_event

    notify_item_event(
        event=event,
        item_doc=item_doc,
        created_by=get_current_sub(),
    )


# Public service helpers
from .service import create_notification, mark_read, unread_count  # noqa: F401
