import logging

from app.models import Hotel, Task, TaskType
from app.services.messaging.factory import get_message_provider
from app.services.whatsapp_client import send_staff_alert

logger = logging.getLogger("hotelbot.staff")


ALERT_TASK_TYPES = {
    TaskType.LOST_AND_FOUND,
    TaskType.MAINTENANCE,
}


def notify_new_task(task: Task, hotel: Hotel) -> None:
    """
    Send a staff alert if configured. Currently logs or calls WhatsApp stub.
    """
    if not hotel.staff_alert_phone:
        return
    should_alert = False
    priority = getattr(task, "priority", "NORMAL")
    if priority in ("URGENT", "CRITICAL"):
        should_alert = True
    if task.type in ALERT_TASK_TYPES:
        should_alert = True
    if not should_alert:
        return

    # Different emoji based on priority
    emoji = "🔔"
    if priority == "CRITICAL":
        emoji = "🚨🆘"
    elif priority == "URGENT":
        emoji = "⚠️"

    summary = (
        task.staff_summary
        or f"Task {task.id} ({task.type.value if hasattr(task.type, 'value') else task.type})"
    )
    text = f"{emoji} Task nou – {summary} (Hotel {hotel.name})"
    try:
        # Use provider factory for multi-provider support (Meta/Twilio)
        provider = get_message_provider(hotel)
        success = provider.send_text(phone_number=hotel.staff_alert_phone, message=text)
        if success:
            logger.info(
                "Sent staff alert via %s to %s: %s",
                provider.provider_name,
                hotel.staff_alert_phone,
                text,
            )
        else:
            logger.warning(
                "Failed to send staff alert via %s to %s",
                provider.provider_name,
                hotel.staff_alert_phone,
            )
    except Exception as exc:
        logger.warning("Failed to send staff alert: %s", exc)
        # Fallback to old method if provider fails
        try:
            provider_type = (hotel.settings or {}).get("messaging_provider", "meta")
            if provider_type != "line":
                send_staff_alert(hotel.staff_alert_phone, text, hotel=hotel)
        except Exception as exc2:
            logger.warning("Staff alert fallback failed: %s", exc2)
