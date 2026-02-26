from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.security import _redis as redis_client
from app.core.security import (
    create_access_token,
    decode_access_token,
    get_bearer_token,
)
from app.models import Hotel, StaffUser

router = APIRouter(prefix="/ui/admin", tags=["admin-ui"])
settings = get_settings()

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _render(request: Request, template_name: str):
    return templates.TemplateResponse(f"admin/{template_name}", {"request": request})


def _require_ui_auth(request: Request):
    token = request.cookies.get("admin_token") or get_bearer_token(request)
    if not token:
        return RedirectResponse(url="/ui/admin/login")
    try:
        decode_access_token(token)
    except Exception:
        return RedirectResponse(url="/ui/admin/login")
    return True


def _is_trial_expired(request: Request) -> bool:
    """Check if hotel's trial has expired (for FREE tier only)."""
    token = request.cookies.get("admin_token") or get_bearer_token(request)
    if not token:
        return False
    db_gen = get_db()
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if not user_id:
            return False

        db = next(db_gen)
        # Get hotel_id from StaffUser
        staff = db.query(StaffUser).filter(StaffUser.id == int(user_id)).first()
        if not staff:
            return False

        hotel = db.query(Hotel).filter(Hotel.id == staff.hotel_id).first()
        if not hotel:
            return False

        if hotel.subscription_tier != "free" or not hotel.trial_ends_at:
            return False

        trial_ends = hotel.trial_ends_at
        if trial_ends.tzinfo is None:
            trial_ends = trial_ends.replace(tzinfo=timezone.utc)

        return datetime.now(timezone.utc) > trial_ends
    except Exception:
        return False
    finally:
        db_gen.close()


@router.get("/conversations")
def conversations_page(request: Request, auth=Depends(_require_ui_auth)):
    if isinstance(auth, RedirectResponse):
        return auth
    return _render(request, "conversations.html")


@router.get("/conversations/{conversation_id}")
def conversation_detail_page(
    request: Request, conversation_id: int, auth=Depends(_require_ui_auth)
):
    if isinstance(auth, RedirectResponse):
        return auth
    return _render(request, "conversation_detail.html")


@router.get("/tasks")
def tasks_page(request: Request, auth=Depends(_require_ui_auth)):
    if isinstance(auth, RedirectResponse):
        return auth
    return _render(request, "tasks.html")


@router.get("/settings/integrations")
def admin_integrations_page(request: Request, code: str = None, auth=Depends(_require_ui_auth)):
    if isinstance(auth, RedirectResponse):
        # If OAuth return code is present, exchange it for token and re-authenticate
        if code and redis_client:
            user_token = redis_client.getdel(f"oauth_return:{code}")
            if user_token:
                token_str = user_token.decode() if isinstance(user_token, bytes) else user_token
                response = RedirectResponse(
                    url="/ui/admin/settings/integrations?cloudbeds_connected=1",
                    status_code=303,
                )
                secure_cookie = settings.environment == "production"
                response.set_cookie(
                    key="admin_token",
                    value=token_str,
                    httponly=True,
                    secure=secure_cookie,
                    samesite="lax",
                    max_age=5184000,
                    path="/",
                )
                return response
        return auth
    # Block if trial expired
    if _is_trial_expired(request):
        return RedirectResponse(url="/upgrade?reason=trial_expired")
    return _render(request, "integrations.html")


@router.get("/settings/staff")
def admin_staff_settings_page(request: Request, auth=Depends(_require_ui_auth)):
    if isinstance(auth, RedirectResponse):
        return auth
    return _render(request, "staff_settings.html")


@router.get("/settings/ai")
def admin_ai_settings_page(request: Request, auth=Depends(_require_ui_auth)):
    if isinstance(auth, RedirectResponse):
        return auth
    # Block if trial expired
    if _is_trial_expired(request):
        return RedirectResponse(url="/upgrade?reason=trial_expired")
    return _render(request, "ai_settings.html")


@router.get("/help")
def admin_help_page(request: Request, auth=Depends(_require_ui_auth)):
    if isinstance(auth, RedirectResponse):
        return auth
    return _render(request, "help.html")


@router.get("/reset-password")
def reset_password_page(request: Request, token: str):
    return templates.TemplateResponse(
        "admin/reset_password.html", {"request": request, "token": token}
    )


@router.get("/force-password-change")
def force_password_change_page(request: Request):
    return _render(request, "force_password_change.html")


@router.get("/login")
def login_page(request: Request, code: str = None, db: Session = Depends(get_db)):
    """Login page. If ?code= is provided, exchange temporary code for JWT and redirect."""
    if code and redis_client:
        staff_id = redis_client.getdel(f"instant_login:{code}")
        if staff_id:
            staff = db.query(StaffUser).filter(StaffUser.id == int(staff_id)).first()
            if staff:
                token = create_access_token(user_id=staff.id, email=staff.email)
                response = RedirectResponse(url="/ui/admin/tasks", status_code=303)
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
    return _render(request, "login.html")
