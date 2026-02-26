import logging
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from linebot import LineBotApi
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.api.routes_admin import require_staff
from app.core.config import get_settings
from app.core.db import get_db
from app.models import Hotel, Journey, StaffUser
from app.services.messaging.line_setup import setup_line_webhook
from app.services.pms.apaleo_client import ApaleoClient
from app.services.pms.cloudbeds_client import CloudbedsClient
from app.services.pms.mews_client import MewsClient

logger = logging.getLogger(__name__)


def _ensure_default_journeys(db: Session, hotel_id: int) -> None:
    """
    Create default Journey records for a hotel if they don't exist.
    Called when PMS is configured to enable automatic welcome/feedback messages.
    """
    default_journeys = [
        {
            "name": "AFTER_CHECKIN_WELCOME",
            "type": "welcome",
            "template_key": "welcome_after_checkin",
            "delay_minutes": 5,
        },
        # TODO: Enable when feedback template is ready
        # {
        #     "name": "AFTER_CHECKOUT_FEEDBACK",
        #     "type": "feedback",
        #     "template_key": "feedback_after_checkout",
        #     "delay_minutes": 60,
        # },
    ]

    for journey_def in default_journeys:
        existing = (
            db.query(Journey)
            .filter(
                Journey.hotel_id == hotel_id,
                Journey.name == journey_def["name"],
            )
            .first()
        )

        if not existing:
            journey = Journey(
                hotel_id=hotel_id,
                name=journey_def["name"],
                type=journey_def["type"],
                template_key=journey_def["template_key"],
                delay_minutes=journey_def["delay_minutes"],
                is_active=True,
            )
            db.add(journey)

    db.commit()


def _compute_connection_status(hotel, settings_obj):
    settings_dict = hotel.settings or {}
    provider = settings_dict.get("messaging_provider", "meta")
    has_wa_custom = bool(
        settings_dict.get("whatsapp_access_token") or settings_dict.get("whatsapp_phone_id")
    )
    has_line_custom = bool(
        settings_dict.get("line_channel_access_token") and settings_dict.get("line_channel_secret")
    )
    locked_flag = settings_dict.get("messaging_locked", False)

    mode = "disconnected"
    locked = False
    status = "disconnected"
    message = "Not configured"
    if provider == "line" and has_line_custom:
        mode = "custom_line"
        status = "active"
        message = "LINE connected with custom credentials."
    elif provider == "meta" and has_wa_custom:
        mode = "custom_meta"
        status = "active"
        message = "WhatsApp connected with custom credentials."
    elif (
        provider == "meta"
        and settings_obj.whatsapp_access_token
        and settings_obj.whatsapp_phone_number_id
    ):
        mode = "platform_default"
        status = "active"
        message = "Using platform default WhatsApp number."
        locked = True

    if locked_flag:
        locked = True

    return {
        "provider": provider,
        "mode": mode,
        "status": status,
        "locked": locked,
        "message": message,
    }


router = APIRouter(prefix="/api/admin", tags=["admin-integrations"])


class AdminIntegrationsGetResponse(BaseModel):
    hotel_id: int
    pms_type: str | None
    pms_property_id: str | None
    pms_configured: bool
    cloudbeds_connected: bool = False  # Cloudbeds OAuth connected
    cloudbeds_property_id: str | None = None  # Cloudbeds property ID
    whatsapp_phone_id: str | None
    whatsapp_business_account_id: str | None
    whatsapp_configured: bool
    messaging_provider: str | None
    whatsapp_access_token_masked: str | None = None
    whatsapp_phone_id_masked: str | None = None
    whatsapp_business_account_id_masked: str | None = None
    whatsapp_verify_token: str | None = None  # BYON: per-hotel verify token
    whatsapp_webhook_url: str | None = None  # BYON: webhook URL for Meta config
    whatsapp_phone_number: str | None = None  # For room QR codes (wa.me links)
    line_channel_secret_masked: str | None = None
    line_channel_access_token_masked: str | None = None
    line_webhook_url: str | None = None
    connection_status: dict | None = None
    messaging_locked: bool | None = None
    staff_role: str | None = None
    security_pin_required: bool | None = None

    class Config:
        orm_mode = True


