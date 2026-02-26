import uuid
from datetime import datetime, timedelta, timezone

import resend
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, constr
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.logging import logger
from app.core.security import (
    create_access_token,
    decode_access_token,
    get_bearer_token,
    hash_password,
    rate_limit,
    verify_password,
)
from app.models import Hotel, PasswordResetToken, PlatformOwner, StaffUser

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


class LoginRequest(BaseModel):
    email: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: constr(min_length=1)
    new_password: constr(min_length=6)


class ForceChangePasswordRequest(BaseModel):
    new_password: constr(min_length=6)


class ForgotPasswordRequest(BaseModel):
    email: str
    user_type: str = "staff"  # staff or owner


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: constr(min_length=6)


def _require_auth(request: Request, db: Session = Depends(get_db)) -> StaffUser:
    """Require authentication and return the current staff user."""
    token = get_bearer_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        payload = decode_access_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = (
        db.query(StaffUser)
        .filter(StaffUser.id == int(payload.get("sub")), StaffUser.is_active == True)  # noqa: E712
        .first()
    )

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user


@router.post("/login")
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    rate_limit(f"login:{request.client.host}", limit=5, window_seconds=60)

    user = (
        db.query(StaffUser)
        .filter(StaffUser.email == payload.email, StaffUser.is_active == True)
        .first()
    )  # noqa: E712
    if not user or not verify_password(payload.password, user.password_hash):
        logger.info("Login failed for email %s from %s", payload.email, request.client.host)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(user_id=user.id, email=user.email)
    logger.info("Login success for email %s from %s", payload.email, request.client.host)

    # Get hotel info for frontend
    hotel = db.query(Hotel).filter(Hotel.id == user.hotel_id).first()

    response_content = {
        "access_token": token,
        "token_type": "bearer",
        "must_change_password": getattr(user, "must_change_password", False),
        "hotel_country": hotel.country if hotel else None,
        "hotel_language": hotel.interface_language if hotel else "en",
    }

    response = JSONResponse(content=response_content)

    # Secure HttpOnly Cookie
    secure_cookie = settings.environment == "production"
    response.set_cookie(
        key="admin_token",
        value=token,
        httponly=True,
        secure=secure_cookie,
        samesite="lax",
        max_age=5184000,
        path="/",
    )

    return response


@router.get("/me")
def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    user: StaffUser = Depends(_require_auth),
):
    """Get the current authenticated user's information."""
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "hotel_id": user.hotel_id,
        "must_change_password": getattr(user, "must_change_password", False),
    }


@router.put("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: StaffUser = Depends(_require_auth),
):
    """Change the current user's password."""
    # Verify current password
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    # Update to new password
    user.password_hash = hash_password(payload.new_password)
    db.add(user)
    db.commit()

    logger.info("Password changed for user %s from %s", user.email, request.client.host)

    return {"success": True, "message": "Password changed successfully"}


@router.post("/change-password-force")
def change_password_force(
    payload: ForceChangePasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: StaffUser = Depends(_require_auth),
):
    """Force password change flow (no current password), marks must_change_password=False."""
    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False
    db.add(user)
    db.commit()
    logger.info("Forced password change for user %s from %s", user.email, request.client.host)
    return {"success": True}


def _send_email(to_email: str, subject: str, body: str):
    api_key = settings.resend_api_key
    if not api_key:
        logger.warning("RESEND_API_KEY missing; email not sent to %s", to_email)
        return
    resend.api_key = api_key
    try:
        resend.Emails.send(
            {
                "from": settings.email_from_address,
                "to": [to_email],
                "subject": subject,
                "html": body,
            }
        )
    except Exception as e:
        logger.error("Failed to send email to %s: %s", to_email, e)


@router.post("/forgot-password")
def forgot_password(
    payload: ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)
):
    rate_limit(f"forgot:{request.client.host}", limit=3, window_seconds=3600)
    target_user = None
    user_type = payload.user_type or "staff"
    if user_type == "owner":
        target_user = (
            db.query(PlatformOwner)
            .filter(PlatformOwner.email == payload.email, PlatformOwner.is_active == True)
            .first()
        )  # noqa: E712
    else:
        target_user = (
            db.query(StaffUser)
            .filter(StaffUser.email == payload.email, StaffUser.is_active == True)
            .first()
        )  # noqa: E712

    if not target_user:
        # Do not reveal existence
        return {"success": True}

    token_value = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    reset = PasswordResetToken(
        user_type=user_type,
        user_id=target_user.id,
        token=token_value,
        expires_at=expires_at,
    )
    db.add(reset)
    db.commit()

    reset_link = f"{settings.public_api_base_url or ''}/ui/{'owner' if user_type == 'owner' else 'admin'}/reset-password?token={token_value}"

    RESET_EMAIL_TEMPLATES = {
        "en": {
            "subject": "Reset Your Password - AI Hotel Suite",
            "title": "Password Reset",
            "intro": "We received a request to reset your password.",
            "instruction": "Click the button below to set a new password:",
            "button": "Reset Password",
            "expires": "This link expires in 1 hour.",
            "ignore": "If you didn't request this, you can safely ignore this email.",
            "footer": "Questions? Contact us at",
        }
    }

    # Get language from user's hotel or default to English
    language = "en"
    if hasattr(target_user, "hotel_id") and target_user.hotel_id:
        hotel = db.query(Hotel).filter(Hotel.id == target_user.hotel_id).first()
        if hotel and hotel.interface_language:
            language = hotel.interface_language

    tpl = RESET_EMAIL_TEMPLATES.get(language, RESET_EMAIL_TEMPLATES["en"])
    contact_email = "support@yourdomain.com"

    body = f"""
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
                    {tpl['intro']}
                </p>

                <p style="color: #57534e; font-size: 15px; line-height: 1.6; text-align: center; margin: 25px 0;">
                    {tpl['instruction']}
                </p>

                <!-- CTA Button -->
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{reset_link}"
                       style="display: inline-block; background: #1c1917; color: #fafaf9;
                              padding: 14px 36px; border-radius: 10px; text-decoration: none;
                              font-weight: 600; font-size: 15px;">
                        {tpl['button']} →
                    </a>
                </div>

                <!-- Expiry Notice -->
                <p style="color: #57534e; font-size: 14px; text-align: center; margin: 20px 0 0 0;
                          background: #f5f5f4; padding: 12px; border-radius: 8px; border: 1px solid #e7e5e4;">
                    {tpl['expires']}
                </p>

                <p style="color: #a8a29e; font-size: 13px; text-align: center; margin-top: 20px;">
                    {tpl['ignore']}
                </p>
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

    _send_email(target_user.email, tpl["subject"], body)
    return {"success": True}


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    reset = db.query(PasswordResetToken).filter(PasswordResetToken.token == payload.token).first()
    if not reset or reset.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    if reset.user_type == "owner":
        user = db.query(PlatformOwner).filter(PlatformOwner.id == reset.user_id).first()
    else:
        user = db.query(StaffUser).filter(StaffUser.id == reset.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.password_hash = hash_password(payload.new_password)
    if hasattr(user, "must_change_password"):
        user.must_change_password = False
    db.add(user)
    db.delete(reset)
    db.commit()
    return {"success": True}
