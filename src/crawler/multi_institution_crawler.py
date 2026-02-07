"""
Multi-institution concurrent crawler with persistent state tracking.
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from config.settings import settings, TARGET_INSTITUTIONS
from src.database.models import (
    InstitutionCrawlState,
    get_session,
    session_scope,
)
from src.database.repositories import (
    AuthorRepository,
    WorkRepository,
    CollaborationRepository,
)
from src.crawler.openalex_client import OpenAlexClient, parse_work
from src.crawler.batch_processor import process_batch
from src.analysis.weight_calculator import WeightCalculator

logger = logging.getLogger(__name__)


class MultiInstitutionCrawler:
    """
    Concurrent crawler for multiple institutions with independent state tracking.

    Features:
    - Concurrent crawling with configurable parallelism
    - Per-institution state persistence for resumable crawling
    - True incremental crawling based on publication date
    - Cursor persistence for crash recovery
    """

    def __init__(
        self,
        institution_ids: Optional[list[str]] = None,
        concept_ids: Optional[list[str]] = None,
        max_concurrent: Optional[int] = None,
        rate_limit_per_crawler: Optional[float] = None,
        commit_batch_size: Optional[int] = None,
        cursor_ttl_hours: Optional[int] = None,
    ):
        self.institution_ids = institution_ids or list(TARGET_INSTITUTIONS.keys())
        self.concept_ids = concept_ids
        self.max_concurrent = max_concurrent or settings.multi_crawler.max_concurrent
        self.rate_limit_per_crawler = rate_limit_per_crawler or settings.multi_crawler.rate_limit_per_crawler
        self.commit_batch_size = commit_batch_size or settings.multi_crawler.commit_batch_size
        self.cursor_ttl_hours = cursor_ttl_hours or settings.multi_crawler.cursor_ttl_hours

        self.weight_calculator = WeightCalculator()
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._clients: dict[str, OpenAlexClient] = {}

    def _get_client(self, institution_id: str) -> OpenAlexClient:
        if institution_id not in self._clients:
            self._clients[institution_id] = OpenAlexClient(
                email=settings.crawler.openalex_email,
                rate_limit=self.rate_limit_per_crawler,
                max_retries=settings.crawler.max_retries,
            )
        return self._clients[institution_id]

    async def close_clients(self):
        for client in self._clients.values():
            await client.close()
        self._clients.clear()

    def _get_or_create_state(
        self, session: Session, institution_id: str
    ) -> InstitutionCrawlState:
        state = (
            session.query(InstitutionCrawlState)
            .filter(InstitutionCrawlState.institution_id == institution_id)
            .first()
        )
        if state is None:
            institution_name = TARGET_INSTITUTIONS.get(institution_id, "Unknown")
            state = InstitutionCrawlState(
                institution_id=institution_id,
                institution_name=institution_name,
                status="idle",
                total_works_crawled=0,
            )
            session.add(state)
            session.commit()
        return state

    def _update_state(
        self,
        session: Session,
        state: InstitutionCrawlState,
        cursor: Optional[str] = None,
        cursor_valid_until: Optional[datetime] = None,
        last_publication_date: Optional[str] = None,
        total_works_crawled: Optional[int] = None,
        status: Optional[str] = None,
        error_message: Optional[str] = None,
        completed: bool = False,
    ):
        if cursor is not None:
            state.last_cursor = cursor
        if cursor_valid_until is not None:
            state.cursor_valid_until = cursor_valid_until
        if last_publication_date is not None:
            if state.last_publication_date is None or last_publication_date > state.last_publication_date:
                state.last_publication_date = last_publication_date
        if total_works_crawled is not None:
            state.total_works_crawled = total_works_crawled
        if status is not None:
            state.status = status
        if error_message is not None:
            state.error_message = error_message
        if completed:
            state.last_crawl_completed = datetime.utcnow()
            state.last_cursor = None
            state.cursor_valid_until = None
        session.commit()

    async def crawl_all(
        self,
        incremental: bool = True,
        max_works_per_inst: Optional[int] = None,
    ) -> dict[str, dict]:
        """Concurrently crawl all configured institutions."""
        self._semaphore = asyncio.Semaphore(self.max_concurrent)

        tasks = [
            self._crawl_institution_with_semaphore(inst_id, incremental, max_works_per_inst)
            for inst_id in self.institution_ids
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)
        await self.close_clients()

        all_stats = {}
        for inst_id, result in zip(self.institution_ids, results):
            if isinstance(result, Exception):
                all_stats[inst_id] = {"status": "failed", "error": str(result)}
            else:
                all_stats[inst_id] = result
        return all_stats

    async def _crawl_institution_with_semaphore(
        self, institution_id: str, incremental: bool, max_works: Optional[int],
    ) -> dict:
        async with self._semaphore:
            return await self._crawl_institution(institution_id, incremental, max_works)

    async def _crawl_institution(
        self, institution_id: str, incremental: bool, max_works: Optional[int],
    ) -> dict:
        """Crawl a single institution with state tracking."""
        stats = {
            "institution_id": institution_id,
            "institution_name": TARGET_INSTITUTIONS.get(institution_id, "Unknown"),
            "works_processed": 0,
            "works_new": 0,
            "authors_new": 0,
            "authorships_new": 0,
            "collaborations_updated": 0,
            "errors": [],
        }

        session = get_session()
        client = self._get_client(institution_id)

        try:
            state = self._get_or_create_state(session, institution_id)
            self._update_state(session, state, status="running", error_message=None)

            from_date = settings.scope.from_date
            cursor = None

            if incremental and state.last_publication_date:
                from_date = state.last_publication_date
                logger.info(f"[{institution_id}] Incremental crawl from {from_date}")

            now = datetime.utcnow()
            if state.last_cursor and state.cursor_valid_until and state.cursor_valid_until > now:
                cursor = state.last_cursor
                logger.info(f"[{institution_id}] Resuming from saved cursor")

            author_repo = AuthorRepository(session)
            work_repo = WorkRepository(session)
            collab_repo = CollaborationRepository(session)

            batch_works = []
            batch_authors = []
            batch_authorships = []
            max_pub_date = state.last_publication_date

            async for work_data in self._iter_works_with_cursor(
                client=client, institution_id=institution_id,
                from_date=from_date, cursor=cursor,
                max_results=max_works, state=state, session=session,
            ):
                try:
                    work_dict, authors, authorships = parse_work(
                        work_data, preferred_institution_ids=[institution_id],
                    )

                    pub_date_str = work_data.get("publication_date")
                    if pub_date_str:
                        if max_pub_date is None or pub_date_str > max_pub_date:
                            max_pub_date = pub_date_str

                    if not work_repo.exists(work_dict["id"]):
                        batch_works.append(work_dict)
                        batch_authors.extend(authors)
                        batch_authorships.extend(authorships)
                        stats["works_new"] += 1

                    stats["works_processed"] += 1

                    if len(batch_works) >= self.commit_batch_size:
                        new_a, new_as, new_c = process_batch(
                            session, author_repo, work_repo, collab_repo,
                            batch_works, batch_authors, batch_authorships,
                            self.weight_calculator,
                        )
                        stats["authors_new"] += new_a
                        stats["authorships_new"] += new_as
                        stats["collaborations_updated"] += new_c
                        batch_works, batch_authors, batch_authorships = [], [], []

                        logger.info(
                            f"[{institution_id}] Processed {stats['works_processed']} works, "
                            f"{stats['works_new']} new"
                        )

                except Exception as e:
                    logger.error(f"[{institution_id}] Error processing work: {e}")
                    stats["errors"].append(str(e))

            if batch_works:
                new_a, new_as, new_c = process_batch(
                    session, author_repo, work_repo, collab_repo,
                    batch_works, batch_authors, batch_authorships,
                    self.weight_calculator,
                )
                stats["authors_new"] += new_a
                stats["authorships_new"] += new_as
                stats["collaborations_updated"] += new_c

            self._update_state(
                session, state,
                last_publication_date=max_pub_date,
                total_works_crawled=state.total_works_crawled + stats["works_new"],
                status="completed", completed=True,
            )
            stats["status"] = "completed"
            logger.info(f"[{institution_id}] Crawl completed: {stats['works_new']} new works")

        except Exception as e:
            logger.error(f"[{institution_id}] Crawl failed: {e}")
            if state:
                self._update_state(session, state, status="failed", error_message=str(e))
            stats["status"] = "failed"
            stats["errors"].append(str(e))
        finally:
            session.close()

        return stats

    async def _iter_works_with_cursor(
        self, client: OpenAlexClient, institution_id: str,
        from_date: str, cursor: Optional[str],
        max_results: Optional[int],
        state: InstitutionCrawlState, session: Session,
    ):
        """Iterate through works with cursor persistence."""
        current_cursor = cursor or "*"
        total_yielded = 0
        batch_count = 0

        while current_cursor:
            response = await client.get_works(
                institution_ids=[institution_id],
                concept_ids=self.concept_ids,
                from_date=from_date,
                cursor=current_cursor,
                per_page=200,
            )

            results = response.get("results", [])
            meta = response.get("meta", {})

            for work in results:
                yield work
                total_yielded += 1
                if max_results and total_yielded >= max_results:
                    return

            current_cursor = meta.get("next_cursor")
            batch_count += 1

            if current_cursor and batch_count % 5 == 0:
                cursor_valid = datetime.utcnow() + timedelta(hours=self.cursor_ttl_hours)
                self._update_state(session, state, cursor=current_cursor, cursor_valid_until=cursor_valid)
                logger.debug(f"[{institution_id}] Saved cursor checkpoint")

            if not results:
                break


def get_all_institution_states() -> list[dict]:
    """Get crawl states for all institutions."""
    with session_scope() as session:
        states = session.query(InstitutionCrawlState).all()
        return [
            {
                "institution_id": s.institution_id,
                "institution_name": s.institution_name or TARGET_INSTITUTIONS.get(s.institution_id, "Unknown"),
                "status": s.status,
                "total_works_crawled": s.total_works_crawled,
                "last_publication_date": s.last_publication_date,
                "last_crawl_completed": s.last_crawl_completed.isoformat() if s.last_crawl_completed else None,
                "has_pending_cursor": bool(
                    s.last_cursor and s.cursor_valid_until and s.cursor_valid_until > datetime.utcnow()
                ),
                "error_message": s.error_message,
            }
            for s in states
        ]


async def run_multi_crawl(
    institution_ids: Optional[list[str]] = None,
    concept_ids: Optional[list[str]] = None,
    incremental: bool = True,
    max_works_per_inst: Optional[int] = None,
    max_concurrent: Optional[int] = None,
) -> dict[str, dict]:
    """Convenience function to run multi-institution crawler."""
    crawler = MultiInstitutionCrawler(
        institution_ids=institution_ids,
        concept_ids=concept_ids,
        max_concurrent=max_concurrent,
    )
    return await crawler.crawl_all(incremental=incremental, max_works_per_inst=max_works_per_inst)