class LineQrResponse(BaseModel):
    qr_url: str
    basic_id: str


class AdminIntegrationsUpdateRequest(BaseModel):
    pms_type: str | None = None
    pms_api_key: str | None = None
    pms_property_id: str | None = None
    messaging_provider: str | None = None
    whatsapp_phone_id: str | None = None
    whatsapp_business_account_id: str | None = None
    whatsapp_access_token: str | None = None
    line_channel_secret: str | None = None
    line_channel_access_token: str | None = None
    messaging_locked: bool | None = None


@router.get("/integrations", response_model=AdminIntegrationsGetResponse)
def get_integrations(
    request: Request,
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(require_staff),
):
    hotel = db.query(Hotel).filter(Hotel.id == staff.hotel_id).first()
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")

    pms_configured = bool(hotel.pms_type and hotel.pms_api_key and hotel.pms_property_id)

    # WhatsApp is globally managed - check if global credentials exist
    settings = get_settings()
    whatsapp_configured = bool(settings.whatsapp_access_token and settings.whatsapp_phone_number_id)
    hotel_settings = hotel.settings or {}

    def _mask(val: str | None) -> str | None:
        if not val:
            return None
        if len(val) <= 4:
            return "****"
        return "****" + val[-4:]

    wa_token_masked = _mask(
        hotel_settings.get("whatsapp_access_token") or settings.whatsapp_access_token
    )
    wa_phone_masked = _mask(
        hotel_settings.get("whatsapp_phone_id")
        or hotel_settings.get("whatsapp_phone_number_id")
        or settings.whatsapp_phone_number_id
    )
    line_secret_masked = _mask(hotel_settings.get("line_channel_secret"))
    line_token_masked = _mask(hotel_settings.get("line_channel_access_token"))
    wa_business_id_masked = _mask(hotel_settings.get("whatsapp_business_account_id"))

    base_url = settings.public_api_base_url or str(request.base_url).rstrip("/")

    # LINE webhook URL
    line_webhook_url = (
        f"{base_url}/webhook/line/{hotel.id}"
        if (hotel.settings or {}).get("messaging_provider") == "line"
        else None
    )

    # WhatsApp BYON: webhook URL and verify token (only if BYON configured)
    has_wa_byon = bool(hotel_settings.get("whatsapp_access_token"))
    wa_webhook_url = f"{base_url}/webhook/whatsapp/{hotel.id}" if has_wa_byon else None
    wa_verify_token = hotel_settings.get("whatsapp_verify_token") if has_wa_byon else None

    # Cloudbeds OAuth: check if connected
    cloudbeds_connected = bool(
        hotel.pms_type == "cloudbeds" and hotel_settings.get("cloudbeds_access_token")
    )
    cloudbeds_property_id = (
        hotel_settings.get("cloudbeds_property_id") if cloudbeds_connected else None
    )

    return AdminIntegrationsGetResponse(
        hotel_id=hotel.id,
        pms_type=hotel.pms_type,
        pms_property_id=hotel.pms_property_id,
        pms_configured=pms_configured,
        cloudbeds_connected=cloudbeds_connected,
        cloudbeds_property_id=cloudbeds_property_id,
        whatsapp_phone_id=settings.whatsapp_phone_number_id,
        whatsapp_business_account_id=None,  # Not used in global model
        whatsapp_configured=whatsapp_configured,
        messaging_provider=(hotel.settings or {}).get("messaging_provider", "meta"),
        whatsapp_access_token_masked=wa_token_masked,
        whatsapp_phone_id_masked=wa_phone_masked,
        whatsapp_business_account_id_masked=wa_business_id_masked,
        whatsapp_verify_token=wa_verify_token,
        whatsapp_webhook_url=wa_webhook_url,
        whatsapp_phone_number=settings.whatsapp_phone_number,
        line_channel_secret_masked=line_secret_masked,
        line_channel_access_token_masked=line_token_masked,
        line_webhook_url=line_webhook_url,
        connection_status=_compute_connection_status(hotel, settings),
        messaging_locked=(hotel.settings or {}).get("messaging_locked", False),
        staff_role=staff.role,
        security_pin_required=bool(hotel.security_pin),
    )


