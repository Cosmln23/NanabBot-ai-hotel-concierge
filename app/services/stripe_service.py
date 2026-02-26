"""
Stripe payment integration service.
Handles Checkout sessions for Basic plan subscriptions.
Supports multi-currency (EUR, THB, RON) and locale-based checkout.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Tuple

import resend
import stripe
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Hotel, StaffUser
from app.models.models import StripeWebhookEvent

logger = logging.getLogger("hotelbot.stripe")
settings = get_settings()

# Initialize Stripe
if settings.stripe_secret_key:
    stripe.api_key = settings.stripe_secret_key

# Country to Price ID mapping
COUNTRY_PRICE_MAP = {
    "TH": "stripe_basic_price_id_thb",  # Thai Baht
    "RO": "stripe_basic_price_id_ron",  # Romanian Lei
}

# Country/Language to Stripe locale mapping

# Country to PRO Price ID mapping
COUNTRY_PRO_PRICE_MAP = {
    # "TH": "stripe_pro_price_id_thb",  # Thai Baht - DISABLED: PMS not ready for LINE
    "RO": "stripe_pro_price_id_ron",  # Romanian Lei
}
# Language to PRO Price ID mapping
LANGUAGE_PRO_PRICE_MAP = {}
LOCALE_MAP = {
    "en": "en",  # English
}

# ============================================================================
# EMAIL TEMPLATES FOR SUBSCRIPTION NOTIFICATIONS
# ============================================================================

RENEWAL_REMINDER_TEMPLATES = {
    "en": {
        "subject": "Your AI Hotel Suite subscription renews in 3 days",
        "title": "Subscription Renewal Reminder",
        "intro": "Your subscription for <strong>{hotel_name}</strong> will automatically renew on <strong>{renewal_date}</strong>.",
        "amount_info": "Amount to be charged:",
        "what_happens": "What to expect:",
        "item_1": "✓ Your subscription will renew automatically",
        "item_2": "✓ The payment method on file will be charged",
        "item_3": "✓ Your chatbot will continue working without interruption",
        "cta_text": "Need to update your payment method or cancel?",
        "button": "Manage Subscription",
        "footer": "Questions? Contact us at",
        "footer_thanks": "Thank you for choosing AI Hotel Suite!",
    },
}

PAYMENT_FAILED_TEMPLATES = {
    "en": {
        "subject": "Action Required: Payment failed for your AI Hotel Suite subscription",
        "title": "Payment Failed",
        "intro": "We couldn't process the payment for <strong>{hotel_name}</strong>.",
        "what_happened": "What happened:",
        "item_1": "• Your payment method was declined",
        "item_2": "• We will retry the payment automatically ({attempts_info})",
        "item_3": "• If payment continues to fail, your subscription will be canceled",
        "warning": "If the payment is not resolved, your chatbot will be disabled and guests will not receive responses.",
        "cta_text": "Please update your payment method to avoid service interruption.",
        "button": "Update Payment Method",
        "footer": "Questions? Contact us at",
        "footer_thanks": "Thank you for choosing AI Hotel Suite!",
    },
}

SUBSCRIPTION_CANCELED_TEMPLATES = {
    "en": {
        "subject": "Your AI Hotel Suite subscription has been canceled",
        "title": "Subscription Canceled",
        "intro": "Your subscription for <strong>{hotel_name}</strong> has been canceled.",
        "status": "What this means:",
        "item_1": "• Your chatbot is now DISABLED - guests will not receive responses",
        "item_2": "• AI Settings and Integrations are locked",
        "item_3": "• Your conversations and data are preserved",
        "cta_text": "Miss your AI concierge? You can reactivate anytime.",
        "button": "Reactivate Subscription",
        "footer": "Questions? Contact us at",
        "footer_thanks": "Thank you for choosing AI Hotel Suite!",
    },
}


def get_price_id_for_country(country: str) -> str:
    """Get the appropriate Stripe Price ID based on hotel country."""
    price_attr = COUNTRY_PRICE_MAP.get(country)
    if price_attr:
        price_id = getattr(settings, price_attr, None)
        if price_id:
            return price_id
    # Fallback to default EUR price
    return settings.stripe_basic_price_id


def get_pro_price_id_for_country(country: str) -> str:
    """Get the appropriate Stripe PRO Price ID based on hotel country."""
    price_attr = COUNTRY_PRO_PRICE_MAP.get(country)
    if price_attr:
        price_id = getattr(settings, price_attr, None)
        if price_id:
            return price_id
    # Fallback to default EUR PRO price
    return settings.stripe_pro_price_id


def get_pro_price_id_for_language(language: str, country: str = "") -> str:
    """Get the appropriate Stripe PRO Price ID based on language (priority) or country (fallback)."""
    # First try language
    price_attr = LANGUAGE_PRO_PRICE_MAP.get(language)
    if price_attr:
        price_id = getattr(settings, price_attr, None)
        if price_id:
            return price_id
    # Fallback to country
    if country:
        return get_pro_price_id_for_country(country)
    # Final fallback to default EUR PRO price
    return settings.stripe_pro_price_id


def get_locale_for_language(language: str) -> str:
    """Get Stripe locale code from interface language."""
    return LOCALE_MAP.get(language, "en")


def _get_admin_email(hotel_id: int, db: Session) -> Optional[str]:
    """Get the admin user's email for a hotel."""
    from sqlalchemy import func

    admin = (
        db.query(StaffUser)
        .filter(
            StaffUser.hotel_id == hotel_id,
            func.upper(StaffUser.role) == "ADMIN",
            StaffUser.is_active == True,
        )
        .first()
    )
    return admin.email if admin else None


