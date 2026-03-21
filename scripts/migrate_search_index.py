#!/usr/bin/env python3
"""
Database migration script to create pg_trgm trigram indexes for fuzzy search.

Creates GIN indexes using pg_trgm on:
- authors.display_name: for author name search
- institution_stats.institution_name: for institution name search

Requires the pg_trgm extension to be enabled in PostgreSQL.
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from src.database.models import get_engine


def migrate():
    """Create pg_trgm indexes for fuzzy text search."""
    engine = get_engine()

    with engine.connect() as conn:
        # Ensure pg_trgm extension is available
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        conn.commit()
        print("pg_trgm extension ensured")

        # Author display_name trigram index
        conn.execute(text(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_author_display_name_trgm "
            "ON authors USING gin (display_name gin_trgm_ops)"
        ))
        conn.commit()
        print("Author display_name trigram index created")

        # Institution name trigram index
        conn.execute(text(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_institution_name_trgm "
            "ON institution_stats USING gin (institution_name gin_trgm_ops)"
        ))
        conn.commit()
        print("Institution name trigram index created")

    print("\nSearch index migration completed successfully!")


if __name__ == "__main__":
    migrate()
