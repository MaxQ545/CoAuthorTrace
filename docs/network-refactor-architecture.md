# Network Refactor Architecture

Multi-author progressive collaboration network — complete system design.

## 1. Overview

**Goal**: Replace the single-author star-graph network with a multi-author progressive expansion system. Users select 2+ authors, and the backend streams a merged collaboration network via SSE, progressively expanding from seed authors outward.

**Key constraints**:
- No new pip dependencies (use FastAPI's built-in `StreamingResponse`)
- No new npm dependencies (use native `EventSource` API)
- Preserve existing vis-network rendering (enhance, don't replace)
- Keep existing single-author `/network/:authorId` route working
- All new backend code follows existing patterns (repository pattern, Pydantic models, `get_db` dependency injection)

---

## 2. Backend Architecture

### 2.1 New Router: `src/api/routers/network.py`

Dedicated router mounted at `/api/v1/network`. Keeps network-specific logic separate from the general author CRUD in `authors.py`.

**Registration in `src/api/main.py`**:
```python
from src.api.routers import network
app.include_router(network.router, prefix="/api/v1/network", tags=["network"])
```

#### Endpoint: `GET /api/v1/network/expand`

```python
@router.get("/expand")
async def expand_network(
    author_ids: str = Query(..., description="Comma-separated author IDs (1-10)"),
    max_depth: int = Query(2, ge=1, le=3, description="BFS expansion depth"),
    max_nodes: int = Query(200, ge=10, le=500, description="Max nodes before stopping expansion"),
    top_k: int = Query(15, ge=5, le=50, description="Top collaborators per author per level"),
    from_year: Optional[int] = Query(None, ge=1900, le=2100),
    to_year: Optional[int] = Query(None, ge=1900, le=2100),
    db: Session = Depends(get_db),
):
```

**Returns**: `StreamingResponse` with `media_type="text/event-stream"`.

**Validation**:
- Parse `author_ids` into a list, validate 1-10 IDs
- Resolve each ID to canonical via `AuthorRepository.get_canonical_id()`
- Return 404 if any author not found
- Return 400 if 0 unique canonical IDs after dedup

### 2.2 SSE Event Protocol

All events are JSON-encoded in SSE `data:` fields with an `event:` type prefix.

#### Event Types

| Event | Payload | When |
|---|---|---|
| `init` | `{ seed_authors: [{id, name, institution}], max_depth, top_k }` | Immediately after connection |
| `node` | `{ id, label, institution, works_count, cited_by_count, depth, is_seed }` | Each new author discovered |
| `edge` | `{ from, to, weight, collaboration_count }` | Each collaboration edge |
| `progress` | `{ depth, authors_processed, authors_total, phase, percent }` | After each author expansion |
| `connected` | `{ depth, components }` | When all seeds merge into one component |
| `component` | `{ component_id, author_ids, is_connected }` | After Union-Find merge detection |
| `complete` | `{ total_nodes, total_edges, components, all_connected, elapsed_ms }` | Stream finished |
| `error` | `{ message, code }` | On failure |

#### Event format example

```
event: node
data: {"id":"A1234","label":"Alice Smith","institution":"MIT","works_count":45,"cited_by_count":1200,"depth":0,"is_seed":true}

event: edge
data: {"from":"A1234","to":"A5678","weight":12,"collaboration_count":12}

event: progress
data: {"depth":1,"authors_processed":3,"authors_total":8,"phase":"expanding","percent":37}

event: connected
data: {"depth":2,"components":1}

```

### 2.3 NetworkBuilder Service: `src/api/services/network_builder.py`

Stateful service class that encapsulates the progressive expansion algorithm. Instantiated per-request (not a singleton).

```python
class NetworkBuilder:
    """Progressive multi-author network expansion via BFS with Union-Find."""

    def __init__(
        self,
        db: Session,
        seed_author_ids: list[str],
        max_depth: int = 2,
        max_nodes: int = 200,
        top_k: int = 15,
        from_year: int | None = None,
        to_year: int | None = None,
    ):
        self.db = db
        self.seed_ids = seed_author_ids
        self.max_depth = max_depth
        self.max_nodes = max_nodes
        self.top_k = top_k
        self.from_year = from_year
        self.to_year = to_year

        # State
        self._nodes: dict[str, dict] = {}      # id -> node data
        self._edges: list[dict] = []            # edge list
        self._visited: set[str] = set()         # already-expanded IDs
        self._uf = UnionFind()                  # connected components

        # Repos
        self._author_repo = AuthorRepository(db)
        self._collab_repo = CollaborationRepository(db)

    async def stream(self) -> AsyncGenerator[str, None]:
        """Main entry point — yields SSE-formatted strings."""
        ...
```

#### Algorithm: Modified Multi-Source BFS

```
1. INIT: Add all seed authors to queue at depth=0, emit `init` event
2. For each depth level d = 0..max_depth-1:
   a. For each author A in queue at depth d:
      - If A already visited, skip
      - If len(nodes) >= max_nodes, stop adding new nodes (still process edges)
      - Mark A as visited
      - Fetch top-K collaborators of A via AuthorRepository.get_collaborators()
      - For each collaborator C:
        - If C not in nodes dict AND len(nodes) < max_nodes: emit `node` event, add to nodes
        - If edge (A, C) not already emitted: emit `edge` event
        - Union(A, C) in Union-Find
        - If C not visited and d+1 <= max_depth and len(nodes) < max_nodes: add C to next-depth queue
      - Emit `progress` event
      - If all seeds connected (uf.all_seeds_connected): emit `connected` event
   b. After processing all authors at depth d, emit `component` events
   c. Early termination: if all seeds connected AND current_depth > 0, stop expansion
3. Emit `complete` event with all_connected flag
```

**Key design decisions**:
- **Per-author expansion, not batch**: We process one author at a time and emit events as we go. This gives the frontend smooth progressive updates.
- **Depth limit**: Default 2 (seed -> their collaborators -> those collaborators' collaborators). Max 3 to prevent explosion.
- **Max nodes guard**: Default 200 nodes. Prevents runaway expansion in dense graphs. Once hit, the algorithm stops adding new nodes but finishes processing current depth's edges.
- **Top-K pruning**: Only top-K collaborators (by collaboration_count) per author per level. Prevents dense graphs.
- **Deduplication**: The `_visited` set ensures we never expand the same author twice. The `_nodes` dict prevents duplicate node events.
- **Early termination**: When all seed authors are in the same connected component, the algorithm can stop early (after finishing the current depth level), since the user's primary goal — seeing how selected authors connect — has been achieved.

### 2.4 Union-Find: `src/api/services/union_find.py`

Lightweight Union-Find for tracking connected components in real-time as edges are added.

```python
class UnionFind:
    """Disjoint-set data structure with union-by-rank and path compression."""

    def __init__(self):
        self._parent: dict[str, str] = {}
        self._rank: dict[str, int] = {}

    def find(self, x: str) -> str:
        if x not in self._parent:
            self._parent[x] = x
            self._rank[x] = 0
        if self._parent[x] != x:
            self._parent[x] = self.find(self._parent[x])  # path compression
        return self._parent[x]

    def union(self, x: str, y: str) -> bool:
        """Returns True if x and y were in different components (i.e., a merge happened)."""
        rx, ry = self.find(x), self.find(y)
        if rx == ry:
            return False
        if self._rank[rx] < self._rank[ry]:
            rx, ry = ry, rx
        self._parent[ry] = rx
        if self._rank[rx] == self._rank[ry]:
            self._rank[rx] += 1
        return True

    def connected(self, x: str, y: str) -> bool:
        """Check if x and y are in the same component."""
        return self.find(x) == self.find(y)

    def all_seeds_connected(self, seeds: list[str]) -> bool:
        """Check if all seed nodes are in the same component."""
        if len(seeds) <= 1:
            return True
        root = self.find(seeds[0])
        return all(self.find(s) == root for s in seeds[1:])

    def components(self) -> dict[str, list[str]]:
        """Returns {root_id: [member_ids]} mapping."""
        groups: dict[str, list[str]] = {}
        for x in self._parent:
            root = self.find(x)
            groups.setdefault(root, []).append(x)
        return groups

    def component_count(self) -> int:
        return len(self.components())
```

**Why Union-Find**: The multi-author scenario requires detecting when separate author networks merge into one connected component. Union-Find gives us O(alpha(n)) amortized merge detection, and we can emit `component` events when merges happen (i.e., when `union()` returns `True`).

### 2.5 SSE Formatting Helper

Located in `src/api/services/network_builder.py` (private function):

```python
def _sse_event(event_type: str, data: dict) -> str:
    """Format a single SSE event string."""
    import json
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
```

### 2.6 Data Access Strategy

The `NetworkBuilder` reuses existing repository methods:

| Operation | Method | Notes |
|---|---|---|
| Get author by ID | `AuthorRepository.get_by_id(id)` | Already exists |
| Resolve canonical ID | `AuthorRepository.get_canonical_id(id)` | Already exists |
| Get collaborators | `AuthorRepository.get_collaborators(id, limit, from_year, to_year)` | Already exists, returns `list[tuple[Author, int]]` |
| Batch institution lookup | `AuthorRepository.batch_get_institution_frequencies(ids, 1)` | Already exists, use for enriching node data |

No new database queries or repository methods needed. The existing `get_collaborators()` method already handles alias expansion and year filtering.

---

## 3. Frontend Architecture

### 3.1 Route Changes

**File: `frontend/src/App.jsx`**

Keep existing routes, add a new multi-author route:

```
/network                  → NetworkPage (empty state, multi-author selector)
/network/:authorId        → NetworkPage (legacy single-author, auto-add as seed)
```

No new routes needed — the `NetworkPage` component becomes smarter.

### 3.2 Component Hierarchy

```
NetworkPage (refactored)
├── MultiAuthorSelector        (NEW - author chip input + search)
│   ├── SearchBox              (EXISTING - reused for author search)
│   └── AuthorChip[]           (NEW - removable chip per selected author)
├── NetworkControls            (NEW - depth/top-k sliders + expand button)
├── ProgressOverlay            (NEW - SSE progress display)
├── NetworkGraph               (EXISTING - enhanced for progressive updates)
├── NetworkSidebar             (NEW - replaces inline collaborator list)
│   ├── ComponentList          (NEW - connected components)
│   └── CollaboratorList       (EXISTING logic, extracted)
└── NetworkLegend              (NEW - extracted from NetworkPage inline JSX)
```

### 3.3 New Files

| File | Purpose |
|---|---|
| `frontend/src/components/MultiAuthorSelector.jsx` | Chip-based author selection with search |
| `frontend/src/components/NetworkControls.jsx` | Depth/top-k controls + "Build Network" button |
| `frontend/src/components/ProgressOverlay.jsx` | SSE progress bar + phase text |
| `frontend/src/components/NetworkSidebar.jsx` | Right sidebar with components + author list |
| `frontend/src/hooks/useNetworkStream.js` | SSE EventSource hook |

### 3.4 State Management

**No new context** — all state lives in `NetworkPage` and flows down via props. This follows the existing pattern (NetworkPage already manages `nodes`, `edges`, and `loading` locally).

#### NetworkPage State Shape

```javascript
// Seed authors (selected by user)
const [seedAuthors, setSeedAuthors] = useState([]);       // [{id, display_name, institution}]

// Network expansion parameters
const [depth, setDepth] = useState(2);
const [topK, setTopK] = useState(15);

// Progressive graph data (accumulated from SSE)
const [nodes, setNodes] = useState(new Map());             // Map<id, nodeData>
const [edges, setEdges] = useState([]);                    // [{from, to, weight, count}]
const [components, setComponents] = useState([]);          // [{id, author_ids, is_connected}]

// Stream state
const [streamState, setStreamState] = useState('idle');    // 'idle' | 'streaming' | 'complete' | 'error'
const [progress, setProgress] = useState(null);            // {depth, authors_processed, authors_total, phase}
const [error, setError] = useState(null);

// Legacy single-author support
const { authorId } = useParams();
```

### 3.5 Custom Hook: `useNetworkStream`

**File: `frontend/src/hooks/useNetworkStream.js`**

Encapsulates the SSE EventSource lifecycle.

```javascript
export function useNetworkStream() {
  const [state, setState] = useState('idle');        // 'idle' | 'connecting' | 'streaming' | 'complete' | 'error'
  const [progress, setProgress] = useState(null);
  const [error, setError] = useState(null);
  const eventSourceRef = useRef(null);
  const callbacksRef = useRef({});

  const connect = useCallback((params, callbacks) => {
    // params: { authorIds, maxDepth, topK, fromYear, toYear }
    // callbacks: { onNode, onEdge, onProgress, onConnected, onComponent, onComplete, onError }
    callbacksRef.current = callbacks;

    // Close existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const searchParams = new URLSearchParams({
      author_ids: params.authorIds.join(','),
      max_depth: params.maxDepth,
      top_k: params.topK,
    });
    if (params.fromYear) searchParams.set('from_year', params.fromYear);
    if (params.toYear) searchParams.set('to_year', params.toYear);

    const url = `/api/v1/network/expand?${searchParams}`;
    const es = new EventSource(url);
    eventSourceRef.current = es;

    setState('connecting');

    es.addEventListener('init', (e) => {
      setState('streaming');
      // no callback needed — init data is informational
    });

    es.addEventListener('node', (e) => {
      const data = JSON.parse(e.data);
      callbacksRef.current.onNode?.(data);
    });

    es.addEventListener('edge', (e) => {
      const data = JSON.parse(e.data);
      callbacksRef.current.onEdge?.(data);
    });

    es.addEventListener('progress', (e) => {
      const data = JSON.parse(e.data);
      setProgress(data);
      callbacksRef.current.onProgress?.(data);
    });

    es.addEventListener('component', (e) => {
      const data = JSON.parse(e.data);
      callbacksRef.current.onComponent?.(data);
    });

    es.addEventListener('connected', (e) => {
      const data = JSON.parse(e.data);
      callbacksRef.current.onConnected?.(data);
    });

    es.addEventListener('complete', (e) => {
      const data = JSON.parse(e.data);
      setState('complete');
      callbacksRef.current.onComplete?.(data);
      es.close();
    });

    es.addEventListener('error', (e) => {
      // SSE error event — could be network error or server-sent error
      if (e.data) {
        const data = JSON.parse(e.data);
        setError(data.message);
        callbacksRef.current.onError?.(data);
      } else {
        setError('Connection lost');
      }
      setState('error');
      es.close();
    });

    es.onerror = () => {
      // Browser-level connection error (different from SSE error event)
      if (es.readyState === EventSource.CLOSED) {
        // Only set error if we didn't already complete
        if (state !== 'complete') {
          setState('error');
          setError('Connection closed unexpectedly');
        }
      }
    };
  }, []);

  const disconnect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setState('idle');
    setProgress(null);
    setError(null);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  return { state, progress, error, connect, disconnect };
}
```

### 3.6 NetworkGraph Enhancement

**File: `frontend/src/components/NetworkGraph.jsx`**

The existing `NetworkGraph` component recreates the vis-network on every `nodes`/`edges` change. For progressive updates, we need incremental updates instead.

**Changes**:
- Accept a `progressive` boolean prop (default `false` for backward compat)
- When `progressive=true`, use `visNodes.add()` / `visEdges.add()` instead of recreating the network
- Expose `addNode(node)` and `addEdge(edge)` methods via `useImperativeHandle` + `forwardRef`
- Add color differentiation for seed nodes vs expanded nodes vs different depth levels

**Color scheme by depth**:
```javascript
const DEPTH_COLORS = [
  { background: '#2563EB', border: '#1E40AF' },  // depth 0: seed (blue-600)
  { background: '#8B5CF6', border: '#6D28D9' },  // depth 1: purple-500
  { background: '#EC4899', border: '#BE185D' },   // depth 2: pink-500
  { background: '#F97316', border: '#C2410C' },   // depth 3: orange-500
];
```

**Updated component signature**:
```jsx
const NetworkGraph = forwardRef(function NetworkGraph(
  { nodes, edges, centerNodeId, onNodeClick, progressive = false },
  ref
) {
  // ...existing code for non-progressive mode...

  // Imperative API for progressive mode
  useImperativeHandle(ref, () => ({
    addNode(nodeData) {
      if (visNodesRef.current) {
        visNodesRef.current.add(formatNode(nodeData));
      }
    },
    addEdge(edgeData) {
      if (visEdgesRef.current) {
        visEdgesRef.current.add(formatEdge(edgeData));
      }
    },
    fit() {
      if (networkRef.current) {
        networkRef.current.fit({ animation: { duration: 500, easingFunction: 'easeInOutQuad' } });
      }
    },
    clear() {
      if (visNodesRef.current) visNodesRef.current.clear();
      if (visEdgesRef.current) visEdgesRef.current.clear();
    },
  }));
});
```

### 3.7 NetworkPage Data Flow

```
User selects authors → clicks "Build Network"
       ↓
useNetworkStream.connect({authorIds, depth, topK})
       ↓
EventSource connects to /api/v1/network/expand?...
       ↓
┌─ SSE event: "node"  → graphRef.current.addNode(data) + setNodes(prev => new Map([...prev, [data.id, data]]))
├─ SSE event: "edge"  → graphRef.current.addEdge(data) + setEdges(prev => [...prev, data])
├─ SSE event: "progress" → setProgress(data) → ProgressOverlay updates
├─ SSE event: "component" → setComponents(data) → NetworkSidebar updates
└─ SSE event: "complete" → graphRef.current.fit() + setStreamState('complete')
```

### 3.8 MultiAuthorSelector Component

**File: `frontend/src/components/MultiAuthorSelector.jsx`**

Inline search + chip display. Reuses the `SearchBox` pattern but accumulates selections.

**Props**:
```jsx
{
  selectedAuthors,      // [{id, display_name, primary_institution_name}]
  onAdd,                // (author) => void
  onRemove,             // (authorId) => void
  maxAuthors,           // default 10
  disabled,             // boolean
}
```

**Behavior**:
- Text input with debounced search (300ms) using `api.searchAuthors(query, 10, 0, false, true)`
- Dropdown with search results (excludes already-selected authors)
- Clicking a result adds it as a chip
- Each chip shows author name + "x" remove button
- When `authorId` is in URL params, auto-add that author on mount (legacy compat)

### 3.9 ProgressOverlay Component

**File: `frontend/src/components/ProgressOverlay.jsx`**

Transparent overlay on the graph area during streaming.

**Props**: `{ state, progress }`

**Visual**:
- Semi-transparent backdrop with blur (like existing loading state)
- Animated progress bar: `(authors_processed / authors_total) * 100%`
- Phase text: "Initializing..." → "Expanding depth 1..." → "Expanding depth 2..." → "Analyzing components..."
- Spinner icon (reuse `Loader2` from lucide-react)
- Node/edge counters updating in real-time

---

## 4. File Change List

### New Files (Backend)

| File | Purpose |
|---|---|
| `src/api/routers/network.py` | SSE endpoint + request validation |
| `src/api/services/__init__.py` | Package init |
| `src/api/services/network_builder.py` | NetworkBuilder class + SSE formatter |
| `src/api/services/union_find.py` | Union-Find data structure |

### New Files (Frontend)

| File | Purpose |
|---|---|
| `frontend/src/components/MultiAuthorSelector.jsx` | Author chip selector |
| `frontend/src/components/NetworkControls.jsx` | Depth/top-k controls |
| `frontend/src/components/ProgressOverlay.jsx` | Streaming progress display |
| `frontend/src/components/NetworkSidebar.jsx` | Sidebar with components + author list |
| `frontend/src/hooks/useNetworkStream.js` | SSE EventSource hook |

### Modified Files

| File | Changes |
|---|---|
| `src/api/main.py` | Add `network.router` include (1 line) |
| `frontend/src/pages/NetworkPage.jsx` | Major refactor: multi-author state, SSE integration, new component composition |
| `frontend/src/components/NetworkGraph.jsx` | Add `forwardRef`, `useImperativeHandle`, progressive mode, depth colors |
| `frontend/src/api/client.js` | No changes needed (SSE uses native EventSource, not ApiClient) |
| `frontend/src/hooks/queries.js` | No changes needed (SSE doesn't use TanStack Query) |

---

## 5. Data Flow Diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND                                   │
│                                                                         │
│  ┌─────────────────┐    ┌──────────────┐    ┌────────────────────────┐ │
│  │ MultiAuthor     │───>│ NetworkPage  │───>│ useNetworkStream       │ │
│  │ Selector        │    │  (state hub) │    │  (EventSource hook)    │ │
│  └─────────────────┘    └──────┬───────┘    └────────┬───────────────┘ │
│                                │                     │                  │
│                    ┌───────────┼───────────┐         │ SSE connection  │
│                    │           │           │         │                  │
│              ┌─────┴───┐ ┌────┴────┐ ┌────┴──────┐  │                 │
│              │Progress │ │Network  │ │Network    │  │                  │
│              │Overlay  │ │Graph    │ │Sidebar    │  │                  │
│              └─────────┘ │(vis.js) │ └───────────┘  │                  │
│                          └─────────┘                │                  │
└──────────────────────────────────────────────────────┼──────────────────┘
                                                       │
                            GET /api/v1/network/expand?author_ids=A1,A2&...
                                                       │
┌──────────────────────────────────────────────────────┼──────────────────┐
│                              BACKEND                  │                  │
│                                                       ▼                  │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  network.py router                                               │   │
│  │  - Validates author_ids                                          │   │
│  │  - Creates NetworkBuilder(db, seed_ids, depth, top_k, years)    │   │
│  │  - Returns StreamingResponse(builder.stream())                   │   │
│  └──────────────────────────────┬───────────────────────────────────┘   │
│                                 │                                       │
│  ┌──────────────────────────────▼───────────────────────────────────┐   │
│  │  NetworkBuilder.stream()                                         │   │
│  │                                                                  │   │
│  │  1. emit init event                                              │   │
│  │  2. For depth 0..max_depth:                                      │   │
│  │     For each author in queue[depth]:                              │   │
│  │       collabs = AuthorRepo.get_collaborators(id, top_k, years)  │   │
│  │       For each collab:                                           │   │
│  │         if new: emit node event                                  │   │
│  │         emit edge event                                          │   │
│  │         UnionFind.union(author, collab)                          │   │
│  │       emit progress event                                        │   │
│  │     emit component events                                        │   │
│  │  3. emit complete event                                          │   │
│  └──────────────────────────────┬───────────────────────────────────┘   │
│                                 │                                       │
│         ┌───────────────────────┼────────────────────────┐              │
│         │                       │                        │              │
│  ┌──────▼──────┐  ┌────────────▼──────────┐  ┌─────────▼─────────┐   │
│  │ UnionFind   │  │ AuthorRepository      │  │ CollabRepository  │   │
│  │ (in-memory) │  │ .get_collaborators()  │  │ (not needed —     │   │
│  └─────────────┘  │ .get_by_id()          │  │  covered by       │   │
│                   │ .get_canonical_id()    │  │  AuthorRepo)      │   │
│                   │ .batch_get_inst_freq() │  └───────────────────┘   │
│                   └───────────┬────────────┘                           │
│                               │                                        │
│                   ┌───────────▼────────────┐                           │
│                   │     PostgreSQL          │                           │
│                   │  authors, authorships,  │                           │
│                   │  collaborations, works  │                           │
│                   └────────────────────────┘                           │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Implementation Notes

### 6.1 Backend: SSE with FastAPI

FastAPI doesn't have a first-class SSE abstraction, but `StreamingResponse` from Starlette works perfectly:

```python
from starlette.responses import StreamingResponse

@router.get("/expand")
async def expand_network(..., db: Session = Depends(get_db)):
    builder = NetworkBuilder(db, seed_ids, max_depth, max_nodes, top_k, from_year, to_year)
    return StreamingResponse(
        builder.stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
```

The `NetworkBuilder.stream()` method is an `async def` generator that `yield`s SSE-formatted strings.

### 6.2 Database Session Lifetime

The `get_db` dependency yields a session that lives for the duration of the request. Since SSE is a long-lived connection, the session stays open throughout the stream. This is fine because:
- Expansion is bounded (max_depth=3, top_k=50 → at most ~50^3 = 125K lookups, but pruning makes this far smaller)
- Typical expansion completes in seconds, not minutes
- The session is read-only (no writes)

### 6.3 Frontend: Batched State Updates

To avoid excessive re-renders, the `NetworkPage` should batch node/edge additions:

```javascript
// In the SSE callbacks:
const pendingNodes = useRef([]);
const pendingEdges = useRef([]);
const flushTimer = useRef(null);

const flushUpdates = useCallback(() => {
  if (pendingNodes.current.length > 0) {
    setNodes(prev => {
      const next = new Map(prev);
      for (const n of pendingNodes.current) next.set(n.id, n);
      return next;
    });
    // Also update vis-network directly
    for (const n of pendingNodes.current) {
      graphRef.current?.addNode(n);
    }
    pendingNodes.current = [];
  }
  if (pendingEdges.current.length > 0) {
    setEdges(prev => [...prev, ...pendingEdges.current]);
    for (const e of pendingEdges.current) {
      graphRef.current?.addEdge(e);
    }
    pendingEdges.current = [];
  }
}, []);

// Schedule flush every 100ms (batches ~10 events per frame at typical SSE speed)
const scheduleFlush = useCallback(() => {
  if (!flushTimer.current) {
    flushTimer.current = setTimeout(() => {
      flushUpdates();
      flushTimer.current = null;
    }, 100);
  }
}, [flushUpdates]);
```

### 6.4 Legacy Single-Author Compatibility

When `NetworkPage` mounts with a URL param `authorId`:
1. Fetch author details via `useAuthor(authorId)` (existing hook)
2. Auto-add to `seedAuthors` state
3. Show the MultiAuthorSelector pre-filled with that author
4. User can add more authors or click "Build Network" with just one (which falls back to the existing single-star behavior — server just does depth-1 BFS from one seed)

Wait — the server requires 2+ authors. For single-author backward compat, we have two options:
- **Option A**: Allow 1 author on the server (change validation to `ge=1`)
- **Option B**: Keep the existing client-side star graph for single author, only use SSE for 2+

**Decision: Option A** — allow 1+ authors. The algorithm works identically with 1 seed. This simplifies the frontend (one code path) and gives single-author mode the same progressive expansion UX.

### 6.5 vis-network Physics During Streaming

During progressive streaming, physics should run with relaxed settings to absorb new nodes smoothly:

```javascript
// When streaming starts:
network.setOptions({
  physics: {
    stabilization: { enabled: false },  // Don't wait for stabilization
    solver: 'forceAtlas2Based',
    forceAtlas2Based: {
      gravitationalConstant: -50,       // Weaker gravity = more spread
      springLength: 200,                // Longer springs = less cramped
      damping: 0.5,                     // More damping = less jitter
    },
  },
});

// When streaming completes:
network.stabilize(300);  // Final stabilization pass
network.fit({ animation: { duration: 800 } });
```

### 6.6 Error Handling

**Backend**: If a DB query fails mid-stream, emit an `error` event and close the generator:
```python
try:
    # ... expansion logic ...
except Exception as e:
    yield _sse_event("error", {"message": str(e), "code": "internal_error"})
    return
```

**Frontend**: On `error` event or `onerror`, show error toast via `sonner` (already in the project) and stop the progress overlay.

---

## 7. Testing Strategy

### Backend Tests (in `tests/test_api.py` or new `tests/test_network.py`)

1. **Unit: UnionFind** — test union, find, components, path compression
2. **Unit: NetworkBuilder** — mock `AuthorRepository`, verify SSE event sequence
3. **Integration: `/expand` endpoint** — test with real DB fixtures:
   - 2 seed authors with overlapping collaborators → verify merged graph
   - Invalid author ID → 404
   - Single author → works correctly
   - Year filtering → respects from_year/to_year

### Frontend Tests

Not in scope for this refactor — the project has no frontend test infrastructure. Manual testing via the dev server is sufficient.

---

## 8. Performance Considerations

| Concern | Mitigation |
|---|---|
| Large graph (depth=3, top_k=50) | Max ~50^3 = 125K potential lookups, but visited-set pruning + top-K limits keep practical sizes under 500 nodes |
| DB queries per author | 1 `get_collaborators()` query per unique author. With 100 nodes, ~100 queries over ~5-10 seconds |
| SSE connection timeout | Nginx default is 60s. Set `X-Accel-Buffering: no`. Typical expansion finishes in 2-15s |
| Frontend rendering | Batched vis-network updates (100ms flush interval) prevent frame drops |
| Memory | `_nodes` dict + `_edges` list + UnionFind — all in-memory, negligible for <1000 nodes |

---

## 9. Implementation Order

**Backend first, frontend second** — the SSE endpoint can be tested independently via `curl`.

1. **`src/api/services/union_find.py`** — standalone, no dependencies
2. **`src/api/services/network_builder.py`** — depends on union_find + existing repos
3. **`src/api/routers/network.py`** — depends on network_builder
4. **`src/api/main.py`** — 1-line router registration
5. **`frontend/src/hooks/useNetworkStream.js`** — standalone hook
6. **`frontend/src/components/MultiAuthorSelector.jsx`** — depends on existing SearchBox pattern
7. **`frontend/src/components/NetworkControls.jsx`** — simple UI
8. **`frontend/src/components/ProgressOverlay.jsx`** — simple UI
9. **`frontend/src/components/NetworkSidebar.jsx`** — simple UI
10. **`frontend/src/components/NetworkGraph.jsx`** — add progressive mode
11. **`frontend/src/pages/NetworkPage.jsx`** — final assembly

---

## 10. API Client Note

The SSE endpoint uses native `EventSource`, **not** the `ApiClient` class. This is because:
- `EventSource` is the browser's native SSE client
- It handles reconnection, parsing, and event dispatch automatically
- The `ApiClient.request()` method uses `fetch()` which returns a single response, not a stream
- No auth is needed for the network endpoint (it's public, like all author endpoints)

No changes to `frontend/src/api/client.js` are required.
