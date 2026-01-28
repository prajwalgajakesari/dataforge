"""
First Normal Form (1NF) Normalizer.

This module provides the Normalizer1NF class for transforming tables that
violate First Normal Form into properly normalized relational structures.

1NF Requirements:
- All column values must be atomic (indivisible)
- No repeating groups (e.g., phone1, phone2, phone3)
- No multi-valued attributes (comma-separated lists, arrays)
- No nested or complex data structures (JSON with multiple fields)

The normalizer handles:
- Array columns -> Junction/bridge tables
- JSON columns -> Flattened columns or separate tables
- Repeating groups -> Separate tables with proper relationships
- Multi-valued strings -> Separate tables
- Compound values -> Split into atomic columns
"""

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from core.models.schema import (
    Table,
    Column,
    Constraint,
    ConstraintType,
    Index,
    IndexType,
    ReferentialAction,
)
from core.normalization.violations import Violation1NF, ViolationType, SeverityLevel


@dataclass
class NormalizationStep1NF:
    """
    Represents a single step in the 1NF normalization process.

    Each step documents what action was taken, which columns were affected,
    what new tables were created, and provides a human-readable description.

    Attributes:
        action: Type of normalization action performed.
        affected_columns: List of column names that were modified or removed.
        new_tables_created: Names of any new tables created by this step.
        description: Human-readable description of the normalization step.
        original_column: The original column that triggered this step.
        sql_migration: Optional SQL statements to perform this migration.
    """
    action: str
    affected_columns: List[str]
    new_tables_created: List[str]
    description: str
    original_column: Optional[str] = None
    sql_migration: Optional[List[str]] = None


@dataclass
class Normalization1NFResult:
    """
    Result of normalizing a table to First Normal Form.

    Contains the original table, all resulting normalized tables,
    the steps taken during normalization, and summary statistics.

    Attributes:
        original_table: The original table before normalization.
        normalized_tables: List of all tables after normalization
            (includes modified original and any new tables).
        steps: List of normalization steps performed.
        repeating_groups_extracted: Number of repeating groups normalized.
        arrays_flattened: Number of array columns converted to tables.
        json_columns_handled: Number of JSON columns normalized.
        multi_valued_extracted: Number of multi-valued columns normalized.
        compound_values_split: Number of compound columns atomized.
        is_fully_normalized: Whether table is now in 1NF.
    """
    original_table: Table
    normalized_tables: List[Table]
    steps: List[NormalizationStep1NF]
    repeating_groups_extracted: int = 0
    arrays_flattened: int = 0
    json_columns_handled: int = 0
    multi_valued_extracted: int = 0
    compound_values_split: int = 0
    is_fully_normalized: bool = True

    @property
    def new_tables_count(self) -> int:
        """Number of new tables created during normalization."""
        return len(self.normalized_tables) - 1

    @property
    def total_changes(self) -> int:
        """Total number of normalization changes made."""
        return (
            self.repeating_groups_extracted
            + self.arrays_flattened
            + self.json_columns_handled
            + self.multi_valued_extracted
            + self.compound_values_split
        )


