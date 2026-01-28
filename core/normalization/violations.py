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


class ComprehensiveViolationDetector:
    """
    Comprehensive detector for normalization violations across all tables.

    This class provides detection of normalization violations across all normal
    forms (1NF, 2NF, 3NF, BCNF) using table metadata, functional dependencies,
    and candidate keys. It's designed to analyze entire schemas at once.

    Unlike ViolationDetector which analyzes single tables, this class takes
    dictionaries of FDs and candidate keys for all tables in a schema.

    Attributes:
        tables: List of Table objects to analyze.
        functional_dependencies: FDs indexed by table name.
        candidate_keys: Candidate keys indexed by table name.

    Example:
        >>> from core.models.schema import Table, Column
        >>> from core.models.analysis import FunctionalDependency, CandidateKey
        >>>
        >>> # Create test data
        >>> table = Table(name="orders", columns=[...])
        >>> fds = {"orders": [FunctionalDependency(...)]}
        >>> keys = {"orders": [CandidateKey(...)]}
        >>>
        >>> # Detect violations
        >>> detector = ComprehensiveViolationDetector(
        ...     tables=[table],
        ...     functional_dependencies=fds,
        ...     candidate_keys=keys
        ... )
        >>> violations = detector.detect_all_violations()
        >>> print(detector.get_highest_normal_form("orders"))
        "3NF"
    """

    # Data types that indicate potential 1NF violations
    ARRAY_TYPES: FrozenSet[str] = frozenset({
        "array", "json", "jsonb", "hstore", "xml",
        "text[]", "integer[]", "varchar[]", "bytea[]",
        "uuid[]", "boolean[]", "bigint[]", "smallint[]",
        "real[]", "double precision[]", "numeric[]", "date[]",
        "timestamp[]", "timestamptz[]", "interval[]",
        "_text", "_int4", "_int8", "_float4", "_float8",
        "_bool", "_varchar", "_uuid", "_numeric", "_date",
        "_timestamp", "_timestamptz", "_interval",
    })

    # Regex patterns for detecting repeating column groups
    REPEATING_PATTERNS: List[Tuple[str, re.Pattern]] = [
        # name1, name2, name3 pattern
        ("numbered", re.compile(r"^(\w+?)(\d+)$", re.IGNORECASE)),
        # name_1, name_2, name_3 pattern
        ("underscore_numbered", re.compile(r"^(\w+?)_(\d+)$", re.IGNORECASE)),
        # first_name, second_name, third_name pattern (ordinal)
        ("ordinal", re.compile(
            r"^(first|second|third|fourth|fifth)_(\w+)$", re.IGNORECASE
        )),
        # primary_X, secondary_X, tertiary_X pattern
        ("priority", re.compile(
            r"^(primary|secondary|tertiary|alt|alternate|backup)_(\w+)$",
            re.IGNORECASE
        )),
        # home_phone, work_phone, mobile_phone pattern
        ("prefixed", re.compile(
            r"^(home|work|office|mobile|cell|main|other|emergency)_(\w+)$",
            re.IGNORECASE
        )),
    ]

    def __init__(
        self,
        tables: List[Table],
        functional_dependencies: Dict[str, List[FunctionalDependency]],
        candidate_keys: Dict[str, List[CandidateKey]],
    ) -> None:
        """
        Initialize the comprehensive violation detector.

        Args:
            tables: List of Table objects to analyze.
            functional_dependencies: Dictionary mapping table names to
                their discovered functional dependencies.
            candidate_keys: Dictionary mapping table names to their
                discovered candidate keys.
        """
        self.tables = tables
        self.functional_dependencies = functional_dependencies
        self.candidate_keys = candidate_keys

        # Build lookup tables for efficient access
        self._table_lookup: Dict[str, Table] = {t.name: t for t in tables}
        self._column_lookup: Dict[str, Dict[str, Column]] = {}
        for table in tables:
            self._column_lookup[table.name] = {c.name: c for c in table.columns}

    def detect_1nf_violations(self, table: Table) -> List[Violation1NF]:
        """
        Detect First Normal Form violations in a table.

        Checks for:
        1. Array or JSON column types (non-atomic values)
        2. Repeating column groups (e.g., phone1, phone2, phone3)
        3. Multi-valued attributes based on naming patterns

        Args:
            table: The table to analyze.

        Returns:
            List of Violation1NF objects describing any violations found.

        Example:
            >>> violations = detector.detect_1nf_violations(customers_table)
            >>> for v in violations:
            ...     print(f"{v.violation_type}: {v.description}")
        """
        violations: List[Violation1NF] = []

        # Check for array/JSON types (non-atomic values)
        for column in table.columns:
            if self._check_array_types(column):
                violations.append(Violation1NF(
                    column_name=column.name,
                    violation_type=ViolationType.NON_ATOMIC,
                    description=(
                        f"Column '{column.name}' has type '{column.data_type}' which "
                        f"can store non-atomic values, violating 1NF."
                    ),
                    severity=SeverityLevel.HIGH,
                    suggested_fix=(
                        f"Create a separate table for '{column.name}' values with a "
                        f"foreign key reference back to '{table.name}'. For JSON "
                        f"columns, consider extracting structured data into proper "
                        f"relational tables."
                    ),
                    related_columns=[column.name],
                ))

        # Check for repeating column groups
        repeating_groups = self._check_repeating_pattern(table)
        for pattern, columns in repeating_groups:
            violations.append(Violation1NF(
                column_name=columns[0],
                violation_type=ViolationType.REPEATING_GROUP,
                description=(
                    f"Columns {list(columns)} form a repeating group with pattern "
                    f"'{pattern}'. This violates 1NF as it represents a "
                    f"multi-valued attribute."
                ),
                severity=SeverityLevel.HIGH,
                suggested_fix=(
                    f"Create a new table to store '{pattern}' values with a "
                    f"foreign key reference back to '{table.name}'. Each row "
                    f"in the new table would hold one value instead of having "
                    f"multiple numbered columns."
                ),
                related_columns=list(columns),
            ))

        return violations

    def detect_2nf_violations(self, table: Table) -> List[Violation2NF]:
        """
        Detect Second Normal Form violations in a table.

        A table is in 2NF if:
        1. It is in 1NF
        2. No non-key column depends on only part of a composite key

        This method checks for partial dependencies where a non-key column
        depends on a proper subset of the primary key.

        Args:
            table: The table to analyze.

        Returns:
            List of Violation2NF objects describing any partial dependencies.

        Example:
            >>> violations = detector.detect_2nf_violations(order_items_table)
            >>> for v in violations:
            ...     print(f"Partial dependency: {v.partial_key} -> {v.dependent_columns}")
        """
        violations: List[Violation2NF] = []

        # Get the primary key columns
        pk_columns = set(table.primary_key_columns)

        # 2NF only applies to tables with composite keys
        if len(pk_columns) <= 1:
            return violations

        # Get non-key columns
        non_key_columns = self._get_non_key_columns(table)

        # Get functional dependencies for this table
        table_fds = self.functional_dependencies.get(table.name, [])

        for fd in table_fds:
            determinant = set(fd.determinant)

            # Check if this is a partial dependency:
            # - Determinant is a proper subset of the primary key
            # - Dependent is a non-key column
            # - FD is not trivial
            if (
                determinant < pk_columns  # proper subset
                and fd.dependent in non_key_columns
                and not fd.is_trivial
            ):
                violations.append(Violation2NF(
                    table_name=table.name,
                    partial_key=list(determinant),
                    dependent_columns=[fd.dependent],
                    full_primary_key=list(pk_columns),
                    description=(
                        f"Column '{fd.dependent}' depends only on "
                        f"{list(determinant)} which is a "
                        f"subset of the primary key {list(pk_columns)}. "
                        f"This is a partial dependency violating 2NF."
                    ),
                ))

        return violations

    def detect_3nf_violations(self, table: Table) -> List[Violation3NF]:
        """
        Detect Third Normal Form violations in a table.

        A table is in 3NF if:
        1. It is in 2NF
        2. No non-key column depends transitively on the primary key
           (i.e., no non-key column depends on another non-key column)

        This method checks for transitive dependencies where a non-key
        column determines another non-key column.

        Args:
            table: The table to analyze.

        Returns:
            List of Violation3NF objects describing any transitive dependencies.

        Example:
            >>> violations = detector.detect_3nf_violations(employees_table)
            >>> for v in violations:
            ...     print(f"Transitive: {v.determinant} -> {v.dependent_columns}")
        """
        violations: List[Violation3NF] = []

        # Get key columns (all candidate keys)
        all_key_columns: Set[str] = set()
        table_keys = self.candidate_keys.get(table.name, [])
        for key in table_keys:
            all_key_columns.update(key.columns)

        # Also include primary key columns
        all_key_columns.update(table.primary_key_columns)

        # Get non-key columns
        non_key_columns = self._get_non_key_columns(table)

        # Get functional dependencies for this table
        table_fds = self.functional_dependencies.get(table.name, [])

        for fd in table_fds:
            if fd.is_trivial:
                continue

            determinant = set(fd.determinant)

            # Check if this is a transitive dependency:
            # - Determinant consists of non-key columns only
            # - Dependent is also a non-key column
            # - Determinant is not a superkey
            if (
                determinant.issubset(non_key_columns)
                and fd.dependent in non_key_columns
                and not self._is_superkey(determinant, table)
            ):
                violations.append(Violation3NF(
                    table_name=table.name,
                    determinant=list(determinant),
                    dependent_columns=[fd.dependent],
                    primary_key=table.primary_key_columns,
                    description=(
                        f"Column '{fd.dependent}' depends on non-key column(s) "
                        f"{list(determinant)}. This is a transitive dependency: "
                        f"the primary key determines {list(determinant)}, which "
                        f"in turn determines '{fd.dependent}'."
                    ),
                ))

        return violations

    def detect_bcnf_violations(self, table: Table) -> List[ViolationBCNF]:
        """
        Detect Boyce-Codd Normal Form violations in a table.

        A table is in BCNF if:
        1. It is in 3NF
        2. For every non-trivial functional dependency X -> Y,
           X is a superkey

        BCNF is stricter than 3NF and eliminates all redundancy that can
        be detected using functional dependencies alone.

        Args:
            table: The table to analyze.

        Returns:
            List of ViolationBCNF objects describing any violations.

        Example:
            >>> violations = detector.detect_bcnf_violations(course_table)
            >>> for v in violations:
            ...     print(f"Non-superkey determinant: {v.determinant}")
        """
        violations: List[ViolationBCNF] = []

        # Get candidate keys for this table
        table_keys = self.candidate_keys.get(table.name, [])
        candidate_key_lists = [list(k.columns) for k in table_keys]

        # If no candidate keys known, use primary key
        if not candidate_key_lists and table.primary_key_columns:
            candidate_key_lists = [table.primary_key_columns]

        # Get functional dependencies for this table
        table_fds = self.functional_dependencies.get(table.name, [])

        for fd in table_fds:
            if fd.is_trivial:
                continue

            determinant = set(fd.determinant)

            # Check if determinant is a superkey
            if not self._is_superkey(determinant, table):
                violations.append(ViolationBCNF(
                    table_name=table.name,
                    determinant=list(determinant),
                    dependent_columns=[fd.dependent],
                    candidate_keys=candidate_key_lists,
                    description=(
                        f"Functional dependency {list(determinant)} -> {fd.dependent} "
                        f"violates BCNF because {list(determinant)} is not a "
                        f"superkey of '{table.name}'."
                    ),
                ))

        return violations

    def detect_all_violations(self) -> Dict[str, List[Union[Violation1NF, Violation2NF, Violation3NF, ViolationBCNF]]]:
        """
        Detect all normalization violations across all tables.

        Runs all violation detection methods (1NF, 2NF, 3NF, BCNF) on
        each table and aggregates the results.

        Returns:
            Dictionary mapping table names to lists of violations.
            Tables with no violations are included with empty lists.

        Example:
            >>> all_violations = detector.detect_all_violations()
            >>> for table_name, violations in all_violations.items():
            ...     print(f"{table_name}: {len(violations)} violations")
        """
        all_violations: Dict[str, List] = {}

        for table in self.tables:
            table_violations: List = []

            # Detect all types of violations
            table_violations.extend(self.detect_1nf_violations(table))
            table_violations.extend(self.detect_2nf_violations(table))
            table_violations.extend(self.detect_3nf_violations(table))
            table_violations.extend(self.detect_bcnf_violations(table))

            # Sort by severity (critical first)
            severity_order = {
                SeverityLevel.CRITICAL: 0,
                SeverityLevel.HIGH: 1,
                SeverityLevel.MEDIUM: 2,
                SeverityLevel.LOW: 3,
                SeverityLevel.INFO: 4,
                "critical": 0,
                "high": 1,
                "medium": 2,
                "low": 3,
            }

            def get_severity(v: Any) -> int:
                if hasattr(v, 'severity'):
                    return severity_order.get(v.severity, 5)
                return 5

            table_violations.sort(key=get_severity)

            all_violations[table.name] = table_violations

        return all_violations

    def get_highest_normal_form(self, table_name: str) -> str:
        """
        Determine the highest normal form achieved by a table.

        Analyzes the table for violations at each normal form level and
        returns the highest form that the table satisfies.

        Args:
            table_name: Name of the table to analyze.

        Returns:
            The highest normal form: "UNNORMALIZED", "1NF", "2NF", "3NF",
            or "BCNF".

        Raises:
            ValueError: If the table is not found.

        Example:
            >>> nf = detector.get_highest_normal_form("orders")
            >>> print(f"Orders table is in {nf}")
            "Orders table is in 3NF"
        """
        table = self._table_lookup.get(table_name)
        if table is None:
            raise ValueError(f"Table '{table_name}' not found")

        # Check for 1NF violations
        violations_1nf = self.detect_1nf_violations(table)
        if violations_1nf:
            return "UNNORMALIZED"

        # Check for 2NF violations
        violations_2nf = self.detect_2nf_violations(table)
        if violations_2nf:
            return "1NF"

        # Check for 3NF violations
        violations_3nf = self.detect_3nf_violations(table)
        if violations_3nf:
            return "2NF"

        # Check for BCNF violations
        violations_bcnf = self.detect_bcnf_violations(table)
        if violations_bcnf:
            return "3NF"

        return "BCNF"

    def _is_superkey(self, columns: Set[str], table: Table) -> bool:
        """
        Check if a set of columns is a superkey for a table.

        A superkey is a set of columns that contains at least one
        candidate key. It can uniquely identify rows in the table.

        Args:
            columns: Set of column names to check.
            table: The table to check against.

        Returns:
            True if the columns form a superkey, False otherwise.
        """
        # Get candidate keys for this table
        table_keys = self.candidate_keys.get(table.name, [])

        # Check if columns contain any candidate key
        for key in table_keys:
            key_set = set(key.columns)
            if key_set.issubset(columns):
                return True

        # Also check against primary key
        pk_columns = set(table.primary_key_columns)
        if pk_columns and pk_columns.issubset(columns):
            return True

        return False

    def _get_non_key_columns(self, table: Table) -> Set[str]:
        """
        Get all non-key columns for a table.

        Non-key columns are columns that are not part of any candidate key.

        Args:
            table: The table to analyze.

        Returns:
            Set of non-key column names.
        """
        # Get all key columns
        key_columns: Set[str] = set()

        # Add primary key columns
        key_columns.update(table.primary_key_columns)

        # Add candidate key columns
        table_keys = self.candidate_keys.get(table.name, [])
        for key in table_keys:
            key_columns.update(key.columns)

        # Return columns not in any key
        all_columns = {c.name for c in table.columns}
        return all_columns - key_columns

    def _check_array_types(self, column: Column) -> bool:
        """
        Check if a column has an array or JSON type.

        These types can store non-atomic values, violating 1NF.

        Args:
            column: The column to check.

        Returns:
            True if the column has an array/JSON type, False otherwise.
        """
        # Get the base type (remove modifiers)
        base_type = column.data_type.lower().strip()

        # Check for array notation
        if base_type.endswith("[]"):
            return True

        # Check for explicit array types
        if base_type.startswith("_"):  # PostgreSQL internal array notation
            return True

        # Check against known array/JSON types
        base_without_params = base_type.split("(")[0].strip()
        return base_without_params in self.ARRAY_TYPES

    def _check_repeating_pattern(self, table: Table) -> List[Tuple[str, Tuple[str, ...]]]:
        """
        Detect repeating column patterns in a table.

        Looks for patterns like:
        - phone1, phone2, phone3
        - address_1, address_2, address_3
        - first_name, second_name, third_name
        - home_phone, work_phone, mobile_phone

        Args:
            table: The table to analyze.

        Returns:
            List of tuples (pattern_base, (matching_column_names...))
        """
        found_patterns: Dict[str, List[str]] = {}
        column_names = [c.name for c in table.columns]

        for col_name in column_names:
            for pattern_type, pattern in self.REPEATING_PATTERNS:
                match = pattern.match(col_name)
                if match:
                    groups = match.groups()
                    if len(groups) >= 2:
                        # Determine the base pattern
                        if pattern_type in ("ordinal", "priority", "prefixed"):
                            # Use the suffix as base (e.g., "phone" from "home_phone")
                            base = groups[1].lower()
                        else:
                            # Use the prefix as base (e.g., "phone" from "phone1")
                            base = groups[0].lower()

                        if base not in found_patterns:
                            found_patterns[base] = []
                        if col_name not in found_patterns[base]:
                            found_patterns[base].append(col_name)
                    break

        # Only return patterns with multiple columns (actual repeating groups)
        results: List[Tuple[str, Tuple[str, ...]]] = []
        for base, columns in found_patterns.items():
            if len(columns) >= 2:  # Need at least 2 to be a repeating group
                results.append((base, tuple(sorted(columns))))

        return results

    def get_violation_summary(self) -> Dict[str, Dict[str, Any]]:
        """
        Get a summary of violations by table and normal form.

        Returns:
            Dictionary with structure:
            {
                "table_name": {
                    "1NF": count,
                    "2NF": count,
                    "3NF": count,
                    "BCNF": count,
                    "total": count,
                    "highest_nf": "3NF"
                }
            }

        Example:
            >>> summary = detector.get_violation_summary()
            >>> for table, stats in summary.items():
            ...     print(f"{table}: {stats['highest_nf']} ({stats['total']} violations)")
        """
        summary: Dict[str, Dict[str, Any]] = {}

        for table in self.tables:
            counts: Dict[str, Any] = {
                "1NF": 0,
                "2NF": 0,
                "3NF": 0,
                "BCNF": 0,
                "total": 0,
            }

            # Count violations by type
            v1nf = self.detect_1nf_violations(table)
            v2nf = self.detect_2nf_violations(table)
            v3nf = self.detect_3nf_violations(table)
            vbcnf = self.detect_bcnf_violations(table)

            counts["1NF"] = len(v1nf)
            counts["2NF"] = len(v2nf)
            counts["3NF"] = len(v3nf)
            counts["BCNF"] = len(vbcnf)
            counts["total"] = counts["1NF"] + counts["2NF"] + counts["3NF"] + counts["BCNF"]
            counts["highest_nf"] = self.get_highest_normal_form(table.name)

            summary[table.name] = counts

        return summary

    def get_violations_by_severity(
        self,
        severity: Union[SeverityLevel, str]
    ) -> Dict[str, List]:
        """
        Get all violations of a specific severity level.

        Args:
            severity: The severity level to filter by.

        Returns:
            Dictionary mapping table names to lists of violations
            with the specified severity.
        """
        all_violations = self.detect_all_violations()
        filtered: Dict[str, List] = {}

        severity_val = severity.value if isinstance(severity, SeverityLevel) else severity

        for table_name, violations in all_violations.items():
            matching = []
            for v in violations:
                v_severity = v.severity.value if hasattr(v.severity, 'value') else v.severity
                if v_severity == severity_val:
                    matching.append(v)
            if matching:
                filtered[table_name] = matching

        return filtered

    def get_violations_by_type(
        self,
        violation_type: ViolationType
    ) -> Dict[str, List]:
        """
        Get all violations of a specific type.

        Args:
            violation_type: The type of violation to filter by.

        Returns:
            Dictionary mapping table names to lists of violations
            with the specified type.
        """
        all_violations = self.detect_all_violations()
        filtered: Dict[str, List] = {}

        for table_name, violations in all_violations.items():
            matching = [v for v in violations if v.violation_type == violation_type]
            if matching:
                filtered[table_name] = matching

        return filtered
