"""OAuth 2.0 routes for Cloudbeds PMS integration."""

import json
import logging
import secrets
from urllib.parse import quote, urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.api.routes_admin import require_staff
from app.api.routes_admin_integrations import _ensure_default_journeys
from app.core.config import get_settings
from app.core.db import get_db
from app.core.security import _redis as redis_client
from app.models import Hotel, StaffUser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/oauth/cloudbeds", tags=["oauth"])

# Cloudbeds OAuth endpoints
CLOUDBEDS_AUTH_URL = "https://hotels.cloudbeds.com/api/v1.1/oauth"
CLOUDBEDS_TOKEN_URL = "https://hotels.cloudbeds.com/api/v1.1/access_token"


def _get_redirect_uri(request: Request) -> str:
    """Build the OAuth callback URL."""
    settings = get_settings()
    # Use public_api_base_url (set on server), fallback to base_url, then request
    base_url = (
        settings.public_api_base_url or settings.base_url or str(request.base_url).rstrip("/")
    )
    # Router is mounted at /oauth/cloudbeds (no /api prefix)
    return f"{base_url}/oauth/cloudbeds/callback"


@router.get("/authorize/{hotel_id}")
def cloudbeds_authorize(
    hotel_id: int,
    request: Request,
    db: Session = Depends(get_db),
    token: str = Query(None, description="User auth token to preserve after OAuth"),
):
    """
    Start OAuth flow for Cloudbeds.

    Redirects admin to Cloudbeds login page.
    After approval, Cloudbeds redirects back to /callback with auth code.
    """
    settings = get_settings()

    # Verify hotel exists
    hotel = db.query(Hotel).filter(Hotel.id == hotel_id).first()
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")

    # Check if Cloudbeds client credentials are configured
    client_id = settings.cloudbeds_client_id
    if not client_id:
        raise HTTPException(
            status_code=500,
            detail="Cloudbeds client_id not configured. Set CLOUDBEDS_CLIENT_ID in .env",
        )

    # Generate state token for CSRF protection
    # Store hotel_id and user_token in Redis (expires in 5 minutes)
    state = secrets.token_urlsafe(32)
    if not redis_client:
        raise HTTPException(status_code=500, detail="Redis unavailable for OAuth state storage")
    redis_client.setex(
        f"oauth:{state}", 300, json.dumps({"hotel_id": hotel_id, "user_token": token})
    )

    # Build authorization URL
    redirect_uri = _get_redirect_uri(request)
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "read:reservation read:guest",
        "state": state,
    }

    auth_url = f"{CLOUDBEDS_AUTH_URL}?{urlencode(params)}"
    logger.info(f"Redirecting hotel {hotel_id} to Cloudbeds OAuth: {auth_url}")

    return RedirectResponse(url=auth_url)


