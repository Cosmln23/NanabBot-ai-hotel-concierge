"""
Abstract base class for messaging providers.

Follows the same pattern as PMS providers for consistency.
"""

from abc import ABC, abstractmethod

from app.models import Hotel


class MessageProvider(ABC):
    """Abstract base class for messaging providers.

    All messaging providers (Meta, Twilio, etc.) must implement this interface.
    Providers support both per-hotel credentials (BYON Premium) and global
    credentials (Platform Shared Number) with automatic fallback.
    """

    def __init__(self, hotel: Hotel):
        """Initialize provider with hotel context.

        Args:
            hotel: Hotel instance containing settings and credentials

        Raises:
            ValueError: If required credentials are not configured
        """
        self.hotel = hotel
        self._validate_credentials()

    @abstractmethod
    def _validate_credentials(self) -> None:
        """Validate and load provider-specific credentials.

        Should check hotel.settings for per-hotel credentials first,
        then fall back to global credentials from get_settings().

        Raises:
            ValueError: If credentials are missing or invalid
        """
        pass

    @abstractmethod
    def send_text(self, phone_number: str, message: str) -> bool:
        """Send text message to WhatsApp number.

        Args:
            phone_number: Recipient phone number (E.164 format)
            message: Message text to send

        Returns:
            bool: True if message sent successfully, False otherwise
        """
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        """Test provider connection and credentials.

        Makes a lightweight API call to validate credentials are working.

        Returns:
            bool: True if connection successful, False otherwise
        """
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Get provider name for logging and display.

        Returns:
            str: Human-readable provider name (e.g., "Meta Direct API", "Twilio")
        """
        pass
