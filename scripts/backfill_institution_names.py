"""Backfill institution names from OpenAlex API for states showing 'Unknown'."""
import httpx
from sqlalchemy import text
from src.database.models import get_session

session = get_session()
rows = session.execute(
    text("SELECT institution_id FROM institution_crawl_state WHERE institution_name IS NULL OR institution_name = 'Unknown' ORDER BY institution_id")
).fetchall()
ids = [r[0] for r in rows]
print(f"Fetching names for {len(ids)} institutions from OpenAlex...")

updated = 0
with httpx.Client(timeout=10) as client:
    for inst_id in ids:
        try:
            resp = client.get(f"https://api.openalex.org/institutions/{inst_id}")
            if resp.status_code == 200:
                data = resp.json()
                name = data.get("display_name", "Unknown")
                session.execute(
                    text("UPDATE institution_crawl_state SET institution_name = :name WHERE institution_id = :id"),
                    {"name": name, "id": inst_id},
                )
                print(f"  {inst_id} -> {name}")
                updated += 1
            else:
                print(f"  {inst_id} -> HTTP {resp.status_code}")
        except Exception as e:
            print(f"  {inst_id} -> Error: {e}")

session.commit()
print(f"Updated {updated} names")
session.close()
