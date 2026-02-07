"""
Pydantic response / request models for the API.

Centralised here so routers stay focused on endpoint logic.
"""
from typing import Optional

from pydantic import BaseModel


# ---- Author ----

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
    alias_ids: Optional[list[str]] = None
    all_ids: Optional[list[AuthorIdInfo]] = None

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
            alias_ids=author.get_alias_ids() or None,
            all_ids=all_ids_info,
        )


class AuthorSearchResponse(BaseModel):
    """Author search results."""
    results: list[AuthorResponse]
    total: int
    limit: int
    offset: int


# ---- Ranking ----

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


# ---- Relations / Network ----

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


# ---- Co-authored papers ----

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


# ---- System ----

class DatabaseStats(BaseModel):
    """Database statistics."""
    total_authors: int
    total_works: int
    total_collaborations: int
    total_relationship_scores: int


class CrawlStatus(BaseModel):
    """Crawl status."""
    status: str
    last_crawl_date: Optional[str] = None
    works_crawled: int = 0
    error_message: Optional[str] = None


class SystemStatus(BaseModel):
    """System status response."""
    status: str
    version: str
    database: DatabaseStats
    crawl: CrawlStatus
    redis_enabled: bool
    redis_connected: bool


class AnalysisStatus(BaseModel):
    """Analysis status."""
    last_run: Optional[str] = None
    model_version: Optional[str] = None
    scores_computed: int = 0
