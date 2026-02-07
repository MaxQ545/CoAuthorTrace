"""
Shared batch processing logic for crawlers.

Operates entirely through the ``StorageBackend`` protocol — no direct
dependency on SQLAlchemy, ORM models, or repositories.
"""
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.crawler.storage import StorageBackend
    from src.crawler.weight import WeightCalculator

logger = logging.getLogger(__name__)


def process_batch(
    storage: "StorageBackend",
    weight_calculator: "WeightCalculator",
    works: list[dict],
    authors: list[dict],
    authorships: list[dict],
) -> tuple[int, int, int]:
    """
    Persist a batch of works / authors / authorships and build collaboration
    edges.

    Returns:
        (new_authors, new_authorships, new_collaborations)
    """
    new_authors = 0
    new_authorships = 0
    new_collaborations = 0

    # ---- authors ----
    for author_data in authors:
        if not storage.author_exists(author_data["id"]):
            new_authors += 1
        storage.save_or_update_author(author_data)

    storage.flush()

    # ---- works ----
    for work_data in works:
        try:
            storage.save_work(work_data)
        except Exception:
            pass  # duplicate guard

    try:
        storage.flush()
    except Exception as e:
        storage.rollback()
        logger.warning(f"Batch flush error, retrying one by one: {e}")
        for work_data in works:
            try:
                storage.save_work(work_data)
                storage.flush()
            except Exception:
                storage.rollback()

    # ---- authorships + collaboration edges ----
    work_authorships: dict[str, list[dict]] = {}

    for auth_data in authorships:
        if not storage.authorship_exists(auth_data["author_id"], auth_data["work_id"]):
            storage.save_authorship(auth_data)
            new_authorships += 1

            wid = auth_data["work_id"]
            work_authorships.setdefault(wid, []).append(auth_data)

    storage.flush()

    for work_id, work_auths in work_authorships.items():
        if len(work_auths) < 2:
            continue

        pub_date = storage.get_work_publication_date(work_id)

        for i, a1 in enumerate(work_auths):
            for a2 in work_auths[i + 1:]:
                weight = weight_calculator.calculate_weight(
                    position_1=a1["author_position"],
                    position_2=a2["author_position"],
                    is_corresponding_1=a1.get("is_corresponding", False),
                    is_corresponding_2=a2.get("is_corresponding", False),
                    total_authors=len(work_auths),
                    publication_date=pub_date,
                )
                storage.save_or_update_collaboration(
                    a1["author_id"], a2["author_id"], weight, pub_date,
                )
                new_collaborations += 1

    storage.commit()
    return new_authors, new_authorships, new_collaborations
