import requests

from app.core.config import get_settings


def setup_line_webhook(
    hotel_id: int, channel_access_token: str, base_url: str | None = None
) -> tuple[bool, str | None]:
    """
    Configure LINE webhook endpoint for a hotel.

    Args:
        hotel_id: Target hotel id (used to build webhook URL)
        channel_access_token: LINE channel access token
        base_url: Optional base URL; falls back to PUBLIC_API_BASE_URL or empty

    Returns:
        (success: bool, warning_message: str|None)
    """
    settings = get_settings()
    api_base = base_url or settings.public_api_base_url or ""
    if not api_base:
        return False, "Missing PUBLIC_API_BASE_URL for webhook URL"

    webhook_url = f"{api_base.rstrip('/')}/webhook/line/{hotel_id}"
    try:
        resp = requests.put(
            "https://api.line.me/v2/bot/channel/webhook/endpoint",
            headers={
                "Authorization": f"Bearer {channel_access_token}",
                "Content-Type": "application/json",
            },
            json={"endpoint": webhook_url},
            timeout=10,
        )
        if resp.status_code >= 300:
            return False, f"LINE webhook not set: {resp.status_code} {resp.text}"
    except Exception as exc:
        return False, f"LINE webhook not set: {exc}"
    return True, None
