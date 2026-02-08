#!/usr/bin/env python3
"""
Database migration script to add task queue fields to InstitutionCrawlState.

Adds columns:
- queue_position: order in crawl queue
- priority: higher = crawl first
- progress_current: works fetched in current run
- progress_total: estimated total from OpenAlex meta.count
- started_at: when current run started
- paused_at: when last paused

Also extends status values to support:
  idle, queued, running, paused, pause_requested, stop_requested, stopped, completed, failed
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from src.database.models import get_engine


def migrate():
    """Add task queue columns to institution_crawl_state."""
    engine = get_engine()

    migrations = [
        ("institution_crawl_state", "queue_position", "ALTER TABLE institution_crawl_state ADD COLUMN queue_position INTEGER"),
        ("institution_crawl_state", "priority", "ALTER TABLE institution_crawl_state ADD COLUMN priority INTEGER DEFAULT 0"),
        ("institution_crawl_state", "progress_current", "ALTER TABLE institution_crawl_state ADD COLUMN progress_current INTEGER DEFAULT 0"),
        ("institution_crawl_state", "progress_total", "ALTER TABLE institution_crawl_state ADD COLUMN progress_total INTEGER"),
        ("institution_crawl_state", "started_at", "ALTER TABLE institution_crawl_state ADD COLUMN started_at TIMESTAMP"),
        ("institution_crawl_state", "paused_at", "ALTER TABLE institution_crawl_state ADD COLUMN paused_at TIMESTAMP"),
    ]

    with engine.connect() as conn:
        for table, column, sql in migrations:
            # Check if column already exists
            result = conn.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = :table AND column_name = :column"
            ), {"table": table, "column": column})

            if result.fetchone():
                print(f"Column {table}.{column} already exists, skipping...")
            else:
                print(f"Adding column {table}.{column}...")
                conn.execute(text(sql))
                print(f"  Done!")

        conn.commit()

    print("\nMigration completed successfully!")


if __name__ == "__main__":
    migrate()
