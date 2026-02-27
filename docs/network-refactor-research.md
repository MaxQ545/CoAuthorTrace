# Network Refactor Research: Progressive Multi-Author Expansion

## 1. Current Architecture Analysis

### 1.1 Frontend Flow

**NetworkPage.jsx** — Single-author, star-topology network:
- User searches for one author via `SearchBox`
- Navigates to `/network/:authorId`
- Calls `useAuthor(authorId)` and `useAuthorCollaborators(authorId, 50, fromYear, toYear)`
- Builds a flat star graph in `useMemo`: center node = queried author, spokes = top-N collaborators
- No inter-collaborator edges — the graph is always a single-level ego network
- Sidebar lists collaborators ranked by `collaboration_count`
- Clicking a node navigates to `/author/:id` (leaves network page entirely)

**NetworkGraph.jsx** — vis-network rendering:
- Dynamically imports `vis-network/standalone` and `vis-data/standalone`
- Accepts `{ nodes, edges, centerNodeId, onNodeClick }` props
- Uses `DataSet` for nodes/edges — supports incremental add/update/remove
- Physics: `forceAtlas2Based` solver with stabilization (200 iterations)
- Node sizing: center = 35px, others = `15 + collabCount * 0.5` (capped at 30)
- Edge width: `count * 0.5` (capped at 5)
- Destroys and recreates the entire network on every prop change

**Key Limitation**: The current graph is reconstructed from scratch on every render. There is no incremental update path.

### 1.2 API & Data Layer

**`GET /authors/{author_id}/collaborators`** (authors.py:709-757):
- Returns `{ author_id, author_name, collaborators: [...] }`
- Each collaborator: `{ id, display_name, collaboration_count, primary_institution_name }`
- Delegates to `AuthorRepository.get_collaborators()` with optional year filtering
- Does NOT return `works_count` or `cited_by_count` for collaborators (only `collaboration_count`)

**`AuthorRepository.get_collaborators()`** (author_repository.py:219-263):
- Without year filter: Queries the pre-computed `Collaboration` table (fast — indexed)
- With year filter: Falls back to `_get_collaborators_by_year_range()` which joins `Authorship × Work` and dynamically counts (slower)
- Returns `list[tuple[Author, int]]` — (author model, collaboration count)
- Handles alias/merged authors properly

**`Collaboration` model** (models.py:149-175):
- Stores pre-computed edges between author pairs
- Fields: `author_id_1`, `author_id_2` (alphabetically ordered), `collaboration_count`, `total_weight`, `first_collaboration`, `last_collaboration`
- Indexed on both author columns and weight
- The `total_weight` incorporates author position, corresponding author status, total authors per paper, and publication date recency

**`CollaborationRepository.get_collaborations_for_author()`** (collaboration_repository.py:78-97):
- Fetches all collaboration edges for a single author
- Supports `min_count` filter and `limit`
- Ordered by `total_weight` descending

**Other relevant endpoints:**
- `GET /authors/{author_id}` — Full author details including institution, research fields, all merged IDs
- `GET /authors/{author_id}/top-relations` — GNN-scored relationships (uses `RelationshipScore` table)
- `GET /authors/{author_id}/network-metrics` — Graph centrality metrics (degree, betweenness, PageRank, etc.)

### 1.3 Data Model Summary

```
Author (id, display_name, works_count, cited_by_count, institution, alias_ids, research_fields)
  │
  ├── Authorship (author_id, work_id, position, is_corresponding, affiliation)
  │     └── Work (id, title, doi, publication_year, cited_by_count, concepts)
  │
  ├── Collaboration (author_id_1, author_id_2, collaboration_count, total_weight, date range)
  │
  └── RelationshipScore (author_id_1, author_id_2, graphsage_score, weighted_score, combined_score)
```

### 1.4 What's Missing for Multi-Author Networks

1. **No multi-author query endpoint** — current API fetches collaborators for one author at a time
2. **No inter-collaborator edges** — the star graph has no edges between collaborators
3. **No progressive expansion** — the entire graph is built at once; no streaming or incremental growth
4. **No connectivity detection** — no way to tell if two selected authors are in the same connected component
5. **No real-time progress** — loading is all-or-nothing with a spinner

---

## 2. Progressive Expansion Algorithm

### 2.1 Core Concept

Given multiple seed authors, we want to **progressively expand** the collaboration network outward from each seed using BFS, layer by layer, until either:
- All seeds are connected in a single component, OR
- A maximum depth / node count is reached

This is analogous to **multi-source BFS** on the collaboration graph, with **Union-Find** to efficiently track connected components.

### 2.2 Pseudocode

