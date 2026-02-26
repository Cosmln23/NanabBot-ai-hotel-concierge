"""Abstract base class for PMS (Property Management System) providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

from app.models import Hotel


class ReservationState(str, Enum):
    """State of a reservation in the PMS."""

    IN_HOUSE = "in_house"  # Guest is checked in
    CHECKED_OUT = "checked_out"  # Guest has checked out
    CONFIRMED = "confirmed"  # Reservation confirmed but not yet checked in
    CANCELLED = "cancelled"  # Reservation cancelled


@dataclass
class PMSReservation:
    """
    Normalized reservation data from any PMS.

    This is the common format that all PMS providers must return.
    """

    reservation_id: str  # Unique ID from PMS
    guest_name: str
    guest_phone: str  # International format preferred (e.g., +40712345678)
    guest_email: Optional[str]
    room_number: Optional[str]
    state: ReservationState
    checkin_date: datetime
    checkout_date: datetime
    preferred_language: Optional[str] = None


class PMSProvider(ABC):
    """
    Abstract base class for all PMS integrations.

    Each PMS (Mews, Cloudbeds, etc.) must implement this interface.
    """

    def __init__(self, hotel: Hotel):
        """
        Initialize the PMS provider with hotel credentials.

        Args:
            hotel: Hotel object containing pms_api_key, pms_property_id, etc.
        """
        self.hotel = hotel
        self._validate_credentials()

    def _validate_credentials(self) -> None:
        """
        Validate that hotel has required PMS credentials.

        Raises:
            ValueError: If credentials are missing or invalid.
        """
        if not self.hotel.pms_api_key:
            raise ValueError(f"Hotel {self.hotel.id} missing pms_api_key")
        if not self.hotel.pms_property_id:
            raise ValueError(f"Hotel {self.hotel.id} missing pms_property_id")

    @abstractmethod
    def get_reservations(self, time_window_hours: int = 24) -> list[PMSReservation]:
        """
        Fetch reservations from PMS within a time window.

        This method should return ALL reservations that have changed state
        within the time window (check-ins, check-outs, updates).

        Args:
            time_window_hours: Number of hours to look back (default 24)

        Returns:
            List of PMSReservation objects

        Raises:
            ConnectionError: If PMS API is unreachable
            ValueError: If API returns invalid data
        """
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        """
        Test the connection to the PMS API.

        This should make a lightweight API call to verify credentials work.

        Returns:
            True if connection successful, False otherwise
        """
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the name of this PMS provider (e.g., 'mews', 'cloudbeds')."""
        pass
