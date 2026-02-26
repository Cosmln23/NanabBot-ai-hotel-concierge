import logging
import time
from typing import Dict, List, Optional

import requests

from app.core.config import get_settings
from app.utils.message_splitter import WHATSAPP_MAX_LENGTH, split_message

logger = logging.getLogger("hotelbot.whatsapp")


def _get_whatsapp_credentials(hotel=None) -> tuple:
    """
    Get WhatsApp credentials based on hotel settings or global config.

    Returns:
        tuple: (token, phone_number_id, credential_source) or (None, None, None) if not available
    """
    settings = get_settings()

    if hotel and hotel.settings:
        hotel_settings = hotel.settings or {}
        has_byon = bool(
            hotel_settings.get("whatsapp_access_token") or hotel_settings.get("whatsapp_phone_id")
        )

        if has_byon:
            token = hotel_settings.get("whatsapp_access_token")
            phone_number_id = hotel_settings.get("whatsapp_phone_id") or hotel_settings.get(
                "whatsapp_phone_number_id"
            )

            if not token or not phone_number_id:
                logger.error("BYON hotel %s has incomplete credentials", hotel.id)
                return None, None, None
            return token, phone_number_id, "hotel-specific"

    # Global credentials
    token = settings.whatsapp_access_token
    phone_number_id = settings.whatsapp_phone_number_id
    return token, phone_number_id, "global"


def _send_single_chunk(wa_id: str, text: str, token: str, phone_number_id: str) -> bool:
    """Send a single message chunk via WhatsApp Cloud API.

    Args:
        wa_id: Recipient WhatsApp ID
        text: Message text chunk to send (must be <= 4096 chars)
        token: WhatsApp access token
        phone_number_id: WhatsApp phone number ID

    Returns:
        bool: True if message sent successfully, False otherwise
    """
    url = f"https://graph.facebook.com/v22.0/{phone_number_id}/messages"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": wa_id,
        "type": "text",
        "text": {"body": text},
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        return True
    except Exception as e:
        logger.error("WhatsApp send error to %s: %s", wa_id, e)
        if hasattr(e, "response") and e.response is not None:
            logger.error("   Response: %s", e.response.text)
        return False


def send_text_message(
    wa_id: str, text: str, access_token: Optional[str] = None, hotel=None
) -> None:
    """
    Send a WhatsApp text message via WhatsApp Cloud API.

    Automatically splits long messages (>4096 chars) into multiple chunks.

    Credentials priority:
    1. Explicit access_token parameter (for manual override)
    2. Hotel-specific credentials from hotel.settings (BYON Premium - NO fallback)
    3. Global credentials from .env (Platform Shared Number - only if no BYON configured)

    BYON mode: If hotel has whatsapp_access_token set, use ONLY hotel credentials.
               NO fallback to global - error if incomplete.
    """
    settings = get_settings()

    # Priority 1: Explicit access_token parameter
    if access_token:
        token = access_token
        phone_number_id = settings.whatsapp_phone_number_id
        credential_source = "explicit"
    # Priority 2: Hotel-specific credentials (BYON)
    elif hotel and hotel.settings:
        hotel_settings = hotel.settings or {}
        has_byon = bool(
            hotel_settings.get("whatsapp_access_token") or hotel_settings.get("whatsapp_phone_id")
        )

        if has_byon:
            # BYON mode: Use ONLY hotel credentials, NO fallback
            token = hotel_settings.get("whatsapp_access_token")
            phone_number_id = hotel_settings.get("whatsapp_phone_id") or hotel_settings.get(
                "whatsapp_phone_number_id"
            )
            credential_source = "hotel-specific"

            if not token or not phone_number_id:
                logger.error(
                    "BYON hotel %s has incomplete credentials - NOT sending message (no fallback)",
                    hotel.id,
                )
                return None
        else:
            # Platform mode: Use global credentials
            token = settings.whatsapp_access_token
            phone_number_id = settings.whatsapp_phone_number_id
            credential_source = "global"
    # Priority 3: Global credentials (Platform Shared)
    else:
        token = settings.whatsapp_access_token
        phone_number_id = settings.whatsapp_phone_number_id
        credential_source = "global"

    logger.debug(
        "send_text_message called: wa_id=%s, token=%s, phone_number_id=%s, source=%s",
        wa_id,
        "***" if token else "MISSING",
        phone_number_id or "MISSING",
        credential_source,
    )

    if not token or not phone_number_id:
        logger.warning("WhatsApp send SKIPPED - missing credentials!")
        return None

    chunks = split_message(text, WHATSAPP_MAX_LENGTH)

    if not chunks:
        return None

    logger.debug("WhatsApp: Sending %d chunk(s) to %s", len(chunks), wa_id)

    for i, chunk in enumerate(chunks):
        if i > 0:
            time.sleep(0.5)  # Small delay between chunks to avoid rate limiting

        if not _send_single_chunk(wa_id, chunk, token, phone_number_id):
            logger.error("WhatsApp: Failed to send chunk %d/%d to %s", i + 1, len(chunks), wa_id)

    logger.info("WhatsApp message sent successfully to %s (%d chunk(s))", wa_id, len(chunks))


