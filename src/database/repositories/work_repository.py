"""Repository for Work operations."""
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.database.models import Work, Authorship, Author


class WorkRepository:
    """Repository for Work CRUD operations."""

    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, work_id: str) -> Optional[Work]:
        """Get work by OpenAlex ID."""
        return self.session.query(Work).filter(Work.id == work_id).first()

    def get_by_doi(self, doi: str) -> Optional[Work]:
        """Get work by DOI."""
        return self.session.query(Work).filter(Work.doi == doi).first()

    def exists(self, work_id: str) -> bool:
        """Check if work exists."""
        return (
            self.session.query(func.count(Work.id))
            .filter(Work.id == work_id)
            .scalar() > 0
        )

    def create(self, work_data: dict) -> Work:
        """Create a new work."""
        work = Work(**work_data)
        self.session.add(work)
        return work

    def get_or_create(self, work_id: str, **kwargs) -> tuple[Work, bool]:
        """Get existing work or create new one. Returns (work, created)."""
        work = self.get_by_id(work_id)
        if work:
            # Update fields if provided
            for key, value in kwargs.items():
                if hasattr(work, key) and value is not None:
                    setattr(work, key, value)
            return work, False

        work = Work(id=work_id, **kwargs)
        self.session.add(work)
        return work, True

    def bulk_insert(self, works: list[dict]) -> int:
        """Bulk insert works. Returns count of new works."""
        created_count = 0
        for work_data in works:
            work_id = work_data.pop("id")
            _, created = self.get_or_create(work_id, **work_data)
            if created:
                created_count += 1
        return created_count

    def get_works_by_author(
        self,
        author_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> list[Work]:
        """Get works by a specific author."""
        return (
            self.session.query(Work)
            .join(Authorship)
            .filter(Authorship.author_id == author_id)
            .order_by(Work.publication_date.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_works_in_date_range(
        self,
        start_date: datetime,
        end_date: Optional[datetime] = None
    ) -> list[Work]:
        """Get works published in a date range."""
        query = self.session.query(Work).filter(
            Work.publication_date >= start_date
        )
        if end_date:
            query = query.filter(Work.publication_date <= end_date)
        return query.order_by(Work.publication_date.desc()).all()

    def count(self) -> int:
        """Get total number of works."""
        return self.session.query(func.count(Work.id)).scalar()

    def get_latest_publication_date(self) -> Optional[datetime]:
        """Get the most recent publication date."""
        return (
            self.session.query(func.max(Work.publication_date)).scalar()
        )

    def get_statistics(self) -> dict:
        """Get work statistics."""
        return {
            "total_works": self.count(),
            "avg_citations": (
                self.session.query(func.avg(Work.cited_by_count)).scalar() or 0
            ),
            "open_access_count": (
                self.session.query(func.count(Work.id))
                .filter(Work.is_open_access == True)
                .scalar()
            ),
            "latest_publication": self.get_latest_publication_date(),
        }
