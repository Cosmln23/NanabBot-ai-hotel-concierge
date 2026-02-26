"""
SEO routes for robots.txt, sitemap.xml, and verification files.
"""

from datetime import date

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, PlainTextResponse, Response

from app.core.config import get_settings

router = APIRouter(tags=["seo"])
settings = get_settings()


@router.get("/google69d40a862eb08f4b.html", response_class=HTMLResponse)
def google_verification():
    """Serve Google Search Console verification file."""
    return HTMLResponse(content="google-site-verification: google69d40a862eb08f4b.html")


@router.get("/robots.txt", response_class=PlainTextResponse)
def robots_txt():
    """Serve robots.txt for search engine crawlers."""
    base_url = settings.public_api_base_url or "https://yourdomain.com"
    content = f"""User-agent: *
Allow: /
Disallow: /api/
Disallow: /ui/admin/
Disallow: /ui/owner/
Disallow: /auth/
Disallow: /oauth/
Disallow: /upgrade
Disallow: /upgrade-pro
Disallow: /webhook/

Sitemap: {base_url}/sitemap.xml
"""
    return PlainTextResponse(content=content, media_type="text/plain")


@router.get("/sitemap.xml")
def sitemap_xml():
    """Serve sitemap.xml for search engine indexing."""
    base_url = settings.public_api_base_url or "https://yourdomain.com"
    today = date.today().isoformat()

    pages = [
        {"loc": f"{base_url}/", "priority": "1.0", "changefreq": "weekly"},
        {"loc": f"{base_url}/contact.html", "priority": "0.8", "changefreq": "monthly"},
        {"loc": f"{base_url}/register", "priority": "0.8", "changefreq": "monthly"},
        {"loc": f"{base_url}/privacy", "priority": "0.3", "changefreq": "yearly"},
        {"loc": f"{base_url}/terms", "priority": "0.3", "changefreq": "yearly"},
        {"loc": f"{base_url}/support", "priority": "0.5", "changefreq": "monthly"},
    ]

    hreflang_pages = {
        f"{base_url}/": [
            {"lang": "en", "href": f"{base_url}/"},
            {"lang": "ro", "href": f"{base_url}/?lang=ro"},
            {"lang": "th", "href": f"{base_url}/?lang=th"},
            {"lang": "x-default", "href": f"{base_url}/"},
        ],
        f"{base_url}/contact.html": [
            {"lang": "en", "href": f"{base_url}/contact.html"},
            {"lang": "ro", "href": f"{base_url}/contact.html?lang=ro"},
            {"lang": "th", "href": f"{base_url}/contact.html?lang=th"},
            {"lang": "x-default", "href": f"{base_url}/contact.html"},
        ],
        f"{base_url}/register": [
            {"lang": "en", "href": f"{base_url}/register"},
            {"lang": "ro", "href": f"{base_url}/register?lang=ro"},
            {"lang": "th", "href": f"{base_url}/register?lang=th"},
            {"lang": "x-default", "href": f"{base_url}/register"},
        ],
    }

    urls = ""
    for page in pages:
        urls += f"""  <url>
    <loc>{page['loc']}</loc>
    <lastmod>{today}</lastmod>
    <changefreq>{page['changefreq']}</changefreq>
    <priority>{page['priority']}</priority>"""
        if page["loc"] in hreflang_pages:
            for alt in hreflang_pages[page["loc"]]:
                urls += f"""
    <xhtml:link rel="alternate" hreflang="{alt['lang']}" href="{alt['href']}" />"""
        urls += """
  </url>
"""

    content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:xhtml="http://www.w3.org/1999/xhtml">
{urls}</urlset>
"""
    return Response(content=content, media_type="application/xml")