```
FUNCTION progressive_network_build(seed_author_ids, max_depth=3, max_nodes=200, top_k_per_node=10):

    # --- Initialization ---
    uf = UnionFind(seed_author_ids)         # Union-Find with seeds as initial elements
    visited = set(seed_author_ids)          # Global set of all visited author IDs
    graph = { nodes: {}, edges: {} }        # Accumulated graph
    queue = deque()                         # BFS frontier: (author_id, depth, source_seed)

    # Fetch seed author details (parallel batch)
    seed_authors = batch_fetch_authors(seed_author_ids)
    for author in seed_authors:
        graph.nodes[author.id] = author
        queue.append((author.id, 0, author.id))

    YIELD SSE event: { type: "init", seeds: seed_author_ids, total_seeds: len(seed_author_ids) }

    # --- BFS Expansion ---
    current_depth = 0

    WHILE queue is not empty AND len(graph.nodes) < max_nodes AND current_depth <= max_depth:

        # Process all nodes at current depth level
        level_size = len(queue)
        level_nodes = []

        FOR i in range(level_size):
            author_id, depth, source_seed = queue.popleft()

            IF depth > current_depth:
                # We've moved to the next BFS layer — re-enqueue and break
                queue.appendleft((author_id, depth, source_seed))
                BREAK

            # Fetch top-K collaborators for this author
            collaborators = get_collaborators(author_id, limit=top_k_per_node)

            FOR collab_id, collab_author, collab_count in collaborators:
                # Add edge (always, even if node already visited)
                edge_key = tuple(sorted([author_id, collab_id]))
                IF edge_key not in graph.edges:
                    graph.edges[edge_key] = {
                        from: author_id,
                        to: collab_id,
                        weight: collab_count
                    }

                # If this collaborator connects two previously separate components:
                IF collab_id in visited:
                    uf.union(author_id, collab_id)
                ELSE:
                    # New node discovered
                    visited.add(collab_id)
                    graph.nodes[collab_id] = collab_author
                    uf.add(collab_id)
                    uf.union(author_id, collab_id)
                    level_nodes.append(collab_id)

                    # Enqueue for next depth level
                    IF depth + 1 <= max_depth:
                        queue.append((collab_id, depth + 1, source_seed))

            YIELD SSE event: {
                type: "expansion",
                depth: current_depth,
                expanded_author: author_id,
                new_nodes: [newly discovered nodes this step],
                new_edges: [newly discovered edges this step],
                total_nodes: len(graph.nodes),
                total_edges: len(graph.edges),
                components: uf.component_count(),
                all_connected: uf.all_seeds_connected(seed_author_ids)
            }

        current_depth += 1

        # Early termination: all seeds connected
        IF uf.all_seeds_connected(seed_author_ids):
            YIELD SSE event: { type: "connected", depth: current_depth }
            # Optional: do one more round to enrich the graph
            IF current_depth > max_depth:
                BREAK

    # --- Finalization ---
    YIELD SSE event: {
        type: "complete",
        total_nodes: len(graph.nodes),
        total_edges: len(graph.edges),
        components: uf.component_count(),
        all_connected: uf.all_seeds_connected(seed_author_ids),
        max_depth_reached: current_depth
    }
```

### 2.3 Union-Find Data Structure

```python
class UnionFind:
    def __init__(self, elements):
        self.parent = {e: e for e in elements}
        self.rank = {e: 0 for e in elements}
        self.component_sizes = {e: 1 for e in elements}

    def add(self, x):
        if x not in self.parent:
            self.parent[x] = x
            self.rank[x] = 0
            self.component_sizes[x] = 1

    def find(self, x):
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])  # Path compression
        return self.parent[x]

    def union(self, x, y):
        rx, ry = self.find(x), self.find(y)
        if rx == ry:
            return False
        # Union by rank
        if self.rank[rx] < self.rank[ry]:
            rx, ry = ry, rx
        self.parent[ry] = rx
        self.component_sizes[rx] += self.component_sizes[ry]
        del self.component_sizes[ry]
        if self.rank[rx] == self.rank[ry]:
            self.rank[rx] += 1
        return True

    def connected(self, x, y):
        return self.find(x) == self.find(y)

    def component_count(self):
        return len(self.component_sizes)

    def all_seeds_connected(self, seeds):
        if len(seeds) <= 1:
            return True
        root = self.find(seeds[0])
        return all(self.find(s) == root for s in seeds[1:])
```

### 2.4 Algorithm Properties

| Property | Value |
|----------|-------|
| Time complexity | O(V × K) where V = visited nodes, K = top-K per node |
| Space complexity | O(V + E) for graph storage |
| Union-Find ops | Near O(1) amortized with path compression + union by rank |
| Early termination | When all seeds share same component root |
| Max nodes guard | Prevents runaway expansion in dense graphs |
| Depth guard | Controls BFS radius (default: 3 hops) |
| Incremental output | SSE event after each node expansion |

