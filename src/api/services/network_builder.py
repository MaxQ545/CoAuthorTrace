"""
Progressive network expansion service.

Builds a co-authorship network starting from one or more seed authors
using BFS traversal. Streams incremental graph updates to the client
via Server-Sent Events (SSE).

Key design decisions:
- Union-Find tracks connected components so the frontend can visualize
  when previously separate clusters merge.
- BFS is depth-limited (max_depth) and width-limited (top_k
  collaborators per node) to keep response sizes manageable.
- Individual node/edge events are yielded for smooth progressive
  rendering on the frontend.
"""
import asyncio
import logging
import time
from typing import AsyncGenerator, Optional

from sqlalchemy.orm import Session

from src.database.models import Author, Collaboration
from src.database.repositories import AuthorRepository

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration defaults
# ---------------------------------------------------------------------------
DEFAULT_MAX_DEPTH = 3
DEFAULT_MAX_NODES = 500
DEFAULT_TOP_K = 20
DEFAULT_MIN_COLLAB_COUNT = 1


# ---------------------------------------------------------------------------
# Union-Find for connected component tracking
# ---------------------------------------------------------------------------
class UnionFind:
    """Disjoint-set data structure with union-by-rank and path compression."""

    def __init__(self):
        self._parent: dict[str, str] = {}
        self._rank: dict[str, int] = {}

    def find(self, x: str) -> str:
        if x not in self._parent:
            self._parent[x] = x
            self._rank[x] = 0
            return x
        # Path compression (iterative)
        while self._parent[x] != x:
            self._parent[x] = self._parent[self._parent[x]]
            x = self._parent[x]
        return x

    def union(self, a: str, b: str) -> bool:
        """Union two elements. Returns True if they were in different sets."""
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return False
        # Union by rank
        if self._rank[ra] < self._rank[rb]:
            ra, rb = rb, ra
        self._parent[rb] = ra
        if self._rank[ra] == self._rank[rb]:
            self._rank[ra] += 1
        return True

    def connected(self, a: str, b: str) -> bool:
        return self.find(a) == self.find(b)

    def component_count(self) -> int:
        roots = set()
        for x in self._parent:
            roots.add(self.find(x))
        return len(roots)

    def components(self) -> dict[str, list[str]]:
        """Return mapping of root -> list of member ids."""
        comp: dict[str, list[str]] = {}
        for x in self._parent:
            root = self.find(x)
            comp.setdefault(root, []).append(x)
        return comp

    def all_seeds_connected(self, seed_ids: list[str]) -> bool:
        """Check if all seed authors are in the same connected component."""
        if len(seed_ids) <= 1:
            return True
        root = self.find(seed_ids[0])
        return all(self.find(s) == root for s in seed_ids[1:])


