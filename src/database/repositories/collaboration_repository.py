"""
Collaboration data access layer.
"""
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import func, or_, and_
from sqlalchemy.orm import Session

from src.database.models import (
    Author, Work, Authorship, Collaboration, RelationshipScore,
)

logger = logging.getLogger(__name__)


class CollaborationRepository:
    """Repository for collaboration data access."""

    def __init__(self, session: Session):
        self.session = session

    def get_collaboration(
        self, author_id_1: str, author_id_2: str,
    ) -> Optional[Collaboration]:
        """Get collaboration between two authors (order-independent)."""
        a, b = sorted([author_id_1, author_id_2])
        return (
            self.session.query(Collaboration)
            .filter(
                Collaboration.author_id_1 == a,
                Collaboration.author_id_2 == b,
            )
            .first()
        )

    def get_collaboration_counts_batch(
        self, author_id: str, other_ids: list[str],
    ) -> dict[str, int]:
        """
        Batch-fetch collaboration counts between author_id and each of other_ids.

        Returns dict mapping other_id -> collaboration_count.
        Avoids N+1 by using a single IN query.
        """
        if not other_ids:
            return {}

        rows = (
            self.session.query(
                Collaboration.author_id_1,
                Collaboration.author_id_2,
                Collaboration.collaboration_count,
            )
            .filter(
                or_(
                    and_(
                        Collaboration.author_id_1 == author_id,
                        Collaboration.author_id_2.in_(other_ids),
                    ),
                    and_(
                        Collaboration.author_id_2 == author_id,
                        Collaboration.author_id_1.in_(other_ids),
                    ),
                )
            )
            .all()
        )

        result = {}
        for a1, a2, cnt in rows:
            other = a2 if a1 == author_id else a1
            result[other] = cnt
        return result

    def create_or_update(
        self,
        author_id_1: str,
        author_id_2: str,
        weight: float,
        publication_date: Optional[datetime] = None,
    ) -> Collaboration:
        """Create or update a collaboration edge."""
        a, b = sorted([author_id_1, author_id_2])

        collab = self.get_collaboration(a, b)
        if collab:
            collab.collaboration_count += 1
            collab.total_weight += weight
            if publication_date:
                if collab.first_collaboration is None or publication_date < collab.first_collaboration:
                    collab.first_collaboration = publication_date
                if collab.last_collaboration is None or publication_date > collab.last_collaboration:
                    collab.last_collaboration = publication_date
        else:
            collab = Collaboration(
                author_id_1=a,
                author_id_2=b,
                collaboration_count=1,
                total_weight=weight,
                first_collaboration=publication_date,
                last_collaboration=publication_date,
            )
            self.session.add(collab)

        return collab

    def get_co_authored_works(
        self,
        author_id_1: str,
        author_id_2: str,
        limit: int = 20,
        offset: int = 0,
        sort_by: str = "publication_date",
        sort_order: str = "desc",
        from_year: Optional[int] = None,
        to_year: Optional[int] = None,
    ) -> tuple[list, int]:
        """Get co-authored works between two authors (handles aliases)."""
        author_1 = self.session.query(Author).filter(Author.id == author_id_1).first()
        author_2 = self.session.query(Author).filter(Author.id == author_id_2).first()

        ids_1 = author_1.get_all_ids() if author_1 else [author_id_1]
        ids_2 = author_2.get_all_ids() if author_2 else [author_id_2]

        sub1 = (
            self.session.query(Authorship.work_id)
            .filter(Authorship.author_id.in_(ids_1))
            .subquery()
        )
        sub2 = (
            self.session.query(Authorship.work_id)
            .filter(Authorship.author_id.in_(ids_2))
            .subquery()
        )

        q = self.session.query(Work).filter(
            Work.id.in_(self.session.query(sub1)),
            Work.id.in_(self.session.query(sub2)),
        )

        if from_year:
            q = q.filter(Work.publication_year >= from_year)
        if to_year:
            q = q.filter(Work.publication_year <= to_year)

        total = q.count()

        sort_col = getattr(Work, sort_by, Work.publication_date)
        if sort_order == "desc":
            q = q.order_by(sort_col.desc().nullslast())
        else:
            q = q.order_by(sort_col.asc().nullsfirst())

        works = q.offset(offset).limit(limit).all()
        return works, total

    def get_statistics(self) -> dict:
        total = self.session.query(func.count(Collaboration.id)).scalar() or 0
        total_scores = self.session.query(func.count(RelationshipScore.id)).scalar() or 0
        return {"total_collaborations": total, "total_relationship_scores": total_scores}
