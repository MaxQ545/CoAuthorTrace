"""
APScheduler jobs for automated crawling and analysis.
"""
import asyncio
import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.triggers.cron import CronTrigger

from config.settings import settings

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler: BackgroundScheduler = None


def get_jobstore_url() -> str:
    """Get SQLAlchemy URL for job store."""
    return settings.database.postgres_url


def create_scheduler() -> BackgroundScheduler:
    """Create and configure scheduler."""
    jobstores = {
        "default": SQLAlchemyJobStore(url=get_jobstore_url())
    }

    return BackgroundScheduler(
        jobstores=jobstores,
        job_defaults={
            "coalesce": True,
            "max_instances": 1,
            "misfire_grace_time": 3600,
        },
    )


def daily_crawl_job():
    """
    Daily incremental crawl job.

    Runs at configured hour (default: 2:00 AM).
    """
    logger.info("Starting daily incremental crawl...")

    try:
        from src.crawler.incremental_crawler import run_crawl

        stats = asyncio.run(run_crawl(incremental=True))
        logger.info(f"Daily crawl completed: {stats}")

    except Exception as e:
        logger.error(f"Daily crawl failed: {e}")
        raise


def weekly_analysis_job():
    """
    Weekly GNN analysis job.

    Runs on configured day (default: Sunday) at configured hour (default: 4:00 AM).
    """
    logger.info("Starting weekly GNN analysis...")

    try:
        from src.analysis.relationship_scorer import run_analysis

        model_path = str(settings.project_root / "data/models/graphsage.pt")
        stats = run_analysis(model_path=model_path)
        logger.info(f"Weekly analysis completed: {stats}")

    except Exception as e:
        logger.error(f"Weekly analysis failed: {e}")
        raise


def start_scheduler() -> BackgroundScheduler:
    """
    Start the scheduler with configured jobs.

    Returns:
        Started scheduler instance
    """
    global scheduler

    if scheduler is not None and scheduler.running:
        logger.warning("Scheduler already running")
        return scheduler

    scheduler = create_scheduler()

    # Add daily crawl job
    scheduler.add_job(
        daily_crawl_job,
        trigger=CronTrigger(hour=settings.scheduler.crawl_cron_hour),
        id="daily_crawl",
        name="Daily Incremental Crawl",
        replace_existing=True,
    )
    logger.info(f"Added daily crawl job at {settings.scheduler.crawl_cron_hour}:00")

    # Add weekly analysis job
    scheduler.add_job(
        weekly_analysis_job,
        trigger=CronTrigger(
            day_of_week=settings.scheduler.analysis_cron_day,
            hour=settings.scheduler.analysis_cron_hour,
        ),
        id="weekly_analysis",
        name="Weekly GNN Analysis",
        replace_existing=True,
    )
    logger.info(
        f"Added weekly analysis job on {settings.scheduler.analysis_cron_day} "
        f"at {settings.scheduler.analysis_cron_hour}:00"
    )

    scheduler.start()
    logger.info("Scheduler started")

    return scheduler


def stop_scheduler():
    """Stop the scheduler."""
    global scheduler

    if scheduler is not None and scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped")

    scheduler = None


def get_scheduler_status() -> dict:
    """Get scheduler status and job information."""
    global scheduler

    if scheduler is None or not scheduler.running:
        return {
            "status": "stopped",
            "jobs": [],
        }

    jobs = []
    for job in scheduler.get_jobs():
        next_run = job.next_run_time
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": next_run.isoformat() if next_run else None,
        })

    return {
        "status": "running",
        "jobs": jobs,
    }


def trigger_job(job_id: str) -> bool:
    """
    Manually trigger a scheduled job.

    Args:
        job_id: Job ID to trigger

    Returns:
        True if job was triggered, False otherwise
    """
    global scheduler

    if scheduler is None or not scheduler.running:
        return False

    job = scheduler.get_job(job_id)
    if job is None:
        return False

    # Run job function directly
    job.func()
    return True


if __name__ == "__main__":
    import time

    logging.basicConfig(level=logging.INFO)

    # Initialize database
    from src.database.models import init_database
    init_database()

    # Start scheduler
    start_scheduler()

    try:
        # Keep running
        while True:
            time.sleep(60)
            status = get_scheduler_status()
            logger.info(f"Scheduler status: {status}")
    except KeyboardInterrupt:
        stop_scheduler()
