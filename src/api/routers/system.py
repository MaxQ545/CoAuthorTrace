"""
System status and management API endpoints.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import text

from config.settings import settings
from src.database.models import CrawlState
from src.database.repositories import (
    AuthorRepository,
    WorkRepository,
    CollaborationRepository,
)
from src.api.cache import get_cache, cache_key
from src.api.deps import get_db
from src.api.schemas import (
    DatabaseStats,
    CrawlStatus,
    SystemStatus,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _fast_row_count(db: Session, table: str) -> int:
    """Fast row-count approximation using PostgreSQL pg_class statistics."""
    value = db.execute(
        text("SELECT reltuples::bigint FROM pg_class WHERE relname = :table"),
        {"table": table},
    ).scalar()
    return int(value or 0)


@router.get("/status", response_model=SystemStatus)
async def get_system_status(
    db: Session = Depends(get_db),
):
    """Get system status including database statistics and crawl status."""
    cache = get_cache()
    status_cache_key = cache_key("system_status")
    if cache:
        cached = cache.get(status_cache_key)
        if cached:
            return SystemStatus(**cached)

    db_stats = DatabaseStats(
        total_authors=_fast_row_count(db, "authors"),
        total_works=_fast_row_count(db, "works"),
        total_collaborations=_fast_row_count(db, "collaborations"),
        total_relationship_scores=_fast_row_count(db, "relationship_scores"),
    )

    crawl_state = db.query(CrawlState).order_by(CrawlState.updated_at.desc()).first()
    if crawl_state:
        crawl_status = CrawlStatus(
            status=crawl_state.status,
            last_crawl_date=crawl_state.last_crawl_date.isoformat() if crawl_state.last_crawl_date else None,
            works_crawled=crawl_state.works_crawled,
            error_message=crawl_state.error_message,
        )
    else:
        crawl_status = CrawlStatus(status="not_started")

    redis_connected = False
    if settings.database.redis_enabled:
        try:
            from src.api.cache import is_redis_connected
            redis_connected = is_redis_connected()
        except Exception:
            pass

    response = SystemStatus(
        status="healthy",
        version="1.0.0",
        database=db_stats,
        crawl=crawl_status,
        redis_enabled=settings.database.redis_enabled,
        redis_connected=redis_connected,
    )
    if cache:
        cache.set(status_cache_key, response.model_dump(), ex=300)
    return response


@router.get("/stats")
async def get_detailed_stats(
    db: Session = Depends(get_db),
):
    """Get detailed statistics about the database."""
    return {
        "authors": AuthorRepository(db).get_statistics(),
        "works": WorkRepository(db).get_statistics(),
        "collaborations": CollaborationRepository(db).get_statistics(),
    }


@router.post("/crawl/trigger")
async def trigger_crawl(
    background_tasks: BackgroundTasks,
    incremental: bool = True,
    max_works: Optional[int] = None,
):
    """Trigger a crawl operation (background)."""
    from src.crawler.incremental_crawler import run_crawl
    import asyncio

    def run_crawl_task():
        asyncio.run(run_crawl(incremental=incremental, max_works=max_works))

    background_tasks.add_task(run_crawl_task)
    return {
        "status": "started",
        "message": "Crawl operation started in background",
        "incremental": incremental,
        "max_works": max_works,
    }


@router.post("/analysis/trigger")
async def trigger_analysis(
    background_tasks: BackgroundTasks,
    model_path: Optional[str] = None,
):
    """Trigger analysis (GNN training and score computation) in background."""
    from src.analysis.relationship_scorer import run_analysis

    model_path = model_path or str(settings.project_root / "data/models/graphsage.pt")

    def run_analysis_task():
        run_analysis(model_path=model_path)

    background_tasks.add_task(run_analysis_task)
    return {
        "status": "started",
        "message": "Analysis operation started in background",
        "model_path": model_path,
    }


@router.get("/config")
async def get_config():
    """Get current system configuration (non-sensitive values only)."""
    return {
        "scope": {
            "institution_ids": settings.scope.institution_ids,
            "concept_ids": settings.scope.concept_ids,
            "source_ids": settings.scope.source_ids,
            "from_date": settings.scope.from_date,
        },
        "crawler": {
            "rate_limit": settings.crawler.rate_limit,
            "batch_size": settings.crawler.batch_size,
        },
        "analysis": {
            "hidden_dim": settings.analysis.hidden_dim,
            "output_dim": settings.analysis.output_dim,
            "num_layers": settings.analysis.num_layers,
            "epochs": settings.analysis.epochs,
        },
        "api": {
            "default_top_k": settings.api.default_top_k,
            "cache_ttl": settings.api.cache_ttl,
        },
    }
