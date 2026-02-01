"""Crawler module for OpenAlex data collection."""
from .openalex_client import OpenAlexClient
from .incremental_crawler import IncrementalCrawler
from .multi_institution_crawler import MultiInstitutionCrawler

__all__ = ["OpenAlexClient", "IncrementalCrawler", "MultiInstitutionCrawler"]
