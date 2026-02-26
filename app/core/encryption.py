"""
Encryption utilities for sensitive data storage.

Uses Fernet symmetric encryption (AES-128-CBC with HMAC).
Requires ENCRYPTION_KEY environment variable to be set.
"""

import logging
import os
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger("hotelbot.encryption")


@lru_cache(maxsize=1)
def get_fernet() -> Fernet:
    """
    Get Fernet instance with encryption key from environment.
    Cached to avoid repeated key loading.
    """
    key = os.getenv("ENCRYPTION_KEY")
    if not key:
        raise ValueError(
            "ENCRYPTION_KEY environment variable must be set. "
            'Generate one with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
        )
    try:
        return Fernet(key.encode())
    except Exception as e:
        raise ValueError(f"Invalid ENCRYPTION_KEY format: {e}")


def encrypt_value(value: str | None) -> str | None:
    """
    Encrypt a string value for database storage.

    Args:
        value: Plain text string to encrypt

    Returns:
        Encrypted string (base64 encoded) or None if input is None/empty
    """
    if not value:
        return value
    try:
        f = get_fernet()
        encrypted = f.encrypt(value.encode())
        return encrypted.decode()
    except Exception as e:
        logger.error(f"Encryption failed: {e}")
        raise


def decrypt_value(encrypted: str | None) -> str | None:
    """
    Decrypt an encrypted string from database.

    Args:
        encrypted: Encrypted string (base64 encoded)

    Returns:
        Decrypted plain text string or None if input is None/empty
    """
    if not encrypted:
        return encrypted
    try:
        f = get_fernet()
        decrypted = f.decrypt(encrypted.encode())
        return decrypted.decode()
    except InvalidToken:
        logger.warning(
            "Decryption failed: Invalid token (wrong key or corrupted data) — returning None"
        )
        return None
    except Exception as e:
        logger.warning(f"Decryption failed: {e} — returning None")
        return None


def is_encrypted(value: str | None) -> bool:
    """
    Check if a value appears to be Fernet-encrypted.
    Fernet tokens start with 'gAAAAA' (base64 encoded).
    """
    if not value:
        return False
    return value.startswith("gAAAAA")


def generate_key() -> str:
    """Generate a new Fernet encryption key."""
    return Fernet.generate_key().decode()
