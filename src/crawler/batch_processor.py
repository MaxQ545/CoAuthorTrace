"""
Shared batch processing logic for crawlers.

Extracted from incremental_crawler and multi_institution_crawler to
eliminate code duplication.
"""
import logging

from sqlalchemy.orm import Session

from src.database.models import Author, Work, Authorship
from src.database.repositories import (
    AuthorRepository,
    WorkRepository,
    CollaborationRepository,
)
from src.analysis.weight_calculator import WeightCalculator

logger = logging.getLogger(__name__)


def process_batch(
    session: Session,
    author_repo: AuthorRepository,
    work_repo: WorkRepository,
    collab_repo: CollaborationRepository,
    works: list[dict],
    authors: list[dict],
    authorships: list[dict],
    weight_calculator: WeightCalculator,
) -> tuple[int, int, int]:
    """
    Process a batch of works, authors, and authorships.

    Inserts authors, works, and authorships into the database, then builds
    collaboration edges between co-authors.

    Returns:
        Tuple of (new_authors, new_authorships, new_collaborations)
    """
    new_authors = 0
    new_authorships = 0
    new_collaborations = 0

    # Insert authors
    for author_data in authors:
        author_id = author_data["id"]
        existing = author_repo.get_by_id(author_id)
        if not existing:
            author = Author(**author_data)
            session.add(author)
            new_authors += 1
        else:
            # Refresh core fields when new data is present
            if author_data.get("orcid"):
                existing.orcid = author_data["orcid"]
            if author_data.get("last_known_institution_id") or author_data.get("last_known_institution_name"):
                existing.last_known_institution_id = author_data.get("last_known_institution_id")
                existing.last_known_institution_name = author_data.get("last_known_institution_name")
            if author_data.get("works_count"):
                existing.works_count = author_data["works_count"]
            if author_data.get("cited_by_count"):
                existing.cited_by_count = author_data["cited_by_count"]

    session.flush()

    # Insert works (skip duplicates)
    for work_data in works:
        if not work_repo.exists(work_data["id"]):
            work = Work(**work_data)
            session.add(work)

    try:
        session.flush()
    except Exception as e:
        session.rollback()
        logger.warning(f"Batch flush error, retrying one by one: {e}")
        for work_data in works:
            try:
                if not work_repo.exists(work_data["id"]):
                    work = Work(**work_data)
                    session.add(work)
                    session.flush()
            except Exception:
                session.rollback()

    # Insert authorships and build collaborations
    work_authorships: dict[str, list[dict]] = {}

    for auth_data in authorships:
        existing = (
            session.query(Authorship)
            .filter(
                Authorship.author_id == auth_data["author_id"],
                Authorship.work_id == auth_data["work_id"],
            )
            .first()
        )

        if not existing:
            authorship = Authorship(**auth_data)
            session.add(authorship)
            new_authorships += 1

            work_id = auth_data["work_id"]
            if work_id not in work_authorships:
                work_authorships[work_id] = []
            work_authorships[work_id].append(auth_data)

    session.flush()

    # Build collaboration edges
    for work_id, work_auths in work_authorships.items():
        if len(work_auths) < 2:
            continue

        work = work_repo.get_by_id(work_id)
        pub_date = work.publication_date if work else None

        for i, auth1 in enumerate(work_auths):
            for auth2 in work_auths[i + 1:]:
                weight = weight_calculator.calculate_weight(
                    position_1=auth1["author_position"],
                    position_2=auth2["author_position"],
                    is_corresponding_1=auth1.get("is_corresponding", False),
                    is_corresponding_2=auth2.get("is_corresponding", False),
                    total_authors=len(work_auths),
                    publication_date=pub_date,
                )
                collab_repo.create_or_update(
                    auth1["author_id"],
                    auth2["author_id"],
                    weight,
                    pub_date,
                )
                new_collaborations += 1

    session.commit()

    return new_authors, new_authorships, new_collaborations
