from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Hotel, HotelAIProfile

DEFAULT_BOT_NAME = "AI Hotel Suite Assistant"
DEFAULT_TONE = "friendly"
DEFAULT_USE_EMOJIS = True
DEFAULT_MAX_SENTENCES = 2


@dataclass
class AIProfile:
    hotel: Hotel
    bot_name: str
    tone: str
    use_emojis: bool
    max_reply_sentences: int
    primary_language: Optional[str]
    reply_in_guest_language: bool
    wifi_ssid: str
    wifi_password: str
    breakfast_hours: str
    parking_info: str
    late_checkout_policy: str
    custom_instructions: str


def get_ai_profile_for_hotel(db: Session, hotel_id: int) -> AIProfile:
    hotel = db.query(Hotel).filter(Hotel.id == hotel_id).first()
    if not hotel:
        raise ValueError(f"Hotel {hotel_id} not found")
    ai = db.query(HotelAIProfile).filter(HotelAIProfile.hotel_id == hotel_id).first()

    bot_name = ai.bot_name if ai and ai.bot_name else DEFAULT_BOT_NAME
    tone = ai.tone if ai and ai.tone else DEFAULT_TONE
    use_emojis = ai.use_emojis if ai is not None else DEFAULT_USE_EMOJIS
    max_sentences = (
        ai.max_reply_sentences if ai and ai.max_reply_sentences else DEFAULT_MAX_SENTENCES
    )
    primary_language = ai.primary_language if ai and ai.primary_language else None
    reply_in_guest_language = ai.reply_in_guest_language if ai is not None else True
    return AIProfile(
        hotel=hotel,
        bot_name=bot_name,
        tone=tone,
        use_emojis=use_emojis,
        max_reply_sentences=max_sentences,
        primary_language=primary_language,
        reply_in_guest_language=reply_in_guest_language,
        wifi_ssid=ai.wifi_ssid if ai and ai.wifi_ssid else "",
        wifi_password=ai.wifi_password if ai and ai.wifi_password else "",
        breakfast_hours=ai.breakfast_hours if ai and ai.breakfast_hours else "",
        parking_info=ai.parking_info if ai and ai.parking_info else "",
        late_checkout_policy=(ai.late_checkout_policy if ai and ai.late_checkout_policy else ""),
        custom_instructions=(ai.custom_instructions if ai and ai.custom_instructions else ""),
    )
