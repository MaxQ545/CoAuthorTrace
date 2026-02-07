"""
Incremental crawler for OpenAlex data with state persistence.
"""
import asyncio
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from config.settings import settings
from src.database.models import CrawlState, get_session, session_scope
from src.database.repositories import (
    AuthorRepository,
    WorkRepository,
    CollaborationRepository,
)
from src.crawler.openalex_client import OpenAlexClient, parse_work
from src.crawler.batch_processor import process_batch
from src.analysis.weight_calculator import WeightCalculator

logger = logging.getLogger(__name__)


class IncrementalCrawler:
    """Incremental crawler that tracks state and only fetches new data."""

    def __init__(
        self,
        institution_ids: Optional[list[str]] = None,
        concept_ids: Optional[list[str]] = None,
        source_ids: Optional[list[str]] = None,
        from_date: Optional[str] = None,
    ):
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
        scope_str = f"{sorted(self.institution_ids)}|{sorted(self.concept_ids)}|{sorted(self.source_ids)}"
        return hashlib.sha256(scope_str.encode()).hexdigest()[:16]

    def _get_crawl_state(self, session: Session) -> Optional[CrawlState]:
        return (
            session.query(CrawlState)
            .filter(CrawlState.scope_hash == self._scope_hash)
            .first()
        )

    def _create_crawl_state(self, session: Session) -> CrawlState:
        state = CrawlState(scope_hash=self._scope_hash, status="idle", works_crawled=0)
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
        if cursor is not None:
            state.last_cursor = cursor
        if works_crawled is not None:
            state.works_crawled = works_crawled
        if status is not None:
            state.status = status
        if error_message is not None:
            state.error_message = error_message
        state.last_crawl_date = datetime.utcnow()
        session.commit()

    async def crawl(
        self,
        incremental: bool = True,
        max_works: Optional[int] = None,
        batch_size: int = 100,
    ) -> dict:
        """Execute crawl operation."""
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
            state = self._get_crawl_state(session)
            if state is None:
                state = self._create_crawl_state(session)

            from_date = self.from_date
            if incremental and state.last_crawl_date:
                from_date = (state.last_crawl_date - timedelta(days=1)).strftime("%Y-%m-%d")
                logger.info(f"Incremental crawl from {from_date}")

            self._update_crawl_state(session, state, status="running")

            author_repo = AuthorRepository(session)
            work_repo = WorkRepository(session)
            collab_repo = CollaborationRepository(session)

            batch_works = []
            batch_authors = []
            batch_authorships = []

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

                    if not work_repo.exists(work_dict["id"]):
                        batch_works.append(work_dict)
                        batch_authors.extend(authors)
                        batch_authorships.extend(authorships)
                        stats["works_new"] += 1

                    stats["works_processed"] += 1

                    if len(batch_works) >= batch_size:
                        new_a, new_as, new_c = process_batch(
                            session, author_repo, work_repo, collab_repo,
                            batch_works, batch_authors, batch_authorships,
                            self.weight_calculator,
                        )
                        stats["authors_new"] += new_a
                        stats["authorships_new"] += new_as
                        stats["collaborations_updated"] += new_c
                        batch_works, batch_authors, batch_authorships = [], [], []
                        logger.info(f"Processed {stats['works_processed']} works...")

                except Exception as e:
                    logger.error(f"Error processing work: {e}")
                    stats["errors"].append(str(e))

            # Process remaining
            if batch_works:
                new_a, new_as, new_c = process_batch(
                    session, author_repo, work_repo, collab_repo,
                    batch_works, batch_authors, batch_authorships,
                    self.weight_calculator,
                )
                stats["authors_new"] += new_a
                stats["authorships_new"] += new_as
                stats["collaborations_updated"] += new_c

            self._update_crawl_state(
                session, state,
                works_crawled=state.works_crawled + stats["works_new"],
                status="completed",
            )
            logger.info(f"Crawl completed: {stats}")

        except Exception as e:
            logger.error(f"Crawl failed: {e}")
            if state:
                self._update_crawl_state(session, state, status="failed", error_message=str(e))
            stats["errors"].append(str(e))
            raise
        finally:
            await self.client.close()
            session.close()

        return stats

    def get_status(self) -> dict:
        with session_scope() as session:
            state = self._get_crawl_state(session)
            if state:
                return {
                    "status": state.status,
                    "last_crawl_date": state.last_crawl_date.isoformat() if state.last_crawl_date else None,
                    "works_crawled": state.works_crawled,
                    "error_message": state.error_message,
                }
            return {"status": "not_started", "last_crawl_date": None, "works_crawled": 0, "error_message": None}


async def run_crawl(
    incremental: bool = True,
    max_works: Optional[int] = None,
) -> dict:
    """Convenience function to run crawler."""
    crawler = IncrementalCrawler()
    return await crawler.crawl(incremental=incremental, max_works=max_works)


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    from src.database.engine import init_database
    init_database()
    max_works = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    stats = asyncio.run(run_crawl(incremental=True, max_works=max_works))
    print(f"Crawl completed: {stats}")
