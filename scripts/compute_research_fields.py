#!/usr/bin/env python3
"""
Compute research fields for all authors based on their papers' concepts.

This script should be run after backfill_concepts.py has populated the
concepts field for works.

Usage:
    python scripts/compute_research_fields.py
    python scripts/compute_research_fields.py --limit 100  # For testing
"""
import argparse
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.database.models import get_session, Author
from src.analysis.research_fields import ResearchFieldsCalculator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def compute_all_author_fields(limit: int = None, batch_size: int = 100):
    """
    Compute research fields for all canonical authors.

    Args:
        limit: Maximum number of authors to process (None for all)
        batch_size: Number of authors to process before committing
    """
    session = get_session()

    try:
        # Count total canonical authors
        total = session.query(Author).filter(Author.is_canonical == True).count()
        logger.info(f"Found {total} canonical authors")

        if limit:
            logger.info(f"Will process up to {limit} authors")

        calculator = ResearchFieldsCalculator(session)

        # Query authors in batches
        offset = 0
        processed = 0
        updated = 0

        while True:
            authors = (
                session.query(Author)
                .filter(Author.is_canonical == True)
                .order_by(Author.id)
                .offset(offset)
                .limit(batch_size)
                .all()
            )

            if not authors:
                break

            for author in authors:
                try:
                    fields = calculator.compute_for_author(
                        author.id,
                        top_k=5,
                        update_cache=True
                    )
                    if fields:
                        updated += 1
                except Exception as e:
                    logger.warning(f"Failed to compute fields for {author.id}: {e}")

                processed += 1

                if limit and processed >= limit:
                    break

            # Commit batch
            session.commit()

            # Progress logging
            logger.info(f"Processed {processed}/{total} authors, {updated} with fields")

            if limit and processed >= limit:
                break

            offset += batch_size

    finally:
        session.close()

    logger.info(f"Complete! Processed {processed} authors, {updated} have research fields")


def main():
    parser = argparse.ArgumentParser(
        description="Compute research fields for all authors"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum authors to process (default: all)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Batch size for commits (default: 100)"
    )

    args = parser.parse_args()

    compute_all_author_fields(limit=args.limit, batch_size=args.batch_size)


if __name__ == "__main__":
    main()
