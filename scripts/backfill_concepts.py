#!/usr/bin/env python3
"""
Backfill concepts for existing works in the database.

This script fetches concepts from OpenAlex for works that don't have them yet.
Uses the API key for higher rate limits (100 req/s).

Usage:
    python scripts/backfill_concepts.py --batch-size 100 --concurrent 5
"""
import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from src.database.models import get_engine, get_session, Work
from src.crawler.openalex_client import OpenAlexClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def fetch_work_concepts(client: OpenAlexClient, work_id: str) -> str | None:
    """Fetch concepts for a single work from OpenAlex."""
    try:
        work = await client.get_work(work_id)
        raw_concepts = work.get("concepts", [])

        # Filter level 1-2, score >= 0.3, keep top 10
        filtered = [
            {
                "id": c.get("id", "").replace("https://openalex.org/", ""),
                "display_name": c.get("display_name", ""),
                "level": c.get("level", 0),
                "score": c.get("score", 0),
            }
            for c in raw_concepts
            if c.get("level") in [1, 2] and c.get("score", 0) >= 0.3
        ]

        if filtered:
            filtered.sort(key=lambda x: x["score"], reverse=True)
            return json.dumps(filtered[:10])
        return None

    except Exception as e:
        logger.warning(f"Failed to fetch concepts for {work_id}: {e}")
        return None


async def process_batch(
    client: OpenAlexClient,
    work_ids: list[str],
    session
) -> int:
    """Process a batch of works concurrently."""
    tasks = [fetch_work_concepts(client, wid) for wid in work_ids]
    results = await asyncio.gather(*tasks)

    updated = 0
    for work_id, concepts in zip(work_ids, results):
        # Always update: use "[]" for works without matching concepts
        # This prevents re-querying the same works
        concepts_value = concepts if concepts else "[]"
        session.execute(
            text("UPDATE works SET concepts = :concepts WHERE id = :id"),
            {"concepts": concepts_value, "id": work_id}
        )
        if concepts:
            updated += 1

    session.commit()
    return updated


async def backfill(batch_size: int = 100, concurrent: int = 5, limit: int = None):
    """
    Backfill concepts for all works without them.

    Args:
        batch_size: Number of works to fetch per batch
        concurrent: Number of concurrent API requests
        limit: Maximum number of works to process (None for all)
    """
    engine = get_engine()

    # Count works needing backfill
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM works WHERE concepts IS NULL"))
        total_null = result.scalar()

    if total_null == 0:
        logger.info("No works need backfilling!")
        return

    logger.info(f"Found {total_null} works without concepts")
    if limit:
        logger.info(f"Will process up to {limit} works")

    # Initialize client with API key (100 req/s allowed with API key)
    from config.settings import settings
    client = OpenAlexClient(
        api_key=settings.crawler.openalex_api_key,
        rate_limit=80  # Use 80 req/s (below 100 limit for safety)
    )

    try:
        processed = 0
        updated = 0

        while True:
            # Get batch of work IDs
            session = get_session()
            works = (
                session.query(Work.id)
                .filter(Work.concepts.is_(None))
                .limit(batch_size)
                .all()
            )
            session.close()

            if not works:
                break

            work_ids = [w.id for w in works]

            # Process in chunks for concurrency
            chunk_size = concurrent
            for i in range(0, len(work_ids), chunk_size):
                chunk = work_ids[i:i + chunk_size]
                session = get_session()
                batch_updated = await process_batch(client, chunk, session)
                session.close()
                updated += batch_updated

            processed += len(work_ids)

            # Progress logging
            logger.info(f"Processed {processed}/{total_null} works, updated {updated}")

            if limit and processed >= limit:
                logger.info(f"Reached limit of {limit} works")
                break

    finally:
        await client.close()

    logger.info(f"Backfill complete! Processed {processed} works, updated {updated}")


def main():
    parser = argparse.ArgumentParser(description="Backfill concepts for existing works")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of works per batch (default: 100)"
    )
    parser.add_argument(
        "--concurrent",
        type=int,
        default=5,
        help="Number of concurrent requests (default: 5)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum works to process (default: all)"
    )

    args = parser.parse_args()

    asyncio.run(backfill(
        batch_size=args.batch_size,
        concurrent=args.concurrent,
        limit=args.limit
    ))


if __name__ == "__main__":
    main()
