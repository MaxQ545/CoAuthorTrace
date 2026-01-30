#!/usr/bin/env python3
"""
Run the incremental crawler.
"""
import sys
import asyncio
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.database.models import init_database
from src.crawler.incremental_crawler import run_crawl


def main():
    """Run crawler."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Parse arguments
    incremental = "--full" not in sys.argv
    max_works = None

    for arg in sys.argv[1:]:
        if arg.startswith("--max="):
            max_works = int(arg.split("=")[1])

    # Initialize database
    init_database()

    # Run crawler
    print(f"Starting crawl (incremental={incremental}, max_works={max_works})...")
    stats = asyncio.run(run_crawl(incremental=incremental, max_works=max_works))

    print("\nCrawl Results:")
    for key, value in stats.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
