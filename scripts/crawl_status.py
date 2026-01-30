#!/usr/bin/env python3
"""
View crawl status for all institutions.

Usage:
    python scripts/crawl_status.py
"""
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.settings import TARGET_INSTITUTIONS
from src.database.models import init_database
from src.crawler.multi_institution_crawler import get_all_institution_states


def format_number(n: int) -> str:
    """Format number with thousands separator."""
    return f"{n:,}" if n else "0"


def format_datetime(dt_str: str) -> str:
    """Format datetime string for display."""
    if not dt_str:
        return "Never"
    try:
        dt = datetime.fromisoformat(dt_str)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return dt_str


def main():
    """Display crawl status for all institutions."""
    # Initialize database
    init_database()

    # Get all states
    states = get_all_institution_states()

    # Create a set of tracked institution IDs
    tracked_ids = {s["institution_id"] for s in states}

    print("\n" + "=" * 70)
    print("INSTITUTION CRAWL STATUS")
    print("=" * 70)

    if not states:
        print("\nNo crawl history found.")
        print("\nConfigured institutions (not yet crawled):")
        for inst_id, name in TARGET_INSTITUTIONS.items():
            print(f"  - {name} ({inst_id})")
    else:
        # Sort by institution name
        states.sort(key=lambda x: x.get("institution_name", ""))

        for state in states:
            inst_id = state["institution_id"]
            inst_name = state.get("institution_name") or TARGET_INSTITUTIONS.get(inst_id, "Unknown")
            status = state.get("status", "unknown")

            # Status emoji
            status_icon = {
                "completed": "[OK]",
                "running": "[..]",
                "failed": "[!!]",
                "idle": "[--]",
            }.get(status, "[??]")

            print(f"\n{status_icon} {inst_name} ({inst_id})")
            print(f"    Status: {status}")
            print(f"    Total works crawled: {format_number(state.get('total_works_crawled', 0))}")
            print(f"    Last publication date: {state.get('last_publication_date') or 'N/A'}")
            print(f"    Last crawl completed: {format_datetime(state.get('last_crawl_completed'))}")

            if state.get("has_pending_cursor"):
                print(f"    Resume cursor: Available (can resume interrupted crawl)")

            if status == "failed" and state.get("error_message"):
                error = state["error_message"]
                if len(error) > 60:
                    error = error[:60] + "..."
                print(f"    Error: {error}")

        # Show uncrawled institutions
        uncrawled = [
            (inst_id, name)
            for inst_id, name in TARGET_INSTITUTIONS.items()
            if inst_id not in tracked_ids
        ]

        if uncrawled:
            print("\n" + "-" * 70)
            print("NOT YET CRAWLED:")
            print("-" * 70)
            for inst_id, name in uncrawled:
                print(f"  - {name} ({inst_id})")

    # Summary
    print("\n" + "-" * 70)
    print("SUMMARY")
    print("-" * 70)

    total_works = sum(s.get("total_works_crawled", 0) for s in states)
    completed = sum(1 for s in states if s.get("status") == "completed")
    failed = sum(1 for s in states if s.get("status") == "failed")
    running = sum(1 for s in states if s.get("status") == "running")

    print(f"Total institutions configured: {len(TARGET_INSTITUTIONS)}")
    print(f"Institutions with data: {len(states)}")
    print(f"  - Completed: {completed}")
    print(f"  - Running: {running}")
    print(f"  - Failed: {failed}")
    print(f"Total works crawled: {format_number(total_works)}")
    print()


if __name__ == "__main__":
    main()
