"""
SQLAlchemy ORM models for Coauthor Tracing System.
"""
from datetime import datetime
from typing import Optional
from contextlib import contextmanager

from sqlalchemy import (
    create_engine,
    Column,
    String,
    Integer,
    Float,
    DateTime,
    Boolean,
    Text,
    ForeignKey,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    relationship,
    sessionmaker,
    Session,
)

from config.settings import settings


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class Author(Base):
    """Author information from OpenAlex."""

    __tablename__ = "authors"

    id = Column(String(50), primary_key=True)  # OpenAlex author ID (e.g., A1234567890)
    display_name = Column(String(500), nullable=False)
    orcid = Column(String(50), nullable=True)
    works_count = Column(Integer, default=0)
    cited_by_count = Column(Integer, default=0)
    last_known_institution_id = Column(String(50), nullable=True)
    last_known_institution_name = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Author deduplication fields
    is_canonical = Column(Boolean, default=True)  # True if this is the primary record
    alias_ids = Column(Text, nullable=True)  # JSON array of merged author IDs

    # Research fields (computed from works' concepts)
    research_fields = Column(Text, nullable=True)  # JSON: [{"id", "name", "score", "count"}]
    research_fields_updated_at = Column(DateTime, nullable=True)

    # Relationships
    authorships = relationship("Authorship", back_populates="author")

    __table_args__ = (
        Index("idx_author_name", "display_name"),
        Index("idx_author_orcid", "orcid"),
        Index("idx_author_institution", "last_known_institution_id"),
        Index("idx_author_canonical", "is_canonical"),
    )


class Work(Base):
    """Published work (paper) from OpenAlex."""

    __tablename__ = "works"

    id = Column(String(50), primary_key=True)  # OpenAlex work ID (e.g., W1234567890)
    doi = Column(String(200), nullable=True)
    title = Column(Text, nullable=False)
    publication_date = Column(DateTime, nullable=True)
    publication_year = Column(Integer, nullable=True)
    type = Column(String(100), nullable=True)  # article, preprint, etc.
    cited_by_count = Column(Integer, default=0)
    source_id = Column(String(50), nullable=True)  # Journal/conference ID
    source_name = Column(String(500), nullable=True)
    is_open_access = Column(Boolean, default=False)
    concepts = Column(Text, nullable=True)  # JSON: [{"id", "display_name", "level", "score"}]
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    authorships = relationship("Authorship", back_populates="work")

    __table_args__ = (
        Index("idx_work_doi", "doi"),
        Index("idx_work_pub_date", "publication_date"),
        Index("idx_work_pub_year", "publication_year"),
        Index("idx_work_source", "source_id"),
    )


class Authorship(Base):
    """Author-Work relationship with position information."""

    __tablename__ = "authorships"

    id = Column(Integer, primary_key=True, autoincrement=True)
    author_id = Column(String(50), ForeignKey("authors.id"), nullable=False)
    work_id = Column(String(50), ForeignKey("works.id"), nullable=False)
    author_position = Column(Integer, nullable=False)  # 0-indexed position
    is_corresponding = Column(Boolean, default=False)
    raw_author_name = Column(String(500), nullable=True)  # Name as appears on paper
    raw_affiliation = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    author = relationship("Author", back_populates="authorships")
    work = relationship("Work", back_populates="authorships")

    __table_args__ = (
        UniqueConstraint("author_id", "work_id", name="uq_authorship"),
        Index("idx_authorship_author", "author_id"),
        Index("idx_authorship_work", "work_id"),
        Index("idx_authorship_position", "author_position"),
    )


