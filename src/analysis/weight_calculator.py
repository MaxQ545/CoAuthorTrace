"""
Backward-compatible re-export.

WeightCalculator has been moved to ``src.crawler.weight`` as it is
fundamentally a crawler-time concern.  This module re-exports it so
existing ``from src.analysis.weight_calculator import WeightCalculator``
continues to work.
"""
from src.crawler.weight import WeightCalculator  # noqa: F401
