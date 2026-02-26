"""PMS Synchronization Engine - Core logic for guest lifecycle management."""

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.models import (
    Guest,
    GuestPII,
    Hotel,
    Journey,
    JourneyEvent,
    JourneyEventStatus,
    Room,
    Stay,
    StayStatus,
)
from app.services.pms.apaleo_client import ApaleoClient
from app.services.pms.base import PMSReservation, ReservationState
from app.services.pms.cloudbeds_client import CloudbedsClient
from app.services.pms.mews_client import MewsClient
from app.services.pms.simulation_client import SimulationClient

logger = logging.getLogger(__name__)


class SyncStats:
    """Statistics for a sync operation."""

    def __init__(self):
        self.checkins_processed = 0
        self.checkouts_processed = 0
        self.guests_created = 0
        self.stays_created = 0
        self.stays_closed = 0
        self.journeys_triggered = 0
        self.errors = 0


def _hash_phone(phone: str) -> str:
    """Hash phone number for storage."""
    # Normalize: remove non-digits
    digits = "".join(c for c in phone if c.isdigit())
    return hashlib.sha256(digits.encode()).hexdigest()


def _get_or_create_guest(db: Session, hotel_id: int, phone: str) -> Guest:
    """
    Get existing guest or create new one.

    Uses phone hash for lookup, handles race conditions.
    """
    phone_hash = _hash_phone(phone)

    # Try to find existing guest
    guest = (
        db.query(Guest).filter(Guest.hotel_id == hotel_id, Guest.phone_hash == phone_hash).first()
    )

    if not guest:
        guest = Guest(hotel_id=hotel_id, phone_hash=phone_hash)
        db.add(guest)
        try:
            db.commit()
            db.refresh(guest)
        except IntegrityError:
            # Another process created this guest, rollback and re-query
            db.rollback()
            guest = (
                db.query(Guest)
                .filter(Guest.hotel_id == hotel_id, Guest.phone_hash == phone_hash)
                .first()
            )

    return guest


def _upsert_guest_pii(
    db: Session, guest: Guest, name: str, phone: str, email: Optional[str]
) -> None:
    """
    Update or create GuestPII record.

    GuestPII stores plain-text identifiable information.
    """
    pii = db.query(GuestPII).filter(GuestPII.guest_id == guest.id).first()

    if not pii:
        pii = GuestPII(
            guest_id=guest.id,
            full_name=name,
            phone_plain=phone,
            email_plain=email,
        )
    else:
        # Update with latest data from PMS
        pii.full_name = name
        pii.phone_plain = phone
        if email:
            pii.email_plain = email

    db.add(pii)
    db.commit()


def _get_or_create_room(db: Session, hotel_id: int, room_number: Optional[str]) -> Optional[int]:
    """
    Get existing room or create new one.

    Returns room_id or None if no room number provided.
    """
    if not room_number:
        return None

    room = db.query(Room).filter(Room.hotel_id == hotel_id, Room.room_number == room_number).first()

    if not room:
        room = Room(hotel_id=hotel_id, room_number=room_number, is_active=True)
        db.add(room)
        try:
            db.commit()
            db.refresh(room)
        except IntegrityError:
            # Another process created this room
            db.rollback()
            room = (
                db.query(Room)
                .filter(Room.hotel_id == hotel_id, Room.room_number == room_number)
                .first()
            )

    return room.id if room else None


def _close_previous_stays(db: Session, guest_id: int, room_id: Optional[int]) -> int:
    """
    Close any previous IN_HOUSE stays for this guest.

    This handles the case where a guest checks out but the PMS didn't send
    a check-out event, or we missed it.

    Also handles room turnover: if someone new is checking into a room,
    close any previous guest's stay in that room.

    Returns: Number of stays closed
    """
    closed_count = 0

    # Close guest's previous stays
    previous_stays = (
        db.query(Stay)
        .filter(
            Stay.guest_id == guest_id,
            Stay.status == StayStatus.IN_HOUSE,
        )
        .all()
    )

    for stay in previous_stays:
        stay.status = StayStatus.POST_STAY
        db.add(stay)
        closed_count += 1
        logger.info(f"Auto-closed previous stay {stay.id} for guest {guest_id}")

    # Close any other guest's stay in this room (room turnover)
    if room_id:
        room_stays = (
            db.query(Stay)
            .filter(
                Stay.room_id == room_id,
                Stay.status == StayStatus.IN_HOUSE,
                Stay.guest_id != guest_id,
            )
            .all()
        )

        for stay in room_stays:
            stay.status = StayStatus.POST_STAY
            db.add(stay)
            closed_count += 1
            logger.info(f"Auto-closed room turnover stay {stay.id} for room {room_id}")

    if closed_count > 0:
        db.commit()

    return closed_count


