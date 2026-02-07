"""
Collaboration weight calculator.

Standalone module — no project dependencies. Computes edge weights for
co-authorship links based on author position and publication recency.

    Weight = BaseWeight × PositionFactor × TimeFactor
"""
import math
from datetime import datetime
from typing import Optional


class WeightCalculator:
    """
    Calculator for collaboration edge weights.

    Considers:
    1. Author positions (first, corresponding, last, middle)
    2. Time decay (exponential with configurable half-life)
    """

    def __init__(self, half_life_days: int = 730):
        """
        Args:
            half_life_days: Half-life for time decay in days (default 730 ≈ 2 years).
        """
        self.half_life_days = half_life_days

    # ---- position ----

    def calculate_position_factor(
        self,
        position_1: int,
        position_2: int,
        is_corresponding_1: bool,
        is_corresponding_2: bool,
        total_authors: int,
    ) -> float:
        if total_authors < 1:
            total_authors = 1

        def _author_factor(position: int, is_corresponding: bool) -> float:
            is_first = position == 0
            is_last = position == total_authors - 1

            if is_first and is_corresponding:
                return 1.0
            elif is_first:
                return 0.8
            elif is_corresponding:
                return 0.7
            elif is_last:
                return 0.6
            else:
                distance = min(position, total_authors - 1 - position)
                return max(0.3, 0.5 / (1 + distance * 0.1))

        f1 = _author_factor(position_1, is_corresponding_1)
        f2 = _author_factor(position_2, is_corresponding_2)
        combined = math.sqrt(f1 * f2)
        normalization = 1.0 / math.log2(max(2, total_authors))
        return combined * normalization

    # ---- time decay ----

    def calculate_time_factor(
        self,
        publication_date: Optional[datetime],
        reference_date: Optional[datetime] = None,
    ) -> float:
        if publication_date is None:
            return 0.5
        if reference_date is None:
            reference_date = datetime.utcnow()
        days_since = (reference_date - publication_date).days
        if days_since < 0:
            return 1.0
        return math.pow(0.5, days_since / self.half_life_days)

    # ---- combined ----

    def calculate_weight(
        self,
        position_1: int,
        position_2: int,
        is_corresponding_1: bool,
        is_corresponding_2: bool,
        total_authors: int,
        publication_date: Optional[datetime] = None,
        base_weight: float = 1.0,
    ) -> float:
        """Calculate total collaboration weight."""
        pf = self.calculate_position_factor(
            position_1, position_2,
            is_corresponding_1, is_corresponding_2,
            total_authors,
        )
        tf = self.calculate_time_factor(publication_date)
        return base_weight * pf * tf
