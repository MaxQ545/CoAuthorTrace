#!/usr/bin/env python3
"""
Migrate data from SQLite to PostgreSQL.

Usage:
    python scripts/migrate_sqlite_to_pg.py <sqlite_db_path>

The target PostgreSQL URL is read from the COAUTHOR_DATABASE__POSTGRES_URL
environment variable (or the default in settings).
"""
import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.database.models import Base
from config.settings import settings

# Table migration order (respects foreign-key dependencies)
TABLE_ORDER = [
    "authors",
    "institution_stats",
    "works",
    "authorships",
    "collaborations",
    "relationship_scores",
    "crawl_state",
    "institution_crawl_state",
]

BATCH_SIZE = 5000

# SQLite stores booleans as 0/1 integers; PostgreSQL needs real booleans
BOOL_COLUMNS = {
    "authors": {"is_canonical"},
    "works": {"is_open_access"},
    "authorships": {"is_corresponding"},
}


def _convert_row(table_name: str, columns: list[str], row) -> dict:
    """Convert a SQLite row to a dict with proper types for PostgreSQL."""
    d = dict(zip(columns, row))
    bool_cols = BOOL_COLUMNS.get(table_name)
    if bool_cols:
        for col in bool_cols:
            if col in d and d[col] is not None:
                d[col] = bool(d[col])
    return d


def migrate(sqlite_path: str):
    """Migrate all data from SQLite to PostgreSQL."""
    # Source: SQLite
    src_engine = create_engine(
        f"sqlite:///{sqlite_path}",
        echo=False,
        connect_args={"check_same_thread": False},
    )

    # Target: PostgreSQL
    pg_url = settings.database.postgres_url
    dst_engine = create_engine(pg_url, echo=False)

    print(f"Source:  sqlite:///{sqlite_path}")
    print(f"Target:  {pg_url}")
    print()

    # Create all tables in PostgreSQL
    print("Creating tables in PostgreSQL...")
    Base.metadata.create_all(dst_engine)
    print("  Done.\n")

    SrcSession = sessionmaker(bind=src_engine)
    DstSession = sessionmaker(bind=dst_engine)

    total_start = time.time()

    for table_name in TABLE_ORDER:
        # Check if table exists in source
        with src_engine.connect() as conn:
            try:
                row_count = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
            except Exception:
                print(f"[SKIP] Table '{table_name}' not found in source database.")
                continue

        if row_count == 0:
            print(f"[SKIP] Table '{table_name}' is empty.")
            continue

        print(f"[MIGRATE] {table_name}: {row_count:,} rows ...")
        t0 = time.time()

        # Read column names from source
        with src_engine.connect() as conn:
            result = conn.execute(text(f"PRAGMA table_info({table_name})"))
            columns = [row[1] for row in result.fetchall()]

        col_list = ", ".join(columns)
        migrated = 0

        while migrated < row_count:
            # Read batch from SQLite
            with src_engine.connect() as src_conn:
                rows = src_conn.execute(
                    text(f"SELECT {col_list} FROM {table_name} LIMIT :limit OFFSET :offset"),
                    {"limit": BATCH_SIZE, "offset": migrated},
                ).fetchall()

            if not rows:
                break

            # Write batch to PostgreSQL
            placeholders = ", ".join([f":{c}" for c in columns])
            insert_sql = f"INSERT INTO {table_name} ({col_list}) VALUES ({placeholders})"

            with dst_engine.begin() as dst_conn:
                dst_conn.execute(
                    text(insert_sql),
                    [_convert_row(table_name, columns, row) for row in rows],
                )

            migrated += len(rows)
            elapsed = time.time() - t0
            rate = migrated / elapsed if elapsed > 0 else 0
            print(f"  {migrated:>10,} / {row_count:,}  ({rate:,.0f} rows/s)")

        elapsed = time.time() - t0
        print(f"  Completed in {elapsed:.1f}s\n")

    # Reset PostgreSQL sequences for autoincrement columns
    print("Resetting sequences...")
    with dst_engine.begin() as conn:
        for table_name in TABLE_ORDER:
            try:
                max_id = conn.execute(text(f"SELECT MAX(id) FROM {table_name}")).scalar()
                if max_id is not None:
                    seq_name = f"{table_name}_id_seq"
                    conn.execute(text(f"SELECT setval('{seq_name}', :val)"), {"val": max_id})
                    print(f"  {seq_name} -> {max_id}")
            except Exception:
                pass  # Table may not have an id column or sequence
    print()

    total_elapsed = time.time() - total_start
    print(f"Migration completed in {total_elapsed:.1f}s")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <sqlite_db_path>")
        sys.exit(1)

    sqlite_path = sys.argv[1]
    if not Path(sqlite_path).exists():
        print(f"Error: SQLite file not found: {sqlite_path}")
        sys.exit(1)

    migrate(sqlite_path)
