"""
FastAPI application for Coauthor Tracing System.
"""
import hashlib
import logging
import time
import uuid
from contextvars import ContextVar
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Depends, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from config.settings import settings
from src.database.models import init_database, get_session
from src.api.routers import admin, authors, network, system
from src.api.metrics import record_request, render_prometheus

# Structured logging with request ID
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIDFilter(logging.Filter):
    def filter(self, record):
        record.request_id = request_id_var.get("-")
        return True


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] [req:%(request_id)s] %(message)s",
    force=True,
)
for handler in logging.root.handlers:
    handler.addFilter(RequestIDFilter())

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting Coauthor Tracing API...")
    init_database()
    logger.info("Database initialized")

    yield

    # Shutdown
    logger.info("Shutting down Coauthor Tracing API...")


tags_metadata = [
    {"name": "authors", "description": "Author search, profiles, collaborators, and publication data"},
    {"name": "network", "description": "Collaboration network visualization with SSE streaming"},
    {"name": "system", "description": "System status, configuration, and health checks"},
    {"name": "admin", "description": "Admin dashboard, crawl management, and analytics"},
]


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title="CoAuthorTrace API",
        description="Academic co-authorship tracking and collaboration network analysis API. Powered by OpenAlex data and GraphSAGE GNN.",
        version="2.0.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        contact={"name": "CoAuthorTrace", "url": "https://github.com/MaxQ545/CoAuthorTrace"},
        license_info={"name": "MIT"},
        openapi_tags=tags_metadata,
    )

    # GZip compression (applied last = runs first in the middleware stack)
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )

    # Request ID + metrics middleware
    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        rid = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request_id_var.set(rid)
        start = time.time()
        response = await call_next(request)
        duration = time.time() - start
        response.headers["X-Request-ID"] = rid
        if request.url.path != "/metrics":
            record_request(request.method, request.url.path, response.status_code, duration)
        return response

    # Security headers middleware
    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response

    # ETag caching middleware — 304 for unchanged API JSON responses
    @app.middleware("http")
    async def etag_middleware(request: Request, call_next):
        response = await call_next(request)
        if request.method != "GET" or not request.url.path.startswith("/api/"):
            return response
        if response.status_code != 200:
            return response
        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type:
            return response
        body = b""
        async for chunk in response.body_iterator:
            body += chunk
        etag = f'W/"{hashlib.md5(body).hexdigest()[:16]}"'
        if request.headers.get("if-none-match") == etag:
            return Response(status_code=304, headers={"ETag": etag})
        return Response(
            content=body,
            status_code=response.status_code,
            headers={**dict(response.headers), "ETag": etag},
            media_type=response.media_type,
        )

    # Include routers
    app.include_router(
        authors.router,
        prefix="/api/v1/authors",
        tags=["authors"],
    )
    app.include_router(
        system.router,
        prefix="/api/v1/system",
        tags=["system"],
    )
    app.include_router(
        network.router,
        prefix="/api/v1/network",
        tags=["network"],
    )
    app.include_router(
        admin.router,
        prefix="/api/v1/admin",
        tags=["admin"],
    )

    @app.get("/")
    async def root():
        """Root endpoint."""
        return {
            "name": "CoAuthorTrace API",
            "version": "2.0.0",
            "docs": "/api/docs",
        }

    @app.get("/metrics", include_in_schema=False)
    async def metrics():
        """Prometheus-compatible metrics endpoint."""
        return Response(content=render_prometheus(), media_type="text/plain")

    @app.get("/health")
    async def health():
        """Health check endpoint with DB connectivity verification."""
        try:
            from sqlalchemy import text
            session = get_session()
            try:
                session.execute(text("SELECT 1"))
            finally:
                session.close()
        except Exception as e:
            return JSONResponse(
                status_code=503,
                content={"status": "unhealthy", "detail": str(e)},
            )
        return {"status": "healthy"}

    return app


# Create default app instance
app = create_app()


def run_server(
    host: Optional[str] = None,
    port: Optional[int] = None,
):
    """Run the API server."""
    import uvicorn

    host = host or settings.api.host
    port = port or settings.api.port

    uvicorn.run(
        "src.api.main:app",
        host=host,
        port=port,
        reload=False,
    )


if __name__ == "__main__":
    run_server()
