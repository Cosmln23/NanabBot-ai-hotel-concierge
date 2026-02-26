import html
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from linebot import LineBotApi
from linebot.exceptions import LineBotApiError
from pydantic import BaseModel, EmailStr, constr
from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.api.routes_auth import _send_email
from app.core.config import get_settings
from app.core.db import get_db
from app.core.security import (
    create_access_token,
    decode_access_token,
    get_bearer_token,
    hash_password,
    verify_password,
)
from app.models import Hotel, PlatformOwner, StaffUser, SystemSetting, UsageDaily
from app.services.analytics import get_daily_usage
from app.services.hotel_onboarding import (
    HotelAlreadyExistsError,
    StaffEmailAlreadyExistsError,
    create_hotel_with_admin,
    generate_security_pin,
)
from app.services.messaging.line_setup import setup_line_webhook

router = APIRouter(prefix="/owner", tags=["owner"])
settings = get_settings()
logger = logging.getLogger("hotelbot")


def require_owner(request: Request, db: Session = Depends(get_db)) -> PlatformOwner:
    token = get_bearer_token(request) or request.headers.get("X-Owner-Token")
    if not token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        payload = decode_access_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")
    owner = (
        db.query(PlatformOwner)
        .filter(PlatformOwner.id == int(payload.get("sub")), PlatformOwner.is_active == True)
        .first()
    )  # noqa: E712
    if not owner:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return owner


class OwnerLoginRequest(BaseModel):
    email: EmailStr
    password: str


class OwnerLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CreateHotelAdminRequest(BaseModel):
    hotel_name: constr(strip_whitespace=True, min_length=2)
    hotel_timezone: constr(strip_whitespace=True, min_length=2)
    admin_name: constr(strip_whitespace=True, min_length=2)
    admin_email: EmailStr
    admin_password: constr(min_length=6)
    messaging_provider: Optional[str] = "meta"
    line_channel_secret: Optional[str] = None
    line_channel_access_token: Optional[str] = None
    whatsapp_phone_id: Optional[str] = None
    whatsapp_access_token: Optional[str] = None
    whatsapp_business_account_id: Optional[str] = None
    messaging_locked: Optional[bool] = True
    interface_language: Optional[str] = "en"
    language_locked: Optional[bool] = False


class CreateHotelAdminResponse(BaseModel):
    hotel_id: int
    hotel_name: str
    admin_id: int
    admin_email: EmailStr
    warning: Optional[str] = None
    calculated_webhook_url: Optional[str] = None
    security_pin: Optional[str] = None
    interface_language: Optional[str] = None
    language_locked: Optional[bool] = None


class ConnectionSettingsResponse(BaseModel):
    hotel_id: int
    messaging_provider: str
    whatsapp_phone_id_masked: Optional[str] = None
    whatsapp_access_token_masked: Optional[str] = None
    whatsapp_business_account_id: Optional[str] = None
    line_channel_secret_masked: Optional[str] = None
    line_channel_access_token_masked: Optional[str] = None
    webhook_url: Optional[str] = None
    warning: Optional[str] = None
    messaging_locked: Optional[bool] = None
    security_pin: Optional[str] = None
    interface_language: Optional[str] = None
    language_locked: Optional[bool] = None


class ConnectionSettingsUpdateRequest(BaseModel):
    messaging_provider: str = "meta"
    whatsapp_phone_id: Optional[str] = None
    whatsapp_access_token: Optional[str] = None
    whatsapp_business_account_id: Optional[str] = None
    line_channel_secret: Optional[str] = None
    line_channel_access_token: Optional[str] = None
    messaging_locked: Optional[bool] = None
    interface_language: Optional[str] = None
    language_locked: Optional[bool] = None


class PlatformSettingsPayload(BaseModel):
    openai_api_key: Optional[str] = None
    resend_api_key: Optional[str] = None
    whatsapp_platform_token: Optional[str] = None


@router.get("/hotels")
def list_hotels(db: Session = Depends(get_db), _auth=Depends(require_owner)):
    hotels: List[Hotel] = db.query(Hotel).all()
    return [{"id": h.id, "name": h.name, "timezone": h.timezone} for h in hotels]


