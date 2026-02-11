#!/usr/bin/env python3
"""
Deduplicate authors: merge OpenAlex IDs with same display_name AND same primary institution.

Primary institution = most frequent institution across an author's authorships
(splitting raw_affiliation on "; " and counting each individually).

Safety: different non-null ORCIDs = definitely different people → never merged.

Steps:
  1. Reset all existing merges (is_canonical=True, alias_ids=NULL)
  2. Compute primary institution per author from authorships
  3. Group by (display_name, primary_institution)
  4. Within each group, sub-divide by ORCID to prevent false merges
  5. Pick canonical (most works), set alias_ids on canonical, mark aliases
"""

import json
import logging
import sys
from collections import defaultdict
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine, text

from config.settings import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    settings = get_settings()
    # Use a single raw connection (pool_size=1) to avoid self-deadlocks
    engine = create_engine(
        settings.database.postgres_url,
        pool_size=1,
        max_overflow=0,
    )
    conn = engine.connect()

    try:
        # ── Step 1: Reset all existing merges ──────────────────────────
        logger.info("Step 1: Resetting all existing merges ...")
        conn.execute(text("UPDATE authors SET is_canonical = true, alias_ids = NULL"))
        conn.commit()
        logger.info("  Done — all authors reset to canonical.")

        # ── Step 2: Compute primary institution per author ─────────────
        logger.info("Step 2: Computing primary institution per author ...")
        rows = conn.execute(text("""
            WITH split_aff AS (
                SELECT author_id,
                       trim(unnest(string_to_array(raw_affiliation, '; '))) AS institution
                FROM authorships
                WHERE raw_affiliation IS NOT NULL
                  AND raw_affiliation != ''
            ),
            counted AS (
                SELECT author_id, institution, count(*) AS cnt
                FROM split_aff
                WHERE institution != ''
                GROUP BY author_id, institution
            ),
            ranked AS (
                SELECT author_id, institution, cnt,
                       row_number() OVER (
                           PARTITION BY author_id
                           ORDER BY cnt DESC, institution
                       ) AS rn
                FROM counted
            )
            SELECT r.author_id,
                   r.institution,
                   r.cnt,
                   a.display_name,
                   a.orcid,
                   a.works_count
            FROM ranked r
            JOIN authors a ON a.id = r.author_id
            WHERE r.rn = 1
        """)).fetchall()
        conn.commit()

        logger.info(f"  Got primary institution for {len(rows)} authors.")

        author_info: dict[str, dict] = {}
        for author_id, institution, cnt, display_name, orcid, works_count in rows:
            author_info[author_id] = {
                "display_name": display_name,
                "primary_institution": institution,
                "orcid": orcid,
                "works_count": works_count or 0,
                "inst_count": cnt,
            }

        # ── Step 3: Group by (display_name, primary_institution) ───────
        logger.info("Step 3: Grouping by (name, primary_institution) ...")
        groups: dict[tuple, list[str]] = defaultdict(list)
        for author_id, info in author_info.items():
            key = (info["display_name"], info["primary_institution"])
            groups[key].append(author_id)

        multi_groups = {k: v for k, v in groups.items() if len(v) > 1}
        logger.info(f"  {len(multi_groups)} groups have 2+ authors (candidates).")

        # ── Step 4: Sub-divide by ORCID ────────────────────────────────
        #   - Same ORCID → definitely same person → merge
        #   - Different ORCIDs → definitely different people → separate
        #   - No ORCID → merge with each other (same name + same inst)
        logger.info("Step 4: Sub-dividing by ORCID within each group ...")
        merge_groups: list[list[str]] = []

        for (_name, _inst), author_ids in multi_groups.items():
            orcid_map: dict[str, list[str]] = defaultdict(list)
            no_orcid: list[str] = []

            for aid in author_ids:
                orcid = author_info[aid]["orcid"]
                if orcid:
                    orcid_map[orcid].append(aid)
                else:
                    no_orcid.append(aid)

            if len(orcid_map) <= 1:
                # 0 or 1 distinct ORCID → safe to merge all
                merge_groups.append(author_ids)
            else:
                # Multiple different ORCIDs → each ORCID is a separate person
                for _orcid, aids in orcid_map.items():
                    if len(aids) > 1:
                        merge_groups.append(aids)
                # Null-ORCID authors: merge together (conservative)
                if len(no_orcid) > 1:
                    merge_groups.append(no_orcid)

        # Filter out singletons
        merge_groups = [g for g in merge_groups if len(g) > 1]
        total_aliases = sum(len(g) - 1 for g in merge_groups)
        logger.info(
            f"  {len(merge_groups)} final merge groups, "
            f"{total_aliases} authors will become aliases."
        )

        # ── Step 5: Execute merges ─────────────────────────────────────
        logger.info("Step 5: Executing merges ...")
        for group in merge_groups:
            # Canonical = most works, then most primary-institution authorships
            group.sort(
                key=lambda aid: (
                    author_info[aid]["works_count"],
                    author_info[aid]["inst_count"],
                ),
                reverse=True,
            )
            canonical_id = group[0]
            alias_ids = group[1:]

            conn.execute(
                text("UPDATE authors SET alias_ids = :aliases WHERE id = :id"),
                {"aliases": json.dumps(alias_ids), "id": canonical_id},
            )
            for chunk_start in range(0, len(alias_ids), 500):
                chunk = alias_ids[chunk_start : chunk_start + 500]
                conn.execute(
                    text(
                        "UPDATE authors SET is_canonical = false "
                        "WHERE id = ANY(:ids)"
                    ),
                    {"ids": chunk},
                )

        conn.commit()
        logger.info("  All merges committed.")

        # ── Summary ────────────────────────────────────────────────────
        canonical = conn.execute(
            text("SELECT count(*) FROM authors WHERE is_canonical = true")
        ).scalar()
        aliases = conn.execute(
            text("SELECT count(*) FROM authors WHERE is_canonical = false")
        ).scalar()
        with_alias = conn.execute(
            text("SELECT count(*) FROM authors WHERE alias_ids IS NOT NULL")
        ).scalar()
        logger.info(
            f"Done. canonical={canonical}, aliases={aliases}, "
            f"authors_with_alias_ids={with_alias}"
        )

    finally:
        conn.close()


if __name__ == "__main__":
    main()
