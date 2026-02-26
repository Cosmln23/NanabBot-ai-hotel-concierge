"""
Trial expiration jobs - Email notifications for trial warnings and expiration.
"""

import logging
from datetime import datetime, timedelta, timezone

import resend
from sqlalchemy import func

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.models import Hotel, StaffUser

logger = logging.getLogger("hotelbot.jobs.trial")
settings = get_settings()

# Email templates for trial warnings
TRIAL_WARNING_TEMPLATES = {
    "en": {
        "subject": "⏰ Your AI Hotel Suite trial expires tomorrow!",
        "title": "Trial Expiring Soon",
        "intro": "Your free trial for {hotel_name} expires in 24 hours.",
        "what_happens": "What happens after expiration:",
        "item_1": "Your chatbot will stop responding to guests",
        "item_2": "AI Settings and Integrations will be locked",
        "item_3": "Your conversations and tasks will remain visible",
        "cta_text": "Upgrade now to continue using AI Hotel Suite without interruption.",
        "button": "Upgrade to Basic",
        "footer": "Questions? Contact us at",
    },
}

TRIAL_EXPIRED_TEMPLATES = {
    "en": {
        "subject": "❌ Your AI Hotel Suite trial has expired",
        "title": "Trial Expired",
        "intro": "Your free trial for {hotel_name} has ended.",
        "status": "Current status:",
        "item_1": "🔴 Chatbot is DISABLED - guests receive no response",
        "item_2": "🔒 AI Settings and Integrations are locked",
        "item_3": "✓ Conversations and tasks are still visible",
        "cta_text": "Reactivate your chatbot by upgrading to Basic.",
        "button": "Upgrade Now",
        "footer": "Questions? Contact us at",
    },
}


def _send_trial_email(
    to_email: str, hotel_name: str, language: str, template: dict, login_url: str
):
    """Send trial-related email using Resend."""
    api_key = settings.resend_api_key
    if not api_key:
        logger.warning("RESEND_API_KEY missing; trial email not sent to %s", to_email)
        return False

    tpl = template.get(language, template["en"])
    contact_email = "support@yourdomain.com"

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

                <!-- Status Box -->
                <div style="background: #fafaf9; padding: 25px; border-radius: 12px; margin: 30px 0; border-left: 4px solid #1c1917;">
                    <h3 style="color: #1c1917; margin: 0 0 15px 0; font-size: 15px; font-weight: 600;">
                        {tpl.get('what_happens', tpl.get('status', ''))}
                    </h3>
                    <ul style="color: #57534e; margin: 0; padding-left: 20px; line-height: 1.8; font-size: 14px;">
                        <li>{tpl['item_1']}</li>
                        <li>{tpl['item_2']}</li>
                        <li>{tpl['item_3']}</li>
                    </ul>
                </div>

                <p style="color: #78716c; font-size: 15px; line-height: 1.6; text-align: center;">
                    {tpl['cta_text']}
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
            </div>

            <!-- Footer -->
            <div style="text-align: center; margin-top: 30px;">
                <p style="color: #a8a29e; font-size: 13px; margin-bottom: 10px;">
                    {tpl['footer']} <a href="mailto:{contact_email}" style="color: #1c1917;">{contact_email}</a>
                </p>
            </div>
        </div>
    </body>
    </html>
    """

    try:
        resend.api_key = api_key
        resend.Emails.send(
            {
                "from": settings.email_from_address,
                "to": [to_email],
                "subject": tpl["subject"],
                "html": html_body,
            }
        )
        logger.info(f"Trial email sent to {to_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send trial email to {to_email}: {e}")
        return False


def check_trial_expirations():
    """
    Scheduled job to check trial expirations.
    Run this daily (e.g., at 09:00 local time).

    - Sends warning email 24h before expiration
    - Sends expired email when trial expires
    """
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        _tomorrow = now + timedelta(hours=24)  # Reserved for future filtering

        # Find hotels with FREE tier trial
        hotels = (
            db.query(Hotel)
            .filter(
                Hotel.subscription_tier == "free",
                Hotel.trial_ends_at.isnot(None),
            )
            .all()
        )

        for hotel in hotels:
            trial_ends = hotel.trial_ends_at
            if trial_ends.tzinfo is None:
                trial_ends = trial_ends.replace(tzinfo=timezone.utc)

            # Get admin user email (case-insensitive role check)
            admin = (
                db.query(StaffUser)
                .filter(
                    StaffUser.hotel_id == hotel.id,
                    func.upper(StaffUser.role) == "ADMIN",
                    StaffUser.is_active == True,
                )
                .first()
            )

            if not admin:
                continue

            language = hotel.interface_language or "en"
            base_url = settings.public_api_base_url or "http://localhost:8000"
            login_url = f"{base_url}/upgrade"

            # Check if expiring in next 24 hours (and not already expired)
            hours_until_expiry = (trial_ends - now).total_seconds() / 3600

            if 0 < hours_until_expiry <= 24:
                # Send warning email (24h before)
                logger.info(
                    f"[BILLING] Hotel {hotel.id} trial expires in {hours_until_expiry:.1f}h - sending warning email"
                )
                _send_trial_email(
                    to_email=admin.email,
                    hotel_name=hotel.name,
                    language=language,
                    template=TRIAL_WARNING_TEMPLATES,
                    login_url=login_url,
                )
            elif hours_until_expiry <= 0 and hours_until_expiry > -24:
                # Just expired (within last 24h) - send expired email AND disable chatbot
                logger.info(
                    f"[BILLING] Hotel {hotel.id} trial expired {abs(hours_until_expiry):.1f}h ago - "
                    f"disabling chatbot and sending expired email"
                )

                # CRITICAL: Disable chatbot and ensure tier is free
                hotel.subscription_tier = "free"
                hotel.is_active = False  # DISABLE CHATBOT
                hotel.trial_ends_at = None  # Clear trial date to prevent repeated processing
                db.add(hotel)
                db.commit()

                logger.info(f"[BILLING] Hotel {hotel.id} DISABLED after trial expiration")

                _send_trial_email(
                    to_email=admin.email,
                    hotel_name=hotel.name,
                    language=language,
                    template=TRIAL_EXPIRED_TEMPLATES,
                    login_url=login_url,
                )

            elif hours_until_expiry <= -24:
                # Expired more than 24h ago but somehow still has trial_ends_at set
                # Clean up - disable and clear trial
                if hotel.is_active:
                    logger.warning(
                        f"[BILLING] Hotel {hotel.id} trial expired {abs(hours_until_expiry):.1f}h ago "
                        f"but still active - fixing..."
                    )
                    hotel.subscription_tier = "free"
                    hotel.is_active = False
                    hotel.trial_ends_at = None
                    db.add(hotel)
                    db.commit()
                    logger.info(f"[BILLING] Hotel {hotel.id} DISABLED (late cleanup)")

    except Exception as e:
        logger.error(f"Error in check_trial_expirations: {e}")
    finally:
        db.close()
