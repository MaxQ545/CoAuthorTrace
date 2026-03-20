"""
OpenAlex API client with rate limiting and cursor pagination.
"""
import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Optional, AsyncGenerator
from urllib.parse import urlencode

import httpx

from config.settings import settings

logger = logging.getLogger(__name__)


class RateLimiter:
    """Token bucket rate limiter for API requests."""

    def __init__(self, rate: float = 8.0):
        """
        Initialize rate limiter.

        Args:
            rate: Maximum requests per second
        """
        self.rate = rate
        self.tokens = rate
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self):
        """Acquire a token, waiting if necessary."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            self.tokens = min(self.rate, self.tokens + elapsed * self.rate)
            self.last_update = now

            if self.tokens < 1:
                wait_time = (1 - self.tokens) / self.rate
                await asyncio.sleep(wait_time)
                self.tokens = 0
            else:
                self.tokens -= 1


class OpenAlexClient:
    """
    Async client for OpenAlex API with rate limiting.

    OpenAlex API docs: https://docs.openalex.org/
    """

    BASE_URL = "https://api.openalex.org"

    def __init__(
        self,
        email: Optional[str] = None,
        api_key: Optional[str] = None,
        rate_limit: float = 10.0,
        max_retries: int = 3,
    ):
        """
        Initialize OpenAlex client.

        Args:
            email: Email for polite pool
            api_key: OpenAlex API key for higher rate limits
            rate_limit: Requests per second
            max_retries: Maximum retry attempts for failed requests
        """
        self.email = email or settings.crawler.openalex_email
        self.api_key = api_key or settings.crawler.openalex_api_key
        self.rate_limiter = RateLimiter(rate_limit)
        self.max_retries = max_retries
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            headers = {"User-Agent": "CoauthorTracing/1.0"}
            if self.email:
                headers["mailto"] = self.email
            self._client = httpx.AsyncClient(
                headers=headers,
                timeout=30.0,
                follow_redirects=True,
            )
        return self._client

    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _request(
        self,
        endpoint: str,
        params: Optional[dict] = None
    ) -> dict:
        """
        Make a rate-limited API request with retries.

        Args:
            endpoint: API endpoint (e.g., "/works")
            params: Query parameters

        Returns:
            JSON response as dict
        """
        client = await self._get_client()
        url = f"{self.BASE_URL}{endpoint}"

        if params:
            if self.api_key:
                params["api_key"] = self.api_key
            elif self.email:
                params["mailto"] = self.email
            url = f"{url}?{urlencode(params, safe=',|:')}"

        for attempt in range(self.max_retries):
            await self.rate_limiter.acquire()

            try:
                response = await client.get(url)
                response.raise_for_status()
                return response.json()

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    # Rate limited, wait and retry
                    wait_time = 2 ** attempt
                    logger.warning(f"Rate limited, waiting {wait_time}s...")
                    await asyncio.sleep(wait_time)
                elif e.response.status_code >= 500:
                    # Server error, retry
                    wait_time = 2 ** attempt
                    logger.warning(f"Server error {e.response.status_code}, retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    raise

            except httpx.RequestError as e:
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"Request error: {e}, retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    raise

        raise Exception(f"Failed after {self.max_retries} retries")

    def _build_works_filter(
        self,
        institution_ids: Optional[list[str]] = None,
        concept_ids: Optional[list[str]] = None,
        source_ids: Optional[list[str]] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> str:
        """Build OpenAlex filter string for works endpoint."""
        filters = []

        if institution_ids:
            # Filter by institution affiliations
            inst_filter = "|".join(institution_ids)
            filters.append(f"authorships.institutions.id:{inst_filter}")

        if concept_ids:
            # Filter by concepts
            concept_filter = "|".join(concept_ids)
            filters.append(f"concepts.id:{concept_filter}")

        if source_ids:
            # Filter by source (journal/conference)
            source_filter = "|".join(source_ids)
            filters.append(f"primary_location.source.id:{source_filter}")

        if from_date:
            filters.append(f"from_publication_date:{from_date}")

        if to_date:
            filters.append(f"to_publication_date:{to_date}")

        return ",".join(filters)

    async def get_works(
        self,
        institution_ids: Optional[list[str]] = None,
        concept_ids: Optional[list[str]] = None,
        source_ids: Optional[list[str]] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        cursor: Optional[str] = None,
        per_page: int = 200,
    ) -> dict:
        """
        Get works with filtering and pagination.

        Args:
            institution_ids: Filter by institution IDs
            concept_ids: Filter by concept IDs
            source_ids: Filter by source IDs
            from_date: Start date (YYYY-MM-DD)
            to_date: End date (YYYY-MM-DD)
            cursor: Pagination cursor
            per_page: Results per page (max 200)

        Returns:
            API response with results and meta info
        """
        filter_str = self._build_works_filter(
            institution_ids=institution_ids,
            concept_ids=concept_ids,
            source_ids=source_ids,
            from_date=from_date,
            to_date=to_date,
        )

        params = {
            "per-page": min(per_page, 200),
            "select": "id,doi,title,publication_date,type,cited_by_count,authorships,primary_location,open_access,concepts",
        }

        if filter_str:
            params["filter"] = filter_str

        if cursor:
            params["cursor"] = cursor
        else:
            params["cursor"] = "*"

        return await self._request("/works", params)

    async def iter_works(
        self,
        institution_ids: Optional[list[str]] = None,
        concept_ids: Optional[list[str]] = None,
        source_ids: Optional[list[str]] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        per_page: int = 200,
        max_results: Optional[int] = None,
    ) -> AsyncGenerator[dict, None]:
        """
        Iterate through all works matching filters.

        Args:
            institution_ids: Filter by institution IDs
            concept_ids: Filter by concept IDs
            source_ids: Filter by source IDs
            from_date: Start date (YYYY-MM-DD)
            to_date: End date (YYYY-MM-DD)
            per_page: Results per page
            max_results: Maximum total results to return

        Yields:
            Individual work records
        """
        cursor = "*"
        total_yielded = 0

        while cursor:
            response = await self.get_works(
                institution_ids=institution_ids,
                concept_ids=concept_ids,
                source_ids=source_ids,
                from_date=from_date,
                to_date=to_date,
                cursor=cursor,
                per_page=per_page,
            )

            results = response.get("results", [])
            meta = response.get("meta", {})

            for work in results:
                yield work
                total_yielded += 1

                if max_results and total_yielded >= max_results:
                    return

            # Get next cursor
            cursor = meta.get("next_cursor")

            if not results:
                break

    async def get_author(self, author_id: str) -> dict:
        """
        Get author details by ID.

        Args:
            author_id: OpenAlex author ID (e.g., "A1234567890")

        Returns:
            Author data
        """
        return await self._request(f"/authors/{author_id}")

    async def get_institution(self, institution_id: str) -> dict:
        """
        Get institution details by ID.

        Args:
            institution_id: OpenAlex institution ID (e.g., "I1234567890")

        Returns:
            Institution data
        """
        return await self._request(f"/institutions/{institution_id}")

    async def search_authors(
        self,
        query: str,
        per_page: int = 25
    ) -> dict:
        """
        Search authors by name.

        Args:
            query: Search query
            per_page: Results per page

        Returns:
            Search results
        """
        params = {
            "search": query,
            "per-page": per_page,
        }
        return await self._request("/authors", params)

    async def get_work(self, work_id: str) -> dict:
        """
        Get work details by ID.

        Args:
            work_id: OpenAlex work ID

        Returns:
            Work data
        """
        return await self._request(f"/works/{work_id}")


def parse_work(
    work: dict,
    preferred_institution_ids: Optional[list[str]] = None,
) -> Optional[tuple[dict, list[dict], list[dict]]]:
    """
    Parse OpenAlex work response into database-ready dicts.

    Args:
        work: Raw work data from OpenAlex
        preferred_institution_ids: Optional list of institution IDs to prioritize
            when selecting the author's institution from a work.

    Returns:
        Tuple of (work_dict, list of author_dicts, list of authorship_dicts),
        or None if the work is missing critical fields (id, title).
    """
    # Guard against malformed data missing critical fields
    if "id" not in work or not work.get("id"):
        return None

    # Parse work
    work_dict = {
        "id": work["id"].replace("https://openalex.org/", ""),
        "doi": work.get("doi"),
        "title": work.get("title") or "Untitled",
        "publication_date": None,
        "publication_year": None,
        "type": work.get("type"),
        "cited_by_count": work.get("cited_by_count", 0),
        "source_id": None,
        "source_name": None,
        "is_open_access": work.get("open_access", {}).get("is_oa", False),
        "concepts": None,
    }

    # Parse concepts: filter level 1-2, score >= 0.3, keep top 10
    raw_concepts = work.get("concepts", [])
    filtered_concepts = [
        {
            "id": c.get("id", "").replace("https://openalex.org/", ""),
            "display_name": c.get("display_name", ""),
            "level": c.get("level", 0),
            "score": c.get("score", 0),
        }
        for c in raw_concepts
        if c.get("level") in [1, 2] and c.get("score", 0) >= 0.3
    ]
    if filtered_concepts:
        # Sort by score descending and take top 10
        filtered_concepts.sort(key=lambda x: x["score"], reverse=True)
        work_dict["concepts"] = json.dumps(filtered_concepts[:10])

    # Parse publication date
    pub_date_str = work.get("publication_date")
    if pub_date_str:
        try:
            work_dict["publication_date"] = datetime.strptime(pub_date_str, "%Y-%m-%d")
            work_dict["publication_year"] = work_dict["publication_date"].year
        except ValueError:
            pass

    # Parse source
    primary_location = work.get("primary_location") or {}
    source = primary_location.get("source") or {}
    if source:
        source_id = source.get("id", "")
        work_dict["source_id"] = source_id.replace("https://openalex.org/", "") if source_id else None
        work_dict["source_name"] = source.get("display_name")

    # Parse authorships
    authors = []
    authorships = []
    raw_authorships = work.get("authorships", [])

    preferred_ids = set(preferred_institution_ids or [])

    def _normalize_inst_id(inst_id: str) -> Optional[str]:
        return inst_id.replace("https://openalex.org/", "") if inst_id else None

    def _select_institution(institutions: list[dict]) -> tuple[dict, Optional[str]]:
        if not institutions:
            return {}, None

        if preferred_ids:
            for inst in institutions:
                inst_id = _normalize_inst_id(inst.get("id", ""))
                if inst_id in preferred_ids:
                    return inst, inst_id

        inst = institutions[0]
        return inst, _normalize_inst_id(inst.get("id", ""))

    for idx, authorship in enumerate(raw_authorships):
        author = authorship.get("author") or {}
        author_id = author.get("id", "")

        if not author_id:
            continue

        author_id = author_id.replace("https://openalex.org/", "")

        # Get institution info
        institutions = authorship.get("institutions", [])
        if not institutions:
            # Fallback to author's last known institution if available
            author_inst = author.get("last_known_institution") or {}
            if author_inst:
                institutions = [author_inst]

        last_institution, inst_id = _select_institution(institutions)

        author_dict = {
            "id": author_id,
            "display_name": author.get("display_name", "Unknown"),
            "orcid": author.get("orcid"),
            "last_known_institution_id": _normalize_inst_id(inst_id),
            "last_known_institution_name": last_institution.get("display_name"),
        }
        authors.append(author_dict)

        # Build affiliation string
        affiliations = [inst.get("display_name", "") for inst in institutions if inst.get("display_name")]
        raw_affiliation = "; ".join(affiliations) if affiliations else None

        authorship_dict = {
            "author_id": author_id,
            "work_id": work_dict["id"],
            "author_position": idx,
            "is_corresponding": authorship.get("is_corresponding", False),
            "raw_author_name": authorship.get("raw_author_name"),
            "raw_affiliation": raw_affiliation,
        }
        authorships.append(authorship_dict)

    return work_dict, authors, authorships
