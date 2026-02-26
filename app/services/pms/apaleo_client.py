"""Apaleo PMS API integration client."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests

from app.services.pms.base import PMSProvider, PMSReservation, ReservationState

logger = logging.getLogger(__name__)


class ApaleoClient(PMSProvider):
    """
    Apaleo PMS API client implementation.

    Documentation: https://api.apaleo.com/swagger/index.html

    Authentication: OAuth 2.0 Client Credentials Flow
    - Token endpoint: https://identity.apaleo.com/connect/token
    - API Base: https://api.apaleo.com

    Credentials stored in hotel model:
    - pms_api_key: client_id:client_secret (colon-separated)
    - pms_property_id: Apaleo property ID
    """

    TOKEN_URL = "https://identity.apaleo.com/connect/token"
    API_BASE_URL = "https://api.apaleo.com"
    TIMEOUT = 30  # seconds

    # Token cache (simple in-memory, could be Redis in production)
    _token_cache: dict = {}

    @property
    def provider_name(self) -> str:
        return "apaleo"

    def _get_credentials(self) -> tuple[str, str]:
        """
        Extract client_id and client_secret from pms_api_key.

        Expected format: "client_id:client_secret"
        """
        api_key = self.hotel.pms_api_key or ""
        if ":" not in api_key:
            raise ValueError(
                "Invalid Apaleo credentials format. Expected 'client_id:client_secret'"
            )
        parts = api_key.split(":", 1)
        if len(parts[0]) < 5 or len(parts[1]) < 10:
            raise ValueError(
                "Apaleo credentials appear incomplete. Please check you copied the full client_id and client_secret."
            )
        return parts[0], parts[1]

    def _get_property_id(self) -> str:
        """Get Apaleo property ID."""
        return self.hotel.pms_property_id or ""

    def _get_access_token(self) -> str:
        """
        Get OAuth 2.0 access token using Client Credentials flow.

        Tokens are cached in memory for 55 minutes (Apaleo tokens expire after 1 hour).
        """
        cache_key = f"apaleo_token_{self.hotel.id}"

        # Check cache
        cached = self._token_cache.get(cache_key)
        if cached:
            token, expires_at = cached
            if datetime.now(timezone.utc) < expires_at:
                return token

        # Request new token
        client_id, client_secret = self._get_credentials()

        data = {
            "grant_type": "client_credentials",
        }

        try:
            response = requests.post(
                self.TOKEN_URL,
                data=data,
                auth=(client_id, client_secret),
                timeout=self.TIMEOUT,
            )
            if response.status_code == 400:
                error_body = response.json() if response.text else {}
                error_type = error_body.get("error", "unknown")
                if error_type == "invalid_client":
                    raise ConnectionError(
                        "Invalid client_id or client_secret. Please verify your Apaleo credentials."
                    )
                raise ConnectionError(f"Apaleo authentication error: {error_type}")
            response.raise_for_status()
            token_data = response.json()

            access_token = token_data["access_token"]
            expires_in = token_data.get("expires_in", 3600)

            # Cache with 5-minute buffer
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in - 300)
            self._token_cache[cache_key] = (access_token, expires_at)

            logger.info(f"Obtained new Apaleo access token for hotel {self.hotel.id}")
            return access_token

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to obtain Apaleo access token for hotel {self.hotel.id}: {e}")
            raise ConnectionError(f"Apaleo authentication failed: {e}")

    def _invalidate_token_cache(self) -> None:
        """Clear cached token for this hotel, forcing a new token fetch."""
        cache_key = f"apaleo_token_{self.hotel.id}"
        if cache_key in self._token_cache:
            del self._token_cache[cache_key]
            logger.info(f"Invalidated Apaleo token cache for hotel {self.hotel.id}")

    def _make_request(self, endpoint: str, params: dict = None, _retry: bool = False) -> dict:
        """
        Make authenticated request to Apaleo API.

        Args:
            endpoint: API endpoint path (e.g., '/booking/v1/reservations')
            params: Query parameters
            _retry: Internal flag to prevent infinite retry loops

        Returns:
            Response JSON

        Raises:
            ConnectionError: If API request fails
        """
        access_token = self._get_access_token()

        url = f"{self.API_BASE_URL}{endpoint}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }

        try:
            response = requests.get(url, params=params, headers=headers, timeout=self.TIMEOUT)

            # Handle 401 Unauthorized - token may have been revoked or expired early
            if response.status_code == 401 and not _retry:
                logger.warning(
                    f"Apaleo token invalid for hotel {self.hotel.id}, fetching new token..."
                )
                self._invalidate_token_cache()
                # Retry with fresh token
                return self._make_request(endpoint, params, _retry=True)

            # Handle rate limiting
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After", "60")
                logger.warning(
                    f"Apaleo rate limit hit for hotel {self.hotel.id}. "
                    f"Retry after {retry_after} seconds."
                )
                raise ConnectionError(f"Apaleo rate limit exceeded. Retry after {retry_after}s")

            response.raise_for_status()
            return response.json()

        except requests.exceptions.Timeout:
            logger.error(f"Apaleo API timeout for hotel {self.hotel.id}")
            raise ConnectionError("Apaleo API timeout")
        except requests.exceptions.RequestException as e:
            logger.error(f"Apaleo API error for hotel {self.hotel.id}: {e}")
            raise ConnectionError(f"Apaleo API request failed: {e}")

    def get_reservations(self, time_window_hours: int = 24) -> list[PMSReservation]:
        """
        Fetch reservations from Apaleo within time window.

        Apaleo API: GET /booking/v1/reservations

        We fetch reservations that:
        - Belong to the configured property
        - Have arrival or departure within the time window
        - Are in relevant statuses (Confirmed, InHouse, CheckedOut)
        """
        property_id = self._get_property_id()
        if not property_id:
            logger.error(f"No Apaleo property ID configured for hotel {self.hotel.id}")
            return []

        # Apaleo requires ISO 8601 format with timezone (Z suffix for UTC)
        # and dateFilter parameter to specify what the from/to dates refer to
        now = datetime.now(timezone.utc)
        start_date = (now - timedelta(hours=time_window_hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
        end_date = (now + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")

        params = {
            "propertyIds": property_id,
            "from": start_date,
            "to": end_date,
            "dateFilter": "Stay",  # Filter by stay dates (arrival to departure)
            "status": "Confirmed,InHouse,CheckedOut",
            "expand": "unit",
            "pageSize": 100,
        }

        try:
            response = self._make_request("/booking/v1/reservations", params=params)
        except ConnectionError as e:
            logger.warning(f"Failed to fetch Apaleo reservations for hotel {self.hotel.id}: {e}")
            return []

        return self._parse_reservations(response)

    def _parse_reservations(self, response: dict) -> list[PMSReservation]:
        """
        Parse Apaleo API response into PMSReservation objects.

        Apaleo response structure:
        {
            "reservations": [...],
            "count": 10
        }
        """
        reservations = response.get("reservations", [])

        parsed = []
        for res in reservations:
            try:
                # Determine state from Apaleo status
                apaleo_status = res.get("status", "")
                state = self._map_status(apaleo_status)
                if state is None:
                    logger.warning(f"Unknown Apaleo status: {apaleo_status}")
                    continue

                # Extract primary guest info
                primary_guest = res.get("primaryGuest", {})
                phone = self._extract_phone(primary_guest)
                if not phone:
                    logger.warning(f"Reservation {res.get('id')} has no phone number, skipping")
                    continue

                # Extract room number from assigned unit
                room_number = self._extract_room_number(res)

                # Parse dates - use actual check-in time if available, else scheduled arrival
                actual_checkin = res.get("checkInTime")
                checkin = self._parse_datetime(
                    actual_checkin if actual_checkin else res.get("arrival")
                )
                checkout = self._parse_datetime(res.get("departure"))

                # Calculate guests count
                adults = res.get("adults", 1)
                children = len(res.get("childrenAges", []))
                guests_count = adults + children

                pms_reservation = PMSReservation(
                    reservation_id=res.get("id", ""),
                    guest_name=self._get_guest_name(primary_guest),
                    guest_phone=phone,
                    guest_email=primary_guest.get("email"),
                    room_number=room_number,
                    state=state,
                    checkin_date=checkin,
                    checkout_date=checkout,
                    preferred_language=self._extract_language(primary_guest),
                )

                parsed.append(pms_reservation)

            except Exception as e:
                logger.error(f"Error parsing Apaleo reservation: {e}", exc_info=True)
                continue

        logger.info(f"Parsed {len(parsed)} reservations from Apaleo for hotel {self.hotel.id}")
        return parsed

    def _map_status(self, apaleo_status: str) -> Optional[ReservationState]:
        """Map Apaleo status to ReservationState."""
        status_map = {
            "Confirmed": ReservationState.CONFIRMED,
            "InHouse": ReservationState.IN_HOUSE,
            "CheckedOut": ReservationState.CHECKED_OUT,
            "Canceled": ReservationState.CANCELLED,
            "NoShow": ReservationState.CANCELLED,  # Treat NoShow as Cancelled
        }
        return status_map.get(apaleo_status)

    def _extract_phone(self, guest: dict) -> Optional[str]:
        """Extract phone number from Apaleo guest data."""
        phone = guest.get("phone")
        if phone:
            return phone.strip()
        return None

    def _get_guest_name(self, guest: dict) -> str:
        """Build full name from Apaleo guest data."""
        first = guest.get("firstName", "")
        last = guest.get("lastName", "")
        title = guest.get("title", "")

        parts = [p for p in [title, first, last] if p]
        return " ".join(parts) or "Unknown Guest"

    def _extract_room_number(self, reservation: dict) -> Optional[str]:
        """
        Extract room number from Apaleo reservation.

        Apaleo returns room in 'unit' field or 'assignedUnits' array.
        """
        # Try direct unit field first
        unit = reservation.get("unit")
        if unit and unit.get("name"):
            return unit.get("name")

        # Fallback to assignedUnits array
        assigned_units = reservation.get("assignedUnits", [])
        if assigned_units:
            unit = assigned_units[0].get("unit", {})
            return unit.get("name")
        return None

    def _extract_language(self, guest: dict) -> Optional[str]:
        """Extract language preference from guest data."""
        # Apaleo stores nationality/language in various fields
        language = guest.get("preferredLanguage") or guest.get("nationalityCountryCode")
        if language:
            return language.lower()[:2]
        return None

    def _parse_datetime(self, dt_string: Optional[str]) -> datetime:
        """Parse Apaleo datetime string to datetime object."""
        if not dt_string:
            return datetime.now(timezone.utc)
        try:
            # Apaleo uses ISO 8601 format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
            if "T" in dt_string:
                return datetime.fromisoformat(dt_string.replace("Z", "+00:00"))
            else:
                return datetime.strptime(dt_string, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except (ValueError, AttributeError):
            logger.warning(f"Failed to parse datetime: {dt_string}")
            return datetime.now(timezone.utc)

    def test_connection(self) -> bool:
        """
        Test connection to Apaleo API.

        Makes a lightweight request to verify credentials work.
        """
        try:
            # Try to get current account info (lightweight endpoint)
            response = self._make_request("/account/v1/accounts/current")
            account_name = response.get("name", "Unknown")
            logger.info(
                f"Apaleo connection test successful for hotel {self.hotel.id}: {account_name}"
            )
            return True
        except ConnectionError as e:
            logger.error(f"Apaleo connection test failed for hotel {self.hotel.id}: {e}")
            return False

    def get_reservation_by_id(self, reservation_id: str) -> Optional[PMSReservation]:
        """
        Fetch a single reservation by ID.

        Useful for webhook processing or on-demand lookups.
        """
        try:
            response = self._make_request(f"/booking/v1/reservations/{reservation_id}")
            reservations = self._parse_reservations({"reservations": [response]})
            return reservations[0] if reservations else None
        except ConnectionError as e:
            logger.error(f"Failed to fetch Apaleo reservation {reservation_id}: {e}")
            return None
