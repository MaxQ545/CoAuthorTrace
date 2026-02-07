"""
Shared FastAPI dependencies.

Centralises dependency callables that are reused across routers.
"""
from sqlalchemy.orm import Session

from src.database.engine import get_session


def get_db():
    """Yield a database session, closing it on exit."""
    session = get_session()
    try:
        yield session
    finally:
        session.close()