# ---------------------------------------------------------------------------
# NetworkBuilder — core progressive BFS
# ---------------------------------------------------------------------------
class NetworkBuilder:
    """
    Builds a collaboration network progressively from seed authors.

    Instantiated per-request. Uses existing AuthorRepository for
    data access and Union-Find for connectivity tracking.

    Usage::

        builder = NetworkBuilder(db, seed_ids, max_depth=2, top_k=15)
        async for sse_string in builder.stream():
            yield sse_string
    """

    def __init__(
        self,
        db: Session,
        seed_author_ids: list[str],
        max_depth: int = DEFAULT_MAX_DEPTH,
        max_nodes: int = DEFAULT_MAX_NODES,
        top_k: int = DEFAULT_TOP_K,
        min_collab_count: int = DEFAULT_MIN_COLLAB_COUNT,
        from_year: Optional[int] = None,
        to_year: Optional[int] = None,
    ):
        self.db = db
        self.seed_ids = seed_author_ids
        self.max_depth = max_depth
        self.max_nodes = max_nodes
        self.top_k = top_k
        self.min_collab_count = min_collab_count
        self.from_year = from_year
        self.to_year = to_year

        # State
        self._nodes: dict[str, dict] = {}  # id -> node data
        self._edge_set: set[tuple[str, str]] = set()  # dedup edges
        self._edges: list[dict] = []
        self._visited: set[str] = set()  # already-expanded IDs
        self._uf = UnionFind()

        # Repositories
        self._author_repo = AuthorRepository(db)

    async def stream(self) -> AsyncGenerator[str, None]:
        """Main entry point — yields SSE-formatted strings."""
        t0 = time.monotonic()

        try:
            # Resolve seed authors
            seed_authors = self._resolve_seeds()
            if not seed_authors:
                yield _sse_event("error", {"message": "No valid seed authors found"})
                return

            resolved_seed_ids = [a.id for a in seed_authors]

            # Emit init event
            yield _sse_event("init", {
                "seed_authors": [
                    {
                        "id": a.id,
                        "name": a.display_name,
                        "institution": a.last_known_institution_name,
                    }
                    for a in seed_authors
                ],
                "max_depth": self.max_depth,
                "max_nodes": self.max_nodes,
                "top_k": self.top_k,
            })

            # Add seed nodes
            for author in seed_authors:
                node_data = self._make_node(author, depth=0, is_seed=True)
                self._nodes[author.id] = node_data
                self._uf.find(author.id)
                yield _sse_event("node", node_data)

            # Check for edges between seed authors
            for event in self._emit_edges_between(resolved_seed_ids):
                yield event

            # BFS expansion
            # Queue: list of (author_id, depth) — process level by level
            queue: list[tuple[str, int]] = [(aid, 0) for aid in resolved_seed_ids]
            queue_idx = 0

            current_depth = 0
            authors_at_depth = len(resolved_seed_ids)
            authors_processed_at_depth = 0

            while queue_idx < len(queue):
                author_id, depth = queue[queue_idx]
                queue_idx += 1

                # Moving to next depth level?
                if depth > current_depth:
                    # Emit component summary for completed depth
                    for event in self._emit_component_events():
                        yield event

                    # Early termination: all seeds connected
                    if self._uf.all_seeds_connected(resolved_seed_ids):
                        yield _sse_event("connected", {
                            "depth": current_depth,
                            "components": self._uf.component_count(),
                        })
                        break

                    current_depth = depth
                    # Count how many authors are at this depth in the queue
                    authors_at_depth = sum(
                        1 for _, d in queue[queue_idx - 1:] if d == depth
                    )
                    authors_processed_at_depth = 0

                # Skip if already expanded
                if author_id in self._visited:
                    continue
                self._visited.add(author_id)

                # Don't expand beyond max_depth
                if depth >= self.max_depth:
                    continue

                # Fetch collaborators using existing repository method
                collaborators = self._author_repo.get_collaborators(
                    author_id,
                    limit=self.top_k,
                    from_year=self.from_year,
                    to_year=self.to_year,
                )

                for collab_author, collab_count in collaborators:
                    if collab_count < self.min_collab_count:
                        continue

                    # Add node if new and within max_nodes limit
                    if collab_author.id not in self._nodes:
                        if len(self._nodes) >= self.max_nodes:
                            continue  # Don't add more nodes, but still process edges

                        node_data = self._make_node(
                            collab_author, depth=depth + 1, is_seed=False,
                        )
                        self._nodes[collab_author.id] = node_data
                        self._uf.find(collab_author.id)
                        yield _sse_event("node", node_data)

                        # Enqueue for next depth expansion
                        if depth + 1 < self.max_depth:
                            queue.append((collab_author.id, depth + 1))

                    # Add edge if new
                    edge_key = _edge_key(author_id, collab_author.id)
                    if edge_key not in self._edge_set and collab_author.id in self._nodes:
                        self._edge_set.add(edge_key)
                        edge_data = {
                            "from": author_id,
                            "to": collab_author.id,
                            "weight": collab_count,
                            "collaboration_count": collab_count,
                        }
                        self._edges.append(edge_data)
                        yield _sse_event("edge", edge_data)

                        # Track component merges
                        self._uf.union(author_id, collab_author.id)

                # Emit progress
                authors_processed_at_depth += 1
                yield _sse_event("progress", {
                    "depth": depth,
                    "authors_processed": authors_processed_at_depth,
                    "authors_total": authors_at_depth,
                    "phase": "expanding",
                    "nodes_count": len(self._nodes),
                    "edges_count": len(self._edges),
                    "components": self._uf.component_count(),
                })

                # Yield control to event loop periodically
                await asyncio.sleep(0)

            # Final component events
            for event in self._emit_component_events():
                yield event

            # Check if all seeds connected (may not have triggered the early-exit above)
            all_connected = self._uf.all_seeds_connected(resolved_seed_ids)
            if all_connected and len(resolved_seed_ids) > 1:
                yield _sse_event("connected", {
                    "depth": current_depth,
                    "components": self._uf.component_count(),
                })

            # Complete event
            elapsed = time.monotonic() - t0
            components = self._uf.components()
            yield _sse_event("complete", {
                "total_nodes": len(self._nodes),
                "total_edges": len(self._edges),
                "components": len(components),
                "component_sizes": sorted(
                    [len(members) for members in components.values()],
                    reverse=True,
                ),
                "all_connected": all_connected,
                "elapsed_ms": round(elapsed * 1000, 1),
            })

        except Exception as exc:
            logger.exception("Network expansion failed")
            yield _sse_event("error", {"message": str(exc)})

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _resolve_seeds(self) -> list[Author]:
        """Look up seed authors by ID, resolving aliases to canonical."""
        authors = []
        seen = set()
        for sid in self.seed_ids:
            canonical_id = self._author_repo.get_canonical_id(sid)
            author = self._author_repo.get_by_id(canonical_id)
            if not author:
                continue
            if author.id not in seen:
                seen.add(author.id)
                authors.append(author)
        return authors

    def _make_node(self, author: Author, depth: int, is_seed: bool) -> dict:
        """Create a node data dict from an Author model."""
        return {
            "id": author.id,
            "label": author.display_name,
            "institution": author.last_known_institution_name,
            "works_count": author.works_count or 0,
            "cited_by_count": author.cited_by_count or 0,
            "depth": depth,
            "is_seed": is_seed,
        }

    def _emit_edges_between(self, author_ids: list[str]):
        """Yield edge events for all collaboration edges between a set of authors."""
        if len(author_ids) < 2:
            return

        collabs = (
            self.db.query(Collaboration)
            .filter(
                Collaboration.author_id_1.in_(author_ids),
                Collaboration.author_id_2.in_(author_ids),
                Collaboration.collaboration_count >= self.min_collab_count,
            )
            .all()
        )

        for c in collabs:
            edge_key = _edge_key(c.author_id_1, c.author_id_2)
            if edge_key not in self._edge_set:
                self._edge_set.add(edge_key)
                edge_data = {
                    "from": c.author_id_1,
                    "to": c.author_id_2,
                    "weight": c.collaboration_count,
                    "collaboration_count": c.collaboration_count,
                }
                self._edges.append(edge_data)
                self._uf.union(c.author_id_1, c.author_id_2)
                yield _sse_event("edge", edge_data)

    def _emit_component_events(self):
        """Yield component events showing current connected components."""
        components = self._uf.components()
        for root, members in components.items():
            yield _sse_event("component", {
                "component_id": root,
                "author_ids": members,
                "size": len(members),
            })


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------
def _sse_event(event_type: str, data: dict) -> str:
    """Format a single SSE event string."""
    import json
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _edge_key(a: str, b: str) -> tuple[str, str]:
    """Canonical edge key (ordered pair) to avoid duplicates."""
    return (min(a, b), max(a, b))
