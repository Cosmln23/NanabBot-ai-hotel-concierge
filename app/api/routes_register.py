"""
Self-registration routes for hotel trial signup.
Creates a hotel with FREE trial (7 days) and admin user.
"""

import html
import logging
import secrets
from datetime import datetime, timedelta, timezone

import resend
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, EmailStr, constr
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.security import _redis as redis_client
from app.core.security import create_access_token, hash_password, rate_limit
from app.models import Hotel, HotelAIProfile, StaffUser

router = APIRouter(tags=["register"])
templates = Jinja2Templates(directory="templates")
logger = logging.getLogger("hotelbot")

# Country to language mapping
COUNTRY_LANGUAGE_MAP = {
    "TH": "en",  # Thailand -> EN
    "RO": "en",  # Romania -> EN
}

# Welcome email templates - platform specific with step-by-step instructions
WELCOME_EMAIL_TEMPLATES = {
    "en": {
        "subject": "Welcome to AI Hotel Suite! Your Hotel Bot is Ready",
        "title": "Welcome to AI Hotel Suite!",
        "intro": "Your hotel <strong>{hotel_name}</strong> is now active.",
        "platform": "WhatsApp / LINE",
        "how_title": "How it works:",
        "step_1": "Go to Dashboard → Generate QR Code",
        "step_2": "Print QR Code → Place in rooms or reception",
        "step_3": "Guests scan → Bot responds automatically 24/7",
        "benefit": "Your AI assistant answers guest questions about WiFi, check-out, restaurant, room service and more - instantly! See the Help section in Dashboard for more details.",
        "button": "Go to Dashboard",
        "trial_note": "Free trial • Ends {trial_date}",
        "questions": "Questions?",
        "footer": "Thank you for choosing AI Hotel Suite!",
    }
}


def _send_welcome_email(
    to_email: str, hotel_name: str, language: str, trial_date: str, login_url: str
):
    """Send simple welcome email after registration."""
    # Escape hotel_name to prevent HTML injection in email
    hotel_name = html.escape(hotel_name)
    settings = get_settings()
    api_key = settings.resend_api_key

    if not api_key:
        logger.warning("RESEND_API_KEY missing; welcome email not sent to %s", to_email)
        return

    # Get template for language (fallback to English)
    tpl = WELCOME_EMAIL_TEMPLATES.get(language, WELCOME_EMAIL_TEMPLATES["en"])

    # Contact email
    contact_email = "contact@yourdomain.com"

    # Build HTML email
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    </head>
    <body style="margin:0; padding:0; font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; background-color: #fafaf9;">
        <div style="max-width: 600px; margin: 0 auto; padding: 40px 20px;">
            <!-- Header -->
            <div style="text-align: center; margin-bottom: 30px;">
                <img src="https://yourdomain.com/static/logo.png" alt="AI Hotel Suite" style="height: 48px; width: auto; border-radius: 10px;">
                <p style="color: #1c1917; font-size: 20px; font-weight: 600; margin: 12px 0 0 0;">AI Hotel Suite</p>
            </div>

            <!-- Main Card -->
            <div style="background: white; border-radius: 16px; padding: 40px; border: 1px solid #e7e5e4;">
                <h1 style="color: #1c1917; margin: 0 0 20px 0; font-size: 24px; text-align: center; font-weight: 600;">
                    {tpl['title']}
                </h1>

                <p style="color: #78716c; font-size: 16px; line-height: 1.6; text-align: center;">
                    {tpl['intro'].format(hotel_name=hotel_name)}
                </p>

                <!-- Platform Badge -->
                <div style="text-align: center; margin: 20px 0;">
                    <span style="display: inline-block; background: #f5f5f4; color: #1c1917; padding: 8px 16px; border-radius: 20px; font-size: 14px; font-weight: 500; border: 1px solid #e7e5e4;">
                        {tpl['platform']}
                    </span>
                </div>

                <!-- How it works -->
                <div style="background: #fafaf9; padding: 25px; border-radius: 12px; margin: 30px 0;">
                    <h3 style="color: #1c1917; margin: 0 0 20px 0; font-size: 15px; font-weight: 600;">
                        {tpl['how_title']}
                    </h3>
                    <div style="color: #57534e; font-size: 14px; line-height: 2;">
                        <div style="margin-bottom: 8px;">1. {tpl['step_1']}</div>
                        <div style="margin-bottom: 8px;">2. {tpl['step_2']}</div>
                        <div>3. {tpl['step_3']}</div>
                    </div>
                </div>

                <!-- Benefit -->
                <p style="color: #78716c; font-size: 14px; line-height: 1.6; text-align: center; margin: 0 0 20px 0;">
                    {tpl['benefit']}
                </p>

                <!-- CTA Button -->
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{login_url}"
                       style="display: inline-block; background: #1c1917; color: #fafaf9;
                              padding: 14px 36px; border-radius: 10px; text-decoration: none;
                              font-weight: 600; font-size: 15px;">
                        {tpl['button']} →
                    </a>
                </div>

                <!-- Trial Note -->
                <p style="color: #57534e; font-size: 14px; text-align: center; margin: 20px 0 0 0;
                          background: #f5f5f4; padding: 12px; border-radius: 8px; border: 1px solid #e7e5e4;">
                    {tpl['trial_note'].format(trial_date=trial_date)}
                </p>
            </div>

            <!-- Footer -->
            <div style="text-align: center; margin-top: 30px;">
                <p style="color: #a8a29e; font-size: 13px; margin-bottom: 10px;">
                    {tpl['questions']} <a href="mailto:{contact_email}" style="color: #1c1917;">{contact_email}</a>
                </p>
                <p style="color: #a8a29e; font-size: 13px;">
                    {tpl['footer']}
                </p>
            </div>
        </div>
    </body>
    </html>
    """

    resend.api_key = api_key
    try:
        resend.Emails.send(
            {
                "from": settings.email_from_address,
                "to": [to_email],
                "subject": tpl["subject"],
                "html": html_body,
            }
        )
        logger.info(f"Welcome email sent to {to_email}")
    except Exception as e:
        logger.error(f"Failed to send welcome email to {to_email}: {e}")


class RegisterRequest(BaseModel):
    email: EmailStr
    password: constr(min_length=6)
    hotel_name: constr(strip_whitespace=True, min_length=2)
    country: constr(strip_whitespace=True, min_length=2, max_length=2)
    accepted_terms: bool = False


class RegisterResponse(BaseModel):
    success: bool
    hotel_id: int
    access_token: str
    message: str


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Serve the registration page."""
    return templates.TemplateResponse("register.html", {"request": request})