@router.get("/integrations/line-qr", response_model=LineQrResponse)
def get_line_qr(
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(require_staff),
):
    hotel = db.query(Hotel).filter(Hotel.id == staff.hotel_id).first()
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")

    settings_dict = hotel.settings or {}

    # Try cached basic_id first (saved during Test Connection)
    cached_basic_id = settings_dict.get("line_basic_id")
    if cached_basic_id:
        qr_url = f"https://qr-official.line.me/sid/L/{cached_basic_id.lstrip('@')}.png"
        return LineQrResponse(qr_url=qr_url, basic_id=cached_basic_id)

    # Fallback: call LINE API
    access_token = (
        settings_dict.get("line_channel_access_token") or get_settings().line_channel_access_token
    )
    if not access_token:
        raise HTTPException(status_code=400, detail="LINE not configured for this hotel.")

    try:
        client = LineBotApi(access_token)
        info = client.get_bot_info()
        basic_id = getattr(info, "basic_id", None) or getattr(info, "basicId", None)
        if not basic_id:
            raise HTTPException(status_code=400, detail="Unable to retrieve LINE bot info.")

        # Cache for future requests
        if not hotel.settings:
            hotel.settings = {}
        hotel.settings = {**hotel.settings, "line_basic_id": basic_id}
        flag_modified(hotel, "settings")
        db.commit()

        qr_url = f"https://qr-official.line.me/sid/L/{basic_id.lstrip('@')}.png"
        return LineQrResponse(qr_url=qr_url, basic_id=basic_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to fetch LINE bot info: {exc}")


@router.put("/integrations", response_model=AdminIntegrationsGetResponse)
def update_integrations(
    payload: AdminIntegrationsUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(require_staff),
):
    hotel = db.query(Hotel).filter(Hotel.id == staff.hotel_id).first()
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")

    # Update PMS credentials
    if payload.pms_type is not None:
        hotel.pms_type = payload.pms_type
    if payload.pms_api_key is not None:
        hotel.pms_api_key = payload.pms_api_key
    if payload.pms_property_id is not None:
        hotel.pms_property_id = payload.pms_property_id

    settings_dict = dict(hotel.settings or {})

    # Normalize provider and update messaging settings (BYOC)
    provider = (
        payload.messaging_provider or settings_dict.get("messaging_provider") or "meta"
    ).lower()
    has_line_payload = bool(payload.line_channel_secret or payload.line_channel_access_token)
    if has_line_payload:
        provider = "line"
    if provider not in {"meta", "line", "twilio"}:
        provider = "meta"

    if payload.messaging_locked is not None and staff.role.lower() == "admin":
        settings_dict["messaging_locked"] = payload.messaging_locked

    settings_dict["messaging_provider"] = provider

    if provider == "line":
        secret = payload.line_channel_secret or settings_dict.get("line_channel_secret")
        token = payload.line_channel_access_token or settings_dict.get("line_channel_access_token")
        if not secret or not token:
            raise HTTPException(
                status_code=400, detail="LINE requires channel secret and access token."
            )
        settings_dict["line_channel_secret"] = secret
        settings_dict["line_channel_access_token"] = token
        # clear WA keys when switching to LINE
        settings_dict.pop("whatsapp_phone_id", None)
        settings_dict.pop("whatsapp_business_account_id", None)
        settings_dict.pop("whatsapp_access_token", None)
    else:
        if payload.whatsapp_phone_id is not None:
            settings_dict["whatsapp_phone_id"] = payload.whatsapp_phone_id
        if payload.whatsapp_business_account_id is not None:
            settings_dict["whatsapp_business_account_id"] = payload.whatsapp_business_account_id
        if payload.whatsapp_access_token is not None:
            settings_dict["whatsapp_access_token"] = payload.whatsapp_access_token
            # BYON: Auto-generate verify_token if not already set
            if not settings_dict.get("whatsapp_verify_token"):
                settings_dict["whatsapp_verify_token"] = secrets.token_hex(16)
        # clear LINE keys when switching to META
        settings_dict.pop("line_channel_secret", None)
        settings_dict.pop("line_channel_access_token", None)

    hotel.settings = settings_dict
    flag_modified(hotel, "settings")

    db.commit()
    db.refresh(hotel)

    pms_configured = bool(hotel.pms_type and hotel.pms_api_key and hotel.pms_property_id)

    # Auto-create default Journeys when PMS is configured
    if pms_configured:
        try:
            _ensure_default_journeys(db, hotel.id)
            logger.info(f"Ensured default journeys exist for hotel {hotel.id}")
        except Exception as e:
            logger.error(f"Failed to create default journeys for hotel {hotel.id}: {e}")

    # WhatsApp is globally managed - check global credentials
    settings = get_settings()
    whatsapp_configured = bool(settings.whatsapp_access_token and settings.whatsapp_phone_number_id)
    base_url = settings.public_api_base_url or str(request.base_url).rstrip("/")

    # Auto-wire LINE if creds provided
    hotel_settings = hotel.settings or {}
    if provider == "line" and hotel_settings.get("line_channel_access_token"):
        success, _warn = setup_line_webhook(
            hotel.id, hotel_settings.get("line_channel_access_token"), base_url=base_url
        )

    # Use same masking function as GET endpoint for consistency
    def _mask(val: str | None) -> str | None:
        if not val:
            return None
        if len(val) <= 4:
            return "****"
        return "****" + val[-4:]

    wa_token_masked = _mask(hotel_settings.get("whatsapp_access_token"))
    wa_phone_masked = _mask(
        hotel_settings.get("whatsapp_phone_id") or hotel_settings.get("whatsapp_phone_number_id")
    )
    line_secret_masked = _mask(hotel_settings.get("line_channel_secret"))
    line_token_masked = _mask(hotel_settings.get("line_channel_access_token"))
    wa_business_id_masked = _mask(hotel_settings.get("whatsapp_business_account_id"))

    # WhatsApp BYON: webhook URL and verify token
    has_wa_byon = bool(hotel_settings.get("whatsapp_access_token"))
    wa_webhook_url = f"{base_url}/webhook/whatsapp/{hotel.id}" if has_wa_byon else None
    wa_verify_token = hotel_settings.get("whatsapp_verify_token") if has_wa_byon else None

    # Cloudbeds OAuth: check if connected
    cloudbeds_connected = bool(
        hotel.pms_type == "cloudbeds" and hotel_settings.get("cloudbeds_access_token")
    )
    cloudbeds_property_id = (
        hotel_settings.get("cloudbeds_property_id") if cloudbeds_connected else None
    )

    return AdminIntegrationsGetResponse(
        hotel_id=hotel.id,
        pms_type=hotel.pms_type,
        pms_property_id=hotel.pms_property_id,
        pms_configured=pms_configured,
        cloudbeds_connected=cloudbeds_connected,
        cloudbeds_property_id=cloudbeds_property_id,
        whatsapp_phone_id=settings.whatsapp_phone_number_id,
        whatsapp_business_account_id=None,
        whatsapp_configured=whatsapp_configured,
        messaging_provider=(hotel.settings or {}).get("messaging_provider", "meta"),
        whatsapp_access_token_masked=wa_token_masked,
        whatsapp_phone_id_masked=wa_phone_masked,
        whatsapp_business_account_id_masked=wa_business_id_masked,
        whatsapp_verify_token=wa_verify_token,
        whatsapp_webhook_url=wa_webhook_url,
        whatsapp_phone_number=settings.whatsapp_phone_number,
        line_channel_secret_masked=line_secret_masked,
        line_channel_access_token_masked=line_token_masked,
        line_webhook_url=f"{base_url}/webhook/line/{hotel.id}",
        connection_status=_compute_connection_status(hotel, settings),
        messaging_locked=(hotel.settings or {}).get("messaging_locked", False),
        staff_role=staff.role,
        security_pin_required=bool(hotel.security_pin),
    )


class VerifyPasswordRequest(BaseModel):
    password: str


@router.post("/verify-password")
def verify_password(
    payload: VerifyPasswordRequest,
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(require_staff),
):
    """Verify staff password to unlock sensitive settings."""
    from app.core.security import verify_password as check_password

    if check_password(payload.password, staff.password_hash):
        return {"success": True}
    raise HTTPException(status_code=400, detail="Incorrect password")


class TestPmsPayload(BaseModel):
    """Payload for testing PMS connection with unsaved credentials."""

    pms_type: Optional[str] = None
    pms_property_id: Optional[str] = None
    pms_api_key: Optional[str] = None


@router.post("/integrations/test-connection")
def test_pms_connection(
    payload: Optional[TestPmsPayload] = None,
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(require_staff),
):
    """
    Test PMS API connection.

    If payload contains credentials, test with those (unsaved).
    Otherwise, test with stored credentials from DB.
    """
    hotel = db.query(Hotel).filter(Hotel.id == staff.hotel_id).first()
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")

    # Use payload values if provided, otherwise fall back to stored values
    pms_type = (payload.pms_type if payload and payload.pms_type else hotel.pms_type) or ""
    pms_property_id = (
        payload.pms_property_id if payload and payload.pms_property_id else hotel.pms_property_id
    ) or ""
    pms_api_key = (
        payload.pms_api_key if payload and payload.pms_api_key else hotel.pms_api_key
    ) or ""

    # Check if PMS is configured
    if not pms_type or not pms_api_key or not pms_property_id:
        return {
            "success": False,
            "message": "PMS not fully configured. Please provide PMS Type, Property ID, and API Key.",
        }

    # Create a temporary hotel-like object for testing
    class TempHotel:
        def __init__(self, hotel_id, pms_type, pms_property_id, pms_api_key):
            self.id = hotel_id
            self.pms_type = pms_type
            self.pms_property_id = pms_property_id
            self.pms_api_key = pms_api_key

    temp_hotel = TempHotel(hotel.id, pms_type, pms_property_id, pms_api_key)

    # Get appropriate PMS client
    try:
        if pms_type.lower() == "mews":
            client = MewsClient(temp_hotel)
        elif pms_type.lower() == "cloudbeds":
            client = CloudbedsClient(temp_hotel)
        elif pms_type.lower() == "apaleo":
            client = ApaleoClient(temp_hotel)
        else:
            return {
                "success": False,
                "message": f"PMS type '{pms_type}' is not yet supported. Supported: mews, cloudbeds, apaleo.",
            }

        # Test the connection
        success = client.test_connection()

        if success:
            return {
                "success": True,
                "message": f"Successfully connected to {pms_type} PMS!",
            }
        else:
            return {
                "success": False,
                "message": f"Failed to connect to {pms_type}. Please check your credentials.",
            }

    except ValueError as e:
        # Validation error (missing credentials)
        return {
            "success": False,
            "message": str(e),
        }
    except Exception as e:
        # Connection or other error
        return {
            "success": False,
            "message": f"Error testing connection: {str(e)}",
        }


class LineTestRequest(BaseModel):
    """Request body for testing LINE credentials from form."""

    channel_secret: str | None = None
    access_token: str | None = None


@router.post("/integrations/test-line")
def test_line_connection(
    request_body: LineTestRequest = None,
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(require_staff),
):
    """
    Test LINE API connection.

    If credentials are provided in request body (from form), test those directly.
    Otherwise, fall back to stored credentials in database.
    """
    hotel = db.query(Hotel).filter(Hotel.id == staff.hotel_id).first()
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")

    # Use credentials from form if provided, otherwise from database
    channel_secret = None
    access_token = None

    if request_body:
        channel_secret = request_body.channel_secret if request_body.channel_secret else None
        access_token = request_body.access_token if request_body.access_token else None

    # Fall back to database if not provided in request
    if not access_token or not channel_secret:
        hotel_settings = hotel.settings or {}
        if not channel_secret:
            channel_secret = hotel_settings.get("line_channel_secret")
        if not access_token:
            access_token = hotel_settings.get("line_channel_access_token")

    # Final fallback to global settings
    if not access_token:
        access_token = get_settings().line_channel_access_token
    if not channel_secret:
        channel_secret = get_settings().line_channel_secret

    if not access_token or not channel_secret:
        return {
            "success": False,
            "message": "LINE credentials not configured. Please provide Channel Secret and Access Token.",
        }

    try:
        client = LineBotApi(access_token)
        info = client.get_bot_info()
        basic_id = getattr(info, "basic_id", None) or getattr(info, "basicId", None)
        display_name = (
            getattr(info, "display_name", None) or getattr(info, "displayName", None) or "LINE Bot"
        )

        # Cache basic_id in hotel settings for QR code generation
        if basic_id:
            if not hotel.settings:
                hotel.settings = {}
            hotel.settings = {**hotel.settings, "line_basic_id": basic_id}
            flag_modified(hotel, "settings")
            db.commit()

        return {
            "success": True,
            "message": f"Connected! Bot: {display_name}",
            "basic_id": basic_id,
            "display_name": display_name,
        }
    except Exception as e:
        error_msg = str(e)
        return {
            "success": False,
            "message": f"Connection failed: {error_msg}",
        }


class GenerateQrTokenRequest(BaseModel):
    room_number: str


class GenerateQrTokenResponse(BaseModel):
    token: str
    room_number: str


@router.post("/integrations/generate-qr-token", response_model=GenerateQrTokenResponse)
def generate_qr_token(
    payload: GenerateQrTokenRequest,
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(require_staff),
):
    """Generate a unique QR token for a room. Used to prevent QR code spoofing."""
    from datetime import datetime, timezone

    hotel = db.query(Hotel).filter(Hotel.id == staff.hotel_id).first()
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")

    if not hotel.settings:
        hotel.settings = {}

    settings_dict = dict(hotel.settings)
    qr_tokens = dict(settings_dict.get("qr_tokens", {}))

    # Enforce max 500 tokens per hotel — remove oldest if at limit
    if len(qr_tokens) >= 500:
        sorted_tokens = sorted(qr_tokens.items(), key=lambda x: x[1].get("created_at", ""))
        # Remove oldest 50 to make room
        for tok, _ in sorted_tokens[:50]:
            del qr_tokens[tok]

    # Generate unique 6-char hex token (0-9a-f only, no ambiguous chars)
    token = secrets.token_hex(3)
    while token in qr_tokens:
        token = secrets.token_hex(3)

    qr_tokens[token] = {
        "room": payload.room_number,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    settings_dict["qr_tokens"] = qr_tokens
    hotel.settings = settings_dict
    flag_modified(hotel, "settings")
    db.commit()

    return GenerateQrTokenResponse(token=token, room_number=payload.room_number)


class WhatsAppTestRequest(BaseModel):
    """Request body for testing WhatsApp credentials from form."""

    phone_id: str | None = None
    access_token: str | None = None
    waba_id: str | None = None


@router.post("/integrations/test-whatsapp")
def test_whatsapp_connection(
    request_body: WhatsAppTestRequest = None,
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(require_staff),
):
    """
    Test WhatsApp API connection.

    If credentials are provided in request body (from form), test those directly.
    Otherwise, fall back to stored credentials in database.
    """
    import requests

    hotel = db.query(Hotel).filter(Hotel.id == staff.hotel_id).first()
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")

    # Use credentials from form if provided, otherwise from database
    access_token = None
    phone_id = None

    if request_body:
        access_token = request_body.access_token if request_body.access_token else None
        phone_id = request_body.phone_id if request_body.phone_id else None

    # Fall back to database if not provided in request
    if not access_token or not phone_id:
        hotel_settings = hotel.settings or {}
        if not access_token:
            access_token = hotel_settings.get("whatsapp_access_token")
        if not phone_id:
            phone_id = hotel_settings.get("whatsapp_phone_id") or hotel_settings.get(
                "whatsapp_phone_number_id"
            )

    if not access_token or not phone_id:
        return {
            "success": False,
            "message": "WhatsApp credentials not configured. Please provide Phone Number ID and Access Token.",
        }

    # Test via Meta Graph API - get phone number info
    url = f"https://graph.facebook.com/v22.0/{phone_id}"
    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        display_name = data.get("verified_name") or data.get("display_phone_number") or "Connected"
        return {
            "success": True,
            "message": f"Connected! Phone: {display_name}",
        }
    except requests.exceptions.RequestException as e:
        error_msg = str(e)
        if hasattr(e, "response") and e.response is not None:
            try:
                error_data = e.response.json()
                error_msg = error_data.get("error", {}).get("message", str(e))
            except Exception:
                pass
        return {
            "success": False,
            "message": f"Connection failed: {error_msg}",
        }
