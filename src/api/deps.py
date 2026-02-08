"""
Shared FastAPI dependencies.
"""
from src.database.models import get_session


def get_db():
    """Get database session dependency for FastAPI routes."""
    session = get_session()
    try:
        yield session
    finally:
        session.close()
