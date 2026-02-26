"""
LINE Messaging API provider implementation.

Supports per-hotel credentials stored in hotel.settings with optional
global fallback from .env.
"""

import logging
import time
from typing import Dict, List

from linebot import LineBotApi
from linebot.exceptions import LineBotApiError
from linebot.models import (
    MessageAction,
    QuickReply,
    QuickReplyButton,
    TextSendMessage,
)

from app.core.config import get_settings
from app.services.messaging.base import MessageProvider
from app.utils.message_splitter import LINE_MAX_LENGTH, split_message

logger = logging.getLogger("hotelbot.messaging.line")


class LineProvider(MessageProvider):
    """LINE Messaging API provider."""

    def _validate_credentials(self) -> None:
        """Validate and load LINE credentials with fallback logic."""
        settings = self.hotel.settings or {}
        access_token = settings.get("line_channel_access_token")
        channel_secret = settings.get("line_channel_secret")

        # Optional global fallback (shared channel)
        if not access_token or not channel_secret:
            global_settings = get_settings()
            access_token = access_token or global_settings.line_channel_access_token
            channel_secret = channel_secret or global_settings.line_channel_secret

        if not access_token or not channel_secret:
            raise ValueError(
                "LINE credentials not configured. "
                "Set line_channel_access_token and line_channel_secret in hotel settings "
                "or configure global values in the environment."
            )

        self.access_token = access_token
        self.channel_secret = channel_secret
        self.client = LineBotApi(self.access_token)

        logger.info(
            "LINE provider initialized for hotel_id=%s using %s credentials",
            self.hotel.id,
            "hotel-specific" if settings.get("line_channel_access_token") else "global",
        )

    def _send_single_chunk(self, user_id: str, text: str) -> bool:
        """Send a single message chunk via LINE push API.

        Args:
            user_id: Recipient LINE user ID
            text: Message text chunk to send (must be <= 5000 chars)

        Returns:
            bool: True if message sent successfully, False otherwise
        """
        try:
            self.client.push_message(user_id, TextSendMessage(text=text))
            return True
        except LineBotApiError as e:
            logger.warning("LINE: Failed to send chunk to %s: %s", user_id, e)
            return False
        except Exception as e:
            logger.error("LINE: Unexpected error sending chunk to %s: %s", user_id, e)
            return False

    def send_text(self, phone_number: str, message: str) -> bool:
        """Send text message via LINE push API.

        Automatically splits long messages (>5000 chars) into multiple chunks.

        Args:
            phone_number: Recipient LINE user ID (legacy interface name kept for compatibility)
            message: Message text to send

        Returns:
            bool: True if all message chunks sent successfully, False otherwise
        """
        user_id = phone_number
        chunks = split_message(message, LINE_MAX_LENGTH)

        if not chunks:
            return True

        logger.debug("LINE: Sending %d chunk(s) to user_id=%s", len(chunks), user_id)

        success = True
        for i, chunk in enumerate(chunks):
            if i > 0:
                time.sleep(0.5)  # Small delay between chunks to avoid rate limiting

            if not self._send_single_chunk(user_id, chunk):
                logger.error(
                    "LINE: Failed to send chunk %d/%d to %s",
                    i + 1,
                    len(chunks),
                    user_id,
                )
                success = False

        if success:
            logger.info(
                "LINE: Message sent successfully to %s (%d chunk(s))",
                user_id,
                len(chunks),
            )

        return success

    def send_quick_reply_message(
        self, user_id: str, text: str, buttons: List[Dict[str, str]]
    ) -> bool:
        """Send a text message with Quick Reply buttons via LINE push API.

        Quick Reply buttons appear below the message. When tapped, the button
        label is sent as a regular text message (same behavior as WhatsApp
        interactive buttons).

        Args:
            user_id: Recipient LINE user ID
            text: Main message text
            buttons: List of dicts with 'id' and 'title' keys (max 13, title max 20 chars)

        Returns:
            bool: True if sent successfully, False otherwise
        """
        try:
            items = []
            for btn in buttons[:13]:  # LINE allows up to 13 quick reply buttons
                label = btn.get("title", "Button")[:20]
                items.append(QuickReplyButton(action=MessageAction(label=label, text=label)))

            msg = TextSendMessage(text=text, quick_reply=QuickReply(items=items))
            self.client.push_message(user_id, msg)
            logger.info("LINE: Quick Reply message sent to %s (%d buttons)", user_id, len(items))
            return True
        except LineBotApiError as e:
            logger.warning("LINE: Failed to send Quick Reply to %s: %s", user_id, e)
            return False
        except Exception as e:
            logger.error("LINE: Unexpected error sending Quick Reply to %s: %s", user_id, e)
            return False

    def test_connection(self) -> bool:
        """Test LINE API connection by fetching bot info."""
        try:
            logger.debug("LINE: Testing connection via get_bot_info()")
            self.client.get_bot_info()
            logger.info("LINE: Connection test successful")
            return True
        except LineBotApiError as e:
            logger.warning("LINE: Connection test failed: %s", e)
            return False
        except Exception as e:
            logger.error("LINE: Unexpected error during connection test: %s", e)
            return False

    def get_user_profile(self, user_id: str) -> dict:
        """Fetch LINE user profile (display name, picture).

        Defensive implementation - NEVER raises exceptions.
        Returns empty dict on any error.

        Args:
            user_id: LINE user ID

        Returns:
            dict with 'display_name' and 'picture_url', or empty dict on error
        """
        try:
            profile = self.client.get_profile(user_id)
            return {
                "display_name": profile.display_name,
                "picture_url": getattr(profile, "picture_url", None),
            }
        except LineBotApiError as e:
            logger.debug("LINE: Could not fetch profile for %s: %s", user_id, e)
            return {}
        except Exception as e:
            logger.debug("LINE: Unexpected error fetching profile for %s: %s", user_id, e)
            return {}

    @property
    def provider_name(self) -> str:
        """Get provider name for logging and display."""
        return "LINE"
