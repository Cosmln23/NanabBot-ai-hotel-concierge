"""
Provider factory for messaging service selection.

Routes to appropriate provider based on hotel configuration with backward compatibility.
"""

from app.models import Hotel
from app.services.messaging.base import MessageProvider
from app.services.messaging.providers.line import LineProvider
from app.services.messaging.providers.meta import MetaDirectProvider
from app.services.messaging.providers.twilio import TwilioProvider


def get_message_provider(hotel: Hotel) -> MessageProvider:
    """Get appropriate messaging provider for hotel.

    Provider selection logic:
    1. Check hotel.settings["messaging_provider"] for per-hotel override
    2. Default to "meta" for backward compatibility (Platform Shared Number)

    Supported providers:
    - "meta" (default): Meta WhatsApp Cloud API
    - "twilio": Twilio WhatsApp API
    - "line": LINE Messaging API
    - "" or None: Falls back to Meta

    Args:
        hotel: Hotel instance containing settings and credentials

    Returns:
        MessageProvider: Appropriate provider instance (Meta or Twilio)

    Raises:
        ValueError: If credentials are not configured for selected provider
    """
    # Check hotel-specific provider preference
    settings = hotel.settings or {}
    provider_type = settings.get("messaging_provider", "meta")

    # Handle empty string as default
    if not provider_type:
        provider_type = "meta"

    import logging

    logger = logging.getLogger("hotelbot.messaging.factory")
    logger.debug("Selecting provider '%s' for hotel_id=%s", provider_type, hotel.id)

    # Route to appropriate provider
    if provider_type == "twilio":
        return TwilioProvider(hotel)
    if provider_type == "line":
        return LineProvider(hotel)
    elif provider_type == "meta":
        return MetaDirectProvider(hotel)
    else:
        # Unknown provider - default to Meta with warning
        logger.warning(
            "Unknown provider '%s' for hotel_id=%s, defaulting to Meta",
            provider_type,
            hotel.id,
        )
        return MetaDirectProvider(hotel)
