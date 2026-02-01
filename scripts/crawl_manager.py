#!/usr/bin/env python3
"""
Crawl manager for batch institution crawling with progress tracking.

Usage:
    # Crawl all P0 priority institutions
    python scripts/crawl_manager.py --priority 0

    # Crawl all institutions
    python scripts/crawl_manager.py --all

    # Crawl specific institutions by ID
    python scripts/crawl_manager.py --institutions I99065089 I20231570

    # Resume failed institutions
    python scripts/crawl_manager.py --retry-failed

    # Dry run (show what would be crawled)
    python scripts/crawl_manager.py --priority 0 --dry-run

    # Full crawl (not incremental)
    python scripts/crawl_manager.py --all --full

    # Limit works per institution
    python scripts/crawl_manager.py --all --max-works 1000
"""
import sys
import json
import asyncio
import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.settings import settings
from src.database.models import init_database
from src.crawler.multi_institution_crawler import MultiInstitutionCrawler, get_all_institution_states

CONFIG_FILE = project_root / "config" / "crawl_targets.json"
logger = logging.getLogger(__name__)


def load_config() -> dict:
    """Load crawl targets configuration."""
    if not CONFIG_FILE.exists():
        raise FileNotFoundError(f"Config file not found: {CONFIG_FILE}")

    with open(CONFIG_FILE) as f:
        return json.load(f)


