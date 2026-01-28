"""
Normalization violation models and detection.

This module provides data classes representing violations of various
normal forms (1NF, 2NF, 3NF, BCNF). These are used during schema analysis
to identify normalization issues and guide the normalization process.

Violations:
- 1NF: Non-atomic values, repeating groups, array/JSON columns
- 2NF: Partial dependencies (for composite keys only)
- 3NF: Transitive dependencies
- BCNF: Non-superkey determinants

Usage:
    from core.normalization.violations import ViolationDetector

    detector = ViolationDetector(tables, functional_dependencies, candidate_keys)
    all_violations = detector.detect_all_violations()
    normal_form = detector.get_highest_normal_form("my_table")
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple, Union

from core.models.schema import Table, Column, ForeignKeyRelationship
from core.models.analysis import FunctionalDependency, CandidateKey, ColumnProfile
from core.models.types import SemanticType


class ViolationType(str, Enum):
    """Types of normalization violations."""

    # 1NF Violations
    MULTI_VALUED = "multi_valued"  # Comma-separated or delimited values
    REPEATING_GROUP = "repeating_group"  # phone1, phone2, phone3
    ARRAY_COLUMN = "array_column"  # Array data type
    JSON_COLUMN = "json_column"  # JSON/JSONB data type
    NESTED_STRUCTURE = "nested_structure"  # Complex nested data
    NON_ATOMIC = "non_atomic"  # General non-atomic values

    # 2NF Violations
    PARTIAL_DEPENDENCY = "partial_dependency"  # Depends on part of composite key

    # 3NF Violations
    TRANSITIVE_DEPENDENCY = "transitive_dependency"  # Non-key determines non-key

    # BCNF Violations
    NON_BCNF_DETERMINANT = "non_bcnf_determinant"

    # Legacy aliases
    MULTI_VALUED_ATTRIBUTE = "multi_valued_attribute"  # 1NF (legacy alias)


class SeverityLevel(str, Enum):
    """Severity level of a violation."""

    CRITICAL = "critical"  # Must be fixed for proper normalization
    HIGH = "high"  # Should be fixed for data integrity
    MEDIUM = "medium"  # Recommended to fix
    LOW = "low"  # Minor issue, optional to fix
    INFO = "info"  # Informational finding


# Alias for backward compatibility
ViolationSeverity = SeverityLevel


@dataclass
class NFViolation:
    """Base class for all normal form violations.

    This dataclass represents a normalization violation detected in a database
    table. It provides common attributes shared by all violation types.

    Attributes:
        table: Name of the table containing the violation.
        columns: Set of column names involved in the violation.
        violation_type: The type of normalization violation.
        severity: Severity level of the violation.
        description: Human-readable description of the violation.
        fix_suggestion: Suggested fix for the violation.
        normal_form: The normal form being violated (1NF, 2NF, 3NF, BCNF).

    Example:
        >>> violation = NFViolation(
        ...     table="orders",
        ...     columns=frozenset({"phone1", "phone2"}),
        ...     violation_type=ViolationType.REPEATING_GROUP,
        ...     severity=SeverityLevel.HIGH,
        ...     description="Repeating phone columns detected",
        ...     fix_suggestion="Create a separate phones table"
        ... )
    """
    table: str
    columns: FrozenSet[str]
    violation_type: ViolationType
    severity: SeverityLevel
    description: str
    fix_suggestion: str
    normal_form: str = "UNKNOWN"

    def __post_init__(self) -> None:
        """Convert columns to frozenset if necessary."""
        if isinstance(self.columns, (set, list, tuple)):
            object.__setattr__(self, 'columns', frozenset(self.columns))

    def to_dict(self) -> Dict[str, Any]:
        """Convert violation to dictionary representation.

        Returns:
            Dictionary with all violation attributes.
        """
        return {
            "table": self.table,
            "columns": list(self.columns),
            "violation_type": self.violation_type.value,
            "severity": self.severity.value,
            "description": self.description,
            "fix_suggestion": self.fix_suggestion,
            "normal_form": self.normal_form,
        }


@dataclass
class Violation1NF:
    """
    First Normal Form violation.

    1NF violations occur when a table contains:
    - Non-atomic values (multiple values in a single cell)
    - Repeating groups (e.g., phone1, phone2, phone3)
    - Array or JSON columns (in strict relational model)

    Attributes:
        column_name: Name of the column with the violation.
        violation_type: Type of 1NF violation.
        description: Human-readable description of the violation.
        severity: Severity level of the violation.
        sample_values: Example values demonstrating the violation.
        detected_delimiter: Delimiter used for multi-valued fields (if applicable).
        related_columns: Other columns in a repeating group (if applicable).
        suggested_fix: Recommended approach to fix the violation.
        estimated_new_tables: Number of new tables needed to fix.
        json_structure: Detected JSON structure (if JSON column).
    """
    column_name: str
    violation_type: ViolationType
    description: str
    severity: SeverityLevel = SeverityLevel.HIGH
    sample_values: List[Any] = field(default_factory=list)
    detected_delimiter: Optional[str] = None
    related_columns: List[str] = field(default_factory=list)
    suggested_fix: Optional[str] = None
    estimated_new_tables: int = 1
    json_structure: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """Set default suggested fix based on violation type."""
        if self.suggested_fix is None:
            fixes = {
                ViolationType.MULTI_VALUED: (
                    f"Extract values from '{self.column_name}' into a separate "
                    "table with a foreign key relationship"
                ),
                ViolationType.REPEATING_GROUP: (
                    f"Consolidate repeating columns {self.related_columns} into "
                    "a separate table with type/sequence column"
                ),
                ViolationType.ARRAY_COLUMN: (
                    f"Convert array column '{self.column_name}' to a junction "
                    "table for proper relational modeling"
                ),
                ViolationType.JSON_COLUMN: (
                    f"Flatten JSON column '{self.column_name}' into separate "
                    "columns or extract to related tables"
                ),
                ViolationType.NESTED_STRUCTURE: (
                    f"Decompose nested structure in '{self.column_name}' into "
                    "normalized related tables"
                ),
                ViolationType.NON_ATOMIC: (
                    f"Split compound values in '{self.column_name}' into "
                    "separate atomic columns"
                ),
            }
            self.suggested_fix = fixes.get(
                self.violation_type,
                f"Normalize column '{self.column_name}' to atomic values"
            )

    def __str__(self) -> str:
        """Return string representation."""
        return f"1NF Violation ({self.violation_type.value}): {self.description}"


@dataclass
class Violation2NF:
    """
    Represents a Second Normal Form violation (partial dependency).

    A 2NF violation occurs when a non-prime attribute (not part of any
    candidate key) is functionally dependent on a proper subset of a
    candidate key. This typically happens with composite primary keys.

    Example:
        In a table with PK (order_id, product_id):
        - If product_name depends only on product_id, this is a 2NF violation
        - The determinant {product_id} is a proper subset of the full PK

    Attributes:
        table_name: Name of the table with the violation.
        partial_key: The subset of the primary key causing the violation.
        dependent_columns: Columns dependent on the partial key.
        full_primary_key: The complete primary key of the table.
        description: Human-readable description of the violation.
        severity: Severity level (low, medium, high).
        functional_dependency_str: String representation of the FD.

    Example:
        >>> violation = Violation2NF(
        ...     table_name="order_details",
        ...     partial_key=["product_id"],
        ...     dependent_columns=["product_name", "product_category"],
        ...     full_primary_key=["order_id", "product_id"],
        ...     description="product_name depends only on product_id"
        ... )
    """

    table_name: str
    partial_key: List[str]
    dependent_columns: List[str]
    full_primary_key: List[str]
    description: str = ""
    severity: str = "medium"
    functional_dependency_str: str = field(default="", init=False)

    def __post_init__(self) -> None:
        """Set the functional dependency string after initialization."""
        det = ", ".join(self.partial_key)
        dep = ", ".join(self.dependent_columns)
        self.functional_dependency_str = f"{{{det}}} -> {{{dep}}}"

        if not self.description:
            self.description = (
                f"Columns {self.dependent_columns} depend on partial key "
                f"{self.partial_key}, which is a subset of the full primary key "
                f"{self.full_primary_key}"
            )

    @property
    def is_proper_subset(self) -> bool:
        """Check if partial_key is a proper subset of full_primary_key."""
        partial_set = set(self.partial_key)
        full_set = set(self.full_primary_key)
        return partial_set < full_set  # proper subset

    def __str__(self) -> str:
        """Return string representation of the violation."""
        return (
            f"2NF Violation in {self.table_name}: "
            f"{self.functional_dependency_str}"
        )

    def __repr__(self) -> str:
        """Return detailed representation."""
        return (
            f"Violation2NF(table={self.table_name!r}, "
            f"partial_key={self.partial_key!r}, "
            f"dependent_columns={self.dependent_columns!r})"
        )


@dataclass
class Violation3NF:
    """
    Represents a Third Normal Form violation (transitive dependency).

    A 3NF violation occurs when a non-prime attribute depends on another
    non-prime attribute (transitive dependency through a non-key attribute).

    Example:
        In an employees table with PK (employee_id):
        - employee_id -> department_id (direct)
        - department_id -> department_name (transitive violation)

    Attributes:
        table_name: Name of the table with the violation.
        determinant: Non-key column(s) that other columns depend on.
        dependent_columns: Columns dependent on the determinant.
        primary_key: The primary key of the table.
        description: Human-readable description.
        severity: Severity level.
    """

    table_name: str
    determinant: List[str]
    dependent_columns: List[str]
    primary_key: List[str]
    description: str = ""
    severity: str = "medium"
    functional_dependency_str: str = field(default="", init=False)

    def __post_init__(self) -> None:
        """Set the functional dependency string after initialization."""
        det = ", ".join(self.determinant)
        dep = ", ".join(self.dependent_columns)
        self.functional_dependency_str = f"{{{det}}} -> {{{dep}}}"

        if not self.description:
            self.description = (
                f"Columns {self.dependent_columns} transitively depend on "
                f"non-key columns {self.determinant}"
            )

    def __str__(self) -> str:
        """Return string representation."""
        return (
            f"3NF Violation in {self.table_name}: "
            f"{self.functional_dependency_str}"
        )


@dataclass
class ViolationBCNF:
    """
    Represents a Boyce-Codd Normal Form violation.

    A BCNF violation occurs when a determinant of a non-trivial
    functional dependency is not a superkey.

    Attributes:
        table_name: Name of the table with the violation.
        determinant: Column(s) that are the determinant.
        dependent_columns: Columns dependent on the determinant.
        candidate_keys: All candidate keys of the table.
        description: Human-readable description.
        severity: Severity level.
    """

    table_name: str
    determinant: List[str]
    dependent_columns: List[str]
    candidate_keys: List[List[str]]
    description: str = ""
    severity: str = "high"
    functional_dependency_str: str = field(default="", init=False)

    def __post_init__(self) -> None:
        """Set the functional dependency string after initialization."""
        det = ", ".join(self.determinant)
        dep = ", ".join(self.dependent_columns)
        self.functional_dependency_str = f"{{{det}}} -> {{{dep}}}"

        if not self.description:
            self.description = (
                f"Determinant {self.determinant} is not a superkey. "
                f"Candidate keys are: {self.candidate_keys}"
            )

    def __str__(self) -> str:
        """Return string representation."""
        return (
            f"BCNF Violation in {self.table_name}: "
            f"{self.functional_dependency_str}"
        )


class ViolationDetector:
    """
    Detector for normalization violations.

    This class provides methods to detect violations at each normal form
    level (1NF, 2NF, 3NF, BCNF) in database tables.

    Usage:
        detector = ViolationDetector()

        # Detect 1NF violations
        violations_1nf = detector.detect_1nf_violations(table, profiles)

        # Detect all violations
        all_violations = detector.detect_all_violations(table, fds, profiles)

    Attributes:
        min_delimiter_occurrences: Minimum occurrences of a delimiter to consider
            a column as multi-valued.
        min_delimiter_ratio: Minimum ratio of values containing delimiter.
        check_json_structure: Whether to analyze JSON column structure.
    """

    # Common delimiters for multi-valued fields
    DELIMITERS = [",", ";", "|", "\t", "\n", " / ", " - "]

    # Common repeating group base names
    REPEATING_BASE_NAMES = [
        "phone", "email", "address", "contact", "line", "option",
        "item", "choice", "value", "field", "attr", "param"
    ]

    def __init__(
        self,
        min_delimiter_occurrences: int = 3,
        min_delimiter_ratio: float = 0.1,
        check_json_structure: bool = True,
    ):
        """
        Initialize the violation detector.

        Args:
            min_delimiter_occurrences: Minimum occurrences of a delimiter
                to consider a column as multi-valued.
            min_delimiter_ratio: Minimum ratio of values containing delimiter
                to total non-null values.
            check_json_structure: Whether to analyze JSON column structure.
        """
        self.min_delimiter_occurrences = min_delimiter_occurrences
        self.min_delimiter_ratio = min_delimiter_ratio
        self.check_json_structure = check_json_structure

    def detect_1nf_violations(
        self,
        table: Table,
        profiles: Optional[Dict[str, ColumnProfile]] = None,
        sample_values: Optional[Dict[str, List[Any]]] = None,
    ) -> List[Violation1NF]:
        """
        Detect First Normal Form violations in a table.

        Checks for:
        1. Array data types
        2. JSON/JSONB data types
        3. Multi-valued string columns (comma-separated, etc.)
        4. Repeating column groups (phone1, phone2, phone3)

        Args:
            table: Table to analyze.
            profiles: Column profiles with statistics (optional).
            sample_values: Sample values for each column (optional).

        Returns:
            List of Violation1NF objects describing found violations.
        """
        violations: List[Violation1NF] = []

        # Check for array columns
        violations.extend(self._detect_array_columns(table))

        # Check for JSON columns
        violations.extend(
            self._detect_json_columns(table, profiles, sample_values)
        )

        # Check for multi-valued string columns
        if sample_values:
            violations.extend(
                self._detect_multi_valued_columns(table, sample_values)
            )
        elif profiles:
            # Use sample values from profiles
            sample_vals = {
                name: prof.sample_values
                for name, prof in profiles.items()
                if prof.sample_values
            }
            violations.extend(
                self._detect_multi_valued_columns(table, sample_vals)
            )

        # Check for repeating groups
        violations.extend(self._detect_repeating_groups(table))

        return violations

    def detect_2nf_violations(
        self,
        table: Table,
        fds: List[FunctionalDependency],
    ) -> List[Violation2NF]:
        """
        Detect Second Normal Form violations in a table.

        2NF violations only apply to tables with composite primary keys.
        A violation occurs when a non-key column depends on only part
        of the primary key.

        Args:
            table: Table to analyze.
            fds: Functional dependencies discovered in the table.

        Returns:
            List of Violation2NF objects.
        """
        violations: List[Violation2NF] = []

        # Get primary key
        pk_columns = table.primary_key_columns

        # 2NF only applies to composite keys
        if len(pk_columns) < 2:
            return violations

        pk_set = set(pk_columns)

        # Check each FD for partial dependencies
        for fd in fds:
            # Skip if the dependent is part of the key
            if fd.dependent in pk_set:
                continue

            det_set = set(fd.determinant)

            # Check if determinant is a proper subset of the primary key
            if det_set < pk_set:
                violations.append(Violation2NF(
                    table_name=table.name,
                    partial_key=fd.determinant,
                    dependent_columns=[fd.dependent],
                    full_primary_key=pk_columns,
                ))

        return violations

    def detect_3nf_violations(
        self,
        table: Table,
        fds: List[FunctionalDependency],
    ) -> List[Violation3NF]:
        """
        Detect Third Normal Form violations in a table.

        A 3NF violation occurs when a non-key attribute depends on
        another non-key attribute (transitive dependency).

        Args:
            table: Table to analyze.
            fds: Functional dependencies discovered in the table.

        Returns:
            List of Violation3NF objects.
        """
        violations: List[Violation3NF] = []

        pk_columns = table.primary_key_columns
        pk_set = set(pk_columns)

        # Build a map of what each column is determined by
        determined_by: Dict[str, List[FunctionalDependency]] = {}
        for fd in fds:
            if fd.dependent not in determined_by:
                determined_by[fd.dependent] = []
            determined_by[fd.dependent].append(fd)

        # Check for transitive dependencies
        for fd in fds:
            det_set = set(fd.determinant)

            # Skip if determinant includes a key column
            if det_set & pk_set:
                continue

            # Skip if dependent is a key column
            if fd.dependent in pk_set:
                continue

            # This is a non-key -> non-key dependency
            # Check if the determinant itself is determined by the PK
            for det_col in fd.determinant:
                if det_col in determined_by:
                    for parent_fd in determined_by[det_col]:
                        if set(parent_fd.determinant) & pk_set:
                            # Found transitive chain: PK -> det_col -> dependent
                            violations.append(Violation3NF(
                                table_name=table.name,
                                determinant=fd.determinant,
                                dependent_columns=[fd.dependent],
                                primary_key=pk_columns,
                            ))
                            break

        return violations

    def detect_bcnf_violations(
        self,
        table: Table,
        fds: List[FunctionalDependency],
        candidate_keys: List[List[str]],
    ) -> List[ViolationBCNF]:
        """
        Detect Boyce-Codd Normal Form violations in a table.

        A BCNF violation occurs when a functional dependency has a
        determinant that is not a superkey.

        Args:
            table: Table to analyze.
            fds: Functional dependencies discovered in the table.
            candidate_keys: List of candidate keys for the table.

        Returns:
            List of ViolationBCNF objects.
        """
        violations: List[ViolationBCNF] = []

        # Convert candidate keys to sets for comparison
        key_sets = [set(ck) for ck in candidate_keys]

        for fd in fds:
            det_set = set(fd.determinant)

            # Check if determinant is a superkey (contains a candidate key)
            is_superkey = any(ck <= det_set for ck in key_sets)

            if not is_superkey:
                violations.append(ViolationBCNF(
                    table_name=table.name,
                    determinant=fd.determinant,
                    dependent_columns=[fd.dependent],
                    candidate_keys=candidate_keys,
                ))

        return violations

    def detect_all_violations(
        self,
        table: Table,
        fds: List[FunctionalDependency],
        profiles: Optional[Dict[str, ColumnProfile]] = None,
        sample_values: Optional[Dict[str, List[Any]]] = None,
        candidate_keys: Optional[List[List[str]]] = None,
    ) -> Dict[str, List]:
        """
        Detect all normalization violations in a table.

        Args:
            table: Table to analyze.
            fds: Functional dependencies discovered in the table.
            profiles: Column profiles with statistics.
            sample_values: Sample values for each column.
            candidate_keys: List of candidate keys.

        Returns:
            Dict with keys '1nf', '2nf', '3nf', 'bcnf' containing
            lists of violations at each level.
        """
        # If no candidate keys provided, use primary key
        if candidate_keys is None:
            pk = table.primary_key_columns
            candidate_keys = [pk] if pk else []

        return {
            "1nf": self.detect_1nf_violations(table, profiles, sample_values),
            "2nf": self.detect_2nf_violations(table, fds),
            "3nf": self.detect_3nf_violations(table, fds),
            "bcnf": self.detect_bcnf_violations(table, fds, candidate_keys),
        }

    def _detect_array_columns(self, table: Table) -> List[Violation1NF]:
        """Detect columns with array data types."""
        violations = []

        for column in table.columns:
            data_type_lower = column.data_type.lower()

            # Check for array types
            if (
                "[]" in data_type_lower
                or "array" in data_type_lower
                or data_type_lower.startswith("_")  # PostgreSQL array notation
            ):
                violations.append(Violation1NF(
                    column_name=column.name,
                    violation_type=ViolationType.ARRAY_COLUMN,
                    description=(
                        f"Column '{column.name}' has array type "
                        f"'{column.data_type}', violating 1NF atomicity"
                    ),
                    severity=SeverityLevel.HIGH,
                ))

        return violations

    def _detect_json_columns(
        self,
        table: Table,
        profiles: Optional[Dict[str, ColumnProfile]] = None,
        sample_values: Optional[Dict[str, List[Any]]] = None,
    ) -> List[Violation1NF]:
        """Detect columns with JSON data types and analyze structure."""
        violations = []

        for column in table.columns:
            if not column.is_json():
                continue

            # Basic JSON violation
            violation = Violation1NF(
                column_name=column.name,
                violation_type=ViolationType.JSON_COLUMN,
                description=(
                    f"Column '{column.name}' has JSON type "
                    f"'{column.data_type}', which may violate 1NF depending "
                    "on usage"
                ),
                severity=SeverityLevel.MEDIUM,
            )

            # Analyze JSON structure if possible
            if self.check_json_structure:
                samples = None
                if sample_values and column.name in sample_values:
                    samples = sample_values[column.name]
                elif profiles and column.name in profiles:
                    samples = profiles[column.name].sample_values

                if samples:
                    structure = self._analyze_json_structure(samples)
                    if structure:
                        violation.json_structure = structure
                        violation.severity = SeverityLevel.HIGH
                        violation.description = (
                            f"Column '{column.name}' contains structured JSON "
                            f"data with fields: {list(structure.get('fields', {}).keys())}"
                        )

            violations.append(violation)

        return violations

    def _detect_multi_valued_columns(
        self,
        table: Table,
        sample_values: Dict[str, List[Any]],
    ) -> List[Violation1NF]:
        """Detect columns containing multi-valued (delimited) data."""
        violations = []

        for column in table.columns:
            # Only check text columns
            if not column.is_text():
                continue

            samples = sample_values.get(column.name, [])
            if not samples:
                continue

            # Check for delimiter patterns
            delimiter, count, ratio = self._detect_delimiter(samples)

            if (
                delimiter
                and count >= self.min_delimiter_occurrences
                and ratio >= self.min_delimiter_ratio
            ):
                # Get sample values showing the delimiter
                delimited_samples = [
                    str(v) for v in samples
                    if v and delimiter in str(v)
                ][:5]

                violations.append(Violation1NF(
                    column_name=column.name,
                    violation_type=ViolationType.MULTI_VALUED,
                    description=(
                        f"Column '{column.name}' contains multi-valued data "
                        f"separated by '{delimiter}' ({ratio:.1%} of values)"
                    ),
                    severity=SeverityLevel.HIGH,
                    sample_values=delimited_samples,
                    detected_delimiter=delimiter,
                ))

        return violations

    def _detect_repeating_groups(self, table: Table) -> List[Violation1NF]:
        """Detect repeating column groups (e.g., phone1, phone2, phone3)."""
        violations = []
        column_names = [c.name.lower() for c in table.columns]

        # Group columns by potential base name
        groups: Dict[str, List[str]] = {}

        for col in table.columns:
            col_lower = col.name.lower()

            # Check for numbered suffix patterns
            for base in self.REPEATING_BASE_NAMES:
                if col_lower.startswith(base):
                    suffix = col_lower[len(base):]
                    # Check if suffix is a number or _number
                    if re.match(r"^_?\d+$", suffix):
                        if base not in groups:
                            groups[base] = []
                        groups[base].append(col.name)
                        break

            # Also check generic numbered patterns
            match = re.match(r"^(.+?)_?(\d+)$", col_lower)
            if match:
                base = match.group(1)
                # Check if other columns share this base
                pattern = f"^{re.escape(base)}_?\\d+$"
                matching = [
                    c for c in column_names
                    if re.match(pattern, c)
                ]
                if len(matching) >= 2 and base not in groups:
                    groups[base] = [
                        c.name for c in table.columns
                        if c.name.lower() in matching
                    ]

        # Create violations for groups with 2+ columns
        for base, columns in groups.items():
            if len(columns) >= 2:
                violations.append(Violation1NF(
                    column_name=columns[0],
                    violation_type=ViolationType.REPEATING_GROUP,
                    description=(
                        f"Repeating group detected: {columns} should be "
                        "normalized into a separate table"
                    ),
                    severity=SeverityLevel.HIGH,
                    related_columns=columns,
                    estimated_new_tables=1,
                ))

        return violations

    def _detect_delimiter(
        self,
        samples: List[Any],
    ) -> Tuple[Optional[str], int, float]:
        """
        Detect the most likely delimiter in sample values.

        Returns:
            Tuple of (delimiter, occurrence_count, ratio_of_values).
        """
        str_samples = [str(s) for s in samples if s is not None]
        if not str_samples:
            return None, 0, 0.0

        best_delimiter = None
        best_count = 0
        best_ratio = 0.0

        for delimiter in self.DELIMITERS:
            count = sum(1 for s in str_samples if delimiter in s)
            ratio = count / len(str_samples)

            if count > best_count:
                best_delimiter = delimiter
                best_count = count
                best_ratio = ratio

        return best_delimiter, best_count, best_ratio

    def _analyze_json_structure(
        self,
        samples: List[Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze the structure of JSON values.

        Returns a dict describing the JSON structure:
        {
            "type": "object" | "array" | "mixed",
            "fields": {"field_name": {"types": [...], "count": N}},
            "array_length_avg": float (for arrays),
        }
        """
        import json

        parsed = []
        for sample in samples:
            if sample is None:
                continue
            try:
                if isinstance(sample, str):
                    parsed.append(json.loads(sample))
                elif isinstance(sample, (dict, list)):
                    parsed.append(sample)
            except (json.JSONDecodeError, TypeError):
                continue

        if not parsed:
            return None

        # Determine primary type
        types = [type(p).__name__ for p in parsed]
        if all(t == "dict" for t in types):
            structure_type = "object"
        elif all(t == "list" for t in types):
            structure_type = "array"
        else:
            structure_type = "mixed"

        result: Dict[str, Any] = {"type": structure_type}

        # Analyze object fields
        if structure_type == "object":
            fields: Dict[str, Dict[str, Any]] = {}
            for obj in parsed:
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        if key not in fields:
                            fields[key] = {"types": set(), "count": 0}
                        fields[key]["types"].add(type(value).__name__)
                        fields[key]["count"] += 1

            # Convert sets to lists for JSON serialization
            result["fields"] = {
                k: {"types": list(v["types"]), "count": v["count"]}
                for k, v in fields.items()
            }

        # Analyze array lengths
        elif structure_type == "array":
            lengths = [len(a) for a in parsed if isinstance(a, list)]
            result["array_length_avg"] = sum(lengths) / len(lengths) if lengths else 0

        return result