def _send_subscription_email(
    to_email: str,
    hotel_name: str,
    language: str,
    template: dict,
    portal_url: str = "",
    amount: str = "",
    renewal_date: str = "",
    attempts_info: str = "",
) -> bool:
    """
    Send subscription-related email using Resend.

    Args:
        to_email: Recipient email
        hotel_name: Hotel name for personalization
        language: Language code (en, ro, th)
        template: Template dict (RENEWAL_REMINDER_TEMPLATES, etc.)
        portal_url: Stripe customer portal URL
        amount: Formatted amount string (e.g., "€9.99")
        renewal_date: Formatted date string
        attempts_info: Payment retry info (e.g., "attempt 1 of 3")
    """
    api_key = settings.resend_api_key
    if not api_key:
        logger.warning("RESEND_API_KEY missing; subscription email not sent to %s", to_email)
        return False

    tpl = template.get(language, template["en"])
    contact_email = "support@yourdomain.com"

    # Determine button color based on template type
    is_warning = "warning" in tpl or "status" in tpl
    button_color = "#dc2626" if is_warning else "#1c1917"  # Red for warnings, stone-dark for info
    box_bg = "#fef2f2" if is_warning else "#fafaf9"  # Red-ish or stone background
    box_border = "#dc2626" if is_warning else "#1c1917"

    # Build the status/info box content
    info_items = f"""
        <li>{tpl.get('item_1', '').format(attempts_info=attempts_info)}</li>
        <li>{tpl.get('item_2', '').format(attempts_info=attempts_info)}</li>
        <li>{tpl.get('item_3', '').format(attempts_info=attempts_info)}</li>
    """

    # Add amount info for renewal reminders
    amount_section = ""
    if amount and "amount_info" in tpl:
        amount_section = f"""
        <div style="text-align: center; margin: 25px 0; background: #f5f5f4; padding: 20px; border-radius: 12px; border: 1px solid #e7e5e4;">
            <span style="color: #78716c; font-size: 14px;">{tpl['amount_info']}</span>
            <div style="font-size: 32px; font-weight: 700; color: #1c1917; margin-top: 8px;">{amount}</div>
        </div>
        """

    # Add warning box for payment failed
    warning_section = ""
    if "warning" in tpl:
        warning_section = f"""
        <div style="background: #fef2f2; padding: 16px; border-radius: 10px; margin: 20px 0; border: 1px solid #fecaca;">
            <p style="color: #991b1b; margin: 0; font-size: 14px; line-height: 1.5;">{tpl['warning']}</p>
        </div>
        """

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
                    {tpl['intro'].format(hotel_name=hotel_name, renewal_date=renewal_date)}
                </p>

                {amount_section}

                <!-- Status Box -->
                <div style="background: #fafaf9; padding: 25px; border-radius: 12px; margin: 30px 0; border-left: 4px solid {box_border};">
                    <h3 style="color: #1c1917; margin: 0 0 15px 0; font-size: 15px; font-weight: 600;">
                        {tpl.get('what_happens', tpl.get('what_happened', tpl.get('status', '')))}
                    </h3>
                    <div style="color: #57534e; font-size: 14px; line-height: 2;">
                        <div style="margin-bottom: 8px;">{tpl.get('item_1', '').format(attempts_info=attempts_info)}</div>
                        <div style="margin-bottom: 8px;">{tpl.get('item_2', '').format(attempts_info=attempts_info)}</div>
                        <div>{tpl.get('item_3', '').format(attempts_info=attempts_info)}</div>
                    </div>
                </div>

                {warning_section}

                <p style="color: #78716c; font-size: 14px; line-height: 1.6; text-align: center; margin: 0 0 20px 0;">
                    {tpl['cta_text']}
                </p>

                <!-- CTA Button -->
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{portal_url}"
                       style="display: inline-block; background: {button_color}; color: #fafaf9;
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
                <p style="color: #a8a29e; font-size: 13px;">
                    {tpl.get('footer_thanks', 'Thank you for choosing AI Hotel Suite!')}
                </p>
            </div>
        </div>
    </body>
    </html>
    """

    try:
        import httpx

        resend.api_key = api_key
        # Set a short timeout (3 seconds) to prevent webhook timeout
        # Stripe expects response within 10-30 seconds
        with httpx.Client(timeout=3.0):
            resend.Emails.send(
                {
                    "from": settings.email_from_address,
                    "to": [to_email],
                    "subject": tpl["subject"],
                    "html": html_body,
                }
            )
        logger.info(f"[BILLING] Subscription email sent to {to_email} (type: {tpl['title']})")
        return True
    except httpx.TimeoutException:
        # Email timeout - log but don't fail webhook
        logger.warning(f"[BILLING] Email timeout for {to_email} - webhook will continue")
        return False
    except Exception as e:
        # Email failed - log but don't fail webhook (non-critical)
        logger.error(f"[BILLING] Failed to send email to {to_email}: {e}")
        return False


def is_event_processed(event_id: str, db: Session) -> bool:
    """
    Check if a webhook event has already been processed (idempotency).
    Uses FOR UPDATE to prevent race conditions with concurrent webhooks.
    """
    try:
        # Use FOR UPDATE to acquire row-level lock
        existing = (
            db.query(StripeWebhookEvent)
            .filter(StripeWebhookEvent.event_id == event_id)
            .with_for_update(nowait=False)  # Wait for lock if another transaction has it
            .first()
        )
        return existing is not None
    except Exception as e:
        logger.error(f"[BILLING] Error checking if event processed: {e}")
        return False  # Assume not processed to ensure we don't skip legitimate events


def mark_event_processed(event_id: str, event_type: str, db: Session) -> None:
    """
    Mark a webhook event as processed.
    Handles IntegrityError if another transaction already marked it.
    """
    from sqlalchemy.exc import IntegrityError

    try:
        event_record = StripeWebhookEvent(event_id=event_id, event_type=event_type)
        db.add(event_record)
        db.commit()
        logger.info(f"[BILLING] Marked event as processed: {event_id} ({event_type})")
    except IntegrityError:
        # Another concurrent request already processed this event
        db.rollback()
        logger.info(f"[BILLING] Event {event_id} already marked by concurrent request")


def create_checkout_session(
    hotel_id: int,
    success_url: str,
    cancel_url: str,
    db: Session,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Create a Stripe Checkout session for Basic plan subscription.
    Automatically selects currency and locale based on hotel's country/language.

    Returns:
        Tuple of (checkout_url, error_message)
    """
    if not settings.stripe_secret_key:
        return None, "Stripe is not configured"

    if not settings.stripe_basic_price_id:
        return None, "Stripe Basic price ID not configured"

    hotel = db.query(Hotel).filter(Hotel.id == hotel_id).first()
    if not hotel:
        return None, "Hotel not found"

    # IMPORTANT: Check if hotel already has an active subscription
    if hotel.subscription_tier in ("basic", "pro"):
        logger.warning(
            f"[BILLING] Hotel {hotel_id} already has {hotel.subscription_tier} subscription"
        )
        return (
            None,
            f"Already subscribed to {hotel.subscription_tier.upper()} plan. Use customer portal to change plans.",
        )

    try:
        # Create or get Stripe customer
        customer_id = hotel.stripe_customer_id
        if not customer_id:
            customer = stripe.Customer.create(
                metadata={"hotel_id": str(hotel_id), "hotel_name": hotel.name},
            )
            customer_id = customer.id
            hotel.stripe_customer_id = customer_id
            db.add(hotel)
            db.commit()

        # Get price ID based on hotel country
        price_id = get_price_id_for_country(hotel.country or "")

        # Get locale based on hotel interface language
        locale = get_locale_for_language(hotel.interface_language or "en")

        # Create checkout session with locale
        # IMPORTANT: Include "plan": "basic" in metadata for consistency with PRO
        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[
                {
                    "price": price_id,
                    "quantity": 1,
                }
            ],
            mode="subscription",
            locale=locale,
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"hotel_id": str(hotel_id), "plan": "basic"},
            subscription_data={
                "metadata": {"hotel_id": str(hotel_id), "plan": "basic"},
            },
        )

        logger.info(
            f"[BILLING] Created BASIC checkout session for hotel {hotel_id}: {session.id} (locale={locale})"
        )
        return session.url, None

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating checkout session: {e}")
        return None, str(e)
    except Exception as e:
        logger.exception(f"Error creating checkout session: {e}")
        return None, str(e)


