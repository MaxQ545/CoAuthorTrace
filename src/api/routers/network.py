"""
Network expansion API endpoints.

Provides a Server-Sent Events (SSE) endpoint for progressive
co-authorship network building from one or more seed authors.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import StreamingResponse

from src.database.models import get_session
from src.api.services.network_builder import (
    NetworkBuilder,
    DEFAULT_MAX_DEPTH,
    DEFAULT_MAX_NODES,
    DEFAULT_TOP_K,
    DEFAULT_MIN_COLLAB_COUNT,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/expand")
async def expand_network(
    author_ids: str = Query(
        ...,
        description="Comma-separated list of seed author IDs (e.g., A123,A456)",
    ),
    max_depth: int = Query(
        DEFAULT_MAX_DEPTH,
        ge=1,
        le=5,
        description="BFS expansion depth",
    ),
    max_nodes: int = Query(
        DEFAULT_MAX_NODES,
        ge=10,
        le=2000,
        description="Max nodes before stopping expansion",
    ),
    top_k: int = Query(
        DEFAULT_TOP_K,
        ge=5,
        le=100,
        description="Top collaborators per author per level",
    ),
    min_collab_count: int = Query(
        DEFAULT_MIN_COLLAB_COUNT,
        ge=1,
        le=100,
        description="Minimum co-authored papers to include an edge",
    ),
    from_year: Optional[int] = Query(
        None, ge=1900, le=2100, description="Filter collaborations from this year",
    ),
    to_year: Optional[int] = Query(
        None, ge=1900, le=2100, description="Filter collaborations to this year",
    ),
):
    """
    Progressively expand a co-authorship network via Server-Sent Events.

    The client receives a stream of SSE events as the network is built
    level-by-level using BFS from the seed authors.

    **Event types:**

    - `init` — seed author details and build parameters
    - `node` — each new author discovered
    - `edge` — each collaboration edge
    - `progress` — after each author expansion (depth, counts, phase)
    - `component` — connected component state after each depth level
    - `connected` — when all seeds merge into one component
    - `complete` — final summary (total nodes/edges/components, timing)
    - `error` — error details

    **Example usage (JavaScript):**

    ```js
    const es = new EventSource(
      '/api/v1/network/expand?author_ids=A123,A456&max_depth=2'
    );
    es.addEventListener('node', (e) => {
      const node = JSON.parse(e.data);
      graph.addNode(node);
    });
    es.addEventListener('edge', (e) => {
      const edge = JSON.parse(e.data);
      graph.addEdge(edge);
    });
    es.addEventListener('complete', () => es.close());
    ```
    """
    # Parse and validate seed IDs
    ids = [s.strip() for s in author_ids.split(",") if s.strip()]
    if not ids:
        raise HTTPException(
            status_code=400,
            detail="At least one seed author ID is required",
        )
    if len(ids) > 10:
        raise HTTPException(
            status_code=400,
            detail="Maximum 10 seed authors allowed",
        )

    async def _stream_with_session():
        db = get_session()
        try:
            builder = NetworkBuilder(
                db=db,
                seed_author_ids=ids,
                max_depth=max_depth,
                max_nodes=max_nodes,
                top_k=top_k,
                min_collab_count=min_collab_count,
                from_year=from_year,
                to_year=to_year,
            )
            async for event in builder.stream():
                yield event
        finally:
            db.close()

    return StreamingResponse(
        _stream_with_session(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # disable nginx buffering
        },
    )
