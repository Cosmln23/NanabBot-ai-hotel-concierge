"""Cloudbeds PMS API integration client."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests

from app.services.pms.base import PMSProvider, PMSReservation, ReservationState

logger = logging.getLogger(__name__)


class CloudbedsClient(PMSProvider):
    """
    Cloudbeds PMS API client implementation.

    Documentation: https://hotels.cloudbeds.com/api/docs/

    Uses OAuth 2.0 for authentication. Tokens are stored in hotel.settings:
    - cloudbeds_access_token: Bearer token for API calls
    - cloudbeds_refresh_token: Token to refresh access when expired
    - cloudbeds_property_id: Property ID from OAuth response
    """

    BASE_URL = "https://hotels.cloudbeds.com/api/v1.1"
    TIMEOUT = 30  # seconds

    @property
    def provider_name(self) -> str:
        return "cloudbeds"

    def _get_access_token(self) -> Optional[str]:
        """Get OAuth access token from hotel settings."""
        settings = self.hotel.settings or {}
        # Try OAuth token first, fallback to pms_api_key for backwards compatibility
        return settings.get("cloudbeds_access_token") or self.hotel.pms_api_key

    def _get_property_id(self) -> Optional[str]:
        """Get property ID from hotel settings or pms_property_id."""
        settings = self.hotel.settings or {}
        return settings.get("cloudbeds_property_id") or self.hotel.pms_property_id

    def _make_request(self, endpoint: str, params: dict = None, _retry: bool = False) -> dict:
        """
        Make authenticated request to Cloudbeds API.

        Args:
            endpoint: API endpoint path (e.g., '/getReservations')
            params: Query parameters
            _retry: Internal flag to prevent infinite retry loops

        Returns:
            Response JSON

        Raises:
            ConnectionError: If API request fails
        """
        access_token = self._get_access_token()
        if not access_token:
            raise ConnectionError("No Cloudbeds access token configured")

        url = f"{self.BASE_URL}{endpoint}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }

        try:
            response = requests.get(url, params=params, headers=headers, timeout=self.TIMEOUT)

            # Handle 401 Unauthorized - token expired
            if response.status_code == 401 and not _retry:
                logger.warning(
                    f"Cloudbeds token expired for hotel {self.hotel.id}, attempting refresh..."
                )
                if self._refresh_token():
                    # Retry with new token
                    return self._make_request(endpoint, params, _retry=True)
                else:
                    raise ConnectionError("Cloudbeds token refresh failed - please reconnect OAuth")

            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            logger.error(f"Cloudbeds API timeout for hotel {self.hotel.id}")
            raise ConnectionError("Cloudbeds API timeout")
        except requests.exceptions.RequestException as e:
            logger.error(f"Cloudbeds API error for hotel {self.hotel.id}: {e}")
            raise ConnectionError(f"Cloudbeds API request failed: {e}")

    def _refresh_token(self) -> bool:
        """
        Refresh OAuth token using stored refresh_token.
        Updates hotel.settings in DB with new access_token.
        Returns True if successful, False otherwise.
        """
        from sqlalchemy.orm.attributes import flag_modified

        from app.core.config import get_settings
        from app.core.db import SessionLocal
        from app.models import Hotel

        settings = get_settings()
        hotel_settings = self.hotel.settings or {}
        refresh_token = hotel_settings.get("cloudbeds_refresh_token")

        if not refresh_token:
            logger.error(f"No refresh token available for hotel {self.hotel.id}")
            return False

        try:
            response = requests.post(
                "https://hotels.cloudbeds.com/api/v1.1/access_token",
                data={
                    "grant_type": "refresh_token",
                    "client_id": settings.cloudbeds_client_id,
                    "client_secret": settings.cloudbeds_client_secret,
                    "refresh_token": refresh_token,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30,
            )
            response.raise_for_status()
            token_data = response.json()

            new_access_token = token_data.get("access_token")
            new_refresh_token = token_data.get("refresh_token", refresh_token)

            if not new_access_token:
                logger.error(f"No access_token in refresh response for hotel {self.hotel.id}")
                return False

            # Update DB with new tokens
            db = SessionLocal()
            try:
                hotel = db.query(Hotel).filter(Hotel.id == self.hotel.id).first()
                if hotel:
                    hotel_settings = hotel.settings or {}
                    hotel_settings["cloudbeds_access_token"] = new_access_token
                    hotel_settings["cloudbeds_refresh_token"] = new_refresh_token
                    hotel.settings = hotel_settings
                    flag_modified(hotel, "settings")
                    db.add(hotel)
                    db.commit()

                    # Update local reference
                    self.hotel.settings = hotel_settings

                    logger.info(f"Cloudbeds token refreshed successfully for hotel {self.hotel.id}")
                    return True
            finally:
                db.close()

            return False

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to refresh Cloudbeds token for hotel {self.hotel.id}: {e}")
            return False

    def _get_guest_details(self, guest_id: str) -> dict:
        """
        Fetch guest contact details from Cloudbeds.

        Cloudbeds /getReservations doesn't include contact info,
        so we need a separate call to /getGuest for phone/email.
        """
        try:
            response = self._make_request(
                "/getGuest",
                {"propertyID": self._get_property_id(), "guestID": guest_id},
            )
            if response.get("success"):
                return response.get("data", {})
        except ConnectionError as e:
            logger.warning(f"Failed to fetch guest {guest_id} details: {e}")
        return {}

    def _get_reservation_details(self, reservation_id: str) -> dict:
        """
        Fetch full reservation details including room assignment.

        Cloudbeds /getReservations doesn't include room info,
        so we need a separate call to /getReservation for room details.
        """
        try:
            response = self._make_request(
                "/getReservation",
                {"propertyID": self._get_property_id(), "reservationID": reservation_id},
            )
            if response.get("success"):
                return response.get("data", {})
        except ConnectionError as e:
            logger.warning(f"Failed to fetch reservation {reservation_id} details: {e}")
        return {}

    def get_reservations(self, time_window_hours: int = 24) -> list[PMSReservation]:
        """
        Fetch reservations from Cloudbeds within time window.

        Cloudbeds API: GET /getReservations

        We fetch reservations that have:
        - Status: checked_in or checked_out
        - Modified within the time window
        """
        now = datetime.now(timezone.utc)
        start_time = now - timedelta(hours=time_window_hours)

        params = {
            "propertyID": self._get_property_id(),
            "modifiedSince": start_time.strftime("%Y-%m-%d"),
            "includeGuestInfo": "true",
        }

        try:
            response = self._make_request("/getReservations", params=params)
        except ConnectionError as e:
            logger.warning(f"Failed to fetch Cloudbeds reservations for hotel {self.hotel.id}: {e}")
            return []

        return self._parse_reservations(response)

    def _parse_reservations(self, response: dict) -> list[PMSReservation]:
        """
        Parse Cloudbeds API response into PMSReservation objects.

        Cloudbeds response structure:
        {
            "success": true,
            "data": [...]
        }
        """
        if not response.get("success"):
            logger.warning(f"Cloudbeds API returned success=false for hotel {self.hotel.id}")
            return []

        reservations = response.get("data", [])

        parsed = []
        for res in reservations:
            try:
                # Determine state from Cloudbeds status
                cb_status = res.get("status", "").lower()
                if cb_status == "checked_in":
                    state = ReservationState.IN_HOUSE
                elif cb_status == "checked_out":
                    state = ReservationState.CHECKED_OUT
                elif cb_status == "confirmed":
                    state = ReservationState.CONFIRMED
                elif cb_status == "canceled":
                    state = ReservationState.CANCELLED
                else:
                    logger.warning(f"Unknown Cloudbeds status: {cb_status}")
                    continue

                # Fetch guest contact details via separate API call
                # Cloudbeds /getReservations doesn't include phone/email
                guest_id = res.get("guestID")
                if not guest_id:
                    logger.warning(
                        f"Reservation {res.get('reservationID')} has no guestID, skipping"
                    )
                    continue

                guest = self._get_guest_details(guest_id)

                # Extract phone: prefer cellPhone, fallback to phone
                phone = guest.get("cellPhone") or guest.get("phone")
                # Filter out "N/A" values
                if phone and phone.strip().upper() == "N/A":
                    phone = None

                if not phone:
                    logger.warning(
                        f"Reservation {res.get('reservationID')} has no phone number, skipping"
                    )
                    continue

                # Parse dates
                checkin = self._parse_date(res.get("startDate"))
                checkout = self._parse_date(res.get("endDate"))

                # Guest name from reservation or guest details
                guest_name = res.get("guestName") or (
                    f"{guest.get('firstName', '')} {guest.get('lastName', '')}".strip()
                )

                # Extract room - try multiple strategies
                room_name = None
                reservation_id = res.get("reservationID")

                # Strategy 1: 'rooms' array from getReservations
                rooms_list = res.get("rooms", [])
                if rooms_list:
                    room_name = rooms_list[0].get("roomName")

                # Strategy 2: 'assigned' array from getReservations
                if not room_name:
                    assigned_list = res.get("assigned", [])
                    if assigned_list:
                        room_name = assigned_list[0].get("roomName")

                # Strategy 3: Call getReservation (singular) for full details
                if not room_name and reservation_id:
                    res_details = self._get_reservation_details(str(reservation_id))
                    if res_details:
                        # Try assigned array from detailed response
                        assigned = res_details.get("assigned", [])
                        if assigned:
                            room_name = assigned[0].get("roomName")
                        # Try rooms array from detailed response
                        if not room_name:
                            rooms = res_details.get("rooms", [])
                            if rooms:
                                room_name = rooms[0].get("roomName")

                pms_reservation = PMSReservation(
                    reservation_id=str(res.get("reservationID", "")),
                    guest_name=guest_name or "Unknown Guest",
                    guest_phone=phone.strip(),
                    guest_email=guest.get("email"),
                    room_number=room_name,
                    state=state,
                    checkin_date=checkin,
                    checkout_date=checkout,
                    preferred_language="en",  # Cloudbeds doesn't provide language
                )

                parsed.append(pms_reservation)

            except Exception as e:
                logger.error(f"Error parsing Cloudbeds reservation: {e}", exc_info=True)
                continue

        logger.info(f"Parsed {len(parsed)} reservations from Cloudbeds for hotel {self.hotel.id}")
        return parsed

    def _parse_date(self, date_string: Optional[str]) -> datetime:
        """Parse Cloudbeds date string to datetime object."""
        if not date_string:
            return datetime.now(timezone.utc)
        try:
            # Cloudbeds uses YYYY-MM-DD format
            return datetime.strptime(date_string, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except (ValueError, AttributeError):
            logger.warning(f"Failed to parse date: {date_string}")
            return datetime.now(timezone.utc)

    def test_connection(self) -> bool:
        """
        Test connection to Cloudbeds API.

        Makes a lightweight request to verify credentials.
        """
        access_token = self._get_access_token()
        if not access_token:
            logger.error(f"No Cloudbeds access token for hotel {self.hotel.id}")
            return False

        params = {
            "propertyID": self._get_property_id(),
        }

        try:
            # Try to fetch property info (lightweight endpoint)
            response = self._make_request("/getHotelDetails", params=params)
            property_name = response.get("data", {}).get("propertyName", "Unknown")
            logger.info(
                f"✅ Cloudbeds connection test successful for hotel {self.hotel.id}: {property_name}"
            )
            return True
        except ConnectionError as e:
            logger.error(f"Cloudbeds connection test failed for hotel {self.hotel.id}: {e}")
            return False
