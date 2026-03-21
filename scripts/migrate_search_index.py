"""Add pg_trgm GIN index for fast author name search.

This migration enables PostgreSQL's pg_trgm extension and creates a GIN
trigram index on authors.display_name.  The trigram index accelerates
ILIKE '%query%' patterns from full-table scans to index scans, reducing
search latency from >30s to <500ms on 2M rows.

Usage:
    python scripts/migrate_search_index.py
"""
from sqlalchemy import text
from src.database.models import get_session


def migrate():
    session = get_session()
    try:
        # Enable pg_trgm extension (requires superuser or CREATE privilege)
        session.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        session.commit()
        print("pg_trgm extension enabled")

        # Create GIN trigram index on display_name
        # CONCURRENTLY avoids locking the table during index creation
        # Must run outside a transaction block
        session.execute(text("COMMIT"))
        session.execute(text(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_author_display_name_trgm "
            "ON authors USING gin (display_name gin_trgm_ops)"
        ))
        print("Trigram index idx_author_display_name_trgm created successfully")
    except Exception as e:
        session.rollback()
        print(f"Error: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    migrate()
