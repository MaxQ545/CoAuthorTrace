"""
FastAPI application for Coauthor Tracing System.
"""
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from config.settings import settings
from src.database.models import init_database, get_session
from src.api.routers import admin, authors, network, system

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

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
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

    @app.get("/health")
    async def health():
        """Health check endpoint."""
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