def _handle_checkin(
    db: Session,
    hotel_id: int,
    reservation: PMSReservation,
    stats: SyncStats,
) -> None:
    """
    Handle a check-in event from PMS.

    Creates Guest, GuestPII, Room, Stay, and triggers Welcome journey.
    """
    try:
        # 1. Get or create guest
        guest = _get_or_create_guest(db, hotel_id, reservation.guest_phone)
        if not db.query(Guest).filter(Guest.id == guest.id).first():
            stats.guests_created += 1

        # 2. Update guest PII
        _upsert_guest_pii(
            db,
            guest,
            reservation.guest_name,
            reservation.guest_phone,
            reservation.guest_email,
        )

        # 3. Update guest language preference
        if reservation.preferred_language and not guest.preferred_language:
            guest.preferred_language = reservation.preferred_language
            db.add(guest)
            db.commit()

        # 4. Get or create room
        room_id = _get_or_create_room(db, hotel_id, reservation.room_number)

        # 5. Check if stay already exists for this reservation
        existing_stay = (
            db.query(Stay)
            .filter(
                Stay.hotel_id == hotel_id,
                Stay.guest_id == guest.id,
                Stay.pms_reservation_id == reservation.reservation_id,
            )
            .first()
        )

        if existing_stay:
            # Update existing stay (PMS may have sent updated dates)
            if existing_stay.status != StayStatus.IN_HOUSE:
                existing_stay.status = StayStatus.IN_HOUSE
                logger.info(
                    f"Reopened stay {existing_stay.id} for reservation {reservation.reservation_id}"
                )
            existing_stay.room_id = room_id
            existing_stay.checkin_date = reservation.checkin_date
            existing_stay.checkout_date = reservation.checkout_date
            db.add(existing_stay)
            db.commit()
            stats.checkins_processed += 1
            return

        # 6. Close any previous stays (room turnover safety)
        closed = _close_previous_stays(db, guest.id, room_id)
        stats.stays_closed += closed

        # 7. Create new stay
        stay = Stay(
            hotel_id=hotel_id,
            guest_id=guest.id,
            room_id=room_id,
            checkin_date=reservation.checkin_date,
            checkout_date=reservation.checkout_date,
            status=StayStatus.IN_HOUSE,
            channel="pms",
            pms_reservation_id=reservation.reservation_id,
            whatsapp_opt_in=True,  # Assume opt-in, can be changed later
        )
        db.add(stay)
        db.commit()
        db.refresh(stay)
        stats.stays_created += 1

        # 8. Trigger welcome journey event
        journey = (
            db.query(Journey)
            .filter(
                Journey.hotel_id == hotel_id,
                Journey.name == "AFTER_CHECKIN_WELCOME",
                Journey.is_active == True,  # noqa: E712
            )
            .first()
        )

        if journey:
            # Check for existing event to prevent duplicate welcome messages
            existing_event = (
                db.query(JourneyEvent)
                .filter(
                    JourneyEvent.stay_id == stay.id,
                    JourneyEvent.journey_id == journey.id,
                    JourneyEvent.status.in_([JourneyEventStatus.PENDING, JourneyEventStatus.SENT]),
                )
                .first()
            )

            if not existing_event:
                # Schedule based on NOW (when we discover the check-in), not PMS checkin_date
                # PMS may only provide date without time, causing scheduling in the past
                run_at = datetime.now(timezone.utc) + timedelta(minutes=journey.delay_minutes)
                event = JourneyEvent(
                    hotel_id=hotel_id,
                    journey_id=journey.id,
                    guest_id=guest.id,
                    stay_id=stay.id,
                    channel="whatsapp",
                    run_at=run_at,
                    status=JourneyEventStatus.PENDING,
                )
                db.add(event)
                db.commit()
                stats.journeys_triggered += 1
                logger.info(f"Triggered welcome journey for stay {stay.id}")
            else:
                logger.debug(
                    f"Welcome journey already exists for stay {stay.id}, skipping duplicate"
                )

        stats.checkins_processed += 1
        logger.info(
            f"Processed check-in: Guest {guest.id}, Stay {stay.id}, Reservation {reservation.reservation_id}"
        )

    except Exception as e:
        logger.error(
            f"Error handling check-in for reservation {reservation.reservation_id}: {e}",
            exc_info=True,
        )
        stats.errors += 1
        db.rollback()


