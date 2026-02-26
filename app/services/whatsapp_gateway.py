from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class IncomingWhatsAppMessage:
    wa_id: str
    text: str
    message_id: Optional[str]
    timestamp: Optional[str]
    raw_message: Dict[str, Any]
    raw_value: Dict[str, Any]


def parse_payload(payload: Dict[str, Any]) -> Optional[IncomingWhatsAppMessage]:
    try:
        entry = payload.get("entry", [])[0]
        changes = entry.get("changes", [])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])
        if not messages:
            return None
        message_obj = messages[0]
        wa_id = message_obj.get("from") or value.get("contacts", [{}])[0].get("wa_id")

        # Extract text from different message types
        text = ""
        msg_type = message_obj.get("type", "text")

        if msg_type == "text":
            text = (message_obj.get("text") or {}).get("body") or ""
        elif msg_type == "interactive":
            # Handle button clicks - extract title from button_reply or list_reply
            interactive = message_obj.get("interactive", {})
            interactive_type = interactive.get("type", "")
            if interactive_type == "button_reply":
                text = interactive.get("button_reply", {}).get("title", "")
            elif interactive_type == "list_reply":
                text = interactive.get("list_reply", {}).get("title", "")
        elif msg_type == "button":
            # Handle Quick Reply button clicks from Template Messages
            button_data = message_obj.get("button", {})
            text = button_data.get("text", "")

        return IncomingWhatsAppMessage(
            wa_id=wa_id or "",
            text=text,
            message_id=message_obj.get("id"),
            timestamp=message_obj.get("timestamp"),
            raw_message=message_obj,
            raw_value=value,
        )
    except Exception:
        return None
