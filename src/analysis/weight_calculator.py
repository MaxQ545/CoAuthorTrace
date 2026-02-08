"""
Weight calculator for collaboration edges.

Implements the collaboration weight formula:
Weight = BaseWeight * PositionFactor * TimeFactor
"""
import math
from datetime import datetime
from typing import Optional

from sqlalchemy import func

from config.settings import settings


class WeightCalculator:
    """
    Calculator for collaboration edge weights.

    The weight formula considers:
    1. Author positions (first author, corresponding author, middle authors)
    2. Time decay (exponential decay with configurable half-life)
    """

    def __init__(self, half_life_days: Optional[int] = None):
        """
        Initialize weight calculator.

        Args:
            half_life_days: Half-life for time decay in days (default: 730 = 2 years)
        """
        self.half_life_days = half_life_days or settings.analysis.time_decay_half_life_days

    def calculate_position_factor(
        self,
        position_1: int,
        position_2: int,
        is_corresponding_1: bool,
        is_corresponding_2: bool,
        total_authors: int,
    ) -> float:
        """
        Calculate position-based weight factor for a collaboration.

        Position factors:
        - First author (position 0) + Corresponding: 1.0
        - First author only: 0.8
        - Corresponding only (not first): 0.7
        - Middle authors: 0.5 / |position_diff|

        The final factor is the product of both authors' individual factors,
        normalized by the number of potential collaborations.

        Args:
            position_1: Position of first author (0-indexed)
            position_2: Position of second author (0-indexed)
            is_corresponding_1: Whether first author is corresponding
            is_corresponding_2: Whether second author is corresponding
            total_authors: Total number of authors on the paper

        Returns:
            Position factor between 0 and 1
        """
        # Guard against invalid total_authors
        if total_authors < 1:
            total_authors = 1

        def author_factor(position: int, is_corresponding: bool) -> float:
            is_first = position == 0
            is_last = position == total_authors - 1

            if is_first and is_corresponding:
                return 1.0
            elif is_first:
                return 0.8
            elif is_corresponding:
                return 0.7
            elif is_last:
                # Last author often has significance
                return 0.6
            else:
                # Middle authors - weight decreases with distance from ends
                distance_from_end = min(position, total_authors - 1 - position)
                return max(0.3, 0.5 / (1 + distance_from_end * 0.1))

        factor_1 = author_factor(position_1, is_corresponding_1)
        factor_2 = author_factor(position_2, is_corresponding_2)

        # Combine factors (geometric mean to balance both contributions)
        combined = math.sqrt(factor_1 * factor_2)

        # Normalize by author count (more authors = lower individual contribution)
        normalization = 1.0 / math.log2(max(2, total_authors))

        return combined * normalization

    def calculate_time_factor(
        self,
        publication_date: Optional[datetime],
        reference_date: Optional[datetime] = None,
    ) -> float:
        """
        Calculate time-based decay factor.

        Uses exponential decay: factor = 0.5^(days / half_life)

        Args:
            publication_date: Publication date of the work
            reference_date: Reference date for decay calculation (default: now)

        Returns:
            Time factor between 0 and 1
        """
        if publication_date is None:
            return 0.5  # Default for unknown dates

        if reference_date is None:
            reference_date = datetime.utcnow()

        days_since = (reference_date - publication_date).days

        if days_since < 0:
            # Future publication (shouldn't happen, but handle gracefully)
            return 1.0

        # Exponential decay with half-life
        return math.pow(0.5, days_since / self.half_life_days)

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
        """
        Calculate total collaboration weight.

        Weight = BaseWeight * PositionFactor * TimeFactor

        Args:
            position_1: Position of first author (0-indexed)
            position_2: Position of second author (0-indexed)
            is_corresponding_1: Whether first author is corresponding
            is_corresponding_2: Whether second author is corresponding
            total_authors: Total number of authors on the paper
            publication_date: Publication date of the work
            base_weight: Base weight (default: 1.0)

        Returns:
            Combined weight
        """
        position_factor = self.calculate_position_factor(
            position_1,
            position_2,
            is_corresponding_1,
            is_corresponding_2,
            total_authors,
        )

        time_factor = self.calculate_time_factor(publication_date)

        return base_weight * position_factor * time_factor

    def recalculate_all_weights(
        self,
        session,
        reference_date: Optional[datetime] = None,
    ) -> int:
        """
        Recalculate time-decayed weights for all collaborations.

        This is useful for periodic updates to refresh time decay.

        Args:
            session: Database session
            reference_date: Reference date for decay calculation

        Returns:
            Number of collaborations updated
        """
        from src.database.models import Collaboration, Authorship, Work

        collaborations = session.query(Collaboration).all()
        updated = 0

        for collab in collaborations:
            # Get all shared works between these authors
            shared_works = (
                session.query(Work)
                .join(Authorship, Work.id == Authorship.work_id)
                .filter(Authorship.author_id.in_([collab.author_id_1, collab.author_id_2]))
                .group_by(Work.id)
                .having(func.count() == 2)
                .all()
            )

            total_weight = 0.0
            for work in shared_works:
                # Get authorships for both authors
                auth1 = (
                    session.query(Authorship)
                    .filter(
                        Authorship.work_id == work.id,
                        Authorship.author_id == collab.author_id_1
                    )
                    .first()
                )
                auth2 = (
                    session.query(Authorship)
                    .filter(
                        Authorship.work_id == work.id,
                        Authorship.author_id == collab.author_id_2
                    )
                    .first()
                )

                if auth1 and auth2:
                    # Get total authors for this work
                    total_authors = (
                        session.query(Authorship)
                        .filter(Authorship.work_id == work.id)
                        .count()
                    )

                    weight = self.calculate_weight(
                        position_1=auth1.author_position,
                        position_2=auth2.author_position,
                        is_corresponding_1=auth1.is_corresponding,
                        is_corresponding_2=auth2.is_corresponding,
                        total_authors=total_authors,
                        publication_date=work.publication_date,
                    )
                    total_weight += weight

            collab.total_weight = total_weight
            updated += 1

        session.commit()
        return updated
