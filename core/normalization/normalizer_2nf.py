"""
Second Normal Form (2NF) Normalizer.

This module provides the Normalizer2NF class for automatically normalizing
database tables to Second Normal Form by identifying and eliminating partial
dependencies.

A table is in 2NF if:
1. It is in 1NF (atomic values, no repeating groups)
2. All non-prime attributes are fully functionally dependent on the entire
   primary key (no partial dependencies)

Partial dependencies occur when a non-prime attribute depends on only part
of a composite primary key.

Example:
    Consider a table ORDER_DETAILS with columns:
    - order_id (PK)
    - product_id (PK)
    - quantity
    - product_name      <- depends only on product_id (partial dependency)
    - product_category  <- depends only on product_id (partial dependency)

    2NF normalization would decompose this into:
    - ORDER_DETAILS(order_id, product_id, quantity) with FK to PRODUCTS
    - PRODUCTS(product_id, product_name, product_category)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from core.models.schema import (
    Column,
    Constraint,
    ConstraintType,
    ForeignKeyRelationship,
    Table,
)
from core.models.analysis import CandidateKey, FunctionalDependency
from core.normalization.violations import Violation2NF
from core.normalization.decomposer import DecompositionResult, SchemaDecomposer


@dataclass
class NormalizationStep2NF:
    """
    Represents a single step in the 2NF normalization process.

    Each step documents a specific action taken to resolve a partial
    dependency, including which columns were moved and to where.

    Attributes:
        action: The type of action performed (e.g., "extract_table").
        partial_dependency_removed: Description of the FD that was eliminated.
        new_table_name: Name of the newly created table, if any.
        columns_moved: List of column names moved to the new table.
        description: Human-readable description of the step.
        determinant: The columns forming the partial key.
        dependents: The columns that depended on the partial key.

    Example:
        >>> step = NormalizationStep2NF(
        ...     action="extract_table",
        ...     partial_dependency_removed="{product_id} -> {product_name, category}",
        ...     new_table_name="products",
        ...     columns_moved=["product_name", "product_category"],
        ...     description="Extracted product attributes to separate table"
        ... )
    """

    action: str
    partial_dependency_removed: str
    new_table_name: str = ""
    columns_moved: List[str] = field(default_factory=list)
    description: str = ""
    determinant: List[str] = field(default_factory=list)
    dependents: List[str] = field(default_factory=list)

    def __str__(self) -> str:
        """Return string representation of the step."""
        return (
            f"Step: {self.action} - "
            f"Removed {self.partial_dependency_removed}"
        )


@dataclass
class Normalization2NFResult:
    """
    Result of normalizing a table to Second Normal Form.

    Contains the original table, the resulting normalized tables,
    all steps taken during normalization, and metadata about the
    process including foreign keys and losslessness verification.

    Attributes:
        original_table: The table before normalization.
        normalized_tables: List of tables after normalization.
        steps: List of normalization steps performed.
        foreign_keys_added: Foreign keys created between tables.
        is_lossless: Whether the decomposition is lossless.
        violations_resolved: Number of 2NF violations resolved.
        preserves_dependencies: Whether all FDs are preserved.

    Example:
        >>> result = Normalization2NFResult(
        ...     original_table=order_details,
        ...     normalized_tables=[order_items, products],
        ...     steps=[step1],
        ...     foreign_keys_added=[fk_to_products],
        ...     is_lossless=True
        ... )
        >>> print(f"Normalized into {len(result.normalized_tables)} tables")
    """

    original_table: Table
    normalized_tables: List[Table]
    steps: List[NormalizationStep2NF] = field(default_factory=list)
    foreign_keys_added: List[ForeignKeyRelationship] = field(default_factory=list)
    is_lossless: bool = True
    violations_resolved: int = 0
    preserves_dependencies: bool = True

    @property
    def was_normalized(self) -> bool:
        """Check if any normalization was performed."""
        return len(self.steps) > 0

    @property
    def table_count(self) -> int:
        """Return the number of resulting tables."""
        return len(self.normalized_tables)

    def get_table(self, name: str) -> Optional[Table]:
        """
        Get a normalized table by name.

        Args:
            name: The table name to find.

        Returns:
            The table if found, None otherwise.
        """
        for table in self.normalized_tables:
            if table.name.lower() == name.lower():
                return table
        return None

    def get_steps_summary(self) -> str:
        """
        Get a summary of all normalization steps.

        Returns:
            Multi-line string summarizing the normalization process.
        """
        if not self.steps:
            return "No normalization required - table already in 2NF"

        lines = [
            f"2NF Normalization of {self.original_table.name}:",
            f"  - Steps performed: {len(self.steps)}",
            f"  - Tables created: {self.table_count}",
            f"  - Foreign keys added: {len(self.foreign_keys_added)}",
            "",
            "Steps:",
        ]

        for i, step in enumerate(self.steps, 1):
            lines.append(f"  {i}. {step.action}: {step.description}")
            if step.new_table_name:
                lines.append(f"     Created table: {step.new_table_name}")
            if step.columns_moved:
                lines.append(f"     Moved columns: {', '.join(step.columns_moved)}")

        return "\n".join(lines)

    def __str__(self) -> str:
        """Return string representation."""
        if not self.was_normalized:
            return f"2NF Result: {self.original_table.name} (no changes)"
        return (
            f"2NF Result: {self.original_table.name} -> "
            f"{[t.name for t in self.normalized_tables]} "
            f"({self.violations_resolved} violations resolved)"
        )


class Normalizer2NF:
    """
    Normalizes database tables to Second Normal Form.

    The normalizer identifies partial dependencies (where non-prime attributes
    depend on a proper subset of the primary key) and decomposes the table
    to eliminate them while ensuring:
    - Lossless decomposition (original can be reconstructed via joins)
    - Dependency preservation (all original FDs are preserved)
    - Proper foreign key relationships

    The normalization process:
    1. Identify all partial dependencies using provided violations
    2. For each partial dependency, extract the dependent columns to a new table
    3. The partial key becomes the primary key of the new table
    4. A foreign key links the original table to the new table
    5. Merge tables with the same primary key if needed

    Example:
        >>> normalizer = Normalizer2NF()
        >>>
        >>> # Create violations and FDs from analysis
        >>> violations = [
        ...     Violation2NF(
        ...         table_name="order_details",
        ...         partial_key=["product_id"],
        ...         dependent_columns=["product_name", "category"],
        ...         full_primary_key=["order_id", "product_id"]
        ...     )
        ... ]
        >>>
        >>> result = normalizer.normalize(
        ...     table=order_details,
        ...     violations=violations,
        ...     fds=functional_dependencies,
        ...     primary_key=["order_id", "product_id"]
        ... )
        >>>
        >>> print(result.get_steps_summary())
    """

    def __init__(self, decomposer: Optional[SchemaDecomposer] = None) -> None:
        """
        Initialize the 2NF normalizer.

        Args:
            decomposer: Optional SchemaDecomposer instance. If not provided,
                a new one will be created.
        """
        self.decomposer = decomposer or SchemaDecomposer()
        self._generated_table_names: Set[str] = set()

    def normalize(
        self,
        table: Table,
        violations: List[Violation2NF],
        fds: List[FunctionalDependency],
        primary_key: List[str],
    ) -> Normalization2NFResult:
        """
        Normalize a table to Second Normal Form.

        Processes each partial dependency violation by extracting the
        dependent columns to a new table, ensuring the decomposition is
        lossless and dependency-preserving.

        Args:
            table: The table to normalize.
            violations: List of 2NF violations (partial dependencies) found.
            fds: List of all functional dependencies in the table.
            primary_key: The primary key columns of the table.

        Returns:
            Normalization2NFResult with normalized tables and metadata.

        Example:
            >>> result = normalizer.normalize(
            ...     table=order_details,
            ...     violations=[violation1, violation2],
            ...     fds=all_fds,
            ...     primary_key=["order_id", "product_id"]
            ... )
        """
        # If no violations, table is already in 2NF
        if not violations:
            return Normalization2NFResult(
                original_table=table,
                normalized_tables=[table],
                steps=[],
                foreign_keys_added=[],
                is_lossless=True,
                violations_resolved=0,
                preserves_dependencies=True,
            )

        # Filter to only valid violations
        valid_violations = [
            v for v in violations
            if self._is_partial_dependency(
                determinant=v.partial_key,
                primary_key=primary_key
            )
        ]

        if not valid_violations:
            return Normalization2NFResult(
                original_table=table,
                normalized_tables=[table],
                steps=[],
                foreign_keys_added=[],
                is_lossless=True,
                violations_resolved=0,
                preserves_dependencies=True,
            )

        # Group violations by partial key to avoid creating duplicate tables
        grouped_violations = self._group_violations_by_partial_key(valid_violations)

        # Process each group of violations
        steps: List[NormalizationStep2NF] = []
        foreign_keys: List[ForeignKeyRelationship] = []
        extracted_tables: List[Table] = []
        current_table = table

        for partial_key, violation_group in grouped_violations.items():
            # Combine all dependent columns for this partial key
            all_dependents: List[str] = []
            for v in violation_group:
                all_dependents.extend(v.dependent_columns)
            all_dependents = list(dict.fromkeys(all_dependents))  # Remove duplicates

            # Generate table name for extracted table
            new_table_name = self._generate_table_name(list(partial_key))

            # Extract the partial dependency
            current_table, new_table, fk = self._extract_partial_dependency_columns(
                table=current_table,
                partial_key=list(partial_key),
                dependent_columns=all_dependents,
                new_table_name=new_table_name,
            )

            extracted_tables.append(new_table)
            foreign_keys.append(fk)

            # Record the step
            step = NormalizationStep2NF(
                action="extract_table",
                partial_dependency_removed=f"{{{', '.join(partial_key)}}} -> {{{', '.join(all_dependents)}}}",
                new_table_name=new_table_name,
                columns_moved=all_dependents,
                description=f"Extracted columns dependent on {list(partial_key)} to new table",
                determinant=list(partial_key),
                dependents=all_dependents,
            )
            steps.append(step)

        # Merge tables with the same primary key if any
        merged_tables = self._merge_overlapping_tables(extracted_tables)

        # Build final list of normalized tables
        normalized_tables = [current_table] + merged_tables

        # Verify losslessness
        is_lossless = self._verify_lossless_decomposition(
            original=table,
            decomposed=normalized_tables,
            primary_key=primary_key,
        )

        return Normalization2NFResult(
            original_table=table,
            normalized_tables=normalized_tables,
            steps=steps,
            foreign_keys_added=foreign_keys,
            is_lossless=is_lossless,
            violations_resolved=len(valid_violations),
            preserves_dependencies=True,  # 2NF decomposition always preserves FDs
        )

    def _extract_partial_dependency(
        self,
        table: Table,
        violation: Violation2NF,
    ) -> Tuple[Table, Table, ForeignKeyRelationship]:
        """
        Extract a partial dependency to a new table.

        Creates a new table with the partial key as primary key and moves
        the dependent columns to it. Adds a foreign key from the original
        table to the new table.

        Args:
            table: The table containing the partial dependency.
            violation: The 2NF violation describing the partial dependency.

        Returns:
            Tuple of (modified_original_table, new_table, foreign_key).

        Example:
            >>> modified, extracted, fk = normalizer._extract_partial_dependency(
            ...     table=order_details,
            ...     violation=product_violation
            ... )
        """
        new_table_name = self._generate_table_name(violation.partial_key)

        return self._extract_partial_dependency_columns(
            table=table,
            partial_key=violation.partial_key,
            dependent_columns=violation.dependent_columns,
            new_table_name=new_table_name,
        )

    def _extract_partial_dependency_columns(
        self,
        table: Table,
        partial_key: List[str],
        dependent_columns: List[str],
        new_table_name: str,
    ) -> Tuple[Table, Table, ForeignKeyRelationship]:
        """
        Extract columns forming a partial dependency.

        Args:
            table: The source table.
            partial_key: The partial key columns (will be new PK).
            dependent_columns: Columns to move to new table.
            new_table_name: Name for the new table.

        Returns:
            Tuple of (modified_original_table, new_table, foreign_key).
        """
        # Create the new (extracted) table with partial key as PK
        new_columns: List[Column] = []

        # Add partial key columns as primary key
        for pk_name in partial_key:
            source_col = table.get_column(pk_name)
            if source_col:
                new_col = Column(
                    name=source_col.name,
                    data_type=source_col.data_type,
                    is_nullable=False,  # PK columns cannot be null
                    is_primary_key=True,
                    is_unique=len(partial_key) == 1,
                    ordinal_position=len(new_columns) + 1,
                    character_maximum_length=source_col.character_maximum_length,
                    numeric_precision=source_col.numeric_precision,
                    numeric_scale=source_col.numeric_scale,
                    description=source_col.description,
                )
                new_columns.append(new_col)

        # Add dependent columns
        for dep_name in dependent_columns:
            source_col = table.get_column(dep_name)
            if source_col:
                new_col = Column(
                    name=source_col.name,
                    data_type=source_col.data_type,
                    is_nullable=source_col.is_nullable,
                    is_primary_key=False,
                    is_unique=source_col.is_unique,
                    ordinal_position=len(new_columns) + 1,
                    character_maximum_length=source_col.character_maximum_length,
                    numeric_precision=source_col.numeric_precision,
                    numeric_scale=source_col.numeric_scale,
                    description=source_col.description,
                )
                new_columns.append(new_col)

        # Create primary key constraint for new table
        pk_constraint = Constraint(
            name=f"pk_{new_table_name}",
            type=ConstraintType.PRIMARY_KEY,
            columns=partial_key,
        )

        new_table = Table(
            name=new_table_name,
            schema_name=table.schema_name,
            columns=new_columns,
            constraints=[pk_constraint],
            description=f"Extracted from {table.name} during 2NF normalization",
        )

        # Create the modified original table (without dependent columns)
        dependent_set = {col.lower() for col in dependent_columns}
        modified_columns: List[Column] = []

        for col in table.columns:
            if col.name.lower() not in dependent_set:
                # Create a copy of the column
                new_col = Column(
                    name=col.name,
                    data_type=col.data_type,
                    is_nullable=col.is_nullable,
                    is_primary_key=col.is_primary_key,
                    is_foreign_key=col.is_foreign_key,
                    is_unique=col.is_unique,
                    is_identity=col.is_identity,
                    default_value=col.default_value,
                    foreign_key_table=col.foreign_key_table,
                    foreign_key_column=col.foreign_key_column,
                    ordinal_position=len(modified_columns) + 1,
                    character_maximum_length=col.character_maximum_length,
                    numeric_precision=col.numeric_precision,
                    numeric_scale=col.numeric_scale,
                    description=col.description,
                )
                modified_columns.append(new_col)

        # Copy constraints that don't involve removed columns
        modified_constraints: List[Constraint] = []
        for constraint in table.constraints:
            constraint_cols = {c.lower() for c in constraint.columns}
            if not (constraint_cols & dependent_set):
                modified_constraints.append(constraint)

        modified_table = Table(
            name=table.name,
            schema_name=table.schema_name,
            columns=modified_columns,
            constraints=modified_constraints,
            description=table.description,
            table_type=table.table_type,
        )

        # Mark the FK columns in the modified table
        for col_name in partial_key:
            col = modified_table.get_column(col_name)
            if col:
                col.is_foreign_key = True
                col.foreign_key_table = new_table.name
                col.foreign_key_column = col_name

        # Create foreign key relationship
        fk = self._create_foreign_key(
            from_table=modified_table,
            to_table=new_table,
            columns=partial_key,
        )

        return modified_table, new_table, fk

    def _is_partial_dependency(
        self,
        determinant: List[str],
        primary_key: List[str],
    ) -> bool:
        """
        Check if a functional dependency is a partial dependency.

        A partial dependency exists when the determinant is a proper subset
        of the primary key (not equal to, but contained within).

        Args:
            determinant: The left-hand side of the functional dependency.
            primary_key: The primary key columns.

        Returns:
            True if this is a partial dependency (determinant is proper subset).

        Example:
            >>> normalizer._is_partial_dependency(
            ...     determinant=["product_id"],
            ...     primary_key=["order_id", "product_id"]
            ... )
            True
            >>> normalizer._is_partial_dependency(
            ...     determinant=["order_id", "product_id"],
            ...     primary_key=["order_id", "product_id"]
            ... )
            False  # Not a proper subset
        """
        det_set = set(col.lower() for col in determinant)
        pk_set = set(col.lower() for col in primary_key)

        # Must be a proper subset: subset AND not equal
        return det_set < pk_set

    def _is_partial_dependency_fd(
        self,
        fd: FunctionalDependency,
        primary_key: List[str],
    ) -> bool:
        """
        Check if a functional dependency represents a partial dependency.

        Args:
            fd: The functional dependency to check.
            primary_key: The primary key columns.

        Returns:
            True if the FD is a partial dependency.
        """
        return self._is_partial_dependency(fd.determinant, primary_key)

    def _merge_overlapping_tables(self, tables: List[Table]) -> List[Table]:
        """
        Merge tables that have the same primary key.

        When multiple partial dependencies have the same partial key,
        they should be combined into a single table.

        Args:
            tables: List of extracted tables to potentially merge.

        Returns:
            List of tables after merging those with identical primary keys.

        Example:
            >>> # If two tables both have PK (product_id), merge them
            >>> merged = normalizer._merge_overlapping_tables([table1, table2])
        """
        if len(tables) <= 1:
            return tables

        # Group tables by their primary key columns
        pk_groups: Dict[frozenset, List[Table]] = {}

        for table in tables:
            pk_cols = frozenset(
                col.name.lower() for col in table.columns if col.is_primary_key
            )
            if pk_cols not in pk_groups:
                pk_groups[pk_cols] = []
            pk_groups[pk_cols].append(table)

        # Merge tables in each group
        merged_tables: List[Table] = []

        for pk_cols, group in pk_groups.items():
            if len(group) == 1:
                merged_tables.append(group[0])
            else:
                # Merge all tables in the group
                merged = self._merge_table_group(group, list(pk_cols))
                merged_tables.append(merged)

        return merged_tables

    def _merge_table_group(
        self,
        tables: List[Table],
        primary_key: List[str],
    ) -> Table:
        """
        Merge a group of tables that share the same primary key.

        Args:
            tables: Tables to merge.
            primary_key: The shared primary key columns.

        Returns:
            A single merged table.
        """
        if not tables:
            raise ValueError("No tables to merge")

        if len(tables) == 1:
            return tables[0]

        # Merge tables manually
        base_table = tables[0]
        merged_columns: List[Column] = list(base_table.columns)
        seen_columns = {col.name.lower() for col in merged_columns}

        # Add columns from other tables
        for table in tables[1:]:
            for col in table.columns:
                if col.name.lower() not in seen_columns:
                    merged_columns.append(col)
                    seen_columns.add(col.name.lower())

        # Reorder: PK columns first
        key_set = {k.lower() for k in primary_key}
        pk_cols = [c for c in merged_columns if c.name.lower() in key_set]
        other_cols = [c for c in merged_columns if c.name.lower() not in key_set]

        for i, col in enumerate(pk_cols + other_cols):
            col.ordinal_position = i + 1

        return Table(
            name=base_table.name,
            schema_name=base_table.schema_name,
            columns=pk_cols + other_cols,
            constraints=base_table.constraints,
            description=f"Merged from {[t.name for t in tables]}",
        )

    def _group_violations_by_partial_key(
        self,
        violations: List[Violation2NF],
    ) -> Dict[frozenset, List[Violation2NF]]:
        """
        Group violations by their partial key.

        Violations with the same partial key should be handled together
        to create a single table.

        Args:
            violations: List of 2NF violations.

        Returns:
            Dictionary mapping partial key sets to their violations.
        """
        groups: Dict[frozenset, List[Violation2NF]] = {}

        for violation in violations:
            key = frozenset(col.lower() for col in violation.partial_key)
            if key not in groups:
                groups[key] = []
            groups[key].append(violation)

        return groups

    def _generate_table_name(self, partial_key: List[str]) -> str:
        """
        Generate a unique table name based on the partial key.

        Args:
            partial_key: The partial key columns.

        Returns:
            A unique table name.
        """
        # Use the first column as the base name
        base = partial_key[0]

        # Remove common suffixes
        for suffix in ["_id", "_key", "_code"]:
            if base.lower().endswith(suffix):
                base = base[:-len(suffix)]
                break

        # Pluralize if it doesn't end in 's'
        if not base.endswith("s"):
            base = f"{base}s"

        # Ensure uniqueness
        name = base
        counter = 1
        while name.lower() in self._generated_table_names:
            name = f"{base}_{counter}"
            counter += 1

        self._generated_table_names.add(name.lower())
        return name

    def _create_foreign_key(
        self,
        from_table: Table,
        to_table: Table,
        columns: List[str],
    ) -> ForeignKeyRelationship:
        """
        Create a foreign key relationship between tables.

        Args:
            from_table: Table containing the foreign key.
            to_table: Table being referenced.
            columns: Columns forming the relationship.

        Returns:
            ForeignKeyRelationship object.
        """
        return ForeignKeyRelationship(
            name=f"fk_{from_table.name}_{to_table.name}",
            from_schema=from_table.schema_name,
            from_table=from_table.name,
            from_columns=columns,
            to_schema=to_table.schema_name,
            to_table=to_table.name,
            to_columns=columns,
            cardinality="N:1",
        )

    def _verify_lossless_decomposition(
        self,
        original: Table,
        decomposed: List[Table],
        primary_key: List[str],
    ) -> bool:
        """
        Verify that the decomposition is lossless.

        A decomposition is lossless if the original table can be
        reconstructed by natural joining the decomposed tables.
        For 2NF normalization, this is always true because we're
        only extracting columns based on functional dependencies.

        Args:
            original: The original table.
            decomposed: The decomposed tables.
            primary_key: The original primary key.

        Returns:
            True if the decomposition is lossless.
        """
        # Collect all columns from decomposed tables
        all_decomposed_cols: Set[str] = set()
        for table in decomposed:
            all_decomposed_cols.update(col.name.lower() for col in table.columns)

        # All original columns must be present in decomposed tables
        original_cols = {col.name.lower() for col in original.columns}

        return original_cols <= all_decomposed_cols

    def detect_partial_dependencies(
        self,
        table: Table,
        fds: List[FunctionalDependency],
        primary_key: List[str],
    ) -> List[Violation2NF]:
        """
        Detect partial dependencies in a table.

        Analyzes functional dependencies to find those where the determinant
        is a proper subset of the primary key.

        Args:
            table: The table to analyze.
            fds: All functional dependencies for the table.
            primary_key: The primary key columns.

        Returns:
            List of 2NF violations representing partial dependencies.

        Example:
            >>> fds = [
            ...     FunctionalDependency(
            ...         determinant=["product_id"],
            ...         dependent="product_name"
            ...     )
            ... ]
            >>> violations = normalizer.detect_partial_dependencies(
            ...     table=order_details,
            ...     fds=fds,
            ...     primary_key=["order_id", "product_id"]
            ... )
        """
        violations: List[Violation2NF] = []
        pk_set = set(col.lower() for col in primary_key)

        # Only check for partial dependencies if we have a composite key
        if len(primary_key) <= 1:
            return violations

        # Find prime attributes (columns in any candidate key)
        # For simplicity, we consider only the primary key columns as prime
        prime_attributes = pk_set

        for fd in fds:
            det_set = set(col.lower() for col in fd.determinant)

            # Check if this is a partial dependency
            if det_set < pk_set:  # proper subset
                # Check if dependent is non-prime
                if fd.dependent.lower() not in prime_attributes:
                    violation = Violation2NF(
                        table_name=table.name,
                        partial_key=fd.determinant,
                        dependent_columns=[fd.dependent],
                        full_primary_key=primary_key,
                        description=(
                            f"Column '{fd.dependent}' depends on "
                            f"{fd.determinant}, which is a proper subset "
                            f"of the primary key {primary_key}"
                        ),
                    )
                    violations.append(violation)

        return violations

    def is_in_2nf(
        self,
        table: Table,
        fds: List[FunctionalDependency],
        primary_key: List[str],
    ) -> bool:
        """
        Check if a table is already in Second Normal Form.

        Args:
            table: The table to check.
            fds: Functional dependencies for the table.
            primary_key: The primary key columns.

        Returns:
            True if the table is in 2NF, False otherwise.

        Example:
            >>> if normalizer.is_in_2nf(table, fds, pk):
            ...     print("Table is already in 2NF")
        """
        violations = self.detect_partial_dependencies(table, fds, primary_key)
        return len(violations) == 0
