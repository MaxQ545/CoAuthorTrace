#!/usr/bin/env python3
"""Query OpenAlex institution ID by name."""
import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.crawler.openalex_client import OpenAlexClient
from config.settings import settings


async def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/query_institution.py <name>")
        sys.exit(1)

    query = " ".join(sys.argv[1:])
    client = OpenAlexClient(email=settings.crawler.openalex_email, rate_limit=5.0)

    try:
        response = await client._request("/institutions", {"search": query, "per-page": 5})
        results = response.get("results", [])

        if not results:
            print(f"No results for: {query}")
            return

        print(f"\nResults for '{query}':\n")
        for r in results:
            rid = r.get("id", "").replace("https://openalex.org/", "")
            name = r.get("display_name", "")
            country = r.get("country_code", "")
            works = r.get("works_count", 0)
            print(f"  {rid}: {name} [{country}] - {works:,} works")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
