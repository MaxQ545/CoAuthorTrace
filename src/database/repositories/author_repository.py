"""Repository for Author operations."""
from functools import lru_cache
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_, func, select

from src.database.models import Author, Authorship, Collaboration, RelationshipScore, Work

# Simple in-memory cache for search count (cleared on restart)
_search_count_cache = {}


class AuthorRepository:
    """Repository for Author CRUD operations."""

    def __init__(self, session: Session):
        self.session = session

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
        """Search authors by name (case-insensitive partial match).

        Args:
            canonical_only: If True, only return deduplicated main records
        """
        pattern = f"%{query}%"

        base_query = self.session.query(Author).filter(Author.display_name.ilike(pattern))

        # Only return canonical (deduplicated) records by default
        if canonical_only:
            base_query = base_query.filter(Author.is_canonical == True)

        results = (
            base_query
            .order_by(Author.works_count.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        return results

    def search_by_name_with_count(
        self,
        query: str,
        limit: int = 20,
        offset: int = 0,
        canonical_only: bool = True
    ) -> tuple[list[Author], int]:
        """Search authors by name with total count.

        Args:
            canonical_only: If True, only return deduplicated main records
        """
        pattern = f"%{query}%"

        # Build base filter
        base_filter = Author.display_name.ilike(pattern)
        if canonical_only:
            base_filter = (Author.display_name.ilike(pattern)) & (Author.is_canonical == True)

        # Get total count (with simple caching)
        cache_key = f"search_count:{query.lower()}:{'canonical' if canonical_only else 'all'}"
        if cache_key in _search_count_cache:
            total = _search_count_cache[cache_key]
        else:
            count_query = self.session.query(func.count(Author.id)).filter(base_filter)
            total = count_query.scalar() or 0
            # Cache for this session (simple dict cache)
            if len(_search_count_cache) < 1000:  # Limit cache size
                _search_count_cache[cache_key] = total

        # Get results
        results = (
            self.session.query(Author)
            .filter(base_filter)
            .order_by(Author.works_count.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

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
        to_year: Optional[int] = None
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
        import json

        # Build base query for canonical authors only
        base_query = self.session.query(Author).filter(Author.is_canonical == True)

        if institution_id:
            base_query = base_query.filter(Author.last_known_institution_id == institution_id)
        elif institution_name:
            base_query = base_query.filter(
                Author.last_known_institution_name.ilike(f"%{institution_name}%")
            )
        else:
            raise ValueError("Either institution_id or institution_name must be provided")

        # Get total count
        total = base_query.count()

        # If year filter is specified, we need to count works dynamically
        if from_year is not None or to_year is not None:
            # Get all authors for this institution
            authors = base_query.all()

            # Calculate works count and cited_by_count for each author within year range
            results = []
            for author in authors:
                works_count = self._get_merged_works_count_by_year(
                    author.id, from_year, to_year
                )
                if works_count > 0:  # Only include authors with works in range
                    cited_by_count = self._get_merged_cited_by_count_by_year(
                        author.id, from_year, to_year
                    )
                    results.append((author, works_count, cited_by_count))

            # Sort by works count
            results.sort(key=lambda x: x[1], reverse=True)

            # Apply pagination
            return results[offset:offset + limit], len(results)

        # Original logic without year filter
        authors = (
            base_query
            .order_by(Author.works_count.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        # Calculate merged works count and cited_by_count for each author
        results = []
        for author in authors:
            merged_count = self.get_merged_works_count(author.id)
            cited_by_count = self._get_merged_cited_by_count_by_year(author.id)
            results.append((author, merged_count, cited_by_count))

        # Re-sort by merged count (in case merging changes the order)
        results.sort(key=lambda x: x[1], reverse=True)

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

    def get_institutions(self) -> list[dict]:
        """Get list of all institutions with author counts."""
        results = (
            self.session.query(
                Author.last_known_institution_id,
                Author.last_known_institution_name,
                func.count(Author.id).label('author_count')
            )
            .filter(Author.is_canonical == True)
            .filter(Author.last_known_institution_id.isnot(None))
            .group_by(Author.last_known_institution_id, Author.last_known_institution_name)
            .order_by(func.count(Author.id).desc())
            .all()
        )

        return [
            {
                "id": r[0],
                "name": r[1],
                "author_count": r[2]
            }
            for r in results
        ]
