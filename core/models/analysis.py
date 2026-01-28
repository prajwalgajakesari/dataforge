"""
Models for data analysis results.

This module provides Pydantic models for representing the results of data
analysis operations including:
- Column statistics and profiling
- Pattern detection and matching
- Functional dependency discovery
- Candidate key analysis
- Table relationship inference
- Complete schema analysis

All models are JSON serializable and use Pydantic v2 conventions.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, computed_field


class PatternType(str, Enum):
    """
    Types of data patterns that can be detected in string columns.

    These patterns help identify semantic meaning and appropriate
    data types for columns beyond their raw storage type.
    """
    EMAIL = "email"
    PHONE = "phone"
    URL = "url"
    UUID = "uuid"
    IP_ADDRESS = "ip_address"
    DATE_ISO = "date_iso"
    DATE_US = "date_us"
    DATE_EU = "date_eu"
    CREDIT_CARD = "credit_card"
    SSN = "ssn"
    ZIP_CODE = "zip_code"
    CURRENCY = "currency"
    PERCENTAGE = "percentage"
    JSON = "json"
    NUMERIC_ID = "numeric_id"
    ALPHANUMERIC_CODE = "alphanumeric_code"
    MAC_ADDRESS = "mac_address"
    SLUG = "slug"


class ConfidenceLevel(str, Enum):
    """
    Confidence levels for inferred properties.

    Used to indicate how confident the analysis is about a detected
    pattern, relationship, or inferred property.
    """
    HIGH = "high"      # >95% confidence
    MEDIUM = "medium"  # 80-95% confidence
    LOW = "low"        # <80% confidence


class PatternMatch(BaseModel):
    """
    Result of pattern matching on a column.

    Represents how well a specific pattern matches the values
    in a column, including match statistics and sample values.

    Attributes:
        pattern_type: The type of pattern detected.
        match_count: Number of values matching the pattern.
        total_count: Total number of non-null values checked.
        match_percentage: Percentage of values matching (0-100).
        confidence: Confidence level of the pattern detection.
        sample_matches: Up to 5 sample values that match the pattern.
    """
    pattern_type: PatternType
    match_count: int = Field(ge=0, description="Number of matching values")
    total_count: int = Field(ge=0, description="Total non-null values")
    match_percentage: float = Field(ge=0, le=100, description="Match percentage")
    confidence: ConfidenceLevel
    sample_matches: List[str] = Field(
        default_factory=list,
        max_length=5,
        description="Sample values matching the pattern"
    )

    @field_validator("match_percentage", mode="before")
    @classmethod
    def round_percentage(cls, v: float) -> float:
        """Round percentage to 2 decimal places."""
        return round(v, 2)

    model_config = {"frozen": False, "extra": "forbid"}


class TopValue(BaseModel):
    """Represents a frequently occurring value in a column."""
    value: Any
    count: int
    percentage: float = Field(ge=0, le=100)


class ColumnStatistics(BaseModel):
    """
    Statistical analysis of a column.

    Contains comprehensive statistics about a column including
    null analysis, distinct values, numeric statistics, string
    statistics, value distribution, and detected patterns.

    Attributes:
        column_name: Name of the column.
        data_type: Database or inferred data type.
        total_count: Total number of rows.
        null_count: Number of null/missing values.
        distinct_count: Number of unique values.
        quality_score: Data quality score (0-100).
    """
    column_name: str = Field(min_length=1, description="Column name")
    data_type: str = Field(min_length=1, description="Data type")

    # Null analysis
    total_count: int = Field(ge=0, description="Total row count")
    null_count: int = Field(default=0, ge=0, description="Null value count")
    null_percentage: float = Field(default=0.0, ge=0, le=100, description="Null percentage")

    # Distinct values
    distinct_count: int = Field(default=0, ge=0, description="Distinct value count")
    distinct_percentage: float = Field(default=0.0, ge=0, le=100, description="Distinct percentage")
    is_unique: bool = Field(default=False, description="Whether all non-null values are unique")

    # For numeric columns
    min_value: Optional[Any] = Field(default=None, description="Minimum value")
    max_value: Optional[Any] = Field(default=None, description="Maximum value")
    mean_value: Optional[float] = Field(default=None, description="Mean value")
    median_value: Optional[float] = Field(default=None, description="Median value")
    stddev_value: Optional[float] = Field(default=None, description="Standard deviation")
    percentile_25: Optional[float] = Field(default=None, description="25th percentile")
    percentile_75: Optional[float] = Field(default=None, description="75th percentile")
    percentile_90: Optional[float] = Field(default=None, description="90th percentile")
    percentile_99: Optional[float] = Field(default=None, description="99th percentile")

    # For string columns
    min_length: Optional[int] = Field(default=None, ge=0, description="Minimum string length")
    max_length: Optional[int] = Field(default=None, ge=0, description="Maximum string length")
    avg_length: Optional[float] = Field(default=None, ge=0, description="Average string length")
    empty_count: Optional[int] = Field(default=None, ge=0, description="Empty string count")

    # Distribution
    top_values: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Top values with counts: [{value, count, percentage}]"
    )
    histogram: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Histogram buckets: [{bucket, count}]"
    )

    # Patterns detected
    patterns: List[PatternMatch] = Field(
        default_factory=list,
        description="Detected patterns in the column"
    )

    # Quality score (0-100)
    quality_score: float = Field(
        default=100.0,
        ge=0,
        le=100,
        description="Data quality score"
    )
    quality_issues: List[str] = Field(
        default_factory=list,
        description="List of detected quality issues"
    )

    @computed_field
    @property
    def non_null_count(self) -> int:
        """Calculate the number of non-null values."""
        return self.total_count - self.null_count

    @computed_field
    @property
    def completeness(self) -> float:
        """Calculate completeness as percentage of non-null values."""
        if self.total_count == 0:
            return 100.0
        return round((1 - self.null_count / self.total_count) * 100, 2)

    @field_validator("null_percentage", "distinct_percentage", mode="before")
    @classmethod
    def round_percentages(cls, v: float) -> float:
        """Round percentages to 2 decimal places."""
        return round(v, 2)

    model_config = {"frozen": False, "extra": "forbid"}


class ColumnProfile(BaseModel):
    """
    Complete profile of a single column.

    Combines column statistics with semantic type inference
    and profiling metadata.

    Attributes:
        column_name: Name of the column.
        table_name: Name of the containing table.
        schema_name: Name of the database schema.
        statistics: Detailed column statistics.
        inferred_semantic_type: Detected semantic type (e.g., 'email', 'phone').
    """
    column_name: str = Field(min_length=1, description="Column name")
    table_name: str = Field(min_length=1, description="Table name")
    schema_name: str = Field(min_length=1, description="Schema name")

    # Statistics
    statistics: ColumnStatistics = Field(description="Column statistics")

    # Inferred semantic type
    inferred_semantic_type: Optional[str] = Field(
        default=None,
        description="Inferred semantic type (e.g., 'email', 'phone')"
    )
    semantic_type_confidence: ConfidenceLevel = Field(
        default=ConfidenceLevel.LOW,
        description="Confidence in semantic type inference"
    )

    # Sample values
    sample_values: List[Any] = Field(
        default_factory=list,
        max_length=10,
        description="Sample values from the column"
    )

    # Profiling metadata
    profiled_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp of profiling"
    )
    sample_size: int = Field(
        default=0,
        ge=0,
        description="Number of rows sampled for profiling"
    )

    @computed_field
    @property
    def fully_qualified_name(self) -> str:
        """Return the fully qualified column name."""
        return f"{self.schema_name}.{self.table_name}.{self.column_name}"

    model_config = {"frozen": False, "extra": "forbid"}


class TableProfile(BaseModel):
    """
    Complete profile of a table.

    Contains metadata about the table, profiles of all columns,
    and table-level quality metrics.

    Attributes:
        table_name: Name of the table.
        schema_name: Name of the database schema.
        row_count: Total number of rows.
        column_count: Number of columns.
        columns: List of column profiles.
    """
    table_name: str = Field(min_length=1, description="Table name")
    schema_name: str = Field(min_length=1, description="Schema name")

    # Basic info
    row_count: int = Field(ge=0, description="Total row count")
    column_count: int = Field(ge=0, description="Column count")
    size_bytes: Optional[int] = Field(default=None, ge=0, description="Table size in bytes")

    # Column profiles
    columns: List[ColumnProfile] = Field(
        default_factory=list,
        description="Column profiles"
    )

    # Table-level analysis
    has_primary_key: bool = Field(default=False, description="Whether table has a primary key")
    primary_key_columns: List[str] = Field(
        default_factory=list,
        description="Primary key column names"
    )
    potential_foreign_keys: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Potential foreign key relationships detected"
    )

    # Quality metrics
    overall_quality_score: float = Field(
        default=100.0,
        ge=0,
        le=100,
        description="Overall data quality score"
    )
    completeness_score: float = Field(
        default=100.0,
        ge=0,
        le=100,
        description="Percentage of non-null values"
    )
    uniqueness_score: float = Field(
        default=100.0,
        ge=0,
        le=100,
        description="Average uniqueness of columns"
    )
    consistency_score: float = Field(
        default=100.0,
        ge=0,
        le=100,
        description="Data consistency score"
    )

    # Profiling metadata
    profiled_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp of profiling"
    )
    profiling_duration_ms: Optional[int] = Field(
        default=None,
        ge=0,
        description="Profiling duration in milliseconds"
    )
    sample_size_used: Optional[int] = Field(
        default=None,
        description="Sample size used for profiling"
    )

    @computed_field
    @property
    def fully_qualified_name(self) -> str:
        """Return the fully qualified table name."""
        return f"{self.schema_name}.{self.table_name}"

    @computed_field
    @property
    def size_mb(self) -> Optional[float]:
        """Return table size in megabytes."""
        if self.size_bytes is None:
            return None
        return round(self.size_bytes / (1024 * 1024), 2)

    def get_column(self, column_name: str) -> Optional[ColumnProfile]:
        """
        Get a column profile by name.

        Args:
            column_name: Name of the column to retrieve.

        Returns:
            The column profile if found, None otherwise.
        """
        for col in self.columns:
            if col.column_name == column_name:
                return col
        return None

    model_config = {"frozen": False, "extra": "forbid"}


class FunctionalDependency(BaseModel):
    """
    Represents a functional dependency: determinant -> dependent.

    A functional dependency X -> Y means that for any two rows,
    if they have the same values for columns X, they must have
    the same value for column Y.

    Attributes:
        determinant: Left-hand side columns (X).
        dependent: Right-hand side column (Y).
        confidence: 1.0 for exact FD, <1.0 for approximate.
        support: Fraction of rows supporting this FD.
        violations: Number of rows violating the FD.
    """
    determinant: List[str] = Field(
        min_length=1,
        description="Left-hand side columns (X)"
    )
    dependent: str = Field(min_length=1, description="Right-hand side column (Y)")

    # Analysis results
    confidence: float = Field(
        default=1.0,
        ge=0,
        le=1,
        description="Confidence (1.0 = exact, <1.0 = approximate)"
    )
    support: float = Field(
        default=1.0,
        ge=0,
        le=1,
        description="Fraction of rows supporting this FD"
    )
    violations: int = Field(
        default=0,
        ge=0,
        description="Number of violating rows"
    )

    # Classification
    is_trivial: bool = Field(
        default=False,
        description="Whether Y is a subset of X"
    )
    is_partial: bool = Field(
        default=False,
        description="Partial dependency (2NF violation)"
    )
    is_transitive: bool = Field(
        default=False,
        description="Transitive dependency (3NF violation)"
    )

    @computed_field
    @property
    def is_exact(self) -> bool:
        """Return True if this is an exact (not approximate) FD."""
        return self.confidence == 1.0 and self.violations == 0

    @computed_field
    @property
    def determinant_size(self) -> int:
        """Return the number of columns in the determinant."""
        return len(self.determinant)

    def __str__(self) -> str:
        """Return string representation of the functional dependency."""
        return f"{', '.join(self.determinant)} -> {self.dependent}"

    def __repr__(self) -> str:
        """Return detailed string representation."""
        return (
            f"FunctionalDependency({', '.join(self.determinant)} -> {self.dependent}, "
            f"confidence={self.confidence:.2f}, violations={self.violations})"
        )

    def __eq__(self, other: object) -> bool:
        """Check equality based on determinant and dependent."""
        if not isinstance(other, FunctionalDependency):
            return False
        return (
            set(self.determinant) == set(other.determinant)
            and self.dependent == other.dependent
        )

    def __hash__(self) -> int:
        """Hash based on determinant and dependent."""
        return hash((frozenset(self.determinant), self.dependent))

    model_config = {"frozen": False, "extra": "forbid"}


class CandidateKey(BaseModel):
    """
    A candidate key for a table.

    A candidate key is a minimal set of columns that uniquely
    identifies each row in a table.

    Attributes:
        columns: Columns forming the candidate key.
        is_minimal: Whether no proper subset is also a key.
        uniqueness: 1.0 for perfectly unique, <1.0 otherwise.
        null_percentage: Percentage of rows with null in key columns.
    """
    columns: List[str] = Field(
        min_length=1,
        description="Columns forming the key"
    )

    # Analysis
    is_minimal: bool = Field(
        default=True,
        description="Whether no subset is also a key"
    )
    uniqueness: float = Field(
        default=1.0,
        ge=0,
        le=1,
        description="Uniqueness ratio (1.0 = perfectly unique)"
    )
    null_percentage: float = Field(
        default=0.0,
        ge=0,
        le=100,
        description="Percentage of nulls in key columns"
    )

    # Recommendation
    recommended_as_primary: bool = Field(
        default=False,
        description="Whether recommended as primary key"
    )
    recommendation_reason: Optional[str] = Field(
        default=None,
        description="Reason for recommendation"
    )

    @computed_field
    @property
    def column_count(self) -> int:
        """Return the number of columns in the key."""
        return len(self.columns)

    @computed_field
    @property
    def is_simple_key(self) -> bool:
        """Return True if this is a single-column key."""
        return len(self.columns) == 1

    @computed_field
    @property
    def is_composite_key(self) -> bool:
        """Return True if this is a multi-column key."""
        return len(self.columns) > 1

    def __str__(self) -> str:
        """Return string representation of the candidate key."""
        return f"({', '.join(self.columns)})"

    def __eq__(self, other: object) -> bool:
        """Check equality based on column set."""
        if not isinstance(other, CandidateKey):
            return False
        return set(self.columns) == set(other.columns)

    def __hash__(self) -> int:
        """Hash based on column set."""
        return hash(frozenset(self.columns))

    model_config = {"frozen": False, "extra": "forbid"}


class KeyAnalysis(BaseModel):
    """
    Complete key analysis for a table.

    Contains information about existing keys, discovered candidate
    keys, and recommendations for primary key selection.

    Attributes:
        table_name: Name of the table.
        schema_name: Name of the database schema.
        primary_key: Existing primary key columns, if any.
        candidate_keys: Discovered candidate keys.
    """
    table_name: str = Field(min_length=1, description="Table name")
    schema_name: str = Field(min_length=1, description="Schema name")

    # Existing keys
    primary_key: Optional[List[str]] = Field(
        default=None,
        description="Existing primary key columns"
    )
    unique_constraints: List[List[str]] = Field(
        default_factory=list,
        description="Existing unique constraints"
    )

    # Discovered keys
    candidate_keys: List[CandidateKey] = Field(
        default_factory=list,
        description="Discovered candidate keys"
    )

    # Recommendations
    recommended_primary_key: Optional[List[str]] = Field(
        default=None,
        description="Recommended primary key columns"
    )
    key_recommendation_reason: Optional[str] = Field(
        default=None,
        description="Reason for key recommendation"
    )

    @computed_field
    @property
    def has_existing_primary_key(self) -> bool:
        """Return True if the table has an existing primary key."""
        return self.primary_key is not None and len(self.primary_key) > 0

    @computed_field
    @property
    def candidate_key_count(self) -> int:
        """Return the number of discovered candidate keys."""
        return len(self.candidate_keys)

    def get_best_candidate_key(self) -> Optional[CandidateKey]:
        """
        Get the best candidate key based on minimality and uniqueness.

        Returns:
            The best candidate key, or None if no candidates exist.
        """
        if not self.candidate_keys:
            return None

        # Prefer keys that are recommended, minimal, and have high uniqueness
        sorted_keys = sorted(
            self.candidate_keys,
            key=lambda k: (
                -int(k.recommended_as_primary),
                -int(k.is_minimal),
                -k.uniqueness,
                k.null_percentage,
                k.column_count
            )
        )
        return sorted_keys[0]

    model_config = {"frozen": False, "extra": "forbid"}


class RelationshipAnalysis(BaseModel):
    """
    Analysis of relationships between tables.

    Represents a potential or actual foreign key relationship
    between two tables, including analysis of value overlap
    and cardinality.

    Attributes:
        from_table: Source table name.
        from_column: Source column name (foreign key).
        to_table: Target table name.
        to_column: Target column name (primary/unique key).
        cardinality: Relationship cardinality ("1:1", "1:N", etc.).
    """
    from_table: str = Field(min_length=1, description="Source table")
    from_column: str = Field(min_length=1, description="Source column")
    to_table: str = Field(min_length=1, description="Target table")
    to_column: str = Field(min_length=1, description="Target column")

    # Analysis
    value_overlap_percentage: float = Field(
        ge=0,
        le=100,
        description="Percentage of FK values existing in PK"
    )
    cardinality: str = Field(
        description="Relationship cardinality: '1:1', '1:N', 'N:1', 'N:M'"
    )
    is_nullable: bool = Field(description="Whether FK column allows nulls")
    null_percentage: float = Field(
        ge=0,
        le=100,
        description="Percentage of null FK values"
    )

    # Confidence
    confidence: ConfidenceLevel = Field(
        description="Confidence in the relationship inference"
    )
    is_explicit_fk: bool = Field(
        description="Whether FK is explicitly defined in schema"
    )

    @computed_field
    @property
    def is_valid_reference(self) -> bool:
        """Return True if all FK values exist in the PK (referential integrity)."""
        return self.value_overlap_percentage == 100.0

    @computed_field
    @property
    def relationship_name(self) -> str:
        """Generate a descriptive name for the relationship."""
        return f"{self.from_table}.{self.from_column} -> {self.to_table}.{self.to_column}"

    @field_validator("cardinality")
    @classmethod
    def validate_cardinality(cls, v: str) -> str:
        """Validate cardinality is one of the allowed values."""
        allowed = {"1:1", "1:N", "N:1", "N:M"}
        if v not in allowed:
            raise ValueError(f"Cardinality must be one of {allowed}, got '{v}'")
        return v

    def __str__(self) -> str:
        """Return string representation of the relationship."""
        return f"{self.from_table}.{self.from_column} -> {self.to_table}.{self.to_column} ({self.cardinality})"

    model_config = {"frozen": False, "extra": "forbid"}


class SchemaAnalysis(BaseModel):
    """
    Complete analysis of a database schema.

    Contains comprehensive analysis results including table profiles,
    functional dependencies, key analysis, and relationship inference
    for all tables in a schema.

    Attributes:
        schema_name: Name of the analyzed schema.
        analyzed_at: Timestamp of the analysis.
        table_profiles: Profiles indexed by table name.
        functional_dependencies: FDs indexed by table name.
        key_analysis: Key analysis indexed by table name.
        relationships: Discovered relationships between tables.
    """
    schema_name: str = Field(min_length=1, description="Schema name")
    analyzed_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Analysis timestamp"
    )

    # Table profiles
    table_profiles: Dict[str, TableProfile] = Field(
        default_factory=dict,
        description="Table profiles indexed by table name"
    )

    # Functional dependencies by table
    functional_dependencies: Dict[str, List[FunctionalDependency]] = Field(
        default_factory=dict,
        description="Functional dependencies by table name"
    )

    # Key analysis by table
    key_analysis: Dict[str, KeyAnalysis] = Field(
        default_factory=dict,
        description="Key analysis by table name"
    )

    # Relationship analysis
    relationships: List[RelationshipAnalysis] = Field(
        default_factory=list,
        description="Discovered relationships"
    )

    # Overall metrics
    total_tables: int = Field(default=0, ge=0, description="Total table count")
    total_columns: int = Field(default=0, ge=0, description="Total column count")
    total_rows: int = Field(default=0, ge=0, description="Total row count")
    overall_quality_score: float = Field(
        default=100.0,
        ge=0,
        le=100,
        description="Overall quality score"
    )

    @computed_field
    @property
    def table_names(self) -> List[str]:
        """Return list of analyzed table names."""
        return list(self.table_profiles.keys())

    @computed_field
    @property
    def relationship_count(self) -> int:
        """Return the number of discovered relationships."""
        return len(self.relationships)

    def get_table_profile(self, table_name: str) -> Optional[TableProfile]:
        """
        Get a table profile by name.

        Args:
            table_name: Name of the table.

        Returns:
            The table profile if found, None otherwise.
        """
        return self.table_profiles.get(table_name)

    def get_functional_dependencies(self, table_name: str) -> List[FunctionalDependency]:
        """
        Get functional dependencies for a table.

        Args:
            table_name: Name of the table.

        Returns:
            List of functional dependencies, empty if table not found.
        """
        return self.functional_dependencies.get(table_name, [])

    def get_key_analysis(self, table_name: str) -> Optional[KeyAnalysis]:
        """
        Get key analysis for a table.

        Args:
            table_name: Name of the table.

        Returns:
            The key analysis if found, None otherwise.
        """
        return self.key_analysis.get(table_name)

    def get_relationships_for_table(self, table_name: str) -> List[RelationshipAnalysis]:
        """
        Get all relationships involving a table (as source or target).

        Args:
            table_name: Name of the table.

        Returns:
            List of relationships involving the table.
        """
        return [
            r for r in self.relationships
            if r.from_table == table_name or r.to_table == table_name
        ]

    def get_outgoing_relationships(self, table_name: str) -> List[RelationshipAnalysis]:
        """
        Get relationships where the table is the source (has foreign keys).

        Args:
            table_name: Name of the table.

        Returns:
            List of outgoing relationships.
        """
        return [r for r in self.relationships if r.from_table == table_name]

    def get_incoming_relationships(self, table_name: str) -> List[RelationshipAnalysis]:
        """
        Get relationships where the table is the target (is referenced).

        Args:
            table_name: Name of the table.

        Returns:
            List of incoming relationships.
        """
        return [r for r in self.relationships if r.to_table == table_name]

    model_config = {"frozen": False, "extra": "forbid"}
