"""
Incremental crawler for OpenAlex data with state persistence.
"""
import asyncio
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from config.settings import settings
from src.database.models import (
    CrawlState,
    get_session,
    session_scope,
)
from src.database.repositories import (
    AuthorRepository,
    WorkRepository,
    CollaborationRepository,
)
from src.crawler.openalex_client import OpenAlexClient, parse_work
from src.crawler.batch_processor import BatchProcessor
from src.analysis.weight_calculator import WeightCalculator

logger = logging.getLogger(__name__)


class IncrementalCrawler:
    """
    Incremental crawler that tracks state and only fetches new data.
    """

    def __init__(
        self,
        institution_ids: Optional[list[str]] = None,
        concept_ids: Optional[list[str]] = None,
        source_ids: Optional[list[str]] = None,
        from_date: Optional[str] = None,
    ):
        """
        Initialize crawler with scope configuration.

        Args:
            institution_ids: Institution IDs to filter
            concept_ids: Concept IDs to filter
            source_ids: Source IDs to filter
            from_date: Start date for crawling
        """
        self.institution_ids = institution_ids or settings.scope.institution_ids
        self.concept_ids = concept_ids or settings.scope.concept_ids
        self.source_ids = source_ids or settings.scope.source_ids
        self.from_date = from_date or settings.scope.from_date

        self.client = OpenAlexClient(
            email=settings.crawler.openalex_email,
            rate_limit=settings.crawler.rate_limit,
            max_retries=settings.crawler.max_retries,
        )

        self.weight_calculator = WeightCalculator()
        self._scope_hash = self._compute_scope_hash()

    def _compute_scope_hash(self) -> str:
        """Compute hash of scope configuration for state tracking."""
        scope_str = f"{sorted(self.institution_ids)}|{sorted(self.concept_ids)}|{sorted(self.source_ids)}"
        return hashlib.sha256(scope_str.encode()).hexdigest()[:16]

    def _get_crawl_state(self, session: Session) -> Optional[CrawlState]:
        """Get existing crawl state for this scope."""
        return (
            session.query(CrawlState)
            .filter(CrawlState.scope_hash == self._scope_hash)
            .first()
        )

    def _create_crawl_state(self, session: Session) -> CrawlState:
        """Create new crawl state."""
        state = CrawlState(
            scope_hash=self._scope_hash,
            status="idle",
            works_crawled=0,
        )
        session.add(state)
        session.commit()
        return state

    def _update_crawl_state(
        self,
        session: Session,
        state: CrawlState,
        cursor: Optional[str] = None,
        works_crawled: Optional[int] = None,
        status: Optional[str] = None,
        error_message: Optional[str] = None,
    ):
        """Update crawl state."""
        if cursor is not None:
            state.last_cursor = cursor
        if works_crawled is not None:
            state.works_crawled = works_crawled
        if status is not None:
            state.status = status
        if error_message is not None:
            state.error_message = error_message
        state.last_crawl_date = datetime.now(timezone.utc)
        session.commit()

    async def crawl(
        self,
        incremental: bool = True,
        max_works: Optional[int] = None,
        batch_size: int = 100,
    ) -> dict:
        """
        Execute crawl operation.

        Args:
            incremental: If True, only fetch new works since last crawl
            max_works: Maximum number of works to fetch
            batch_size: Number of works to process before committing

        Returns:
            Statistics about the crawl operation
        """
        stats = {
            "works_processed": 0,
            "works_new": 0,
            "authors_new": 0,
            "authorships_new": 0,
            "collaborations_updated": 0,
            "errors": [],
        }

        session = get_session()

        try:
            # Get or create crawl state
            state = self._get_crawl_state(session)
            if state is None:
                state = self._create_crawl_state(session)

            # Determine date range for incremental crawl
            from_date = self.from_date
            if incremental and state.last_crawl_date:
                # Start from day before last crawl to catch any missed items
                from_date = (state.last_crawl_date - timedelta(days=1)).strftime("%Y-%m-%d")
                logger.info(f"Incremental crawl from {from_date}")

            self._update_crawl_state(session, state, status="running")

            # Initialize repositories
            author_repo = AuthorRepository(session)
            work_repo = WorkRepository(session)
            collab_repo = CollaborationRepository(session)

            # Create shared batch processor
            processor = BatchProcessor(
                session, author_repo, work_repo, collab_repo, self.weight_calculator,
            )

            # Iterate through works
            batch_works = []
            batch_authors = []
            batch_authorships = []
            # Collect parsed works for batch existence check
            pending_parsed = []

            async for work_data in self.client.iter_works(
                institution_ids=self.institution_ids,
                concept_ids=self.concept_ids,
                source_ids=self.source_ids,
                from_date=from_date,
                max_results=max_works,
            ):
                try:
                    work_dict, authors, authorships = parse_work(
                        work_data,
                        preferred_institution_ids=self.institution_ids,
                    )

                    pending_parsed.append((work_dict, authors, authorships))
                    stats["works_processed"] += 1

                    # Process batch
                    if len(pending_parsed) >= batch_size:
                        # Batch existence check
                        all_ids = [w["id"] for w, _, _ in pending_parsed]
                        existing_ids = work_repo.exists_batch(all_ids)
                        for w, a, au in pending_parsed:
                            if w["id"] not in existing_ids:
                                batch_works.append(w)
                                batch_authors.extend(a)
                                batch_authorships.extend(au)
                                stats["works_new"] += 1

                        new_authors, new_authorships, new_collabs = await processor.process(
                            batch_works, batch_authors, batch_authorships,
                        )
                        stats["authors_new"] += new_authors
                        stats["authorships_new"] += new_authorships
                        stats["collaborations_updated"] += new_collabs

                        batch_works = []
                        batch_authors = []
                        batch_authorships = []
                        pending_parsed = []

                        logger.info(f"Processed {stats['works_processed']} works...")

                except Exception as e:
                    logger.error(f"Error processing work: {e}")
                    stats["errors"].append(str(e))

            # Process remaining batch
            if pending_parsed:
                all_ids = [w["id"] for w, _, _ in pending_parsed]
                existing_ids = work_repo.exists_batch(all_ids)
                for w, a, au in pending_parsed:
                    if w["id"] not in existing_ids:
                        batch_works.append(w)
                        batch_authors.extend(a)
                        batch_authorships.extend(au)
                        stats["works_new"] += 1

            if batch_works:
                new_authors, new_authorships, new_collabs = await processor.process(
                    batch_works, batch_authors, batch_authorships,
                )
                stats["authors_new"] += new_authors
                stats["authorships_new"] += new_authorships
                stats["collaborations_updated"] += new_collabs

            # Update final state
            self._update_crawl_state(
                session,
                state,
                works_crawled=state.works_crawled + stats["works_new"],
                status="completed",
            )

            logger.info(f"Crawl completed: {stats}")

        except Exception as e:
            logger.error(f"Crawl failed: {e}")
            if state:
                self._update_crawl_state(
                    session,
                    state,
                    status="failed",
                    error_message=str(e),
                )
            stats["errors"].append(str(e))
            raise

        finally:
            await self.client.close()
            session.close()

        return stats

    def get_status(self) -> dict:
        """Get current crawl status."""
        with session_scope() as session:
            state = self._get_crawl_state(session)
            if state:
                return {
                    "status": state.status,
                    "last_crawl_date": state.last_crawl_date.isoformat() if state.last_crawl_date else None,
                    "works_crawled": state.works_crawled,
                    "error_message": state.error_message,
                }
            return {
                "status": "not_started",
                "last_crawl_date": None,
                "works_crawled": 0,
                "error_message": None,
            }


async def run_crawl(
    incremental: bool = True,
    max_works: Optional[int] = None,
) -> dict:
    """
    Convenience function to run crawler.

    Args:
        incremental: If True, only fetch new works
        max_works: Maximum works to fetch

    Returns:
        Crawl statistics
    """
    crawler = IncrementalCrawler()
    return await crawler.crawl(incremental=incremental, max_works=max_works)


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    # Initialize database
    from src.database.models import init_database
    init_database()

    # Run crawl
    max_works = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    stats = asyncio.run(run_crawl(incremental=True, max_works=max_works))
    print(f"Crawl completed: {stats}")
