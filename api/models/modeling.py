"""
Pydantic models for the modeling API endpoints.

This module contains all request and response models for:
- Session management
- Schema discovery
- Data profiling
- Design generation
- Code generation
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# =============================================================================
# Enums
# =============================================================================

class ModelingStrategy(str, Enum):
    """Data modeling strategy options."""
    STAR_SCHEMA = "STAR_SCHEMA"
    NORMALIZED_3NF = "NORMALIZED_3NF"
    DATA_VAULT = "DATA_VAULT"


class SessionStatus(str, Enum):
    """Session status values."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


# =============================================================================
# Session Models
# =============================================================================

class CreateSessionRequest(BaseModel):
    """
    Request to create a new modeling session.

    A session represents a complete data modeling workflow from discovery
    through code generation.
    """

    project_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Name of the data modeling project",
        examples=["ecommerce_analytics", "customer_360"]
    )
    requirements: str = Field(
        ...,
        min_length=10,
        description="Business requirements describing the data model needs",
        examples=["Build a star schema for e-commerce analytics with sales facts and customer dimensions"]
    )
    data_source: str = Field(
        default="postgres",
        description="Data source identifier from MCP registry",
        examples=["postgres", "snowflake", "bigquery"]
    )
    modeling_strategy: ModelingStrategy = Field(
        default=ModelingStrategy.STAR_SCHEMA,
        description="Data modeling strategy to apply"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "project_name": "ecommerce_analytics",
                    "requirements": "Build a star schema for e-commerce analytics tracking sales, customers, and products",
                    "data_source": "postgres",
                    "modeling_strategy": "STAR_SCHEMA"
                }
            ]
        }
    }


class SessionResponse(BaseModel):
    """
    Response containing session information and status.
    """

    session_id: str = Field(
        ...,
        description="Unique identifier for the modeling session",
        examples=["550e8400-e29b-41d4-a716-446655440000"]
    )
    project_name: str = Field(
        ...,
        description="Name of the modeling project",
        examples=["ecommerce_analytics"]
    )
    data_source: str = Field(
        ...,
        description="Data source identifier",
        examples=["postgres"]
    )
    modeling_strategy: ModelingStrategy = Field(
        ...,
        description="Data modeling strategy"
    )
    status: SessionStatus = Field(
        ...,
        description="Current session status"
    )
    current_step: str = Field(
        ...,
        description="Current workflow step",
        examples=["initialized", "discovery", "profiling", "design", "generation"]
    )
    progress: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall progress as a percentage (0.0 to 1.0)",
        examples=[0.25, 0.5, 0.75, 1.0]
    )
    created_at: datetime = Field(
        ...,
        description="Timestamp when the session was created"
    )
    updated_at: datetime = Field(
        ...,
        description="Timestamp of last update"
    )
    errors: List[str] = Field(
        default_factory=list,
        description="List of errors encountered"
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="List of warnings"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "session_id": "550e8400-e29b-41d4-a716-446655440000",
                    "project_name": "ecommerce_analytics",
                    "data_source": "postgres",
                    "modeling_strategy": "STAR_SCHEMA",
                    "status": "in_progress",
                    "current_step": "design",
                    "progress": 0.5,
                    "created_at": "2024-01-15T10:30:00Z",
                    "updated_at": "2024-01-15T10:35:00Z",
                    "errors": [],
                    "warnings": []
                }
            ]
        }
    }


class SessionListResponse(BaseModel):
    """
    Response containing a list of sessions.
    """

    sessions: List[SessionResponse] = Field(
        default_factory=list,
        description="List of sessions"
    )
    total: int = Field(
        ...,
        ge=0,
        description="Total number of sessions"
    )


# =============================================================================
# Discovery Models
# =============================================================================

class DiscoveryRequest(BaseModel):
    """
    Request to discover schemas and tables from the data source.
    """

    schema_pattern: Optional[str] = Field(
        default=None,
        description="Regex pattern to filter schemas (e.g., 'public|staging')",
        examples=["public", "sales_*", "^(?!pg_).*$"]
    )
    exclude_system: bool = Field(
        default=True,
        description="Exclude system schemas (pg_catalog, information_schema, etc.)"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "schema_pattern": "public|staging",
                    "exclude_system": True
                }
            ]
        }
    }


