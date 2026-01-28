"""
Common API models shared across all endpoints.

This module contains base response models used throughout the DataForge API.
"""

from typing import Any, Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field


T = TypeVar("T")


class ErrorResponse(BaseModel):
    """
    Standard error response format for API errors.

    Provides consistent error structure with machine-readable code
    and human-readable detail message.
    """

    detail: str = Field(
        ...,
        description="Human-readable error message",
        examples=["Session not found"]
    )
    code: str = Field(
        ...,
        description="Machine-readable error code",
        examples=["SESSION_NOT_FOUND", "VALIDATION_ERROR", "MCP_UNAVAILABLE"]
    )
    status_code: int = Field(
        ...,
        description="HTTP status code",
        ge=400,
        le=599,
        examples=[404, 500, 503]
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "detail": "Session not found",
                    "code": "SESSION_NOT_FOUND",
                    "status_code": 404
                }
            ]
        }
    }


class StatusResponse(BaseModel):
    """
    Generic status response for operations that don't return data.

    Used for confirmations, health checks, and simple acknowledgments.
    """

    status: str = Field(
        ...,
        description="Operation status",
        examples=["success", "healthy", "running"]
    )
    message: Optional[str] = Field(
        default=None,
        description="Optional additional message",
        examples=["Operation completed successfully"]
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "status": "success",
                    "message": "Operation completed successfully"
                }
            ]
        }
    }


class HealthResponse(BaseModel):
    """
    Health check response with service status information.
    """

    status: str = Field(
        ...,
        description="Overall health status",
        examples=["healthy", "degraded", "unhealthy"]
    )
    mcp_servers: int = Field(
        ...,
        ge=0,
        description="Number of connected MCP servers",
        examples=[3, 5]
    )
    environment: str = Field(
        ...,
        description="Current deployment environment",
        examples=["development", "staging", "production"]
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "status": "healthy",
                    "mcp_servers": 3,
                    "environment": "development"
                }
            ]
        }
    }


class CapabilitiesResponse(BaseModel):
    """
    Response containing available capabilities from MCP servers.
    """

    data_sources: List[str] = Field(
        default_factory=list,
        description="Available database connections",
        examples=[["postgres", "mysql", "snowflake"]]
    )
    tools: List[str] = Field(
        default_factory=list,
        description="Available development tools",
        examples=[["dbt", "git"]]
    )
    platforms: List[str] = Field(
        default_factory=list,
        description="Available cloud platforms",
        examples=[["aws", "gcp"]]
    )
    apis: List[str] = Field(
        default_factory=list,
        description="Available API integrations",
        examples=[[]]
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "data_sources": ["postgres", "snowflake"],
                    "tools": ["dbt", "git"],
                    "platforms": ["aws"],
                    "apis": []
                }
            ]
        }
    }


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Generic paginated response wrapper for list endpoints.

    Provides standard pagination metadata alongside the data items.
    """

    items: List[Any] = Field(
        ...,
        description="List of items for the current page"
    )
    total: int = Field(
        ...,
        description="Total number of items across all pages",
        ge=0,
        examples=[100]
    )
    page: int = Field(
        ...,
        description="Current page number (1-indexed)",
        ge=1,
        examples=[1]
    )
    page_size: int = Field(
        ...,
        description="Number of items per page",
        ge=1,
        le=1000,
        examples=[20]
    )

    @property
    def total_pages(self) -> int:
        """Calculate total number of pages."""
        if self.page_size == 0:
            return 0
        return (self.total + self.page_size - 1) // self.page_size

    @property
    def has_next(self) -> bool:
        """Check if there is a next page."""
        return self.page < self.total_pages

    @property
    def has_previous(self) -> bool:
        """Check if there is a previous page."""
        return self.page > 1

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "items": [{"id": 1}, {"id": 2}],
                    "total": 100,
                    "page": 1,
                    "page_size": 20
                }
            ]
        }
    }
