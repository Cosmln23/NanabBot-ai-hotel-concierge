from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/ui/owner", tags=["owner-ui"])

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "templates" / "owner"


def _render(name: str) -> HTMLResponse:
    path = TEMPLATES_DIR / name
    if not path.exists():
        return HTMLResponse("Template not found", status_code=404)
    return HTMLResponse(path.read_text(encoding="utf-8"))


@router.get("/dashboard")
def dashboard_page():
    return _render("dashboard.html")


@router.get("/login")
def login_page():
    return _render("login.html")


@router.get("/hotels/{hotel_id}/stats")
def hotel_stats_page(hotel_id: int):
    return _render("hotel_stats.html")


@router.get("/hotel/{hotel_id}/setup")
def hotel_setup_page(hotel_id: int):
    return _render("hotel_setup.html")


@router.get("/platform-settings")
def platform_settings_page():
    return _render("platform_settings.html")
