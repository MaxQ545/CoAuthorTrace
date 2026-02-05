"""
Tests for database engine configuration and collaboration repository helpers.
"""
import json
from pathlib import Path

import pytest

from config.settings import settings
from src.database import models
from src.database.models import Author, Work, Authorship
from src.database.repositories import CollaborationRepository


@pytest.fixture
def db_session():
    """Provide an in-memory database session for tests."""
    original_path = settings.database.sqlite_path
    original_engine = models._engine
    original_session = models._SessionLocal

    # settings.database.sqlite_path expects a Path; get_engine converts ":memory:" sentinel to string.
    settings.database.sqlite_path = Path(":memory:")
    models._engine = None
    models._SessionLocal = None
    engine = models.init_database()
    session = models.get_session()

    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        models._engine = original_engine
        models._SessionLocal = original_session
        settings.database.sqlite_path = original_path


def test_get_engine_in_memory(db_session):
    """Ensure in-memory database uses sqlite memory URL."""
    engine = models.get_engine()
    assert str(engine.url) == "sqlite:///:memory:"
    assert db_session.query(Author).count() == 0


def test_co_authored_works_resolves_aliases(db_session):
    """Alias IDs should resolve to canonical author works."""
    canonical = Author(
        id="A1",
        display_name="Author One",
        is_canonical=True,
        alias_ids=json.dumps(["A1_alias"]),
    )
    alias = Author(id="A1_alias", display_name="Author One Alias", is_canonical=False)
    collaborator = Author(id="A2", display_name="Author Two", is_canonical=True)

    work1 = Work(id="W1", title="Work One")
    work2 = Work(id="W2", title="Work Two")

    db_session.add_all([canonical, alias, collaborator, work1, work2])
    db_session.flush()

    db_session.add_all(
        [
            Authorship(author_id="A1_alias", work_id="W1", author_position=0),
            Authorship(author_id="A2", work_id="W1", author_position=1),
            Authorship(author_id="A1", work_id="W2", author_position=0),
            Authorship(author_id="A2", work_id="W2", author_position=1),
        ]
    )
    db_session.commit()

    repo = CollaborationRepository(db_session)
    works, total = repo.get_co_authored_works("A1_alias", "A2")

    assert total == 2
    work_ids = {work.id for work in works}
    assert work_ids == {"W1", "W2"}

    authorship_ids = {
        authorship.author_id
        for authorship in db_session.query(Authorship)
        .filter(Authorship.work_id.in_(work_ids))
        .all()
    }
    assert "A1" in authorship_ids
    assert "A1_alias" in authorship_ids
