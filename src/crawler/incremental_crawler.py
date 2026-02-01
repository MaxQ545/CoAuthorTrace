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
from src.database.models import (
    CrawlState,
    Author,
    Work,
    Authorship,
    get_session,
    session_scope,
)
from src.database.repositories import (
    AuthorRepository,
    WorkRepository,
    CollaborationRepository,
)
from src.crawler.openalex_client import OpenAlexClient, parse_work
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
        state.last_crawl_date = datetime.utcnow()
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

            # Iterate through works
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

                    # Check if work already exists
                    if not work_repo.exists(work_dict["id"]):
                        batch_works.append(work_dict)
                        batch_authors.extend(authors)
                        batch_authorships.extend(authorships)
                        stats["works_new"] += 1

                    stats["works_processed"] += 1

                    # Process batch
                    if len(batch_works) >= batch_size:
                        new_authors, new_authorships, new_collabs = await self._process_batch(
                            session,
                            author_repo,
                            work_repo,
                            collab_repo,
                            batch_works,
                            batch_authors,
                            batch_authorships,
                        )
                        stats["authors_new"] += new_authors
                        stats["authorships_new"] += new_authorships
                        stats["collaborations_updated"] += new_collabs

                        batch_works = []
                        batch_authors = []
                        batch_authorships = []

                        logger.info(f"Processed {stats['works_processed']} works...")

                except Exception as e:
                    logger.error(f"Error processing work: {e}")
                    stats["errors"].append(str(e))

            # Process remaining batch
            if batch_works:
                new_authors, new_authorships, new_collabs = await self._process_batch(
                    session,
                    author_repo,
                    work_repo,
                    collab_repo,
                    batch_works,
                    batch_authors,
                    batch_authorships,
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

    async def _process_batch(
        self,
        session: Session,
        author_repo: AuthorRepository,
        work_repo: WorkRepository,
        collab_repo: CollaborationRepository,
        works: list[dict],
        authors: list[dict],
        authorships: list[dict],
    ) -> tuple[int, int, int]:
        """
        Process a batch of works, authors, and authorships.

        Returns:
            Tuple of (new_authors, new_authorships, new_collaborations)
        """
        new_authors = 0
        new_authorships = 0
        new_collaborations = 0

        # Insert authors
        for author_data in authors:
            author_id = author_data["id"]
            existing = author_repo.get_by_id(author_id)
            if not existing:
                author = Author(**author_data)
                session.add(author)
                new_authors += 1
            else:
                # Refresh core fields when new data is present
                if author_data.get("orcid"):
                    existing.orcid = author_data["orcid"]
                if author_data.get("last_known_institution_id") or author_data.get("last_known_institution_name"):
                    existing.last_known_institution_id = author_data.get("last_known_institution_id")
                    existing.last_known_institution_name = author_data.get("last_known_institution_name")
                # Update stats if available
                if author_data.get("works_count"):
                    existing.works_count = author_data["works_count"]
                if author_data.get("cited_by_count"):
                    existing.cited_by_count = author_data["cited_by_count"]

        session.flush()

        # Insert works (skip duplicates)
        for work_data in works:
            if not work_repo.exists(work_data["id"]):
                work = Work(**work_data)
                session.add(work)

        try:
            session.flush()
        except Exception as e:
            # Handle any remaining duplicates
            session.rollback()
            logger.warning(f"Batch flush error, retrying one by one: {e}")
            for work_data in works:
                try:
                    if not work_repo.exists(work_data["id"]):
                        work = Work(**work_data)
                        session.add(work)
                        session.flush()
                except Exception:
                    session.rollback()

        # Insert authorships and build collaborations
        work_authorships = {}  # work_id -> list of authorships

        for auth_data in authorships:
            # Check if authorship exists
            existing = (
                session.query(Authorship)
                .filter(
                    Authorship.author_id == auth_data["author_id"],
                    Authorship.work_id == auth_data["work_id"],
                )
                .first()
            )

            if not existing:
                authorship = Authorship(**auth_data)
                session.add(authorship)
                new_authorships += 1

                # Group by work for collaboration building
                work_id = auth_data["work_id"]
                if work_id not in work_authorships:
                    work_authorships[work_id] = []
                work_authorships[work_id].append(auth_data)

        session.flush()

        # Build collaboration edges
        for work_id, work_auths in work_authorships.items():
            if len(work_auths) < 2:
                continue

            # Get publication date
            work = work_repo.get_by_id(work_id)
            pub_date = work.publication_date if work else None

            # Create edges between all author pairs
            for i, auth1 in enumerate(work_auths):
                for auth2 in work_auths[i + 1:]:
                    weight = self.weight_calculator.calculate_weight(
                        position_1=auth1["author_position"],
                        position_2=auth2["author_position"],
                        is_corresponding_1=auth1.get("is_corresponding", False),
                        is_corresponding_2=auth2.get("is_corresponding", False),
                        total_authors=len(work_auths),
                        publication_date=pub_date,
                    )
                    collab_repo.create_or_update(
                        auth1["author_id"],
                        auth2["author_id"],
                        weight,
                        pub_date,
                    )
                    new_collaborations += 1

        session.commit()

        return new_authors, new_authorships, new_collaborations

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
