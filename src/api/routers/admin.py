"""
Admin dashboard API endpoints: login, visitor tracking, analytics, and crawl management.
"""
import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
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
# Login rate limiting — in-memory tracker for brute-force protection
# ---------------------------------------------------------------------------
_login_attempts: dict[str, list[float]] = {}
_RATE_LIMIT_WINDOW = 60       # seconds — track failures within this window
_RATE_LIMIT_MAX_FAILURES = 5  # max allowed failures in the window
_RATE_LIMIT_COOLDOWN = 300    # seconds — block duration after exceeding limit


def _check_rate_limit(ip: str) -> bool:
    """Return True if the IP is currently blocked. Cleans up stale entries."""
    now = time.monotonic()
    attempts = _login_attempts.get(ip)
    if attempts is None:
        return False
    # Remove entries older than the cooldown period
    cutoff = now - _RATE_LIMIT_COOLDOWN
    _login_attempts[ip] = [t for t in attempts if t > cutoff]
    attempts = _login_attempts[ip]
    if not attempts:
        del _login_attempts[ip]
        return False
    # Check if there are >= max failures within the short window
    recent = [t for t in attempts if t > now - _RATE_LIMIT_WINDOW]
    if len(recent) >= _RATE_LIMIT_MAX_FAILURES:
        return True
    return False


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


class ReorderItem(BaseModel):
    institution_id: str
    position: int


class ReorderRequest(BaseModel):
    items: List[ReorderItem]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/login")
async def admin_login(body: LoginRequest, request: Request):
    """Authenticate with admin password and receive a JWT."""
    ip = request.client.host if request.client else "unknown"

    if _check_rate_limit(ip):
        return JSONResponse(
            status_code=429,
            content={"ok": False, "error": "Too many failed login attempts. Try again later."},
            headers={"Retry-After": str(_RATE_LIMIT_COOLDOWN)},
        )

    if not verify_password(body.password):
        _login_attempts.setdefault(ip, []).append(time.monotonic())
        return {"ok": False, "error": "Invalid password"}

    # Successful login — clear any tracked failures for this IP
    _login_attempts.pop(ip, None)
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
    }