### 2.5 Prioritization Strategy

Within each BFS level, nodes should be expanded in priority order:
1. **Seed nodes** first (depth 0)
2. **Bridge candidates** — nodes that appear as collaborators of multiple different seed components (they might connect components)
3. **High collaboration count** — nodes with stronger ties to already-visited nodes

This can be implemented by using a priority queue instead of a simple deque:

```python
# Priority: (depth, -bridge_score, -collab_weight, author_id)
heapq.heappush(queue, (depth, -bridge_score, -collab_weight, author_id))
```

---

## 3. Real-Time Progress Protocol: Server-Sent Events (SSE)

### 3.1 Why SSE over WebSocket

| Criterion | SSE | WebSocket |
|-----------|-----|-----------|
| Direction | Server → Client (unidirectional) | Bidirectional |
| Complexity | Simple — works over standard HTTP | Requires upgrade handshake, separate protocol |
| Reconnection | Built-in auto-reconnect | Must implement manually |
| FastAPI support | Native via `StreamingResponse` | Requires `websockets` dependency |
| Proxy/CDN compatibility | Works through HTTP proxies | Often blocked by proxies |
| Use case fit | Progressive data push = perfect fit | Overkill — client doesn't need to send data mid-stream |

**Recommendation: SSE** — the data flow is purely server→client (the client sends the initial request with seed authors, then receives progressive updates). SSE is simpler to implement, automatically reconnects, and works natively with FastAPI's `StreamingResponse`.

### 3.2 SSE Event Format

**Endpoint:** `GET /api/v1/authors/network/build?author_ids=A1,A2,A3&max_depth=3&max_nodes=200&top_k=10`

**Content-Type:** `text/event-stream`

#### Event Types

**1. `init` — Stream started**
```
event: init
data: {"type":"init","seeds":["A123","A456"],"total_seeds":2,"max_depth":3,"max_nodes":200}
```

**2. `node` — New node discovered**
```
event: node
data: {"type":"node","id":"A789","display_name":"Jane Doe","works_count":42,"cited_by_count":1200,"institution":"MIT","depth":1,"source_seed":"A123"}
```

**3. `edge` — New edge discovered**
```
event: edge
data: {"type":"edge","from":"A123","to":"A789","weight":5,"collaboration_count":5}
```

**4. `progress` — Expansion step completed**
```
event: progress
data: {"type":"progress","depth":1,"expanded":"A123","nodes_total":15,"edges_total":22,"components":2,"all_connected":false,"percent":35}
```

**5. `connected` — All seeds now in same component**
```
event: connected
data: {"type":"connected","depth":2,"components":1}
```

**6. `complete` — Expansion finished**
```
event: complete
data: {"type":"complete","nodes_total":87,"edges_total":142,"components":1,"all_connected":true,"max_depth_reached":2,"elapsed_ms":3200}
```

**7. `error` — Error occurred**
```
event: error
data: {"type":"error","message":"Author A999 not found","code":"AUTHOR_NOT_FOUND"}
```

### 3.3 FastAPI Implementation Sketch

```python
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
import json
import asyncio
from typing import AsyncGenerator

router = APIRouter()

async def network_build_stream(
    author_ids: list[str],
    max_depth: int,
    max_nodes: int,
    top_k: int,
    db_session,
) -> AsyncGenerator[str, None]:
    """Generate SSE events for progressive network expansion."""

    def sse_event(event_type: str, data: dict) -> str:
        return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"

    # ... (algorithm implementation) ...

    yield sse_event("init", {"type": "init", "seeds": author_ids, ...})

    # BFS loop with yields...
    for step in expansion_steps:
        yield sse_event("node", {...})
        yield sse_event("edge", {...})
        yield sse_event("progress", {...})
        await asyncio.sleep(0)  # Yield control to event loop

    yield sse_event("complete", {...})


@router.get("/network/build")
async def build_network(
    author_ids: str = Query(..., description="Comma-separated author IDs"),
    max_depth: int = Query(3, ge=1, le=5),
    max_nodes: int = Query(200, ge=10, le=500),
    top_k: int = Query(10, ge=5, le=30),
    db = Depends(get_db),
):
    ids = [aid.strip() for aid in author_ids.split(",") if aid.strip()]
    return StreamingResponse(
        network_build_stream(ids, max_depth, max_nodes, top_k, db),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
```

### 3.4 Frontend SSE Consumption