class Collaboration(Base):
    """Pre-computed collaboration edges between authors."""

    __tablename__ = "collaborations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    author_id_1 = Column(String(50), ForeignKey("authors.id"), nullable=False)
    author_id_2 = Column(String(50), ForeignKey("authors.id"), nullable=False)
    collaboration_count = Column(Integer, default=1)  # Number of co-authored papers
    total_weight = Column(Float, default=0.0)  # Sum of weighted collaborations
    first_collaboration = Column(DateTime, nullable=True)
    last_collaboration = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    author_1 = relationship("Author", foreign_keys=[author_id_1])
    author_2 = relationship("Author", foreign_keys=[author_id_2])

    __table_args__ = (
        # Ensure author_id_1 < author_id_2 to avoid duplicates
        UniqueConstraint("author_id_1", "author_id_2", name="uq_collaboration"),
        Index("idx_collaboration_author1", "author_id_1"),
        Index("idx_collaboration_author2", "author_id_2"),
        Index("idx_collaboration_weight", "total_weight"),
    )


class RelationshipScore(Base):
    """GNN-computed relationship strength scores."""

    __tablename__ = "relationship_scores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    author_id_1 = Column(String(50), ForeignKey("authors.id"), nullable=False)
    author_id_2 = Column(String(50), ForeignKey("authors.id"), nullable=False)

    # Different score types
    graphsage_score = Column(Float, nullable=True)  # GraphSAGE embedding similarity
    weighted_score = Column(Float, nullable=True)   # Weighted collaboration score
    combined_score = Column(Float, nullable=True)   # Combined final score

    # Metadata
    computed_at = Column(DateTime, default=datetime.utcnow)
    model_version = Column(String(50), nullable=True)

    # Relationships
    author_1 = relationship("Author", foreign_keys=[author_id_1])
    author_2 = relationship("Author", foreign_keys=[author_id_2])

    __table_args__ = (
        UniqueConstraint("author_id_1", "author_id_2", name="uq_relationship_score"),
        Index("idx_relscore_author1", "author_id_1"),
        Index("idx_relscore_author2", "author_id_2"),
        Index("idx_relscore_combined", "combined_score"),
    )


class CrawlState(Base):
    """Tracking state for incremental crawling."""

    __tablename__ = "crawl_state"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scope_hash = Column(String(64), nullable=False)  # Hash of scope config
    last_cursor = Column(String(500), nullable=True)  # OpenAlex cursor for pagination
    last_crawl_date = Column(DateTime, nullable=True)
    works_crawled = Column(Integer, default=0)
    status = Column(String(50), default="idle")  # idle, running, completed, failed
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_crawl_scope", "scope_hash"),
    )


class InstitutionCrawlState(Base):
    """Per-institution crawl state for multi-institution crawling."""

    __tablename__ = "institution_crawl_state"

    id = Column(Integer, primary_key=True, autoincrement=True)
    institution_id = Column(String(50), unique=True, nullable=False)  # e.g., I136199984
    institution_name = Column(String(500), nullable=True)

    # Pagination state (for resumable crawling)
    last_cursor = Column(String(500), nullable=True)
    cursor_valid_until = Column(DateTime, nullable=True)

    # Incremental crawl state
    last_publication_date = Column(String(10), nullable=True)  # Latest paper date (YYYY-MM-DD)
    last_crawl_completed = Column(DateTime, nullable=True)

    # Statistics
    total_works_crawled = Column(Integer, default=0)

    # Status
    status = Column(String(50), default="idle")  # idle/running/completed/failed
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_inst_crawl_institution", "institution_id"),
        Index("idx_inst_crawl_status", "status"),
    )


# Database engine and session management
_engine = None
_SessionLocal = None


def get_engine():
    """Get or create the database engine."""
    global _engine
    if _engine is None:
        db_path = settings.project_root / settings.database.sqlite_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(
            f"sqlite:///{db_path}",
            echo=False,
            connect_args={"check_same_thread": False}
        )
    return _engine


def get_session() -> Session:
    """Get a new database session."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine())
    return _SessionLocal()


@contextmanager
def session_scope():
    """Provide a transactional scope around a series of operations."""
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_database():
    """Initialize the database by creating all tables."""
    engine = get_engine()
    Base.metadata.create_all(engine)
    return engine
