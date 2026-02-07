"""
Standalone OpenAlex API client with rate limiting and cursor pagination.

No dependency on project-wide configuration — all parameters are passed
explicitly via constructor arguments.
"""
import asyncio
import logging
from typing import Optional, AsyncGenerator
from urllib.parse import urlencode

import httpx

logger = logging.getLogger(__name__)


class RateLimiter:
    """Token bucket rate limiter for API requests."""

    def __init__(self, rate: float = 8.0):
        self.rate = rate
        self.tokens = rate
        self.last_update = asyncio.get_event_loop().time() if asyncio.get_event_loop().is_running() else 0
        self._lock = asyncio.Lock()

    async def acquire(self):
        async with self._lock:
            now = asyncio.get_event_loop().time()
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
    Async client for the OpenAlex API.

    All configuration is passed via constructor — the class does **not** read
    any global settings object.
    """

    BASE_URL = "https://api.openalex.org"

    def __init__(
        self,
        email: Optional[str] = None,
        api_key: Optional[str] = None,
        rate_limit: float = 10.0,
        max_retries: int = 3,
    ):
        self.email = email
        self.api_key = api_key
        self.rate_limiter = RateLimiter(rate_limit)
        self.max_retries = max_retries
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
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
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _request(self, endpoint: str, params: Optional[dict] = None) -> dict:
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
                    wait_time = 2 ** attempt
                    logger.warning(f"Rate limited, waiting {wait_time}s...")
                    await asyncio.sleep(wait_time)
                elif e.response.status_code >= 500:
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

    # ---- works ----

    @staticmethod
    def _build_works_filter(
        institution_ids: Optional[list[str]] = None,
        concept_ids: Optional[list[str]] = None,
        source_ids: Optional[list[str]] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> str:
        filters = []
        if institution_ids:
            filters.append(f"authorships.institutions.id:{'|'.join(institution_ids)}")
        if concept_ids:
            filters.append(f"concepts.id:{'|'.join(concept_ids)}")
        if source_ids:
            filters.append(f"primary_location.source.id:{'|'.join(source_ids)}")
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
        params["cursor"] = cursor or "*"
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

            cursor = meta.get("next_cursor")
            if not results:
                break

    # ---- single-entity lookups ----

    async def get_author(self, author_id: str) -> dict:
        return await self._request(f"/authors/{author_id}")

    async def get_institution(self, institution_id: str) -> dict:
        return await self._request(f"/institutions/{institution_id}")

    async def search_authors(self, query: str, per_page: int = 25) -> dict:
        return await self._request("/authors", {"search": query, "per-page": per_page})

    async def get_work(self, work_id: str) -> dict:
        return await self._request(f"/works/{work_id}")
