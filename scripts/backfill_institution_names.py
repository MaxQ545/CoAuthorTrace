"""Backfill institution names from OpenAlex API for states showing 'Unknown'."""
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import httpx
from sqlalchemy import text
from src.database.models import get_session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    try:
        session = get_session()
    except Exception:
        logger.exception("Failed to connect to database")
        sys.exit(1)

    try:
        rows = session.execute(
            text(
                "SELECT institution_id FROM institution_crawl_state "
                "WHERE institution_name IS NULL OR institution_name = 'Unknown' "
                "ORDER BY institution_id"
            )
        ).fetchall()
    except Exception:
        logger.exception("Failed to query institution_crawl_state")
        session.close()
        sys.exit(1)

    ids = [r[0] for r in rows]
    logger.info("Fetching names for %d institutions from OpenAlex...", len(ids))

    if not ids:
        logger.info("Nothing to backfill — all institutions already have names.")
        session.close()
        return

    updated = 0
    errors = 0
    with httpx.Client(timeout=30) as client:
        for inst_id in ids:
            try:
                resp = client.get(
                    f"https://api.openalex.org/institutions/{inst_id}",
                    timeout=30,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    name = data.get("display_name", "Unknown")
                    if name == "Unknown":
                        logger.warning("  %s -> display_name missing, skipping", inst_id)
                        continue
                    session.execute(
                        text(
                            "UPDATE institution_crawl_state "
                            "SET institution_name = :name WHERE institution_id = :id"
                        ),
                        {"name": name, "id": inst_id},
                    )
                    logger.info("  %s -> %s", inst_id, name)
                    updated += 1
                else:
                    logger.warning("  %s -> HTTP %d", inst_id, resp.status_code)
            except httpx.TimeoutException:
                logger.error("  %s -> Request timed out", inst_id)
                errors += 1
            except httpx.HTTPError:
                logger.exception("  %s -> HTTP error", inst_id)
                errors += 1
            except Exception:
                logger.exception("  %s -> Unexpected error", inst_id)
                errors += 1

    try:
        session.commit()
    except Exception:
        logger.exception("Failed to commit updates")
        session.rollback()
        session.close()
        sys.exit(1)

    logger.info("Updated %d names (%d errors)", updated, errors)
    session.close()

    if errors > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