@router.get("/visits")
async def get_visits(
    limit: int = 20,
    offset: int = 0,
    _admin: str = Depends(require_admin),
    db: Session = Depends(_get_db),
):
    """Return paginated recent visits."""
    total = db.query(func.count(PageVisit.id)).scalar() or 0

    rows = (
        db.query(PageVisit)
        .order_by(PageVisit.timestamp.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    visits = [
        {
            "ip": r.ip_address,
            "region": r.region,
            "path": r.path,
            "author_id": r.author_id,
            "user_agent": r.user_agent,
            "timestamp": r.timestamp.isoformat() if r.timestamp else None,
        }
        for r in rows
    ]

    return {"visits": visits, "total": total, "limit": limit, "offset": offset}


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
    import src.crawler.multi_institution_crawler as mic

    # Read targets from DB; fallback to hardcoded defaults if table is empty
    targets = db.query(CrawlTarget).filter(CrawlTarget.enabled == True).all()
    if targets:
        institution_ids = [t.institution_id for t in targets]
        target_names = {t.institution_id: t.institution_name for t in targets}
    else:
        from config.settings import TARGET_INSTITUTIONS
        institution_ids = list(TARGET_INSTITUTIONS.keys())
        target_names = dict(TARGET_INSTITUTIONS)

    # Respect queue_position ordering: order by queue_position (nulls last), then priority desc
    states = (
        db.query(InstitutionCrawlState)
        .filter(InstitutionCrawlState.institution_id.in_(institution_ids))
        .all()
    )
    state_map = {s.institution_id: s for s in states}

    def sort_key(inst_id):
        s = state_map.get(inst_id)
        if s and s.queue_position is not None:
            return (0, s.queue_position, -(s.priority or 0))
        return (1, 0, -(s.priority or 0) if s else 0)

    institution_ids.sort(key=sort_key)

    # Set queued status for waiting institutions
    now = datetime.utcnow()
    for idx, inst_id in enumerate(institution_ids):
        state = state_map.get(inst_id)
        if state:
            state.status = "queued"
            state.queue_position = idx
            state.started_at = now
            state.progress_current = 0
            state.progress_total = None
            state.error_message = None
            # Fill in institution name if missing
            if (not state.institution_name or state.institution_name == "Unknown") and inst_id in target_names:
                state.institution_name = target_names[inst_id]

    db.commit()

    def _run(ids):
        crawler = mic.MultiInstitutionCrawler(institution_ids=ids)
        mic._active_crawler = crawler
        try:
            asyncio.run(crawler.crawl_all())
        finally:
            mic._active_crawler = None

    background_tasks.add_task(_run, institution_ids)
    return {"status": "started", "message": "Multi-institution crawl started in background", "institution_ids": institution_ids}


@router.post("/crawl/stop")
async def stop_crawl_all(
    _admin: str = Depends(require_admin),
):
    """Stop all running crawls."""
    import src.crawler.multi_institution_crawler as mic
    crawler = mic._active_crawler
    if not crawler:
        raise HTTPException(status_code=409, detail="No active crawl to stop")
    crawler.stop_all()
    return {"ok": True, "message": "Global stop signal sent"}


@router.post("/crawl/stop/{institution_id}")
async def stop_crawl_institution(
    institution_id: str,
    _admin: str = Depends(require_admin),
):
    """Stop crawl for a specific institution."""
    import src.crawler.multi_institution_crawler as mic
    crawler = mic._active_crawler
    if not crawler:
        raise HTTPException(status_code=409, detail="No active crawl running")
    crawler.stop_institution(institution_id)
    return {"ok": True, "message": f"Stop signal sent for {institution_id}"}


@router.post("/crawl/pause/{institution_id}")
async def pause_crawl_institution(
    institution_id: str,
    _admin: str = Depends(require_admin),
):
    """Pause crawl for a specific institution."""
    import src.crawler.multi_institution_crawler as mic
    crawler = mic._active_crawler
    if not crawler:
        raise HTTPException(status_code=409, detail="No active crawl running")
    crawler.pause_institution(institution_id)
    return {"ok": True, "message": f"Pause signal sent for {institution_id}"}


@router.post("/crawl/resume/{institution_id}")
async def resume_crawl_institution(
    institution_id: str,
    _admin: str = Depends(require_admin),
):
    """Resume a paused institution crawl."""
    import src.crawler.multi_institution_crawler as mic
    crawler = mic._active_crawler
    if not crawler:
        raise HTTPException(status_code=409, detail="No active crawl running")
    crawler.resume_institution(institution_id)
    return {"ok": True, "message": f"Resume signal sent for {institution_id}"}


@router.post("/crawl/retry/{institution_id}")
async def retry_crawl_institution(
    institution_id: str,
    _admin: str = Depends(require_admin),
    db: Session = Depends(_get_db),
):
    """Reset a failed/stopped institution back to idle so it can be re-queued."""
    state = (
        db.query(InstitutionCrawlState)
        .filter(InstitutionCrawlState.institution_id == institution_id)
        .first()
    )
    if not state:
        raise HTTPException(status_code=404, detail="Institution crawl state not found")
    if state.status not in ("failed", "stopped", "completed"):
        raise HTTPException(status_code=409, detail=f"Cannot retry institution with status '{state.status}'")
    state.status = "idle"
    state.error_message = None
    state.progress_current = 0
    state.progress_total = None
    state.started_at = None
    state.paused_at = None
    db.commit()
    return {"ok": True, "institution_id": institution_id, "status": "idle"}


@router.put("/crawl/reorder")
async def reorder_crawl_queue(
    body: ReorderRequest,
    _admin: str = Depends(require_admin),
    db: Session = Depends(_get_db),
):
    """Update queue_position for institutions."""
    updated = []
    for item in body.items:
        state = (
            db.query(InstitutionCrawlState)
            .filter(InstitutionCrawlState.institution_id == item.institution_id)
            .first()
        )
        if state:
            state.queue_position = item.position
            updated.append(item.institution_id)
    db.commit()
    return {"ok": True, "updated": updated}


@router.get("/crawl/progress")
async def get_crawl_progress(
    _admin: str = Depends(require_admin),
    db: Session = Depends(_get_db),
):
    """Return real-time progress for all institutions (excludes idle)."""
    rows = (
        db.query(InstitutionCrawlState)
        .filter(InstitutionCrawlState.status != "idle")
        .order_by(
            InstitutionCrawlState.started_at.desc().nullslast(),
        )
        .all()
    )
    institutions = [
        {
            "institution_id": r.institution_id,
            "institution_name": r.institution_name,
            "status": r.status,
            "queue_position": r.queue_position,
            "priority": r.priority,
            "progress_current": r.progress_current,
            "progress_total": r.progress_total,
            "total_works_crawled": r.total_works_crawled,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "paused_at": r.paused_at.isoformat() if r.paused_at else None,
            "last_crawl_completed": r.last_crawl_completed.isoformat() if r.last_crawl_completed else None,
            "error_message": r.error_message,
        }
        for r in rows
    ]
    import src.crawler.multi_institution_crawler as mic
    return {
        "crawler_active": mic._active_crawler is not None,
        "institutions": institutions,
    }


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


@router.get("/crawl/search-institution")
async def search_openalex_institution(
    q: str,
    _admin: str = Depends(require_admin),
):
    """Search OpenAlex for institutions by name. Returns top 10 matches."""
    if not q or len(q.strip()) < 2:
        return {"results": []}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.openalex.org/institutions",
                params={
                    "search": q.strip(),
                    "per_page": 10,
                    "select": "id,display_name,country_code,works_count,type",
                },
                headers={"User-Agent": f"CoAuthorTrace/1.0 (mailto:{settings.crawler.openalex_email})"},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning(f"OpenAlex institution search failed: {e}")
        return {"results": [], "error": str(e)}

    results = []
    for item in data.get("results", []):
        raw_id = item.get("id", "")
        inst_id = raw_id.split("/")[-1] if "/" in raw_id else raw_id
        results.append({
            "institution_id": inst_id,
            "display_name": item.get("display_name", ""),
            "country_code": item.get("country_code", ""),
            "works_count": item.get("works_count", 0),
            "type": item.get("type", ""),
        })
    return {"results": results}


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
