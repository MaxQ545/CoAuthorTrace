"""
Crawler package for OpenAlex data collection.

This package is designed to be self-contained.  Core modules (client, parser,
weight, config) have **no** project-level dependencies and can be used
standalone.  The ``StorageBackend`` protocol in ``storage.py`` defines the
persistence contract; ``SQLAlchemyStorage`` is the default adapter bridging to
the project's database layer.

Standalone modules (zero project dependencies):
    - client.py       – OpenAlexClient (async HTTP with rate limiting)
    - parser.py       – parse_work() (raw API response → flat dicts)
    - weight.py       – WeightCalculator (collaboration edge weights)
    - config.py       – CrawlerConfig dataclass

Modules with storage dependency:
    - storage.py      – StorageBackend protocol + SQLAlchemyStorage adapter
    - batch_processor.py – shared batch insertion logic
    - incremental_crawler.py – incremental single-scope crawler
    - multi_institution_crawler.py – concurrent multi-institution crawler
"""
from src.crawler.client import OpenAlexClient
from src.crawler.parser import parse_work
from src.crawler.config import CrawlerConfig
from src.crawler.weight import WeightCalculator
from src.crawler.incremental_crawler import IncrementalCrawler
from src.crawler.multi_institution_crawler import MultiInstitutionCrawler

__all__ = [
    "OpenAlexClient",
    "parse_work",
    "CrawlerConfig",
    "WeightCalculator",
    "IncrementalCrawler",
    "MultiInstitutionCrawler",
]
