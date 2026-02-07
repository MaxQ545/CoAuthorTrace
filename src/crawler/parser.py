"""
Standalone OpenAlex work-record parser.

Transforms raw OpenAlex API responses into flat dicts ready for storage.
No external dependencies beyond the standard library.
"""
import json
from datetime import datetime
from typing import Optional


def parse_work(
    work: dict,
    preferred_institution_ids: Optional[list[str]] = None,
) -> tuple[dict, list[dict], list[dict]]:
    """
    Parse an OpenAlex work response into storage-ready dicts.

    Args:
        work: Raw work data from OpenAlex.
        preferred_institution_ids: Institution IDs to prioritise when
            selecting the author's institution from a work.

    Returns:
        Tuple of (work_dict, list_of_author_dicts, list_of_authorship_dicts)
    """
    # ---- work ----
    work_dict = {
        "id": work["id"].replace("https://openalex.org/", ""),
        "doi": work.get("doi"),
        "title": work.get("title") or "Untitled",
        "publication_date": None,
        "publication_year": None,
        "type": work.get("type"),
        "cited_by_count": work.get("cited_by_count", 0),
        "source_id": None,
        "source_name": None,
        "is_open_access": work.get("open_access", {}).get("is_oa", False),
        "concepts": None,
    }

    # concepts (level 1-2, score >= 0.3, top 10)
    raw_concepts = work.get("concepts", [])
    filtered = [
        {
            "id": c.get("id", "").replace("https://openalex.org/", ""),
            "display_name": c.get("display_name", ""),
            "level": c.get("level", 0),
            "score": c.get("score", 0),
        }
        for c in raw_concepts
        if c.get("level") in (1, 2) and c.get("score", 0) >= 0.3
    ]
    if filtered:
        filtered.sort(key=lambda x: x["score"], reverse=True)
        work_dict["concepts"] = json.dumps(filtered[:10])

    # publication date
    pub_date_str = work.get("publication_date")
    if pub_date_str:
        try:
            work_dict["publication_date"] = datetime.strptime(pub_date_str, "%Y-%m-%d")
            work_dict["publication_year"] = work_dict["publication_date"].year
        except ValueError:
            pass

    # source
    primary_location = work.get("primary_location") or {}
    source = primary_location.get("source") or {}
    if source:
        sid = source.get("id", "")
        work_dict["source_id"] = sid.replace("https://openalex.org/", "") if sid else None
        work_dict["source_name"] = source.get("display_name")

    # ---- authorships ----
    preferred_ids = set(preferred_institution_ids or [])

    def _norm(inst_id: str) -> Optional[str]:
        return inst_id.replace("https://openalex.org/", "") if inst_id else None

    def _pick_institution(institutions: list[dict]) -> tuple[dict, Optional[str]]:
        if not institutions:
            return {}, None
        if preferred_ids:
            for inst in institutions:
                iid = _norm(inst.get("id", ""))
                if iid in preferred_ids:
                    return inst, iid
        inst = institutions[0]
        return inst, _norm(inst.get("id", ""))

    authors: list[dict] = []
    authorships: list[dict] = []

    for idx, authorship in enumerate(work.get("authorships", [])):
        author = authorship.get("author") or {}
        author_id = author.get("id", "")
        if not author_id:
            continue
        author_id = author_id.replace("https://openalex.org/", "")

        institutions = authorship.get("institutions", [])
        if not institutions:
            last_known = author.get("last_known_institution") or {}
            if last_known:
                institutions = [last_known]

        last_inst, inst_id = _pick_institution(institutions)

        authors.append({
            "id": author_id,
            "display_name": author.get("display_name", "Unknown"),
            "orcid": author.get("orcid"),
            "last_known_institution_id": _norm(inst_id),
            "last_known_institution_name": last_inst.get("display_name"),
        })

        affiliations = [i.get("display_name", "") for i in institutions if i.get("display_name")]
        authorships.append({
            "author_id": author_id,
            "work_id": work_dict["id"],
            "author_position": idx,
            "is_corresponding": authorship.get("is_corresponding", False),
            "raw_author_name": authorship.get("raw_author_name"),
            "raw_affiliation": "; ".join(affiliations) if affiliations else None,
        })

    return work_dict, authors, authorships
