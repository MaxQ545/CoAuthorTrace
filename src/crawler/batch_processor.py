"""
Shared batch processor for crawler work/author/authorship ingestion.
"""
import logging
from typing import Optional

from sqlalchemy import tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from src.database.models import Author, Work, Authorship
from src.database.repositories import (
    AuthorRepository,
    WorkRepository,
    CollaborationRepository,
)
from src.analysis.weight_calculator import WeightCalculator

logger = logging.getLogger(__name__)


class BatchProcessor:
    """
    Processes a batch of works, authors, and authorships into the database.

    Handles:
    - Batch existence checks for works and authorships
    - Author upsert with field refresh
    - Duplicate key handling with rollback+retry for individual records
    - Collaboration edge building with weight calculation
    - Stats tracking
    """

    def __init__(
        self,
        session: Session,
        author_repo: AuthorRepository,
        work_repo: WorkRepository,
        collab_repo: CollaborationRepository,
        weight_calculator: WeightCalculator,
    ):
        self.session = session
        self.author_repo = author_repo
        self.work_repo = work_repo
        self.collab_repo = collab_repo
        self.weight_calculator = weight_calculator

    async def process(
        self,
        works: list[dict],
        authors: list[dict],
        authorships: list[dict],
    ) -> tuple[int, int, int]:
        """
        Process a batch of works, authors, and authorships.

        Returns:
            Tuple of (new_authors, new_authorships, new_collaborations)
        """
        new_authors = 0
        new_authorships = 0
        new_collaborations = 0

        # Insert authors
        for author_data in authors:
            author_id = author_data["id"]
            existing = self.author_repo.get_by_id(author_id)
            if not existing:
                author = Author(**author_data)
                self.session.add(author)
                new_authors += 1
            else:
                # Refresh core fields when new data is present
                if author_data.get("orcid"):
                    existing.orcid = author_data["orcid"]
                if author_data.get("last_known_institution_id") or author_data.get("last_known_institution_name"):
                    existing.last_known_institution_id = author_data.get("last_known_institution_id")
                    existing.last_known_institution_name = author_data.get("last_known_institution_name")
                # Update stats if available
                if author_data.get("works_count"):
                    existing.works_count = author_data["works_count"]
                if author_data.get("cited_by_count"):
                    existing.cited_by_count = author_data["cited_by_count"]

        self.session.flush()

        # Batch check which works already exist
        work_ids = [w["id"] for w in works]
        existing_work_ids = self.work_repo.exists_batch(work_ids)

        # Insert works (skip duplicates)
        new_works = [w for w in works if w["id"] not in existing_work_ids]
        for work_data in new_works:
            work = Work(**work_data)
            self.session.add(work)

        try:
            self.session.flush()
        except Exception as e:
            # Handle any remaining duplicates (race condition)
            self.session.rollback()
            logger.warning(f"Batch flush error, retrying one by one: {e}")
            for work_data in new_works:
                try:
                    if not self.work_repo.exists(work_data["id"]):
                        work = Work(**work_data)
                        self.session.add(work)
                        self.session.flush()
                except Exception:
                    self.session.rollback()

        # Batch check which authorships already exist (performance optimization)
        pairs_to_check = [
            (ad["author_id"], ad["work_id"]) for ad in authorships
        ]
        if pairs_to_check:
            existing_pairs: set[tuple[str, str]] = set()
            chunk_size = 500
            for i in range(0, len(pairs_to_check), chunk_size):
                chunk = pairs_to_check[i:i + chunk_size]
                rows = (
                    self.session.query(Authorship.author_id, Authorship.work_id)
                    .filter(
                        tuple_(Authorship.author_id, Authorship.work_id).in_(chunk)
                    )
                    .all()
                )
                existing_pairs.update((r.author_id, r.work_id) for r in rows)
        else:
            existing_pairs = set()

        # Filter to new authorships only, deduplicate within batch
        work_authorships: dict[str, list[dict]] = {}  # work_id -> list of authorships
        new_auth_records = []
        seen_pairs: set[tuple[str, str]] = set()

        for auth_data in authorships:
            pair = (auth_data["author_id"], auth_data["work_id"])
            if pair in existing_pairs or pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            new_auth_records.append(auth_data)

            # Group by work for collaboration building
            work_id = auth_data["work_id"]
            if work_id not in work_authorships:
                work_authorships[work_id] = []
            work_authorships[work_id].append(auth_data)

        # Bulk insert authorships with ON CONFLICT DO NOTHING
        # This safely handles any duplicates the existence check missed
        if new_auth_records:
            insert_chunk_size = 500
            for i in range(0, len(new_auth_records), insert_chunk_size):
                chunk = new_auth_records[i:i + insert_chunk_size]
                values = [
                    {
                        "author_id": r["author_id"],
                        "work_id": r["work_id"],
                        "author_position": r["author_position"],
                        "is_corresponding": r.get("is_corresponding", False),
                        "raw_author_name": r.get("raw_author_name"),
                        "raw_affiliation": r.get("raw_affiliation"),
                    }
                    for r in chunk
                ]
                stmt = (
                    pg_insert(Authorship)
                    .values(values)
                    .on_conflict_do_nothing(
                        index_elements=["author_id", "work_id"]
                    )
                )
                result = self.session.execute(stmt)
                new_authorships += result.rowcount

            self.session.flush()

        # Build collaboration edges
        for work_id, work_auths in work_authorships.items():
            if len(work_auths) < 2:
                continue

            # Get publication date
            work = self.work_repo.get_by_id(work_id)
            pub_date = work.publication_date if work else None

            # Create edges between all author pairs
            for i, auth1 in enumerate(work_auths):
                for auth2 in work_auths[i + 1:]:
                    weight = self.weight_calculator.calculate_weight(
                        position_1=auth1["author_position"],
                        position_2=auth2["author_position"],
                        is_corresponding_1=auth1.get("is_corresponding", False),
                        is_corresponding_2=auth2.get("is_corresponding", False),
                        total_authors=len(work_auths),
                        publication_date=pub_date,
                    )
                    self.collab_repo.create_or_update(
                        auth1["author_id"],
                        auth2["author_id"],
                        weight,
                        pub_date,
                    )
                    new_collaborations += 1

        self.session.commit()

        return new_authors, new_authorships, new_collaborations