class ColumnInfo(BaseModel):
    """
    Information about a single table column.
    """

    name: str = Field(
        ...,
        description="Column name",
        examples=["customer_id", "created_at", "total_amount"]
    )
    data_type: str = Field(
        ...,
        description="Database data type",
        examples=["integer", "varchar(255)", "timestamp with time zone", "numeric(10,2)"]
    )
    is_nullable: bool = Field(
        ...,
        description="Whether the column allows NULL values"
    )
    is_primary_key: bool = Field(
        ...,
        description="Whether the column is part of the primary key"
    )
    is_foreign_key: bool = Field(
        ...,
        description="Whether the column is a foreign key"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "customer_id",
                    "data_type": "integer",
                    "is_nullable": False,
                    "is_primary_key": True,
                    "is_foreign_key": False
                }
            ]
        }
    }


class SchemaInfo(BaseModel):
    """
    Information about a database schema.
    """

    name: str = Field(
        ...,
        description="Schema name",
        examples=["public", "sales", "staging"]
    )
    table_count: int = Field(
        ...,
        ge=0,
        description="Number of tables in the schema",
        examples=[15, 42]
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "public",
                    "table_count": 25
                }
            ]
        }
    }


class TableInfo(BaseModel):
    """
    Information about a database table including its columns.
    """

    schema_name: str = Field(
        ...,
        alias="schema",
        description="Schema containing the table",
        examples=["public", "sales"]
    )
    name: str = Field(
        ...,
        description="Table name",
        examples=["customers", "orders", "products"]
    )
    row_count: Optional[int] = Field(
        default=None,
        ge=0,
        description="Estimated row count (may be approximate)",
        examples=[10000, 1500000]
    )
    columns: List[ColumnInfo] = Field(
        default_factory=list,
        description="List of columns in the table"
    )

    model_config = {
        "populate_by_name": True,
        "json_schema_extra": {
            "examples": [
                {
                    "schema": "public",
                    "name": "customers",
                    "row_count": 50000,
                    "columns": [
                        {
                            "name": "id",
                            "data_type": "integer",
                            "is_nullable": False,
                            "is_primary_key": True,
                            "is_foreign_key": False
                        }
                    ]
                }
            ]
        }
    }


class DiscoveryResponse(BaseModel):
    """
    Response containing discovered schemas and tables.
    """

    schemas: List[SchemaInfo] = Field(
        default_factory=list,
        description="List of discovered schemas"
    )
    tables: List[TableInfo] = Field(
        default_factory=list,
        description="List of discovered tables with column information"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "schemas": [
                        {"name": "public", "table_count": 10},
                        {"name": "staging", "table_count": 5}
                    ],
                    "tables": [
                        {
                            "schema": "public",
                            "name": "customers",
                            "row_count": 50000,
                            "columns": []
                        }
                    ]
                }
            ]
        }
    }


# =============================================================================
# Profiling Models
# =============================================================================

class ProfileRequest(BaseModel):
    """
    Request to profile tables in a schema.

    Profiling analyzes data patterns, distributions, and quality metrics.
    """

    schema_name: str = Field(
        ...,
        alias="schema",
        description="Schema to profile",
        examples=["public", "sales"]
    )
    tables: Optional[List[str]] = Field(
        default=None,
        description="Specific tables to profile (None = all tables)",
        examples=[["customers", "orders"], None]
    )
    sample_size: int = Field(
        default=1000,
        ge=100,
        le=1000000,
        description="Number of rows to sample for profiling",
        examples=[1000, 10000]
    )

    model_config = {
        "populate_by_name": True,
        "json_schema_extra": {
            "examples": [
                {
                    "schema": "public",
                    "tables": ["customers", "orders"],
                    "sample_size": 5000
                }
            ]
        }
    }


class ColumnProfile(BaseModel):
    """
    Statistical profile of a single column.
    """

    column_name: str = Field(
        ...,
        description="Name of the profiled column",
        examples=["customer_id", "email", "total_amount"]
    )
    data_type: str = Field(
        ...,
        description="Database data type",
        examples=["integer", "varchar", "numeric"]
    )
    null_percentage: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Percentage of NULL values",
        examples=[0.0, 5.5, 25.3]
    )
    distinct_count: Optional[int] = Field(
        default=None,
        ge=0,
        description="Number of distinct values",
        examples=[100, 50000]
    )
    min_value: Optional[Any] = Field(
        default=None,
        description="Minimum value (for numeric/date types)",
        examples=[1, "2020-01-01", 0.01]
    )
    max_value: Optional[Any] = Field(
        default=None,
        description="Maximum value (for numeric/date types)",
        examples=[999999, "2024-12-31", 99999.99]
    )
    sample_values: List[Any] = Field(
        default_factory=list,
        description="Sample of actual values from the column",
        examples=[["value1", "value2", "value3"]]
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "column_name": "total_amount",
                    "data_type": "numeric",
                    "null_percentage": 2.5,
                    "distinct_count": 8500,
                    "min_value": 0.99,
                    "max_value": 15000.00,
                    "sample_values": [25.99, 149.99, 499.00]
                }
            ]
        }
    }


