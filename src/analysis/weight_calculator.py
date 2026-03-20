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

        Uses a bulk approach: one query loads all relevant authorship+work data,
        then weights are computed in Python and batch-committed.

        Args:
            session: Database session
            reference_date: Reference date for decay calculation

        Returns:
            Number of collaborations updated
        """
        from sqlalchemy import case
        from src.database.models import Collaboration, Authorship, Work

        collaborations = session.query(Collaboration).all()
        if not collaborations:
            return 0

        # Collect all author IDs involved in collaborations
        all_author_ids = set()
        for collab in collaborations:
            all_author_ids.add(collab.author_id_1)
            all_author_ids.add(collab.author_id_2)

        # Single bulk query: get all authorships for these authors with work info
        # and per-work author counts via a window function
        author_count_subq = (
            session.query(
                Authorship.work_id,
                func.count().label("total_authors"),
            )
            .group_by(Authorship.work_id)
            .subquery()
        )

        rows = (
            session.query(
                Authorship.author_id,
                Authorship.work_id,
                Authorship.author_position,
                Authorship.is_corresponding,
                Work.publication_date,
                author_count_subq.c.total_authors,
            )
            .join(Work, Work.id == Authorship.work_id)
            .join(author_count_subq, author_count_subq.c.work_id == Authorship.work_id)
            .filter(Authorship.author_id.in_(all_author_ids))
            .all()
        )

        # Build lookup: (author_id, work_id) -> (position, is_corresponding, pub_date, total_authors)
        auth_lookup: dict[tuple[str, str], tuple] = {}
        # Also build author_id -> set of work_ids for fast intersection
        author_works: dict[str, set[str]] = {}
        for author_id, work_id, position, is_corresponding, pub_date, total_authors in rows:
            auth_lookup[(author_id, work_id)] = (position, is_corresponding, pub_date, total_authors)
            author_works.setdefault(author_id, set()).add(work_id)

        # Compute weights in Python
        updated = 0
        for idx, collab in enumerate(collaborations):
            works_1 = author_works.get(collab.author_id_1, set())
            works_2 = author_works.get(collab.author_id_2, set())
            shared_work_ids = works_1 & works_2

            total_weight = 0.0
            for work_id in shared_work_ids:
                info1 = auth_lookup.get((collab.author_id_1, work_id))
                info2 = auth_lookup.get((collab.author_id_2, work_id))
                if info1 and info2:
                    weight = self.calculate_weight(
                        position_1=info1[0],
                        position_2=info2[0],
                        is_corresponding_1=info1[1],
                        is_corresponding_2=info2[1],
                        total_authors=info1[3],
                        publication_date=info1[2],
                    )
                    total_weight += weight

            collab.total_weight = total_weight
            updated += 1

            # Batch commit every 500
            if updated % 500 == 0:
                session.flush()

        session.commit()
        return updated
