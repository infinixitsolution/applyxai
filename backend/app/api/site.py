"""Public site content (CMS). No authentication."""

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.errors import ok
from backend.app.services import platform_settings_service as ps
from backend.app.services import site_seo_service

router = APIRouter(prefix="/site", tags=["site"])


@router.get("/public", summary="Public branding, banner, landing copy, legal text, and SEO")
def public_site(db: Session = Depends(get_db)):
    return ok(ps.get_public_site(db))


@router.get("/robots.txt", summary="Robots.txt from CMS SEO settings", response_class=PlainTextResponse)
def robots_txt(db: Session = Depends(get_db)):
    return PlainTextResponse(site_seo_service.robots_txt(db), media_type="text/plain; charset=utf-8")


@router.get("/sitemap.xml", summary="Sitemap for public marketing pages")
def sitemap_xml(db: Session = Depends(get_db)):
    return Response(content=site_seo_service.sitemap_xml(db), media_type="application/xml; charset=utf-8")