def send_staff_alert(phone: str, text: str, hotel=None) -> None:
    """
    Send a WhatsApp alert to staff.

    Automatically splits long messages (>4096 chars) into multiple chunks.

    Credentials priority:
    1. Hotel-specific credentials from hotel.settings (BYON Premium - NO fallback)
    2. Global credentials from .env (Platform Shared Number - only if no BYON configured)

    BYON mode: If hotel has whatsapp_access_token set, use ONLY hotel credentials.
               NO fallback to global - error if incomplete.
    """
    settings = get_settings()

    # Check hotel-specific credentials first (BYON)
    if hotel and hotel.settings:
        hotel_settings = hotel.settings or {}
        has_byon = bool(
            hotel_settings.get("whatsapp_access_token") or hotel_settings.get("whatsapp_phone_id")
        )

        if has_byon:
            # BYON mode: Use ONLY hotel credentials, NO fallback
            token = hotel_settings.get("whatsapp_access_token")
            phone_number_id = hotel_settings.get("whatsapp_phone_id") or hotel_settings.get(
                "whatsapp_phone_number_id"
            )
            credential_source = "hotel-specific"

            if not token or not phone_number_id:
                logger.error(
                    "BYON hotel %s has incomplete credentials - NOT sending staff alert (no fallback)",
                    hotel.id,
                )
                return None
        else:
            # Platform mode: Use global credentials
            token = settings.whatsapp_access_token
            phone_number_id = settings.whatsapp_phone_number_id
            credential_source = "global"
    # Use global credentials (Platform Shared)
    else:
        token = settings.whatsapp_access_token
        phone_number_id = settings.whatsapp_phone_number_id
        credential_source = "global"

    logger.debug(
        "send_staff_alert called: phone=%s, token=%s, phone_number_id=%s, source=%s",
        phone,
        "***" if token else "MISSING",
        phone_number_id or "MISSING",
        credential_source,
    )
    if not token or not phone_number_id:
        logger.warning("Staff alert SKIPPED - missing credentials!")
        return None

    chunks = split_message(text, WHATSAPP_MAX_LENGTH)

    if not chunks:
        return None

    logger.debug("Staff alert: Sending %d chunk(s) to %s", len(chunks), phone)

    for i, chunk in enumerate(chunks):
        if i > 0:
            time.sleep(0.5)  # Small delay between chunks to avoid rate limiting

        if not _send_single_chunk(phone, chunk, token, phone_number_id):
            logger.error(
                "Staff alert: Failed to send chunk %d/%d to %s",
                i + 1,
                len(chunks),
                phone,
            )

    logger.info("Staff alert sent successfully to %s (%d chunk(s))", phone, len(chunks))