class Normalizer1NF:
    """
    Normalizer for First Normal Form violations.

    This class transforms tables that violate 1NF into properly normalized
    relational structures. It handles various types of 1NF violations:

    - Array columns: Creates junction/bridge tables
    - JSON columns: Flattens to separate columns or tables
    - Repeating groups: Extracts to separate tables with sequences
    - Multi-valued strings: Creates junction tables
    - Compound values: Splits into atomic columns

    Usage:
        normalizer = Normalizer1NF()
        violations = detect_1nf_violations(table)
        result = normalizer.normalize(table, violations)

        # Access normalized tables
        for table in result.normalized_tables:
            print(table.name, [c.name for c in table.columns])

    Attributes:
        extract_to_separate_tables: If True, multi-valued data is extracted
            to separate tables. If False, attempts in-place flattening where
            possible (e.g., JSON with fixed fields).
    """

    # Semantic type hints for splitting compound values
    COMPOUND_PATTERNS = {
        "full_name": ["first_name", "last_name"],
        "name": ["first_name", "last_name"],
        "fullname": ["first_name", "last_name"],
        "address": ["street", "city", "state", "postal_code", "country"],
        "full_address": ["street", "city", "state", "postal_code", "country"],
        "location": ["city", "state", "country"],
        "datetime": ["date", "time"],
        "date_time": ["date", "time"],
        "phone_fax": ["phone", "fax"],
        "start_end": ["start", "end"],
        "min_max": ["min_value", "max_value"],
        "first_last": ["first", "last"],
        "lat_long": ["latitude", "longitude"],
        "latitude_longitude": ["latitude", "longitude"],
        "coordinates": ["latitude", "longitude"],
    }

    def __init__(self, extract_to_separate_tables: bool = True):
        """
        Initialize the 1NF normalizer.

        Args:
            extract_to_separate_tables: If True, multi-valued data is extracted
                to separate junction tables. If False, attempts flattening to
                columns where feasible.
        """
        self.extract_to_separate_tables = extract_to_separate_tables

    def normalize(
        self,
        table: Table,
        violations: List[Violation1NF],
    ) -> Normalization1NFResult:
        """
        Normalize a table to First Normal Form.

        Processes each violation and transforms the table structure to
        eliminate all 1NF violations. The original table is modified
        and additional tables may be created as needed.

        Args:
            table: The table to normalize.
            violations: List of 1NF violations detected in the table.

        Returns:
            Normalization1NFResult containing all normalized tables and
            metadata about the normalization process.
        """
        if not violations:
            return Normalization1NFResult(
                original_table=table,
                normalized_tables=[table],
                steps=[],
                is_fully_normalized=True,
            )

        # Create a working copy of the table
        working_table = self._copy_table(table)
        new_tables: List[Table] = []
        steps: List[NormalizationStep1NF] = []
        stats = {
            "repeating_groups": 0,
            "arrays": 0,
            "json": 0,
            "multi_valued": 0,
            "compound": 0,
        }

        # Group violations by type for organized processing
        violations_by_type: Dict[ViolationType, List[Violation1NF]] = {}
        for v in violations:
            if v.violation_type not in violations_by_type:
                violations_by_type[v.violation_type] = []
            violations_by_type[v.violation_type].append(v)

        # Process repeating groups first (they may involve multiple columns)
        for violation in violations_by_type.get(ViolationType.REPEATING_GROUP, []):
            result = self._handle_repeating_groups(
                working_table, violation.related_columns
            )
            if result:
                working_table, bridge_table = result
                new_tables.append(bridge_table)
                stats["repeating_groups"] += 1
                steps.append(NormalizationStep1NF(
                    action="extract_repeating_group",
                    affected_columns=violation.related_columns,
                    new_tables_created=[bridge_table.name],
                    description=(
                        f"Extracted repeating group {violation.related_columns} "
                        f"to new table '{bridge_table.name}'"
                    ),
                    original_column=violation.column_name,
                ))

        # Process array columns
        for violation in violations_by_type.get(ViolationType.ARRAY_COLUMN, []):
            column = working_table.get_column(violation.column_name)
            if column:
                result = self._handle_array_column(working_table, column)
                if result:
                    working_table, bridge_table = result
                    new_tables.append(bridge_table)
                    stats["arrays"] += 1
                    steps.append(NormalizationStep1NF(
                        action="flatten_array",
                        affected_columns=[column.name],
                        new_tables_created=[bridge_table.name],
                        description=(
                            f"Converted array column '{column.name}' to "
                            f"junction table '{bridge_table.name}'"
                        ),
                        original_column=column.name,
                    ))

        # Process JSON columns
        for violation in violations_by_type.get(ViolationType.JSON_COLUMN, []):
            column = working_table.get_column(violation.column_name)
            if column:
                result = self._handle_json_column(
                    working_table,
                    column,
                    violation.json_structure,
                )
                if result:
                    working_table = result[0]
                    for new_table in result[1:]:
                        new_tables.append(new_table)
                    stats["json"] += 1
                    new_table_names = [t.name for t in result[1:]] if len(result) > 1 else []
                    steps.append(NormalizationStep1NF(
                        action="flatten_json",
                        affected_columns=[column.name],
                        new_tables_created=new_table_names,
                        description=(
                            f"Flattened JSON column '{column.name}'"
                            + (f" to tables {new_table_names}" if new_table_names else " to columns")
                        ),
                        original_column=column.name,
                    ))

        # Process multi-valued columns
        for violation in violations_by_type.get(ViolationType.MULTI_VALUED, []):
            column = working_table.get_column(violation.column_name)
            if column:
                result = self._handle_multi_valued_column(
                    working_table,
                    column,
                    violation.detected_delimiter,
                )
                if result:
                    working_table, bridge_table = result
                    new_tables.append(bridge_table)
                    stats["multi_valued"] += 1
                    steps.append(NormalizationStep1NF(
                        action="extract_multi_valued",
                        affected_columns=[column.name],
                        new_tables_created=[bridge_table.name],
                        description=(
                            f"Extracted multi-valued column '{column.name}' "
                            f"to junction table '{bridge_table.name}'"
                        ),
                        original_column=column.name,
                    ))

        # Process non-atomic/compound values
        for violation in violations_by_type.get(ViolationType.NON_ATOMIC, []):
            column = working_table.get_column(violation.column_name)
            if column:
                result = self._make_atomic(column)
                if result and len(result) > 1:
                    # Replace column with atomic columns
                    working_table = self._replace_column_with_atomics(
                        working_table, column, result
                    )
                    stats["compound"] += 1
                    steps.append(NormalizationStep1NF(
                        action="split_compound",
                        affected_columns=[column.name] + [c.name for c in result],
                        new_tables_created=[],
                        description=(
                            f"Split compound column '{column.name}' into "
                            f"atomic columns: {[c.name for c in result]}"
                        ),
                        original_column=column.name,
                    ))

        # Combine all tables
        all_tables = [working_table] + new_tables

        return Normalization1NFResult(
            original_table=table,
            normalized_tables=all_tables,
            steps=steps,
            repeating_groups_extracted=stats["repeating_groups"],
            arrays_flattened=stats["arrays"],
            json_columns_handled=stats["json"],
            multi_valued_extracted=stats["multi_valued"],
            compound_values_split=stats["compound"],
            is_fully_normalized=len(violations) == len(steps),
        )

    def _handle_array_column(
        self,
        table: Table,
        column: Column,
    ) -> Optional[Tuple[Table, Table]]:
        """
        Handle an array column by creating a junction/bridge table.

        Creates a new table that stores array elements with a foreign key
        back to the original table. The original array column is removed.

        Args:
            table: The table containing the array column.
            column: The column with array type.

        Returns:
            Tuple of (modified original table, new bridge table), or None
            if the column cannot be processed.
        """
        # Generate bridge table name
        bridge_table_name = self._generate_bridge_table_name(table.name, column.name)

        # Infer element type from array type
        element_type = self._infer_array_element_type(column)

        # Get primary key columns from original table
        pk_columns = table.primary_key_columns
        if not pk_columns:
            pk_columns = ["id"]

        # Create bridge table columns
        bridge_columns = []

        # Foreign key column(s) to original table
        for pk_col in pk_columns:
            orig_col = table.get_column(pk_col)
            fk_col = Column(
                name=f"{table.name}_{pk_col}",
                data_type=orig_col.data_type if orig_col else "integer",
                is_nullable=False,
                is_foreign_key=True,
                foreign_key_table=table.name,
                foreign_key_column=pk_col,
            )
            bridge_columns.append(fk_col)

        # Value column for array elements
        value_col = Column(
            name=f"{column.name}_value",
            data_type=element_type,
            is_nullable=True,
        )
        bridge_columns.append(value_col)

        # Optional: sequence/position column
        seq_col = Column(
            name="sequence",
            data_type="integer",
            is_nullable=False,
            description="Position of element in original array",
        )
        bridge_columns.append(seq_col)

        # Create bridge table
        bridge_table = Table(
            name=bridge_table_name,
            schema_name=table.schema_name,
            columns=bridge_columns,
            description=f"Junction table for {table.name}.{column.name} array values",
        )

        # Add composite primary key constraint
        pk_constraint = Constraint(
            name=f"pk_{bridge_table_name}",
            type=ConstraintType.PRIMARY_KEY,
            columns=[c.name for c in bridge_columns if c.is_foreign_key] + ["sequence"],
        )
        bridge_table.constraints.append(pk_constraint)

        # Add foreign key constraint
        fk_constraint = Constraint(
            name=f"fk_{bridge_table_name}_{table.name}",
            type=ConstraintType.FOREIGN_KEY,
            columns=[f"{table.name}_{pk}" for pk in pk_columns],
            reference_table=table.name,
            reference_columns=pk_columns,
            on_delete=ReferentialAction.CASCADE,
        )
        bridge_table.constraints.append(fk_constraint)

        # Remove array column from original table
        modified_table = self._copy_table(table)
        modified_table.remove_column(column.name)

        return modified_table, bridge_table

    def _handle_json_column(
        self,
        table: Table,
        column: Column,
        json_structure: Optional[Dict[str, Any]] = None,
    ) -> Optional[List[Table]]:
        """
        Handle a JSON column by flattening to columns or separate tables.

        For simple JSON objects with a fixed set of fields, flattens to
        additional columns on the same table. For complex or nested JSON,
        creates separate tables.

        Args:
            table: The table containing the JSON column.
            column: The column with JSON type.
            json_structure: Detected structure of JSON values (optional).

        Returns:
            List of tables starting with modified original table, followed
            by any new tables created for nested structures.
        """
        modified_table = self._copy_table(table)

        if not json_structure:
            # No structure detected, just remove the column
            modified_table.remove_column(column.name)
            return [modified_table]

        structure_type = json_structure.get("type", "unknown")

        if structure_type == "object":
            # Flatten object fields to columns
            fields = json_structure.get("fields", {})

            if not self.extract_to_separate_tables and len(fields) <= 10:
                # Simple case: add columns directly to table
                return self._flatten_json_to_columns(
                    modified_table, column, fields
                )
            else:
                # Complex case: create separate table
                return self._flatten_json_to_table(
                    modified_table, column, fields
                )

        elif structure_type == "array":
            # JSON array - similar to array column
            element_type = self._detect_json_array_element_type(json_structure)
            return self._handle_json_array(modified_table, column, element_type)

        else:
            # Mixed or unknown - just remove
            modified_table.remove_column(column.name)
            return [modified_table]

    def _handle_repeating_groups(
        self,
        table: Table,
        columns: List[str],
    ) -> Optional[Tuple[Table, Table]]:
        """
        Handle repeating column groups by extracting to a separate table.

        Converts columns like phone1, phone2, phone3 into a separate table
        with a type/sequence column and a single value column.

        Args:
            table: The table containing the repeating group.
            columns: List of column names in the repeating group.

        Returns:
            Tuple of (modified original table, new extracted table), or None
            if the columns cannot be processed.
        """
        if not columns or len(columns) < 2:
            return None

        # Determine base name from columns
        base_name = self._extract_base_name(columns)
        if not base_name:
            base_name = columns[0].rstrip("0123456789_")

        # Generate new table name
        new_table_name = f"{table.name}_{base_name}s"

        # Get column type from first column in group
        first_col = table.get_column(columns[0])
        if not first_col:
            return None
        value_type = first_col.data_type

        # Get primary key columns
        pk_columns = table.primary_key_columns
        if not pk_columns:
            pk_columns = ["id"]

        # Create new table columns
        new_columns = []

        # Foreign key to original table
        for pk_col in pk_columns:
            orig_col = table.get_column(pk_col)
            fk_col = Column(
                name=f"{table.name}_{pk_col}",
                data_type=orig_col.data_type if orig_col else "integer",
                is_nullable=False,
                is_foreign_key=True,
                foreign_key_table=table.name,
                foreign_key_column=pk_col,
            )
            new_columns.append(fk_col)

        # Type/sequence column
        type_col = Column(
            name=f"{base_name}_type",
            data_type="varchar(50)",
            is_nullable=False,
            description=f"Type or sequence of {base_name}",
        )
        new_columns.append(type_col)

        # Value column
        value_col = Column(
            name=base_name,
            data_type=value_type,
            is_nullable=True,
            description=f"Value from repeating group",
        )
        new_columns.append(value_col)

        # Create new table
        new_table = Table(
            name=new_table_name,
            schema_name=table.schema_name,
            columns=new_columns,
            description=f"Normalized repeating group from {table.name}",
        )

        # Add primary key constraint
        pk_constraint = Constraint(
            name=f"pk_{new_table_name}",
            type=ConstraintType.PRIMARY_KEY,
            columns=[f"{table.name}_{pk}" for pk in pk_columns] + [f"{base_name}_type"],
        )
        new_table.constraints.append(pk_constraint)

        # Add foreign key constraint
        fk_constraint = Constraint(
            name=f"fk_{new_table_name}_{table.name}",
            type=ConstraintType.FOREIGN_KEY,
            columns=[f"{table.name}_{pk}" for pk in pk_columns],
            reference_table=table.name,
            reference_columns=pk_columns,
            on_delete=ReferentialAction.CASCADE,
        )
        new_table.constraints.append(fk_constraint)

        # Remove repeating columns from original table
        modified_table = self._copy_table(table)
        for col_name in columns:
            modified_table.remove_column(col_name)

        return modified_table, new_table

    def _handle_multi_valued_column(
        self,
        table: Table,
        column: Column,
        delimiter: Optional[str] = None,
    ) -> Optional[Tuple[Table, Table]]:
        """
        Handle a multi-valued (delimited) column by creating a junction table.

        Similar to array handling but for string columns containing
        delimiter-separated values.

        Args:
            table: The table containing the multi-valued column.
            column: The column with delimited values.
            delimiter: The detected delimiter (e.g., ",", ";").

        Returns:
            Tuple of (modified original table, new junction table).
        """
        # Generate bridge table name
        bridge_table_name = self._generate_bridge_table_name(table.name, column.name)

        # Get primary key columns
        pk_columns = table.primary_key_columns
        if not pk_columns:
            pk_columns = ["id"]

        # Create bridge table columns
        bridge_columns = []

        # Foreign key to original table
        for pk_col in pk_columns:
            orig_col = table.get_column(pk_col)
            fk_col = Column(
                name=f"{table.name}_{pk_col}",
                data_type=orig_col.data_type if orig_col else "integer",
                is_nullable=False,
                is_foreign_key=True,
                foreign_key_table=table.name,
                foreign_key_column=pk_col,
            )
            bridge_columns.append(fk_col)

        # Value column (text type to hold extracted values)
        value_col = Column(
            name=f"{column.name}_value",
            data_type="varchar(255)",
            is_nullable=False,
        )
        bridge_columns.append(value_col)

        # Create bridge table
        bridge_table = Table(
            name=bridge_table_name,
            schema_name=table.schema_name,
            columns=bridge_columns,
            description=f"Junction table for {table.name}.{column.name} values",
            metadata={"source_delimiter": delimiter} if delimiter else {},
        )

        # Add composite primary key
        pk_constraint = Constraint(
            name=f"pk_{bridge_table_name}",
            type=ConstraintType.PRIMARY_KEY,
            columns=[c.name for c in bridge_columns],
        )
        bridge_table.constraints.append(pk_constraint)

        # Add foreign key constraint
        fk_constraint = Constraint(
            name=f"fk_{bridge_table_name}_{table.name}",
            type=ConstraintType.FOREIGN_KEY,
            columns=[f"{table.name}_{pk}" for pk in pk_columns],
            reference_table=table.name,
            reference_columns=pk_columns,
            on_delete=ReferentialAction.CASCADE,
        )
        bridge_table.constraints.append(fk_constraint)

        # Remove multi-valued column from original table
        modified_table = self._copy_table(table)
        modified_table.remove_column(column.name)

        return modified_table, bridge_table

    def _make_atomic(self, column: Column) -> List[Column]:
        """
        Split a compound column into atomic columns.

        Uses semantic type hints and column name patterns to determine
        how to split compound values (e.g., full_name -> first_name, last_name).

        Args:
            column: The column with compound values.

        Returns:
            List of atomic columns to replace the compound column.
            Returns a single-element list with the original column if
            no splitting pattern is detected.
        """
        col_name_lower = column.name.lower()

        # Check for known compound patterns
        for pattern, parts in self.COMPOUND_PATTERNS.items():
            if pattern in col_name_lower or col_name_lower == pattern:
                # Determine base type for split columns
                if column.is_text():
                    part_type = "varchar(100)"
                else:
                    part_type = column.data_type

                atomic_columns = []
                for part in parts:
                    atomic_col = Column(
                        name=f"{column.name}_{part}" if column.name != pattern else part,
                        data_type=part_type,
                        is_nullable=column.is_nullable,
                        description=f"Atomic value extracted from {column.name}",
                    )
                    atomic_columns.append(atomic_col)

                return atomic_columns

        # Check semantic type hints
        if column.semantic_type:
            semantic_lower = column.semantic_type.lower()
            if "name" in semantic_lower and "full" in semantic_lower:
                return [
                    Column(
                        name=f"{column.name}_first",
                        data_type="varchar(50)",
                        is_nullable=column.is_nullable,
                    ),
                    Column(
                        name=f"{column.name}_last",
                        data_type="varchar(50)",
                        is_nullable=column.is_nullable,
                    ),
                ]
            elif "address" in semantic_lower and "full" in semantic_lower:
                return [
                    Column(name="street", data_type="varchar(200)", is_nullable=True),
                    Column(name="city", data_type="varchar(100)", is_nullable=True),
                    Column(name="state", data_type="varchar(50)", is_nullable=True),
                    Column(name="postal_code", data_type="varchar(20)", is_nullable=True),
                ]

        # No pattern found - return original
        return [column]

    def _detect_json_structure(
        self,
        column: Column,
        sample_values: List[Any],
    ) -> Dict[str, Any]:
        """
        Detect the structure of JSON values in a column.

        Analyzes sample values to determine:
        - Whether values are objects, arrays, or mixed
        - For objects: field names and their types
        - For arrays: average length and element types

        Args:
            column: The JSON column.
            sample_values: Sample values from the column.

        Returns:
            Dict describing the JSON structure with keys:
            - "type": "object" | "array" | "mixed"
            - "fields": Dict of field info (for objects)
            - "array_length_avg": Average array length (for arrays)
        """
        parsed = []
        for value in sample_values:
            if value is None:
                continue
            try:
                if isinstance(value, str):
                    parsed.append(json.loads(value))
                elif isinstance(value, (dict, list)):
                    parsed.append(value)
            except (json.JSONDecodeError, TypeError):
                continue

        if not parsed:
            return {"type": "unknown"}

        # Determine type
        types = [type(p).__name__ for p in parsed]
        if all(t == "dict" for t in types):
            structure_type = "object"
        elif all(t == "list" for t in types):
            structure_type = "array"
        else:
            structure_type = "mixed"

        result: Dict[str, Any] = {"type": structure_type}

        if structure_type == "object":
            fields: Dict[str, Dict[str, Any]] = {}
            for obj in parsed:
                if isinstance(obj, dict):
                    for key, val in obj.items():
                        if key not in fields:
                            fields[key] = {"types": set(), "count": 0}
                        fields[key]["types"].add(type(val).__name__)
                        fields[key]["count"] += 1

            result["fields"] = {
                k: {"types": list(v["types"]), "count": v["count"]}
                for k, v in fields.items()
            }

        elif structure_type == "array":
            lengths = [len(a) for a in parsed if isinstance(a, list)]
            result["array_length_avg"] = sum(lengths) / len(lengths) if lengths else 0

        return result

    def _generate_bridge_table_name(
        self,
        table_name: str,
        column_name: str,
    ) -> str:
        """
        Generate a name for a bridge/junction table.

        Creates a descriptive name following naming conventions:
        {table_name}_{column_name}s or {table_name}_{column_name}_values

        Args:
            table_name: Name of the original table.
            column_name: Name of the column being extracted.

        Returns:
            Generated bridge table name.
        """
        # Clean up column name
        base = column_name.rstrip("s")

        # Avoid double pluralization
        if base.endswith("_value"):
            return f"{table_name}_{base}s"

        return f"{table_name}_{base}_values"

    def _infer_array_element_type(self, column: Column) -> str:
        """
        Infer the element type of an array column.

        Parses the array type declaration to extract the element type.

        Args:
            column: The column with array type.

        Returns:
            SQL type string for the array elements.
        """
        data_type = column.data_type.lower()

        # PostgreSQL style: integer[], text[], etc.
        if "[]" in data_type:
            return data_type.replace("[]", "").strip()

        # PostgreSQL internal style: _int4, _text, etc.
        if data_type.startswith("_"):
            type_map = {
                "_int4": "integer",
                "_int8": "bigint",
                "_float8": "double precision",
                "_text": "text",
                "_varchar": "varchar(255)",
                "_bool": "boolean",
                "_timestamp": "timestamp",
                "_uuid": "uuid",
            }
            return type_map.get(data_type, "text")

        # ARRAY keyword style: ARRAY[integer]
        match = re.search(r"array\s*\[(\w+)\]", data_type, re.IGNORECASE)
        if match:
            return match.group(1)

        # Default to text
        return "text"

    def _detect_json_array_element_type(
        self,
        json_structure: Dict[str, Any],
    ) -> str:
        """
        Detect the element type for a JSON array.

        Args:
            json_structure: The analyzed JSON structure.

        Returns:
            SQL type string for array elements.
        """
        # For now, default to text
        # Could be enhanced to analyze element structure
        return "text"

    def _flatten_json_to_columns(
        self,
        table: Table,
        column: Column,
        fields: Dict[str, Dict[str, Any]],
    ) -> List[Table]:
        """
        Flatten JSON object fields into additional columns on the table.

        Args:
            table: The table to modify.
            column: The JSON column being flattened.
            fields: Dict of field names to type info.

        Returns:
            List containing only the modified table.
        """
        # Add a column for each JSON field
        for field_name, field_info in fields.items():
            # Infer type from field info
            types = field_info.get("types", ["str"])
            sql_type = self._json_type_to_sql(types)

            new_col = Column(
                name=f"{column.name}_{field_name}",
                data_type=sql_type,
                is_nullable=True,
                description=f"Extracted from JSON field '{field_name}'",
            )
            table.add_column(new_col)

        # Remove original JSON column
        table.remove_column(column.name)

        return [table]

    def _flatten_json_to_table(
        self,
        table: Table,
        column: Column,
        fields: Dict[str, Dict[str, Any]],
    ) -> List[Table]:
        """
        Extract JSON object to a separate table.

        Args:
            table: The original table.
            column: The JSON column being extracted.
            fields: Dict of field names to type info.

        Returns:
            List of tables: [modified original, new JSON table].
        """
        # Generate new table name
        new_table_name = f"{table.name}_{column.name}"

        # Get primary key columns
        pk_columns = table.primary_key_columns
        if not pk_columns:
            pk_columns = ["id"]

        new_columns = []

        # Foreign key to original table
        for pk_col in pk_columns:
            orig_col = table.get_column(pk_col)
            fk_col = Column(
                name=f"{table.name}_{pk_col}",
                data_type=orig_col.data_type if orig_col else "integer",
                is_nullable=False,
                is_primary_key=True,
                is_foreign_key=True,
                foreign_key_table=table.name,
                foreign_key_column=pk_col,
            )
            new_columns.append(fk_col)

        # Add columns for each JSON field
        for field_name, field_info in fields.items():
            types = field_info.get("types", ["str"])
            sql_type = self._json_type_to_sql(types)

            field_col = Column(
                name=field_name,
                data_type=sql_type,
                is_nullable=True,
            )
            new_columns.append(field_col)

        # Create new table
        new_table = Table(
            name=new_table_name,
            schema_name=table.schema_name,
            columns=new_columns,
            description=f"Extracted JSON data from {table.name}.{column.name}",
        )

        # Add foreign key constraint
        fk_constraint = Constraint(
            name=f"fk_{new_table_name}_{table.name}",
            type=ConstraintType.FOREIGN_KEY,
            columns=[f"{table.name}_{pk}" for pk in pk_columns],
            reference_table=table.name,
            reference_columns=pk_columns,
            on_delete=ReferentialAction.CASCADE,
        )
        new_table.constraints.append(fk_constraint)

        # Remove JSON column from original
        table.remove_column(column.name)

        return [table, new_table]

    def _handle_json_array(
        self,
        table: Table,
        column: Column,
        element_type: str,
    ) -> List[Table]:
        """
        Handle a JSON array column similar to native array handling.

        Args:
            table: The table containing the JSON array column.
            column: The JSON column.
            element_type: Inferred type of array elements.

        Returns:
            List of tables: [modified original, bridge table].
        """
        result = self._handle_array_column(table, column)
        if result:
            return list(result)
        return [table]

    def _json_type_to_sql(self, types: List[str]) -> str:
        """
        Convert Python/JSON types to SQL type.

        Args:
            types: List of Python type names observed.

        Returns:
            Appropriate SQL type.
        """
        if not types:
            return "text"

        # Use most specific type if only one
        if len(types) == 1:
            type_name = types[0].lower()
            type_map = {
                "int": "integer",
                "float": "double precision",
                "bool": "boolean",
                "str": "text",
                "nonetype": "text",
                "list": "jsonb",
                "dict": "jsonb",
            }
            return type_map.get(type_name, "text")

        # Mixed types - use text
        return "text"

    def _extract_base_name(self, columns: List[str]) -> Optional[str]:
        """
        Extract the common base name from a list of numbered column names.

        Args:
            columns: List of column names like ["phone1", "phone2", "phone3"].

        Returns:
            Base name (e.g., "phone") or None if no pattern found.
        """
        if not columns:
            return None

        # Try to find common prefix
        first = columns[0].lower()

        # Remove trailing digits and underscores
        base = re.sub(r"[_\d]+$", "", first)

        if base and all(c.lower().startswith(base) for c in columns):
            return base

        return None

    def _replace_column_with_atomics(
        self,
        table: Table,
        old_column: Column,
        new_columns: List[Column],
    ) -> Table:
        """
        Replace a compound column with atomic columns.

        Args:
            table: The table to modify.
            old_column: The column to remove.
            new_columns: The atomic columns to add.

        Returns:
            Modified table.
        """
        # Find position of old column
        old_position = None
        for i, col in enumerate(table.columns):
            if col.name == old_column.name:
                old_position = i
                break

        # Remove old column
        table.remove_column(old_column.name)

        # Insert new columns at the same position
        if old_position is not None:
            for i, new_col in enumerate(new_columns):
                table.columns.insert(old_position + i, new_col)
        else:
            # Append if position not found
            for new_col in new_columns:
                table.columns.append(new_col)

        return table

    def _copy_table(self, table: Table) -> Table:
        """
        Create a shallow copy of a table.

        Args:
            table: The table to copy.

        Returns:
            A new Table instance with copied attributes.
        """
        return Table(
            name=table.name,
            schema_name=table.schema_name,
            columns=list(table.columns),
            constraints=list(table.constraints),
            indexes=list(table.indexes),
            row_count=table.row_count,
            size_bytes=table.size_bytes,
            description=table.description,
            table_type=table.table_type,
            is_partitioned=table.is_partitioned,
            partition_key=table.partition_key,
            tags=list(table.tags),
            metadata=dict(table.metadata),
        )
