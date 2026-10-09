"""Robots.txt and sitemap.xml from CMS SEO settings."""

from __future__ import annotations

from xml.sax.saxutils import escape

from sqlalchemy.orm import Session

from backend.app.services import platform_settings_service as ps

_PUBLIC_PATHS = (
    ("/", "home", "daily", "1.0"),
    ("/login", "login", "monthly", "0.4"),
    ("/register", "register", "monthly", "0.5"),
    ("/privacy", "privacy", "yearly", "0.3"),
    ("/terms", "terms", "yearly", "0.3"),
    ("/refund-policy", "refund", "yearly", "0.3"),
)


def _seo(db: Session) -> dict:
    cms = ps.get_effective_cms(db)
    return cms.get("seo") or {}


def robots_txt(db: Session) -> str:
    seo = _seo(db)
    base = (seo.get("site_url") or "https://applyxai.com").rstrip("/")
    allow_index = bool(seo.get("robots_index", True))
    lines = ["User-agent: *"]
    if allow_index:
        lines.append("Allow: /")
        for path in (seo.get("robots_disallow") or ["/app/", "/admin/", "/onboarding"]):
            p = str(path).strip()
            if p:
                lines.append(f"Disallow: {p}")
    else:
        lines.append("Disallow: /")
    lines.append(f"Sitemap: {base}/sitemap.xml")
    return "\n".join(lines) + "\n"


def sitemap_xml(db: Session) -> str:
    seo = _seo(db)
    base = (seo.get("site_url") or "https://applyxai.com").rstrip("/")
    pages = seo.get("pages") or {}
    allow_index = bool(seo.get("robots_index", True))
    urls: list[str] = []
    if allow_index:
        for path, key, _freq, priority in _PUBLIC_PATHS:
            meta = pages.get(key) or {}
            if meta.get("noindex"):
                continue
            loc = escape(f"{base}{path if path != '/' else '/'}")
            urls.append(
                f"  <url>\n    <loc>{loc}</loc>\n    <changefreq>{_freq}</changefreq>\n"
                f"    <priority>{priority}</priority>\n  </url>"
            )
    body = "\n".join(urls)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{body}\n</urlset>\n"
    )