def send_interactive_message(
    wa_id: str,
    body_text: str,
    buttons: List[Dict[str, str]],
    header_text: Optional[str] = None,
    footer_text: Optional[str] = None,
    hotel=None,
) -> bool:
    """
    Send a WhatsApp interactive message with reply buttons.

    Args:
        wa_id: Recipient WhatsApp ID
        body_text: Main message text
        buttons: List of button dicts with 'id' and 'title' keys (max 3 buttons, title max 20 chars)
        header_text: Optional header text
        footer_text: Optional footer text
        hotel: Hotel object for credentials

    Returns:
        bool: True if message sent successfully, False otherwise

    Example:
        send_interactive_message(
            wa_id="1234567890",
            body_text="Welcome! How can I help you?",
            buttons=[
                {"id": "housekeeping", "title": "Housekeeping"},
                {"id": "room_service", "title": "Room Service"},
                {"id": "info", "title": "Hotel Info"}
            ],
            hotel=hotel
        )
    """
    token, phone_number_id, source = _get_whatsapp_credentials(hotel)

    if not token or not phone_number_id:
        logger.warning("WhatsApp interactive message SKIPPED - missing credentials!")
        return False

    # Validate buttons (max 3, title max 20 chars)
    if len(buttons) > 3:
        logger.warning("WhatsApp allows max 3 buttons, truncating to 3")
        buttons = buttons[:3]

    # Build button objects
    button_objects = []
    for btn in buttons:
        title = btn.get("title", "Button")[:20]  # Max 20 chars
        btn_id = btn.get("id", title.lower().replace(" ", "_"))
        button_objects.append({"type": "reply", "reply": {"id": btn_id, "title": title}})

    # Build interactive message payload
    interactive = {
        "type": "button",
        "body": {"text": body_text[:1024]},  # Max 1024 chars
        "action": {"buttons": button_objects},
    }

    if header_text:
        interactive["header"] = {
            "type": "text",
            "text": header_text[:60],
        }  # Max 60 chars

    if footer_text:
        interactive["footer"] = {"text": footer_text[:60]}  # Max 60 chars

    url = f"https://graph.facebook.com/v22.0/{phone_number_id}/messages"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": wa_id,
        "type": "interactive",
        "interactive": interactive,
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        logger.info("WhatsApp interactive message sent to %s (source=%s)", wa_id, source)
        return True
    except Exception as e:
        logger.error("WhatsApp interactive send error to %s: %s", wa_id, e)
        if hasattr(e, "response") and e.response is not None:
            logger.error("   Response: %s", e.response.text)
        return False


# Button labels by language
BUTTON_LABELS = {
    "en": {
        "hotel_policies": "Hotel Policies",
        "menu": "Menu",
        "room_service": "Room Service",
        "housekeeping": "Housekeeping",
        "what_can_i_ask": "What can I ask?",
    },
    "ro": {
        "hotel_policies": "Politici Hotel",
        "menu": "Meniu",
        "room_service": "Room Service",
        "housekeeping": "Curățenie",
        "what_can_i_ask": "Ce pot întreba?",
    },
    "th": {
        "hotel_policies": "นโยบายโรงแรม",
        "menu": "เมนู",
        "room_service": "รูมเซอร์วิส",
        "housekeeping": "แม่บ้าน",
        "what_can_i_ask": "ถามอะไรได้บ้าง?",
    },
}


def get_welcome_buttons(hotel) -> List[Dict[str, str]]:
    """
    Build welcome buttons dynamically based on hotel config and service toggles.

    Priority order (max 3 buttons):
    1. Hotel Policies  (if custom_knowledge_text exists)
    2. Menu            (if hotel_products_text exists + allow_food_beverage)
    3. Housekeeping    (if allow_housekeeping)
    4. What can I ask? (always - fills remaining slot)

    Max 3 buttons (WhatsApp limit).
    """
    lang = "en"
    settings = {}
    if hotel:
        lang = hotel.staff_language or hotel.interface_language or "en"
        settings = hotel.settings or {}

    labels = BUTTON_LABELS.get(lang, BUTTON_LABELS["en"])

    # Check what's available in DB
    has_policies = bool(settings.get("custom_knowledge_text", "").strip())
    has_menu = bool(settings.get("hotel_products_text", "").strip())
    allow_food_beverage = settings.get("allow_food_beverage", True) is not False
    allow_housekeeping = settings.get("allow_housekeeping", True) is not False

    buttons = []

    # Priority 1: Hotel Policies
    if has_policies:
        buttons.append({"id": "hotel_policies", "title": labels["hotel_policies"]})

    # Priority 2: Menu (only if F&B enabled AND menu exists)
    if allow_food_beverage and has_menu:
        buttons.append({"id": "show_menu", "title": labels["menu"]})

    # Priority 3: Housekeeping
    if allow_housekeeping:
        buttons.append({"id": "housekeeping", "title": labels["housekeeping"]})

    # Priority 4: "What can I ask?" fills remaining slot
    buttons.append({"id": "what_can_i_ask", "title": labels["what_can_i_ask"]})

    # Max 3 buttons
    return buttons[:3]