```javascript
function useNetworkBuild(authorIds, options = {}) {
    const [state, setState] = useState({ nodes: [], edges: [], status: 'idle', progress: 0 });

    useEffect(() => {
        if (!authorIds?.length) return;

        const params = new URLSearchParams({
            author_ids: authorIds.join(','),
            max_depth: options.maxDepth || 3,
            max_nodes: options.maxNodes || 200,
            top_k: options.topK || 10,
        });

        const source = new EventSource(`/api/v1/authors/network/build?${params}`);

        source.addEventListener('node', (e) => {
            const node = JSON.parse(e.data);
            setState(prev => ({
                ...prev,
                nodes: [...prev.nodes, node],
            }));
        });

        source.addEventListener('edge', (e) => {
            const edge = JSON.parse(e.data);
            setState(prev => ({
                ...prev,
                edges: [...prev.edges, edge],
            }));
        });

        source.addEventListener('progress', (e) => {
            const progress = JSON.parse(e.data);
            setState(prev => ({
                ...prev,
                progress: progress.percent,
                status: 'expanding',
            }));
        });

        source.addEventListener('complete', (e) => {
            setState(prev => ({ ...prev, status: 'complete' }));
            source.close();
        });

        source.addEventListener('error', () => {
            setState(prev => ({ ...prev, status: 'error' }));
            source.close();
        });

        return () => source.close();
    }, [authorIds]);

    return state;
}
```

---

## 4. Incremental vis-network Updates

The current `NetworkGraph.jsx` destroys and recreates the vis-network instance on every prop change. For progressive expansion, we need **incremental updates** using vis-data's `DataSet`:

```javascript
// Store DataSet refs (persistent across renders)
const visNodesRef = useRef(null);
const visEdgesRef = useRef(null);

// On new node from SSE:
visNodesRef.current.add({
    id: node.id,
    label: node.display_name,
    // ... styling
});

// On new edge from SSE:
visEdgesRef.current.add({
    from: edge.from,
    to: edge.to,
    value: edge.weight,
    // ... styling
});
```

Key benefit: vis-network will smoothly animate new nodes into the physics simulation without resetting the entire layout.

---

## 5. Key Design Decisions & Recommendations

### 5.1 Batch vs. Streaming DB Access

The BFS expansion queries collaborators one node at a time. For efficiency:
- **Batch fetch collaborators** for all nodes at the same depth level in a single query
- Use `CollaborationRepository.get_collaborations_for_author()` — already indexed and fast
- Consider a new batch method: `batch_get_top_collaborators(author_ids, limit)` to avoid N+1

### 5.2 Handling Merged Authors (Aliases)

The system has author deduplication (canonical + alias IDs). The algorithm must:
- Always resolve to canonical IDs before adding to the graph
- Use `AuthorRepository.get_canonical_id()` for any discovered collaborator
- Avoid duplicate nodes for the same person under different IDs

### 5.3 Edge Cases

1. **Disconnected seeds**: Some authors may have no path between them in the collaboration graph. The algorithm handles this by tracking components and reporting `all_connected: false` at completion.

2. **Very prolific authors**: An author with thousands of collaborators would dominate the graph. The `top_k_per_node` parameter limits expansion fan-out.

3. **Self-loops**: The `Collaboration` table uses `author_id_1 < author_id_2` ordering, so self-loops are impossible.

4. **Year filtering**: Currently deferred for the SSE endpoint. The pre-computed `Collaboration` table doesn't filter by year — year-filtered queries are much slower. Recommendation: use the pre-computed table for progressive expansion and add year filtering as a post-expansion client-side filter later.

### 5.4 Performance Estimates

Based on current data patterns:
- Average collaborator count per author: ~10-50 in the top-K
- With `max_depth=3` and `top_k=10`: worst case ~1,000 nodes, typical ~50-200
- Each collaborator fetch: ~5-20ms (indexed query on `Collaboration` table)
- Full expansion for 2 seeds, depth 3: estimated 1-5 seconds
- SSE keeps the client responsive throughout

---

## 6. Summary of Recommendations

| Decision | Recommendation |
|----------|----------------|
| Real-time protocol | **SSE** via FastAPI `StreamingResponse` |
| Graph algorithm | **Multi-source BFS** with Union-Find for connectivity |
| Data structure | Union-Find with path compression + union by rank |
| Expansion strategy | Layer-by-layer BFS, top-K collaborators per node |
| Early termination | When all seeds connected OR max_nodes/max_depth reached |
| Frontend graph updates | **Incremental** vis-data `DataSet.add()` (no full rebuild) |
| DB access pattern | Batch collaborator fetches per BFS level |
| Author dedup | Resolve to canonical IDs before adding to graph |
| Year filtering | Defer to post-expansion client-side filtering |
| New backend service | `NetworkBuilder` class encapsulating BFS + Union-Find + SSE generation |
| New API endpoint | `GET /api/v1/authors/network/build?author_ids=...` returning `text/event-stream` |
