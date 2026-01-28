"""
API route aggregation.

This module aggregates all API routers into a single router
that can be included in the main FastAPI application.
"""

from fastapi import APIRouter

from .health import router as health_router
from .mcp import router as mcp_router
from .modeling import router as modeling_router

api_router = APIRouter()

# Health routes at root level (/, /health, /capabilities)
api_router.include_router(health_router, tags=["Health"])

# MCP server management routes
api_router.include_router(mcp_router, prefix="/mcp", tags=["MCP"])

# Modeling workflow routes
api_router.include_router(modeling_router, prefix="/modeling", tags=["Modeling"])
