"""
Author-related API endpoints.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from config.settings import settings
from src.database.models import get_session, Author
from src.database.repositories import AuthorRepository, CollaborationRepository
from src.analysis.relationship_scorer import RelationshipScorer
from src.api.cache import get_cache, cache_key

logger = logging.getLogger(__name__)

router = APIRouter()


# Pydantic models for API responses

class AuthorIdInfo(BaseModel):
    """Individual author ID info (for merged records)."""
    id: str
    orcid: Optional[str] = None
    works_count: int = 0


class AuthorResponse(BaseModel):
    """Author response model."""
    id: str
    display_name: str
    orcid: Optional[str] = None
    works_count: int = 0
    cited_by_count: int = 0
    last_known_institution_id: Optional[str] = None
    last_known_institution_name: Optional[str] = None
    is_canonical: bool = True
    alias_ids: Optional[list[str]] = None  # Merged author IDs (simple list)
    all_ids: Optional[list[AuthorIdInfo]] = None  # All IDs with their ORCIDs

    class Config:
        from_attributes = True

    @classmethod
    def from_author(cls, author, works_count: int = None, cited_by_count: int = None, all_ids_info: list = None):
        """Create response from Author model with computed stats."""
        import json
        alias_ids = None
        if author.alias_ids:
            try:
                alias_ids = json.loads(author.alias_ids)
            except:
                pass

        return cls(
            id=author.id,
            display_name=author.display_name,
            orcid=author.orcid,
            works_count=works_count if works_count is not None else author.works_count,
            cited_by_count=cited_by_count if cited_by_count is not None else author.cited_by_count,
            last_known_institution_id=author.last_known_institution_id,
            last_known_institution_name=author.last_known_institution_name,
            is_canonical=author.is_canonical if author.is_canonical is not None else True,
            alias_ids=alias_ids,
            all_ids=all_ids_info,
        )


class AuthorSearchResponse(BaseModel):
    """Author search results."""
    results: list[AuthorResponse]
    total: int
    limit: int
    offset: int


class RankedAuthor(BaseModel):
    """Author with ranking info."""
    rank: int
    id: str
    display_name: str
    orcid: Optional[str] = None
    works_count: int
    cited_by_count: int = 0


class InstitutionRankingResponse(BaseModel):
    """Institution author ranking response."""
    institution_id: Optional[str] = None
    institution_name: str
    authors: list[RankedAuthor]
    total: int
    limit: int
    offset: int


class InstitutionInfo(BaseModel):
    """Institution summary info."""
    id: str
    name: str
    author_count: int


class InstitutionsResponse(BaseModel):
    """List of institutions."""
    institutions: list[InstitutionInfo]
    total: int


class RelatedAuthor(BaseModel):
    """Related author with score."""
    id: str
    display_name: str
    score: float
    collaboration_count: Optional[int] = None


class TopRelationsResponse(BaseModel):
    """Top relations response."""
    author_id: str
    author_name: str
    relations: list[RelatedAuthor]
    score_type: str


class NetworkMetrics(BaseModel):
    """Network centrality metrics (computed within institution)."""
    institution_name: Optional[str] = None
    institution_author_count: Optional[int] = None
    degree_centrality: Optional[float] = None
    betweenness_centrality: Optional[float] = None
    closeness_centrality: Optional[float] = None
    pagerank: Optional[float] = None
    eigenvector_centrality: Optional[float] = None
    clustering_coefficient: Optional[float] = None


class NetworkMetricsResponse(BaseModel):
    """Network metrics response."""
    author_id: str
    author_name: str
    metrics: NetworkMetrics


# Dependency for database session
def get_db():
    """Get database session."""
    session = get_session()
    try:
        yield session
    finally:
        session.close()


@router.get("/search", response_model=AuthorSearchResponse)
async def search_authors(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Result offset"),
    include_aliases: bool = Query(False, description="Include non-canonical (alias) records"),
    include_all_ids: bool = Query(False, description="Include detailed info for all merged IDs"),
    db: Session = Depends(get_db),
):
    """
    Search authors by name.

    Performs case-insensitive partial matching on author display names.
    Results are sorted by works count (descending).

    By default, only returns deduplicated (canonical) author records.
    Set include_aliases=true to see all records including duplicates.
    Set include_all_ids=true to get detailed info (ID, ORCID, works) for all merged IDs.
    """
    repo = AuthorRepository(db)
    canonical_only = not include_aliases
    authors, total = repo.search_by_name_with_count(q, limit=limit, offset=offset, canonical_only=canonical_only)

    # Build responses with merged works count
    results = []
    for author in authors:
        works_count = repo.get_merged_works_count(author.id) if author.is_canonical else author.works_count

        # Optionally include all IDs info
        all_ids_info = None
        if include_all_ids and author.is_canonical:
            all_ids_data = repo.get_all_ids_info(author.id)
            all_ids_info = [AuthorIdInfo(**info) for info in all_ids_data]

        results.append(AuthorResponse.from_author(author, works_count=works_count, all_ids_info=all_ids_info))

    return AuthorSearchResponse(
        results=results,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/institutions", response_model=InstitutionsResponse)
async def list_institutions(
    db: Session = Depends(get_db),
):
    """
    List all institutions with author counts.

    Returns institutions sorted by number of authors (descending).
    """
    repo = AuthorRepository(db)
    institutions = repo.get_institutions()

    return InstitutionsResponse(
        institutions=[InstitutionInfo(**inst) for inst in institutions],
        total=len(institutions),
    )


@router.get("/ranking/by-institution", response_model=InstitutionRankingResponse)
async def get_institution_ranking(
    institution_id: Optional[str] = Query(None, description="OpenAlex institution ID"),
    institution_name: Optional[str] = Query(None, description="Institution name (partial match)"),
    limit: int = Query(50, ge=1, le=200, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Result offset"),
    db: Session = Depends(get_db),
):
    """
    Get author ranking by publication count for an institution.

    Query by either institution_id (exact match) or institution_name (partial match).
    Returns authors sorted by works count (descending).
    """
    if not institution_id and not institution_name:
        raise HTTPException(
            status_code=400,
            detail="Either institution_id or institution_name must be provided"
        )

    repo = AuthorRepository(db)

    try:
        results, total = repo.get_top_authors_by_institution(
            institution_id=institution_id,
            institution_name=institution_name,
            limit=limit,
            offset=offset,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not results:
        raise HTTPException(status_code=404, detail="No authors found for this institution")

    # Get institution name from first result
    inst_name = results[0][0].last_known_institution_name if results else institution_name

    authors = [
        RankedAuthor(
            rank=offset + idx + 1,
            id=author.id,
            display_name=author.display_name,
            orcid=author.orcid,
            works_count=works_count,
            cited_by_count=author.cited_by_count or 0,
        )
        for idx, (author, works_count) in enumerate(results)
    ]

    return InstitutionRankingResponse(
        institution_id=institution_id,
        institution_name=inst_name,
        authors=authors,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{author_id}", response_model=AuthorResponse)
async def get_author(
    author_id: str,
    db: Session = Depends(get_db),
):
    """
    Get author details by ID.

    Returns detailed information about a specific author.
    If the ID is an alias (merged), redirects to the canonical record.
    Includes all merged IDs with their individual ORCIDs and works counts.
    """
    repo = AuthorRepository(db)

    # Resolve to canonical ID if this is an alias
    canonical_id = repo.get_canonical_id(author_id)
    author = repo.get_by_id(canonical_id)

    if not author:
        raise HTTPException(status_code=404, detail="Author not found")

    # Get merged works count
    works_count = repo.get_merged_works_count(author.id)

    # Get all IDs info (with ORCIDs and individual works counts)
    all_ids_info = repo.get_all_ids_info(author.id)
    all_ids_response = [AuthorIdInfo(**info) for info in all_ids_info]

    return AuthorResponse.from_author(author, works_count=works_count, all_ids_info=all_ids_response)


@router.get("/{author_id}/top-relations", response_model=TopRelationsResponse)
async def get_top_relations(
    author_id: str,
    k: int = Query(None, ge=1, le=100, description="Number of relations"),
    score_type: str = Query(
        "combined_score",
        description="Score type to sort by",
        pattern="^(combined_score|graphsage_score|weighted_score)$"
    ),
    db: Session = Depends(get_db),
):
    """
    Get top-K related authors for a given author.

    Returns authors with highest relationship scores, computed from:
    - GraphSAGE embedding similarity
    - Weighted collaboration scores
    - Combined score (default)

    Results are cached for 24 hours.
    """
    # Use default from settings if not specified
    if k is None:
        k = settings.api.default_top_k

    # Check cache
    cache = get_cache()
    cache_k = cache_key("top_relations", author_id, k, score_type)

    if cache:
        cached = cache.get(cache_k)
        if cached:
            return TopRelationsResponse(**cached)

    # Get author
    repo = AuthorRepository(db)
    author = repo.get_by_id(author_id)

    if not author:
        raise HTTPException(status_code=404, detail="Author not found")

    # Get relations
    collab_repo = CollaborationRepository(db)
    scorer = RelationshipScorer(session=db)

    relations = scorer.get_top_relations(author_id, k=k, score_type=score_type)

    # Get collaboration counts
    result_relations = []
    for other_id, other_name, score in relations:
        collab = collab_repo.get_collaboration(author_id, other_id)
        collab_count = collab.collaboration_count if collab else None

        result_relations.append(RelatedAuthor(
            id=other_id,
            display_name=other_name,
            score=score or 0.0,
            collaboration_count=collab_count,
        ))

    response = TopRelationsResponse(
        author_id=author_id,
        author_name=author.display_name,
        relations=result_relations,
        score_type=score_type,
    )

    # Cache result
    if cache:
        cache.set(cache_k, response.model_dump(), ex=settings.api.cache_ttl)

    return response


@router.get("/{author_id}/network-metrics", response_model=NetworkMetricsResponse)
async def get_network_metrics(
    author_id: str,
    db: Session = Depends(get_db),
):
    """
    Get network centrality metrics for an author.

    Returns various graph-based metrics including:
    - Degree centrality
    - Betweenness centrality
    - Closeness centrality
    - PageRank
    - Eigenvector centrality
    - Clustering coefficient

    Results are cached for 24 hours.
    """
    # Check cache
    cache = get_cache()
    cache_k = cache_key("network_metrics", author_id)

    if cache:
        cached = cache.get(cache_k)
        if cached:
            return NetworkMetricsResponse(**cached)

    # Get author
    repo = AuthorRepository(db)
    author = repo.get_by_id(author_id)

    if not author:
        raise HTTPException(status_code=404, detail="Author not found")

    # Compute metrics
    scorer = RelationshipScorer(session=db)
    metrics = scorer.compute_centrality_metrics(author_id)

    response = NetworkMetricsResponse(
        author_id=author_id,
        author_name=author.display_name,
        metrics=NetworkMetrics(**metrics),
    )

    # Cache result
    if cache:
        cache.set(cache_k, response.model_dump(), ex=settings.api.cache_ttl)

    return response


@router.get("/{author_id}/collaborators")
async def get_collaborators(
    author_id: str,
    limit: int = Query(50, ge=1, le=200, description="Maximum results"),
    db: Session = Depends(get_db),
):
    """
    Get direct collaborators for an author.

    Returns authors who have co-authored papers with the specified author,
    sorted by collaboration count.
    """
    repo = AuthorRepository(db)
    author = repo.get_by_id(author_id)

    if not author:
        raise HTTPException(status_code=404, detail="Author not found")

    collaborators = repo.get_collaborators(author_id, limit=limit)

    return {
        "author_id": author_id,
        "author_name": author.display_name,
        "collaborators": [
            {
                "id": collab.id,
                "display_name": collab.display_name,
                "collaboration_count": count,
            }
            for collab, count in collaborators
        ],
    }
