"""
Schema Decomposition Engine.

This module provides algorithms for decomposing database tables into
higher normal forms (2NF, 3NF, BCNF) while preserving functional
dependencies and ensuring lossless joins where possible.

The decomposition algorithms implemented:
- 2NF: Eliminates partial dependencies
- 3NF: Uses Bernstein's synthesis algorithm (dependency preserving)
- BCNF: Iterative decomposition on violating FDs (may lose dependencies)
"""

from dataclasses import dataclass, field
from typing import FrozenSet, List, Optional, Set, Tuple

from core.models.analysis import CandidateKey, FunctionalDependency
from core.models.schema import (
    Column,
    Constraint,
    ConstraintType,
    ForeignKeyRelationship,
    Table,
)


@dataclass
class DecomposedTable:
    """
    Represents a table resulting from decomposition.

    Attributes:
        name: Name of the decomposed table.
        columns: List of column names in this table.
        primary_key: List of column names forming the primary key.
        source_table: Name of the original table this was decomposed from.
        reason: Reason for creating this decomposed table.
    """

    name: str
    columns: List[str]
    primary_key: List[str]
    source_table: str
    reason: str

    def __post_init__(self) -> None:
        """Validate the decomposed table."""
        if not self.columns:
            raise ValueError("DecomposedTable must have at least one column")
        if not self.primary_key:
            raise ValueError("DecomposedTable must have a primary key")
        # Ensure PK columns are in the table
        pk_set = set(self.primary_key)
        col_set = set(self.columns)
        if not pk_set.issubset(col_set):
            missing = pk_set - col_set
            raise ValueError(
                f"Primary key columns {missing} not in table columns"
            )


@dataclass
class DecompositionResult:
    """
    Result of a schema decomposition operation.

    Attributes:
        original_table: The original table that was decomposed.
        decomposed_tables: List of tables resulting from decomposition.
        foreign_keys_created: Foreign key relationships between decomposed tables.
        is_lossless: Whether the decomposition is lossless (can reconstruct original).
        preserves_dependencies: Whether all original FDs are preserved.
    """

    original_table: Table
    decomposed_tables: List[DecomposedTable]
    foreign_keys_created: List[ForeignKeyRelationship]
    is_lossless: bool
    preserves_dependencies: bool


