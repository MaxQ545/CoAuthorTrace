"""
Admin dashboard API endpoints: login, visitor tracking, analytics, and crawl management.
"""
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, Request
from pydantic import BaseModel
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from config.settings import settings
from src.api.auth import create_access_token, require_admin, verify_password
from src.database.models import (
    Author,
    CrawlTarget,
    InstitutionCrawlState,
    PageVisit,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# IP geolocation — GeoLite2 local DB with ip-api.com online fallback
# ---------------------------------------------------------------------------
_geoip_reader = None
_geoip_checked = False


def _get_geoip_reader():
    global _geoip_reader, _geoip_checked
    if not _geoip_checked:
        _geoip_checked = True
        db_path = Path(settings.admin.geoip_db_path)
        if not db_path.is_absolute():
            db_path = settings.project_root / db_path
        if db_path.exists():
            try:
                import geoip2.database
                _geoip_reader = geoip2.database.Reader(str(db_path))
                logger.info("GeoIP database loaded from %s", db_path)
            except Exception as e:
                logger.warning("Failed to load GeoIP database: %s", e)
    return _geoip_reader


def _resolve_region(ip: str) -> Optional[str]:
    if not ip or ip in ("127.0.0.1", "::1", "unknown"):
        return None
    # Try local GeoLite2 first
    reader = _get_geoip_reader()
    if reader is not None:
        try:
            resp = reader.city(ip)
            parts = [p for p in [
                resp.city.name if resp.city else None,
                resp.country.name if resp.country else None,
            ] if p]
            if parts:
                return ", ".join(parts)
        except Exception:
            pass
    # Fallback: Baidu IP API (accurate for Chinese IPs, no key required)
    try:
        r = httpx.get(
            "https://opendata.baidu.com/api.php",
            params={"query": ip, "co": "", "resource_id": "6006", "oe": "utf8"},
            timeout=3,
        )
        if r.status_code == 200:
            data = r.json()
            items = data.get("data", [])
            if items and items[0].get("location"):
                return items[0]["location"]
    except Exception:
        pass
    return None


# Database session dependency (shared)
from src.api.deps import get_db as _get_db


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------
class LoginRequest(BaseModel):
    password: str


class TrackRequest(BaseModel):
    path: str
    author_id: Optional[str] = None


class CrawlTargetRequest(BaseModel):
    institution_id: str
    institution_name: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/login")
async def admin_login(body: LoginRequest):
    """Authenticate with admin password and receive a JWT."""
    if not verify_password(body.password):
        return {"ok": False, "error": "Invalid password"}
    token = create_access_token()
    return {"ok": True, "token": token}


@router.post("/track")
async def track_visit(body: TrackRequest, request: Request, db: Session = Depends(_get_db)):
    """Record a page visit (fire-and-forget from frontend)."""
    try:
        ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        if not ip:
            ip = request.client.host if request.client else "unknown"
        region = _resolve_region(ip)
        visit = PageVisit(
            ip_address=ip,
            region=region,
            path=body.path,
            author_id=body.author_id,
            user_agent=request.headers.get("user-agent"),
        )
        db.add(visit)
        db.commit()
    except Exception as e:
        logger.debug("track_visit error: %s", e)
        db.rollback()
    return {"ok": True}


@router.get("/analytics")
async def get_analytics(
    days: int = 30,
    _admin: str = Depends(require_admin),
    db: Session = Depends(_get_db),
):
    """Return visitor analytics data for the admin dashboard."""
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())

    # Summary counts
    total = db.query(func.count(PageVisit.id)).filter(PageVisit.timestamp >= since).scalar() or 0
    unique_ips = (
        db.query(func.count(func.distinct(PageVisit.ip_address)))
        .filter(PageVisit.timestamp >= since)
        .scalar()
        or 0
    )
    today_count = (
        db.query(func.count(PageVisit.id)).filter(PageVisit.timestamp >= today_start).scalar() or 0
    )
    week_count = (
        db.query(func.count(PageVisit.id)).filter(PageVisit.timestamp >= week_start).scalar() or 0
    )

    # Daily visits
    daily_rows = (
        db.query(
            func.date(PageVisit.timestamp).label("day"),
            func.count(PageVisit.id).label("count"),
        )
        .filter(PageVisit.timestamp >= since)
        .group_by(text("day"))
        .order_by(text("day"))
        .all()
    )
    daily_visits = [{"date": str(r.day), "count": r.count} for r in daily_rows]

    # Top pages (join author name)
    top_pages_rows = (
        db.query(
            PageVisit.path,
            PageVisit.author_id,
            func.count(PageVisit.id).label("count"),
            Author.display_name,
        )
        .outerjoin(Author, PageVisit.author_id == Author.id)
        .filter(PageVisit.timestamp >= since)
        .group_by(PageVisit.path, PageVisit.author_id, Author.display_name)
        .order_by(text("count DESC"))
        .limit(20)
        .all()
    )
    top_pages = [
        {
            "path": r.path,
            "author_id": r.author_id,
            "author_name": r.display_name,
            "count": r.count,
        }
        for r in top_pages_rows
    ]

    # Top regions
    top_regions_rows = (
        db.query(
            PageVisit.region,
            func.count(PageVisit.id).label("count"),
        )
        .filter(PageVisit.timestamp >= since, PageVisit.region.isnot(None))
        .group_by(PageVisit.region)
        .order_by(text("count DESC"))
        .limit(20)
        .all()
    )
    top_regions = [{"region": r.region, "count": r.count} for r in top_regions_rows]

    # Recent visits
    recent_rows = (
        db.query(PageVisit)
        .order_by(PageVisit.timestamp.desc())
        .limit(50)
        .all()
    )
    recent_visits = [
        {
            "ip": r.ip_address,
            "region": r.region,
            "path": r.path,
            "author_id": r.author_id,
            "user_agent": r.user_agent,
            "timestamp": r.timestamp.isoformat() if r.timestamp else None,
        }
        for r in recent_rows
    ]

    return {
        "summary": {
            "total": total,
            "unique_ips": unique_ips,
            "today": today_count,
            "this_week": week_count,
        },
        "daily_visits": daily_visits,
        "top_pages": top_pages,
        "top_regions": top_regions,
        "recent_visits": recent_visits,
    }