def create_pro_checkout_session(
    hotel_id: int,
    success_url: str,
    cancel_url: str,
    db: Session,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Create a Stripe Checkout session for PRO plan subscription.
    Automatically selects currency and locale based on hotel's country/language.

    Returns:
        Tuple of (checkout_url, error_message)
    """
    if not settings.stripe_secret_key:
        return None, "Stripe is not configured"

    if not settings.stripe_pro_price_id:
        return None, "Stripe PRO price ID not configured"

    hotel = db.query(Hotel).filter(Hotel.id == hotel_id).first()
    if not hotel:
        return None, "Hotel not found"

    # IMPORTANT: Check if hotel already has PRO subscription
    if hotel.subscription_tier == "pro":
        logger.warning(f"[BILLING] Hotel {hotel_id} already has PRO subscription")
        return (
            None,
            "Already subscribed to PRO plan. Use customer portal to manage subscription.",
        )

    try:
        # Create or get Stripe customer
        customer_id = hotel.stripe_customer_id
        if not customer_id:
            customer = stripe.Customer.create(
                metadata={"hotel_id": str(hotel_id), "hotel_name": hotel.name},
            )
            customer_id = customer.id
            hotel.stripe_customer_id = customer_id
            db.add(hotel)
            db.commit()

        # Get PRO price ID based on hotel language (priority) or country (fallback)
        price_id = get_pro_price_id_for_language(
            hotel.interface_language or "", hotel.country or ""
        )

        # Get locale based on hotel interface language
        locale = get_locale_for_language(hotel.interface_language or "en")

        # Create checkout session with locale
        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[
                {
                    "price": price_id,
                    "quantity": 1,
                }
            ],
            mode="subscription",
            locale=locale,
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"hotel_id": str(hotel_id), "plan": "pro"},
            subscription_data={
                "metadata": {"hotel_id": str(hotel_id), "plan": "pro"},
            },
        )

        logger.info(
            f"[BILLING] Created PRO checkout session for hotel {hotel_id}: {session.id} (locale={locale})"
        )
        return session.url, None

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating PRO checkout session: {e}")
        return None, str(e)
    except Exception as e:
        logger.exception(f"Error creating PRO checkout session: {e}")
        return None, str(e)


def handle_checkout_completed(session: dict, db: Session) -> bool:
    """
    Handle successful checkout completion.
    Updates hotel subscription tier to 'basic' or 'pro' based on plan metadata.

    Returns:
        True if successful, False otherwise
    """
    try:
        metadata = session.get("metadata", {})
        hotel_id = metadata.get("hotel_id")
        plan = metadata.get("plan", "basic")  # Default to basic if not specified

        if not hotel_id:
            logger.error("[BILLING] No hotel_id in checkout session metadata")
            return False

        hotel = db.query(Hotel).filter(Hotel.id == int(hotel_id)).first()
        if not hotel:
            logger.error(
                f"[BILLING] Hotel {hotel_id} not found - accepting webhook to prevent retry"
            )
            return True  # Accept webhook to prevent infinite retry

        # Get subscription ID from session
        subscription_id = session.get("subscription")

        # Determine tier based on plan metadata
        new_tier = "pro" if plan == "pro" else "basic"

        # IMPORTANT: Prevent downgrade from PRO to BASIC (simultaneous checkout protection)
        if hotel.subscription_tier == "pro" and new_tier == "basic":
            logger.warning(f"[BILLING] Preventing downgrade from PRO to BASIC for hotel {hotel_id}")
            return True  # Accept webhook but don't downgrade

        previous_tier = hotel.subscription_tier

        # Update subscription
        hotel.subscription_tier = new_tier
        hotel.trial_ends_at = None  # Clear trial end date
        hotel.is_active = True  # Ensure chatbot is active
        if subscription_id:
            hotel.stripe_subscription_id = subscription_id
        db.add(hotel)
        db.commit()

        logger.info(
            f"[BILLING] Hotel {hotel_id} upgraded from {previous_tier.upper()} to {new_tier.upper()} (subscription: {subscription_id})"
        )
        return True

    except Exception as e:
        db.rollback()  # CRITICAL: Rollback on any error
        logger.exception(f"[BILLING] Error handling checkout completed: {e}")
        return False


def handle_subscription_updated(subscription: dict, db: Session) -> bool:
    """
    Handle subscription update events (cancellation, etc.)
    Sends notification email when subscription is canceled.

    GRACE PERIOD LOGIC:
    - past_due: Don't cut access yet (Stripe is still retrying payments)
    - canceled/unpaid: Cut access (Stripe has given up on payment)
    """
    try:
        hotel_id = subscription.get("metadata", {}).get("hotel_id")
        if not hotel_id:
            logger.warning("[BILLING] No hotel_id in subscription metadata")
            return False

        hotel = db.query(Hotel).filter(Hotel.id == int(hotel_id)).first()
        if not hotel:
            logger.warning(f"[BILLING] Hotel {hotel_id} not found in subscription update")
            return True  # Accept webhook to prevent retry

        status = subscription.get("status")
        subscription_id = subscription.get("id")

        # Update subscription ID if not set
        if subscription_id and not hotel.stripe_subscription_id:
            hotel.stripe_subscription_id = subscription_id

        # GRACE PERIOD: Only downgrade on final states (canceled, unpaid)
        # past_due = Stripe is still retrying, don't cut access yet
        if status in ("canceled", "unpaid"):
            # Final states - downgrade to free and disable chatbot
            previous_tier = hotel.subscription_tier
            hotel.subscription_tier = "free"
            hotel.is_active = False  # Disable chatbot
            hotel.stripe_subscription_id = None  # Clear subscription ID
            db.add(hotel)
            db.commit()
            logger.info(
                f"[BILLING] Hotel {hotel_id} downgraded to FREE and DISABLED (subscription {status})"
            )

            # Send cancellation email
            if previous_tier != "free":
                admin_email = _get_admin_email(int(hotel_id), db)
                if admin_email:
                    portal_url = settings.public_api_base_url or "https://app.yourdomain.com"
                    portal_url = f"{portal_url}/upgrade"

                    language = hotel.interface_language or "en"
                    _send_subscription_email(
                        to_email=admin_email,
                        hotel_name=hotel.name,
                        language=language,
                        template=SUBSCRIPTION_CANCELED_TEMPLATES,
                        portal_url=portal_url,
                    )
                    logger.info(
                        f"[BILLING] Cancellation notification sent to {admin_email} for hotel {hotel_id}"
                    )

        elif status == "past_due":
            # Grace period - log but don't cut access
            # Payment failed emails are sent via invoice.payment_failed
            logger.warning(
                f"[BILLING] Hotel {hotel_id} subscription is past_due - grace period active, chatbot still enabled"
            )

        elif status == "active":
            # Subscription is active - ensure tier matches and chatbot is enabled
            plan = subscription.get("metadata", {}).get("plan", "basic")
            new_tier = "pro" if plan == "pro" else "basic"

            # Always update tier to match Stripe (handles upgrades/reactivations)
            if hotel.subscription_tier != new_tier or not hotel.is_active:
                previous_tier = hotel.subscription_tier
                hotel.subscription_tier = new_tier
                hotel.is_active = True  # Ensure chatbot is active
                db.add(hotel)
                db.commit()
                logger.info(
                    f"[BILLING] Hotel {hotel_id} subscription active: {previous_tier.upper()} -> {new_tier.upper()}"
                )

        return True

    except Exception as e:
        db.rollback()  # CRITICAL: Rollback on any error
        logger.exception(f"[BILLING] Error handling subscription update: {e}")
        return False


def handle_invoice_payment_failed(invoice: dict, db: Session) -> bool:
    """
    Handle failed invoice payment events.
    Logs the failure and sends notification email to hotel admin.

    NOTE: This does NOT cut access - grace period is active.
    Access is only cut when subscription status becomes 'canceled' or 'unpaid'.
    """
    try:
        subscription_id = invoice.get("subscription")
        customer_id = invoice.get("customer")
        attempt_count = invoice.get("attempt_count", 0)
        amount_due = invoice.get("amount_due", 0)
        currency = invoice.get("currency", "eur").upper()

        logger.warning(
            f"[BILLING] Invoice payment failed: customer={customer_id}, subscription={subscription_id}, "
            f"attempt={attempt_count}, amount={amount_due / 100:.2f} {currency}"
        )

        # Find hotel by stripe_customer_id
        hotel = db.query(Hotel).filter(Hotel.stripe_customer_id == customer_id).first()
        if not hotel:
            logger.warning(
                f"[BILLING] Hotel not found for customer {customer_id} in payment_failed"
            )
            return True  # Return True to mark event as processed

        logger.warning(
            f"[BILLING] Payment failed for hotel {hotel.id} ({hotel.name}), attempt {attempt_count} - "
            f"GRACE PERIOD ACTIVE, chatbot still enabled"
        )

        # Get admin email
        admin_email = _get_admin_email(hotel.id, db)
        if not admin_email:
            logger.warning(f"[BILLING] No admin email found for hotel {hotel.id}")
            return True

        # Format attempts info (Stripe typically retries 3-4 times)
        max_attempts = 4
        attempts_info = f"attempt {attempt_count} of {max_attempts}"

        # Generate portal URL for updating payment method
        portal_url = settings.public_api_base_url or "https://app.yourdomain.com"
        portal_url = f"{portal_url}/admin/tasks"

        # Send email notification
        language = hotel.interface_language or "en"
        _send_subscription_email(
            to_email=admin_email,
            hotel_name=hotel.name,
            language=language,
            template=PAYMENT_FAILED_TEMPLATES,
            portal_url=portal_url,
            attempts_info=attempts_info,
        )

        logger.info(
            f"[BILLING] Payment failed notification sent to {admin_email} for hotel {hotel.id}"
        )
        return True

    except Exception as e:
        db.rollback()  # CRITICAL: Rollback on any error
        logger.exception(f"[BILLING] Error handling invoice payment failed: {e}")
        return False


def handle_charge_refunded(charge: dict, db: Session) -> bool:
    """
    Handle charge refund events.
    On FULL refund, downgrade subscription to free.
    """
    try:
        customer_id = charge.get("customer")
        amount_refunded = charge.get("amount_refunded", 0)
        amount_total = charge.get("amount", 0)
        currency = charge.get("currency", "")
        refund_reason = charge.get("refund_reason", "unknown")

        logger.info(
            f"[BILLING] Charge refunded: customer={customer_id}, "
            f"refunded={amount_refunded / 100:.2f}/{amount_total / 100:.2f} {currency.upper()}"
        )

        # Find hotel by stripe_customer_id
        hotel = db.query(Hotel).filter(Hotel.stripe_customer_id == customer_id).first()
        if not hotel:
            logger.warning(f"[BILLING] Hotel not found for customer {customer_id} in refund")
            return True

        # Check if this is a FULL refund (>=90% of total to account for rounding)
        if amount_total > 0 and amount_refunded >= (amount_total * 0.9):
            previous_tier = hotel.subscription_tier

            # Full refund = downgrade to free and disable
            hotel.subscription_tier = "free"
            hotel.is_active = False
            hotel.stripe_subscription_id = None
            db.add(hotel)
            db.commit()

            logger.warning(
                f"[BILLING] FULL REFUND: Hotel {hotel.id} downgraded from {previous_tier.upper()} "
                f"to FREE and DISABLED (refund: {amount_refunded / 100:.2f} {currency.upper()})"
            )

            # Send cancellation email
            admin_email = _get_admin_email(hotel.id, db)
            if admin_email:
                portal_url = settings.public_api_base_url or "https://app.yourdomain.com"
                portal_url = f"{portal_url}/upgrade"

                language = hotel.interface_language or "en"
                _send_subscription_email(
                    to_email=admin_email,
                    hotel_name=hotel.name,
                    language=language,
                    template=SUBSCRIPTION_CANCELED_TEMPLATES,
                    portal_url=portal_url,
                )
        else:
            # Partial refund - just log, no tier change
            logger.info(
                f"[BILLING] Partial refund for hotel {hotel.id}: "
                f"{amount_refunded / 100:.2f}/{amount_total / 100:.2f} {currency.upper()} - no tier change"
            )

        return True

    except Exception as e:
        db.rollback()  # CRITICAL: Rollback on any error
        logger.exception(f"[BILLING] Error handling charge refunded: {e}")
        return False


def handle_invoice_upcoming(invoice: dict, db: Session) -> bool:
    """
    Handle invoice.upcoming events (sent ~3 days before renewal).
    Sends email notification to hotel admin about upcoming charge.
    """
    try:
        customer_id = invoice.get("customer")
        amount_due = invoice.get("amount_due", 0)
        currency = invoice.get("currency", "eur").upper()
        period_end = invoice.get("period_end")  # Unix timestamp

        if not customer_id:
            logger.warning("[BILLING] No customer_id in invoice.upcoming event")
            return True  # Accept webhook to prevent retry loop

        # Find hotel by stripe_customer_id
        hotel = db.query(Hotel).filter(Hotel.stripe_customer_id == customer_id).first()
        if not hotel:
            logger.warning(
                f"[BILLING] Hotel not found for customer {customer_id} in invoice.upcoming"
            )
            return True  # Accept webhook to prevent retry loop

        # Get admin email
        admin_email = _get_admin_email(hotel.id, db)
        if not admin_email:
            logger.warning(f"[BILLING] No admin email found for hotel {hotel.id}")
            return True  # Accept webhook, just can't send email

        # Format amount (convert from cents)
        currency_symbols = {"EUR": "€", "USD": "$", "THB": "฿", "RON": "RON "}
        symbol = currency_symbols.get(currency, f"{currency} ")
        formatted_amount = f"{symbol}{amount_due / 100:.2f}"

        # Format renewal date
        renewal_date = ""
        if period_end:
            renewal_dt = datetime.fromtimestamp(period_end, tz=timezone.utc)
            renewal_date = renewal_dt.strftime("%B %d, %Y")

        # Generate portal URL for managing subscription
        portal_url = settings.public_api_base_url or "https://app.yourdomain.com"
        portal_url = (
            f"{portal_url}/admin/tasks"  # Redirect to dashboard, they can click manage subscription
        )

        # Send email
        language = hotel.interface_language or "en"
        _send_subscription_email(
            to_email=admin_email,
            hotel_name=hotel.name,
            language=language,
            template=RENEWAL_REMINDER_TEMPLATES,
            portal_url=portal_url,
            amount=formatted_amount,
            renewal_date=renewal_date,
        )

        logger.info(
            f"Renewal reminder email sent for hotel {hotel.id} ({hotel.name}): "
            f"{formatted_amount} due {renewal_date}"
        )
        return True

    except Exception as e:
        db.rollback()  # CRITICAL: Rollback on any error
        logger.exception(f"[BILLING] Error handling invoice upcoming: {e}")
        return False


def create_customer_portal_session(
    hotel_id: int,
    return_url: str,
    db: Session,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Create a Stripe Customer Portal session for subscription management.
    Allows users to cancel/update their subscription.

    Returns:
        Tuple of (portal_url, error_message)
    """
    if not settings.stripe_secret_key:
        return None, "Stripe is not configured"

    hotel = db.query(Hotel).filter(Hotel.id == hotel_id).first()
    if not hotel:
        return None, "Hotel not found"

    if not hotel.stripe_customer_id:
        return None, "No active subscription found"

    try:
        # Get locale based on hotel interface language
        locale = get_locale_for_language(hotel.interface_language or "en")

        session = stripe.billing_portal.Session.create(
            customer=hotel.stripe_customer_id,
            return_url=return_url,
            locale=locale,
        )
        logger.info(f"Created Stripe portal session for hotel {hotel_id} (locale={locale})")
        return session.url, None

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating portal session: {e}")
        return None, str(e)
    except Exception as e:
        logger.exception(f"Error creating portal session: {e}")
        return None, str(e)


def verify_webhook_signature(payload: bytes, sig_header: str) -> Optional[dict]:
    """
    Verify Stripe webhook signature and return event data.

    Returns:
        Event dict if valid, None if invalid
    """
    if not settings.stripe_webhook_secret:
        logger.warning("Stripe webhook secret not configured")
        return None

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.stripe_webhook_secret)
        return event
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Invalid Stripe webhook signature: {e}")
        return None
    except Exception as e:
        logger.exception(f"Error verifying webhook: {e}")
        return None
