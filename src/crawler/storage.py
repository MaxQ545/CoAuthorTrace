"""
Storage abstraction for the crawler.

Defines a ``StorageBackend`` Protocol so the crawler can persist data without
knowing anything about the database layer.  The ``SQLAlchemyStorage``
implementation bridges the protocol to the project's existing repositories.

To use the crawler in a different project, implement ``StorageBackend`` with
your own persistence layer.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protocol (the contract the crawler depends on)
# ---------------------------------------------------------------------------

@runtime_checkable
class StorageBackend(Protocol):
    """Minimal interface the crawler needs from the persistence layer."""

    # ---- works ----
    def work_exists(self, work_id: str) -> bool: ...

    def save_work(self, work_data: dict) -> None: ...

    # ---- authors ----
    def author_exists(self, author_id: str) -> bool: ...

    def save_or_update_author(self, author_data: dict) -> None: ...

    # ---- authorships ----
    def authorship_exists(self, author_id: str, work_id: str) -> bool: ...

    def save_authorship(self, authorship_data: dict) -> None: ...

    # ---- collaborations ----
    def save_or_update_collaboration(
        self,
        author_id_1: str,
        author_id_2: str,
        weight: float,
        publication_date: Optional[datetime],
    ) -> None: ...

    # ---- crawl state (incremental) ----
    def get_crawl_state(self, scope_hash: str) -> Optional[dict]: ...

    def save_crawl_state(self, scope_hash: str, **fields) -> None: ...

    # ---- institution crawl state ----
    def get_institution_crawl_state(self, institution_id: str) -> Optional[dict]: ...

    def save_institution_crawl_state(self, institution_id: str, **fields) -> None: ...

    # ---- work metadata (for collaboration building) ----
    def get_work_publication_date(self, work_id: str) -> Optional[datetime]: ...

    # ---- transaction helpers ----
    def flush(self) -> None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...

    def close(self) -> None: ...


# ---------------------------------------------------------------------------
# SQLAlchemy implementation (bridges to the project's existing DB layer)
# ---------------------------------------------------------------------------

class SQLAlchemyStorage:
    """``StorageBackend`` implementation backed by SQLAlchemy + repositories."""

    def __init__(self, session=None):
        if session is None:
            from src.database.engine import get_session
            session = get_session()
        self.session = session
        self._init_repos()

    def _init_repos(self):
        from src.database.repositories import (
            AuthorRepository,
            WorkRepository,
            CollaborationRepository,
        )
        self.author_repo = AuthorRepository(self.session)
        self.work_repo = WorkRepository(self.session)
        self.collab_repo = CollaborationRepository(self.session)

    # ---- works ----

    def work_exists(self, work_id: str) -> bool:
        return self.work_repo.exists(work_id)

    def save_work(self, work_data: dict) -> None:
        from src.database.models import Work
        if not self.work_repo.exists(work_data["id"]):
            self.session.add(Work(**work_data))

    # ---- authors ----

    def author_exists(self, author_id: str) -> bool:
        return self.author_repo.exists(author_id)

    def save_or_update_author(self, author_data: dict) -> None:
        from src.database.models import Author
        existing = self.author_repo.get_by_id(author_data["id"])
        if not existing:
            self.session.add(Author(**author_data))
        else:
            if author_data.get("orcid"):
                existing.orcid = author_data["orcid"]
            if author_data.get("last_known_institution_id") or author_data.get("last_known_institution_name"):
                existing.last_known_institution_id = author_data.get("last_known_institution_id")
                existing.last_known_institution_name = author_data.get("last_known_institution_name")
            if author_data.get("works_count"):
                existing.works_count = author_data["works_count"]
            if author_data.get("cited_by_count"):
                existing.cited_by_count = author_data["cited_by_count"]

    # ---- authorships ----

    def authorship_exists(self, author_id: str, work_id: str) -> bool:
        from src.database.models import Authorship
        return (
            self.session.query(Authorship)
            .filter(Authorship.author_id == author_id, Authorship.work_id == work_id)
            .first()
        ) is not None

    def save_authorship(self, authorship_data: dict) -> None:
        from src.database.models import Authorship
        self.session.add(Authorship(**authorship_data))

    # ---- collaborations ----

    def save_or_update_collaboration(
        self,
        author_id_1: str,
        author_id_2: str,
        weight: float,
        publication_date: Optional[datetime],
    ) -> None:
        self.collab_repo.create_or_update(author_id_1, author_id_2, weight, publication_date)

    # ---- crawl state ----

    def get_crawl_state(self, scope_hash: str) -> Optional[dict]:
        from src.database.models import CrawlState
        state = (
            self.session.query(CrawlState)
            .filter(CrawlState.scope_hash == scope_hash)
            .first()
        )
        if state is None:
            return None
        return {
            "scope_hash": state.scope_hash,
            "last_cursor": state.last_cursor,
            "last_crawl_date": state.last_crawl_date,
            "works_crawled": state.works_crawled,
            "status": state.status,
            "error_message": state.error_message,
        }

    def save_crawl_state(self, scope_hash: str, **fields) -> None:
        from src.database.models import CrawlState
        state = (
            self.session.query(CrawlState)
            .filter(CrawlState.scope_hash == scope_hash)
            .first()
        )
        if state is None:
            state = CrawlState(scope_hash=scope_hash, status="idle", works_crawled=0)
            self.session.add(state)
            self.session.flush()

        for key, value in fields.items():
            if value is not None and hasattr(state, key):
                setattr(state, key, value)
        state.last_crawl_date = datetime.utcnow()
        self.session.commit()

    # ---- institution crawl state ----

    def get_institution_crawl_state(self, institution_id: str) -> Optional[dict]:
        from src.database.models import InstitutionCrawlState
        state = (
            self.session.query(InstitutionCrawlState)
            .filter(InstitutionCrawlState.institution_id == institution_id)
            .first()
        )
        if state is None:
            return None
        return {
            "institution_id": state.institution_id,
            "institution_name": state.institution_name,
            "last_cursor": state.last_cursor,
            "cursor_valid_until": state.cursor_valid_until,
            "last_publication_date": state.last_publication_date,
            "last_crawl_completed": state.last_crawl_completed,
            "total_works_crawled": state.total_works_crawled,
            "status": state.status,
            "error_message": state.error_message,
        }

    def save_institution_crawl_state(self, institution_id: str, **fields) -> None:
        from src.database.models import InstitutionCrawlState
        state = (
            self.session.query(InstitutionCrawlState)
            .filter(InstitutionCrawlState.institution_id == institution_id)
            .first()
        )
        if state is None:
            state = InstitutionCrawlState(
                institution_id=institution_id,
                institution_name=fields.pop("institution_name", "Unknown"),
                status="idle",
                total_works_crawled=0,
            )
            self.session.add(state)
            self.session.flush()

        completed = fields.pop("completed", False)

        for key, value in fields.items():
            if key == "last_publication_date" and value is not None:
                if state.last_publication_date is None or value > state.last_publication_date:
                    state.last_publication_date = value
            elif value is not None and hasattr(state, key):
                setattr(state, key, value)

        if completed:
            state.last_crawl_completed = datetime.utcnow()
            state.last_cursor = None
            state.cursor_valid_until = None

        self.session.commit()

    # ---- work metadata ----

    def get_work_publication_date(self, work_id: str) -> Optional[datetime]:
        work = self.work_repo.get_by_id(work_id)
        return work.publication_date if work else None

    # ---- transaction ----

    def flush(self) -> None:
        self.session.flush()

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()

    def close(self) -> None:
        self.session.close()