class TableProfile(BaseModel):
    """
    Complete profile of a table including all column profiles.
    """

    table_name: str = Field(
        ...,
        description="Name of the profiled table",
        examples=["customers", "orders"]
    )
    row_count: int = Field(
        ...,
        ge=0,
        description="Total number of rows in the table",
        examples=[50000, 1500000]
    )
    columns: List[ColumnProfile] = Field(
        default_factory=list,
        description="Profile for each column in the table"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "table_name": "orders",
                    "row_count": 100000,
                    "columns": [
                        {
                            "column_name": "order_id",
                            "data_type": "integer",
                            "null_percentage": 0.0,
                            "distinct_count": 100000,
                            "min_value": 1,
                            "max_value": 100000,
                            "sample_values": [1, 50000, 99999]
                        }
                    ]
                }
            ]
        }
    }


class ProfileResponse(BaseModel):
    """
    Response containing profiles for all requested tables.
    """

    profiles: Dict[str, TableProfile] = Field(
        default_factory=dict,
        description="Map of table name to table profile"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "profiles": {
                        "customers": {
                            "table_name": "customers",
                            "row_count": 50000,
                            "columns": []
                        }
                    }
                }
            ]
        }
    }


# =============================================================================
# Design Models
# =============================================================================

class DesignRequest(BaseModel):
    """
    Request to generate a data model design.

    Uses the discovery and profiling results to create an optimal design.
    """

    strategy: Optional[Literal["STAR_SCHEMA", "NORMALIZED_3NF", "DATA_VAULT"]] = Field(
        default=None,
        description="Override the modeling strategy (uses session default if not specified)"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "strategy": "STAR_SCHEMA"
                },
                {
                    "strategy": None
                }
            ]
        }
    }


class DesignResponse(BaseModel):
    """
    Response containing the generated data model design.
    """

    design: Dict[str, Any] = Field(
        ...,
        description="The complete data model design specification"
    )
    reasoning: str = Field(
        ...,
        description="AI-generated explanation of design decisions",
        examples=["Created a star schema with fact_sales at the center and dimension tables for customer, product, and time..."]
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "design": {
                        "facts": [
                            {
                                "name": "fact_sales",
                                "columns": ["sale_id", "customer_key", "product_key", "date_key", "amount"]
                            }
                        ],
                        "dimensions": [
                            {
                                "name": "dim_customer",
                                "columns": ["customer_key", "name", "email", "segment"]
                            }
                        ]
                    },
                    "reasoning": "Designed a star schema optimized for sales analytics with customer and product dimensions."
                }
            ]
        }
    }


# =============================================================================
# Generation Models
# =============================================================================

class GenerateRequest(BaseModel):
    """
    Request to generate code artifacts from the design.
    """

    output_path: Optional[str] = Field(
        default=None,
        description="Custom output path for generated files (uses workspace default if not specified)",
        examples=["/workspace/output", "./generated"]
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "output_path": "/workspace/generated"
                },
                {
                    "output_path": None
                }
            ]
        }
    }


class GeneratedFile(BaseModel):
    """
    Information about a single generated file.
    """

    path: str = Field(
        ...,
        description="Relative path to the generated file",
        examples=["models/dim_customer.sql", "models/fact_sales.py"]
    )
    content: str = Field(
        ...,
        description="The generated file content"
    )
    file_type: str = Field(
        ...,
        description="Type of generated file",
        examples=["sql", "python", "yaml", "dbt_model"]
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "path": "models/staging/stg_customers.sql",
                    "content": "SELECT id, name, email FROM {{ source('raw', 'customers') }}",
                    "file_type": "dbt_model"
                }
            ]
        }
    }


class GenerateResponse(BaseModel):
    """
    Response containing all generated code files.
    """

    files: List[GeneratedFile] = Field(
        default_factory=list,
        description="List of generated files"
    )
    total_files: int = Field(
        ...,
        ge=0,
        description="Total number of files generated",
        examples=[12, 25]
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "files": [
                        {
                            "path": "models/staging/stg_customers.sql",
                            "content": "-- Generated by DataForge\nSELECT * FROM {{ source('raw', 'customers') }}",
                            "file_type": "dbt_model"
                        }
                    ],
                    "total_files": 15
                }
            ]
        }
    }
