# coding: utf-8
from __future__ import annotations

from typing import Any, Dict, Optional

import jsonschema
from jsonschema import Draft202012Validator


class ValidatingMongoCollection:
    """
    Wrap a mongomock collection to enforce a Mongo-like $jsonSchema validator.

    This is not a full Mongo validator implementation.
    It is enough to test server behavior that calls:
        db.command("collMod", "<collection>", validator={"$jsonSchema": ...}, validationLevel="moderate")
    """

    def __init__(self, raw_collection, validators: Dict[str, Dict[str, Any]]):
        self._c = raw_collection
        self._validators = validators

    def _validate_doc(self, doc: Dict[str, Any]) -> None:
        schema = self._validators.get(self._c.name)
        if not schema:
            return
        # Mongo wraps schema as {"$jsonSchema": {...}}
        js = schema.get("$jsonSchema") or schema
        Draft202012Validator(_normalize_bson_types(js)).validate(doc)

    # --- passthrough helpers
    @property
    def name(self) -> str:
        return self._c.name

    def __getattr__(self, item: str):
        return getattr(self._c, item)

    # --- writes with validation
    def insert_one(self, document: Dict[str, Any], *args, **kwargs):
        self._validate_doc(document)
        return self._c.insert_one(document, *args, **kwargs)

    def insert_many(self, documents, *args, **kwargs):
        for d in documents:
            self._validate_doc(d)
        return self._c.insert_many(documents, *args, **kwargs)

    def replace_one(self, filter, replacement, *args, **kwargs):
        self._validate_doc(replacement)
        return self._c.replace_one(filter, replacement, *args, **kwargs)

    def update_one(self, filter, update, *args, **kwargs):
        # Best-effort: validate full doc after applying update if possible
        # mongomock doesn't expose server-side update validation; we approximate.
        doc = self._c.find_one(filter)
        if doc is not None:
            new_doc = dict(doc)
            if "$set" in update and isinstance(update["$set"], dict):
                new_doc.update(update["$set"])
            self._validate_doc(new_doc)
        return self._c.update_one(filter, update, *args, **kwargs)

    def update_many(self, filter, update, *args, **kwargs):
        # Validate each matched doc best-effort
        for doc in self._c.find(filter):
            new_doc = dict(doc)
            if "$set" in update and isinstance(update["$set"], dict):
                new_doc.update(update["$set"])
            self._validate_doc(new_doc)
        return self._c.update_many(filter, update, *args, **kwargs)


class ValidatingMongoDatabase:
    """
    Wrap a mongomock database and implement `.command("collMod", ...)`.
    """

    def __init__(self, raw_db):
        self._db = raw_db
        self._validators: Dict[str, Dict[str, Any]] = {}

    def command(self, name: str, *args, **kwargs):
        """
        Support:
          db.command("collMod", "<coll>", validator={...}, validationLevel="moderate")
        """
        if name != "collMod":
            raise NotImplementedError(f"Only collMod supported in tests, got {name}")

        if not args:
            raise TypeError("collMod requires collection name as positional arg")

        coll = args[0]
        validator = kwargs.get("validator") or {}
        if validator:
            self._validators[str(coll)] = validator
        # mimic Mongo reply shape loosely
        return {"ok": 1.0, "collection": str(coll), "validator": validator}

    def __getattr__(self, item: str):
        # collection access db.items -> ValidatingMongoCollection
        raw = getattr(self._db, item)
        # mongomock collection has 'name'
        if hasattr(raw, "name"):
            return ValidatingMongoCollection(raw, self._validators)
        return raw

    def get_collection(self, name: str):
        return ValidatingMongoCollection(
            self._db.get_collection(name), self._validators
        )

    # needed sometimes by server code
    @property
    def client(self):
        return self._db.client

    @property
    def name(self) -> str:
        return self._db.name


def _normalize_bson_types(schema: Any) -> Any:
    """
    Convert Mongo-style bsonType to JSON Schema type for test validation.

    This is a best-effort adapter so Draft202012Validator can enforce
    the same constraints that Mongo would apply.
    """
    bson_to_type = {
        "object": "object",
        "string": "string",
        "int": "integer",
        "long": "integer",
        "double": "number",
        "decimal": "number",
        "bool": "boolean",
        "array": "array",
        "date": "string",
    }

    if isinstance(schema, dict):
        out: Dict[str, Any] = {}
        for k, v in schema.items():
            if k == "bsonType":
                if isinstance(v, list):
                    out["type"] = [bson_to_type.get(i, i) for i in v]
                else:
                    out["type"] = bson_to_type.get(v, v)
                continue
            out[k] = _normalize_bson_types(v)
        return out

    if isinstance(schema, list):
        return [_normalize_bson_types(i) for i in schema]

    return schema
