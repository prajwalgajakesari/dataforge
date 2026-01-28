"""
FastAPI server for DataForge.

This module provides the REST API for DataForge data modeling workflows.
Routes are organized into modular routers in the api/routes/ directory.
"""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.dependencies import (
    init_dependencies,
    reset_dependencies,
    InMemorySessionStore,
)
from api.routes import api_router
from core.mcp.registry import MCPRegistry
from core.utils.config import settings
from core.utils.logger import setup_logger

logger = setup_logger("dataforge.api", level=settings.dataforge_log_level)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Lifespan context manager for FastAPI.
    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting DataForge API server")

    # Initialize MCP registry
    mcp_registry = MCPRegistry()
    await mcp_registry.initialize()
    logger.info("MCP registry initialized")

    # Initialize session store
    session_store = InMemorySessionStore()
    logger.info("Session store initialized")

    # Initialize dependencies for injection
    init_dependencies(mcp_registry, session_store)
    logger.info("Dependencies initialized")

    yield

    # Shutdown
    logger.info("Shutting down DataForge API server")
    await mcp_registry.shutdown()
    reset_dependencies()


# Create FastAPI app
app = FastAPI(
    title="DataForge API",
    description="AI-powered data engineering platform API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all routers
app.include_router(api_router, prefix="/api/v1")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api.server:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
        log_level=settings.dataforge_log_level.lower(),
    )
