import tempfile

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.api.routes_admin import require_staff
from app.core.db import get_db
from app.models import Hotel
from app.services.hotel_settings import update_settings

router = APIRouter(prefix="/api/admin/ai-settings", tags=["admin-ai-settings"])


class AISettingsPayload(BaseModel):
    use_llm_agent: bool | None = None
    bot_name: str | None = None
    tone: str | None = None
    guest_languages: list[str] | None = None
    staff_language: str | None = None
    welcome_text: str | None = None
    wifi_ssid: str | None = None
    wifi_pass: str | None = None
    breakfast_hours: str | None = None
    checkin_time: str | None = None
    checkout_time: str | None = None
    parking_policy: str | None = None
    hotel_rules_text: str | None = None
    hotel_products_text: str | None = None
    custom_knowledge_text: str | None = None
    bilingual_welcome: bool | None = None
    # Service toggles
    allow_housekeeping: bool | None = None
    allow_food_beverage: bool | None = None
    # Housekeeping sub-options
    hk_room_cleaning: bool | None = None
    hk_towels_toiletries: bool | None = None
    hk_bed_linen: bool | None = None
    hk_laundry: bool | None = None
    hk_extra_amenities: bool | None = None
    # Session security (BASIC tier)
    qr_session_expiry_enabled: bool | None = None
    qr_session_hours: int | None = None


@router.get("/")
def get_ai_settings(db: Session = Depends(get_db), staff=Depends(require_staff)):
    hotel: Hotel = db.query(Hotel).filter(Hotel.id == staff.hotel_id).first()
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")
    # Include hotel name in response for welcome preview
    response = hotel.settings.copy() if hotel.settings else {}
    response["hotel_name"] = hotel.name or "Hotel"
    response["subscription_tier"] = hotel.subscription_tier or "free"
    return response


@router.put("/")
def update_ai_settings(
    payload: AISettingsPayload,
    db: Session = Depends(get_db),
    staff=Depends(require_staff),
):
    hotel: Hotel = db.query(Hotel).filter(Hotel.id == staff.hotel_id).first()
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")
    updates = payload.dict(exclude_none=True)
    if not updates.get("guest_languages"):
        updates["guest_languages"] = ["auto"]
    if updates.get("staff_language") == "":
        updates.pop("staff_language", None)
    # Copy UI keys to brain.py expected keys (keep both for compatibility)
    if "wifi_pass" in updates:
        updates["wifi_password"] = updates["wifi_pass"]
    if "parking_policy" in updates:
        updates["parking_info"] = updates["parking_policy"]
    update_settings(hotel, updates)

    # Sync to hotel.ai_profile (single source of truth for bot personality)
    if hotel.ai_profile:
        if "bot_name" in updates:
            hotel.ai_profile.bot_name = updates["bot_name"]
        if "tone" in updates:
            # Map UI tone values to ai_profile format
            tone_map = {
                "profesionistă": "professional",
                "professional": "professional",
                "prietenoasă": "friendly",
                "friendly": "friendly",
            }
            hotel.ai_profile.tone = tone_map.get(updates["tone"], updates["tone"])
        if "wifi_ssid" in updates:
            hotel.ai_profile.wifi_ssid = updates["wifi_ssid"]
        if "wifi_pass" in updates:
            hotel.ai_profile.wifi_password = updates["wifi_pass"]
        if "breakfast_hours" in updates:
            hotel.ai_profile.breakfast_hours = updates["breakfast_hours"]
        if "parking_policy" in updates:
            hotel.ai_profile.parking_info = updates["parking_policy"]
        db.add(hotel.ai_profile)

    db.add(hotel)
    db.commit()
    db.refresh(hotel)
    return hotel.settings or {}


@router.post("/upload-knowledge")
def upload_knowledge(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    staff=Depends(require_staff),
):
    hotel: Hotel = db.query(Hotel).filter(Hotel.id == staff.hotel_id).first()
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")
    filename = file.filename or ""
    content = ""
    max_bytes = 2 * 1024 * 1024  # 2MB cap
    try:
        raw_content = file.file.read(max_bytes + 1)
        if len(raw_content) > max_bytes:
            raise HTTPException(status_code=400, detail="File too large (max 2MB).")
        if filename.lower().endswith(".pdf"):
            with tempfile.NamedTemporaryFile(delete=True) as tmp:  # ✅ Auto-cleanup
                tmp.write(raw_content)
                tmp.flush()
                reader = PdfReader(tmp.name)
                pages = [page.extract_text() or "" for page in reader.pages]
                content = "\n".join(pages)
        else:
            # treat as text
            content = raw_content.decode(errors="ignore")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to process file: {e}")
    content = content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="No text could be extracted from the file.")
    current = hotel.settings or {}
    # Replace content entirely (no concatenation to avoid duplicates)
    current["custom_knowledge_text"] = content
    update_settings(hotel, current)
    db.add(hotel)
    db.commit()
    db.refresh(hotel)
    return {"ok": True, "extracted_text": content, "length": len(content)}


@router.post("/upload-products")
def upload_products(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    staff=Depends(require_staff),
):
    hotel: Hotel = db.query(Hotel).filter(Hotel.id == staff.hotel_id).first()
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")
    filename = file.filename or ""
    content = ""
    max_bytes = 2 * 1024 * 1024  # 2MB cap
    try:
        raw_content = file.file.read(max_bytes + 1)
        if len(raw_content) > max_bytes:
            raise HTTPException(status_code=400, detail="File too large (max 2MB).")
        if filename.lower().endswith(".pdf"):
            with tempfile.NamedTemporaryFile(delete=True) as tmp:  # ✅ Auto-cleanup
                tmp.write(raw_content)
                tmp.flush()
                reader = PdfReader(tmp.name)
                pages = [page.extract_text() or "" for page in reader.pages]
                content = "\n".join(pages)
        else:
            # treat as text
            content = raw_content.decode(errors="ignore")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to process file: {e}")
    content = content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="No text could be extracted from the file.")
    current = hotel.settings or {}
    # Replace content entirely (no concatenation to avoid duplicates)
    current["hotel_products_text"] = content
    update_settings(hotel, current)
    db.add(hotel)
    db.commit()
    db.refresh(hotel)
    return {"ok": True, "extracted_text": content, "length": len(content)}
