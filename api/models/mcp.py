"""
MCP-related API models.

Models for MCP server information and test responses.
"""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class MCPServerInfo(BaseModel):
    """Information about an MCP server."""

    name: str = Field(..., description="Server name")
    type: str = Field(..., description="Server type (database, tool, platform, api)")
    enabled: bool = Field(..., description="Whether the server is enabled")
    capabilities: List[str] = Field(
        default_factory=list, description="List of server capabilities"
    )
    healthy: Optional[bool] = Field(None, description="Health status")
    last_check: Optional[datetime] = Field(None, description="Last health check time")


class MCPServerListResponse(BaseModel):
    """Response containing list of MCP servers."""

    servers: Dict[str, MCPServerInfo] = Field(
        ..., description="Dictionary of server names to server info"
    )


class MCPServerTestResponse(BaseModel):
    """Response from testing an MCP server connection."""

    server_name: str = Field(..., description="Name of the tested server")
    success: bool = Field(..., description="Whether the test was successful")
    latency_ms: float = Field(..., description="Connection latency in milliseconds")
    error: Optional[str] = Field(None, description="Error message if test failed")
