"""
Health and capability endpoints.

This module provides endpoints for health checks and capability discovery.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from api.models import CapabilitiesResponse, ErrorResponse, HealthResponse
from api.dependencies import get_mcp_registry
from core.mcp.registry import MCPRegistry
from core.utils.config import settings

router = APIRouter()


@router.get(
    "/",
    summary="Root endpoint",
    description="Returns basic API information and documentation links.",
    response_description="API information",
)
async def root() -> dict:
    """
    Root endpoint providing API information.

    Returns basic metadata about the DataForge API including
    version, status, and links to documentation.
    """
    return {
        "name": "DataForge API",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
        "redoc": "/redoc",
        "openapi": "/openapi.json",
    }


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Check the health status of the API and connected services.",
    response_description="Health status information",
)
async def health_check(
    mcp_registry: MCPRegistry = Depends(get_mcp_registry),
) -> HealthResponse:
    """
    Health check endpoint.

    Returns the current health status of the API including:
    - Overall status
    - Number of connected MCP servers
    - Current environment
    """
    mcp_status = {}
    if mcp_registry:
        mcp_status = mcp_registry.get_server_status()

    return HealthResponse(
        status="healthy",
        mcp_servers=len(mcp_status),
        environment=settings.dataforge_env,
    )


@router.get(
    "/capabilities",
    response_model=CapabilitiesResponse,
    responses={
        503: {"model": ErrorResponse, "description": "MCP registry not available"},
    },
    summary="Get capabilities",
    description="Get available capabilities from all registered MCP servers.",
    response_description="Available capabilities grouped by type",
)
async def get_capabilities(
    mcp_registry: MCPRegistry = Depends(get_mcp_registry),
) -> CapabilitiesResponse:
    """
    Get available capabilities from MCP servers.

    Returns a mapping of capability types to available servers:
    - data_sources: Database connections (postgres, mysql, etc.)
    - tools: Development tools (dbt, git, etc.)
    - platforms: Cloud platforms (aws, gcp, etc.)
    - apis: External API integrations
    """
    capabilities = await mcp_registry.get_capabilities()
    return CapabilitiesResponse(**capabilities)
