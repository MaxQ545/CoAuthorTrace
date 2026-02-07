"""
Incremental crawler for OpenAlex data with state persistence.

Depends only on crawler-internal modules (client, parser, weight,
batch_processor) and the ``StorageBackend`` / ``CrawlerConfig`` abstractions.
"""
import asyncio
import hashlib
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


class IncrementalCrawler:
    """Incremental crawler that tracks state and only fetches new data."""

    def __init__(
        self,
        config: Optional[CrawlerConfig] = None,
        storage: Optional[StorageBackend] = None,
    ):
        self.cfg = config or CrawlerConfig.from_settings()

        self.client = OpenAlexClient(
            email=self.cfg.openalex_email,
            api_key=self.cfg.openalex_api_key,
            rate_limit=self.cfg.rate_limit,
            max_retries=self.cfg.max_retries,
        )
        self.weight_calculator = WeightCalculator(
            half_life_days=self.cfg.time_decay_half_life_days,
        )
        self._storage = storage
        self._scope_hash = self._compute_scope_hash()

    def _compute_scope_hash(self) -> str:
        scope_str = (
            f"{sorted(self.cfg.institution_ids)}"
            f"|{sorted(self.cfg.concept_ids)}"
            f"|{sorted(self.cfg.source_ids)}"
        )
        return hashlib.sha256(scope_str.encode()).hexdigest()[:16]

    def _get_storage(self) -> StorageBackend:
        if self._storage is None:
            self._storage = SQLAlchemyStorage()
        return self._storage

    async def crawl(
        self,
        incremental: bool = True,
        max_works: Optional[int] = None,
        batch_size: int = 100,
    ) -> dict:
        stats = {
            "works_processed": 0,
            "works_new": 0,
            "authors_new": 0,
            "authorships_new": 0,
            "collaborations_updated": 0,
            "errors": [],
        }

        storage = self._get_storage()

        try:
            state = storage.get_crawl_state(self._scope_hash)
            if state is None:
                storage.save_crawl_state(self._scope_hash, status="idle", works_crawled=0)
                state = storage.get_crawl_state(self._scope_hash)

            from_date = self.cfg.from_date
            if incremental and state and state.get("last_crawl_date"):
                last_dt = state["last_crawl_date"]
                if isinstance(last_dt, str):
                    last_dt = datetime.fromisoformat(last_dt)
                from_date = (last_dt - timedelta(days=1)).strftime("%Y-%m-%d")
                logger.info(f"Incremental crawl from {from_date}")

            storage.save_crawl_state(self._scope_hash, status="running")

            batch_works: list[dict] = []
            batch_authors: list[dict] = []
            batch_authorships: list[dict] = []

            async for work_data in self.client.iter_works(
                institution_ids=self.cfg.institution_ids,
                concept_ids=self.cfg.concept_ids,
                source_ids=self.cfg.source_ids,
                from_date=from_date,
                max_results=max_works,
            ):
                try:
                    work_dict, authors, authorships = parse_work(
                        work_data,
                        preferred_institution_ids=self.cfg.institution_ids,
                    )

                    if not storage.work_exists(work_dict["id"]):
                        batch_works.append(work_dict)
                        batch_authors.extend(authors)
                        batch_authorships.extend(authorships)
                        stats["works_new"] += 1

                    stats["works_processed"] += 1

                    if len(batch_works) >= batch_size:
                        na, nas, nc = process_batch(
                            storage, self.weight_calculator,
                            batch_works, batch_authors, batch_authorships,
                        )
                        stats["authors_new"] += na
                        stats["authorships_new"] += nas
                        stats["collaborations_updated"] += nc
                        batch_works, batch_authors, batch_authorships = [], [], []
                        logger.info(f"Processed {stats['works_processed']} works...")

                except Exception as e:
                    logger.error(f"Error processing work: {e}")
                    stats["errors"].append(str(e))

            if batch_works:
                na, nas, nc = process_batch(
                    storage, self.weight_calculator,
                    batch_works, batch_authors, batch_authorships,
                )
                stats["authors_new"] += na
                stats["authorships_new"] += nas
                stats["collaborations_updated"] += nc

            prev_crawled = (state or {}).get("works_crawled", 0) or 0
            storage.save_crawl_state(
                self._scope_hash,
                works_crawled=prev_crawled + stats["works_new"],
                status="completed",
            )
            logger.info(f"Crawl completed: {stats}")

        except Exception as e:
            logger.error(f"Crawl failed: {e}")
            storage.save_crawl_state(self._scope_hash, status="failed", error_message=str(e))
            stats["errors"].append(str(e))
            raise
        finally:
            await self.client.close()
            storage.close()

        return stats


async def run_crawl(
    incremental: bool = True,
    max_works: Optional[int] = None,
    config: Optional[CrawlerConfig] = None,
    storage: Optional[StorageBackend] = None,
) -> dict:
    """Convenience function to run crawler."""
    crawler = IncrementalCrawler(config=config, storage=storage)
    return await crawler.crawl(incremental=incremental, max_works=max_works)


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    from src.database.engine import init_database
    init_database()
    max_works = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    stats = asyncio.run(run_crawl(incremental=True, max_works=max_works))
    print(f"Crawl completed: {stats}")