@router.post("/api/register", response_model=RegisterResponse)
def register_hotel(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    """
    Self-registration endpoint for new hotels.
    Creates a hotel with FREE trial and admin user.
    """
    # Rate limit: max 5 registrations per hour per IP
    try:
        rate_limit(f"register:{request.client.host}", limit=5, window_seconds=3600)
    except HTTPException:
        logger.warning(f"Rate limit exceeded for registration from {request.client.host}")
        raise

    if not payload.accepted_terms:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You must accept the Terms of Service and Data Processing Agreement.",
        )

    norm_email = payload.email.strip().lower()
    norm_name = payload.hotel_name.strip()
    country = payload.country.upper()

    # Check if email already exists
    existing_staff = db.query(StaffUser).filter(func.lower(StaffUser.email) == norm_email).first()
    if existing_staff:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists. Please login instead.",
        )

    # Hotel name is NOT unique - multiple hotels can have same name in different locations
    # Uniqueness is guaranteed by admin email (which is globally unique)

    # Determine interface language based on country
    interface_language = COUNTRY_LANGUAGE_MAP.get(country, "en")

    # Determine messaging provider based on country
    # Thailand → LINE, Romania/Europe → WhatsApp (meta)
    messaging_provider = "line" if country == "TH" else "meta"

    # Create hotel with FREE trial
    trial_ends_at = datetime.now(timezone.utc) + timedelta(days=7)

    hotel = Hotel(
        name=norm_name,
        timezone="UTC",  # Default, can be changed later
        is_active=True,
        settings={
            "messaging_provider": messaging_provider,
            # Service toggles - all FALSE by default (must be explicitly enabled)
            "allow_housekeeping": False,
            "allow_food_beverage": False,
            # Housekeeping sub-options - all FALSE by default
            "hk_room_cleaning": False,
            "hk_towels_toiletries": False,
            "hk_bed_linen": False,
            "hk_laundry": False,
            "hk_extra_amenities": False,
        },
        interface_language=interface_language,
        staff_language=interface_language,  # Task summaries in same language as interface
        language_locked=False,
        country=country,
        subscription_tier="free",
        trial_ends_at=trial_ends_at,
    )
    db.add(hotel)
    db.flush()  # Get hotel.id

    # Create admin user
    staff = StaffUser(
        hotel_id=hotel.id,
        name=norm_name,  # Use hotel name as admin name initially
        role="ADMIN",
        email=norm_email,
        password_hash=hash_password(payload.password),
        is_active=True,
        must_change_password=False,  # They just set their password
    )
    db.add(staff)

    # Create default AI profile
    ai_profile = HotelAIProfile(
        hotel_id=hotel.id,
        bot_name="Hotel Assistant",
        tone="friendly",
        use_emojis=True,
        max_reply_sentences=2,
        primary_language=interface_language,
        reply_in_guest_language=True,
    )
    db.add(ai_profile)

    db.commit()
    db.refresh(hotel)
    db.refresh(staff)

    logger.info(
        f"New hotel registered: {hotel.name} (ID: {hotel.id}) by {norm_email} from {country}"
    )

    # Create access token for immediate login
    access_token = create_access_token(user_id=staff.id, email=staff.email)

    # Send simple welcome email with temporary login code (not JWT in URL)
    base_url = str(request.base_url).rstrip("/")
    if redis_client:
        login_code = secrets.token_urlsafe(32)
        redis_client.setex(f"instant_login:{login_code}", 3600, str(staff.id))
        login_url = f"{base_url}/ui/admin/login?code={login_code}"
    else:
        # Redis unavailable — fall back to plain login page (no auto-login)
        logger.warning(
            "Redis unavailable — welcome email will link to login page without auto-login"
        )
        login_url = f"{base_url}/ui/admin/login"
    _send_welcome_email(
        to_email=norm_email,
        hotel_name=norm_name,
        language=interface_language,
        trial_date=trial_ends_at.strftime("%Y-%m-%d"),
        login_url=login_url,
    )

    return RegisterResponse(
        success=True,
        hotel_id=hotel.id,
        access_token=access_token,
        message=f"Welcome! Your free trial starts now. Trial ends on {trial_ends_at.strftime('%Y-%m-%d')}.",
    )
