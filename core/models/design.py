"""
Models for data model design specifications.

This module provides Pydantic models for representing data model designs
including:
- Modeling strategies (Star Schema, Snowflake, Data Vault, etc.)
- Table roles (Fact, Dimension, Hub, Link, Satellite, etc.)
- Column roles (Surrogate Key, Natural Key, Measure, etc.)
- Slowly Changing Dimension (SCD) types
- Complete model design specifications

All models are JSON serializable and use Pydantic v2 conventions.
"""

from pydantic import BaseModel, Field, field_validator, computed_field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime


class ModelingStrategy(str, Enum):
    """
    Data modeling strategy options.

    Defines the overall approach to structuring the data model,
    each with different trade-offs for query performance, storage,
    and maintainability.
    """
    STAR_SCHEMA = "star_schema"        # Denormalized, fast queries
    SNOWFLAKE = "snowflake"            # Normalized dimensions
    NORMALIZED_3NF = "normalized_3nf"  # Third normal form
    DATA_VAULT = "data_vault"          # Hub, Link, Satellite
    ONE_BIG_TABLE = "one_big_table"    # Fully denormalized


class SCDType(int, Enum):
    """
    Slowly Changing Dimension types.

    Defines how historical changes to dimension data are tracked
    in the data warehouse.
    """
    TYPE_0 = 0  # Fixed dimension, no changes tracked
    TYPE_1 = 1  # Overwrite old values with new
    TYPE_2 = 2  # Track history with new rows
    TYPE_3 = 3  # Track previous value in separate column


class TableRole(str, Enum):
    """
    Role of a table in the data model.

    The role determines how the table functions within the overall
    data model architecture.
    """
    # Star Schema / Dimensional Modeling
    FACT = "fact"              # Contains measures and foreign keys
    DIMENSION = "dimension"    # Contains descriptive attributes
    BRIDGE = "bridge"          # Many-to-many relationship resolver

    # Data Vault
    HUB = "hub"                # Business keys
    LINK = "link"              # Relationships between hubs
    SATELLITE = "satellite"    # Descriptive attributes

    # General / Operational
    STAGING = "staging"        # Raw data landing zone
    ENTITY = "entity"          # Normalized entity table
    JUNCTION = "junction"      # Many-to-many resolver (generic)
    LOOKUP = "lookup"          # Reference/lookup data


class ColumnRole(str, Enum):
    """
    Role of a column in the data model.

    The role indicates the semantic purpose of the column
    within the table and overall model.
    """
    SURROGATE_KEY = "surrogate_key"              # System-generated unique ID
    NATURAL_KEY = "natural_key"                  # Business-meaningful unique ID
    BUSINESS_KEY = "business_key"                # Key identifying business entity
    FOREIGN_KEY = "foreign_key"                  # Reference to another table
    MEASURE = "measure"                          # Numeric value for aggregation
    ATTRIBUTE = "attribute"                      # Descriptive attribute
    DEGENERATE_DIMENSION = "degenerate_dimension"  # Dimension in fact table
    AUDIT = "audit"                              # Tracking columns (created_at, etc.)


class DesignedColumn(BaseModel):
    """
    A column in the designed data model.

    Represents a column specification including its source mapping,
    data type, role, constraints, and any transformations.

    Attributes:
        name: Column name in the target model.
        source_column: Original column name (if mapped from source).
        source_table: Original table name (if mapped from source).
        data_type: Target data type.
        role: Semantic role of the column.
    """
    name: str = Field(min_length=1, description="Column name")
    source_column: Optional[str] = Field(
        default=None,
        description="Original source column name"
    )
    source_table: Optional[str] = Field(
        default=None,
        description="Original source table name"
    )
    data_type: str = Field(min_length=1, description="Data type")

    # Role and classification
    role: ColumnRole = Field(
        default=ColumnRole.ATTRIBUTE,
        description="Semantic role of the column"
    )
    is_nullable: bool = Field(default=True, description="Whether column allows nulls")
    is_primary_key: bool = Field(
        default=False,
        description="Whether column is part of primary key"
    )

    # For foreign keys
    references_table: Optional[str] = Field(
        default=None,
        description="Referenced table for foreign keys"
    )
    references_column: Optional[str] = Field(
        default=None,
        description="Referenced column for foreign keys"
    )

    # Transformation
    transformation: Optional[str] = Field(
        default=None,
        description="SQL expression if transformed"
    )

    # Documentation
    description: Optional[str] = Field(
        default=None,
        description="Column description"
    )

    @computed_field
    @property
    def is_key(self) -> bool:
        """Return True if the column is any type of key."""
        return self.role in {
            ColumnRole.SURROGATE_KEY,
            ColumnRole.NATURAL_KEY,
            ColumnRole.BUSINESS_KEY,
            ColumnRole.FOREIGN_KEY
        }

    @computed_field
    @property
    def is_derived(self) -> bool:
        """Return True if the column has a transformation applied."""
        return self.transformation is not None

    @computed_field
    @property
    def source_reference(self) -> Optional[str]:
        """Return the fully qualified source reference if available."""
        if self.source_table and self.source_column:
            return f"{self.source_table}.{self.source_column}"
        return self.source_column

    @field_validator("references_table", "references_column")
    @classmethod
    def validate_references(cls, v: Optional[str], info) -> Optional[str]:
        """Ensure both reference fields are set together."""
        return v

    def to_ddl(self, dialect: str = "standard") -> str:
        """
        Generate DDL fragment for this column.

        Args:
            dialect: SQL dialect ('standard', 'postgresql', 'mysql', etc.)

        Returns:
            DDL string for the column definition.
        """
        parts = [self.name, self.data_type]

        if not self.is_nullable:
            parts.append("NOT NULL")

        if self.is_primary_key:
            parts.append("PRIMARY KEY")

        return " ".join(parts)

    model_config = {"frozen": False, "extra": "forbid"}


