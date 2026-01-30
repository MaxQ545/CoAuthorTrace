#!/usr/bin/env python3
"""
Start the scheduler for automated tasks.
"""
import sys
import time
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.database.models import init_database
from src.scheduler.jobs import start_scheduler, stop_scheduler, get_scheduler_status


def main():
    """Start scheduler."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Initialize database
    init_database()

    # Start scheduler
    print("Starting scheduler...")
    start_scheduler()

    status = get_scheduler_status()
    print(f"\nScheduler Status: {status['status']}")
    print("Scheduled Jobs:")
    for job in status['jobs']:
        print(f"  - {job['name']} (next run: {job['next_run']})")

    print("\nPress Ctrl+C to stop...")

    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("\nStopping scheduler...")
        stop_scheduler()
        print("Done!")


if __name__ == "__main__":
    main()
