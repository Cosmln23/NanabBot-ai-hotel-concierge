"""
Stripe payment routes.
Handles checkout session creation and webhooks.
"""

import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.security import decode_access_token, get_bearer_token, rate_limit
from app.models import Hotel, StaffUser
from app.services import stripe_service

router = APIRouter(tags=["stripe"])
templates = Jinja2Templates(directory="templates")
logger = logging.getLogger("hotelbot.stripe")
settings = get_settings()


def require_staff(request: Request, db: Session = Depends(get_db)) -> StaffUser:
    """Get the current authenticated staff user."""
    token = get_bearer_token(request) or request.headers.get("X-Token")
    if not token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        payload = decode_access_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")
    user = (
        db.query(StaffUser)
        .filter(StaffUser.id == int(payload.get("sub")), StaffUser.is_active == True)  # noqa: E712
        .first()
    )
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return user


class CreateCheckoutResponse(BaseModel):
    checkout_url: str


@router.get("/upgrade", response_class=HTMLResponse)
async def upgrade_page(request: Request):
    """Serve the upgrade page."""
    return templates.TemplateResponse("upgrade.html", {"request": request})


@router.get("/upgrade-pro", response_class=HTMLResponse)
async def upgrade_pro_page(request: Request):
    """Serve the PRO upgrade page."""
    return templates.TemplateResponse("upgrade_pro.html", {"request": request})


@router.get("/terms", response_class=HTMLResponse)
async def terms_page(request: Request):
    """Serve the Terms of Service page."""
    return templates.TemplateResponse("terms.html", {"request": request})


@router.get("/privacy", response_class=HTMLResponse)
async def privacy_page(request: Request):
    """Serve the Privacy Policy page."""
    return templates.TemplateResponse("privacy.html", {"request": request})


@router.get("/dpa", response_class=HTMLResponse)
async def dpa_page(request: Request):
    """Serve the Data Processing Agreement page."""
    return templates.TemplateResponse("dpa.html", {"request": request})


@router.get("/support", response_class=HTMLResponse)
async def support_page(request: Request):
    """Serve the Support page."""
    return templates.TemplateResponse("support.html", {"request": request})


@router.post("/api/stripe/create-checkout", response_model=CreateCheckoutResponse)
def create_checkout(
    request: Request,
    db: Session = Depends(get_db),
    user: StaffUser = Depends(require_staff),
):
    """
    Create a Stripe Checkout session for the user's hotel.
    Redirects to Stripe's hosted checkout page.
    Rate limited to 5 requests per minute per hotel.
    """
    # Rate limit: 5 checkout attempts per minute per hotel
    rate_limit(f"stripe_checkout:{user.hotel_id}", limit=5, window_seconds=60)

    base_url = settings.public_api_base_url or str(request.base_url).rstrip("/")
    success_url = f"{base_url}/upgrade/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{base_url}/upgrade?canceled=true"

    checkout_url, error = stripe_service.create_checkout_session(
        hotel_id=user.hotel_id,
        success_url=success_url,
        cancel_url=cancel_url,
        db=db,
    )

    if error:
        raise HTTPException(status_code=400, detail=error)

    return CreateCheckoutResponse(checkout_url=checkout_url)


@router.post("/api/stripe/create-pro-checkout", response_model=CreateCheckoutResponse)
def create_pro_checkout(
    request: Request,
    db: Session = Depends(get_db),
    user: StaffUser = Depends(require_staff),
):
    """
    Create a Stripe Checkout session for PRO plan subscription.
    Redirects to Stripe's hosted checkout page.
    Rate limited to 5 requests per minute per hotel.
    """
    # Rate limit: 5 checkout attempts per minute per hotel
    rate_limit(f"stripe_pro_checkout:{user.hotel_id}", limit=5, window_seconds=60)

    # Block Thailand - configurable via settings
    hotel = db.query(Hotel).filter(Hotel.id == user.hotel_id).first()
    if hotel and hotel.country == "TH" and settings.allow_th_block:
        raise HTTPException(
            status_code=403,
            detail="PRO plan is not available in your region yet.",
        )

    base_url = settings.public_api_base_url or str(request.base_url).rstrip("/")
    success_url = f"{base_url}/upgrade-pro/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{base_url}/upgrade-pro?canceled=true"

    checkout_url, error = stripe_service.create_pro_checkout_session(
        hotel_id=user.hotel_id,
        success_url=success_url,
        cancel_url=cancel_url,
        db=db,
    )

    if error:
        raise HTTPException(status_code=400, detail=error)

    return CreateCheckoutResponse(checkout_url=checkout_url)