@router.post(
    "/setup-hotel",
    response_model=CreateHotelAdminResponse,
    dependencies=[Depends(require_owner)],
)
def setup_hotel(payload: CreateHotelAdminRequest, request: Request, db: Session = Depends(get_db)):
    warning: Optional[str] = None
    webhook_url: Optional[str] = None
    try:
        provider = (payload.messaging_provider or "meta").lower()
        if provider not in {"meta", "twilio", "line"}:
            provider = "meta"
        settings_dict = {
            "messaging_provider": provider,
            "messaging_locked": (
                payload.messaging_locked if payload.messaging_locked is not None else True
            ),
        }
        # LINE keys
        if provider == "line":
            if not payload.line_channel_secret or not payload.line_channel_access_token:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="LINE requires channel secret and access token.",
                )
            settings_dict["line_channel_secret"] = payload.line_channel_secret
            settings_dict["line_channel_access_token"] = payload.line_channel_access_token
        # WhatsApp custom keys (BYOC)
        if provider == "meta":
            if payload.whatsapp_phone_id:
                settings_dict["whatsapp_phone_id"] = payload.whatsapp_phone_id
            if payload.whatsapp_access_token:
                settings_dict["whatsapp_access_token"] = payload.whatsapp_access_token
            if payload.whatsapp_business_account_id is not None:
                settings_dict["whatsapp_business_account_id"] = payload.whatsapp_business_account_id
        hotel, admin = create_hotel_with_admin(
            db,
            hotel_name=payload.hotel_name,
            hotel_timezone=payload.hotel_timezone,
            admin_name=payload.admin_name,
            admin_email=payload.admin_email,
            admin_password=payload.admin_password,
            messaging_provider=provider,
            settings=settings_dict,
            security_pin=generate_security_pin(),
            interface_language=payload.interface_language or "en",
            language_locked=payload.language_locked or False,
        )
        app_name = settings.app_name or "Platform"
        base_url = (settings.public_api_base_url or str(request.base_url)).rstrip("/")
        login_link = f"{base_url}/ui/admin/login"
        safe_app_name = html.escape(app_name)
        safe_email = html.escape(admin.email)
        safe_password = html.escape(payload.admin_password)
        interface_lang = (hotel.interface_language or "en").lower()
        subject = f"Welcome to {app_name} - Your Credentials"
        body = (
            f"<p>Welcome to {safe_app_name}!</p>"
            f"<p>Here are your login credentials:</p>"
            f"<ul>"
            f"<li><strong>Username:</strong> {safe_email}</li>"
            f"<li><strong>Temporary Password:</strong> {safe_password}</li>"
            f"</ul>"
            f'<p>Login here: <a href="{login_link}">{login_link}</a></p>'
            f"<p>Please change your password after your first login.</p>"
        )
        _send_email(admin.email, subject, body)

        if provider == "line":
            base_url = settings.public_api_base_url or str(request.base_url).rstrip("/")
            webhook_url = f"{base_url}/webhook/line/{hotel.id}"
            success, warn = setup_line_webhook(
                hotel.id, payload.line_channel_access_token, base_url=base_url
            )
            warning = warn
    except HotelAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A hotel with this name already exists.",
        )
    except StaffEmailAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A staff user with this email already exists.",
        )

    return CreateHotelAdminResponse(
        hotel_id=hotel.id,
        hotel_name=hotel.name,
        admin_id=admin.id,
        admin_email=admin.email,
        warning=warning if provider == "line" else None,
        calculated_webhook_url=webhook_url,
        security_pin=hotel.security_pin,
        interface_language=hotel.interface_language,
        language_locked=hotel.language_locked,
    )


