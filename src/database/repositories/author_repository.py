"""
Author data access layer.
"""
import json
import logging
from typing import Optional

from sqlalchemy import func, or_, and_, distinct, text
from sqlalchemy.orm import Session

from src.database.models import Author, Work, Authorship, Collaboration, InstitutionStats

logger = logging.getLogger(__name__)


class AuthorRepository:
    """Repository for author data access."""

    def __init__(self, session: Session):
        self.session = session

    # ---- basic CRUD ----

    def get_by_id(self, author_id: str) -> Optional[Author]:
        return self.session.query(Author).filter(Author.id == author_id).first()

    def get_by_ids(self, author_ids: list[str]) -> list[Author]:
        """Batch-fetch multiple authors by ID."""
        if not author_ids:
            return []
        return self.session.query(Author).filter(Author.id.in_(author_ids)).all()

    def exists(self, author_id: str) -> bool:
        return (
            self.session.query(Author.id)
            .filter(Author.id == author_id)
            .first() is not None
        )

    # ---- canonical / alias ----

    def get_canonical_id(self, author_id: str) -> str:
        """Resolve an author ID to its canonical ID."""
        author = self.get_by_id(author_id)
        if author:
            if author.is_canonical:
                return author.id
            # Look for canonical that owns this alias
            canonical = (
                self.session.query(Author)
                .filter(
                    Author.is_canonical == True,
                    Author.alias_ids.contains(author_id),
                )
                .first()
            )
            if canonical:
                return canonical.id
        return author_id

    def get_all_ids_info(self, canonical_id: str) -> list[dict]:
        """
        Get info for a canonical author and all its aliases in a single query.
        """
        author = self.get_by_id(canonical_id)
        if not author:
            return []

        all_ids = author.get_all_ids()
        if len(all_ids) <= 1:
            # Short-circuit: no aliases, just return the canonical info
            wc = (
                self.session.query(func.count(Authorship.id))
                .filter(Authorship.author_id == canonical_id)
                .scalar()
            ) or 0
            return [{
                "id": canonical_id,
                "orcid": author.orcid,
                "works_count": wc,
            }]

        # Batch query: get works_count for all IDs in one query
        counts = (
            self.session.query(
                Authorship.author_id,
                func.count(Authorship.id).label("cnt"),
            )
            .filter(Authorship.author_id.in_(all_ids))
            .group_by(Authorship.author_id)
            .all()
        )
        count_map = {aid: cnt for aid, cnt in counts}

        # Batch query: get orcid for all IDs in one query
        authors = self.session.query(Author.id, Author.orcid).filter(Author.id.in_(all_ids)).all()
        orcid_map = {a.id: a.orcid for a in authors}

        return [
            {"id": aid, "orcid": orcid_map.get(aid), "works_count": count_map.get(aid, 0)}
            for aid in all_ids
        ]

    # ---- search ----

    def search_by_name_with_count(
        self,
        query: str,
        limit: int = 20,
        offset: int = 0,
        canonical_only: bool = True,
        fuzzy: bool = False,
    ) -> tuple[list[tuple[Author, int]], int]:
        """
        Search authors by name, returning (author, works_count) pairs.

        Uses a subquery to compute merged works counts in a single pass rather
        than issuing per-author queries (N+1 fix).
        """
        base_q = self.session.query(Author)
        if canonical_only:
            base_q = base_q.filter(Author.is_canonical == True)

        if fuzzy:
            base_q = base_q.filter(Author.display_name.ilike(f"%{query}%"))
        else:
            exact = base_q.filter(Author.display_name == query)
            if exact.count() > 0:
                base_q = exact
            else:
                base_q = base_q.filter(Author.display_name.ilike(f"%{query}%"))

        total = base_q.count()
        authors = base_q.order_by(Author.display_name).offset(offset).limit(limit).all()

        if not authors:
            return [], 0

        # Batch compute works counts for all matched authors
        all_ids_per_author: dict[str, list[str]] = {}
        flat_ids: list[str] = []
        for a in authors:
            ids = a.get_all_ids()
            all_ids_per_author[a.id] = ids
            flat_ids.extend(ids)

        counts = (
            self.session.query(
                Authorship.author_id,
                func.count(distinct(Authorship.work_id)).label("cnt"),
            )
            .filter(Authorship.author_id.in_(flat_ids))
            .group_by(Authorship.author_id)
            .all()
        )
        count_map = {aid: cnt for aid, cnt in counts}

        results = []
        for a in authors:
            wc = sum(count_map.get(aid, 0) for aid in all_ids_per_author[a.id])
            results.append((a, wc))

        return results, total

    # ---- merged counts ----

    def get_merged_works_count(self, canonical_id: str) -> int:
        """Get total works count across canonical + alias IDs."""
        author = self.get_by_id(canonical_id)
        if not author:
            return 0

        all_ids = author.get_all_ids()
        count = (
            self.session.query(func.count(distinct(Authorship.work_id)))
            .filter(Authorship.author_id.in_(all_ids))
            .scalar()
        )
        return count or 0

    def _get_merged_cited_by_count_by_year(self, canonical_id: str) -> int:
        """Get total cited_by_count from works authored by canonical + aliases."""
        author = self.get_by_id(canonical_id)
        if not author:
            return 0

        all_ids = author.get_all_ids()
        total = (
            self.session.query(func.coalesce(func.sum(Work.cited_by_count), 0))
            .join(Authorship, Work.id == Authorship.work_id)
            .filter(Authorship.author_id.in_(all_ids))
            .scalar()
        )
        return int(total or 0)

    # ---- institution frequencies ----

    def get_institution_frequencies(self, canonical_id: str, limit: int = 5) -> list[dict]:
        """Get institution frequency from authorship affiliations."""
        author = self.get_by_id(canonical_id)
        if not author:
            return []

        all_ids = author.get_all_ids()

        rows = (
            self.session.query(
                Authorship.raw_affiliation,
                func.count(Authorship.id).label("cnt"),
            )
            .filter(
                Authorship.author_id.in_(all_ids),
                Authorship.raw_affiliation.isnot(None),
                Authorship.raw_affiliation != "",
            )
            .group_by(Authorship.raw_affiliation)
            .order_by(func.count(Authorship.id).desc())
            .limit(limit)
            .all()
        )

        return [{"name": row.raw_affiliation, "count": row.cnt} for row in rows]

    def get_primary_institutions_batch(self, author_ids: list[str]) -> dict[str, Optional[str]]:
        """
        Batch-fetch primary institution name for multiple authors.

        Returns dict mapping author_id -> primary institution name.
        Uses a single query with window function instead of N queries.
        """
        if not author_ids:
            return {}

        sub = (
            self.session.query(
                Authorship.author_id,
                Authorship.raw_affiliation,
                func.row_number().over(
                    partition_by=Authorship.author_id,
                    order_by=func.count(Authorship.id).desc(),
                ).label("rn"),
            )
            .filter(
                Authorship.author_id.in_(author_ids),
                Authorship.raw_affiliation.isnot(None),
                Authorship.raw_affiliation != "",
            )
            .group_by(Authorship.author_id, Authorship.raw_affiliation)
            .subquery()
        )

        rows = (
            self.session.query(sub.c.author_id, sub.c.raw_affiliation)
            .filter(sub.c.rn == 1)
            .all()
        )

        return {row.author_id: row.raw_affiliation for row in rows}

    # ---- collaborators ----

    def get_collaborators(
        self,
        author_id: str,
        limit: int = 50,
        from_year: Optional[int] = None,
        to_year: Optional[int] = None,
    ) -> list[tuple[Author, int]]:
        """Get direct collaborators sorted by collaboration count."""
        q = self.session.query(Collaboration).filter(
            or_(
                Collaboration.author_id_1 == author_id,
                Collaboration.author_id_2 == author_id,
            )
        )
        collaborations = q.order_by(Collaboration.collaboration_count.desc()).limit(limit).all()

        # Batch-fetch all collaborator authors
        other_ids = []
        for collab in collaborations:
            other_id = collab.author_id_2 if collab.author_id_1 == author_id else collab.author_id_1
            other_ids.append(other_id)

        authors_map = {a.id: a for a in self.get_by_ids(other_ids)}

        results = []
        for collab, other_id in zip(collaborations, other_ids):
            other_author = authors_map.get(other_id)
            if other_author:
                results.append((other_author, collab.collaboration_count))

        return results

    # ---- institution ranking ----

    def get_institutions(
        self,
        limit: Optional[int] = None,
        offset: int = 0,
        query: Optional[str] = None,
        use_cache: bool = True,
    ) -> tuple[list[dict], int]:
        """List institutions with author counts."""
        if use_cache:
            q = self.session.query(InstitutionStats)
            if query:
                q = q.filter(InstitutionStats.institution_name.ilike(f"%{query}%"))
            total = q.count()
            q = q.order_by(InstitutionStats.author_count.desc())
            if limit:
                q = q.offset(offset).limit(limit)
            stats = q.all()
            return [
                {"id": s.institution_id, "name": s.institution_name, "author_count": s.author_count}
                for s in stats
            ], total

        # Fallback: live query
        q = (
            self.session.query(
                Author.last_known_institution_id,
                Author.last_known_institution_name,
                func.count(Author.id).label("cnt"),
            )
            .filter(
                Author.is_canonical == True,
                Author.last_known_institution_id.isnot(None),
            )
            .group_by(Author.last_known_institution_id, Author.last_known_institution_name)
            .order_by(func.count(Author.id).desc())
        )
        if query:
            q = q.filter(Author.last_known_institution_name.ilike(f"%{query}%"))
        total = q.count()
        if limit:
            q = q.offset(offset).limit(limit)
        results = q.all()
        return [
            {"id": r.last_known_institution_id, "name": r.last_known_institution_name, "author_count": r.cnt}
            for r in results
        ], total

    def refresh_institution_stats(self):
        """Refresh the institution_stats cache table."""
        self.session.execute(text("DELETE FROM institution_stats"))
        self.session.execute(text("""
            INSERT INTO institution_stats (institution_id, institution_name, author_count)
            SELECT last_known_institution_id, MAX(last_known_institution_name), COUNT(id)
            FROM authors
            WHERE is_canonical = true AND last_known_institution_id IS NOT NULL
            GROUP BY last_known_institution_id
        """))
        self.session.commit()

    def get_top_authors_by_institution(
        self,
        institution_id: Optional[str] = None,
        institution_name: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        from_year: Optional[int] = None,
        to_year: Optional[int] = None,
        fast: bool = True,
    ) -> tuple[list[tuple[Author, int, int]], int]:
        """
        Get top authors for an institution by publication count.

        In fast mode, uses the pre-computed works_count on Author for sorting
        (avoids expensive JOIN/GROUP BY).
        """
        if not institution_id and not institution_name:
            raise ValueError("Either institution_id or institution_name required")

        base_q = self.session.query(Author).filter(Author.is_canonical == True)

        if institution_id:
            base_q = base_q.filter(Author.last_known_institution_id == institution_id)
        elif institution_name:
            base_q = base_q.filter(Author.last_known_institution_name.ilike(f"%{institution_name}%"))

        total = base_q.count()

        if fast:
            authors = (
                base_q
                .order_by(Author.works_count.desc().nullslast())
                .offset(offset)
                .limit(limit)
                .all()
            )
            return [(a, a.works_count or 0, a.cited_by_count or 0) for a in authors], total

        # Slow path: compute from authorships with optional year filter
        count_q = (
            self.session.query(
                Authorship.author_id,
                func.count(distinct(Authorship.work_id)).label("works_cnt"),
            )
        )
        if from_year or to_year:
            count_q = count_q.join(Work, Work.id == Authorship.work_id)
            if from_year:
                count_q = count_q.filter(Work.publication_year >= from_year)
            if to_year:
                count_q = count_q.filter(Work.publication_year <= to_year)

        author_ids_sub = base_q.with_entities(Author.id).subquery()
        count_q = count_q.filter(Authorship.author_id.in_(self.session.query(author_ids_sub)))
        count_q = count_q.group_by(Authorship.author_id)
        count_q = count_q.order_by(func.count(distinct(Authorship.work_id)).desc())
        count_q = count_q.offset(offset).limit(limit)

        rows = count_q.all()
        if not rows:
            return [], total

        author_ids = [r.author_id for r in rows]
        count_map = {r.author_id: r.works_cnt for r in rows}

        authors = self.session.query(Author).filter(Author.id.in_(author_ids)).all()
        author_map = {a.id: a for a in authors}

        results = []
        for aid in author_ids:
            a = author_map.get(aid)
            if a:
                results.append((a, count_map.get(aid, 0), a.cited_by_count or 0))

        return results, total

    # ---- statistics ----

    def get_statistics(self) -> dict:
        total = self.session.query(func.count(Author.id)).scalar() or 0
        canonical = (
            self.session.query(func.count(Author.id))
            .filter(Author.is_canonical == True)
            .scalar()
        ) or 0
        with_orcid = (
            self.session.query(func.count(Author.id))
            .filter(Author.orcid.isnot(None))
            .scalar()
        ) or 0
        return {"total": total, "canonical": canonical, "with_orcid": with_orcid}