class DesignedTable(BaseModel):
    """
    A table in the designed data model.

    Represents a complete table specification including its role,
    columns, source mapping, and documentation.

    Attributes:
        name: Table name in the target model.
        role: Role of the table in the data model.
        columns: List of column specifications.
        source_tables: Source tables this table is derived from.
    """
    name: str = Field(min_length=1, description="Table name")
    role: TableRole = Field(description="Role of the table in the model")
    columns: List[DesignedColumn] = Field(
        default_factory=list,
        description="Column specifications"
    )

    # Source mapping
    source_tables: List[str] = Field(
        default_factory=list,
        description="Source tables this table derives from"
    )

    # For dimensions
    scd_type: Optional[SCDType] = Field(
        default=None,
        description="SCD type for dimension tables"
    )

    # For facts
    grain: Optional[str] = Field(
        default=None,
        description="Grain description (e.g., 'one row per order line item')"
    )
    measures: List[str] = Field(
        default_factory=list,
        description="Measure column names"
    )
    dimension_keys: List[str] = Field(
        default_factory=list,
        description="Foreign key column names to dimensions"
    )

    # Documentation
    description: Optional[str] = Field(
        default=None,
        description="Table description"
    )

    @computed_field
    @property
    def primary_key_columns(self) -> List[str]:
        """Return the list of primary key column names."""
        return [c.name for c in self.columns if c.is_primary_key]

    @computed_field
    @property
    def foreign_key_columns(self) -> List[str]:
        """Return the list of foreign key column names."""
        return [c.name for c in self.columns if c.role == ColumnRole.FOREIGN_KEY]

    @computed_field
    @property
    def column_count(self) -> int:
        """Return the number of columns."""
        return len(self.columns)

    @computed_field
    @property
    def is_fact_table(self) -> bool:
        """Return True if this is a fact table."""
        return self.role == TableRole.FACT

    @computed_field
    @property
    def is_dimension_table(self) -> bool:
        """Return True if this is a dimension table."""
        return self.role == TableRole.DIMENSION

    def get_column(self, column_name: str) -> Optional[DesignedColumn]:
        """
        Get a column by name.

        Args:
            column_name: Name of the column.

        Returns:
            The column if found, None otherwise.
        """
        for col in self.columns:
            if col.name == column_name:
                return col
        return None

    def get_columns_by_role(self, role: ColumnRole) -> List[DesignedColumn]:
        """
        Get all columns with a specific role.

        Args:
            role: The column role to filter by.

        Returns:
            List of columns with the specified role.
        """
        return [c for c in self.columns if c.role == role]

    def add_column(self, column: DesignedColumn) -> None:
        """
        Add a column to the table.

        Args:
            column: The column to add.
        """
        self.columns.append(column)

    model_config = {"frozen": False, "extra": "forbid"}


class DesignedRelationship(BaseModel):
    """
    A relationship between tables in the designed model.

    Represents a foreign key relationship including cardinality
    and whether the relationship is required.

    Attributes:
        name: Descriptive name for the relationship.
        from_table: Source table name (has the foreign key).
        from_columns: Source column names.
        to_table: Target table name (has the primary/unique key).
        to_columns: Target column names.
    """
    name: str = Field(min_length=1, description="Relationship name")
    from_table: str = Field(min_length=1, description="Source table")
    from_columns: List[str] = Field(
        min_length=1,
        description="Source columns"
    )
    to_table: str = Field(min_length=1, description="Target table")
    to_columns: List[str] = Field(
        min_length=1,
        description="Target columns"
    )

    # Cardinality
    cardinality: str = Field(
        default="N:1",
        description="Relationship cardinality: '1:1', '1:N', 'N:1', 'N:M'"
    )
    is_required: bool = Field(
        default=False,
        description="Whether the relationship is required (NOT NULL)"
    )

    @field_validator("cardinality")
    @classmethod
    def validate_cardinality(cls, v: str) -> str:
        """Validate cardinality is one of the allowed values."""
        allowed = {"1:1", "1:N", "N:1", "N:M"}
        if v not in allowed:
            raise ValueError(f"Cardinality must be one of {allowed}, got '{v}'")
        return v

    @computed_field
    @property
    def is_composite(self) -> bool:
        """Return True if this is a composite key relationship."""
        return len(self.from_columns) > 1

    @computed_field
    @property
    def column_mapping(self) -> Dict[str, str]:
        """Return a mapping from source to target columns."""
        return dict(zip(self.from_columns, self.to_columns))

    def __str__(self) -> str:
        """Return string representation of the relationship."""
        from_cols = ", ".join(self.from_columns)
        to_cols = ", ".join(self.to_columns)
        return f"{self.from_table}({from_cols}) -> {self.to_table}({to_cols}) [{self.cardinality}]"

    model_config = {"frozen": False, "extra": "forbid"}