@router.post("/login", response_model=OwnerLoginResponse)
def owner_login(payload: OwnerLoginRequest, request: Request, db: Session = Depends(get_db)):
    # Rate limit: max 5 login attempts per 5 minutes per IP
    from app.core.security import rate_limit

    try:
        rate_limit(f"owner_login:{request.client.host}", limit=5, window_seconds=300)
    except HTTPException:
        logger.warning(f"Rate limit exceeded for owner login from {request.client.host}")
        raise

    owner = (
        db.query(PlatformOwner)
        .filter(PlatformOwner.email == payload.email, PlatformOwner.is_active == True)
        .first()
    )  # noqa: E712
    if not owner or not verify_password(payload.password, owner.password_hash):
        logger.warning(
            f"Failed owner login attempt for email: {payload.email} from IP: {request.client.host}"
        )
        raise HTTPException(status_code=401, detail="Invalid credentials")

    logger.info(f"Successful owner login: {owner.email} from IP: {request.client.host}")
    token = create_access_token(user_id=owner.id, email=owner.email)
    return OwnerLoginResponse(access_token=token)


@router.put("/change-password")
def owner_change_password(
    payload: CreateHotelAdminRequest,
    db: Session = Depends(get_db),
    owner: PlatformOwner = Depends(require_owner),
):
    # reuse fields admin_password for new password
    if not payload.admin_password:
        raise HTTPException(status_code=400, detail="New password required")
    owner.password_hash = hash_password(payload.admin_password)
    db.add(owner)
    db.commit()
    return {"success": True}


@router.get("/hotels/{hotel_id}/usage/daily")
def hotel_usage_daily(
    hotel_id: int,
    days: int = 30,
    db: Session = Depends(get_db),
    _auth=Depends(require_owner),
):
    return get_daily_usage(db, hotel_id=hotel_id, days=days)


@router.get("/overview")
def overview(days: int = 30, db: Session = Depends(get_db), _auth=Depends(require_owner)):
    # Sum per hotel
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    query = db.query(
        UsageDaily.hotel_id,
        func.sum(UsageDaily.messages_in).label("messages_in"),
        func.sum(UsageDaily.messages_out_bot).label("messages_out_bot"),
        func.sum(UsageDaily.tasks_created).label("tasks_created"),
        func.sum(UsageDaily.tasks_done).label("tasks_done"),
        func.sum(UsageDaily.llm_calls).label("llm_calls"),
    )
    query = query.filter(UsageDaily.date >= cutoff.date())
    sub = query.group_by(UsageDaily.hotel_id).all()
    result = []
    for row in sub:
        total_in = row.messages_in or 0
        total_out_bot = row.messages_out_bot or 0
        automation_rate = float(total_out_bot) / total_in if total_in else 0.0
        result.append(
            {
                "hotel_id": row.hotel_id,
                "total_messages_in": total_in,
                "total_messages_out_bot": total_out_bot,
                "automation_rate": automation_rate,
                "total_tasks_created": row.tasks_created or 0,
                "total_tasks_done": row.tasks_done or 0,
                "total_llm_calls": row.llm_calls or 0,
            }
        )
    return result


def _mask(val: Optional[str]) -> Optional[str]:
    if not val:
        return None
    if len(val) <= 4:
        return "****"
    return "****" + val[-4:]


@router.get("/hotel/{hotel_id}/connection-status")
def connection_status(
    hotel_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _auth=Depends(require_owner),
):
    hotel: Optional[Hotel] = db.query(Hotel).filter(Hotel.id == hotel_id).first()
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")

    settings_dict = hotel.settings or {}
    provider = settings_dict.get("messaging_provider", "meta")

    base_url = settings.public_api_base_url or str(request.base_url).rstrip("/")
    webhook_url = f"{base_url}/webhook/line/{hotel.id}" if base_url else None

    if provider != "line":
        return {
            "status": "ok",
            "message": "Provider is not LINE",
            "webhook_url": webhook_url,
            "security_pin": hotel.security_pin,
            "interface_language": hotel.interface_language,
            "language_locked": hotel.language_locked,
        }

    access_token = settings_dict.get("line_channel_access_token")
    if not access_token:
        return {
            "status": "error",
            "message": "Missing LINE access token",
            "webhook_url": webhook_url,
            "security_pin": hotel.security_pin,
        }

    try:
        client = LineBotApi(access_token)
        client.get_bot_info()
        return {
            "status": "ok",
            "message": "Connected to LINE",
            "webhook_url": webhook_url,
            "security_pin": hotel.security_pin,
            "interface_language": hotel.interface_language,
            "language_locked": hotel.language_locked,
        }
    except LineBotApiError as exc:
        return {
            "status": "error",
            "message": f"LINE error: {exc}",
            "webhook_url": webhook_url,
            "security_pin": hotel.security_pin,
        }
    except Exception as exc:
        return {
            "status": "error",
            "message": f"Unexpected error: {exc}",
            "webhook_url": webhook_url,
            "security_pin": hotel.security_pin,
            "interface_language": hotel.interface_language,
            "language_locked": hotel.language_locked,
        }


