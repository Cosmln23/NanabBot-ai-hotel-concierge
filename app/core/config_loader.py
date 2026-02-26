import logging
import os
import time
from typing import Optional

from app.core.db import SessionLocal
from app.models import SystemSetting

logger = logging.getLogger("hotelbot.config_loader")

_CACHE: dict[str, tuple[float, Optional[str]]] = {}
_TTL_SECONDS = 60


def get_conf(key: str, ttl_seconds: int = _TTL_SECONDS) -> Optional[str]:
    """Lookup a configuration value with cache -> DB -> env resolution."""
    now = time.time()
    cached = _CACHE.get(key)
    if cached:
        ts, val = cached
        if now - ts < ttl_seconds:
            return val
    val: Optional[str] = None
    # DB lookup
    try:
        db = SessionLocal()
        try:
            row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
            if row and row.value is not None:
                val = row.value
        finally:
            db.close()
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("Config DB lookup failed for %s: %s", key, exc)
    if val is None:
        val = os.getenv(key)
    _CACHE[key] = (now, val)
    return val
