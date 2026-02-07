"""
FastAPI application for Coauthor Tracing System.
"""
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from config.settings import settings
from src.database.engine import init_database
from src.api.routers import authors, system

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting Coauthor Tracing API...")
    init_database()
    logger.info("Database initialized")
    yield
    logger.info("Shutting down Coauthor Tracing API...")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title="Coauthor Tracing API",
        description="API for tracking and analyzing paper co-authorship relationships",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    # GZip middleware (compress responses > 500 bytes)
    app.add_middleware(GZipMiddleware, minimum_size=500)

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
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

    @app.get("/")
    async def root():
        return {
            "name": "Coauthor Tracing API",
            "version": "1.0.0",
            "docs": "/api/docs",
        }

    @app.get("/health")
    async def health():
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