@router.get("/hotels/{hotel_id}/connection", response_model=ConnectionSettingsResponse)
def get_connection_settings(
    hotel_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _auth=Depends(require_owner),
):
    hotel: Optional[Hotel] = db.query(Hotel).filter(Hotel.id == hotel_id).first()
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")
    settings_dict = hotel.settings or {}
    provider = settings_dict.get("messaging_provider", "meta")
    base_url = settings.public_api_base_url or str(request.base_url).rstrip("/")
    webhook_url = f"{base_url}/webhook/line/{hotel.id}" if provider == "line" else None
    return ConnectionSettingsResponse(
        hotel_id=hotel.id,
        messaging_provider=provider,
        whatsapp_phone_id_masked=_mask(
            settings_dict.get("whatsapp_phone_id") or settings_dict.get("whatsapp_phone_number_id")
        ),
        whatsapp_access_token_masked=_mask(settings_dict.get("whatsapp_access_token")),
        whatsapp_business_account_id=settings_dict.get("whatsapp_business_account_id"),
        line_channel_secret_masked=_mask(settings_dict.get("line_channel_secret")),
        line_channel_access_token_masked=_mask(settings_dict.get("line_channel_access_token")),
        webhook_url=webhook_url,
        messaging_locked=settings_dict.get("messaging_locked", False),
        security_pin=hotel.security_pin,
        interface_language=hotel.interface_language,
        language_locked=hotel.language_locked,
    )


