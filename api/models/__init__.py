"""
API Models for DataForge.

This module exports all Pydantic models used for API request validation
and response serialization.
"""

from api.models.common import (
    CapabilitiesResponse,
    ErrorResponse,
    HealthResponse,
    PaginatedResponse,
    StatusResponse,
)
from api.models.mcp import (
    MCPServerInfo,
    MCPServerListResponse,
    MCPServerTestResponse,
)
from api.models.modeling import (
    # Enums
    ModelingStrategy,
    SessionStatus,
    # Session models
    CreateSessionRequest,
    SessionResponse,
    SessionListResponse,
    # Discovery models
    ColumnInfo,
    DiscoverRequest,
    DiscoveryRequest,
    DiscoveryResponse,
    SchemaInfo,
    TableInfo,
    TablesResponse,
    # Profiling models
    ColumnProfile,
    ProfileRequest,
    ProfileResponse,
    ProfilingResponse,
    TableProfile,
    # Design models
    DesignRequest,
    DesignResponse,
    DesignUpdateRequest,
    # Generation models
    FileContentResponse,
    FileListResponse,
    GeneratedFile,
    GenerateRequest,
    GenerateResponse,
    GenerationResponse,
)

__all__ = [
    # Common models
    "CapabilitiesResponse",
    "ErrorResponse",
    "HealthResponse",
    "PaginatedResponse",
    "StatusResponse",
    # MCP models
    "MCPServerInfo",
    "MCPServerListResponse",
    "MCPServerTestResponse",
    # Enums
    "ModelingStrategy",
    "SessionStatus",
    # Session models
    "CreateSessionRequest",
    "SessionResponse",
    "SessionListResponse",
    # Discovery models
    "DiscoverRequest",
    "DiscoveryRequest",
    "SchemaInfo",
    "TableInfo",
    "ColumnInfo",
    "DiscoveryResponse",
    "TablesResponse",
    # Profiling models
    "ProfileRequest",
    "ColumnProfile",
    "TableProfile",
    "ProfileResponse",
    "ProfilingResponse",
    # Design models
    "DesignRequest",
    "DesignResponse",
    "DesignUpdateRequest",
    # Generation models
    "GenerateRequest",
    "GeneratedFile",
    "GenerateResponse",
    "GenerationResponse",
    "FileListResponse",
    "FileContentResponse",
]
