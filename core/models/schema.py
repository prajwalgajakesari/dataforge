"""
Core domain models for database schema representation.

This module provides the canonical representation of database schemas, tables,
columns, relationships, and constraints used throughout the DataForge system.

These models serve as the internal domain representation, distinct from:
- API-level models (api/models/modeling.py)
- Generation-level models (core/generators/dbt_generator.py)
- MCP-level models (core/mcp/servers/postgres_mcp.py)
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ConstraintType(str, Enum):
    """Database constraint types."""

    PRIMARY_KEY = "primary_key"
    FOREIGN_KEY = "foreign_key"
    UNIQUE = "unique"
    CHECK = "check"
    NOT_NULL = "not_null"
    DEFAULT = "default"
    EXCLUSION = "exclusion"


class IndexType(str, Enum):
    """Database index types (PostgreSQL-focused)."""

    BTREE = "btree"
    HASH = "hash"
    GIN = "gin"
    GIST = "gist"
    BRIN = "brin"
    SPGIST = "spgist"


class ReferentialAction(str, Enum):
    """Referential actions for foreign key constraints."""

    NO_ACTION = "NO ACTION"
    RESTRICT = "RESTRICT"
    CASCADE = "CASCADE"
    SET_NULL = "SET NULL"
    SET_DEFAULT = "SET DEFAULT"


class Constraint(BaseModel):
    """
    Database constraint definition.

    Represents all types of database constraints including primary keys,
    foreign keys, unique constraints, check constraints, and defaults.

    Attributes:
        name: Constraint name in the database.
        type: Type of constraint (primary_key, foreign_key, etc.).
        columns: List of column names involved in the constraint.
        expression: SQL expression for CHECK constraints.
        reference_table: Referenced table for foreign key constraints.
        reference_columns: Referenced columns for foreign key constraints.
        reference_schema: Schema of the referenced table.
        on_delete: Referential action on delete (CASCADE, SET NULL, etc.).
        on_update: Referential action on update.
        is_deferrable: Whether the constraint can be deferred.
        is_deferred: Whether the constraint is initially deferred.
    """

    model_config = ConfigDict(
        frozen=False,
        validate_assignment=True,
        extra="forbid",
    )

    name: str = Field(..., min_length=1, description="Constraint name")
    type: ConstraintType = Field(..., description="Type of constraint")
    columns: List[str] = Field(
        default_factory=list,
        description="Column names in the constraint"
    )
    expression: Optional[str] = Field(
        default=None,
        description="SQL expression for CHECK constraints"
    )
    reference_table: Optional[str] = Field(
        default=None,
        description="Referenced table for foreign keys"
    )
    reference_columns: Optional[List[str]] = Field(
        default=None,
        description="Referenced columns for foreign keys"
    )
    reference_schema: Optional[str] = Field(
        default=None,
        description="Schema of the referenced table"
    )
    on_delete: Optional[ReferentialAction] = Field(
        default=None,
        description="Referential action on delete"
    )
    on_update: Optional[ReferentialAction] = Field(
        default=None,
        description="Referential action on update"
    )
    is_deferrable: bool = Field(
        default=False,
        description="Whether constraint can be deferred"
    )
    is_deferred: bool = Field(
        default=False,
        description="Whether constraint is initially deferred"
    )

    @model_validator(mode="after")
    def validate_foreign_key_fields(self) -> "Constraint":
        """Validate that foreign key constraints have required reference fields."""
        if self.type == ConstraintType.FOREIGN_KEY:
            if not self.reference_table:
                raise ValueError(
                    "Foreign key constraints must specify reference_table"
                )
            if not self.reference_columns:
                raise ValueError(
                    "Foreign key constraints must specify reference_columns"
                )
        return self

    @model_validator(mode="after")
    def validate_check_expression(self) -> "Constraint":
        """Validate that check constraints have an expression."""
        if self.type == ConstraintType.CHECK and not self.expression:
            raise ValueError("CHECK constraints must specify an expression")
        return self


class Index(BaseModel):
    """
    Database index definition.

    Represents database indexes including B-tree, hash, GIN, GiST, and BRIN indexes.

    Attributes:
        name: Index name in the database.
        columns: List of column names in the index.
        type: Index type (btree, hash, gin, etc.).
        is_unique: Whether the index enforces uniqueness.
        is_primary: Whether this is the primary key index.
        is_partial: Whether this is a partial index.
        expression: SQL expression for expression indexes.
        where_clause: WHERE clause for partial indexes.
        include_columns: Additional columns to include (covering index).
        tablespace: Tablespace where the index is stored.
    """

    model_config = ConfigDict(
        frozen=False,
        validate_assignment=True,
        extra="forbid",
    )

    name: str = Field(..., min_length=1, description="Index name")
    columns: List[str] = Field(
        default_factory=list,
        description="Column names in the index"
    )
    type: IndexType = Field(
        default=IndexType.BTREE,
        description="Index type"
    )
    is_unique: bool = Field(default=False, description="Enforces uniqueness")
    is_primary: bool = Field(default=False, description="Primary key index")
    is_partial: bool = Field(default=False, description="Partial index")
    expression: Optional[str] = Field(
        default=None,
        description="SQL expression for expression indexes"
    )
    where_clause: Optional[str] = Field(
        default=None,
        description="WHERE clause for partial indexes"
    )
    include_columns: Optional[List[str]] = Field(
        default=None,
        description="Columns included for covering index"
    )
    tablespace: Optional[str] = Field(
        default=None,
        description="Tablespace for the index"
    )

    @model_validator(mode="after")
    def validate_partial_index(self) -> "Index":
        """Validate partial index has a where clause."""
        if self.is_partial and not self.where_clause:
            raise ValueError("Partial indexes must specify a where_clause")
        return self


class Column(BaseModel):
    """
    Core column model with full metadata.

    This is the canonical representation of a database column used throughout
    the DataForge system. It includes basic type information, constraint flags,
    foreign key details, and semantic metadata populated by analysis.

    Attributes:
        name: Column name.
        data_type: Raw database type (e.g., "varchar(255)", "integer").
        is_nullable: Whether NULL values are allowed.
        is_primary_key: Whether column is part of the primary key.
        is_foreign_key: Whether column is a foreign key.
        is_unique: Whether column has a unique constraint.
        is_identity: Whether column is an identity column.
        default_value: Default value expression.
        foreign_key_table: Referenced table for foreign keys.
        foreign_key_column: Referenced column for foreign keys.
        foreign_key_schema: Schema of the referenced table.
        ordinal_position: Position in table (1-based).
        character_maximum_length: Max length for character types.
        numeric_precision: Precision for numeric types.
        numeric_scale: Scale for numeric types.
        datetime_precision: Precision for datetime types.
        semantic_type: Inferred semantic type (e.g., "email", "phone").
        description: Human-readable description.
        tags: Custom tags for categorization.
        statistics: Column-level statistics from profiling.
    """

    model_config = ConfigDict(
        frozen=False,
        validate_assignment=True,
        extra="forbid",
        populate_by_name=True,
    )

    # Core attributes
    name: str = Field(..., min_length=1, description="Column name")
    data_type: str = Field(..., min_length=1, description="Raw database type")
    is_nullable: bool = Field(default=True, description="Allows NULL values")
    is_primary_key: bool = Field(default=False, description="Part of primary key")
    is_foreign_key: bool = Field(default=False, description="Is a foreign key")
    is_unique: bool = Field(default=False, description="Has unique constraint")
    is_identity: bool = Field(default=False, description="Identity/auto-increment")
    default_value: Optional[str] = Field(
        default=None,
        description="Default value expression"
    )

    # Foreign key details
    foreign_key_table: Optional[str] = Field(
        default=None,
        description="Referenced table for FK"
    )
    foreign_key_column: Optional[str] = Field(
        default=None,
        description="Referenced column for FK"
    )
    foreign_key_schema: Optional[str] = Field(
        default=None,
        description="Schema of referenced table"
    )

    # Position and type details
    ordinal_position: int = Field(
        default=0,
        ge=0,
        description="Position in table (0 if unknown)"
    )
    character_maximum_length: Optional[int] = Field(
        default=None,
        ge=0,
        description="Max length for character types"
    )
    numeric_precision: Optional[int] = Field(
        default=None,
        ge=0,
        description="Precision for numeric types"
    )
    numeric_scale: Optional[int] = Field(
        default=None,
        ge=0,
        description="Scale for numeric types"
    )
    datetime_precision: Optional[int] = Field(
        default=None,
        ge=0,
        description="Precision for datetime types"
    )

    # Semantic information (populated by analysis)
    semantic_type: Optional[str] = Field(
        default=None,
        description="Inferred semantic type (e.g., 'email', 'phone')"
    )
    description: Optional[str] = Field(
        default=None,
        description="Human-readable description"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Custom tags for categorization"
    )

    # Statistics (populated by profiling)
    statistics: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Column statistics from profiling"
    )

    @model_validator(mode="after")
    def validate_foreign_key_consistency(self) -> "Column":
        """Validate FK flag is consistent with FK details."""
        has_fk_details = self.foreign_key_table is not None
        if self.is_foreign_key and not has_fk_details:
            # FK flag set but no details - this is allowed during incremental population
            pass
        if has_fk_details and not self.is_foreign_key:
            # Has FK details but flag not set - set the flag
            object.__setattr__(self, "is_foreign_key", True)
        return self

    @property
    def qualified_foreign_key(self) -> Optional[str]:
        """Get fully qualified foreign key reference."""
        if not self.is_foreign_key or not self.foreign_key_table:
            return None
        parts = []
        if self.foreign_key_schema:
            parts.append(self.foreign_key_schema)
        parts.append(self.foreign_key_table)
        if self.foreign_key_column:
            parts.append(self.foreign_key_column)
        return ".".join(parts)

    @property
    def base_type(self) -> str:
        """Extract base type without length/precision modifiers."""
        # Handle types like "varchar(255)", "numeric(10,2)"
        base = self.data_type.lower().split("(")[0].strip()
        # Handle types with "with time zone" etc.
        if " " in base:
            base = base.split(" ")[0]
        return base

    def is_numeric(self) -> bool:
        """Check if column is a numeric type."""
        numeric_types = {
            "smallint", "integer", "bigint", "int", "int2", "int4", "int8",
            "decimal", "numeric", "real", "float", "double", "money",
            "serial", "bigserial", "smallserial",
        }
        return self.base_type in numeric_types

    def is_text(self) -> bool:
        """Check if column is a text type."""
        text_types = {
            "char", "varchar", "character", "text", "name", "citext",
            "character varying",
        }
        return self.base_type in text_types

    def is_temporal(self) -> bool:
        """Check if column is a temporal type."""
        temporal_types = {
            "date", "time", "timestamp", "timestamptz", "timetz",
            "interval",
        }
        return self.base_type in temporal_types

    def is_boolean(self) -> bool:
        """Check if column is a boolean type."""
        return self.base_type in {"boolean", "bool"}

    def is_json(self) -> bool:
        """Check if column is a JSON type."""
        return self.base_type in {"json", "jsonb"}

    def is_uuid(self) -> bool:
        """Check if column is a UUID type."""
        return self.base_type == "uuid"


class Table(BaseModel):
    """
    Core table model with columns, constraints, and indexes.

    Represents a complete database table including all metadata needed
    for schema analysis, normalization, and code generation.

    Attributes:
        name: Table name.
        schema_name: Schema containing the table.
        columns: List of column definitions.
        constraints: List of constraint definitions.
        indexes: List of index definitions.
        row_count: Estimated or actual row count.
        size_bytes: Table size in bytes.
        description: Human-readable description.
        table_type: Type of table (BASE TABLE, VIEW, etc.).
        is_partitioned: Whether table is partitioned.
        partition_key: Partition key columns.
        tags: Custom tags for categorization.
        metadata: Additional metadata dictionary.
    """

    model_config = ConfigDict(
        frozen=False,
        validate_assignment=True,
        extra="forbid",
    )

    name: str = Field(..., min_length=1, description="Table name")
    schema_name: str = Field(default="public", description="Schema name")
    columns: List[Column] = Field(
        default_factory=list,
        description="Column definitions"
    )
    constraints: List[Constraint] = Field(
        default_factory=list,
        description="Constraint definitions"
    )
    indexes: List[Index] = Field(
        default_factory=list,
        description="Index definitions"
    )

    # Metadata
    row_count: Optional[int] = Field(
        default=None,
        ge=0,
        description="Estimated row count"
    )
    size_bytes: Optional[int] = Field(
        default=None,
        ge=0,
        description="Table size in bytes"
    )
    description: Optional[str] = Field(
        default=None,
        description="Human-readable description"
    )
    table_type: str = Field(
        default="BASE TABLE",
        description="Table type (BASE TABLE, VIEW, etc.)"
    )
    is_partitioned: bool = Field(
        default=False,
        description="Whether table is partitioned"
    )
    partition_key: Optional[List[str]] = Field(
        default=None,
        description="Partition key columns"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Custom tags"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata"
    )

    @property
    def qualified_name(self) -> str:
        """Get fully qualified table name (schema.table)."""
        return f"{self.schema_name}.{self.name}"

    @property
    def primary_key_columns(self) -> List[str]:
        """Get primary key column names."""
        return [c.name for c in self.columns if c.is_primary_key]

    @property
    def primary_key_constraint(self) -> Optional[Constraint]:
        """Get the primary key constraint if one exists."""
        for constraint in self.constraints:
            if constraint.type == ConstraintType.PRIMARY_KEY:
                return constraint
        return None

    @property
    def foreign_key_columns(self) -> List[Column]:
        """Get all foreign key columns."""
        return [c for c in self.columns if c.is_foreign_key]

    @property
    def foreign_key_constraints(self) -> List[Constraint]:
        """Get all foreign key constraints."""
        return [
            c for c in self.constraints
            if c.type == ConstraintType.FOREIGN_KEY
        ]

    @property
    def unique_constraints(self) -> List[Constraint]:
        """Get all unique constraints."""
        return [
            c for c in self.constraints
            if c.type == ConstraintType.UNIQUE
        ]

    @property
    def check_constraints(self) -> List[Constraint]:
        """Get all check constraints."""
        return [
            c for c in self.constraints
            if c.type == ConstraintType.CHECK
        ]

    @property
    def nullable_columns(self) -> List[Column]:
        """Get all nullable columns."""
        return [c for c in self.columns if c.is_nullable]

    @property
    def required_columns(self) -> List[Column]:
        """Get all non-nullable columns."""
        return [c for c in self.columns if not c.is_nullable]

    @property
    def column_count(self) -> int:
        """Get number of columns."""
        return len(self.columns)

    def get_column(self, name: str) -> Optional[Column]:
        """
        Get column by name (case-insensitive).

        Args:
            name: Column name to find.

        Returns:
            Column if found, None otherwise.
        """
        name_lower = name.lower()
        for col in self.columns:
            if col.name.lower() == name_lower:
                return col
        return None

    def get_columns_by_type(self, base_type: str) -> List[Column]:
        """
        Get all columns matching a base type.

        Args:
            base_type: Base type to match (e.g., "varchar", "integer").

        Returns:
            List of matching columns.
        """
        base_type_lower = base_type.lower()
        return [c for c in self.columns if c.base_type == base_type_lower]

    def get_constraint(self, name: str) -> Optional[Constraint]:
        """
        Get constraint by name.

        Args:
            name: Constraint name to find.

        Returns:
            Constraint if found, None otherwise.
        """
        for constraint in self.constraints:
            if constraint.name == name:
                return constraint
        return None

    def get_index(self, name: str) -> Optional[Index]:
        """
        Get index by name.

        Args:
            name: Index name to find.

        Returns:
            Index if found, None otherwise.
        """
        for index in self.indexes:
            if index.name == name:
                return index
        return None

    def has_column(self, name: str) -> bool:
        """Check if table has a column with given name."""
        return self.get_column(name) is not None

    def add_column(self, column: Column) -> None:
        """Add a column to the table."""
        if self.has_column(column.name):
            raise ValueError(f"Column '{column.name}' already exists")
        self.columns.append(column)

    def remove_column(self, name: str) -> bool:
        """
        Remove a column by name.

        Returns:
            True if removed, False if not found.
        """
        for i, col in enumerate(self.columns):
            if col.name.lower() == name.lower():
                self.columns.pop(i)
                return True
        return False


class ForeignKeyRelationship(BaseModel):
    """
    Represents a foreign key relationship between tables.

    This model captures the complete relationship information including
    source and target tables, columns, and inferred cardinality.

    Attributes:
        name: Constraint name for the relationship.
        from_schema: Schema of the source table.
        from_table: Name of the source table.
        from_columns: Columns in the source table.
        to_schema: Schema of the target table.
        to_table: Name of the target table.
        to_columns: Columns in the target table.
        on_delete: Referential action on delete.
        on_update: Referential action on update.
        cardinality: Inferred relationship cardinality.
        is_nullable: Whether the FK columns are nullable.
        is_identifying: Whether this is an identifying relationship.
    """

    model_config = ConfigDict(
        frozen=False,
        validate_assignment=True,
        extra="forbid",
    )

    name: str = Field(..., min_length=1, description="Constraint name")
    from_schema: str = Field(default="public", description="Source schema")
    from_table: str = Field(..., min_length=1, description="Source table")
    from_columns: List[str] = Field(..., min_length=1, description="Source columns")
    to_schema: str = Field(default="public", description="Target schema")
    to_table: str = Field(..., min_length=1, description="Target table")
    to_columns: List[str] = Field(..., min_length=1, description="Target columns")
    on_delete: Optional[ReferentialAction] = Field(
        default=None,
        description="Action on delete"
    )
    on_update: Optional[ReferentialAction] = Field(
        default=None,
        description="Action on update"
    )

    # Inferred properties
    cardinality: Optional[str] = Field(
        default=None,
        description="Relationship cardinality (1:1, 1:N, N:M)"
    )
    is_nullable: bool = Field(
        default=True,
        description="Whether FK columns are nullable"
    )
    is_identifying: bool = Field(
        default=False,
        description="Identifying relationship (FK is part of PK)"
    )

    @field_validator("cardinality")
    @classmethod
    def validate_cardinality(cls, v: Optional[str]) -> Optional[str]:
        """Validate cardinality format."""
        if v is None:
            return v
        valid_cardinalities = {"1:1", "1:N", "N:1", "N:M", "0:1", "0:N"}
        if v not in valid_cardinalities:
            raise ValueError(
                f"Invalid cardinality '{v}'. Must be one of: {valid_cardinalities}"
            )
        return v

    @model_validator(mode="after")
    def validate_column_counts(self) -> "ForeignKeyRelationship":
        """Validate from and to column counts match."""
        if len(self.from_columns) != len(self.to_columns):
            raise ValueError(
                "Number of from_columns must match number of to_columns"
            )
        return self

    @property
    def from_qualified_name(self) -> str:
        """Get fully qualified source table name."""
        return f"{self.from_schema}.{self.from_table}"

    @property
    def to_qualified_name(self) -> str:
        """Get fully qualified target table name."""
        return f"{self.to_schema}.{self.to_table}"

    @property
    def is_composite(self) -> bool:
        """Check if this is a composite foreign key."""
        return len(self.from_columns) > 1

    def reverse(self) -> "ForeignKeyRelationship":
        """Create a reversed relationship (swap from/to)."""
        cardinality_map = {
            "1:1": "1:1",
            "1:N": "N:1",
            "N:1": "1:N",
            "N:M": "N:M",
            "0:1": "1:0",
            "0:N": "N:0",
        }
        reversed_cardinality = (
            cardinality_map.get(self.cardinality) if self.cardinality else None
        )

        return ForeignKeyRelationship(
            name=f"{self.name}_reversed",
            from_schema=self.to_schema,
            from_table=self.to_table,
            from_columns=self.to_columns,
            to_schema=self.from_schema,
            to_table=self.from_table,
            to_columns=self.from_columns,
            on_delete=self.on_delete,
            on_update=self.on_update,
            cardinality=reversed_cardinality,
            is_nullable=self.is_nullable,
            is_identifying=self.is_identifying,
        )


class Schema(BaseModel):
    """
    Complete database schema with tables and relationships.

    This is the top-level model representing an entire database schema
    including all tables, relationships, and metadata.

    Attributes:
        name: Schema name.
        tables: List of tables in the schema.
        relationships: List of foreign key relationships.
        database_name: Name of the database.
        catalog_name: Name of the catalog.
        owner: Schema owner.
        created_at: When the schema was created.
        discovered_at: When the schema was discovered.
        description: Human-readable description.
        tags: Custom tags for categorization.
        metadata: Additional metadata dictionary.
    """

    model_config = ConfigDict(
        frozen=False,
        validate_assignment=True,
        extra="forbid",
    )

    name: str = Field(..., min_length=1, description="Schema name")
    tables: List[Table] = Field(
        default_factory=list,
        description="Tables in the schema"
    )
    relationships: List[ForeignKeyRelationship] = Field(
        default_factory=list,
        description="Foreign key relationships"
    )

    # Metadata
    database_name: Optional[str] = Field(
        default=None,
        description="Database name"
    )
    catalog_name: Optional[str] = Field(
        default=None,
        description="Catalog name"
    )
    owner: Optional[str] = Field(
        default=None,
        description="Schema owner"
    )
    created_at: Optional[datetime] = Field(
        default=None,
        description="Schema creation time"
    )
    discovered_at: Optional[datetime] = Field(
        default=None,
        description="When schema was discovered"
    )
    description: Optional[str] = Field(
        default=None,
        description="Human-readable description"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Custom tags"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata"
    )

    @property
    def qualified_name(self) -> str:
        """Get fully qualified schema name."""
        parts = []
        if self.catalog_name:
            parts.append(self.catalog_name)
        if self.database_name:
            parts.append(self.database_name)
        parts.append(self.name)
        return ".".join(parts)

    @property
    def table_count(self) -> int:
        """Get number of tables."""
        return len(self.tables)

    @property
    def relationship_count(self) -> int:
        """Get number of relationships."""
        return len(self.relationships)

    @property
    def total_columns(self) -> int:
        """Get total number of columns across all tables."""
        return sum(len(t.columns) for t in self.tables)

    @property
    def table_names(self) -> List[str]:
        """Get list of table names."""
        return [t.name for t in self.tables]

    def get_table(self, name: str) -> Optional[Table]:
        """
        Get table by name (case-insensitive).

        Args:
            name: Table name to find.

        Returns:
            Table if found, None otherwise.
        """
        name_lower = name.lower()
        for table in self.tables:
            if table.name.lower() == name_lower:
                return table
        return None

    def get_relationships_for_table(
        self,
        table_name: str,
        include_outgoing: bool = True,
        include_incoming: bool = True,
    ) -> List[ForeignKeyRelationship]:
        """
        Get all relationships involving a table.

        Args:
            table_name: Name of the table.
            include_outgoing: Include relationships where table is source.
            include_incoming: Include relationships where table is target.

        Returns:
            List of matching relationships.
        """
        result = []
        table_lower = table_name.lower()

        for rel in self.relationships:
            if include_outgoing and rel.from_table.lower() == table_lower:
                result.append(rel)
            elif include_incoming and rel.to_table.lower() == table_lower:
                result.append(rel)

        return result

    def get_outgoing_relationships(
        self,
        table_name: str,
    ) -> List[ForeignKeyRelationship]:
        """Get relationships where table is the source (has FK)."""
        return self.get_relationships_for_table(
            table_name,
            include_outgoing=True,
            include_incoming=False,
        )

    def get_incoming_relationships(
        self,
        table_name: str,
    ) -> List[ForeignKeyRelationship]:
        """Get relationships where table is the target (referenced by FK)."""
        return self.get_relationships_for_table(
            table_name,
            include_outgoing=False,
            include_incoming=True,
        )

    def get_related_tables(self, table_name: str) -> List[str]:
        """
        Get names of all tables related to the given table.

        Args:
            table_name: Name of the table.

        Returns:
            List of related table names.
        """
        related = set()
        table_lower = table_name.lower()

        for rel in self.relationships:
            if rel.from_table.lower() == table_lower:
                related.add(rel.to_table)
            elif rel.to_table.lower() == table_lower:
                related.add(rel.from_table)

        return list(related)

    def has_table(self, name: str) -> bool:
        """Check if schema contains a table with given name."""
        return self.get_table(name) is not None

    def add_table(self, table: Table) -> None:
        """Add a table to the schema."""
        if self.has_table(table.name):
            raise ValueError(f"Table '{table.name}' already exists")
        # Ensure table schema matches
        table.schema_name = self.name
        self.tables.append(table)

    def remove_table(self, name: str) -> bool:
        """
        Remove a table by name.

        Returns:
            True if removed, False if not found.
        """
        for i, table in enumerate(self.tables):
            if table.name.lower() == name.lower():
                self.tables.pop(i)
                # Also remove related relationships
                self.relationships = [
                    r for r in self.relationships
                    if r.from_table.lower() != name.lower()
                    and r.to_table.lower() != name.lower()
                ]
                return True
        return False

    def add_relationship(self, relationship: ForeignKeyRelationship) -> None:
        """Add a relationship to the schema."""
        self.relationships.append(relationship)

    def build_relationships_from_tables(self) -> List[ForeignKeyRelationship]:
        """
        Build relationship list from table foreign key constraints.

        This method extracts FK relationships from table constraints
        and populates the relationships list.

        Returns:
            List of discovered relationships.
        """
        discovered = []

        for table in self.tables:
            for constraint in table.foreign_key_constraints:
                if not constraint.reference_table:
                    continue

                relationship = ForeignKeyRelationship(
                    name=constraint.name,
                    from_schema=table.schema_name,
                    from_table=table.name,
                    from_columns=constraint.columns,
                    to_schema=constraint.reference_schema or self.name,
                    to_table=constraint.reference_table,
                    to_columns=constraint.reference_columns or [],
                    on_delete=constraint.on_delete,
                    on_update=constraint.on_update,
                )
                discovered.append(relationship)

        self.relationships = discovered
        return discovered

    def to_summary(self) -> Dict[str, Any]:
        """
        Generate a summary dictionary of the schema.

        Returns:
            Dictionary with schema statistics and overview.
        """
        return {
            "name": self.name,
            "database": self.database_name,
            "table_count": self.table_count,
            "relationship_count": self.relationship_count,
            "total_columns": self.total_columns,
            "tables": [
                {
                    "name": t.name,
                    "column_count": t.column_count,
                    "row_count": t.row_count,
                    "has_pk": bool(t.primary_key_columns),
                    "fk_count": len(t.foreign_key_columns),
                }
                for t in self.tables
            ],
            "discovered_at": (
                self.discovered_at.isoformat() if self.discovered_at else None
            ),
        }