def _handle_checkout(
    db: Session,
    hotel_id: int,
    reservation: PMSReservation,
    stats: SyncStats,
) -> None:
    """
    Handle a check-out event from PMS.

    Updates Stay status to POST_STAY and triggers Goodbye journey.
    """
    try:
        # Find the active stay for this reservation
        stay = (
            db.query(Stay)
            .filter(
                Stay.hotel_id == hotel_id,
                Stay.pms_reservation_id == reservation.reservation_id,
                Stay.status == StayStatus.IN_HOUSE,
            )
            .first()
        )

        if not stay:
            logger.warning(
                f"Checkout event for reservation {reservation.reservation_id} "
                f"but no active stay found. May have been already processed."
            )
            return

        # Update stay status
        stay.status = StayStatus.POST_STAY
        db.add(stay)
        db.commit()
        stats.stays_closed += 1

        # Trigger goodbye/feedback journey
        journey = (
            db.query(Journey)
            .filter(
                Journey.hotel_id == hotel_id,
                Journey.name == "AFTER_CHECKOUT_FEEDBACK",
                Journey.is_active == True,  # noqa: E712
            )
            .first()
        )

        if journey:
            # Check for existing event to prevent duplicate feedback messages
            existing_event = (
                db.query(JourneyEvent)
                .filter(
                    JourneyEvent.stay_id == stay.id,
                    JourneyEvent.journey_id == journey.id,
                    JourneyEvent.status.in_([JourneyEventStatus.PENDING, JourneyEventStatus.SENT]),
                )
                .first()
            )

            if not existing_event:
                run_at = datetime.now(timezone.utc) + timedelta(minutes=journey.delay_minutes)
                event = JourneyEvent(
                    hotel_id=hotel_id,
                    journey_id=journey.id,
                    guest_id=stay.guest_id,
                    stay_id=stay.id,
                    channel="whatsapp",
                    run_at=run_at,
                    status=JourneyEventStatus.PENDING,
                )
                db.add(event)
                db.commit()
                stats.journeys_triggered += 1
                logger.info(f"Triggered feedback journey for stay {stay.id}")
            else:
                logger.debug(
                    f"Feedback journey already exists for stay {stay.id}, skipping duplicate"
                )

        stats.checkouts_processed += 1
        logger.info(
            f"Processed check-out: Stay {stay.id}, Reservation {reservation.reservation_id}"
        )

    except Exception as e:
        logger.error(
            f"Error handling check-out for reservation {reservation.reservation_id}: {e}",
            exc_info=True,
        )
        stats.errors += 1
        db.rollback()


def sync_hotel(hotel_id: int, time_window_hours: int = 24) -> SyncStats:
    """
    Synchronize a single hotel with its PMS.

    This is the main entry point for PMS sync.

    Args:
        hotel_id: ID of hotel to sync
        time_window_hours: How far back to look for reservation changes

    Returns:
        SyncStats object with sync results
    """
    db: Session = SessionLocal()
    stats = SyncStats()

    try:
        # Load hotel
        hotel = (
            db.query(Hotel).filter(Hotel.id == hotel_id, Hotel.is_active == True).first()
        )  # noqa: E712

        if not hotel:
            logger.warning(f"Hotel {hotel_id} not found or inactive")
            return stats

        # Check if hotel has PMS configured
        if not hotel.pms_type or not hotel.pms_api_key:
            logger.debug(f"Hotel {hotel_id} has no PMS configured, skipping")
            return stats

        # Get PMS client based on type
        pms_client = None
        if hotel.pms_type.lower() == "mews":
            pms_client = MewsClient(hotel)
        elif hotel.pms_type.lower() == "cloudbeds":
            pms_client = CloudbedsClient(hotel)
        elif hotel.pms_type.lower() == "apaleo":
            pms_client = ApaleoClient(hotel)
        elif hotel.pms_type.lower() in ("demo", "simulation"):
            pms_client = SimulationClient(hotel)
        else:
            logger.warning(f"Unsupported PMS type '{hotel.pms_type}' for hotel {hotel_id}")
            return stats

        # Fetch reservations from PMS
        logger.info(f"Fetching reservations from {hotel.pms_type} for hotel {hotel_id}")
        reservations = pms_client.get_reservations(time_window_hours=time_window_hours)

        logger.info(f"Found {len(reservations)} reservations for hotel {hotel_id}")

        # Process each reservation
        for reservation in reservations:
            if reservation.state == ReservationState.IN_HOUSE:
                _handle_checkin(db, hotel_id, reservation, stats)
            elif reservation.state == ReservationState.CHECKED_OUT:
                _handle_checkout(db, hotel_id, reservation, stats)
            # Ignore CONFIRMED and CANCELLED for now

        logger.info(
            f"Sync complete for hotel {hotel_id}: "
            f"{stats.checkins_processed} check-ins, "
            f"{stats.checkouts_processed} check-outs, "
            f"{stats.guests_created} guests created, "
            f"{stats.stays_created} stays created, "
            f"{stats.stays_closed} stays closed, "
            f"{stats.journeys_triggered} journeys triggered, "
            f"{stats.errors} errors"
        )

        return stats

    except Exception as e:
        logger.error(f"Fatal error syncing hotel {hotel_id}: {e}", exc_info=True)
        stats.errors += 1
        return stats
    finally:
        db.close()
