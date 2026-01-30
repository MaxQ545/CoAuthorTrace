"""Repository module for data access."""
from .author_repository import AuthorRepository
from .work_repository import WorkRepository
from .collaboration_repository import CollaborationRepository

__all__ = ["AuthorRepository", "WorkRepository", "CollaborationRepository"]
