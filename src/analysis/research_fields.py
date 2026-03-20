"""
Research fields computation from paper concepts.
"""
import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.database.models import Author, Authorship, Work

logger = logging.getLogger(__name__)


class ResearchFieldsCalculator:
    """
    Computes research fields for authors based on their papers' concepts.

    Research fields are aggregated from OpenAlex concepts (level 1-2) across
    all of an author's papers, weighted by concept scores.
    """

    def __init__(self, session: Session):
        self.session = session

    def compute_for_author(
        self,
        author_id: str,
        top_k: int = 5,
        update_cache: bool = True
    ) -> list[dict]:
        """
        Compute research fields for an author from their papers' concepts.

        Args:
            author_id: The author's OpenAlex ID (canonical)
            top_k: Number of top research fields to return
            update_cache: Whether to update the author's cached research_fields

        Returns:
            List of dicts: [{"id", "name", "score", "count"}, ...]
            - id: OpenAlex concept ID
            - name: Concept display name
            - score: Average score across papers
            - count: Number of papers with this concept
        """
        # Get all author IDs (including aliases)
        author = self.session.query(Author).filter(Author.id == author_id).first()
        if not author:
            return []

        author_ids = [author_id]
        if author.alias_ids:
            try:
                author_ids.extend(json.loads(author.alias_ids))
            except Exception:
                pass

        # Query all works with concepts for this author
        works = (
            self.session.query(Work.concepts)
            .join(Authorship, Work.id == Authorship.work_id)
            .filter(Authorship.author_id.in_(author_ids))
            .filter(Work.concepts.isnot(None))
            .all()
        )

        # Aggregate concepts
        concept_stats = defaultdict(lambda: {"total_score": 0.0, "count": 0, "name": ""})

        for (concepts_json,) in works:
            if not concepts_json:
                continue
            try:
                concepts = json.loads(concepts_json)
            except Exception:
                continue

            for concept in concepts:
                concept_id = concept.get("id", "")
                if not concept_id:
                    continue

                stats = concept_stats[concept_id]
                stats["total_score"] += concept.get("score", 0)
                stats["count"] += 1
                stats["name"] = concept.get("display_name", "")

        if not concept_stats:
            return []

        # Calculate average score and combined ranking score
        results = []
        for concept_id, stats in concept_stats.items():
            avg_score = stats["total_score"] / stats["count"] if stats["count"] > 0 else 0
            # Ranking: count * avg_score (papers with concept weighted by score)
            ranking_score = stats["count"] * avg_score
            results.append({
                "id": concept_id,
                "name": stats["name"],
                "score": round(avg_score, 3),
                "count": stats["count"],
                "_ranking": ranking_score,
            })

        # Sort by ranking score and take top_k
        results.sort(key=lambda x: x["_ranking"], reverse=True)
        top_results = results[:top_k]

        # Remove internal ranking field
        for r in top_results:
            del r["_ranking"]

        # Update cache if requested
        if update_cache and top_results:
            author.research_fields = json.dumps(top_results)
            author.research_fields_updated_at = datetime.now(timezone.utc)

        return top_results

    def get_cached_or_compute(
        self,
        author_id: str,
        top_k: int = 5,
        max_age_days: int = 7
    ) -> list[dict]:
        """
        Get research fields from cache if fresh, otherwise compute.

        Args:
            author_id: The author's OpenAlex ID
            top_k: Number of top research fields to return
            max_age_days: Maximum age of cached data in days

        Returns:
            List of research field dicts
        """
        author = self.session.query(Author).filter(Author.id == author_id).first()
        if not author:
            return []

        # Check cache freshness
        if author.research_fields and author.research_fields_updated_at:
            age = datetime.now(timezone.utc) - author.research_fields_updated_at
            if age.days < max_age_days:
                try:
                    cached = json.loads(author.research_fields)
                    return cached[:top_k]
                except Exception:
                    pass

        # Compute and cache
        return self.compute_for_author(author_id, top_k=top_k, update_cache=True)

    def batch_compute(
        self,
        author_ids: list[str],
        top_k: int = 5
    ) -> dict[str, list[dict]]:
        """
        Compute research fields for multiple authors.

        Args:
            author_ids: List of author IDs
            top_k: Number of top research fields per author

        Returns:
            Dict mapping author_id to list of research field dicts
        """
        results = {}
        for author_id in author_ids:
            try:
                fields = self.compute_for_author(author_id, top_k=top_k, update_cache=True)
                results[author_id] = fields
            except Exception as e:
                logger.warning(f"Failed to compute research fields for {author_id}: {e}")
                results[author_id] = []

        return results