class ModelDesign(BaseModel):
    """
    Complete data model design specification.

    Represents a full data model design including all tables,
    relationships, and design metadata.

    Attributes:
        name: Name of the model design.
        strategy: The modeling strategy used.
        tables: List of designed tables.
        relationships: List of relationships between tables.
    """
    name: str = Field(min_length=1, description="Model name")
    strategy: ModelingStrategy = Field(description="Modeling strategy")

    # Tables and relationships
    tables: List[DesignedTable] = Field(
        default_factory=list,
        description="Designed tables"
    )
    relationships: List[DesignedRelationship] = Field(
        default_factory=list,
        description="Relationships between tables"
    )

    # Metadata
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Creation timestamp"
    )
    version: str = Field(default="1.0", description="Design version")

    # Design rationale
    design_notes: Optional[str] = Field(
        default=None,
        description="Notes about design decisions"
    )
    assumptions: List[str] = Field(
        default_factory=list,
        description="Design assumptions"
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Design warnings and caveats"
    )

    # Source reference
    source_schema: Optional[str] = Field(
        default=None,
        description="Source schema name"
    )
    source_tables: List[str] = Field(
        default_factory=list,
        description="Source table names"
    )

    @computed_field
    @property
    def table_count(self) -> int:
        """Return the total number of tables."""
        return len(self.tables)

    @computed_field
    @property
    def relationship_count(self) -> int:
        """Return the total number of relationships."""
        return len(self.relationships)

    def get_facts(self) -> List[DesignedTable]:
        """
        Get all fact tables in the model.

        Returns:
            List of fact tables.
        """
        return [t for t in self.tables if t.role == TableRole.FACT]

    def get_dimensions(self) -> List[DesignedTable]:
        """
        Get all dimension tables in the model.

        Returns:
            List of dimension tables.
        """
        return [t for t in self.tables if t.role == TableRole.DIMENSION]

    def get_hubs(self) -> List[DesignedTable]:
        """
        Get all hub tables (Data Vault).

        Returns:
            List of hub tables.
        """
        return [t for t in self.tables if t.role == TableRole.HUB]

    def get_links(self) -> List[DesignedTable]:
        """
        Get all link tables (Data Vault).

        Returns:
            List of link tables.
        """
        return [t for t in self.tables if t.role == TableRole.LINK]

    def get_satellites(self) -> List[DesignedTable]:
        """
        Get all satellite tables (Data Vault).

        Returns:
            List of satellite tables.
        """
        return [t for t in self.tables if t.role == TableRole.SATELLITE]

    def get_table(self, name: str) -> Optional[DesignedTable]:
        """
        Get a table by name.

        Args:
            name: Table name.

        Returns:
            The table if found, None otherwise.
        """
        for table in self.tables:
            if table.name == name:
                return table
        return None

    def get_tables_by_role(self, role: TableRole) -> List[DesignedTable]:
        """
        Get all tables with a specific role.

        Args:
            role: The table role to filter by.

        Returns:
            List of tables with the specified role.
        """
        return [t for t in self.tables if t.role == role]

    def get_relationships_for_table(self, table_name: str) -> List[DesignedRelationship]:
        """
        Get all relationships involving a table.

        Args:
            table_name: Name of the table.

        Returns:
            List of relationships involving the table.
        """
        return [
            r for r in self.relationships
            if r.from_table == table_name or r.to_table == table_name
        ]

    def add_table(self, table: DesignedTable) -> None:
        """
        Add a table to the model.

        Args:
            table: The table to add.
        """
        self.tables.append(table)

    def add_relationship(self, relationship: DesignedRelationship) -> None:
        """
        Add a relationship to the model.

        Args:
            relationship: The relationship to add.
        """
        self.relationships.append(relationship)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the model to a dictionary.

        Returns:
            Dictionary representation of the model.
        """
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelDesign":
        """
        Create a model from a dictionary.

        Args:
            data: Dictionary containing model data.

        Returns:
            A new ModelDesign instance.
        """
        return cls.model_validate(data)

    model_config = {"frozen": False, "extra": "forbid"}
