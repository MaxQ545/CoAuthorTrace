"""
Author-related API endpoints.
"""
import json
import logging
from functools import lru_cache
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from config.settings import settings
from src.database.models import Author, InstitutionStats
from src.database.repositories import AuthorRepository, CollaborationRepository
from src.analysis.relationship_scorer import RelationshipScorer
from src.analysis.research_fields import ResearchFieldsCalculator
from src.api.cache import get_cache, cache_key
from src.api.deps import get_db
from src.api.schemas import (
    AuthorIdInfo,
    InstitutionFrequency,
    ResearchField,
    AuthorResponse,
    AuthorSearchResponse,
    RankedAuthor,
    InstitutionRankingResponse,
    InstitutionInfo,
    InstitutionsResponse,
    RelatedAuthor,
    TopRelationsResponse,
    NetworkMetrics,
    NetworkMetricsResponse,
    CoAuthoredPaper,
    CoAuthoredPapersResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ---- institution catalog helpers ----

@lru_cache()
def _load_institution_catalog() -> dict:
    """Load institution id -> name mapping from crawl_targets.json."""
    path = settings.project_root / "config/crawl_targets.json"
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        logger.warning(f"Failed to load institution catalog from {path}: {exc}")
        return {}

    mapping = {}
    for inst in data.get("institutions", []):
        inst_id = inst.get("id")
        if not inst_id:
            continue
        name = inst.get("name_en") or inst.get("name")
        if name:
            mapping[inst_id] = name
    return mapping


def _resolve_institution_from_catalog(name: str) -> tuple[Optional[str], Optional[str]]:
    """Resolve institution id/name from catalog by exact/partial name match."""
    if not name:
        return None, None

    q = name.strip().lower()
    if not q:
        return None, None

    catalog = _load_institution_catalog()
    exact: list[tuple[str, str]] = []
    partial: list[tuple[str, str]] = []

    for inst_id, inst_name in catalog.items():
        n = (inst_name or "").strip().lower()
        if not n:
            continue
        if n == q:
            exact.append((inst_id, inst_name))
        elif q in n or n in q:
            partial.append((inst_id, inst_name))

    if exact:
        return exact[0]

    if partial:
        partial.sort(key=lambda item: abs(len(item[1]) - len(name)))
        return partial[0]

    return None, None


# ---- helper: build research-field models from Author ORM ----

def _research_fields_from_author(author: Author, limit: int = 3) -> Optional[list[ResearchField]]:
    """Parse cached research_fields JSON on Author into schema objects."""
    rf_data = author.get_research_fields_list()
    if not rf_data:
        return None
    return [ResearchField(**rf) for rf in rf_data[:limit]]


# ---- endpoints ----

@router.get("/search", response_model=AuthorSearchResponse)
async def search_authors(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Result offset"),
    include_aliases: bool = Query(False, description="Include non-canonical (alias) records"),
    include_all_ids: bool = Query(False, description="Include detailed info for all merged IDs"),
    fuzzy: bool = Query(False, description="Enable fuzzy matching (partial match)"),
    db: Session = Depends(get_db),
):
    """
    Search authors by name.

    Performs case-insensitive matching on author display names.
    By default (fuzzy=False), performs exact match (case-insensitive fallback).
    If fuzzy=True, performs partial match (LIKE %q%).
    """
    repo = AuthorRepository(db)
    canonical_only = not include_aliases
    authors_with_counts, total = repo.search_by_name_with_count(
        q, limit=limit, offset=offset, canonical_only=canonical_only, fuzzy=fuzzy
    )

    results = []
    for author, works_count in authors_with_counts:
        cited_by_count = repo._get_merged_cited_by_count_by_year(author.id)

        all_ids_info = None
        if include_all_ids and author.is_canonical:
            all_ids_data = repo.get_all_ids_info(author.id)
            all_ids_info = [AuthorIdInfo(**info) for info in all_ids_data]

        results.append(AuthorResponse.from_author(
            author,
            works_count=works_count,
            cited_by_count=cited_by_count,
            all_ids_info=all_ids_info,
            research_fields=_research_fields_from_author(author, limit=3),
        ))

    return AuthorSearchResponse(
        results=results,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/institutions", response_model=InstitutionsResponse)
async def list_institutions(
    q: Optional[str] = Query(None, description="Institution name keyword"),
    limit: Optional[int] = Query(None, ge=1, le=5000, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Result offset"),
    refresh: bool = Query(False, description="Refresh cached institution stats"),
    db: Session = Depends(get_db),
):
    """List all institutions with author counts."""
    repo = AuthorRepository(db)
    if refresh:
        repo.refresh_institution_stats()
    institutions, total = repo.get_institutions(
        limit=limit, offset=offset, query=q, use_cache=True,
    )
    return InstitutionsResponse(
        institutions=[InstitutionInfo(**inst) for inst in institutions],
        total=total,
    )


@router.get("/ranking/by-institution", response_model=InstitutionRankingResponse)
async def get_institution_ranking(
    institution_id: Optional[str] = Query(None, description="OpenAlex institution ID"),
    institution_name: Optional[str] = Query(None, description="Institution name (partial match)"),
    limit: int = Query(50, ge=1, le=200, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Result offset"),
    from_year: Optional[int] = Query(None, ge=1900, le=2100, description="Start year (inclusive)"),
    to_year: Optional[int] = Query(None, ge=1900, le=2100, description="End year (inclusive)"),
    fast: bool = Query(True, description="Use cached counts for faster ranking"),
    db: Session = Depends(get_db),
):
    """Get author ranking by publication count for an institution."""
    if not institution_id and not institution_name:
        raise HTTPException(
            status_code=400,
            detail="Either institution_id or institution_name must be provided"
        )

    # In fast mode, skip expensive year-filtered aggregation
    if fast and (from_year is not None or to_year is not None):
        from_year = None
        to_year = None

    # Check cache
    cache = get_cache()
    cache_k = cache_key(
        "institution_ranking",
        institution_id or "",
        institution_name or "",
        limit, offset,
        from_year if from_year is not None else "",
        to_year if to_year is not None else "",
        "fast" if fast else "full",
    )
    if cache:
        cached = cache.get(cache_k)
        if cached:
            return InstitutionRankingResponse(**cached)

    repo = AuthorRepository(db)

    requested_name = institution_name
    query_institution_name = institution_name

    if institution_id:
        query_institution_name = None
        if not requested_name:
            requested_name = _load_institution_catalog().get(institution_id)
    elif institution_name:
        resolved_id, resolved_name = _resolve_institution_from_catalog(institution_name)
        if resolved_id:
            institution_id = resolved_id
            query_institution_name = None
            requested_name = resolved_name or requested_name
        else:
            candidate = (
                db.query(InstitutionStats)
                .filter(InstitutionStats.institution_name.ilike(f"%{institution_name}%"))
                .order_by(InstitutionStats.author_count.desc())
                .first()
            )
            if candidate:
                institution_id = candidate.institution_id
                query_institution_name = None
                requested_name = candidate.institution_name or requested_name

    if fast and query_institution_name and not institution_id:
        raise HTTPException(
            status_code=404,
            detail="Institution not found in indexed catalog. "
                   "Please use institution_id or set fast=false.",
        )

    try:
        results, total = repo.get_top_authors_by_institution(
            institution_id=institution_id,
            institution_name=query_institution_name,
            limit=limit, offset=offset,
            from_year=from_year, to_year=to_year,
            fast=fast,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not results:
        raise HTTPException(status_code=404, detail="No authors found for this institution")

    inst_name = requested_name or (results[0][0].last_known_institution_name if results else None)

    authors = []
    for idx, (author, works_count, cited_by_count) in enumerate(results):
        authors.append(RankedAuthor(
            rank=offset + idx + 1,
            id=author.id,
            display_name=author.display_name,
            orcid=author.orcid,
            works_count=works_count,
            cited_by_count=cited_by_count,
            research_fields=_research_fields_from_author(author, limit=2),
        ))

    response = InstitutionRankingResponse(
        institution_id=institution_id,
        institution_name=inst_name,
        authors=authors,
        total=total,
        limit=limit,
        offset=offset,
    )
    if cache:
        cache.set(cache_k, response.model_dump(), ex=settings.api.cache_ttl)
    return response


@router.get("/{author_id}", response_model=AuthorResponse)
async def get_author(
    author_id: str,
    db: Session = Depends(get_db),
):
    """Get author details by ID (resolves aliases to canonical record)."""
    repo = AuthorRepository(db)
    canonical_id = repo.get_canonical_id(author_id)
    author = repo.get_by_id(canonical_id)

    if not author:
        raise HTTPException(status_code=404, detail="Author not found")

    works_count = repo.get_merged_works_count(author.id)
    cited_by_count = repo._get_merged_cited_by_count_by_year(author.id)

    all_ids_info = repo.get_all_ids_info(author.id)
    all_ids_response = [AuthorIdInfo(**info) for info in all_ids_info]

    institution_freqs = repo.get_institution_frequencies(author.id, limit=5)
    primary_institution_name = (
        institution_freqs[0]["name"] if institution_freqs else author.last_known_institution_name
    )
    primary_institution_count = institution_freqs[0]["count"] if institution_freqs else None
    institution_freq_models = [InstitutionFrequency(**item) for item in institution_freqs]

    research_fields_calculator = ResearchFieldsCalculator(db)
    research_fields_data = research_fields_calculator.get_cached_or_compute(author.id, top_k=5)
    research_fields_models = [ResearchField(**rf) for rf in research_fields_data] if research_fields_data else None

    return AuthorResponse.from_author(
        author,
        works_count=works_count,
        cited_by_count=cited_by_count,
        all_ids_info=all_ids_response,
        primary_institution_name=primary_institution_name,
        primary_institution_count=primary_institution_count,
        top_institutions=institution_freq_models,
        research_fields=research_fields_models,
    )


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
    """Get top-K related authors for a given author."""
    if k is None:
        k = settings.api.default_top_k

    cache = get_cache()
    cache_k = cache_key("top_relations", author_id, k, score_type)
    if cache:
        cached = cache.get(cache_k)
        if cached:
            return TopRelationsResponse(**cached)

    repo = AuthorRepository(db)
    author = repo.get_by_id(author_id)
    if not author:
        raise HTTPException(status_code=404, detail="Author not found")

    collab_repo = CollaborationRepository(db)
    scorer = RelationshipScorer(session=db)
    relations = scorer.get_top_relations(author_id, k=k, score_type=score_type)

    # Batch-fetch collaboration counts to avoid N+1
    other_ids = [other_id for other_id, _, _ in relations]
    collab_counts = collab_repo.get_collaboration_counts_batch(author_id, other_ids)

    result_relations = []
    for other_id, other_name, score in relations:
        result_relations.append(RelatedAuthor(
            id=other_id,
            display_name=other_name,
            score=score or 0.0,
            collaboration_count=collab_counts.get(other_id),
        ))

    response = TopRelationsResponse(
        author_id=author_id,
        author_name=author.display_name,
        relations=result_relations,
        score_type=score_type,
    )
    if cache:
        cache.set(cache_k, response.model_dump(), ex=settings.api.cache_ttl)
    return response


@router.get("/{author_id}/network-metrics", response_model=NetworkMetricsResponse)
async def get_network_metrics(
    author_id: str,
    full: bool = Query(True, description="Compute full graph metrics (slower)"),
    db: Session = Depends(get_db),
):
    """Get network centrality metrics for an author."""
    cache = get_cache()
    cache_k = cache_key("network_metrics", author_id, "full" if full else "fast")
    if cache:
        cached = cache.get(cache_k)
        if cached:
            return NetworkMetricsResponse(**cached)

    repo = AuthorRepository(db)
    author = repo.get_by_id(author_id)
    if not author:
        raise HTTPException(status_code=404, detail="Author not found")

    scorer = RelationshipScorer(session=db)
    metrics = scorer.compute_centrality_metrics(author_id, full=full)

    response = NetworkMetricsResponse(
        author_id=author_id,
        author_name=author.display_name,
        metrics=NetworkMetrics(**metrics),
    )
    if cache:
        cache.set(cache_k, response.model_dump(), ex=settings.api.cache_ttl)
    return response


@router.get("/{author_id}/collaborators")
async def get_collaborators(
    author_id: str,
    limit: int = Query(50, ge=1, le=200, description="Maximum results"),
    from_year: Optional[int] = Query(None, ge=1900, le=2100, description="Start year (inclusive)"),
    to_year: Optional[int] = Query(None, ge=1900, le=2100, description="End year (inclusive)"),
    db: Session = Depends(get_db),
):
    """Get direct collaborators for an author, sorted by collaboration count."""
    repo = AuthorRepository(db)
    author = repo.get_by_id(author_id)
    if not author:
        raise HTTPException(status_code=404, detail="Author not found")

    collaborators = repo.get_collaborators(
        author_id, limit=limit, from_year=from_year, to_year=to_year
    )

    # Batch-fetch primary institutions to avoid N+1
    collab_ids = [collab.id for collab, _ in collaborators]
    institution_map = repo.get_primary_institutions_batch(collab_ids)

    collaborators_list = []
    for collab, count in collaborators:
        primary_inst = institution_map.get(collab.id, collab.last_known_institution_name)
        collaborators_list.append({
            "id": collab.id,
            "display_name": collab.display_name,
            "collaboration_count": count,
            "primary_institution_name": primary_inst,
            "last_known_institution_name": collab.last_known_institution_name,
        })

    return {
        "author_id": author_id,
        "author_name": author.display_name,
        "collaborators": collaborators_list,
    }


@router.get("/{author_id}/co-authored-papers/{collaborator_id}", response_model=CoAuthoredPapersResponse)
async def get_co_authored_papers(
    author_id: str,
    collaborator_id: str,
    limit: int = Query(20, ge=1, le=100, description="Page size"),
    offset: int = Query(0, ge=0, description="Offset"),
    sort_by: str = Query(
        "publication_date",
        description="Sort field",
        pattern="^(publication_date|cited_by_count|title)$"
    ),
    sort_order: str = Query("desc", description="Sort direction", pattern="^(asc|desc)$"),
    from_year: Optional[int] = Query(None, ge=1900, le=2100, description="Start year (inclusive)"),
    to_year: Optional[int] = Query(None, ge=1900, le=2100, description="End year (inclusive)"),
    db: Session = Depends(get_db),
):
    """Get co-authored papers between two authors (handles merged aliases)."""
    repo = AuthorRepository(db)
    collab_repo = CollaborationRepository(db)

    author = repo.get_by_id(author_id)
    if not author:
        raise HTTPException(status_code=404, detail="Author not found")

    collaborator = repo.get_by_id(collaborator_id)
    if not collaborator:
        raise HTTPException(status_code=404, detail="Collaborator not found")

    works, total = collab_repo.get_co_authored_works(
        author_id_1=author_id,
        author_id_2=collaborator_id,
        limit=limit, offset=offset,
        sort_by=sort_by, sort_order=sort_order,
        from_year=from_year, to_year=to_year,
    )

    papers = [
        CoAuthoredPaper(
            id=work.id,
            title=work.title,
            doi=work.doi,
            publication_date=work.publication_date.strftime("%Y-%m-%d") if work.publication_date else None,
            publication_year=work.publication_year,
            source_name=work.source_name,
            cited_by_count=work.cited_by_count or 0,
            is_open_access=work.is_open_access or False,
        )
        for work in works
    ]

    return CoAuthoredPapersResponse(
        author_id=author_id,
        author_name=author.display_name,
        collaborator_id=collaborator_id,
        collaborator_name=collaborator.display_name,
        papers=papers,
        total=total,
        limit=limit,
        offset=offset,
    )