@router.put("/hotels/{hotel_id}/connection", response_model=ConnectionSettingsResponse)
def update_connection_settings(
    hotel_id: int,
    payload: ConnectionSettingsUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    _auth=Depends(require_owner),
):
    hotel: Optional[Hotel] = db.query(Hotel).filter(Hotel.id == hotel_id).first()
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")

    settings_dict = dict(hotel.settings or {})
    provider = (
        payload.messaging_provider or settings_dict.get("messaging_provider") or "meta"
    ).lower()
    has_line_payload = bool(payload.line_channel_secret or payload.line_channel_access_token)
    if has_line_payload:
        provider = "line"
    warning: Optional[str] = None
    logger.info(
        "Owner connection update: hotel=%s provider=%s line_secret=%s line_token=%s wa_phone=%s wa_token=%s",
        hotel.id,
        provider,
        bool(payload.line_channel_secret),
        bool(payload.line_channel_access_token),
        bool(payload.whatsapp_phone_id),
        bool(payload.whatsapp_access_token),
    )

    if provider not in {"meta", "line", "twilio"}:
        provider = "meta"
    settings_dict["messaging_provider"] = provider
    if payload.messaging_locked is not None:
        settings_dict["messaging_locked"] = payload.messaging_locked
    if payload.interface_language:
        hotel.interface_language = payload.interface_language
    if payload.language_locked is not None:
        hotel.language_locked = payload.language_locked
    pin_value = hotel.security_pin or generate_security_pin()
    if not hotel.security_pin:
        hotel.security_pin = pin_value

    if provider == "line":
        secret = payload.line_channel_secret or settings_dict.get("line_channel_secret")
        token = payload.line_channel_access_token or settings_dict.get("line_channel_access_token")
        if not secret or not token:
            raise HTTPException(
                status_code=400, detail="LINE requires channel secret and access token."
            )
        settings_dict["line_channel_secret"] = secret
        settings_dict["line_channel_access_token"] = token
        # clear WA keys
        settings_dict.pop("whatsapp_phone_id", None)
        settings_dict.pop("whatsapp_phone_number_id", None)
        settings_dict.pop("whatsapp_access_token", None)
        settings_dict.pop("whatsapp_business_account_id", None)
        base_url = settings.public_api_base_url or str(request.base_url).rstrip("/")
        success, warn = setup_line_webhook(
            hotel.id, payload.line_channel_access_token, base_url=base_url
        )
        warning = warn
    else:
        if payload.whatsapp_phone_id is not None:
            settings_dict["whatsapp_phone_id"] = payload.whatsapp_phone_id
        if payload.whatsapp_access_token is not None:
            settings_dict["whatsapp_access_token"] = payload.whatsapp_access_token
        if payload.whatsapp_business_account_id is not None:
            settings_dict["whatsapp_business_account_id"] = payload.whatsapp_business_account_id
        # clear LINE keys
        settings_dict.pop("line_channel_secret", None)
        settings_dict.pop("line_channel_access_token", None)

    hotel.settings = settings_dict
    flag_modified(hotel, "settings")
    db.add(hotel)
    db.commit()
    db.refresh(hotel)

    base_url = settings.public_api_base_url or str(request.base_url).rstrip("/")
    webhook_url = f"{base_url}/webhook/line/{hotel.id}" if provider == "line" else None

    return ConnectionSettingsResponse(
        hotel_id=hotel.id,
        messaging_provider=provider,
        whatsapp_phone_id_masked=_mask(
            settings_dict.get("whatsapp_phone_id") or settings_dict.get("whatsapp_phone_number_id")
        ),
        whatsapp_access_token_masked=_mask(settings_dict.get("whatsapp_access_token")),
        whatsapp_business_account_id=settings_dict.get("whatsapp_business_account_id"),
        line_channel_secret_masked=_mask(settings_dict.get("line_channel_secret")),
        line_channel_access_token_masked=_mask(settings_dict.get("line_channel_access_token")),
        webhook_url=webhook_url,
        warning=warning,
        messaging_locked=settings_dict.get("messaging_locked", False),
        security_pin=pin_value,
        interface_language=hotel.interface_language,
        language_locked=hotel.language_locked,
    )


def _mask_secret(val: str | None) -> str | None:
    if not val:
        return None
    if len(val) <= 6:
        return "****"
    return val[:3] + "****" + val[-2:]


@router.get("/platform-settings")
def get_platform_settings(db: Session = Depends(get_db), _auth=Depends(require_owner)):
    settings_rows = db.query(SystemSetting).all()
    data = {row.key: row.value for row in settings_rows}
    return {
        "OPENAI_API_KEY": _mask_secret(data.get("OPENAI_API_KEY")),
        "RESEND_API_KEY": _mask_secret(data.get("RESEND_API_KEY")),
        "WHATSAPP_PLATFORM_TOKEN": _mask_secret(data.get("WHATSAPP_PLATFORM_TOKEN")),
    }


@router.put("/platform-settings")
def update_platform_settings(
    payload: PlatformSettingsPayload,
    db: Session = Depends(get_db),
    _auth=Depends(require_owner),
):
    incoming = {
        "OPENAI_API_KEY": payload.openai_api_key,
        "RESEND_API_KEY": payload.resend_api_key,
        "WHATSAPP_PLATFORM_TOKEN": payload.whatsapp_platform_token,
    }
    for key, val in incoming.items():
        if val is None:
            continue
        row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        if not row:
            row = SystemSetting(key=key, value=val)
        else:
            row.value = val
        db.add(row)
    db.commit()
    return {"success": True}


