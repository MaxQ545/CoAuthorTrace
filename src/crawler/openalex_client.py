"""
Backward-compatible re-exports.

The client and parser have been split into dedicated modules:
  - ``src.crawler.client``  → ``OpenAlexClient``
  - ``src.crawler.parser``  → ``parse_work``

Existing code that does ``from src.crawler.openalex_client import ...``
continues to work.
"""
from src.crawler.client import OpenAlexClient  # noqa: F401
from src.crawler.parser import parse_work       # noqa: F401
