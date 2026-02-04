"""Repository for Author operations."""
from functools import lru_cache
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_, func, select

from src.database.models import (
    Author,
    Authorship,
    Collaboration,
    RelationshipScore,
    Work,
    InstitutionStats,
)

# Simple in-memory cache for search count (cleared on restart)
_search_count_cache = {}


class AuthorRepository:
    """Repository for Author CRUD operations."""

    def __init__(self, session: Session):
        self.session = session

    def _build_works_count_subquery(
        self,
        from_year: Optional[int] = None,
        to_year: Optional[int] = None,
        author_ids_subquery=None,
    ):
        """Build a works count subquery with optional year filters."""
        query = (
            self.session.query(
                Authorship.author_id,
                func.count(func.distinct(Authorship.work_id)).label("works_count"),
            )
        )

        if author_ids_subquery is not None:
            query = query.filter(Authorship.author_id.in_(author_ids_subquery))

        if from_year is not None or to_year is not None:
            query = query.join(Work, Authorship.work_id == Work.id)
            if from_year is not None:
                query = query.filter(Work.publication_year >= from_year)
            if to_year is not None:
                query = query.filter(Work.publication_year <= to_year)

        return query.group_by(Authorship.author_id).subquery()

    def _build_cited_by_subquery(
        self,
        from_year: Optional[int] = None,
        to_year: Optional[int] = None,
        author_ids_subquery=None,
    ):
        """Build a cited_by_count subquery with optional year filters."""
        query = (
            self.session.query(
                Authorship.author_id,
                func.sum(Work.cited_by_count).label("cited_by_count"),
            )
            .join(Work, Authorship.work_id == Work.id)
        )

        if author_ids_subquery is not None:
            query = query.filter(Authorship.author_id.in_(author_ids_subquery))

        if from_year is not None:
            query = query.filter(Work.publication_year >= from_year)
        if to_year is not None:
            query = query.filter(Work.publication_year <= to_year)

        return query.group_by(Authorship.author_id).subquery()

    def get_by_id(self, author_id: str) -> Optional[Author]:
        """Get author by OpenAlex ID."""
        return self.session.query(Author).filter(Author.id == author_id).first()

    def search_by_name(
        self,
        query: str,
        limit: int = 20,
        offset: int = 0,
        canonical_only: bool = True
    ) -> list[Author]:
        """Search authors by name (case-insensitive exact match)."""
        results, _ = self.search_by_name_with_count(
            query=query,
            limit=limit,
            offset=offset,
            canonical_only=canonical_only,
        )
        return [author for author, _ in results]

    def search_by_name_with_count(
        self,
        query: str,
        limit: int = 20,
        offset: int = 0,
        canonical_only: bool = True
    ) -> tuple[list[tuple[Author, int]], int]:
        """Search authors by name with total count (case-insensitive exact match)."""
        # Build base filter - try case-sensitive exact match first (fast path)
        base_filter = Author.display_name == query
        if canonical_only:
            base_filter = base_filter & (Author.is_canonical == True)

        total = (
            self.session.query(func.count(Author.id))
            .filter(base_filter)
            .scalar() or 0
        )

        # Fallback to case-insensitive match if no results
        if total == 0:
            base_filter = Author.display_name.collate("NOCASE") == query
            if canonical_only:
                base_filter = base_filter & (Author.is_canonical == True)
            total = (
                self.session.query(func.count(Author.id))
                .filter(base_filter)
                .scalar() or 0
            )

        rows = (
            self.session.query(Author)
            .filter(base_filter)
            .order_by(Author.works_count.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        # Compute merged works count for all canonical authors
        results: list[tuple[Author, int]] = []
        for author in rows:
            if author.is_canonical:
                # Always compute actual count from authorships table
                merged_count = self.get_merged_works_count(author.id)
            else:
                # For non-canonical (alias) authors, use cached count
                merged_count = author.works_count or 0
            results.append((author, merged_count))

        # Re-sort within the page to reflect merged counts
        results.sort(key=lambda x: x[1], reverse=True)
        return results, total

    def get_or_create(
        self,
        author_id: str,
        display_name: str,
        **kwargs
    ) -> tuple[Author, bool]:
        """Get existing author or create new one. Returns (author, created)."""
        author = self.get_by_id(author_id)
        if author:
            # Update fields if provided
            for key, value in kwargs.items():
                if hasattr(author, key) and value is not None:
                    setattr(author, key, value)
            return author, False

        author = Author(
            id=author_id,
            display_name=display_name,
            **kwargs
        )
        self.session.add(author)
        return author, True

    def bulk_upsert(self, authors: list[dict]) -> int:
        """Bulk insert or update authors. Returns count of new authors."""
        created_count = 0
        for author_data in authors:
            author_id = author_data.pop("id")
            display_name = author_data.pop("display_name")
            _, created = self.get_or_create(author_id, display_name, **author_data)
            if created:
                created_count += 1
        return created_count

    def get_collaborators(
        self,
        author_id: str,
        limit: int = 50,
        from_year: Optional[int] = None,
        to_year: Optional[int] = None
    ) -> list[tuple[Author, int]]:
        """Get collaborators of an author with collaboration count.

        Args:
            author_id: The author's OpenAlex ID
            limit: Maximum results
            from_year: Filter collaborations from this year (inclusive)
            to_year: Filter collaborations up to this year (inclusive)
        """
        # If year filter is specified, we need to count collaborations through works
        if from_year is not None or to_year is not None:
            return self._get_collaborators_by_year_range(
                author_id, limit, from_year, to_year
            )

        # Original logic without year filter - use pre-computed Collaboration table
        # Query where author is author_1
        q1 = (
            self.session.query(Author, Collaboration.collaboration_count)
            .join(Collaboration, Author.id == Collaboration.author_id_2)
            .filter(Collaboration.author_id_1 == author_id)
        )

        # Query where author is author_2
        q2 = (
            self.session.query(Author, Collaboration.collaboration_count)
            .join(Collaboration, Author.id == Collaboration.author_id_1)
            .filter(Collaboration.author_id_2 == author_id)
        )

        # Union and order
        results = (
            q1.union(q2)
            .order_by(Collaboration.collaboration_count.desc())
            .limit(limit)
            .all()
        )

        return [(author, count) for author, count in results]

    def _get_collaborators_by_year_range(
        self,
        author_id: str,
        limit: int = 50,
        from_year: Optional[int] = None,
        to_year: Optional[int] = None
    ) -> list[tuple[Author, int]]:
        """Get collaborators with collaboration count filtered by year range.

        This queries through Authorship and Work tables to dynamically count
        collaborations within the specified time range.
        """
        import json

        # Get all IDs for the author (including aliases)
        author = self.get_by_id(author_id)
        if not author:
            return []

        author_ids = [author_id]
        if author.alias_ids:
            try:
                author_ids.extend(json.loads(author.alias_ids))
            except:
                pass

        # Subquery: find all work_ids the author participated in (within year range)
        # Using select() construct for proper subquery handling in SQLAlchemy 1.4+
        work_ids_stmt = (
            select(Authorship.work_id)
            .join(Work, Authorship.work_id == Work.id)
            .where(Authorship.author_id.in_(author_ids))
        )

        if from_year is not None:
            work_ids_stmt = work_ids_stmt.where(Work.publication_year >= from_year)
        if to_year is not None:
            work_ids_stmt = work_ids_stmt.where(Work.publication_year <= to_year)

        # Query: find all other authors who co-authored these works, with count
        results = (
            self.session.query(
                Author,
                func.count(func.distinct(Authorship.work_id)).label('collab_count')
            )
            .join(Authorship, Author.id == Authorship.author_id)
            .filter(Authorship.work_id.in_(work_ids_stmt))
            .filter(~Authorship.author_id.in_(author_ids))  # Exclude the author themselves
            .filter(Author.is_canonical == True)  # Only canonical authors
            .group_by(Author.id)
            .order_by(func.count(func.distinct(Authorship.work_id)).desc())
            .limit(limit)
            .all()
        )

        return [(author, count) for author, count in results]

    def get_top_relations(
        self,
        author_id: str,
        limit: int = 20,
        score_type: str = "combined_score"
    ) -> list[tuple[Author, float]]:
        """Get top related authors based on relationship scores."""
        score_col = getattr(RelationshipScore, score_type)

        # Use JOIN to avoid N+1 queries
        # Query where author is author_1
        q1 = (
            self.session.query(Author, score_col)
            .join(RelationshipScore, Author.id == RelationshipScore.author_id_2)
            .filter(RelationshipScore.author_id_1 == author_id)
            .filter(score_col.isnot(None))
        )

        # Query where author is author_2
        q2 = (
            self.session.query(Author, score_col)
            .join(RelationshipScore, Author.id == RelationshipScore.author_id_1)
            .filter(RelationshipScore.author_id_2 == author_id)
            .filter(score_col.isnot(None))
        )

        # Union and order
        results = (
            q1.union(q2)
            .order_by(score_col.desc())
            .limit(limit)
            .all()
        )

        return [(author, score) for author, score in results]

    def count(self, canonical_only: bool = True) -> int:
        """Get total number of authors."""
        query = self.session.query(func.count(Author.id))
        if canonical_only:
            query = query.filter(Author.is_canonical == True)
        return query.scalar()

    def get_merged_works_count(self, author_id: str) -> int:
        """Get total works count for an author including all merged aliases."""
        import json

        author = self.get_by_id(author_id)
        if not author:
            return 0

        # Get all IDs (main + aliases)
        all_ids = [author_id]
        if author.alias_ids:
            try:
                all_ids.extend(json.loads(author.alias_ids))
            except:
                pass

        # Count unique works
        count = (
            self.session.query(func.count(func.distinct(Authorship.work_id)))
            .filter(Authorship.author_id.in_(all_ids))
            .scalar() or 0
        )
        return count

    def get_canonical_id(self, author_id: str) -> str:
        """Get the canonical (main) ID for an author.

        If the author_id is an alias, returns the canonical ID.
        Otherwise returns the same ID.
        """
        # Check if this is an alias
        alias = (
            self.session.query(Author)
            .filter(Author.id == author_id, Author.is_canonical == False)
            .first()
        )

        if alias:
            # Find the canonical record that has this ID in alias_ids
            import json
            canonical = (
                self.session.query(Author)
                .filter(Author.is_canonical == True)
                .filter(Author.alias_ids.contains(author_id))
                .first()
            )
            if canonical:
                return canonical.id

        return author_id

    def get_all_ids_info(self, author_id: str) -> list[dict]:
        """Get info for all IDs (main + aliases) of a merged author.

        Returns list of dicts with id, orcid, works_count for each ID.
        """
        import json

        author = self.get_by_id(author_id)
        if not author:
            return []

        # Collect all IDs
        all_ids = [author_id]
        if author.alias_ids:
            try:
                all_ids.extend(json.loads(author.alias_ids))
            except:
                pass

        # Get info for each ID
        results = []
        for aid in all_ids:
            a = self.session.query(Author).filter(Author.id == aid).first()
            if a:
                # Count works for this specific ID
                works = (
                    self.session.query(func.count(Authorship.id))
                    .filter(Authorship.author_id == aid)
                    .scalar() or 0
                )
                results.append({
                    "id": aid,
                    "orcid": a.orcid,
                    "works_count": works,
                })

        # Sort by works_count descending
        results.sort(key=lambda x: x["works_count"], reverse=True)
        return results

    def get_institution_frequencies(
        self,
        author_id: str,
        limit: int = 5,
    ) -> list[dict]:
        """Get top institutions for an author based on authorship affiliations."""
        import json
        from collections import Counter

        author = self.get_by_id(author_id)
        if not author:
            return []

        all_ids = [author_id]
        if author.alias_ids:
            try:
                all_ids.extend(json.loads(author.alias_ids))
            except:
                pass

        rows = (
            self.session.query(Authorship.raw_affiliation)
            .filter(Authorship.author_id.in_(all_ids))
            .filter(Authorship.raw_affiliation.isnot(None))
            .all()
        )

        counter = Counter()
        for (raw_affiliation,) in rows:
            if not raw_affiliation:
                continue
            for inst in [item.strip() for item in raw_affiliation.split(";") if item.strip()]:
                counter[inst] += 1

        return [
            {"name": name, "count": count}
            for name, count in counter.most_common(limit)
        ]

    def get_statistics(self) -> dict:
        """Get author statistics."""
        return {
            "total_authors": self.count(),
            "with_orcid": (
                self.session.query(func.count(Author.id))
                .filter(Author.orcid.isnot(None))
                .scalar()
            ),
            "avg_works_count": (
                self.session.query(func.avg(Author.works_count)).scalar() or 0
            ),
            "avg_cited_by_count": (
                self.session.query(func.avg(Author.cited_by_count)).scalar() or 0
            ),
        }

    def get_top_authors_by_institution(
        self,
        institution_id: str = None,
        institution_name: str = None,
        limit: int = 50,
        offset: int = 0,
        from_year: Optional[int] = None,
        to_year: Optional[int] = None,
        fast: bool = True,
    ) -> tuple[list[tuple], int]:
        """Get top authors by works count for an institution.

        Args:
            institution_id: OpenAlex institution ID (e.g., I16365422)
            institution_name: Institution name (partial match)
            limit: Maximum results
            offset: Result offset
            from_year: Filter works from this year (inclusive)
            to_year: Filter works up to this year (inclusive)

        Returns:
            Tuple of (list of (author, works_count, cited_by_count), total_count)
        """
        if institution_name:
            return self._get_top_authors_by_affiliation(
                institution_name=institution_name,
                limit=limit,
                offset=offset,
                from_year=from_year,
                to_year=to_year,
            )

        # Fallback to last known institution if no name is available
        if not institution_id:
            raise ValueError("Either institution_id or institution_name must be provided")

        # Fast path: use cached counts on Author table (no year filters)
        if fast and from_year is None and to_year is None:
            base_filter = (
                (Author.is_canonical == True)
                & (Author.last_known_institution_id == institution_id)
            )
            total = (
                self.session.query(func.count(Author.id))
                .filter(base_filter)
                .scalar() or 0
            )

            rows = (
                self.session.query(Author)
                .filter(base_filter)
                .order_by(Author.works_count.desc())
                .offset(offset)
                .limit(limit)
                .all()
            )

            results = []
            for author in rows:
                works_count = self.get_merged_works_count(author.id)
                cited_by_count = self._get_merged_cited_by_count_by_year(author.id)
                results.append((author, works_count, cited_by_count))

            results.sort(key=lambda x: x[1], reverse=True)
            return results, total

        # Build base filter for canonical authors only
        base_filter = (
            (Author.is_canonical == True)
            & (Author.last_known_institution_id == institution_id)
        )

        author_ids_subquery = select(Author.id).where(base_filter)

        works_subquery = self._build_works_count_subquery(
            from_year, to_year, author_ids_subquery
        )
        cited_subquery = self._build_cited_by_subquery(
            from_year, to_year, author_ids_subquery
        )

        works_col = func.coalesce(works_subquery.c.works_count, 0)
        cited_col = func.coalesce(cited_subquery.c.cited_by_count, 0)

        query = (
            self.session.query(Author, works_col, cited_col)
            .outerjoin(works_subquery, Author.id == works_subquery.c.author_id)
            .outerjoin(cited_subquery, Author.id == cited_subquery.c.author_id)
            .filter(base_filter)
        )

        # For year-filtered requests, only include authors with works in range
        if from_year is not None or to_year is not None:
            query = query.filter(works_subquery.c.works_count.isnot(None))

        # Total count (fast, accurate for both modes)
        if from_year is not None or to_year is not None:
            total = (
                self.session.query(func.count(Author.id))
                .join(works_subquery, Author.id == works_subquery.c.author_id)
                .filter(base_filter)
                .scalar() or 0
            )
        else:
            total = (
                self.session.query(func.count(Author.id))
                .filter(base_filter)
                .scalar() or 0
            )

        rows = (
            query
            .order_by(works_col.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        # Calculate merged counts only when aliases exist
        results = []
        for author, works_count, cited_by_count in rows:
            merged_count = works_count
            merged_cited = cited_by_count
            if author.alias_ids:
                if from_year is not None or to_year is not None:
                    merged_count = self._get_merged_works_count_by_year(
                        author.id, from_year, to_year
                    )
                    merged_cited = self._get_merged_cited_by_count_by_year(
                        author.id, from_year, to_year
                    )
                else:
                    merged_count = self.get_merged_works_count(author.id)
                    merged_cited = self._get_merged_cited_by_count_by_year(author.id)
            results.append((author, merged_count, merged_cited))

        # Re-sort by merged count to keep ordering stable when aliases exist
        results.sort(key=lambda x: x[1], reverse=True)
        return results, total

    def _get_top_authors_by_affiliation(
        self,
        institution_name: str,
        limit: int = 50,
        offset: int = 0,
        from_year: Optional[int] = None,
        to_year: Optional[int] = None,
    ) -> tuple[list[tuple], int]:
        """Get top authors by works count within a specific affiliation name."""
        from collections import defaultdict
        import json

        query = self.session.query(
            Authorship.author_id,
            func.count(func.distinct(Authorship.work_id)).label("works_count"),
        ).filter(
            Authorship.raw_affiliation.isnot(None),
            Authorship.raw_affiliation.ilike(f"%{institution_name}%"),
        )

        if from_year is not None or to_year is not None:
            query = query.join(Work, Authorship.work_id == Work.id)
            if from_year is not None:
                query = query.filter(Work.publication_year >= from_year)
            if to_year is not None:
                query = query.filter(Work.publication_year <= to_year)

        query = query.group_by(Authorship.author_id)
        rows = query.all()

        if not rows:
            return [], 0

        # Build alias -> canonical map
        alias_to_canonical = {}
        canonical_rows = (
            self.session.query(Author.id, Author.alias_ids)
            .filter(Author.is_canonical == True)
            .filter(Author.alias_ids.isnot(None))
            .all()
        )
        for canonical_id, alias_ids in canonical_rows:
            try:
                aliases = json.loads(alias_ids)
            except Exception:
                aliases = []
            for alias in aliases:
                alias_to_canonical[alias] = canonical_id

        # Aggregate counts by canonical author
        counts = defaultdict(int)
        for author_id, works_count in rows:
            canonical_id = alias_to_canonical.get(author_id, author_id)
            counts[canonical_id] += works_count

        total = len(counts)
        if total == 0:
            return [], 0

        # Fetch author records
        author_ids = list(counts.keys())
        authors = (
            self.session.query(Author)
            .filter(Author.id.in_(author_ids))
            .all()
        )
        author_map = {author.id: author for author in authors}

        # Sort and paginate
        sorted_ids = sorted(counts.keys(), key=lambda aid: counts[aid], reverse=True)
        paged_ids = sorted_ids[offset:offset + limit]

        results = []
        for author_id in paged_ids:
            author = author_map.get(author_id)
            if not author:
                continue
            cited_by_count = self._get_merged_cited_by_count_by_year(author.id)
            results.append((author, counts[author_id], cited_by_count))

        return results, total

    def _get_merged_works_count_by_year(
        self,
        author_id: str,
        from_year: Optional[int] = None,
        to_year: Optional[int] = None
    ) -> int:
        """Get total works count for an author within a year range."""
        import json

        author = self.get_by_id(author_id)
        if not author:
            return 0

        # Get all IDs (main + aliases)
        all_ids = [author_id]
        if author.alias_ids:
            try:
                all_ids.extend(json.loads(author.alias_ids))
            except:
                pass

        # Build query with year filter
        query = (
            self.session.query(func.count(func.distinct(Authorship.work_id)))
            .join(Work, Authorship.work_id == Work.id)
            .filter(Authorship.author_id.in_(all_ids))
        )

        if from_year is not None:
            query = query.filter(Work.publication_year >= from_year)
        if to_year is not None:
            query = query.filter(Work.publication_year <= to_year)

        return query.scalar() or 0

    def _get_merged_cited_by_count_by_year(
        self,
        author_id: str,
        from_year: Optional[int] = None,
        to_year: Optional[int] = None
    ) -> int:
        """Get total cited_by_count for an author's works within a year range."""
        import json

        author = self.get_by_id(author_id)
        if not author:
            return 0

        # Get all IDs (main + aliases)
        all_ids = [author_id]
        if author.alias_ids:
            try:
                all_ids.extend(json.loads(author.alias_ids))
            except:
                pass

        # Build query - sum cited_by_count of all distinct works by this author
        query = (
            self.session.query(func.sum(Work.cited_by_count))
            .join(Authorship, Work.id == Authorship.work_id)
            .filter(Authorship.author_id.in_(all_ids))
        )

        if from_year is not None:
            query = query.filter(Work.publication_year >= from_year)
        if to_year is not None:
            query = query.filter(Work.publication_year <= to_year)

        return query.scalar() or 0

    def get_institutions(
        self,
        limit: Optional[int] = None,
        offset: int = 0,
        query: Optional[str] = None,
        use_cache: bool = True,
    ) -> tuple[list[dict], int]:
        """Get list of all institutions with author counts."""
        if use_cache:
            stats_query = self.session.query(InstitutionStats)
            if query:
                stats_query = stats_query.filter(
                    InstitutionStats.institution_name.ilike(f"%{query}%")
                )
            total = stats_query.count()
            stats_query = stats_query.order_by(InstitutionStats.author_count.desc())
            if limit is not None:
                stats_query = stats_query.offset(offset).limit(limit)
            stats = stats_query.all()
            if stats:
                return (
                    [
                        {
                            "id": s.institution_id,
                            "name": s.institution_name,
                            "author_count": s.author_count,
                        }
                        for s in stats
                    ],
                    total,
                )

        # Fallback to live aggregation (slower)
        query_builder = (
            self.session.query(
                Author.last_known_institution_id,
                func.max(Author.last_known_institution_name).label("institution_name"),
                func.count(Author.id).label("author_count"),
            )
            .filter(Author.is_canonical == True)
            .filter(Author.last_known_institution_id.isnot(None))
        )

        if query:
            query_builder = query_builder.filter(
                Author.last_known_institution_name.ilike(f"%{query}%")
            )

        results = (
            query_builder
            .group_by(Author.last_known_institution_id)
            .order_by(func.count(Author.id).desc())
            .all()
        )

        total = len(results)
        if limit is not None:
            results = results[offset:offset + limit]

        return (
            [
                {
                    "id": r[0],
                    "name": r[1],
                    "author_count": r[2],
                }
                for r in results
            ],
            total,
        )

    def refresh_institution_stats(self) -> int:
        """Rebuild institution stats table. Returns number of institutions."""
        rows = (
            self.session.query(
                Author.last_known_institution_id,
                func.max(Author.last_known_institution_name).label("institution_name"),
                func.count(Author.id).label("author_count"),
            )
            .filter(Author.is_canonical == True)
            .filter(Author.last_known_institution_id.isnot(None))
            .group_by(Author.last_known_institution_id)
            .all()
        )

        self.session.query(InstitutionStats).delete()
        stats = [
            InstitutionStats(
                institution_id=inst_id,
                institution_name=inst_name,
                author_count=author_count,
            )
            for inst_id, inst_name, author_count in rows
        ]
        if stats:
            self.session.bulk_save_objects(stats)
        self.session.commit()
        return len(stats)