class SchemaDecomposer:
    """
    Decomposes database tables into higher normal forms.

    This class provides methods to decompose tables to 2NF, 3NF, and BCNF
    while tracking losslessness and dependency preservation.

    Attributes:
        preserve_dependencies: If True, prefer dependency-preserving decompositions.
        ensure_lossless: If True, ensure all decompositions are lossless.
    """

    def __init__(
        self,
        preserve_dependencies: bool = True,
        ensure_lossless: bool = True,
    ) -> None:
        """
        Initialize the schema decomposer.

        Args:
            preserve_dependencies: Whether to prefer dependency-preserving decompositions.
            ensure_lossless: Whether to ensure decompositions are lossless.
        """
        self.preserve_dependencies = preserve_dependencies
        self.ensure_lossless = ensure_lossless

    def decompose_2nf(
        self,
        table: Table,
        fds: List[FunctionalDependency],
        pk: List[str],
    ) -> DecompositionResult:
        """
        Decompose a table to Second Normal Form (2NF).

        2NF eliminates partial dependencies: non-prime attributes must
        depend on the entire primary key, not just a proper subset.

        Algorithm:
        1. Identify partial dependencies (X -> A where X is proper subset of PK)
        2. For each partial dependency, create a new table with X as PK
        3. Move all attributes dependent on X to the new table
        4. Keep the original table with PK and attributes fully dependent on PK

        Args:
            table: The table to decompose.
            fds: List of functional dependencies for the table.
            pk: List of column names forming the primary key.

        Returns:
            DecompositionResult containing the decomposed tables.
        """
        if len(pk) <= 1:
            # Single-column PK cannot have partial dependencies
            return DecompositionResult(
                original_table=table,
                decomposed_tables=[
                    DecomposedTable(
                        name=table.name,
                        columns=[c.name for c in table.columns],
                        primary_key=pk,
                        source_table=table.name,
                        reason="Already in 2NF (single-column primary key)",
                    )
                ],
                foreign_keys_created=[],
                is_lossless=True,
                preserves_dependencies=True,
            )

        pk_set = frozenset(pk)
        all_columns = {c.name for c in table.columns}

        # Find partial dependencies
        partial_deps: dict[FrozenSet[str], Set[str]] = {}

        for fd in fds:
            det_set = frozenset(fd.determinant)

            # Check if determinant is a proper subset of PK
            if det_set < pk_set:  # Proper subset
                # This is a partial dependency if dependent is not in PK
                if fd.dependent not in pk_set:
                    if det_set not in partial_deps:
                        partial_deps[det_set] = set()
                    partial_deps[det_set].add(fd.dependent)

        if not partial_deps:
            # No partial dependencies, already in 2NF
            return DecompositionResult(
                original_table=table,
                decomposed_tables=[
                    DecomposedTable(
                        name=table.name,
                        columns=[c.name for c in table.columns],
                        primary_key=pk,
                        source_table=table.name,
                        reason="Already in 2NF (no partial dependencies)",
                    )
                ],
                foreign_keys_created=[],
                is_lossless=True,
                preserves_dependencies=True,
            )

        decomposed_tables: List[DecomposedTable] = []
        moved_columns: Set[str] = set()

        # Create tables for each partial dependency
        for det_set, dependents in partial_deps.items():
            det_list = sorted(det_set)

            # Compute closure of determinant to get all dependent columns
            closure = self._compute_closure(det_set, fds)
            # Only include columns that are in this table and not in PK
            table_columns = (closure & all_columns) - pk_set
            table_columns = table_columns | det_set  # Include determinant

            new_table_name = self._name_decomposed_table(table.name, det_list)
            new_columns = sorted(table_columns)

            decomposed_tables.append(
                DecomposedTable(
                    name=new_table_name,
                    columns=new_columns,
                    primary_key=det_list,
                    source_table=table.name,
                    reason=f"Partial dependency: {', '.join(det_list)} -> {', '.join(sorted(dependents))}",
                )
            )

            moved_columns.update(table_columns - det_set)

        # Create the main table with remaining columns
        remaining_columns = (all_columns - moved_columns) | pk_set
        remaining_list = sorted(remaining_columns)

        decomposed_tables.insert(
            0,
            DecomposedTable(
                name=table.name,
                columns=remaining_list,
                primary_key=pk,
                source_table=table.name,
                reason="Main table after 2NF decomposition",
            ),
        )

        # Generate foreign keys
        foreign_keys = self._generate_foreign_keys(decomposed_tables)

        # Check lossless join
        is_lossless = self._is_lossless_join(table, decomposed_tables, fds)

        # Check dependency preservation
        preserves_deps = self._check_dependency_preservation(
            fds, decomposed_tables, all_columns
        )

        return DecompositionResult(
            original_table=table,
            decomposed_tables=decomposed_tables,
            foreign_keys_created=foreign_keys,
            is_lossless=is_lossless,
            preserves_dependencies=preserves_deps,
        )

    def decompose_3nf(
        self,
        table: Table,
        fds: List[FunctionalDependency],
        candidate_keys: List[CandidateKey],
    ) -> DecompositionResult:
        """
        Decompose a table to Third Normal Form (3NF).

        Uses Bernstein's synthesis algorithm which guarantees:
        - Lossless join decomposition
        - Dependency preservation

        Algorithm:
        1. Compute minimal cover of FDs
        2. Create a table for each FD in minimal cover
        3. If no table contains a candidate key, add one
        4. Remove redundant tables

        Args:
            table: The table to decompose.
            fds: List of functional dependencies for the table.
            candidate_keys: List of candidate keys for the table.

        Returns:
            DecompositionResult containing the decomposed tables.
        """
        if not fds:
            # No FDs means table is trivially in 3NF
            pk = (
                candidate_keys[0].columns
                if candidate_keys
                else [c.name for c in table.columns if c.is_primary_key]
            )
            return DecompositionResult(
                original_table=table,
                decomposed_tables=[
                    DecomposedTable(
                        name=table.name,
                        columns=[c.name for c in table.columns],
                        primary_key=pk if pk else [table.columns[0].name],
                        source_table=table.name,
                        reason="Already in 3NF (no functional dependencies)",
                    )
                ],
                foreign_keys_created=[],
                is_lossless=True,
                preserves_dependencies=True,
            )

        all_columns = {c.name for c in table.columns}

        # Step 1: Compute minimal cover
        minimal_cover = self._compute_minimal_cover(fds)

        # Step 2: Group FDs by determinant
        fd_groups: dict[FrozenSet[str], Set[str]] = {}
        for fd in minimal_cover:
            det_key = frozenset(fd.determinant)
            if det_key not in fd_groups:
                fd_groups[det_key] = set()
            fd_groups[det_key].add(fd.dependent)

        # Step 3: Create tables for each FD group
        decomposed_tables: List[DecomposedTable] = []
        table_columns_sets: List[Set[str]] = []

        for det_set, dependents in fd_groups.items():
            det_list = sorted(det_set)
            columns = det_set | dependents
            columns = columns & all_columns  # Only include actual table columns
            columns_list = sorted(columns)

            if not columns_list:
                continue

            new_name = self._name_decomposed_table(table.name, det_list)

            decomposed_tables.append(
                DecomposedTable(
                    name=new_name,
                    columns=columns_list,
                    primary_key=det_list,
                    source_table=table.name,
                    reason=f"3NF synthesis: {', '.join(det_list)} -> {', '.join(sorted(dependents))}",
                )
            )
            table_columns_sets.append(columns)

        # Step 4: Check if any table contains a candidate key
        key_preserved = False
        for ck in candidate_keys:
            ck_set = set(ck.columns)
            for col_set in table_columns_sets:
                if ck_set.issubset(col_set):
                    key_preserved = True
                    break
            if key_preserved:
                break

        # If no candidate key preserved, add a table for the first candidate key
        if not key_preserved and candidate_keys:
            best_key = candidate_keys[0]
            key_cols = sorted(best_key.columns)

            decomposed_tables.append(
                DecomposedTable(
                    name=self._name_decomposed_table(table.name, key_cols),
                    columns=key_cols,
                    primary_key=key_cols,
                    source_table=table.name,
                    reason="Added to preserve candidate key for lossless join",
                )
            )

        # Step 5: Remove redundant tables (subset tables)
        decomposed_tables = self._remove_redundant_tables(decomposed_tables)

        # Handle edge case: if decomposition results in single table with all columns
        if len(decomposed_tables) == 1:
            dt = decomposed_tables[0]
            dt.name = table.name
            dt.reason = "Already in 3NF"

        # Generate foreign keys
        foreign_keys = self._generate_foreign_keys(decomposed_tables)

        return DecompositionResult(
            original_table=table,
            decomposed_tables=decomposed_tables,
            foreign_keys_created=foreign_keys,
            is_lossless=True,  # Bernstein's algorithm guarantees lossless
            preserves_dependencies=True,  # Bernstein's algorithm guarantees preservation
        )

    def decompose_bcnf(
        self,
        table: Table,
        fds: List[FunctionalDependency],
        candidate_keys: List[CandidateKey],
    ) -> DecompositionResult:
        """
        Decompose a table to Boyce-Codd Normal Form (BCNF).

        BCNF requires that for every non-trivial FD X -> Y,
        X must be a superkey.

        Algorithm (iterative):
        1. Find an FD X -> Y that violates BCNF
        2. Decompose into R1(X, Y) and R2(R - Y)
        3. Repeat for each resulting table

        Note: BCNF decomposition may not preserve all dependencies.

        Args:
            table: The table to decompose.
            fds: List of functional dependencies for the table.
            candidate_keys: List of candidate keys for the table.

        Returns:
            DecompositionResult containing the decomposed tables.
        """
        if not fds:
            pk = (
                candidate_keys[0].columns
                if candidate_keys
                else [c.name for c in table.columns if c.is_primary_key]
            )
            return DecompositionResult(
                original_table=table,
                decomposed_tables=[
                    DecomposedTable(
                        name=table.name,
                        columns=[c.name for c in table.columns],
                        primary_key=pk if pk else [table.columns[0].name],
                        source_table=table.name,
                        reason="Already in BCNF (no functional dependencies)",
                    )
                ],
                foreign_keys_created=[],
                is_lossless=True,
                preserves_dependencies=True,
            )

        all_columns = {c.name for c in table.columns}
        superkeys = self._compute_superkeys(all_columns, candidate_keys)

        # Start with the original table
        pending: List[Tuple[str, Set[str], List[FunctionalDependency]]] = [
            (table.name, all_columns, fds)
        ]
        decomposed_tables: List[DecomposedTable] = []

        while pending:
            current_name, current_cols, current_fds = pending.pop(0)

            # Project FDs onto current columns
            projected_fds = self._project_fds(current_fds, current_cols)

            # Find BCNF violation
            violating_fd = self._find_bcnf_violation(
                projected_fds, current_cols, superkeys
            )

            if violating_fd is None:
                # No violation, this table is in BCNF
                # Determine primary key for this decomposed table
                pk = self._find_key_for_columns(current_cols, candidate_keys, fds)
                decomposed_tables.append(
                    DecomposedTable(
                        name=current_name,
                        columns=sorted(current_cols),
                        primary_key=sorted(pk) if pk else sorted(current_cols),
                        source_table=table.name,
                        reason="In BCNF",
                    )
                )
            else:
                # Decompose on the violating FD
                det_set = set(violating_fd.determinant)
                dep_set = {violating_fd.dependent}

                # Compute closure of determinant
                closure = self._compute_closure(det_set, projected_fds)
                closure = closure & current_cols  # Restrict to current columns

                # R1 = X+ (closure of determinant)
                r1_cols = closure
                r1_name = self._name_decomposed_table(
                    current_name, sorted(det_set)
                )

                # R2 = (R - Y) U X = current_cols - (closure - X)
                r2_cols = current_cols - (closure - det_set)
                r2_name = f"{current_name}_rem"

                # Add to pending for further decomposition
                if len(r1_cols) >= 2:  # Only add if meaningful
                    pending.append((r1_name, r1_cols, projected_fds))
                if len(r2_cols) >= 2:
                    pending.append((r2_name, r2_cols, projected_fds))

        # Remove redundant tables
        decomposed_tables = self._remove_redundant_tables(decomposed_tables)

        # Handle single table result
        if len(decomposed_tables) == 1:
            dt = decomposed_tables[0]
            dt.name = table.name
            dt.reason = "Already in BCNF"

        # Generate foreign keys
        foreign_keys = self._generate_foreign_keys(decomposed_tables)

        # Check dependency preservation
        preserves_deps = self._check_dependency_preservation(
            fds, decomposed_tables, all_columns
        )

        # BCNF decomposition is always lossless
        return DecompositionResult(
            original_table=table,
            decomposed_tables=decomposed_tables,
            foreign_keys_created=foreign_keys,
            is_lossless=True,
            preserves_dependencies=preserves_deps,
        )

    def _compute_closure(
        self,
        attributes: Set[str],
        fds: List[FunctionalDependency],
    ) -> Set[str]:
        """
        Compute the attribute closure of a set of attributes under given FDs.

        The closure X+ is the set of all attributes that can be functionally
        determined from X using the given functional dependencies.

        Args:
            attributes: Initial set of attributes.
            fds: List of functional dependencies.

        Returns:
            The closure of the attribute set.
        """
        closure = set(attributes)
        changed = True

        while changed:
            changed = False
            for fd in fds:
                det_set = set(fd.determinant)
                if det_set.issubset(closure) and fd.dependent not in closure:
                    closure.add(fd.dependent)
                    changed = True

        return closure

    def _is_lossless_join(
        self,
        original: Table,
        decomposed: List[DecomposedTable],
        fds: List[FunctionalDependency],
    ) -> bool:
        """
        Check if a decomposition satisfies the lossless join property.

        A decomposition is lossless if joining the decomposed tables
        reconstructs exactly the original table (no spurious tuples).

        Uses the chase algorithm simplified for two-way decompositions
        and the common attribute superkey test.

        Args:
            original: The original table.
            decomposed: List of decomposed tables.
            fds: Functional dependencies of the original table.

        Returns:
            True if decomposition is lossless, False otherwise.
        """
        if len(decomposed) <= 1:
            return True

        all_original_cols = {c.name for c in original.columns}

        # For binary decomposition, check if common attributes form a key
        # for at least one of the decomposed tables
        if len(decomposed) == 2:
            cols1 = set(decomposed[0].columns)
            cols2 = set(decomposed[1].columns)
            common = cols1 & cols2

            if not common:
                return False

            # Check if common is a superkey for either table
            closure = self._compute_closure(common, fds)
            return cols1.issubset(closure) or cols2.issubset(closure)

        # For n-way decomposition, use simplified check:
        # Ensure every pair of tables shares attributes that form a key
        for i, dt1 in enumerate(decomposed):
            cols1 = set(dt1.columns)
            for dt2 in decomposed[i + 1 :]:
                cols2 = set(dt2.columns)
                common = cols1 & cols2

                if common:
                    closure = self._compute_closure(common, fds)
                    if cols1.issubset(closure) or cols2.issubset(closure):
                        return True

        # Check if union of all decomposed tables covers original
        all_decomposed = set()
        for dt in decomposed:
            all_decomposed.update(dt.columns)

        return all_original_cols.issubset(all_decomposed)

    def _compute_minimal_cover(
        self,
        fds: List[FunctionalDependency],
    ) -> List[FunctionalDependency]:
        """
        Compute the minimal cover (canonical cover) of a set of FDs.

        A minimal cover has the following properties:
        1. Single attribute on RHS (already satisfied by our FD model)
        2. No redundant FDs
        3. No extraneous attributes in LHS

        Args:
            fds: List of functional dependencies.

        Returns:
            The minimal cover of the FDs.
        """
        # Step 1: Decompose RHS (already done - our FDs have single RHS)
        result = [
            FunctionalDependency(
                determinant=list(fd.determinant),
                dependent=fd.dependent,
                confidence=fd.confidence,
            )
            for fd in fds
            if not fd.is_trivial
        ]

        # Step 2: Remove extraneous attributes from LHS
        changed = True
        while changed:
            changed = False
            new_result = []

            for fd in result:
                if len(fd.determinant) == 1:
                    new_result.append(fd)
                    continue

                # Try removing each attribute from determinant
                reduced = False
                for i, attr in enumerate(fd.determinant):
                    reduced_det = fd.determinant[:i] + fd.determinant[i + 1 :]
                    if not reduced_det:
                        continue

                    # Check if reduced determinant still determines dependent
                    other_fds = [f for f in result if f != fd] + [
                        FunctionalDependency(
                            determinant=reduced_det,
                            dependent=fd.dependent,
                        )
                    ]
                    closure = self._compute_closure(set(reduced_det), other_fds)

                    if fd.dependent in closure:
                        new_result.append(
                            FunctionalDependency(
                                determinant=reduced_det,
                                dependent=fd.dependent,
                                confidence=fd.confidence,
                            )
                        )
                        reduced = True
                        changed = True
                        break

                if not reduced:
                    new_result.append(fd)

            result = new_result

        # Step 3: Remove redundant FDs
        final_result = []
        for i, fd in enumerate(result):
            other_fds = result[:i] + result[i + 1 :]
            closure = self._compute_closure(set(fd.determinant), other_fds)

            if fd.dependent not in closure:
                final_result.append(fd)

        return final_result

    def _generate_foreign_keys(
        self,
        decomposed: List[DecomposedTable],
    ) -> List[ForeignKeyRelationship]:
        """
        Generate foreign key relationships between decomposed tables.

        Foreign keys are created when the primary key of one table
        appears as columns in another table.

        Args:
            decomposed: List of decomposed tables.

        Returns:
            List of foreign key relationships.
        """
        foreign_keys: List[ForeignKeyRelationship] = []

        for i, dt1 in enumerate(decomposed):
            pk1_set = set(dt1.primary_key)
            cols1_set = set(dt1.columns)

            for dt2 in decomposed[i + 1 :]:
                cols2_set = set(dt2.columns)
                pk2_set = set(dt2.primary_key)

                # Check if dt1's PK is in dt2's columns (dt2 references dt1)
                if pk1_set.issubset(cols2_set) and pk1_set != pk2_set:
                    fk = ForeignKeyRelationship(
                        name=f"fk_{dt2.name}_{dt1.name}",
                        from_table=dt2.name,
                        from_columns=sorted(pk1_set),
                        to_table=dt1.name,
                        to_columns=sorted(pk1_set),
                        cardinality="N:1",
                        is_identifying=pk1_set.issubset(pk2_set),
                    )
                    foreign_keys.append(fk)

                # Check if dt2's PK is in dt1's columns (dt1 references dt2)
                if pk2_set.issubset(cols1_set) and pk2_set != pk1_set:
                    fk = ForeignKeyRelationship(
                        name=f"fk_{dt1.name}_{dt2.name}",
                        from_table=dt1.name,
                        from_columns=sorted(pk2_set),
                        to_table=dt2.name,
                        to_columns=sorted(pk2_set),
                        cardinality="N:1",
                        is_identifying=pk2_set.issubset(pk1_set),
                    )
                    foreign_keys.append(fk)

        return foreign_keys

    def _name_decomposed_table(
        self,
        original_name: str,
        key_columns: List[str],
    ) -> str:
        """
        Generate a name for a decomposed table.

        Creates a meaningful name based on the original table name
        and the key columns of the new table.

        Args:
            original_name: Name of the original table.
            key_columns: Primary key columns of the new table.

        Returns:
            Name for the decomposed table.
        """
        if not key_columns:
            return f"{original_name}_decomp"

        # Create a suffix from key column names
        suffix = "_".join(
            col[:10] for col in key_columns[:3]  # Limit length
        )

        # Clean up suffix
        suffix = suffix.replace(" ", "_").lower()

        return f"{original_name}_{suffix}"

    def _compute_superkeys(
        self,
        all_columns: Set[str],
        candidate_keys: List[CandidateKey],
    ) -> List[FrozenSet[str]]:
        """
        Compute all superkeys from candidate keys.

        A superkey is any superset of a candidate key.

        Args:
            all_columns: All columns in the table.
            candidate_keys: List of candidate keys.

        Returns:
            List of superkey column sets.
        """
        superkeys: List[FrozenSet[str]] = []

        for ck in candidate_keys:
            ck_set = frozenset(ck.columns)
            superkeys.append(ck_set)

            # Generate supersets (limited to avoid explosion)
            remaining = all_columns - ck_set
            for col in remaining:
                superkeys.append(ck_set | {col})

        return superkeys

    def _find_bcnf_violation(
        self,
        fds: List[FunctionalDependency],
        columns: Set[str],
        superkeys: List[FrozenSet[str]],
    ) -> Optional[FunctionalDependency]:
        """
        Find a functional dependency that violates BCNF.

        An FD X -> Y violates BCNF if X is not a superkey.

        Args:
            fds: Functional dependencies to check.
            columns: Columns in the current table.
            superkeys: List of superkeys.

        Returns:
            A violating FD, or None if table is in BCNF.
        """
        for fd in fds:
            det_set = frozenset(fd.determinant)

            # Check if FD is relevant to current columns
            if not det_set.issubset(columns):
                continue
            if fd.dependent not in columns:
                continue

            # Check if trivial
            if fd.dependent in det_set:
                continue

            # Check if determinant is a superkey
            is_superkey = any(sk.issubset(det_set) for sk in superkeys)

            if not is_superkey:
                # Also check by computing closure
                closure = self._compute_closure(det_set, fds)
                is_superkey = columns.issubset(closure)

            if not is_superkey:
                return fd

        return None

    def _project_fds(
        self,
        fds: List[FunctionalDependency],
        columns: Set[str],
    ) -> List[FunctionalDependency]:
        """
        Project functional dependencies onto a subset of columns.

        Returns only FDs whose determinant and dependent are
        both within the given column set.

        Args:
            fds: Original functional dependencies.
            columns: Column set to project onto.

        Returns:
            Projected functional dependencies.
        """
        result = []

        for fd in fds:
            det_set = set(fd.determinant)
            if det_set.issubset(columns) and fd.dependent in columns:
                result.append(fd)

        return result

    def _find_key_for_columns(
        self,
        columns: Set[str],
        candidate_keys: List[CandidateKey],
        fds: List[FunctionalDependency],
    ) -> Optional[Set[str]]:
        """
        Find a key for a subset of columns.

        Args:
            columns: Column set to find key for.
            candidate_keys: Original candidate keys.
            fds: Functional dependencies.

        Returns:
            A set of columns forming a key, or None.
        """
        # Check if any candidate key is within columns
        for ck in candidate_keys:
            ck_set = set(ck.columns)
            if ck_set.issubset(columns):
                # Verify it determines all columns
                projected_fds = self._project_fds(fds, columns)
                closure = self._compute_closure(ck_set, projected_fds)
                if columns.issubset(closure):
                    return ck_set

        # Try to find a minimal key from FDs
        projected_fds = self._project_fds(fds, columns)

        # Start with all columns and try to reduce
        current_key = set(columns)

        for col in list(columns):
            test_key = current_key - {col}
            if not test_key:
                continue
            closure = self._compute_closure(test_key, projected_fds)
            if columns.issubset(closure):
                current_key = test_key

        return current_key if current_key else None

    def _remove_redundant_tables(
        self,
        tables: List[DecomposedTable],
    ) -> List[DecomposedTable]:
        """
        Remove tables whose columns are subsets of another table.

        Args:
            tables: List of decomposed tables.

        Returns:
            List with redundant tables removed.
        """
        result = []

        for i, t1 in enumerate(tables):
            cols1 = set(t1.columns)
            is_subset = False

            for j, t2 in enumerate(tables):
                if i == j:
                    continue
                cols2 = set(t2.columns)
                if cols1 < cols2:  # Proper subset
                    is_subset = True
                    break

            if not is_subset:
                result.append(t1)

        return result

    def _check_dependency_preservation(
        self,
        original_fds: List[FunctionalDependency],
        decomposed: List[DecomposedTable],
        all_columns: Set[str],
    ) -> bool:
        """
        Check if all original FDs are preserved in the decomposition.

        An FD is preserved if it can be derived from the projected FDs
        of the decomposed tables.

        Args:
            original_fds: Original functional dependencies.
            decomposed: Decomposed tables.
            all_columns: All columns in original table.

        Returns:
            True if all FDs are preserved.
        """
        # Collect all projected FDs from decomposed tables
        preserved_fds: List[FunctionalDependency] = []

        for dt in decomposed:
            dt_cols = set(dt.columns)
            for fd in original_fds:
                det_set = set(fd.determinant)
                if det_set.issubset(dt_cols) and fd.dependent in dt_cols:
                    preserved_fds.append(fd)

        # Check if each original FD can be derived
        for fd in original_fds:
            if fd.is_trivial:
                continue

            det_set = set(fd.determinant)
            closure = self._compute_closure(det_set, preserved_fds)

            if fd.dependent not in closure:
                return False

        return True
