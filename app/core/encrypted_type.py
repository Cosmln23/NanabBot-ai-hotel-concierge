"""
SQLAlchemy TypeDecorator for transparent field encryption.

Usage:
    from app.core.encrypted_type import EncryptedString

    class MyModel(Base):
        secret_field = Column(EncryptedString, nullable=True)

The field will be automatically encrypted when saving to DB
and decrypted when reading from DB.
"""

from sqlalchemy import Text, TypeDecorator

from app.core.encryption import decrypt_value, encrypt_value, is_encrypted


class EncryptedString(TypeDecorator):
    """
    SQLAlchemy type that transparently encrypts/decrypts string values.

    - On write: encrypts plain text before storing in database
    - On read: decrypts encrypted text when loading from database
    - Handles migration: if value is not encrypted (legacy), returns as-is
    - Uses TEXT type to accommodate encrypted values (longer than original)
    """

    impl = Text  # TEXT not String - encrypted values are longer than originals
    cache_ok = True

    def process_bind_param(self, value, dialect):
        """
        Called when saving to database.
        Encrypts the value if it's not already encrypted.
        """
        if value is None:
            return None
        # Don't double-encrypt already encrypted values
        if is_encrypted(value):
            return value
        return encrypt_value(value)

    def process_result_value(self, value, dialect):
        """
        Called when loading from database.
        Decrypts the value if it's encrypted.
        """
        if value is None:
            return None
        # Only decrypt if it looks like encrypted data
        if is_encrypted(value):
            return decrypt_value(value)
        # Return plain text as-is (for backwards compatibility during migration)
        return value
