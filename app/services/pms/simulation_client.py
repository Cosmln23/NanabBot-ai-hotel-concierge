"""Simulation PMS Client for testing without a real PMS."""

import json
import os
from datetime import datetime, timedelta, timezone

from app.models import Hotel
from app.services.pms.base import PMSProvider, PMSReservation, ReservationState


class SimulationClient(PMSProvider):
    """
    Simulation PMS client that returns demo data from a JSON file or env variables.

    For testing the full PMS sync flow without a real PMS integration.
    """

    def __init__(self, hotel: Hotel):
        """Initialize with hotel - skip credential validation for simulation."""
        self.hotel = hotel

    def _validate_credentials(self) -> None:
        """No validation needed for simulation."""

    @property
    def provider_name(self) -> str:
        return "simulation"

    def test_connection(self) -> bool:
        """Always returns True for simulation."""
        return True

    def get_reservations(self, time_window_hours: int = 24) -> list[PMSReservation]:
        """
        Return demo reservations from:
        1. JSON file at data/simulation_pms_{hotel_id}.json
        2. Or environment variable PMS_SIMULATION_DATA
        3. Or default demo data using PMS_SIMULATION_TEST_PHONE
        """
        reservations = []

        # Try JSON file first
        json_path = f"data/simulation_pms_{self.hotel.id}.json"
        if os.path.exists(json_path):
            with open(json_path, "r") as f:
                data = json.load(f)
                for r in data.get("reservations", []):
                    reservations.append(self._parse_reservation(r))
            return reservations

        # Try environment variable
        env_data = os.getenv("PMS_SIMULATION_DATA")
        if env_data:
            data = json.loads(env_data)
            for r in data.get("reservations", []):
                reservations.append(self._parse_reservation(r))
            return reservations

        # Default: single IN_HOUSE guest using PMS_SIMULATION_TEST_PHONE
        test_phone = os.getenv("PMS_SIMULATION_TEST_PHONE", "+40771257815")

        now = datetime.now(timezone.utc)
        reservations.append(
            PMSReservation(
                reservation_id=f"SIM-{self.hotel.id}-001",
                guest_name="Simulation Guest",
                guest_phone=test_phone,
                guest_email="simulation@test.com",
                room_number="101",
                state=ReservationState.IN_HOUSE,
                checkin_date=now - timedelta(minutes=2),  # Recent checkin for testing
                checkout_date=now + timedelta(days=2),
                preferred_language="ro",
            )
        )

        return reservations

    def _parse_reservation(self, data: dict) -> PMSReservation:
        """Parse a reservation dict into PMSReservation."""
        state_map = {
            "in_house": ReservationState.IN_HOUSE,
            "checked_out": ReservationState.CHECKED_OUT,
            "confirmed": ReservationState.CONFIRMED,
            "cancelled": ReservationState.CANCELLED,
        }

        return PMSReservation(
            reservation_id=data["reservation_id"],
            guest_name=data["guest_name"],
            guest_phone=data["guest_phone"],
            guest_email=data.get("guest_email"),
            room_number=data.get("room_number"),
            state=state_map.get(data.get("state", "in_house"), ReservationState.IN_HOUSE),
            checkin_date=(
                datetime.fromisoformat(data["checkin_date"])
                if isinstance(data.get("checkin_date"), str)
                else datetime.now(timezone.utc)
            ),
            checkout_date=(
                datetime.fromisoformat(data["checkout_date"])
                if isinstance(data.get("checkout_date"), str)
                else datetime.now(timezone.utc) + timedelta(days=1)
            ),
            preferred_language=data.get("preferred_language"),
        )
