from src.api.errors import Invalid, NotFound
from src.lib.validation import require_keys

_FAKE_DB: dict[str, dict] = {}


def create(payload: dict) -> dict:
    missing = require_keys(payload, ["id", "kind"])
    if missing:
        raise Invalid(f"missing keys: {missing}")
    _FAKE_DB[payload["id"]] = payload
    return payload


def fetch(obj_id: str) -> dict:
    try:
        return _FAKE_DB[obj_id]
    except KeyError:
        raise NotFound(obj_id) from None
