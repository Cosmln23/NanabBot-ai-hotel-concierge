"""
Twilio WhatsApp API provider implementation.

Supports both per-hotel credentials (BYON Premium) and global credentials
(Platform Shared Number) with automatic fallback.
"""

import logging
import time

from twilio.base.exceptions import TwilioException
from twilio.rest import Client

from app.core.config import get_settings
from app.services.messaging.base import MessageProvider
from app.utils.message_splitter import WHATSAPP_MAX_LENGTH, split_message

logger = logging.getLogger("hotelbot.messaging.twilio")


class TwilioProvider(MessageProvider):
    """Twilio WhatsApp API provider.

    Credentials priority:
    1. Hotel-specific credentials from hotel.settings (BYON Premium clients)
    2. Global credentials from .env (Platform Shared Number - default)
    """

    def _validate_credentials(self) -> None:
        """Validate and load Twilio credentials with fallback logic."""
        # Priority 1: Hotel-specific credentials (BYON Premium)
        settings = self.hotel.settings or {}
        account_sid = settings.get("twilio_account_sid")
        auth_token = settings.get("twilio_auth_token")
        from_number = settings.get("twilio_from_number")

        # Priority 2: Global credentials (Platform Shared Number)
        if not account_sid:
            global_settings = get_settings()
            account_sid = global_settings.twilio_account_sid
            auth_token = global_settings.twilio_auth_token
            from_number = global_settings.twilio_from_number

        if not account_sid or not auth_token or not from_number:
            raise ValueError(
                "Twilio credentials not configured. "
                "Please set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_FROM_NUMBER in .env "
                "or configure per-hotel credentials in Admin UI."
            )

        # Initialize Twilio client
        self.client = Client(account_sid, auth_token)
        self.from_number = from_number
        self.account_sid = account_sid

        logger.info(
            "Twilio provider initialized for hotel_id=%s: from_number=%s, using %s credentials",
            self.hotel.id,
            self.from_number,
            "hotel-specific" if settings.get("twilio_account_sid") else "global",
        )

    def _send_single_chunk(self, phone_number: str, text: str) -> bool:
        """Send a single message chunk via Twilio WhatsApp API.

        Args:
            phone_number: Recipient phone number in E.164 format
            text: Message text chunk to send (must be <= 4096 chars)

        Returns:
            bool: True if message sent successfully, False otherwise
        """
        try:
            to_whatsapp = f"whatsapp:{phone_number}"
            from_whatsapp = f"whatsapp:{self.from_number}"

            _message_obj = self.client.messages.create(
                body=text, from_=from_whatsapp, to=to_whatsapp
            )
            return True
        except TwilioException as e:
            logger.warning("Twilio: Failed to send chunk to %s: %s", phone_number, e)
            return False
        except Exception as e:
            logger.error("Twilio: Unexpected error sending chunk to %s: %s", phone_number, e)
            return False

    def send_text(self, phone_number: str, message: str) -> bool:
        """Send text message via Twilio WhatsApp API.

        Automatically splits long messages (>4096 chars) into multiple chunks.

        Args:
            phone_number: Recipient phone number in E.164 format (e.g., +40741234567)
            message: Message text to send

        Returns:
            bool: True if all message chunks sent successfully, False otherwise
        """
        chunks = split_message(message, WHATSAPP_MAX_LENGTH)

        if not chunks:
            return True

        logger.debug(
            "Twilio: Sending %d chunk(s) to %s from %s",
            len(chunks),
            phone_number,
            self.from_number,
        )

        success = True
        for i, chunk in enumerate(chunks):
            if i > 0:
                time.sleep(0.5)  # Small delay between chunks to avoid rate limiting

            if not self._send_single_chunk(phone_number, chunk):
                logger.error(
                    "Twilio: Failed to send chunk %d/%d to %s",
                    i + 1,
                    len(chunks),
                    phone_number,
                )
                success = False

        if success:
            logger.info(
                "Twilio: Message sent successfully to %s (%d chunk(s))",
                phone_number,
                len(chunks),
            )

        return success

    def test_connection(self) -> bool:
        """Test Twilio API connection by fetching account info.

        Makes a lightweight API call to validate credentials.

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            logger.debug("Twilio: Testing connection for account_sid=%s", self.account_sid)
            # Fetch account info to validate credentials
            account = self.client.api.accounts(self.account_sid).fetch()
            logger.info("Twilio: Connection test successful (Status: %s)", account.status)
            return True
        except TwilioException as e:
            logger.warning("Twilio: Connection test failed: %s", e)
            return False
        except Exception as e:
            logger.error("Twilio: Unexpected error during connection test: %s", e)
            return False

    @property
    def provider_name(self) -> str:
        """Get provider name for logging and display."""
        return "Twilio"
