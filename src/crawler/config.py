"""
Standalone crawler configuration.

This module provides a self-contained CrawlerConfig dataclass that holds all
parameters the crawler needs, with no dependency on the project-wide settings.

Usage as standalone:
    config = CrawlerConfig(
        openalex_email="me@example.com",
        institution_ids=["I99065089"],
    )

Usage within the CoAuthorTrace project (auto-fills from project settings):
    from src.crawler.config import CrawlerConfig
    config = CrawlerConfig.from_settings()
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CrawlerConfig:
    """All parameters the crawler needs to operate."""

    # ---- OpenAlex API ----
    openalex_email: Optional[str] = None
    openalex_api_key: Optional[str] = None
    rate_limit: float = 10.0
    max_retries: int = 3

    # ---- scope ----
    institution_ids: list[str] = field(default_factory=lambda: ["I114922016"])
    concept_ids: list[str] = field(default_factory=lambda: [
        "C41008148",    # Computer Science
        "C154945302",   # Artificial Intelligence
        "C119857082",   # Machine Learning
    ])
    source_ids: list[str] = field(default_factory=list)
    from_date: str = "2020-01-01"

    # ---- multi-institution crawler ----
    max_concurrent: int = 3
    rate_limit_per_crawler: float = 2.5
    commit_batch_size: int = 500
    cursor_ttl_hours: int = 24

    # ---- weight calculator ----
    time_decay_half_life_days: int = 730  # 2 years

    # ---- institution catalog ----
    target_institutions: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_settings(cls) -> CrawlerConfig:
        """
        Build a CrawlerConfig from the project-wide settings.

        This is the bridge between the standalone crawler and the project.
        """
        from config.settings import settings, TARGET_INSTITUTIONS

        return cls(
            openalex_email=settings.crawler.openalex_email,
            openalex_api_key=settings.crawler.openalex_api_key,
            rate_limit=settings.crawler.rate_limit,
            max_retries=settings.crawler.max_retries,
            institution_ids=settings.scope.institution_ids,
            concept_ids=settings.scope.concept_ids,
            source_ids=settings.scope.source_ids,
            from_date=settings.scope.from_date,
            max_concurrent=settings.multi_crawler.max_concurrent,
            rate_limit_per_crawler=settings.multi_crawler.rate_limit_per_crawler,
            commit_batch_size=settings.multi_crawler.commit_batch_size,
            cursor_ttl_hours=settings.multi_crawler.cursor_ttl_hours,
            time_decay_half_life_days=settings.analysis.time_decay_half_life_days,
            target_institutions=dict(TARGET_INSTITUTIONS),
        )
