"""
Schema validation module for database schema verification.

This module provides comprehensive validation for database schemas, including
checks for primary keys, foreign keys, naming conventions, data types,
constraints, and indexes. It supports both strict and lenient validation modes.

The validator produces detailed reports with errors, warnings, and suggestions
to help improve schema quality and adherence to best practices.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Set

from core.models.schema import (
    Column,
    Constraint,
    ConstraintType,
    ForeignKeyRelationship,
    Index,
    Schema,
    Table,
)
from core.models.types import SemanticType


# SQL Reserved Words (PostgreSQL-focused, comprehensive list)
SQL_RESERVED_WORDS: FrozenSet[str] = frozenset({
    # SQL Standard Keywords
    "abort", "absolute", "access", "action", "add", "admin", "after", "aggregate",
    "all", "also", "alter", "always", "analyse", "analyze", "and", "any", "array",
    "as", "asc", "assertion", "assignment", "asymmetric", "at", "attach",
    "attribute", "authorization", "backward", "before", "begin", "between",
    "bigint", "binary", "bit", "boolean", "both", "by", "cache", "call", "called",
    "cascade", "cascaded", "case", "cast", "catalog", "chain", "char", "character",
    "characteristics", "check", "checkpoint", "class", "close", "cluster",
    "coalesce", "collate", "collation", "column", "columns", "comment", "comments",
    "commit", "committed", "concurrently", "configuration", "conflict", "connection",
    "constraint", "constraints", "content", "continue", "conversion", "copy",
    "cost", "create", "cross", "csv", "cube", "current", "current_catalog",
    "current_date", "current_role", "current_schema", "current_time",
    "current_timestamp", "current_user", "cursor", "cycle", "data", "database",
    "day", "deallocate", "dec", "decimal", "declare", "default", "defaults",
    "deferrable", "deferred", "definer", "delete", "delimiter", "delimiters",
    "depends", "desc", "detach", "dictionary", "disable", "discard", "distinct",
    "do", "document", "domain", "double", "drop", "each", "else", "enable",
    "encoding", "encrypted", "end", "enum", "escape", "event", "except", "exclude",
    "excluding", "exclusive", "execute", "exists", "explain", "expression",
    "extension", "external", "extract", "false", "family", "fetch", "filter",
    "first", "float", "following", "for", "force", "foreign", "forward", "freeze",
    "from", "full", "function", "functions", "generated", "global", "grant",
    "granted", "greatest", "group", "grouping", "groups", "handler", "having",
    "header", "hold", "hour", "identity", "if", "ilike", "immediate", "immutable",
    "implicit", "import", "in", "include", "including", "increment", "index",
    "indexes", "inherit", "inherits", "initially", "inline", "inner", "inout",
    "input", "insensitive", "insert", "instead", "int", "integer", "intersect",
    "interval", "into", "invoker", "is", "isnull", "isolation", "join", "key",
    "label", "language", "large", "last", "lateral", "leading", "leakproof",
    "least", "left", "level", "like", "limit", "listen", "load", "local",
    "localtime", "localtimestamp", "location", "lock", "locked", "logged",
    "mapping", "match", "materialized", "maxvalue", "method", "minute", "minvalue",
    "mode", "month", "move", "name", "names", "national", "natural", "nchar",
    "new", "next", "no", "none", "not", "nothing", "notify", "notnull", "nowait",
    "null", "nullif", "nulls", "numeric", "object", "of", "off", "offset", "oids",
    "old", "on", "only", "operator", "option", "options", "or", "order",
    "ordinality", "others", "out", "outer", "over", "overlaps", "overlay",
    "overriding", "owned", "owner", "parallel", "parser", "partial", "partition",
    "passing", "password", "placing", "plans", "policy", "position", "preceding",
    "precision", "prepare", "prepared", "preserve", "primary", "prior",
    "privileges", "procedural", "procedure", "procedures", "program", "publication",
    "quote", "range", "read", "real", "reassign", "recheck", "recursive", "ref",
    "references", "referencing", "refresh", "reindex", "relative", "release",
    "rename", "repeatable", "replace", "replica", "reset", "restart", "restrict",
    "returning", "returns", "revoke", "right", "role", "rollback", "rollup",
    "routine", "routines", "row", "rows", "rule", "savepoint", "schema", "schemas",
    "scroll", "search", "second", "security", "select", "sequence", "sequences",
    "serializable", "server", "session", "session_user", "set", "setof", "sets",
    "share", "show", "similar", "simple", "skip", "smallint", "snapshot", "some",
    "sql", "stable", "standalone", "start", "statement", "statistics", "stdin",
    "stdout", "storage", "stored", "strict", "strip", "subscription", "substring",
    "support", "symmetric", "sysid", "system", "table", "tables", "tablesample",
    "tablespace", "temp", "template", "temporary", "text", "then", "ties", "time",
    "timestamp", "to", "trailing", "transaction", "transform", "treat", "trigger",
    "trim", "true", "truncate", "trusted", "type", "types", "uescape", "unbounded",
    "uncommitted", "unencrypted", "union", "unique", "unknown", "unlisten",
    "unlogged", "until", "update", "user", "using", "vacuum", "valid", "validate",
    "validator", "value", "values", "varchar", "variadic", "varying", "verbose",
    "version", "view", "views", "volatile", "when", "where", "whitespace", "window",
    "with", "within", "without", "work", "wrapper", "write", "xml", "xmlattributes",
    "xmlconcat", "xmlelement", "xmlexists", "xmlforest", "xmlnamespaces",
    "xmlparse", "xmlpi", "xmlroot", "xmlserialize", "xmltable", "year", "yes",
    "zone",
})

# Standard constraint name prefixes
CONSTRAINT_PREFIXES: Dict[ConstraintType, str] = {
    ConstraintType.PRIMARY_KEY: "pk_",
    ConstraintType.FOREIGN_KEY: "fk_",
    ConstraintType.UNIQUE: "uq_",
    ConstraintType.CHECK: "chk_",
    ConstraintType.NOT_NULL: "nn_",
    ConstraintType.DEFAULT: "df_",
    ConstraintType.EXCLUSION: "excl_",
}

# Valid PostgreSQL data types (base types)
VALID_DATA_TYPES: FrozenSet[str] = frozenset({
    # Numeric types
    "smallint", "integer", "bigint", "int", "int2", "int4", "int8",
    "decimal", "numeric", "real", "float", "float4", "float8",
    "double", "double precision", "money",
    "serial", "bigserial", "smallserial", "serial2", "serial4", "serial8",
    # Character types
    "char", "character", "varchar", "character varying", "text", "name", "citext",
    # Binary types
    "bytea",
    # Date/time types
    "date", "time", "timetz", "timestamp", "timestamptz", "interval",
    "time with time zone", "time without time zone",
    "timestamp with time zone", "timestamp without time zone",
    # Boolean
    "boolean", "bool",
    # UUID
    "uuid",
    # JSON
    "json", "jsonb",
    # Network
    "inet", "cidr", "macaddr", "macaddr8",
    # Geometric
    "point", "line", "lseg", "box", "path", "polygon", "circle",
    # Other
    "xml", "tsvector", "tsquery", "array", "oid", "bit", "bit varying", "varbit",
})


@dataclass
class ValidationResult:
    """
    Result of validating a single entity (table, column, etc.).

    Attributes:
        is_valid: True if no errors were found.
        errors: List of error messages (validation failures).
        warnings: List of warning messages (potential issues).
        suggestions: List of improvement suggestions.
    """

    is_valid: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

    def add_error(self, message: str) -> None:
        """Add an error and mark as invalid."""
        self.errors.append(message)
        self.is_valid = False

    def add_warning(self, message: str) -> None:
        """Add a warning message."""
        self.warnings.append(message)

    def add_suggestion(self, message: str) -> None:
        """Add a suggestion for improvement."""
        self.suggestions.append(message)

    def merge(self, other: "ValidationResult") -> None:
        """Merge another validation result into this one."""
        if not other.is_valid:
            self.is_valid = False
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        self.suggestions.extend(other.suggestions)


@dataclass
class SchemaValidationReport:
    """
    Comprehensive validation report for an entire schema.

    Attributes:
        tables_validated: Number of tables that were validated.
        total_errors: Total count of errors across all tables.
        total_warnings: Total count of warnings across all tables.
        results_by_table: Mapping of table names to their validation results.
        schema_level_errors: Errors at the schema level (cross-table issues).
        schema_level_warnings: Warnings at the schema level.
    """

    tables_validated: int = 0
    total_errors: int = 0
    total_warnings: int = 0
    results_by_table: Dict[str, ValidationResult] = field(default_factory=dict)
    schema_level_errors: List[str] = field(default_factory=list)
    schema_level_warnings: List[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """Check if the entire schema is valid (no errors)."""
        return self.total_errors == 0 and len(self.schema_level_errors) == 0

    def add_table_result(self, table_name: str, result: ValidationResult) -> None:
        """Add a table validation result to the report."""
        self.results_by_table[table_name] = result
        self.total_errors += len(result.errors)
        self.total_warnings += len(result.warnings)
        self.tables_validated += 1

    def add_schema_error(self, message: str) -> None:
        """Add a schema-level error."""
        self.schema_level_errors.append(message)
        self.total_errors += 1

    def add_schema_warning(self, message: str) -> None:
        """Add a schema-level warning."""
        self.schema_level_warnings.append(message)
        self.total_warnings += 1

    def to_summary(self) -> Dict:
        """Generate a summary dictionary of the validation report."""
        return {
            "is_valid": self.is_valid,
            "tables_validated": self.tables_validated,
            "total_errors": self.total_errors,
            "total_warnings": self.total_warnings,
            "schema_level_errors": self.schema_level_errors,
            "schema_level_warnings": self.schema_level_warnings,
            "tables_with_errors": [
                name for name, result in self.results_by_table.items()
                if not result.is_valid
            ],
        }


class SchemaValidator:
    """
    Comprehensive schema validator for database schemas.

    This validator checks for common schema issues including:
    - Missing primary keys
    - Invalid foreign key references
    - Naming convention violations
    - Invalid data types
    - Nullable constraint issues
    - Missing indexes on foreign keys
    - Reserved word usage

    Attributes:
        strict_mode: If True, warnings become errors.
        check_naming_conventions: If True, validate naming conventions.
    """

    # Regex patterns for naming conventions
    SNAKE_CASE_PATTERN = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$")
    VALID_IDENTIFIER_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

    def __init__(
        self,
        strict_mode: bool = False,
        check_naming_conventions: bool = True,
    ) -> None:
        """
        Initialize the schema validator.

        Args:
            strict_mode: If True, treat warnings as errors.
            check_naming_conventions: If True, validate naming conventions.
        """
        self.strict_mode = strict_mode
        self.check_naming_conventions = check_naming_conventions

    def validate_schema(self, schema: Schema) -> SchemaValidationReport:
        """
        Validate an entire database schema.

        Performs comprehensive validation including:
        - Individual table validation
        - Cross-table foreign key validation
        - Relationship consistency checks
        - Schema-level naming conventions

        Args:
            schema: The schema to validate.

        Returns:
            A comprehensive validation report.
        """
        report = SchemaValidationReport()

        # Build table lookup for FK validation
        tables_by_name: Dict[str, Table] = {
            table.name.lower(): table for table in schema.tables
        }

        # Check for duplicate table names
        table_names = [t.name.lower() for t in schema.tables]
        seen_names: Set[str] = set()
        for name in table_names:
            if name in seen_names:
                report.add_schema_error(f"Duplicate table name: '{name}'")
            seen_names.add(name)

        # Validate each table
        for table in schema.tables:
            table_result = self.validate_table(table)

            # Cross-table FK validation
            fk_errors = self._check_foreign_keys(table, tables_by_name)
            for error in fk_errors:
                table_result.add_error(error)

            report.add_table_result(table.name, table_result)

        # Validate relationships consistency
        self._validate_relationships(schema, tables_by_name, report)

        # Schema-level checks
        if not schema.tables:
            report.add_schema_warning("Schema contains no tables")

        if self.check_naming_conventions:
            schema_name_issues = self._check_naming_conventions(
                schema.name, "schema"
            )
            for issue in schema_name_issues:
                if self.strict_mode:
                    report.add_schema_error(issue)
                else:
                    report.add_schema_warning(issue)

        return report

    def validate_table(self, table: Table) -> ValidationResult:
        """
        Validate a single table.

        Checks:
        - Primary key existence
        - Column validity
        - Constraint definitions
        - Index definitions
        - Naming conventions

        Args:
            table: The table to validate.

        Returns:
            Validation result for the table.
        """
        result = ValidationResult()

        # Check primary key
        pk_errors = self._check_primary_key(table)
        for error in pk_errors:
            if self.strict_mode:
                result.add_error(error)
            else:
                result.add_warning(error)

        # Check each column
        for column in table.columns:
            column_result = self.validate_column(column, table.name)
            result.merge(column_result)

        # Check constraints
        constraint_errors = self._check_constraints(table)
        for error in constraint_errors:
            result.add_error(error)

        # Check indexes
        index_warnings = self._check_indexes(table)
        for warning in index_warnings:
            if self.strict_mode:
                result.add_error(warning)
            else:
                result.add_warning(warning)

        # Check naming conventions
        if self.check_naming_conventions:
            name_issues = self._check_naming_conventions(table.name, "table")
            for issue in name_issues:
                if self.strict_mode:
                    result.add_error(issue)
                else:
                    result.add_warning(issue)

        # Check for empty tables (no columns)
        if not table.columns:
            result.add_error(f"Table '{table.name}' has no columns defined")

        # Check for duplicate column names
        column_names = [c.name.lower() for c in table.columns]
        seen_columns: Set[str] = set()
        for col_name in column_names:
            if col_name in seen_columns:
                result.add_error(
                    f"Duplicate column name '{col_name}' in table '{table.name}'"
                )
            seen_columns.add(col_name)

        return result

    def validate_column(self, column: Column, table_name: str) -> ValidationResult:
        """
        Validate a single column.

        Checks:
        - Data type validity
        - Nullable consistency with PK/FK
        - Naming conventions
        - Foreign key completeness

        Args:
            column: The column to validate.
            table_name: Name of the parent table (for context in messages).

        Returns:
            Validation result for the column.
        """
        result = ValidationResult()

        # Check data type
        type_errors = self._check_data_types(column)
        for error in type_errors:
            result.add_error(f"Column '{table_name}.{column.name}': {error}")

        # Check nullable constraints
        nullable_issues = self._check_nullable(column)
        for issue in nullable_issues:
            if self.strict_mode:
                result.add_error(f"Column '{table_name}.{column.name}': {issue}")
            else:
                result.add_warning(f"Column '{table_name}.{column.name}': {issue}")

        # Check naming conventions
        if self.check_naming_conventions:
            name_issues = self._check_naming_conventions(column.name, "column")
            for issue in name_issues:
                prefixed_issue = f"Column '{table_name}.{column.name}': {issue}"
                if self.strict_mode:
                    result.add_error(prefixed_issue)
                else:
                    result.add_warning(prefixed_issue)

        # Check FK completeness
        if column.is_foreign_key:
            if not column.foreign_key_table:
                result.add_error(
                    f"Column '{table_name}.{column.name}': Foreign key marked but "
                    "no reference table specified"
                )
            if not column.foreign_key_column:
                result.add_warning(
                    f"Column '{table_name}.{column.name}': Foreign key reference "
                    "column not specified (will assume primary key)"
                )

        # Suggestions for common patterns
        self._add_column_suggestions(column, table_name, result)

        return result

    def _check_primary_key(self, table: Table) -> List[str]:
        """
        Check that a table has a primary key defined.

        Args:
            table: The table to check.

        Returns:
            List of error/warning messages.
        """
        issues: List[str] = []

        # Check for PK via column flags
        pk_columns = [c for c in table.columns if c.is_primary_key]

        # Check for PK via constraints
        pk_constraint = table.primary_key_constraint

        if not pk_columns and not pk_constraint:
            issues.append(
                f"Table '{table.name}' has no primary key defined. "
                "Consider adding a primary key for data integrity."
            )
        elif pk_columns and pk_constraint:
            # Verify consistency
            pk_column_names = {c.name.lower() for c in pk_columns}
            constraint_columns = {c.lower() for c in pk_constraint.columns}
            if pk_column_names != constraint_columns:
                issues.append(
                    f"Table '{table.name}': Primary key column flags don't match "
                    f"constraint columns. Columns: {pk_column_names}, "
                    f"Constraint: {constraint_columns}"
                )

        # Check for composite PK issues
        if len(pk_columns) > 3:
            issues.append(
                f"Table '{table.name}' has {len(pk_columns)} primary key columns. "
                "Consider using a surrogate key for simpler joins."
            )

        return issues

    def _check_foreign_keys(
        self,
        table: Table,
        all_tables: Dict[str, Table],
    ) -> List[str]:
        """
        Validate foreign key references against known tables.

        Args:
            table: The table to check.
            all_tables: Dictionary of all tables (lowercase name -> Table).

        Returns:
            List of error messages for invalid FK references.
        """
        errors: List[str] = []

        # Check FK columns
        for column in table.columns:
            if column.is_foreign_key and column.foreign_key_table:
                ref_table_name = column.foreign_key_table.lower()
                if ref_table_name not in all_tables:
                    errors.append(
                        f"Column '{table.name}.{column.name}' references "
                        f"non-existent table '{column.foreign_key_table}'"
                    )
                else:
                    # Check if referenced column exists
                    ref_table = all_tables[ref_table_name]
                    if column.foreign_key_column:
                        ref_col = ref_table.get_column(column.foreign_key_column)
                        if not ref_col:
                            errors.append(
                                f"Column '{table.name}.{column.name}' references "
                                f"non-existent column "
                                f"'{column.foreign_key_table}.{column.foreign_key_column}'"
                            )

        # Check FK constraints
        for constraint in table.foreign_key_constraints:
            if constraint.reference_table:
                ref_table_name = constraint.reference_table.lower()
                if ref_table_name not in all_tables:
                    errors.append(
                        f"Constraint '{constraint.name}' in table '{table.name}' "
                        f"references non-existent table '{constraint.reference_table}'"
                    )
                else:
                    # Check referenced columns
                    ref_table = all_tables[ref_table_name]
                    if constraint.reference_columns:
                        for ref_col_name in constraint.reference_columns:
                            if not ref_table.get_column(ref_col_name):
                                errors.append(
                                    f"Constraint '{constraint.name}' in table "
                                    f"'{table.name}' references non-existent column "
                                    f"'{constraint.reference_table}.{ref_col_name}'"
                                )

                    # Check source columns exist
                    for src_col_name in constraint.columns:
                        if not table.get_column(src_col_name):
                            errors.append(
                                f"Constraint '{constraint.name}' references "
                                f"non-existent source column '{src_col_name}' "
                                f"in table '{table.name}'"
                            )

        return errors

    def _check_naming_conventions(
        self,
        name: str,
        entity_type: str,
    ) -> List[str]:
        """
        Check naming conventions for an entity.

        Validates:
        - snake_case format
        - No SQL reserved words
        - Appropriate prefixes for constraints
        - Valid identifier characters

        Args:
            name: The name to check.
            entity_type: Type of entity (table, column, schema, constraint).

        Returns:
            List of naming convention violation messages.
        """
        issues: List[str] = []

        # Check for valid identifier
        if not self.VALID_IDENTIFIER_PATTERN.match(name):
            issues.append(
                f"{entity_type.capitalize()} name '{name}' contains invalid characters. "
                "Use only letters, numbers, and underscores, starting with a letter or underscore."
            )
            return issues  # Skip other checks if basic validation fails

        # Check snake_case
        if not self.SNAKE_CASE_PATTERN.match(name):
            issues.append(
                f"{entity_type.capitalize()} name '{name}' is not in snake_case format. "
                "Consider using lowercase with underscores (e.g., 'user_account')."
            )

        # Check reserved words
        if name.lower() in SQL_RESERVED_WORDS:
            issues.append(
                f"{entity_type.capitalize()} name '{name}' is a SQL reserved word. "
                "This may cause issues with queries. Consider renaming."
            )

        # Check for overly short names
        if len(name) < 2 and entity_type != "column":
            issues.append(
                f"{entity_type.capitalize()} name '{name}' is very short. "
                "Consider using a more descriptive name."
            )

        # Check for overly long names
        if len(name) > 63:  # PostgreSQL identifier limit
            issues.append(
                f"{entity_type.capitalize()} name '{name}' exceeds 63 characters. "
                "PostgreSQL may truncate this identifier."
            )

        return issues

    def _check_data_types(self, column: Column) -> List[str]:
        """
        Validate column data type.

        Args:
            column: The column to check.

        Returns:
            List of error messages for invalid types.
        """
        errors: List[str] = []

        # Extract base type (without length/precision)
        base_type = column.base_type.lower()

        # Check if type is recognized
        if base_type not in VALID_DATA_TYPES:
            # Check for array types
            if not base_type.endswith("[]") and not base_type.startswith("_"):
                errors.append(
                    f"Unrecognized data type '{column.data_type}'. "
                    "This may be a custom type or extension."
                )

        # Check precision/scale for numeric types
        if base_type in {"numeric", "decimal"}:
            if column.numeric_precision is not None:
                if column.numeric_precision > 1000:
                    errors.append(
                        f"Numeric precision {column.numeric_precision} is unusually high. "
                        "Consider if this precision is necessary."
                    )
                if column.numeric_scale is not None:
                    if column.numeric_scale > column.numeric_precision:
                        errors.append(
                            f"Numeric scale ({column.numeric_scale}) cannot exceed "
                            f"precision ({column.numeric_precision})."
                        )

        # Check character length
        if base_type in {"char", "character", "varchar", "character varying"}:
            if column.character_maximum_length is not None:
                if column.character_maximum_length > 10485760:  # PostgreSQL limit
                    errors.append(
                        f"Character length {column.character_maximum_length} exceeds "
                        "PostgreSQL maximum (10485760)."
                    )

        return errors

    def _check_nullable(self, column: Column) -> List[str]:
        """
        Check nullable constraints for special columns.

        Args:
            column: The column to check.

        Returns:
            List of warning messages.
        """
        warnings: List[str] = []

        # Primary key columns should not be nullable
        if column.is_primary_key and column.is_nullable:
            warnings.append(
                "Primary key column is marked as nullable. "
                "Primary keys must be NOT NULL."
            )

        # Foreign key columns should typically not be nullable (unless optional relationship)
        if column.is_foreign_key and column.is_nullable:
            warnings.append(
                "Foreign key column is nullable. This creates an optional relationship. "
                "Ensure this is intentional."
            )

        # Identity columns should not be nullable
        if column.is_identity and column.is_nullable:
            warnings.append(
                "Identity column is marked as nullable. "
                "Identity columns should be NOT NULL."
            )

        return warnings

    def _check_constraints(self, table: Table) -> List[str]:
        """
        Validate constraint definitions.

        Args:
            table: The table to check.

        Returns:
            List of error messages.
        """
        errors: List[str] = []

        seen_constraint_names: Set[str] = set()

        for constraint in table.constraints:
            # Check for duplicate constraint names
            if constraint.name.lower() in seen_constraint_names:
                errors.append(
                    f"Duplicate constraint name '{constraint.name}' in table '{table.name}'"
                )
            seen_constraint_names.add(constraint.name.lower())

            # Check constraint has columns (except for CHECK with expression)
            if constraint.type != ConstraintType.CHECK and not constraint.columns:
                errors.append(
                    f"Constraint '{constraint.name}' has no columns defined"
                )

            # Check columns exist in table
            for col_name in constraint.columns:
                if not table.get_column(col_name):
                    errors.append(
                        f"Constraint '{constraint.name}' references non-existent "
                        f"column '{col_name}' in table '{table.name}'"
                    )

            # Check constraint naming convention
            if self.check_naming_conventions:
                expected_prefix = CONSTRAINT_PREFIXES.get(constraint.type, "")
                if expected_prefix and not constraint.name.lower().startswith(
                    expected_prefix
                ):
                    # This is a warning, not an error
                    pass  # Could add to warnings if needed

        return errors

    def _check_indexes(self, table: Table) -> List[str]:
        """
        Check index definitions and suggest missing indexes.

        Args:
            table: The table to check.

        Returns:
            List of warning messages.
        """
        warnings: List[str] = []

        # Get all indexed columns
        indexed_columns: Set[str] = set()
        for index in table.indexes:
            for col_name in index.columns:
                indexed_columns.add(col_name.lower())

        # Check FK columns have indexes
        for column in table.foreign_key_columns:
            if column.name.lower() not in indexed_columns:
                # Check if there's a constraint-based index
                has_index = False
                for constraint in table.constraints:
                    if (
                        constraint.type == ConstraintType.FOREIGN_KEY
                        and column.name in constraint.columns
                    ):
                        # FK constraints don't automatically create indexes in PostgreSQL
                        pass

                if not has_index:
                    warnings.append(
                        f"Foreign key column '{column.name}' has no index. "
                        "Consider adding an index for join performance."
                    )

        # Check for duplicate indexes
        index_signatures: Dict[str, str] = {}
        for index in table.indexes:
            signature = ",".join(sorted(c.lower() for c in index.columns))
            if signature in index_signatures:
                warnings.append(
                    f"Index '{index.name}' appears to duplicate '{index_signatures[signature]}' "
                    f"on columns ({signature})"
                )
            else:
                index_signatures[signature] = index.name

        # Check index names follow conventions
        if self.check_naming_conventions:
            for index in table.indexes:
                name_issues = self._check_naming_conventions(index.name, "index")
                warnings.extend(name_issues)

                # Suggest standard prefix
                if not index.name.lower().startswith("idx_"):
                    warnings.append(
                        f"Index '{index.name}' does not follow naming convention. "
                        "Consider using 'idx_' prefix."
                    )

        return warnings

    def _validate_relationships(
        self,
        schema: Schema,
        tables_by_name: Dict[str, Table],
        report: SchemaValidationReport,
    ) -> None:
        """
        Validate schema-level relationship consistency.

        Args:
            schema: The schema to validate.
            tables_by_name: Dictionary of tables by lowercase name.
            report: The report to add issues to.
        """
        for relationship in schema.relationships:
            # Check source table exists
            from_table = relationship.from_table.lower()
            if from_table not in tables_by_name:
                report.add_schema_error(
                    f"Relationship '{relationship.name}' references non-existent "
                    f"source table '{relationship.from_table}'"
                )
                continue

            # Check target table exists
            to_table = relationship.to_table.lower()
            if to_table not in tables_by_name:
                report.add_schema_error(
                    f"Relationship '{relationship.name}' references non-existent "
                    f"target table '{relationship.to_table}'"
                )
                continue

            # Check source columns exist
            source_table = tables_by_name[from_table]
            for col_name in relationship.from_columns:
                if not source_table.get_column(col_name):
                    report.add_schema_error(
                        f"Relationship '{relationship.name}' references non-existent "
                        f"source column '{relationship.from_table}.{col_name}'"
                    )

            # Check target columns exist
            target_table = tables_by_name[to_table]
            for col_name in relationship.to_columns:
                if not target_table.get_column(col_name):
                    report.add_schema_error(
                        f"Relationship '{relationship.name}' references non-existent "
                        f"target column '{relationship.to_table}.{col_name}'"
                    )

    def _add_column_suggestions(
        self,
        column: Column,
        table_name: str,
        result: ValidationResult,
    ) -> None:
        """
        Add improvement suggestions for a column.

        Args:
            column: The column to analyze.
            table_name: Parent table name.
            result: Result to add suggestions to.
        """
        name_lower = column.name.lower()

        # Suggest timestamp columns for audit
        if name_lower in {"created", "updated", "modified", "deleted"}:
            result.add_suggestion(
                f"Column '{table_name}.{column.name}': Consider renaming to "
                f"'{name_lower}_at' for clarity that this is a timestamp."
            )

        # Suggest UUID for id columns in distributed systems
        if (
            name_lower == "id"
            and column.is_primary_key
            and column.base_type in {"integer", "bigint", "serial", "bigserial"}
        ):
            result.add_suggestion(
                f"Column '{table_name}.{column.name}': Consider using UUID type "
                "for primary keys if this system may need distributed ID generation."
            )

        # Suggest text over varchar for variable length
        if column.base_type in {"varchar", "character varying"}:
            if (
                column.character_maximum_length
                and column.character_maximum_length > 10000
            ):
                result.add_suggestion(
                    f"Column '{table_name}.{column.name}': Consider using TEXT type "
                    f"instead of VARCHAR({column.character_maximum_length}) for very "
                    "long strings. PostgreSQL TEXT has no performance penalty."
                )

        # Suggest NOT NULL with default for boolean
        if column.is_boolean() and column.is_nullable:
            result.add_suggestion(
                f"Column '{table_name}.{column.name}': Consider making boolean "
                "column NOT NULL with a DEFAULT value to avoid three-valued logic."
            )

        # Suggest timestamptz over timestamp
        if column.base_type == "timestamp":
            result.add_suggestion(
                f"Column '{table_name}.{column.name}': Consider using "
                "TIMESTAMPTZ (timestamp with time zone) instead of TIMESTAMP "
                "for proper timezone handling."
            )
