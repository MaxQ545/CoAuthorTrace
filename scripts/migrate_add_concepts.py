#!/usr/bin/env python3
"""
Database migration script to add concepts and research_fields columns.

This script adds:
- Work.concepts: JSON field for storing paper concepts from OpenAlex
- Author.research_fields: JSON field for cached research fields
- Author.research_fields_updated_at: Timestamp for cache invalidation
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from src.database.models import get_engine


def migrate():
    """Add new columns to existing tables."""
    engine = get_engine()

    migrations = [
        # Work.concepts
        ("works", "concepts", "ALTER TABLE works ADD COLUMN concepts TEXT"),
        # Author.research_fields
        ("authors", "research_fields", "ALTER TABLE authors ADD COLUMN research_fields TEXT"),
        # Author.research_fields_updated_at
        ("authors", "research_fields_updated_at", "ALTER TABLE authors ADD COLUMN research_fields_updated_at TIMESTAMP"),
    ]

    with engine.connect() as conn:
        for table, column, sql in migrations:
            # Check if column exists
            result = conn.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = :table"
            ), {"table": table})
            columns = [row[0] for row in result.fetchall()]

            if column in columns:
                print(f"Column {table}.{column} already exists, skipping...")
            else:
                print(f"Adding column {table}.{column}...")
                conn.execute(text(sql))
                print(f"  Done!")

        conn.commit()

    print("\nMigration completed successfully!")


if __name__ == "__main__":
    migrate()
