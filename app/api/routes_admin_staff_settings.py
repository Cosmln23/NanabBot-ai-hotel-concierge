from fastapi import APIRouter, Depends
from pydantic import BaseModel, constr
from sqlalchemy.orm import Session

from app.api.routes_admin import require_staff
from app.core.db import get_db
from app.models import Hotel, StaffUser

router = APIRouter(prefix="/api/admin", tags=["admin-staff-settings"])


class StaffSettingsResponse(BaseModel):
    staff_language: str | None
    staff_alert_phone: str | None


class StaffSettingsUpdateRequest(BaseModel):
    staff_language: constr(strip_whitespace=True, min_length=2, max_length=5) | None = None
    staff_alert_phone: constr(strip_whitespace=True, min_length=4) | None = None


@router.get("/staff-settings", response_model=StaffSettingsResponse)
def get_staff_settings(
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(require_staff),
):
    hotel = db.query(Hotel).filter(Hotel.id == staff.hotel_id).first()
    return StaffSettingsResponse(
        staff_language=hotel.staff_language,
        staff_alert_phone=hotel.staff_alert_phone,
    )


@router.put("/staff-settings", response_model=StaffSettingsResponse)
def update_staff_settings(
    payload: StaffSettingsUpdateRequest,
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(require_staff),
):
    hotel = db.query(Hotel).filter(Hotel.id == staff.hotel_id).first()
    if payload.staff_language is not None:
        hotel.staff_language = payload.staff_language
    if payload.staff_alert_phone is not None:
        hotel.staff_alert_phone = payload.staff_alert_phone
    db.add(hotel)
    db.commit()
    db.refresh(hotel)
    return StaffSettingsResponse(
        staff_language=hotel.staff_language,
        staff_alert_phone=hotel.staff_alert_phone,
    )
