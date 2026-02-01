"""
System status and management API endpoints.
"""
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from config.settings import settings
from src.database.models import (
    get_session,
    Author,
    Work,
    Collaboration,
    RelationshipScore,
    CrawlState,
)
from src.database.repositories import (
    AuthorRepository,
    WorkRepository,
    CollaborationRepository,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class DatabaseStats(BaseModel):
    """Database statistics."""
    total_authors: int
    total_works: int
    total_collaborations: int
    total_relationship_scores: int


class CrawlStatus(BaseModel):
    """Crawl status."""
    status: str
    last_crawl_date: Optional[str] = None
    works_crawled: int = 0
    error_message: Optional[str] = None


class SystemStatus(BaseModel):
    """System status response."""
    status: str
    version: str
    database: DatabaseStats
    crawl: CrawlStatus
    redis_enabled: bool
    redis_connected: bool


class AnalysisStatus(BaseModel):
    """Analysis status."""
    last_run: Optional[str] = None
    model_version: Optional[str] = None
    scores_computed: int = 0


# Dependency for database session
def get_db():
    """Get database session."""
    session = get_session()
    try:
        yield session
    finally:
        session.close()


@router.get("/status", response_model=SystemStatus)
async def get_system_status(
    db: Session = Depends(get_db),
):
    """
    Get system status including database statistics and crawl status.
    """
    # Database stats
    total_authors = db.query(func.count(Author.id)).scalar() or 0
    total_works = db.query(func.count(Work.id)).scalar() or 0
    total_collaborations = db.query(func.count(Collaboration.id)).scalar() or 0
    total_scores = db.query(func.count(RelationshipScore.id)).scalar() or 0

    db_stats = DatabaseStats(
        total_authors=total_authors,
        total_works=total_works,
        total_collaborations=total_collaborations,
        total_relationship_scores=total_scores,
    )

    # Crawl status
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

    # Redis status (use cached check to avoid blocking)
    redis_connected = False
    if settings.database.redis_enabled:
        try:
            from src.api.cache import is_redis_connected
            redis_connected = is_redis_connected()
        except Exception:
            pass

    return SystemStatus(
        status="healthy",
        version="1.0.0",
        database=db_stats,
        crawl=crawl_status,
        redis_enabled=settings.database.redis_enabled,
        redis_connected=redis_connected,
    )


@router.get("/stats")
async def get_detailed_stats(
    db: Session = Depends(get_db),
):
    """
    Get detailed statistics about the database.
    """
    author_repo = AuthorRepository(db)
    work_repo = WorkRepository(db)
    collab_repo = CollaborationRepository(db)

    return {
        "authors": author_repo.get_statistics(),
        "works": work_repo.get_statistics(),
        "collaborations": collab_repo.get_statistics(),
    }


@router.post("/crawl/trigger")
async def trigger_crawl(
    background_tasks: BackgroundTasks,
    incremental: bool = True,
    max_works: Optional[int] = None,
):
    """
    Trigger a crawl operation.

    This starts the crawl in the background and returns immediately.
    Check /status for progress.
    """
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
    """
    Trigger analysis (GNN training and score computation).

    This starts the analysis in the background and returns immediately.
    """
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
    """
    Get current system configuration (non-sensitive values only).
    """
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
