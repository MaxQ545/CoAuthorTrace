#!/usr/bin/env python3
"""
Run GNN analysis and compute relationship scores.
"""
import sys
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.database.models import init_database
from src.analysis.relationship_scorer import run_analysis


def main():
    """Run analysis."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Parse arguments
    model_path = str(project_root / "data/models/graphsage.pt")

    for arg in sys.argv[1:]:
        if arg.startswith("--model="):
            model_path = arg.split("=")[1]

    # Initialize database
    init_database()

    # Run analysis
    print(f"Starting analysis (model_path={model_path})...")
    stats = run_analysis(model_path=model_path)

    print("\nAnalysis Results:")
    for key, value in stats.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
