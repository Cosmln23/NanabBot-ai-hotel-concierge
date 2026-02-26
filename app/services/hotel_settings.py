from typing import Any

from sqlalchemy.orm.attributes import flag_modified

from app.models import Hotel


def get_setting(hotel: Hotel, key: str, default: Any = None) -> Any:
    if not hotel or not hasattr(hotel, "settings"):
        return default
    data = hotel.settings or {}
    return data.get(key, default)


def get_bool_setting(hotel: Hotel, key: str, default: bool = False) -> bool:
    val = get_setting(hotel, key, default)
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.lower() in {"1", "true", "yes", "y"}
    if isinstance(val, (int, float)):
        return bool(val)
    return bool(default)


def update_settings(hotel: Hotel, updates: dict[str, Any]) -> None:
    current = hotel.settings or {}
    current.update({k: v for k, v in updates.items() if v is not None})
    hotel.settings = current
    flag_modified(hotel, "settings")
