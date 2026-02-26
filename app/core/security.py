import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

import bcrypt
import jwt
import redis
from fastapi import HTTPException, Request, status

from app.core.config import get_settings

settings = get_settings()

# Simple Redis-backed rate limiter with in-memory fallback
_RATE_LIMIT_BUCKETS: Dict[str, tuple[int, float]] = {}
_rate_limit_lock = threading.RLock()
_redis = None
try:
    _redis = redis.from_url(settings.redis_url)
except Exception:
    _redis = None


def rate_limit(key: str, limit: int, window_seconds: int = 60) -> None:
    # Prefer Redis for cross-process safety
    if _redis:
        try:
            count = _redis.incr(key, 1)
            _redis.expire(key, window_seconds)
            if count > limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests, slow down.",
                )
            return
        except HTTPException:
            raise  # Don't swallow rate-limit 429 rejections
        except Exception:
            pass  # fallback to in-memory on Redis connection errors

    # In-memory fallback (thread-safe with RLock)
    with _rate_limit_lock:
        now = time.time()
        # Cleanup expired keys periodically (every 100th call)
        if len(_RATE_LIMIT_BUCKETS) > 100:
            expired = [k for k, (_, exp) in _RATE_LIMIT_BUCKETS.items() if now > exp]
            for k in expired:
                del _RATE_LIMIT_BUCKETS[k]
        count, reset_at = _RATE_LIMIT_BUCKETS.get(key, (0, now + window_seconds))
        if now > reset_at:
            count = 0
            reset_at = now + window_seconds
        count += 1
        _RATE_LIMIT_BUCKETS[key] = (count, reset_at)
    if count > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests, slow down.",
        )


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: int, email: str, expires_minutes: int = 10080) -> str:
    """Create JWT access token. Default expiry: 7 days (10080 min) - standard for B2B SaaS."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": expire,
        "jti": str(uuid.uuid4()),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token


def decode_access_token(token: str) -> Dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        )


def get_bearer_token(request: Request) -> Optional[str]:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.split(" ", 1)[1].strip()
    return None
