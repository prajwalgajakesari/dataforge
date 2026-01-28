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
    DiscoveryRequest,
    DiscoveryResponse,
    SchemaInfo,
    TableInfo,
    # Profiling models
    ColumnProfile,
    ProfileRequest,
    ProfileResponse,
    TableProfile,
    # Design models
    DesignRequest,
    DesignResponse,
    # Generation models
    GeneratedFile,
    GenerateRequest,
    GenerateResponse,
)

__all__ = [
    # Common models
    "CapabilitiesResponse",
    "ErrorResponse",
    "HealthResponse",
    "PaginatedResponse",
    "StatusResponse",
    # Enums
    "ModelingStrategy",
    "SessionStatus",
    # Session models
    "CreateSessionRequest",
    "SessionResponse",
    "SessionListResponse",
    # Discovery models
    "DiscoveryRequest",
    "SchemaInfo",
    "TableInfo",
    "ColumnInfo",
    "DiscoveryResponse",
    # Profiling models
    "ProfileRequest",
    "ColumnProfile",
    "TableProfile",
    "ProfileResponse",
    # Design models
    "DesignRequest",
    "DesignResponse",
    # Generation models
    "GenerateRequest",
    "GeneratedFile",
    "GenerateResponse",
]
