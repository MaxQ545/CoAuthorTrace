"""
Multi-institution concurrent crawler with persistent state tracking.

Depends only on crawler-internal modules and the ``StorageBackend`` /
``CrawlerConfig`` abstractions.
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from src.crawler.config import CrawlerConfig
from src.crawler.client import OpenAlexClient
from src.crawler.parser import parse_work
from src.crawler.weight import WeightCalculator
from src.crawler.batch_processor import process_batch
from src.crawler.storage import StorageBackend, SQLAlchemyStorage

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
        config: Optional[CrawlerConfig] = None,
        storage_factory=None,
        institution_ids: Optional[list[str]] = None,
        concept_ids: Optional[list[str]] = None,
        max_concurrent: Optional[int] = None,
        rate_limit_per_crawler: Optional[float] = None,
        commit_batch_size: Optional[int] = None,
        cursor_ttl_hours: Optional[int] = None,
    ):
        self.cfg = config or CrawlerConfig.from_settings()

        # Allow overrides
        self.institution_ids = institution_ids or list(self.cfg.target_institutions.keys())
        self.concept_ids = concept_ids
        self.max_concurrent = max_concurrent or self.cfg.max_concurrent
        self.rate_limit_per_crawler = rate_limit_per_crawler or self.cfg.rate_limit_per_crawler
        self.commit_batch_size = commit_batch_size or self.cfg.commit_batch_size
        self.cursor_ttl_hours = cursor_ttl_hours or self.cfg.cursor_ttl_hours

        self.weight_calculator = WeightCalculator(
            half_life_days=self.cfg.time_decay_half_life_days,
        )
        self._storage_factory = storage_factory or (lambda: SQLAlchemyStorage())
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._clients: dict[str, OpenAlexClient] = {}

    def _get_client(self, institution_id: str) -> OpenAlexClient:
        if institution_id not in self._clients:
            self._clients[institution_id] = OpenAlexClient(
                email=self.cfg.openalex_email,
                api_key=self.cfg.openalex_api_key,
                rate_limit=self.rate_limit_per_crawler,
                max_retries=self.cfg.max_retries,
            )
        return self._clients[institution_id]

    async def close_clients(self):
        for client in self._clients.values():
            await client.close()
        self._clients.clear()

    async def crawl_all(
        self,
        incremental: bool = True,
        max_works_per_inst: Optional[int] = None,
    ) -> dict[str, dict]:
        """Concurrently crawl all configured institutions."""
        self._semaphore = asyncio.Semaphore(self.max_concurrent)

        tasks = [
            self._crawl_with_semaphore(inst_id, incremental, max_works_per_inst)
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

    async def _crawl_with_semaphore(
        self, institution_id: str, incremental: bool, max_works: Optional[int],
    ) -> dict:
        async with self._semaphore:
            return await self._crawl_institution(institution_id, incremental, max_works)

    async def _crawl_institution(
        self, institution_id: str, incremental: bool, max_works: Optional[int],
    ) -> dict:
        inst_name = self.cfg.target_institutions.get(institution_id, "Unknown")
        stats = {
            "institution_id": institution_id,
            "institution_name": inst_name,
            "works_processed": 0,
            "works_new": 0,
            "authors_new": 0,
            "authorships_new": 0,
            "collaborations_updated": 0,
            "errors": [],
        }

        storage = self._storage_factory()
        client = self._get_client(institution_id)

        try:
            state = storage.get_institution_crawl_state(institution_id)
            if state is None:
                storage.save_institution_crawl_state(
                    institution_id,
                    institution_name=inst_name,
                    status="running",
                )
                state = storage.get_institution_crawl_state(institution_id) or {}
            else:
                storage.save_institution_crawl_state(
                    institution_id, status="running", error_message="",
                )

            from_date = self.cfg.from_date
            cursor = None

            if incremental and state.get("last_publication_date"):
                from_date = state["last_publication_date"]
                logger.info(f"[{institution_id}] Incremental crawl from {from_date}")

            now = datetime.utcnow()
            valid_until = state.get("cursor_valid_until")
            if state.get("last_cursor") and valid_until and valid_until > now:
                cursor = state["last_cursor"]
                logger.info(f"[{institution_id}] Resuming from saved cursor")

            batch_works: list[dict] = []
            batch_authors: list[dict] = []
            batch_authorships: list[dict] = []
            max_pub_date = state.get("last_publication_date")

            async for work_data in self._iter_works_with_cursor(
                client=client, institution_id=institution_id,
                from_date=from_date, cursor=cursor,
                max_results=max_works,
                storage=storage,
            ):
                try:
                    work_dict, authors, authorships = parse_work(
                        work_data, preferred_institution_ids=[institution_id],
                    )

                    pub_date_str = work_data.get("publication_date")
                    if pub_date_str:
                        if max_pub_date is None or pub_date_str > max_pub_date:
                            max_pub_date = pub_date_str

                    if not storage.work_exists(work_dict["id"]):
                        batch_works.append(work_dict)
                        batch_authors.extend(authors)
                        batch_authorships.extend(authorships)
                        stats["works_new"] += 1

                    stats["works_processed"] += 1

                    if len(batch_works) >= self.commit_batch_size:
                        na, nas, nc = process_batch(
                            storage, self.weight_calculator,
                            batch_works, batch_authors, batch_authorships,
                        )
                        stats["authors_new"] += na
                        stats["authorships_new"] += nas
                        stats["collaborations_updated"] += nc
                        batch_works, batch_authors, batch_authorships = [], [], []

                        logger.info(
                            f"[{institution_id}] Processed {stats['works_processed']} works, "
                            f"{stats['works_new']} new"
                        )

                except Exception as e:
                    logger.error(f"[{institution_id}] Error processing work: {e}")
                    stats["errors"].append(str(e))

            if batch_works:
                na, nas, nc = process_batch(
                    storage, self.weight_calculator,
                    batch_works, batch_authors, batch_authorships,
                )
                stats["authors_new"] += na
                stats["authorships_new"] += nas
                stats["collaborations_updated"] += nc

            prev_crawled = (state or {}).get("total_works_crawled", 0) or 0
            storage.save_institution_crawl_state(
                institution_id,
                last_publication_date=max_pub_date,
                total_works_crawled=prev_crawled + stats["works_new"],
                status="completed",
                completed=True,
            )
            stats["status"] = "completed"
            logger.info(f"[{institution_id}] Crawl completed: {stats['works_new']} new works")

        except Exception as e:
            logger.error(f"[{institution_id}] Crawl failed: {e}")
            storage.save_institution_crawl_state(
                institution_id, status="failed", error_message=str(e),
            )
            stats["status"] = "failed"
            stats["errors"].append(str(e))
        finally:
            storage.close()

        return stats

    async def _iter_works_with_cursor(
        self, client: OpenAlexClient, institution_id: str,
        from_date: str, cursor: Optional[str],
        max_results: Optional[int],
        storage: StorageBackend,
    ):
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
                storage.save_institution_crawl_state(
                    institution_id,
                    last_cursor=current_cursor,
                    cursor_valid_until=cursor_valid,
                )
                logger.debug(f"[{institution_id}] Saved cursor checkpoint")

            if not results:
                break


def get_all_institution_states(
    storage: Optional[StorageBackend] = None,
    config: Optional[CrawlerConfig] = None,
) -> list[dict]:
    """Get crawl states for all institutions."""
    cfg = config or CrawlerConfig.from_settings()

    if storage is None:
        storage = SQLAlchemyStorage()

    target_institutions = cfg.target_institutions
    result = []
    for inst_id in target_institutions:
        state = storage.get_institution_crawl_state(inst_id)
        if state:
            now = datetime.utcnow()
            result.append({
                **state,
                "institution_name": state.get("institution_name") or target_institutions.get(inst_id, "Unknown"),
                "has_pending_cursor": bool(
                    state.get("last_cursor")
                    and state.get("cursor_valid_until")
                    and state["cursor_valid_until"] > now
                ),
            })
    storage.close()
    return result


async def run_multi_crawl(
    institution_ids: Optional[list[str]] = None,
    concept_ids: Optional[list[str]] = None,
    incremental: bool = True,
    max_works_per_inst: Optional[int] = None,
    max_concurrent: Optional[int] = None,
    config: Optional[CrawlerConfig] = None,
    storage_factory=None,
) -> dict[str, dict]:
    """Convenience function to run multi-institution crawler."""
    crawler = MultiInstitutionCrawler(
        config=config,
        storage_factory=storage_factory,
        institution_ids=institution_ids,
        concept_ids=concept_ids,
        max_concurrent=max_concurrent,
    )
    return await crawler.crawl_all(incremental=incremental, max_works_per_inst=max_works_per_inst)
