#!/usr/bin/env python3
"""
Run multi-institution concurrent crawler.

Usage:
    # Incremental crawl all institutions
    python scripts/run_multi_crawl.py

    # Full crawl specified institutions
    python scripts/run_multi_crawl.py --institutions I136199984 I16365422 --full

    # Filter by concepts (CS/AI)
    python scripts/run_multi_crawl.py --concepts C41008148 C154945302

    # Use preset --cs-ai for Computer Science and AI fields
    python scripts/run_multi_crawl.py --cs-ai

    # Limit works per institution
    python scripts/run_multi_crawl.py --max-works 5000

    # Adjust concurrency
    python scripts/run_multi_crawl.py --max-concurrent 4

    # List all configured institutions
    python scripts/run_multi_crawl.py --list
"""
import sys
import asyncio
import argparse
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.settings import TARGET_INSTITUTIONS
from src.database.models import init_database
from src.crawler.multi_institution_crawler import run_multi_crawl


def list_institutions():
    """Print all configured institutions."""
    print("\nConfigured Institutions:")
    print("-" * 60)
    for inst_id, name in TARGET_INSTITUTIONS.items():
        print(f"  {inst_id}: {name}")
    print("-" * 60)
    print(f"Total: {len(TARGET_INSTITUTIONS)} institutions\n")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run multi-institution concurrent crawler",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--institutions",
        nargs="+",
        help="Institution IDs to crawl (defaults to all)",
    )
    parser.add_argument(
        "--concepts",
        nargs="+",
        help="Concept IDs to filter (e.g., C41008148 for CS)",
    )
    parser.add_argument(
        "--cs-ai",
        action="store_true",
        help="Preset: filter by CS, AI, ML concepts",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Run full crawl instead of incremental",
    )
    parser.add_argument(
        "--max-works",
        type=int,
        help="Maximum works to fetch per institution",
    )
    parser.add_argument(
        "--max-concurrent",
        type=int,
        help="Maximum concurrent institution crawls",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all configured institutions and exit",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    return parser.parse_args()


def main():
    """Run multi-institution crawler."""
    args = parse_args()

    # Handle --list
    if args.list:
        list_institutions()
        return

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Validate institutions if specified
    institution_ids = args.institutions
    if institution_ids:
        for inst_id in institution_ids:
            if inst_id not in TARGET_INSTITUTIONS:
                print(f"Warning: Institution {inst_id} not in TARGET_INSTITUTIONS")

    # Handle concept filtering
    concept_ids = args.concepts
    if args.cs_ai:
        # Preset: Computer Science, AI, Machine Learning
        concept_ids = ["C41008148", "C154945302", "C119857082"]

    # Initialize database
    init_database()

    # Run crawler
    incremental = not args.full
    print(f"\nStarting multi-institution crawl:")
    print(f"  Mode: {'Incremental' if incremental else 'Full'}")
    print(f"  Institutions: {len(institution_ids) if institution_ids else len(TARGET_INSTITUTIONS)}")
    if concept_ids:
        print(f"  Concepts filter: {concept_ids}")
    if args.max_works:
        print(f"  Max works per institution: {args.max_works}")
    if args.max_concurrent:
        print(f"  Max concurrent: {args.max_concurrent}")
    print()

    results = asyncio.run(run_multi_crawl(
        institution_ids=institution_ids,
        concept_ids=concept_ids,
        incremental=incremental,
        max_works_per_inst=args.max_works,
        max_concurrent=args.max_concurrent,
    ))

    # Print results
    print("\n" + "=" * 60)
    print("CRAWL RESULTS")
    print("=" * 60)

    total_new = 0
    total_processed = 0
    failed = []

    for inst_id, stats in results.items():
        inst_name = TARGET_INSTITUTIONS.get(inst_id, "Unknown")
        status = stats.get("status", "unknown")

        if status == "completed":
            works_new = stats.get("works_new", 0)
            works_processed = stats.get("works_processed", 0)
            total_new += works_new
            total_processed += works_processed
            print(f"\n{inst_name} ({inst_id})")
            print(f"  Status: {status}")
            print(f"  Works processed: {works_processed:,}")
            print(f"  New works: {works_new:,}")
            print(f"  New authors: {stats.get('authors_new', 0):,}")
            print(f"  New authorships: {stats.get('authorships_new', 0):,}")
        else:
            failed.append((inst_id, inst_name, stats.get("error", "Unknown error")))
            print(f"\n{inst_name} ({inst_id})")
            print(f"  Status: FAILED")
            print(f"  Error: {stats.get('error', 'Unknown')}")

    print("\n" + "-" * 60)
    print("SUMMARY")
    print("-" * 60)
    print(f"Total works processed: {total_processed:,}")
    print(f"Total new works: {total_new:,}")
    print(f"Successful institutions: {len(results) - len(failed)}/{len(results)}")
    if failed:
        print(f"\nFailed institutions:")
        for inst_id, name, error in failed:
            print(f"  - {name} ({inst_id}): {error[:50]}...")
    print()


if __name__ == "__main__":
    main()
