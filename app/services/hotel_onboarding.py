import secrets

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import Hotel, StaffUser


class HotelAlreadyExistsError(Exception):
    pass


class StaffEmailAlreadyExistsError(Exception):
    pass


def create_hotel_with_admin(
    db: Session,
    *,
    hotel_name: str,
    hotel_timezone: str,
    admin_name: str,
    admin_email: str,
    admin_password: str,
    messaging_provider: str = "meta",
    settings: dict | None = None,
    security_pin: str | None = None,
    interface_language: str = "en",
    language_locked: bool = False,
) -> tuple[Hotel, StaffUser]:
    """
    Creates a new Hotel and its first staff admin user in a single transaction.
    Fails if hotel name or staff email already exist (case-insensitive).
    """
    norm_name = hotel_name.strip()
    norm_email = admin_email.strip().lower()

    existing_hotel = db.query(Hotel).filter(func.lower(Hotel.name) == norm_name.lower()).first()
    if existing_hotel:
        raise HotelAlreadyExistsError("Hotel with this name already exists")

    existing_staff = db.query(StaffUser).filter(func.lower(StaffUser.email) == norm_email).first()
    if existing_staff:
        raise StaffEmailAlreadyExistsError("Staff email already exists")

    merged_settings = settings or {}
    if "messaging_provider" not in merged_settings:
        merged_settings["messaging_provider"] = messaging_provider

    pin_value = security_pin or generate_security_pin()

    hotel = Hotel(
        name=norm_name,
        timezone=hotel_timezone,
        is_active=True,
        settings=merged_settings,
        security_pin=pin_value,
        interface_language=interface_language or "en",
        language_locked=language_locked,
    )
    db.add(hotel)
    db.flush()  # get hotel.id

    password_hash = hash_password(admin_password)
    staff = StaffUser(
        hotel_id=hotel.id,
        name=admin_name.strip(),
        role="ADMIN",
        email=norm_email,
        password_hash=password_hash,
        is_active=True,
        must_change_password=True,
    )
    db.add(staff)
    db.commit()
    db.refresh(hotel)
    db.refresh(staff)
    return hotel, staff


def generate_security_pin() -> str:
    """Generate a 4-digit security PIN."""
    return f"{secrets.randbelow(9000) + 1000:04d}"
