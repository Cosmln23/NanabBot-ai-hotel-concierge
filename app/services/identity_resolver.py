import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Set

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Guest, GuestPII, Hotel, Stay, StayStatus

settings = get_settings()


@dataclass
class IdentityContext:
    hotel: Hotel
    guest: Guest
    stay: Optional[Stay]
    state: StayStatus


def phone_variants(raw_phone: str) -> Set[str]:
    """Return possible normalized variants of a phone number (digits only)."""
    digits = re.sub(r"\D", "", raw_phone or "")
    variants: Set[str] = set()
    if not digits:
        return variants
    # Drop leading 00
    if digits.startswith("00"):
        digits = digits[2:]
    variants.add(digits)
    # Remove single leading 0
    if digits.startswith("0") and len(digits) > 1:
        variants.add(digits[1:])
    # If international (e.g., 40...), add local with leading 0
    if digits.startswith("40") and len(digits) > 2:
        variants.add("0" + digits[2:])
    return {v for v in variants if v}


def canonical_phone(raw_phone: str) -> Optional[str]:
    variants = phone_variants(raw_phone)
    if not variants:
        return None
    # Prefer the longest variant (usually international)
    return sorted(variants, key=len, reverse=True)[0]


def _ensure_guest_pii(db: Session, guest: Guest, phone: str) -> None:
    """Ensure GuestPII exists with phone_plain for Basic/Free tier display."""
    if not guest or not phone:
        return

    canonical = canonical_phone(phone)
    if not canonical:
        return

    # Check if PII already exists
    if guest.pii and guest.pii.phone_plain:
        return

    # Create or update PII
    if not guest.pii:
        pii = GuestPII(guest_id=guest.id, phone_plain=canonical)
        db.add(pii)
    else:
        guest.pii.phone_plain = canonical
        db.add(guest.pii)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()


def _ensure_hotel(db: Session, hotel_id: int) -> Optional[Hotel]:
    """Look up hotel by ID. Returns None if the hotel does not exist (never auto-creates)."""
    return db.query(Hotel).filter(Hotel.id == hotel_id).first()


def determine_state(stay: Optional[Stay]) -> StayStatus:
    if not stay:
        return StayStatus.POST_STAY

    now = datetime.now(timezone.utc)
    if stay.checkin_date and stay.checkout_date:
        if now < stay.checkin_date:
            return StayStatus.PRE_STAY
        if stay.checkin_date <= now < stay.checkout_date:
            return StayStatus.IN_HOUSE
        return StayStatus.POST_STAY

    return stay.status if stay.status else StayStatus.POST_STAY


def _find_guest_globally(
    db: Session, variant_hashes: list[str]
) -> Optional[tuple[Guest, Hotel, Stay]]:
    """
    Global Guest Discovery: Search across ALL hotels for a guest with an active IN_HOUSE stay.
    Returns: (Guest, Hotel, Stay) tuple if found, None otherwise.
    """
    if not variant_hashes:
        return None

    # Query ALL guests matching phone hash, join with their active stays
    results = (
        db.query(Guest, Hotel, Stay)
        .join(Hotel, Guest.hotel_id == Hotel.id)
        .join(Stay, Stay.guest_id == Guest.id)
        .filter(Guest.phone_hash.in_(variant_hashes), Stay.status == StayStatus.IN_HOUSE)
        .order_by(Stay.checkin_date.desc())  # Most recent checkin wins if multiple
        .all()
    )

    if results:
        # Return the most recent active stay
        return results[0]

    return None


def resolve_identity(
    db: Session, wa_id: str, hotel_id: Optional[int] = None
) -> Optional[IdentityContext]:
    """
    Resolve guest identity with Global Guest Discovery support.

    If hotel_id is not provided (or matches default), performs a global lookup across
    all hotels to find the guest's active stay. This enables proper multi-tenancy
    routing for shared WhatsApp numbers.
    """
    variants = phone_variants(wa_id)
    variant_hashes = [hashlib.sha256(v.encode()).hexdigest() for v in variants]

    # GLOBAL LOOKUP: If no hotel specified or using default, search across all hotels
    use_global_lookup = hotel_id is None or hotel_id == settings.default_hotel_id

    if use_global_lookup:
        global_result = _find_guest_globally(db, variant_hashes)

        if global_result:
            # Found active stay! Route to that hotel
            guest, hotel, stay = global_result
            state = determine_state(stay)
            return IdentityContext(hotel=hotel, guest=guest, stay=stay, state=state)

    # FALLBACK: Use specified hotel_id or default
    hotel = _ensure_hotel(db, hotel_id or settings.default_hotel_id)
    if not hotel:
        return None

    # Try to find existing guest in this hotel
    guest = None
    if variant_hashes:
        guest = (
            db.query(Guest)
            .filter(Guest.hotel_id == hotel.id, Guest.phone_hash.in_(variant_hashes))
            .first()
        )

    # Create new guest if not found
    if not guest:
        canonical = canonical_phone(wa_id)
        hash_value = (
            hashlib.sha256(canonical.encode()).hexdigest()
            if canonical
            else hashlib.sha256(wa_id.encode()).hexdigest()
        )
        guest = Guest(hotel_id=hotel.id, phone_hash=hash_value)
        db.add(guest)
        try:
            db.commit()
            db.refresh(guest)
        except IntegrityError:
            # Another thread created this guest, rollback and re-query
            db.rollback()
            guest = (
                db.query(Guest)
                .filter(Guest.hotel_id == hotel.id, Guest.phone_hash == hash_value)
                .first()
            )

    # Ensure PII exists with phone for Basic/Free tier display
    _ensure_guest_pii(db, guest, wa_id)

    # Find most recent stay for this guest
    stay = (
        db.query(Stay).filter(Stay.guest_id == guest.id).order_by(Stay.checkin_date.desc()).first()
    )
    state = determine_state(stay)

    return IdentityContext(hotel=hotel, guest=guest, stay=stay, state=state)


def resolve_identity_by_line_user(
    db: Session,
    line_user_id: str,
    hotel_id: Optional[int] = None,
) -> IdentityContext:
    """
    Resolve identity for LINE users based on stored line_user_id.

    Requires the LINE user to have been previously linked to a guest.
    """
    if not line_user_id:
        raise ValueError("Missing line_user_id")

    target_hotel = _ensure_hotel(db, hotel_id or settings.default_hotel_id)
    if not target_hotel:
        raise ValueError("Hotel not found")

    guest = (
        db.query(Guest)
        .filter(
            Guest.hotel_id == target_hotel.id,
            Guest.line_user_id == line_user_id,
        )
        .first()
    )

    if not guest:
        raise ValueError("LINE user not linked to any guest")

    stay = (
        db.query(Stay).filter(Stay.guest_id == guest.id).order_by(Stay.checkin_date.desc()).first()
    )
    state = determine_state(stay)

    return IdentityContext(hotel=target_hotel, guest=guest, stay=stay, state=state)
