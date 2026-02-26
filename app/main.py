import re

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.api import (
    routes_admin,
    routes_admin_ai_settings,
    routes_admin_integrations,
    routes_admin_notifications,
    routes_admin_staff_settings,
    routes_admin_ui,
    routes_auth,
    routes_health,
    routes_oauth_cloudbeds,
    routes_owner,
    routes_owner_ui,
    routes_public,
    routes_register,
    routes_seo,
    routes_stripe,
    routes_webhook_line,
    routes_webhook_whatsapp,
)
from app.core.config import get_settings
from app.core.logging import setup_logging

settings = get_settings()

# SEO: Server-side meta tag translations removed since only EN is supported
_SEO_META = {}


def _localize_html(html: str, lang: str, page: str) -> str:
    """Replace meta tags in HTML with localized versions for SEO crawlers."""
    meta = _SEO_META.get(page, {}).get(lang)
    if not meta:
        return html

    # html lang attribute
    html = html.replace('<html lang="en"', f'<html lang="{lang}"', 1)

    # title tag
    if "title" in meta:
        html = re.sub(r"<title>[^<]+</title>", f"<title>{meta['title']}</title>", html, count=1)

    # meta description
    if "description" in meta:
        html = re.sub(
            r'<meta name="description"\s+content="[^"]+">',
            f'<meta name="description" content="{meta["description"]}">',
            html,
            count=1,
        )

    # og:title
    if "og_title" in meta:
        html = re.sub(
            r'<meta property="og:title" content="[^"]+">',
            f'<meta property="og:title" content="{meta["og_title"]}">',
            html,
            count=1,
        )

    # og:description
    if "og_description" in meta:
        html = re.sub(
            r'<meta property="og:description"\s+content="[^"]+">',
            f'<meta property="og:description" content="{meta["og_description"]}">',
            html,
            count=1,
        )

    # og:locale - set primary locale
    if "og_locale" in meta:
        html = re.sub(
            r'<meta property="og:locale" content="[^"]+">',
            f'<meta property="og:locale" content="{meta["og_locale"]}">',
            html,
            count=1,
        )

    # twitter:title
    if "twitter_title" in meta:
        html = re.sub(
            r'<meta name="twitter:title" content="[^"]+">',
            f'<meta name="twitter:title" content="{meta["twitter_title"]}">',
            html,
            count=1,
        )

    # twitter:description
    if "twitter_description" in meta:
        html = re.sub(
            r'<meta name="twitter:description"\s+content="[^"]+">',
            f'<meta name="twitter:description" content="{meta["twitter_description"]}">',
            html,
            count=1,
        )

    return html


# Initialize Sentry for error monitoring (if configured)
if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        send_default_pii=False,
        environment=settings.environment,
        traces_sample_rate=0.1,  # 10% of transactions for performance monitoring
    )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        if request.url.path.startswith("/static/") or request.url.path.startswith("/landing/"):
            response.headers["Cache-Control"] = "public, max-age=31536000"
        return response


def create_app() -> FastAPI:
    setup_logging("INFO")
    app = FastAPI(
        title=settings.app_name or "AI Hotel Suite",
        description="Open-Source Framework for Hotel AI Assistants and PMS Integrations. Built with FastAPI.",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    @app.on_event("startup")
    def startup_event():
        """Schedule periodic jobs on app startup."""
        # NOTE: trial check now runs from run_worker.py (_start_trial_check_scheduler)
        # The code below is redundant - kept temporarily for reference
        # try:
        #     from app.workers.queue import schedule_trial_check
        #     schedule_trial_check()
        # except Exception as e:
        #     import logging
        #     logging.getLogger("hotelbot").warning(f"Failed to schedule trial check: {e}")
        pass

    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(SecurityHeadersMiddleware)
    # Trust only configured proxy hosts (default: localhost only; set TRUSTED_PROXY_HOSTS for Docker/Traefik)
    trusted = (
        [h.strip() for h in settings.trusted_proxy_hosts.split(",") if h.strip()]
        if settings.trusted_proxy_hosts
        else ["127.0.0.1"]
    )
    app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=trusted)

    # Root redirect
    @app.get("/")
    async def root_redirect():
        return RedirectResponse(url="/ui/admin/login")

    # Redirect /admin/login to /ui/admin/login
    @app.get("/admin/login")
    async def admin_login_redirect():
        return RedirectResponse(url="/ui/admin/login")

    app.include_router(routes_health.router)
    app.include_router(routes_auth.router)
    app.include_router(routes_webhook_whatsapp.router)
    app.include_router(routes_webhook_line.router)
    app.include_router(routes_admin.router)
    app.include_router(routes_admin_integrations.router)
    app.include_router(routes_admin_notifications.router)
    app.include_router(routes_admin_staff_settings.router)
    app.include_router(routes_admin_ai_settings.router)
    app.include_router(routes_admin_ui.router)
    app.include_router(routes_oauth_cloudbeds.router)
    app.include_router(routes_owner.router)
    app.include_router(routes_owner_ui.router)
    app.include_router(routes_register.router)
    app.include_router(routes_stripe.router)
    app.include_router(routes_seo.router)
    app.include_router(routes_public.router)
    app.mount("/static", StaticFiles(directory="static"), name="static")

    return app


app = create_app()
