"""Mews PMS API integration client.

Updated to use Mews Connector API v2023-06-06.
Documentation: https://docs.mews.com/connector-api/
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import requests

from app.core.config import get_settings
from app.services.pms.base import PMSProvider, PMSReservation, ReservationState

logger = logging.getLogger(__name__)


class MewsClient(PMSProvider):
    """
    Mews PMS API client implementation.

    Documentation: https://docs.mews.com/connector-api/

    API Version: 2023-06-06 (latest, non-deprecated)

    Supports both Production and Demo environments:
    - Production: https://api.mews.com (requires real credentials)
    - Demo: https://api.mews-demo.com (use "DEMO_MODE" as API key)

    Note: The new API (2023-06-06) requires 3 separate API calls:
    1. reservations/getAll/2023-06-06 - Get reservations
    2. customers/getAll - Get customer details (name, phone, email)
    3. resources/getAll - Get room numbers
    """

    # Environment URLs
    DEMO_BASE_URL = "https://api.mews-demo.com"
    PROD_BASE_URL = "https://api.mews.com"

    # Certification credentials (received from Mews 28 Jan 2026)
    DEMO_CLIENT_TOKEN = "9381AB282F844CD9A2F4AD200158E7BC-D27113FA792B0855F87D0F93E9E1D71"
    DEMO_ACCESS_TOKEN = "B811B453B8144A73B80CAD6E00805D62-B7899D9C0F3C579C86621146C4C74A2"

    TIMEOUT = 30  # seconds

    @property
    def provider_name(self) -> str:
        return "mews"

    def _is_demo_mode(self) -> bool:
        """Check if using Mews Demo environment."""
        api_key = self.hotel.pms_api_key or ""
        # Demo mode if: explicit "DEMO_MODE" or the official demo AccessToken
        return api_key == "DEMO_MODE" or api_key == self.DEMO_ACCESS_TOKEN

    def _make_request(self, endpoint: str, payload: dict) -> dict:
        """
        Make authenticated request to Mews API.

        Args:
            endpoint: API endpoint path (e.g., '/api/connector/v1/reservations/getAll')
            payload: JSON payload

        Returns:
            Response JSON

        Raises:
            ConnectionError: If API request fails
        """
        is_demo = self._is_demo_mode()
        base_url = self.DEMO_BASE_URL if is_demo else self.PROD_BASE_URL

        url = f"{base_url}{endpoint}"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        # Mews requires both ClientToken and AccessToken in payload
        payload["ClientToken"] = self.DEMO_CLIENT_TOKEN  # Same for demo and prod (app identifier)
        payload["AccessToken"] = self.DEMO_ACCESS_TOKEN if is_demo else self.hotel.pms_api_key
        payload["Client"] = "AI Hotel Suite"  # Required for certification

        if is_demo:
            logger.info(f"🧪 MEWS DEMO MODE: Using {base_url}")

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=self.TIMEOUT)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            logger.error(f"Mews API timeout for hotel {self.hotel.id}")
            raise ConnectionError("Mews API timeout")
        except requests.exceptions.RequestException as e:
            logger.error(f"Mews API error for hotel {self.hotel.id}: {e}")
            raise ConnectionError(f"Mews API request failed: {e}")

    def _fetch_customers(self, account_ids: list[str]) -> dict:
        """
        Fetch customer details by AccountIds.

        Args:
            account_ids: List of customer/account IDs from reservations

        Returns:
            Dict mapping customer ID to customer data
        """
        if not account_ids:
            return {}

        # Mews allows max 1000 IDs per request
        payload = {"CustomerIds": account_ids[:1000], "Limitation": {"Count": 1000}}

        try:
            response = self._make_request("/api/connector/v1/customers/getAll", payload)
            customers = response.get("Customers", [])
            logger.info(f"Fetched {len(customers)} customers from Mews")
            return {c["Id"]: c for c in customers}
        except ConnectionError as e:
            logger.warning(f"Failed to fetch Mews customers: {e}")
            return {}

    def _fetch_resources(self, resource_ids: list[str]) -> dict:
        """
        Fetch resource (room) details by IDs.

        Args:
            resource_ids: List of resource IDs from reservations

        Returns:
            Dict mapping resource ID to resource data (includes Name = room number)
        """
        if not resource_ids:
            return {}

        payload = {
            "ResourceIds": resource_ids[:1000],
            "Extent": {"Resources": True},
            "Limitation": {"Count": 1000},
        }

        try:
            response = self._make_request("/api/connector/v1/resources/getAll", payload)
            resources = response.get("Resources", [])
            logger.info(f"Fetched {len(resources)} resources (rooms) from Mews")
            return {r["Id"]: r for r in resources}
        except ConnectionError as e:
            logger.warning(f"Failed to fetch Mews resources: {e}")
            return {}

    def get_reservations(self, time_window_hours: int = 24) -> list[PMSReservation]:
        """
        Fetch reservations from Mews within time window.

        Mews API v2023-06-06 (3 separate calls):
        1. POST /api/connector/v1/reservations/getAll/2023-06-06
        2. POST /api/connector/v1/customers/getAll
        3. POST /api/connector/v1/resources/getAll

        We fetch reservations that have:
        - State: Started (checked in) or Processed (checked out)
        - CollidingUtc within the time window

        SIMULATION_MODE: If API key is "SIMULATION_MODE", loads mock data from JSON file.
        """
        # SIMULATION MODE: Load mock data from JSON
        if self.hotel.pms_api_key == "SIMULATION_MODE":
            logger.info(f"🎮 SIMULATION MODE activated for hotel {self.hotel.id}")
            return self._load_simulation_data()

        # Normal Mews API flow (v2023-06-06)
        now = datetime.now(timezone.utc)
        start_time = now - timedelta(hours=time_window_hours)

        # NEW PAYLOAD STRUCTURE for v2023-06-06
        payload = {
            "CollidingUtc": {
                "StartUtc": start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "EndUtc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
            "States": ["Started", "Processed"],  # Checked-in and Checked-out
            "Limitation": {"Count": 100},  # Pagination required in new API
        }

        try:
            # STEP 1: Get reservations
            response = self._make_request(
                "/api/connector/v1/reservations/getAll/2023-06-06", payload
            )
            reservations = response.get("Reservations", [])
            logger.info(f"Fetched {len(reservations)} reservations from Mews")

            if not reservations:
                return []

            # Collect IDs for batch fetching
            account_ids = list(set(r["AccountId"] for r in reservations if r.get("AccountId")))
            resource_ids = list(
                set(r["AssignedResourceId"] for r in reservations if r.get("AssignedResourceId"))
            )

            # STEP 2: Get customers (name, phone, email)
            customers = self._fetch_customers(account_ids)

            # STEP 3: Get resources (room numbers)
            resources = self._fetch_resources(resource_ids)

        except ConnectionError as e:
            logger.warning(f"Failed to fetch Mews reservations for hotel {self.hotel.id}: {e}")
            return []

        return self._parse_reservations(reservations, customers, resources)

    def _parse_reservations(
        self, reservations: list, customers: dict, resources: dict
    ) -> list[PMSReservation]:
        """
        Parse Mews API response into PMSReservation objects.

        Args:
            reservations: List of reservation dicts from reservations/getAll
            customers: Dict mapping AccountId to customer data
            resources: Dict mapping ResourceId to resource data (room)

        Returns:
            List of PMSReservation objects
        """
        parsed = []
        for res in reservations:
            try:
                # Get customer data using AccountId (new API uses AccountId, not CustomerId)
                account_id = res.get("AccountId")
                customer = customers.get(account_id, {})

                # Get room number from resources
                resource_id = res.get("AssignedResourceId")
                resource = resources.get(resource_id, {})
                room_number = resource.get("Name")  # Room name/number in Mews

                # Determine state
                mews_state = res.get("State")
                if mews_state == "Started":
                    state = ReservationState.IN_HOUSE
                elif mews_state == "Processed":
                    state = ReservationState.CHECKED_OUT
                elif mews_state == "Confirmed":
                    state = ReservationState.CONFIRMED
                elif mews_state == "Canceled":
                    state = ReservationState.CANCELLED
                else:
                    logger.warning(f"Unknown Mews state: {mews_state}")
                    continue

                # Extract phone (Mews may have multiple phones)
                phone = self._extract_phone(customer)
                if not phone:
                    logger.warning(f"Reservation {res.get('Id')} has no phone number, skipping")
                    continue

                # Parse dates - NEW FIELD NAMES in v2023-06-06
                checkin = self._parse_datetime(res.get("ScheduledStartUtc") or res.get("StartUtc"))
                checkout = self._parse_datetime(res.get("ScheduledEndUtc") or res.get("EndUtc"))

                pms_reservation = PMSReservation(
                    reservation_id=res.get("Id", ""),
                    guest_name=self._get_guest_name(customer),
                    guest_phone=phone,
                    guest_email=customer.get("Email"),
                    room_number=room_number,
                    state=state,
                    checkin_date=checkin,
                    checkout_date=checkout,
                    preferred_language=(customer.get("LanguageCode") or "en").lower()[:2],
                )

                parsed.append(pms_reservation)

            except Exception as e:
                logger.error(f"Error parsing Mews reservation: {e}", exc_info=True)
                continue

        logger.info(f"Parsed {len(parsed)} reservations from Mews for hotel {self.hotel.id}")
        return parsed

    def _extract_phone(self, customer: dict) -> Optional[str]:
        """Extract phone number from Mews customer data."""
        # Mews stores phone in customer.Phone or customer.Telephone
        phone = customer.get("Phone") or customer.get("Telephone")
        if phone:
            return phone.strip()
        return None

    def _get_guest_name(self, customer: dict) -> str:
        """Build full name from Mews customer data."""
        first = customer.get("FirstName", "")
        last = customer.get("LastName", "")
        title = customer.get("Title", "")

        parts = [p for p in [title, first, last] if p]
        return " ".join(parts) or "Unknown Guest"

    def _parse_datetime(self, dt_string: Optional[str]) -> datetime:
        """Parse ISO datetime string to datetime object."""
        if not dt_string:
            return datetime.now(timezone.utc)
        try:
            # Mews uses ISO 8601 format
            return datetime.fromisoformat(dt_string.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            logger.warning(f"Failed to parse datetime: {dt_string}")
            return datetime.now(timezone.utc)

    def _load_simulation_data(self) -> list[PMSReservation]:
        """
        Load mock PMS data from JSON file for testing.

        The property_id field is used as the target room number.
        The phone number of the guest in that room is replaced with the real test number.
        """
        # Path to mock data file
        mock_file = Path(__file__).resolve().parents[3] / "mock_pms_data.json"

        if not mock_file.exists():
            logger.error(f"Mock PMS data file not found: {mock_file}")
            return []

        # Load mock data
        try:
            with open(mock_file, "r", encoding="utf-8") as f:
                mock_guests = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load mock PMS data: {e}")
            return []

        # Get target room and real phone number
        target_room = self.hotel.pms_property_id  # User sets this in UI
        settings = get_settings()
        real_phone = getattr(settings, "pms_simulation_test_phone", None)

        if not real_phone:
            logger.warning(
                "PMS_SIMULATION_TEST_PHONE not set; mock data will keep original phone values."
            )
            real_phone = None

        logger.info(
            f"🎯 Target Room: {target_room} | Real Phone: {real_phone or 'original from mock data'}"
        )

        # Process mock guests and inject real phone into target room
        reservations = []
        for guest in mock_guests:
            room = guest.get("room")
            phone = guest.get("phone")

            # MAGIC: Replace phone for target room
            if room == target_room and real_phone:
                logger.info(f"✨ INJECTING real phone into Room {room}: {phone} → {real_phone}")
                phone = real_phone

            # Convert to PMSReservation
            try:
                checkin = datetime.fromisoformat(guest.get("checkin", "2025-12-05"))
                checkout = datetime.fromisoformat(guest.get("checkout", "2025-12-10"))

                reservation = PMSReservation(
                    reservation_id=f"SIM-{room}",
                    guest_name=guest.get("name", "Unknown"),
                    guest_phone=phone,
                    guest_email=guest.get("email"),
                    room_number=room,
                    state=ReservationState.IN_HOUSE,
                    checkin_date=checkin,
                    checkout_date=checkout,
                    preferred_language=None,
                )
                reservations.append(reservation)
            except Exception as e:
                logger.error(f"Error parsing mock guest {guest}: {e}")
                continue

        logger.info(f"🎮 Loaded {len(reservations)} simulated reservations")
        return reservations

    def test_connection(self) -> bool:
        """
        Test connection to Mews API.

        Makes a lightweight request to verify credentials.
        """
        # SIMULATION MODE: Always return True
        if self.hotel.pms_api_key == "SIMULATION_MODE":
            logger.info("🎮 SIMULATION MODE: Connection test passed")
            return True

        is_demo = self._is_demo_mode()
        payload = {
            "Client": "AI Hotel Suite Hotel Bot Test",
        }

        try:
            # Try to fetch configuration (lightweight endpoint)
            self._make_request("/api/connector/v1/configuration/get", payload)
            mode = "DEMO" if is_demo else "Production"
            logger.info(f"✅ Mews {mode} connection test successful for hotel {self.hotel.id}")
            return True
        except ConnectionError as e:
            logger.error(f"Mews connection test failed for hotel {self.hotel.id}: {e}")
            return False