@router.get("/crawl/status")
async def get_crawl_status(
    _admin: str = Depends(require_admin),
    db: Session = Depends(_get_db),
):
    """Return per-institution crawl status."""
    rows = db.query(InstitutionCrawlState).order_by(InstitutionCrawlState.institution_name).all()
    institutions = [
        {
            "institution_id": r.institution_id,
            "institution_name": r.institution_name,
            "status": r.status,
            "total_works_crawled": r.total_works_crawled,
            "last_crawl_completed": r.last_crawl_completed.isoformat() if r.last_crawl_completed else None,
            "error_message": r.error_message,
        }
        for r in rows
    ]
    return {"institutions": institutions}


@router.post("/crawl/start")
async def start_crawl(
    background_tasks: BackgroundTasks,
    _admin: str = Depends(require_admin),
    db: Session = Depends(_get_db),
):
    """Trigger the multi-institution crawler in the background."""
    import asyncio
    from src.crawler.multi_institution_crawler import MultiInstitutionCrawler

    # Read targets from DB; fallback to hardcoded defaults if table is empty
    targets = db.query(CrawlTarget).filter(CrawlTarget.enabled == True).all()
    if targets:
        institution_ids = [t.institution_id for t in targets]
    else:
        from config.settings import TARGET_INSTITUTIONS
        institution_ids = list(TARGET_INSTITUTIONS.keys())

    def _run(ids):
        crawler = MultiInstitutionCrawler(institution_ids=ids)
        asyncio.run(crawler.crawl_all())

    background_tasks.add_task(_run, institution_ids)
    return {"status": "started", "message": "Multi-institution crawl started in background"}


@router.get("/crawl/targets")
async def list_crawl_targets(
    _admin: str = Depends(require_admin),
    db: Session = Depends(_get_db),
):
    """List all crawl targets."""
    rows = db.query(CrawlTarget).order_by(CrawlTarget.id).all()
    return {
        "targets": [
            {
                "id": r.id,
                "institution_id": r.institution_id,
                "institution_name": r.institution_name,
                "enabled": r.enabled,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    }


@router.post("/crawl/targets")
async def add_crawl_target(
    body: CrawlTargetRequest,
    _admin: str = Depends(require_admin),
    db: Session = Depends(_get_db),
):
    """Add a new crawl target."""
    existing = db.query(CrawlTarget).filter(CrawlTarget.institution_id == body.institution_id).first()
    if existing:
        return {"ok": False, "error": "Target already exists"}
    target = CrawlTarget(institution_id=body.institution_id, institution_name=body.institution_name)
    db.add(target)
    db.commit()
    return {"ok": True, "institution_id": body.institution_id}


@router.delete("/crawl/targets/{institution_id}")
async def delete_crawl_target(
    institution_id: str,
    _admin: str = Depends(require_admin),
    db: Session = Depends(_get_db),
):
    """Delete a crawl target by institution_id."""
    target = db.query(CrawlTarget).filter(CrawlTarget.institution_id == institution_id).first()
    if not target:
        return {"ok": False, "error": "Target not found"}
    db.delete(target)
    db.commit()
    return {"ok": True}


@router.post("/crawl/targets/init")
async def init_crawl_targets(
    _admin: str = Depends(require_admin),
    db: Session = Depends(_get_db),
):
    """Import default targets from TARGET_INSTITUTIONS (skip duplicates)."""
    from config.settings import TARGET_INSTITUTIONS

    added = 0
    for inst_id, inst_name in TARGET_INSTITUTIONS.items():
        existing = db.query(CrawlTarget).filter(CrawlTarget.institution_id == inst_id).first()
        if not existing:
            db.add(CrawlTarget(institution_id=inst_id, institution_name=inst_name))
            added += 1
    db.commit()
    return {"ok": True, "added": added, "total": len(TARGET_INSTITUTIONS)}
