"""
Core domain models for DataForge.

This package contains the canonical domain models used throughout the system
for representing database schemas, tables, columns, relationships, constraints,
semantic type information, analysis results, and design specifications.

These models are distinct from:
- API models (api/models/) - Used for API request/response serialization
- Generator models (core/generators/) - Used for code generation
- MCP models (core/mcp/servers/) - Used for database communication

Model Categories:
- Schema models: Column, Table, Schema, Constraint, Index, ForeignKeyRelationship
- Type models: SemanticType, SemanticCategory, DatabaseType, TypeInferenceResult
- Analysis models: ColumnProfile, TableProfile, SchemaAnalysis, FunctionalDependency
- Design models: ModelDesign, DesignedTable, DesignedColumn, DesignedRelationship

Usage:
    from core.models import Schema, Table, Column, Constraint, Index
    from core.models import SemanticType, SemanticCategory, infer_semantic_type
    from core.models import SchemaAnalysis, ModelDesign

    # Create a schema with tables
    schema = Schema(
        name="public",
        tables=[
            Table(
                name="users",
                columns=[
                    Column(name="id", data_type="integer", is_primary_key=True),
                    Column(name="email", data_type="varchar(255)"),
                ],
            ),
        ],
    )

    # Infer semantic types
    result = infer_semantic_type("email", "varchar(255)")
    print(result.semantic_type)  # SemanticType.EMAIL
"""

# Schema models - Core domain representation
from core.models.schema import (
    Column,
    Constraint,
    ConstraintType,
    ForeignKeyRelationship,
    Index,
    IndexType,
    ReferentialAction,
    Schema,
    Table,
)

# Type models - Semantic type system
from core.models.types import (
    DEFAULT_NAME_PATTERNS,
    PII_TYPES,
    SEMANTIC_TYPE_CATEGORIES,
    SENSITIVE_TYPES,
    DataSensitivity,
    DatabaseType,
    NamePattern,
    SemanticCategory,
    SemanticType,
    TypeInferenceResult,
    TypeMapping,
    get_category,
    get_sensitivity_level,
    infer_semantic_type,
    is_pii,
    is_sensitive,
)

# Analysis models - Data profiling and analysis results
from core.models.analysis import (
    CandidateKey,
    ColumnProfile,
    ColumnStatistics,
    ConfidenceLevel,
    FunctionalDependency,
    KeyAnalysis,
    PatternMatch,
    PatternType,
    RelationshipAnalysis,
    SchemaAnalysis,
    TableProfile,
    TopValue,
)

# Design models - Model design specifications
from core.models.design import (
    ColumnRole,
    DesignedColumn,
    DesignedRelationship,
    DesignedTable,
    ModelDesign,
    ModelingStrategy,
    SCDType,
    TableRole,
)

__all__ = [
    # Schema models
    "Column",
    "Constraint",
    "ConstraintType",
    "ForeignKeyRelationship",
    "Index",
    "IndexType",
    "ReferentialAction",
    "Schema",
    "Table",
    # Type enums
    "DatabaseType",
    "DataSensitivity",
    "SemanticCategory",
    "SemanticType",
    # Type models
    "NamePattern",
    "TypeInferenceResult",
    "TypeMapping",
    # Type constants
    "DEFAULT_NAME_PATTERNS",
    "PII_TYPES",
    "SEMANTIC_TYPE_CATEGORIES",
    "SENSITIVE_TYPES",
    # Type functions
    "get_category",
    "get_sensitivity_level",
    "infer_semantic_type",
    "is_pii",
    "is_sensitive",
    # Analysis models
    "CandidateKey",
    "ColumnProfile",
    "ColumnStatistics",
    "ConfidenceLevel",
    "FunctionalDependency",
    "KeyAnalysis",
    "PatternMatch",
    "PatternType",
    "RelationshipAnalysis",
    "SchemaAnalysis",
    "TableProfile",
    "TopValue",
    # Design models
    "ColumnRole",
    "DesignedColumn",
    "DesignedRelationship",
    "DesignedTable",
    "ModelDesign",
    "ModelingStrategy",
    "SCDType",
    "TableRole",
]