def save_config(config: dict) -> None:
    """Save crawl targets configuration."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def update_institution_status(
    config: dict,
    institution_id: str,
    status: str,
    works_count: Optional[int] = None,
    error: Optional[str] = None,
) -> None:
    """Update status for a specific institution in config."""
    for inst in config["institutions"]:
        if inst.get("id") == institution_id:
            inst["status"] = status
            inst["last_crawl"] = datetime.now().isoformat()
            if works_count is not None:
                inst["works_count"] = works_count
            if error:
                inst["last_error"] = error
            elif "last_error" in inst:
                del inst["last_error"]
            break
    save_config(config)


def get_pending_institutions(
    config: dict,
    priority: Optional[int] = None,
    include_failed: bool = False,
) -> list[dict]:
    """Get list of institutions to crawl."""
    institutions = config.get("institutions", [])

    pending = []
    for inst in institutions:
        # Skip if no ID
        if not inst.get("id"):
            continue

        status = inst.get("status", "pending")

        # Include based on status
        if status == "pending":
            pending.append(inst)
        elif status == "failed" and include_failed:
            pending.append(inst)
        elif status == "completed":
            continue
        elif status == "running":
            # Treat running as pending (may have been interrupted)
            pending.append(inst)

    # Filter by priority if specified
    if priority is not None:
        pending = [i for i in pending if i.get("priority") == priority]

    # Sort by priority
    pending.sort(key=lambda x: (x.get("priority", 99), x.get("name", "")))

    return pending


def get_concept_ids(config: dict, preset: str = "cs_ai") -> list[str]:
    """Get concept IDs from preset."""
    presets = config.get("concept_presets", {})
    return presets.get(preset, [])


async def crawl_institutions(
    institutions: list[dict],
    config: dict,
    concept_ids: list[str],
    incremental: bool = True,
    max_works: Optional[int] = None,
    max_concurrent: int = 3,
) -> dict[str, dict]:
    """
    Crawl a list of institutions with progress tracking.

    Returns:
        Dict mapping institution_id to crawl results
    """
    if not institutions:
        print("No institutions to crawl.")
        return {}

    institution_ids = [inst["id"] for inst in institutions]

    # Mark all as running
    for inst in institutions:
        update_institution_status(config, inst["id"], "running")

    print(f"\nStarting crawl for {len(institutions)} institution(s):")
    for inst in institutions:
        print(f"  P{inst.get('priority', '?')} {inst['name']} ({inst['id']})")
    print()

    # Create crawler
    crawler = MultiInstitutionCrawler(
        institution_ids=institution_ids,
        concept_ids=concept_ids if concept_ids else None,
        max_concurrent=max_concurrent,
    )

    try:
        results = await crawler.crawl_all(
            incremental=incremental,
            max_works_per_inst=max_works,
        )

        # Update config with results
        for inst_id, stats in results.items():
            status = stats.get("status", "failed")
            works_count = stats.get("works_new", 0)
            error = stats.get("error") if status == "failed" else None

            update_institution_status(
                config, inst_id, status,
                works_count=works_count,
                error=error,
            )

        return results

    except Exception as e:
        logger.error(f"Crawl failed: {e}")
        # Mark all as failed
        for inst in institutions:
            update_institution_status(config, inst["id"], "failed", error=str(e))
        raise


def print_results(results: dict[str, dict], config: dict) -> None:
    """Print crawl results summary."""
    print("\n" + "=" * 70)
    print("CRAWL RESULTS")
    print("=" * 70)

    # Build name lookup
    name_lookup = {inst["id"]: inst["name"] for inst in config["institutions"] if inst.get("id")}

    total_new = 0
    total_processed = 0
    completed = 0
    failed = []

    for inst_id, stats in results.items():
        inst_name = name_lookup.get(inst_id, "Unknown")
        status = stats.get("status", "unknown")

        if status == "completed":
            completed += 1
            works_new = stats.get("works_new", 0)
            works_processed = stats.get("works_processed", 0)
            total_new += works_new
            total_processed += works_processed

            print(f"\n[OK] {inst_name} ({inst_id})")
            print(f"     Works: {works_processed:,} processed, {works_new:,} new")
            print(f"     Authors: {stats.get('authors_new', 0):,} new")
        else:
            failed.append((inst_id, inst_name, stats.get("error", "Unknown")))
            print(f"\n[!!] {inst_name} ({inst_id})")
            print(f"     Error: {stats.get('error', 'Unknown')[:60]}...")

    print("\n" + "-" * 70)
    print("SUMMARY")
    print("-" * 70)
    print(f"Institutions: {completed} completed, {len(failed)} failed")
    print(f"Works: {total_processed:,} processed, {total_new:,} new")

    if failed:
        print(f"\nFailed institutions (use --retry-failed to retry):")
        for inst_id, name, _ in failed:
            print(f"  - {name} ({inst_id})")

    print()


def print_status(config: dict) -> None:
    """Print current crawl status from config."""
    institutions = config.get("institutions", [])

    print("\n" + "=" * 70)
    print("CRAWL TARGETS STATUS")
    print("=" * 70)

    # Group by status
    by_status = {"pending": [], "running": [], "completed": [], "failed": []}
    no_id = []

    for inst in institutions:
        if not inst.get("id"):
            no_id.append(inst)
            continue
        status = inst.get("status", "pending")
        if status not in by_status:
            by_status[status] = []
        by_status[status].append(inst)

    # Print by priority within each status
    for status, items in by_status.items():
        if not items:
            continue

        status_icon = {
            "completed": "[OK]",
            "running": "[..]",
            "failed": "[!!]",
            "pending": "[--]",
        }.get(status, "[??]")

        print(f"\n{status.upper()} ({len(items)}):")
        items.sort(key=lambda x: (x.get("priority", 99), x.get("name", "")))
        for inst in items:
            priority = inst.get("priority", "?")
            name = inst.get("name", "Unknown")
            works = inst.get("works_count", 0)
            print(f"  {status_icon} P{priority} {name} - {works:,} works")

    if no_id:
        print(f"\nMISSING ID ({len(no_id)}):")
        for inst in no_id:
            print(f"  [??] P{inst.get('priority', '?')} {inst.get('name', 'Unknown')}")

    # Summary
    total = len(institutions)
    valid = total - len(no_id)
    completed = len(by_status.get("completed", []))
    total_works = sum(i.get("works_count", 0) for i in institutions)

    print("\n" + "-" * 70)
    print(f"Total: {valid}/{total} institutions with valid IDs")
    print(f"Completed: {completed}/{valid}")
    print(f"Total works crawled: {total_works:,}")
    print()


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Batch crawl manager for target institutions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Target selection
    target_group = parser.add_mutually_exclusive_group()
    target_group.add_argument(
        "--priority", "-p",
        type=int,
        choices=[0, 1, 2],
        help="Crawl institutions of specific priority (0, 1, or 2)",
    )
    target_group.add_argument(
        "--all", "-a",
        action="store_true",
        help="Crawl all pending institutions",
    )
    target_group.add_argument(
        "--institutions", "-i",
        nargs="+",
        help="Crawl specific institution IDs",
    )
    target_group.add_argument(
        "--retry-failed",
        action="store_true",
        help="Retry all failed institutions",
    )
    target_group.add_argument(
        "--status",
        action="store_true",
        help="Show current crawl status and exit",
    )

    # Crawl options
    parser.add_argument(
        "--full",
        action="store_true",
        help="Full crawl instead of incremental",
    )
    parser.add_argument(
        "--max-works",
        type=int,
        help="Maximum works per institution",
    )
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=3,
        help="Maximum concurrent crawls (default: 3)",
    )
    parser.add_argument(
        "--concept-preset",
        default="cs_ai",
        help="Concept preset to use (default: cs_ai)",
    )
    parser.add_argument(
        "--no-concepts",
        action="store_true",
        help="Don't filter by concepts",
    )

    # Other options
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be crawled without actually crawling",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Load config
    try:
        config = load_config()
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("Run 'python scripts/query_institution.py --verify-config' to check configuration.")
        sys.exit(1)

    # Handle --status
    if args.status:
        print_status(config)
        return

    # Determine institutions to crawl
    institutions = []

    if args.institutions:
        # Specific institutions
        id_set = set(args.institutions)
        for inst in config["institutions"]:
            if inst.get("id") in id_set:
                institutions.append(inst)

        # Warn about missing
        found_ids = {inst["id"] for inst in institutions}
        missing = id_set - found_ids
        if missing:
            print(f"Warning: Institution IDs not found in config: {missing}")

    elif args.retry_failed:
        institutions = get_pending_institutions(config, include_failed=True)
        institutions = [i for i in institutions if i.get("status") == "failed"]

    elif args.priority is not None:
        institutions = get_pending_institutions(config, priority=args.priority)

    elif args.all:
        institutions = get_pending_institutions(config)

    else:
        # No target specified, show help
        print("No target specified. Use --status to see current progress,")
        print("or specify targets with --priority, --all, --institutions, or --retry-failed.")
        print("\nRun with --help for more options.")
        return

    if not institutions:
        print("No institutions to crawl.")
        print_status(config)
        return

    # Get concept IDs
    concept_ids = []
    if not args.no_concepts:
        concept_ids = get_concept_ids(config, args.concept_preset)

    # Dry run
    if args.dry_run:
        print("\n" + "=" * 70)
        print("DRY RUN - Would crawl the following institutions:")
        print("=" * 70)
        for inst in institutions:
            print(f"  P{inst.get('priority', '?')} {inst['name']} ({inst['id']})")
        print(f"\nTotal: {len(institutions)} institutions")
        print(f"Mode: {'Full' if args.full else 'Incremental'}")
        print(f"Concepts: {concept_ids if concept_ids else 'None (all)'}")
        if args.max_works:
            print(f"Max works per institution: {args.max_works}")
        print(f"Max concurrent: {args.max_concurrent}")
        return

    # Initialize database
    init_database()

    # Run crawl
    print("\n" + "=" * 70)
    print("STARTING BATCH CRAWL")
    print("=" * 70)
    print(f"Institutions: {len(institutions)}")
    print(f"Mode: {'Full' if args.full else 'Incremental'}")
    print(f"Concepts: {concept_ids if concept_ids else 'None (all)'}")
    if args.max_works:
        print(f"Max works per institution: {args.max_works}")
    print(f"Max concurrent: {args.max_concurrent}")

    try:
        results = asyncio.run(crawl_institutions(
            institutions=institutions,
            config=config,
            concept_ids=concept_ids,
            incremental=not args.full,
            max_works=args.max_works,
            max_concurrent=args.max_concurrent,
        ))

        print_results(results, config)

    except KeyboardInterrupt:
        print("\n\nCrawl interrupted by user.")
        print("Progress has been saved. Run again to continue.")

    except Exception as e:
        logger.exception("Crawl failed")
        print(f"\nCrawl failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