@router.get("/callback")
async def cloudbeds_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
):
    """
    OAuth callback from Cloudbeds.

    Exchanges authorization code for access token and saves to hotel settings.
    """
    settings = get_settings()

    # Verify state token and retrieve stored data from Redis
    raw = redis_client.getdel(f"oauth:{state}") if redis_client else None
    state_data = json.loads(raw) if raw else None
    if not state_data:
        raise HTTPException(status_code=400, detail="Invalid or expired state token")
    hotel_id = state_data.get("hotel_id")
    user_token = state_data.get("user_token")

    hotel = db.query(Hotel).filter(Hotel.id == hotel_id).first()
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")

    # Exchange code for tokens
    redirect_uri = _get_redirect_uri(request)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                CLOUDBEDS_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "client_id": settings.cloudbeds_client_id,
                    "client_secret": settings.cloudbeds_client_secret,
                    "redirect_uri": redirect_uri,
                    "code": code,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            token_data = response.json()
            logger.info(f"Cloudbeds token response keys: {list(token_data.keys())}")
    except httpx.HTTPError as e:
        logger.error(f"Cloudbeds token exchange failed for hotel {hotel_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to exchange authorization code")

    # Save tokens to hotel settings
    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    # Property ID might be in 'property_id', 'propertyID', or 'resources' object
    property_id = (
        token_data.get("property_id")
        or token_data.get("propertyID")
        or token_data.get("propertyId")
    )
    # Check if it's in resources (can be list or dict)
    # Cloudbeds returns: {"resources": [{"type": "property", "id": "320133"}]}
    resources = token_data.get("resources")
    if not property_id and resources:
        if isinstance(resources, list) and len(resources) > 0:
            # Resources is a list of properties
            first_resource = resources[0] if isinstance(resources[0], dict) else {}
            property_id = (
                first_resource.get("id")
                or first_resource.get("property_id")
                or first_resource.get("propertyID")
                or first_resource.get("propertyId")
            )
            logger.info(f"Found property_id in resources list: {property_id}")
        elif isinstance(resources, dict):
            property_id = (
                resources.get("id") or resources.get("property_id") or resources.get("propertyID")
            )
            logger.info(f"Found property_id in resources dict: {property_id}")

    if not access_token:
        raise HTTPException(status_code=500, detail="No access token received")

    # Update hotel settings
    hotel_settings = hotel.settings or {}
    hotel_settings["cloudbeds_access_token"] = access_token
    hotel_settings["cloudbeds_refresh_token"] = refresh_token
    hotel_settings["cloudbeds_property_id"] = property_id
    hotel.settings = hotel_settings
    flag_modified(hotel, "settings")  # Force SQLAlchemy to detect JSON changes

    # Set PMS type to cloudbeds
    hotel.pms_type = "cloudbeds"
    hotel.pms_property_id = property_id
    hotel.pms_api_key = "OAUTH"  # Marker that we use OAuth

    db.add(hotel)
    db.commit()

    # Auto-create default Journeys when PMS is configured via OAuth
    try:
        _ensure_default_journeys(db, hotel.id)
        logger.info(f"Created default journeys for hotel {hotel.id}")
    except Exception as e:
        logger.error(f"Failed to create default journeys for hotel {hotel.id}: {e}")

    logger.info(f"✅ Cloudbeds OAuth successful for hotel {hotel_id}, property {property_id}")

    # Redirect back to integrations page with success message
    # Token is preserved via Redis temporary code (not exposed in URL)
    redirect_url = "/ui/admin/settings/integrations?cloudbeds_connected=1"
    if user_token and redis_client:
        return_code = secrets.token_urlsafe(32)
        redis_client.setex(f"oauth_return:{return_code}", 300, user_token)
        redirect_url += f"&code={quote(return_code, safe='')}"
    return RedirectResponse(url=redirect_url, status_code=303)


@router.post("/refresh/{hotel_id}")
async def cloudbeds_refresh_token(
    hotel_id: int,
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(require_staff),
):
    """
    Refresh Cloudbeds access token.

    Called automatically when access token expires.
    """
    settings = get_settings()

    hotel = db.query(Hotel).filter(Hotel.id == hotel_id).first()
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")

    hotel_settings = hotel.settings or {}
    refresh_token = hotel_settings.get("cloudbeds_refresh_token")

    if not refresh_token:
        raise HTTPException(status_code=400, detail="No refresh token available")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                CLOUDBEDS_TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "client_id": settings.cloudbeds_client_id,
                    "client_secret": settings.cloudbeds_client_secret,
                    "refresh_token": refresh_token,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            token_data = response.json()
    except httpx.HTTPError as e:
        logger.error(f"Cloudbeds token refresh failed for hotel {hotel_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to refresh token")

    # Update tokens
    new_access_token = token_data.get("access_token")
    new_refresh_token = token_data.get("refresh_token", refresh_token)

    hotel_settings["cloudbeds_access_token"] = new_access_token
    hotel_settings["cloudbeds_refresh_token"] = new_refresh_token
    hotel.settings = hotel_settings

    db.add(hotel)
    db.commit()

    logger.info(f"✅ Cloudbeds token refreshed for hotel {hotel_id}")

    return {"success": True, "message": "Token refreshed"}


@router.delete("/disconnect/{hotel_id}")
def cloudbeds_disconnect(
    hotel_id: int,
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(require_staff),
):
    """
    Disconnect Cloudbeds integration.

    Removes OAuth tokens from hotel settings.
    """
    hotel = db.query(Hotel).filter(Hotel.id == hotel_id).first()
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")

    # Remove Cloudbeds tokens from settings
    hotel_settings = hotel.settings or {}
    hotel_settings.pop("cloudbeds_access_token", None)
    hotel_settings.pop("cloudbeds_refresh_token", None)
    hotel_settings.pop("cloudbeds_property_id", None)
    hotel.settings = hotel_settings

    # Clear PMS if it was cloudbeds
    if hotel.pms_type == "cloudbeds":
        hotel.pms_type = None
        hotel.pms_property_id = None
        hotel.pms_api_key = None

    db.add(hotel)
    db.commit()

    logger.info(f"🔌 Cloudbeds disconnected for hotel {hotel_id}")

    return {"success": True, "message": "Cloudbeds disconnected"}