def _validate_stripe_session_id(session_id: str) -> str:
    """
    Validate Stripe session ID format to prevent XSS/injection attacks.
    Returns sanitized session_id or None if invalid.
    """
    if not session_id:
        return None
    # Stripe session IDs start with cs_test_ or cs_live_
    if not session_id.startswith(("cs_test_", "cs_live_")):
        logger.warning(f"[SECURITY] Invalid session_id format rejected: {session_id[:50]}...")
        return None
    # Additional sanitization - only allow alphanumeric and underscores
    if not re.match(r"^cs_(test|live)_[a-zA-Z0-9_]+$", session_id):
        logger.warning("[SECURITY] Session_id with suspicious characters rejected")
        return None
    return session_id


@router.get("/upgrade/success", response_class=HTMLResponse)
async def upgrade_success(request: Request, session_id: str = None):
    """Show success page after payment."""
    # Validate session_id to prevent XSS/injection
    safe_session_id = _validate_stripe_session_id(session_id)
    return templates.TemplateResponse(
        "upgrade_success.html", {"request": request, "session_id": safe_session_id}
    )


@router.get("/upgrade-pro/success", response_class=HTMLResponse)
async def upgrade_pro_success(request: Request, session_id: str = None):
    """Show success page after PRO payment."""
    # Validate session_id to prevent XSS/injection
    safe_session_id = _validate_stripe_session_id(session_id)
    return templates.TemplateResponse(
        "upgrade_pro_success.html", {"request": request, "session_id": safe_session_id}
    )


class PortalResponse(BaseModel):
    portal_url: str


@router.post("/api/stripe/customer-portal", response_model=PortalResponse)
def create_customer_portal(
    request: Request,
    db: Session = Depends(get_db),
    user: StaffUser = Depends(require_staff),
):
    """
    Create a Stripe Customer Portal session for subscription management.
    Allows users to view invoices, update payment method, or cancel subscription.
    """
    base_url = settings.public_api_base_url or str(request.base_url).rstrip("/")
    # Return to dashboard with billing context indicator
    return_url = f"{base_url}/admin/tasks?from=billing"

    portal_url, error = stripe_service.create_customer_portal_session(
        hotel_id=user.hotel_id,
        return_url=return_url,
        db=db,
    )

    if error:
        raise HTTPException(status_code=400, detail=error)

    return PortalResponse(portal_url=portal_url)


@router.post("/webhook/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Handle Stripe webhook events with idempotency protection and race condition handling.

    IMPORTANT:
    - Uses row-level locking to prevent duplicate processing
    - Returns 200 OK quickly to avoid Stripe timeout retries
    - All handlers include db.rollback() on errors
    """
    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature", "")

    # Validate signature first (reject invalid requests immediately)
    if not sig_header:
        logger.warning("[BILLING] Missing Stripe-Signature header - rejecting webhook")
        raise HTTPException(status_code=400, detail="Missing signature")

    event = stripe_service.verify_webhook_signature(payload, sig_header)
    if not event:
        logger.warning("[BILLING] Invalid Stripe webhook signature - SECURITY INCIDENT")
        raise HTTPException(status_code=400, detail="Invalid signature")

    event_id = event.get("id", "")
    event_type = event.get("type", "")
    data = event.get("data", {}).get("object", {})

    # Idempotency check with row-level locking (prevents race conditions)
    if stripe_service.is_event_processed(event_id, db):
        logger.info(f"[BILLING] Skipping already processed webhook: {event_id} ({event_type})")
        return {"status": "ok", "message": "already processed"}

    logger.info(f"[BILLING] Processing Stripe webhook: {event_id} ({event_type})")

    # Handle different event types
    success = True
    if event_type == "checkout.session.completed":
        success = stripe_service.handle_checkout_completed(data, db)

    elif event_type in (
        "customer.subscription.updated",
        "customer.subscription.deleted",
    ):
        success = stripe_service.handle_subscription_updated(data, db)

    elif event_type in ("invoice.payment_failed", "payment_intent.payment_failed"):
        success = stripe_service.handle_invoice_payment_failed(data, db)

    elif event_type == "charge.refunded":
        success = stripe_service.handle_charge_refunded(data, db)

    elif event_type == "invoice.upcoming":
        success = stripe_service.handle_invoice_upcoming(data, db)

    else:
        logger.info(f"[BILLING] Unhandled webhook event type: {event_type}")

    # Mark event as processed (even if handler failed - to prevent infinite retries)
    # Failed events are logged and can be investigated manually
    stripe_service.mark_event_processed(event_id, event_type, db)

    if not success:
        logger.error(
            f"[BILLING] Webhook handler failed for {event_id} ({event_type}) - marked as processed to prevent retry loop"
        )

    return {"status": "ok"}
