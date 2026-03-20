"""Refresh institution stats cache table."""
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.database.models import init_database, get_session
from src.database.repositories import AuthorRepository

logging.basicConfig(level=logging.INFO)


def main():
    try:
        init_database()
    except Exception as e:
        logging.error("Failed to initialize database: %s", e)
        sys.exit(1)

    session = get_session()
    try:
        repo = AuthorRepository(session)
        count = repo.refresh_institution_stats()
        logging.info("Refreshed institution stats: %s institutions", count)
    except Exception as e:
        logging.error("Failed to refresh institution stats: %s", e)
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
