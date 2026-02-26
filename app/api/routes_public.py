from html import escape
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr, constr

from app.api.routes_auth import _send_email
from app.core.config import get_settings
from app.core.logging import logger
from app.core.security import rate_limit

router = APIRouter(prefix="/api", tags=["public"])
settings = get_settings()


class ContactRequest(BaseModel):
    name: constr(strip_whitespace=True, min_length=1, max_length=100)
    hotel_name: constr(strip_whitespace=True, min_length=1, max_length=200)
    email: EmailStr
    phone: Optional[constr(strip_whitespace=True, min_length=1, max_length=50)] = None


@router.post("/contact")
def submit_contact(payload: ContactRequest, request: Request):
    client_host = request.client.host if request.client else "unknown"
    rate_limit(f"contact:{client_host}", limit=5, window_seconds=3600)

    if not settings.resend_api_key:
        logger.warning("Contact email skipped; RESEND_API_KEY missing")
        raise HTTPException(status_code=503, detail="Email service unavailable.")

    contact_email = getattr(settings, "contact_email", None) or "contact@yourdomain.com"
    subject_hotel = " ".join(payload.hotel_name.split())
    subject = f"New Lead from Website: {subject_hotel}"

    safe_name = escape(payload.name)
    safe_email = escape(payload.email)
    safe_phone = escape(payload.phone) if payload.phone else "N/A"
    safe_hotel = escape(payload.hotel_name)

    body = (
        "<p><strong>New website lead</strong></p>"
        f"<p><strong>Name:</strong> {safe_name}<br>"
        f"<strong>Email:</strong> {safe_email}<br>"
        f"<strong>Phone:</strong> {safe_phone}<br>"
        f"<strong>Hotel:</strong> {safe_hotel}</p>"
    )

    _send_email(contact_email, subject, body)
    logger.info("Contact lead submitted from %s for %s", client_host, payload.email)
    return {"success": True}