def detect_language_from_phone(phone: str) -> str:
    """
    Detect preferred language based on phone number prefix.

    Logic:
    - +40 (Romania) -> "ro"
    - Everything else -> "en_US"

    Returns Meta language code for templates.
    """
    if not phone:
        return "en_US"

    clean = phone.replace(" ", "").replace("-", "").lstrip("+")

    # Romanian numbers get Romanian
    if clean.startswith("40"):
        return "ro"

    # Everything else gets English (US)
    return "en_US"


def send_template_message(
    wa_id: str,
    template_name: str,
    language_code: str,
    parameters: List[str],
    hotel=None,
) -> bool:
    """
    Send a WhatsApp Template Message (for business-initiated conversations).

    Template messages are pre-approved by Meta and required when:
    - The business initiates contact (no prior message from user)
    - The 24-hour conversation window has expired

    Args:
        wa_id: Recipient WhatsApp ID (phone number)
        template_name: Name of approved template in Meta (e.g., "welcome_guest")
        language_code: Language code (e.g., "ro", "en")
        parameters: List of values for {{1}}, {{2}}, etc. in order
        hotel: Hotel object for credentials

    Returns:
        bool: True if sent successfully, False otherwise

    Example:
        send_template_message(
            wa_id="+40754564716",
            template_name="welcome_guest",
            language_code="ro",
            parameters=["AI Hotel", "105"],  # {{1}}=hotel, {{2}}=room
            hotel=hotel
        )
    """
    token, phone_number_id, source = _get_whatsapp_credentials(hotel)

    if not token or not phone_number_id:
        logger.warning("Template message SKIPPED - missing credentials!")
        return False

    # Build parameters for template body
    body_parameters = [{"type": "text", "text": str(param)} for param in parameters]

    url = f"https://graph.facebook.com/v22.0/{phone_number_id}/messages"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    payload = {
        "messaging_product": "whatsapp",
        "to": wa_id,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language_code},
            "components": (
                [{"type": "body", "parameters": body_parameters}] if body_parameters else []
            ),
        },
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        logger.info(
            "Template message '%s' sent to %s (lang=%s, source=%s)",
            template_name,
            wa_id,
            language_code,
            source,
        )
        return True
    except Exception as e:
        logger.error("Template send error to %s: %s", wa_id, e)
        if hasattr(e, "response") and e.response is not None:
            logger.error("   Response: %s", e.response.text)
        return False


# Legacy - kept for backwards compatibility
WELCOME_BUTTONS = {
    "en": [
        {"id": "room_service", "title": "Room Service"},
        {"id": "housekeeping", "title": "Housekeeping"},
        {"id": "what_can_i_ask", "title": "What can I ask?"},
    ],
    "ro": [
        {"id": "room_service", "title": "Room Service"},
        {"id": "housekeeping", "title": "Curățenie"},
        {"id": "what_can_i_ask", "title": "Ce pot întreba?"},
    ],
    "th": [
        {"id": "room_service", "title": "รูมเซอร์วิส"},
        {"id": "housekeeping", "title": "แม่บ้าน"},
        {"id": "what_can_i_ask", "title": "ถามอะไรได้บ้าง?"},
    ],
}
