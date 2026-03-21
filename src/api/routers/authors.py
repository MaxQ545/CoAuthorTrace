"""
Author-related API endpoints.
"""
import logging
import json
from functools import lru_cache
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from fastapi.responses import Response as FastAPIResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from config.settings import settings
from src.database.models import Author, InstitutionStats
from src.database.repositories import AuthorRepository, CollaborationRepository
from src.analysis.relationship_scorer import RelationshipScorer
from src.analysis.research_fields import ResearchFieldsCalculator
from src.api.cache import get_cache, cache_key

logger = logging.getLogger(__name__)

router = APIRouter()


def _escape_like(value: str) -> str:
    """Escape special characters for SQL LIKE/ILIKE patterns."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

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

# Pydantic models for API responses

class AuthorIdInfo(BaseModel):
    """Individual author ID info (for merged records)."""
    id: str
    orcid: Optional[str] = None
    works_count: int = 0


class InstitutionFrequency(BaseModel):
    """Institution frequency for an author."""
    name: str
    count: int


class ResearchField(BaseModel):
    """Research field for an author."""
    id: str
    name: str
    score: float
    count: int


class AuthorResponse(BaseModel):
    """Author response model."""
    id: str
    display_name: str
    orcid: Optional[str] = None
    works_count: int = 0
    cited_by_count: int = 0
    last_known_institution_id: Optional[str] = None
    last_known_institution_name: Optional[str] = None
    primary_institution_name: Optional[str] = None
    primary_institution_count: Optional[int] = None
    top_institutions: Optional[list[InstitutionFrequency]] = None
    research_fields: Optional[list[ResearchField]] = None
    is_canonical: bool = True
    alias_ids: Optional[list[str]] = None  # Merged author IDs (simple list)
    all_ids: Optional[list[AuthorIdInfo]] = None  # All IDs with their ORCIDs

    class Config:
        from_attributes = True

    @classmethod
    def from_author(
        cls,
        author,
        works_count: int = None,
        cited_by_count: int = None,
        all_ids_info: list = None,
        primary_institution_name: Optional[str] = None,
        primary_institution_count: Optional[int] = None,
        top_institutions: Optional[list] = None,
        research_fields: Optional[list] = None,
    ):
        """Create response from Author model with computed stats."""
        import json
        alias_ids = None
        if author.alias_ids:
            try:
                alias_ids = json.loads(author.alias_ids)
            except Exception:
                pass

        return cls(
            id=author.id,
            display_name=author.display_name,
            orcid=author.orcid,
            works_count=works_count if works_count is not None else author.works_count,
            cited_by_count=cited_by_count if cited_by_count is not None else author.cited_by_count,
            last_known_institution_id=author.last_known_institution_id,
            last_known_institution_name=author.last_known_institution_name,
            primary_institution_name=primary_institution_name,
            primary_institution_count=primary_institution_count,
            top_institutions=top_institutions,
            research_fields=research_fields,
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
    research_fields: Optional[list[ResearchField]] = None


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


class CoAuthoredPaper(BaseModel):
    """Co-authored paper information."""
    id: str
    title: str
    doi: Optional[str] = None
    publication_date: Optional[str] = None
    publication_year: Optional[int] = None
    source_name: Optional[str] = None
    cited_by_count: int = 0
    is_open_access: bool = False


class CoAuthoredPapersResponse(BaseModel):
    """Co-authored papers response."""
    author_id: str
    author_name: str
    collaborator_id: str
    collaborator_name: str
    papers: list[CoAuthoredPaper]
    total: int
    limit: int
    offset: int


# Database session dependency (shared)
from src.api.deps import get_db


@router.get("/search", response_model=AuthorSearchResponse)
async def search_authors(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Result offset"),
    include_aliases: bool = Query(False, description="Include non-canonical (alias) records"),
    include_all_ids: bool = Query(False, description="Include detailed info for all merged IDs"),
    fuzzy: bool = Query(False, description="Enable fuzzy matching (partial match)"),
    institution: Optional[str] = Query(None, description="Filter by institution name (partial match)"),
    db: Session = Depends(get_db),
):
    """
    Search authors by name.

    Performs case-insensitive matching on author display names.
    By default (fuzzy=False), performs exact match (case-insensitive fallback).
    If fuzzy=True, performs partial match (LIKE %q%).

    Results are sorted by works count (descending).

    By default, only returns deduplicated (canonical) author records.
    Set include_aliases=true to see all records including duplicates.
    Set include_all_ids=true to get detailed info (ID, ORCID, works) for all merged IDs.
    Optionally filter by institution name (partial match).
    """
    repo = AuthorRepository(db)
    canonical_only = not include_aliases
    authors_with_counts, total = repo.search_by_name_with_count(
        q, limit=limit, offset=offset, canonical_only=canonical_only, fuzzy=fuzzy,
        institution_filter=institution,
    )

    # Batch fetch cited_by counts — use Author.cited_by_count column when available
    author_ids = [author.id for author, _ in authors_with_counts]

    # Fast path: use pre-computed columns instead of expensive batch queries
    # This avoids the slow batch_get_merged_cited_by_count and
    # batch_get_institution_frequencies queries that dominated search time
    cited_by_map = {}
    institution_map = {}
    all_ids_map = {}

    # Only do expensive batch lookups for small result sets (author detail pages)
    if len(author_ids) <= 5 and not fuzzy:
        cited_by_map = repo.batch_get_merged_cited_by_count(author_ids)
        institution_map = repo.batch_get_institution_frequencies(author_ids, limit_per_author=1)
        if include_all_ids:
            canonical_ids = [
                author.id for author, _ in authors_with_counts if author.is_canonical
            ]
            all_ids_map = repo.batch_get_all_ids_info(canonical_ids)

    # Build responses with merged works count
    results = []
    for author, works_count in authors_with_counts:

        # Use batch-fetched cited_by_count, fall back to Author column
        cited_by_count = cited_by_map.get(author.id, author.cited_by_count or 0)

        # Use batch-fetched primary institution
        inst_freqs = institution_map.get(author.id, [])
        primary_institution_name = (
            inst_freqs[0]["name"] if inst_freqs else author.last_known_institution_name
        )
        primary_institution_count = inst_freqs[0]["count"] if inst_freqs else None

        # Use batch-fetched all IDs info
        all_ids_info = None
        if include_all_ids and author.is_canonical:
            all_ids_data = all_ids_map.get(author.id, [])
            all_ids_info = [AuthorIdInfo(**info) for info in all_ids_data]

        # Get research fields from cache (don't compute to keep search fast)
        research_fields_models = None
        if author.research_fields:
            try:
                rf_data = json.loads(author.research_fields)
                research_fields_models = [ResearchField(**rf) for rf in rf_data[:3]]  # Show top 3 in search
            except Exception:
                pass

        results.append(AuthorResponse.from_author(
            author,
            works_count=works_count,
            cited_by_count=cited_by_count,
            primary_institution_name=primary_institution_name,
            primary_institution_count=primary_institution_count,
            all_ids_info=all_ids_info,
            research_fields=research_fields_models
        ))

    return AuthorSearchResponse(
        results=results,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/institutions", response_model=InstitutionsResponse)
async def list_institutions(
    response: FastAPIResponse,
    q: Optional[str] = Query(None, description="Institution name keyword"),
    limit: int = Query(200, ge=1, le=5000, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Result offset"),
    refresh: bool = Query(False, description="Refresh cached institution stats"),
    db: Session = Depends(get_db),
):
    """
    List all institutions with author counts.

    Returns institutions sorted by number of authors (descending).
    """
    response.headers["Cache-Control"] = "public, max-age=3600"

    repo = AuthorRepository(db)
    if refresh:
        repo.refresh_institution_stats()
    institutions, total = repo.get_institutions(
        limit=limit,
        offset=offset,
        query=q,
        use_cache=True,
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
    from_year: Optional[int] = Query(None, ge=1900, le=2100, description="起始年份（包含）"),
    to_year: Optional[int] = Query(None, ge=1900, le=2100, description="结束年份（包含）"),
    fast: bool = Query(True, description="Use cached counts for faster ranking"),
    db: Session = Depends(get_db),
):
    """
    Get author ranking by publication count for an institution.

    Query by either institution_id (exact match) or institution_name (partial match).
    Returns authors sorted by works count (descending).

    Optionally filter by publication year range using from_year and to_year.
    """
    if not institution_id and not institution_name:
        raise HTTPException(
            status_code=400,
            detail="Either institution_id or institution_name must be provided"
        )

    # Year-filtered ranking without pre-aggregations is expensive on large datasets.
    # In fast mode, keep endpoint responsive by using all-time cached counters.
    if fast and (from_year is not None or to_year is not None):
        from_year = None
        to_year = None

    # Cache by full query tuple to avoid expensive ranking recomputation.
    cache = get_cache()
    cache_k = cache_key(
        "institution_ranking",
        institution_id or "",
        institution_name or "",
        limit,
        offset,
        from_year if from_year is not None else "",
        to_year if to_year is not None else "",
        "fast" if fast else "full",
    )
    if cache:
        cached = cache.get(cache_k)
        if cached:
            return InstitutionRankingResponse(**cached)

    repo = AuthorRepository(db)

    # Prefer institution_id path whenever possible. It's significantly faster
    # than affiliation name scan on large datasets.
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
            # Fallback: query indexed InstitutionStats only (no heavy live aggregation).
            candidate = (
                db.query(InstitutionStats)
                .filter(InstitutionStats.institution_name.ilike(f"%{_escape_like(institution_name)}%"))
                .order_by(InstitutionStats.author_count.desc())
                .first()
            )
            if candidate:
                institution_id = candidate.institution_id
                query_institution_name = None
                requested_name = candidate.institution_name or requested_name

    # Avoid expensive full affiliation scan when fast mode is requested.
    if fast and query_institution_name and not institution_id:
        raise HTTPException(
            status_code=404,
            detail=(
                "Institution not found in indexed catalog. "
                "Please use institution_id or set fast=false."
            ),
        )

    try:
        results, total = repo.get_top_authors_by_institution(
            institution_id=institution_id,
            institution_name=query_institution_name,
            limit=limit,
            offset=offset,
            from_year=from_year,
            to_year=to_year,
            fast=fast,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not results:
        raise HTTPException(status_code=404, detail="No authors found for this institution")

    # Prefer requested institution name when available
    inst_name = requested_name or (results[0][0].last_known_institution_name if results else None)

    authors = []
    for idx, (author, works_count, cited_by_count) in enumerate(results):
        # Get research fields from cache (show top 2 in ranking)
        research_fields_models = None
        if author.research_fields:
            try:
                rf_data = json.loads(author.research_fields)
                research_fields_models = [ResearchField(**rf) for rf in rf_data[:2]]
            except Exception:
                pass

        authors.append(RankedAuthor(
            rank=offset + idx + 1,
            id=author.id,
            display_name=author.display_name,
            orcid=author.orcid,
            works_count=works_count,
            cited_by_count=cited_by_count,
            research_fields=research_fields_models,
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
    author_id: str = Path(..., pattern=r"^A\d+$"),
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

    # Get merged cited_by_count (sum of all works' citations)
    cited_by_count = repo._get_merged_cited_by_count_by_year(author.id)

    # Get all IDs info (with ORCIDs and individual works counts)
    all_ids_info = repo.get_all_ids_info(author.id)
    all_ids_response = [AuthorIdInfo(**info) for info in all_ids_info]

    # Compute top institutions from authorship affiliations
    institution_freqs = repo.get_institution_frequencies(author.id, limit=5)
    primary_institution_name = (
        institution_freqs[0]["name"] if institution_freqs else author.last_known_institution_name
    )
    primary_institution_count = institution_freqs[0]["count"] if institution_freqs else None
    institution_freq_models = [InstitutionFrequency(**item) for item in institution_freqs]

    # Get research fields (from cache or compute)
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


@router.get("/{author_id}/publication-timeline")
async def get_publication_timeline(
    author_id: str = Path(..., pattern=r"^A\d+$"),
    from_year: Optional[int] = Query(None, ge=1900, le=2100, description="Start year (inclusive)"),
    to_year: Optional[int] = Query(None, ge=1900, le=2100, description="End year (inclusive)"),
    db: Session = Depends(get_db),
):
    """
    Get per-year publication counts and citation totals for an author.

    Returns a timeline of yearly works_count and cited_by_count,
    useful for rendering publication activity charts.
    """
    repo = AuthorRepository(db)
    timeline = repo.get_publication_timeline(author_id, from_year, to_year)
    return {"author_id": author_id, "timeline": timeline}


@router.get("/{author_id}/top-relations", response_model=TopRelationsResponse)
async def get_top_relations(
    author_id: str = Path(..., pattern=r"^A\d+$"),
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

    # Batch fetch collaboration counts to avoid N+1 queries
    other_ids = [other_id for other_id, _, _ in relations]
    collab_map = collab_repo.batch_get_collaborations(author_id, other_ids)

    result_relations = []
    for other_id, other_name, score in relations:
        collab = collab_map.get(other_id)
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
    author_id: str = Path(..., pattern=r"^A\d+$"),
    full: bool = Query(True, description="Compute full graph metrics (slower)"),
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
    cache_k = cache_key("network_metrics", author_id, "full" if full else "fast")

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
    metrics = scorer.compute_centrality_metrics(author_id, full=full)

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
    author_id: str = Path(..., pattern=r"^A\d+$"),
    limit: int = Query(50, ge=1, le=200, description="Maximum results"),
    from_year: Optional[int] = Query(None, ge=1900, le=2100, description="起始年份（包含）"),
    to_year: Optional[int] = Query(None, ge=1900, le=2100, description="结束年份（包含）"),
    db: Session = Depends(get_db),
):
    """
    Get direct collaborators for an author.

    Returns authors who have co-authored papers with the specified author,
    sorted by collaboration count.

    Optionally filter by publication year range using from_year and to_year.
    """
    repo = AuthorRepository(db)
    author = repo.get_by_id(author_id)

    if not author:
        raise HTTPException(status_code=404, detail="Author not found")

    collaborators = repo.get_collaborators(
        author_id, limit=limit, from_year=from_year, to_year=to_year
    )

    # Batch fetch primary institutions to avoid N+1 queries
    collab_ids = [collab.id for collab, _ in collaborators]
    institution_map = repo.batch_get_institution_frequencies(collab_ids, limit_per_author=1)

    collaborators_with_institution = []
    for collab, count in collaborators:
        inst_freqs = institution_map.get(collab.id, [])
        primary_institution_name = (
            inst_freqs[0]["name"] if inst_freqs else collab.last_known_institution_name
        )
        collaborators_with_institution.append({
            "id": collab.id,
            "display_name": collab.display_name,
            "collaboration_count": count,
            "primary_institution_name": primary_institution_name,
            "last_known_institution_name": collab.last_known_institution_name,
        })

    return {
        "author_id": author_id,
        "author_name": author.display_name,
        "collaborators": collaborators_with_institution,
    }


@router.get("/{author_id}/co-authored-papers/{collaborator_id}", response_model=CoAuthoredPapersResponse)
async def get_co_authored_papers(
    author_id: str = Path(..., pattern=r"^A\d+$"),
    collaborator_id: str = Path(..., pattern=r"^A\d+$"),
    limit: int = Query(20, ge=1, le=100, description="每页数量"),
    offset: int = Query(0, ge=0, description="分页偏移"),
    sort_by: str = Query(
        "publication_date",
        description="排序字段",
        pattern="^(publication_date|cited_by_count|title)$"
    ),
    sort_order: str = Query(
        "desc",
        description="排序方向",
        pattern="^(asc|desc)$"
    ),
    from_year: Optional[int] = Query(None, ge=1900, le=2100, description="起始年份（包含）"),
    to_year: Optional[int] = Query(None, ge=1900, le=2100, description="结束年份（包含）"),
    db: Session = Depends(get_db),
):
    """
    获取两位作者共同合作的论文列表。

    返回指定作者与合作者共同发表的论文，支持分页和排序。
    会自动处理合并作者 (alias_ids) 的情况。

    可通过 from_year 和 to_year 参数过滤指定年份范围内的论文。
    """
    repo = AuthorRepository(db)
    collab_repo = CollaborationRepository(db)

    # 验证两位作者都存在
    author = repo.get_by_id(author_id)
    if not author:
        raise HTTPException(status_code=404, detail="Author not found")

    collaborator = repo.get_by_id(collaborator_id)
    if not collaborator:
        raise HTTPException(status_code=404, detail="Collaborator not found")

    # 获取共同合作的论文
    works, total = collab_repo.get_co_authored_works(
        author_id_1=author_id,
        author_id_2=collaborator_id,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_order=sort_order,
        from_year=from_year,
        to_year=to_year,
    )

    # 构建响应
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
