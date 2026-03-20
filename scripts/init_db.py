#!/usr/bin/env python3
"""
Initialize the database schema.
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.database.models import init_database


def main():
    """Initialize database."""
    try:
        print("Initializing database...")
        engine = init_database()
        print(f"Database initialized at: {engine.url}")
        print("Done!")
    except Exception as e:
        print(f"Error initializing database: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
