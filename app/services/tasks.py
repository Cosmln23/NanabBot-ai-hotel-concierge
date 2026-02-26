import logging
from typing import Dict, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Hotel, Task, TaskStatus, TaskType
from app.services.analytics import log_task_created
from app.services.llm_client import LLMClient
from app.services.staff_notifier import notify_new_task

settings = get_settings()
logger = logging.getLogger("hotelbot.tasks")

TASK_ACK_TEXT: Dict[TaskType, str] = {
    TaskType.HOUSEKEEPING: "We have notified housekeeping and will follow up shortly.",
    TaskType.MAINTENANCE: "Maintenance has been alerted. We'll keep you posted.",
    TaskType.LOST_AND_FOUND: "We'll check with the team about your item and update you soon.",
    TaskType.FOOD_BEVERAGE: "Your order has been sent to our kitchen/bar. We'll deliver it soon.",
    TaskType.OTHER: "We've logged your request and will update you soon.",
}

PRIORITY_DEFAULT = "NORMAL"


def build_staff_summary_for_task(
    llm_client: LLMClient,
    hotel: Hotel,
    staff_language: str,
    user_message_text: str,
    intent: str,
    room_number: Optional[str],
) -> str:
    if not llm_client.api_key or not llm_client.client:
        base = user_message_text or intent
        if room_number:
            # Use localized room prefix
            room_labels = {"ro": "Camera", "th": "ห้อง", "en": "Room"}
            room_label = room_labels.get(staff_language, "Room")
            return f"{room_label} {room_number}: {base}"
        return base[:200]

    # Map language codes to full language names for LLM understanding
    LANGUAGE_NAMES = {
        "th": "Thai (ภาษาไทย)",
        "en": "English",
        "ro": "Romanian",
        "es": "Spanish",
        "fr": "French",
        "de": "German",
        "it": "Italian",
        "pt": "Portuguese",
        "pl": "Polish",
        "nl": "Dutch",
        "ja": "Japanese",
        "ko": "Korean",
        "zh": "Chinese",
        "ar": "Arabic",
        "ru": "Russian",
        "vi": "Vietnamese",
    }
    lang_full_name = LANGUAGE_NAMES.get(staff_language, staff_language or "English")

    # UPGRADE: Inject hotel products/menu context for detailed food order summaries
    products_context = ""
    if hotel.settings:
        hotel_products = hotel.settings.get("hotel_products_text", "")
        if hotel_products:
            products_context = f"\n\n=== HOTEL MENU/PRODUCTS ===\n{hotel_products}\n"

    system_prompt = (
        "ROLE: You are a professional hotel translator. You receive guest requests in ANY language and produce a concise summary for staff in the specified staff language.\n"
        "CONTEXT: Hospitality only (food, drinks, amenities, housekeeping, maintenance, lost & found). Resolve ambiguities accordingly.\n"
        "CRITICAL TRANSLATION RULES:\n"
        "1) Context is always HOTEL & HOSPITALITY.\n"
        "2) Interpret ambiguous words as hotel items (food, drinks, amenities). Example: 'Ape' in Romanian = Water (not apples). 'Vin' = Wine (not to come).\n"
        "3) Output: very short, operational, no pleasantries. Include room number if provided. Use staff language = {lang}.\n"
        "4) CRITICAL: If the guest request mentions items from the HOTEL MENU/PRODUCTS list below, you MUST specify the EXACT item name and quantity in your summary. Do NOT use generic terms like 'something', 'items', or 'ceva'.\n"
        "{products}"
    ).format(lang=lang_full_name, products=products_context)
    user_prompt = (
        f"Intent: {intent}. Room: {room_number or 'unknown'}. Guest said: {user_message_text}"
    )
    try:
        resp = llm_client.client.chat.completions.create(
            model=llm_client.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=80,
            timeout=llm_client.timeout,
        )
        text = resp.choices[0].message.content or ""
        return text.strip()[:500] or user_prompt[:200]
    except Exception as e:
        logger.warning(
            f"LLM staff_summary translation failed: {type(e).__name__}: {str(e)[:100]} - falling back to raw text"
        )
        base = user_message_text or intent
        if room_number:
            # Use localized room prefix
            room_labels = {"ro": "Camera", "th": "ห้อง", "en": "Room"}
            room_label = room_labels.get(staff_language, "Room")
            return f"{room_label} {room_number}: {base}"
        return base[:200]


def create_task_entry(
    db: Session,
    hotel_id: int,
    stay_id: Optional[int],
    task_type: TaskType,
    payload: Optional[dict] = None,
    *,
    hotel: Optional[Hotel] = None,
    user_message_text: Optional[str] = None,
    room_number: Optional[str] = None,
    staff_language: Optional[str] = None,
    priority: Optional[str] = None,
) -> Tuple[Task, str]:
    task = Task(
        hotel_id=hotel_id,
        stay_id=stay_id,
        type=task_type,
        status=TaskStatus.OPEN,
        payload_json=payload or {},
        priority=priority or PRIORITY_DEFAULT,
    )
    if hotel:
        # Single source of truth: hotel.staff_language.
        lang = hotel.staff_language
        if not lang:
            settings_lang = None
            try:
                settings_lang = (hotel.settings or {}).get("staff_language")
            except Exception:
                settings_lang = None
            if settings_lang:
                hotel.staff_language = settings_lang
                db.add(hotel)
                lang = settings_lang
        if not lang:
            lang = staff_language or "ro"
            logger.warning(f"No staff_language in hotel, using fallback: {lang}")
        llm = LLMClient()
        task.staff_summary = build_staff_summary_for_task(
            llm_client=llm,
            hotel=hotel,
            staff_language=lang,
            user_message_text=user_message_text or "",
            intent=task_type.value,
            room_number=room_number,
        )

    db.add(task)
    db.commit()
    db.refresh(task)
    try:
        log_task_created(
            db,
            hotel_id=hotel_id,
            metadata={"stay_id": stay_id, "task_type": task_type.value},
        )
    except Exception as exc:
        logger.warning("Failed to log task creation for task %s: %s", task.id, exc)

    if hotel:
        try:
            notify_new_task(task, hotel)
        except Exception as exc:
            logger.warning("Failed to notify staff for task %s: %s", task.id, exc)

    response_text = TASK_ACK_TEXT.get(task_type, TASK_ACK_TEXT[TaskType.OTHER])
    return task, response_text
