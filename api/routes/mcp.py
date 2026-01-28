"""
MCP server management endpoints.

This module provides endpoints for listing, inspecting, and testing
MCP (Model Context Protocol) server connections.
"""

from datetime import datetime
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, status

from api.models import (
    ErrorResponse,
    MCPServerInfo,
    MCPServerListResponse,
    MCPServerTestResponse,
)
from api.dependencies import get_mcp_registry
from core.mcp.registry import MCPRegistry

router = APIRouter()


@router.get(
    "/servers",
    response_model=MCPServerListResponse,
    responses={
        503: {"model": ErrorResponse, "description": "MCP registry not available"},
    },
    summary="List MCP servers",
    description="Get a list of all registered MCP servers and their status.",
    response_description="Dictionary of server names to server information",
)
async def list_servers(
    mcp_registry: MCPRegistry = Depends(get_mcp_registry),
) -> MCPServerListResponse:
    """
    List all registered MCP servers.

    Returns information about each server including:
    - Server type (database, tool, platform, api)
    - Whether the server is enabled
    - Available capabilities
    - Health status and last check time
    """
    if not mcp_registry:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MCP registry not initialized",
        )

    server_status = mcp_registry.get_server_status()

    servers: Dict[str, MCPServerInfo] = {}
    for name, info in server_status.items():
        servers[name] = MCPServerInfo(
            name=name,
            type=info["type"],
            enabled=info["enabled"],
            capabilities=info.get("capabilities", []),
            healthy=info.get("healthy"),
            last_check=info.get("last_check"),
        )

    return MCPServerListResponse(servers=servers)


@router.get(
    "/servers/{name}",
    response_model=MCPServerInfo,
    responses={
        404: {"model": ErrorResponse, "description": "Server not found"},
        503: {"model": ErrorResponse, "description": "MCP registry not available"},
    },
    summary="Get MCP server info",
    description="Get detailed information about a specific MCP server.",
    response_description="Server information including configuration and status",
)
async def get_server(
    name: str,
    mcp_registry: MCPRegistry = Depends(get_mcp_registry),
) -> MCPServerInfo:
    """
    Get information about a specific MCP server.

    Args:
        name: The name of the MCP server to retrieve

    Returns:
        Detailed information about the requested server

    Raises:
        HTTPException: 404 if server not found, 503 if registry unavailable
    """
    if not mcp_registry:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MCP registry not initialized",
        )

    if name not in mcp_registry.servers:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MCP server '{name}' not found",
        )

    config = mcp_registry.servers[name]
    health = mcp_registry.health_status.get(name)

    return MCPServerInfo(
        name=name,
        type=config.type,
        enabled=config.enabled,
        capabilities=config.capabilities,
        healthy=health.healthy if health else None,
        last_check=health.last_check if health else None,
    )


@router.post(
    "/servers/{name}/test",
    response_model=MCPServerTestResponse,
    status_code=status.HTTP_200_OK,
    responses={
        404: {"model": ErrorResponse, "description": "Server not found"},
        503: {"model": ErrorResponse, "description": "MCP registry not available"},
    },
    summary="Test MCP server connection",
    description="Test the connection to a specific MCP server and return the result.",
    response_description="Connection test result including latency",
)
async def test_server(
    name: str,
    mcp_registry: MCPRegistry = Depends(get_mcp_registry),
) -> MCPServerTestResponse:
    """
    Test the connection to an MCP server.

    Performs a health check on the specified server and returns
    the result including connection latency.

    Args:
        name: The name of the MCP server to test

    Returns:
        Test result with success status and latency

    Raises:
        HTTPException: 404 if server not found, 503 if registry unavailable
    """
    if not mcp_registry:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MCP registry not initialized",
        )

    if name not in mcp_registry.servers:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MCP server '{name}' not found",
        )

    # Perform health check
    start_time = datetime.now()

    try:
        is_healthy = await mcp_registry.health_check(name)
        end_time = datetime.now()
        latency_ms = (end_time - start_time).total_seconds() * 1000

        health = mcp_registry.health_status.get(name)
        error = health.error if health and not is_healthy else None

        return MCPServerTestResponse(
            server_name=name,
            success=is_healthy,
            latency_ms=latency_ms,
            error=error,
        )

    except Exception as e:
        end_time = datetime.now()
        latency_ms = (end_time - start_time).total_seconds() * 1000

        return MCPServerTestResponse(
            server_name=name,
            success=False,
            latency_ms=latency_ms,
            error=str(e),
        )
