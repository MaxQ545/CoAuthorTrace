"""Crawler module for OpenAlex data collection."""
from .openalex_client import OpenAlexClient
from .incremental_crawler import IncrementalCrawler

__all__ = ["OpenAlexClient", "IncrementalCrawler"]
