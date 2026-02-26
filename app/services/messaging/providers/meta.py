"""
Meta WhatsApp Cloud API provider implementation.

Supports both per-hotel credentials (BYON Premium) and global credentials
(Platform Shared Number). BYON hotels do NOT fallback to global credentials.
"""

import logging
import time

import requests

from app.core.config import get_settings
from app.core.config_loader import get_conf
from app.services.messaging.base import MessageProvider
from app.utils.message_splitter import WHATSAPP_MAX_LENGTH, split_message

logger = logging.getLogger("hotelbot.messaging.meta")


class MetaDirectProvider(MessageProvider):
    """Meta WhatsApp Cloud API provider.

    Credentials priority:
    1. Hotel-specific credentials from hotel.settings (BYON Premium clients)
    2. Global credentials from .env (Platform Shared Number - default)
    """

    def _validate_credentials(self) -> None:
        """Validate and load Meta credentials.

        BYON mode: If hotel has whatsapp_access_token configured, use ONLY hotel credentials.
                   NO fallback to global - error if incomplete.
        Platform mode: If hotel has no BYON config, use global credentials.
        """
        settings = self.hotel.settings or {}

        # Check if hotel has BYON configured (any WhatsApp credential set)
        has_byon = bool(settings.get("whatsapp_access_token") or settings.get("whatsapp_phone_id"))

        if has_byon:
            # BYON mode: Use ONLY hotel-specific credentials, NO fallback
            self.access_token = settings.get("whatsapp_access_token")
            self.phone_id = settings.get("whatsapp_phone_id") or settings.get(
                "whatsapp_phone_number_id"
            )

            if not self.access_token or not self.phone_id:
                raise ValueError(
                    f"Hotel {self.hotel.id} has BYON configured but credentials are incomplete. "
                    "Both Access Token and Phone Number ID are required. "
                    "NOT falling back to platform credentials."
                )

            logger.info(
                "Meta provider using BYON credentials for hotel_id=%s: phone_id=%s",
                self.hotel.id,
                self.phone_id,
            )
        else:
            # Platform mode: Use global credentials
            global_settings = get_settings()
            self.access_token = (
                get_conf("WHATSAPP_PLATFORM_TOKEN") or global_settings.whatsapp_access_token
            )
            self.phone_id = global_settings.whatsapp_phone_number_id

            if not self.access_token or not self.phone_id:
                raise ValueError(
                    "Platform WhatsApp credentials not configured. "
                    "Please set WHATSAPP_ACCESS_TOKEN and WHATSAPP_PHONE_NUMBER_ID in .env."
                )

            logger.info(
                "Meta provider using PLATFORM credentials for hotel_id=%s: phone_id=%s",
                self.hotel.id,
                self.phone_id,
            )

    def _send_single_chunk(self, phone_number: str, text: str) -> bool:
        """Send a single message chunk via Meta WhatsApp Cloud API.

        Args:
            phone_number: Recipient phone number in E.164 format
            text: Message text chunk to send (must be <= 4096 chars)

        Returns:
            bool: True if message sent successfully, False otherwise
        """
        url = f"https://graph.facebook.com/v22.0/{self.phone_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": phone_number,
            "type": "text",
            "text": {"body": text},
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            logger.warning("Meta: Failed to send chunk to %s: %s", phone_number, e)
            if hasattr(e, "response") and e.response is not None:
                logger.debug("Meta: Response body: %s", e.response.text)
            return False

    def send_text(self, phone_number: str, message: str) -> bool:
        """Send text message via Meta WhatsApp Cloud API.

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
            "Meta: Sending %d chunk(s) to %s via phone_id=%s",
            len(chunks),
            phone_number,
            self.phone_id,
        )

        success = True
        for i, chunk in enumerate(chunks):
            if i > 0:
                time.sleep(0.5)  # Small delay between chunks to avoid rate limiting

            if not self._send_single_chunk(phone_number, chunk):
                logger.error(
                    "Meta: Failed to send chunk %d/%d to %s",
                    i + 1,
                    len(chunks),
                    phone_number,
                )
                success = False

        if success:
            logger.info(
                "Meta: Message sent successfully to %s (%d chunk(s))",
                phone_number,
                len(chunks),
            )

        return success

    def test_connection(self) -> bool:
        """Test Meta API connection by fetching phone number info.

        Makes a lightweight GET request to validate credentials.

        Returns:
            bool: True if connection successful, False otherwise
        """
        url = f"https://graph.facebook.com/v22.0/{self.phone_id}"
        headers = {"Authorization": f"Bearer {self.access_token}"}

        try:
            logger.debug("Meta: Testing connection for phone_id=%s", self.phone_id)
            response = requests.get(url, headers=headers, timeout=5)
            response.raise_for_status()
            logger.info("Meta: Connection test successful")
            return True
        except requests.exceptions.RequestException as e:
            logger.warning("Meta: Connection test failed: %s", e)
            if hasattr(e, "response") and e.response is not None:
                logger.debug("Meta: Connection response body: %s", e.response.text)
            return False

    @property
    def provider_name(self) -> str:
        """Get provider name for logging and display."""
        return "Meta Direct API"