@router.get("/hotels/detailed")
def list_hotels_detailed(
    db: Session = Depends(get_db),
    _auth=Depends(require_owner),
):
    """
    Returns all hotels with detailed information including:
    - All hotel fields
    - Usage stats for last 30 days (aggregate from UsageDaily)
    - Connection status indicators
    """
    hotels: List[Hotel] = db.query(Hotel).all()

    # Get usage stats for last 30 days per hotel
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    usage_query = (
        db.query(
            UsageDaily.hotel_id,
            func.sum(UsageDaily.messages_in).label("messages_in"),
            func.sum(UsageDaily.tasks_created).label("tasks_created"),
            func.sum(UsageDaily.llm_calls).label("llm_calls"),
        )
        .filter(UsageDaily.date >= cutoff.date())
        .group_by(UsageDaily.hotel_id)
        .all()
    )

    # Convert usage to dict for quick lookup
    usage_by_hotel = {
        row.hotel_id: {
            "messages_in": row.messages_in or 0,
            "tasks_created": row.tasks_created or 0,
            "llm_calls": row.llm_calls or 0,
        }
        for row in usage_query
    }

    result = []
    now = datetime.now(timezone.utc)

    for h in hotels:
        settings_dict = h.settings or {}
        provider = settings_dict.get("messaging_provider", "meta")

        # Determine connection status
        connected = False
        if provider == "line":
            connected = bool(
                settings_dict.get("line_channel_secret")
                and settings_dict.get("line_channel_access_token")
            )
        elif provider == "meta":
            # Check for custom WhatsApp keys or assume platform default is available
            has_custom = bool(
                settings_dict.get("whatsapp_phone_id")
                or settings_dict.get("whatsapp_phone_number_id")
            )
            connected = has_custom or True  # Platform default always "connected"

        # Calculate trial status
        trial_status = None
        if h.trial_ends_at:
            if h.trial_ends_at.tzinfo is None:
                trial_end_aware = h.trial_ends_at.replace(tzinfo=timezone.utc)
            else:
                trial_end_aware = h.trial_ends_at
            delta = trial_end_aware - now
            if delta.total_seconds() > 0:
                trial_status = f"{delta.days} days left"
            else:
                trial_status = "Trial ended"

        # Calculate months active
        months_active = 0
        if h.created_at:
            created = h.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            delta_created = now - created
            months_active = max(0, delta_created.days // 30)

        # Get usage for this hotel
        usage = usage_by_hotel.get(h.id, {"messages_in": 0, "tasks_created": 0, "llm_calls": 0})

        # Get admin email for this hotel
        admin_user = (
            db.query(StaffUser)
            .filter(StaffUser.hotel_id == h.id, StaffUser.role.ilike("admin"))
            .first()
        )
        admin_email = admin_user.email if admin_user else None

        result.append(
            {
                "id": h.id,
                "name": h.name,
                "admin_email": admin_email,
                "timezone": h.timezone,
                "subscription_tier": h.subscription_tier or "free",
                "trial_status": trial_status,
                "trial_ends_at": h.trial_ends_at.isoformat() if h.trial_ends_at else None,
                "has_stripe": bool(h.stripe_subscription_id),
                "stripe_customer_id": bool(h.stripe_customer_id),
                "messaging_provider": provider.upper() if provider == "line" else "WhatsApp",
                "connected": connected,
                "created_at": h.created_at.isoformat() if h.created_at else None,
                "months_active": months_active,
                "interface_language": h.interface_language,
                "country": h.country,
                "usage_30d": usage,
            }
        )

    return result


@router.delete("/hotels/{hotel_id}")
def delete_hotel(
    hotel_id: int,
    db: Session = Depends(get_db),
    _auth=Depends(require_owner),
):
    """
    Deletes a hotel and all related data.
    Uses cascading delete as configured in the models.
    """
    hotel: Optional[Hotel] = db.query(Hotel).filter(Hotel.id == hotel_id).first()
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")

    hotel_name = hotel.name

    try:
        db.delete(hotel)
        db.commit()
        logger.info(f"Owner deleted hotel: id={hotel_id}, name={hotel_name}")
        return {"success": True, "message": f"Hotel '{hotel_name}' has been deleted."}
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete hotel {hotel_id}: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to delete hotel. Please try again or contact support."
        )
