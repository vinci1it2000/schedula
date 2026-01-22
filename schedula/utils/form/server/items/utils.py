from flask import current_app

from ..utils import abort_json


def get_mongo():
    """
    Return the configured MongoDB database handle for item storage.

    Expects a Flask extension named 'item_storage' exposing `.mongo_db`.
    Raises:
        RuntimeError: if the extension is not initialized/configured.
    """
    storage = current_app.extensions.get("item_storage")
    if storage is None or getattr(storage, "mongo_db", None) is None:
        raise RuntimeError(
            "Item storage not initialized. "
            "Call Items(app) or Items().init_app(app) and configure MONGO_URI."
        )
    return storage.mongo_db


def get_mongo_maxtime_ms() -> int:
    return int(current_app.config.get("ITEMS_MONGO_MAX_TIME_MS", 2000))


def normalize_category(category: str) -> str:
    c = (category or "").strip()
    if not c:
        abort_json(400, "Missing category")
    if any(ch.isspace() for ch in c):
        abort_json(400, "Invalid category")
    return c
