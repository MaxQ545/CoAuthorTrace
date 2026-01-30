#!/usr/bin/env python3
"""
Author deduplication script.

Groups authors by (display_name, institution) and merges duplicates.
The author with the most works (or an ORCID) becomes the canonical record.
"""
import json
import sys
from collections import defaultdict

sys.path.insert(0, '/workspace/Playground/CoauthorTracing')

from sqlalchemy import func
from src.database.models import get_session, Author


def deduplicate_authors():
    """Deduplicate authors by name and institution."""
    session = get_session()

    print("=== 开始作者去重 ===")

    # Reset previous deduplication
    print("重置之前的去重结果...")
    session.query(Author).update({
        Author.is_canonical: True,
        Author.alias_ids: None
    })
    session.commit()

    # Group authors by (display_name, institution_id)
    print("按姓名和机构分组...")
    authors = session.query(Author).all()

    groups = defaultdict(list)
    for author in authors:
        key = (author.display_name, author.last_known_institution_id)
        groups[key].append(author)

    # Process groups with duplicates
    groups_merged = 0
    aliases_created = 0

    duplicate_groups = {k: v for k, v in groups.items() if len(v) > 1}
    print(f"发现 {len(duplicate_groups)} 组重复作者")

    for (name, inst_id), authors_in_group in duplicate_groups.items():
        # Sort by: has ORCID (True first), then works_count (desc)
        authors_in_group.sort(
            key=lambda a: (a.orcid is not None, a.works_count or 0),
            reverse=True
        )

        # First one is canonical
        canonical = authors_in_group[0]
        aliases = authors_in_group[1:]

        # Mark aliases
        alias_ids = []
        for alias in aliases:
            alias.is_canonical = False
            alias_ids.append(alias.id)
            aliases_created += 1

        # Store alias IDs in canonical record
        canonical.alias_ids = json.dumps(alias_ids)
        canonical.is_canonical = True

        groups_merged += 1

    session.commit()
    session.close()

    print(f"\n=== 作者去重完成 ===")
    print(f"合并组数: {groups_merged}")
    print(f"标记为别名的记录: {aliases_created}")

    return {
        "groups_merged": groups_merged,
        "aliases_created": aliases_created
    }


if __name__ == "__main__":
    deduplicate_authors()
