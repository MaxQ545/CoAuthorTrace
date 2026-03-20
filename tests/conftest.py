"""Shared test fixtures."""
import os

import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app
from src.database.models import init_database, get_session, get_engine, Base
import src.database.models as _models

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://coauthor:coauthor@localhost:5432/coauthor_test",
)


@pytest.fixture(scope="function")
def db_session():
    """Provide a clean database session per test for isolation."""
    os.environ["COAUTHOR_DATABASE__POSTGRES_URL"] = TEST_DATABASE_URL
    os.environ["COAUTHOR_DATABASE__REDIS_ENABLED"] = "false"

    _models._engine = None
    _models._SessionLocal = None

    engine = init_database()
    session = get_session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        _models._engine = None
        _models._SessionLocal = None


@pytest.fixture(scope="function")
def test_client():
    """Create a TestClient with a test database per test."""
    os.environ["COAUTHOR_DATABASE__POSTGRES_URL"] = TEST_DATABASE_URL
    os.environ["COAUTHOR_DATABASE__REDIS_ENABLED"] = "false"

    _models._engine = None
    _models._SessionLocal = None

    engine = init_database()
    app = create_app()

    with TestClient(app) as client:
        yield client

    Base.metadata.drop_all(engine)
    _models._engine = None
    _models._SessionLocal = None
