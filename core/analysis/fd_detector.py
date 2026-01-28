"""
Functional Dependency (FD) Detector.

This module implements algorithms for discovering functional dependencies:
- TANE-inspired bottom-up FD discovery
- SQL-based FD verification
- Approximate FD detection (with confidence thresholds)
- Transitive closure computation
"""

import asyncio
import logging
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple, Protocol, runtime_checkable
from itertools import combinations
from dataclasses import dataclass, field

from core.models.analysis import FunctionalDependency, ConfidenceLevel


def get_logger(name: str) -> logging.Logger:
    """Get or create a logger with the given name."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


logger = get_logger(__name__)


@runtime_checkable
class DatabaseConnector(Protocol):
    """Protocol for database connection to execute FD detection queries."""

    async def execute_query(self, query: str) -> List[Dict[str, Any]]:
        """Execute a query and return results as list of dicts."""
        ...


@dataclass
class FDCandidate:
    """A candidate functional dependency to verify."""

    determinant: Tuple[str, ...]  # LHS columns
    dependent: str  # RHS column

    def __hash__(self) -> int:
        return hash((self.determinant, self.dependent))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FDCandidate):
            return False
        return self.determinant == other.determinant and self.dependent == other.dependent

    def __repr__(self) -> str:
        return f"FDCandidate({', '.join(self.determinant)} -> {self.dependent})"


@dataclass
class FDVerificationResult:
    """Result of verifying a functional dependency."""

    determinant: List[str]
    dependent: str
    is_valid: bool
    confidence: float
    support: float
    violations: int
    total_groups: int


class FunctionalDependencyDetector:
    """
    Detects functional dependencies in database tables.

    Uses a combination of:
    1. SQL-based verification for exact FDs
    2. TANE-inspired algorithm for discovery
    3. Approximate FD detection with confidence scoring

    The TANE algorithm works bottom-up, starting with single-column determinants
    and building up to multi-column determinants while pruning non-minimal FDs.

    Usage:
        detector = FunctionalDependencyDetector(db_connector)
        fds = await detector.discover_fds("public", "orders")

        # Or verify specific FD
        fd = await detector.verify_fd(
            "public", "orders",
            determinant=["customer_id", "order_date"],
            dependent="order_total"
        )

        # Compute attribute closure
        closure = detector.compute_closure({"customer_id"}, fds)
    """

    def __init__(
        self,
        db_connector: DatabaseConnector,
        max_lhs_size: int = 3,
        min_confidence: float = 0.95,
        sample_size: int = 10000,
    ):
        """
        Initialize the FD detector.

        Args:
            db_connector: Database connection for queries
            max_lhs_size: Maximum columns in LHS (determinant) to consider.
                          Higher values find more FDs but increase complexity
                          exponentially (O(n^k) where k is max_lhs_size).
            min_confidence: Minimum confidence for approximate FDs (0.0-1.0).
                            1.0 requires exact FDs, lower values allow violations.
            sample_size: Number of rows to sample for large tables. Used when
                         exact verification is too expensive.
        """
        self.db = db_connector
        self.max_lhs_size = max_lhs_size
        self.min_confidence = min_confidence
        self.sample_size = sample_size

    async def discover_fds(
        self,
        schema_name: str,
        table_name: str,
        columns: Optional[List[str]] = None,
        include_trivial: bool = False,
    ) -> List[FunctionalDependency]:
        """
        Discover all functional dependencies in a table.

        Uses a TANE-inspired bottom-up approach:
        1. Start with single-column determinants
        2. For each determinant, test all other columns as dependents
        3. Move to larger determinants, skipping non-minimal candidates
        4. Prune candidates where a subset already determines the dependent

        Args:
            schema_name: Database schema name
            table_name: Table name to analyze
            columns: Specific columns to analyze (None = all columns)
            include_trivial: Include trivial FDs where dependent is in determinant

        Returns:
            List of discovered FunctionalDependency objects, sorted by
            determinant size then confidence
        """
        logger.info(f"Discovering FDs for {schema_name}.{table_name}")

        # Get columns if not specified
        if not columns:
            columns = await self._get_column_names(schema_name, table_name)

        if len(columns) < 2:
            logger.warning(
                f"Table {schema_name}.{table_name} has fewer than 2 columns, "
                "no FDs possible"
            )
            return []

        # Get row count for confidence calculations
        row_count = await self._get_row_count(schema_name, table_name)

        if row_count == 0:
            logger.warning(f"Table {schema_name}.{table_name} is empty")
            return []

        discovered_fds: List[FunctionalDependency] = []

        # Track which (determinant, dependent) pairs we've already found
        # to avoid non-minimal FDs
        found_deps: Dict[str, Set[FrozenSet[str]]] = {col: set() for col in columns}

        # Generate and verify candidates level by level (TANE-like)
        for lhs_size in range(1, min(self.max_lhs_size + 1, len(columns))):
            logger.debug(f"Checking determinants of size {lhs_size}")

            for lhs_combo in combinations(columns, lhs_size):
                lhs = list(lhs_combo)
                lhs_set = frozenset(lhs)

                # Test each potential RHS
                for rhs in columns:
                    # Skip trivial FDs (X -> X) unless requested
                    if rhs in lhs and not include_trivial:
                        continue

                    # Skip if a smaller determinant already determines this
                    if self._has_smaller_determinant(rhs, lhs_set, found_deps):
                        continue

                    # Verify FD using SQL
                    fd = await self._verify_fd_sql(
                        schema_name, table_name, lhs, rhs, row_count
                    )

                    if fd and fd.confidence >= self.min_confidence:
                        # Check if this is a minimal FD
                        if self._is_minimal_fd(fd, discovered_fds):
                            discovered_fds.append(fd)
                            found_deps[rhs].add(lhs_set)
                            logger.debug(f"Found FD: {fd}")

        # Classify FDs (partial, transitive)
        discovered_fds = self._classify_fds(discovered_fds, columns)

        # Sort by determinant size, then confidence
        discovered_fds.sort(key=lambda fd: (len(fd.determinant), -fd.confidence))

        logger.info(
            f"Discovered {len(discovered_fds)} FDs for {schema_name}.{table_name}"
        )
        return discovered_fds

    async def verify_fd(
        self,
        schema_name: str,
        table_name: str,
        determinant: List[str],
        dependent: str,
    ) -> Optional[FunctionalDependency]:
        """
        Verify a specific functional dependency.

        Tests whether determinant -> dependent holds in the table.
        Returns the FD with confidence metrics if it holds (above min_confidence),
        None otherwise.

        Args:
            schema_name: Database schema name
            table_name: Table name
            determinant: LHS columns (X in X -> Y)
            dependent: RHS column (Y in X -> Y)

        Returns:
            FunctionalDependency if valid (confidence >= min_confidence),
            None otherwise
        """
        row_count = await self._get_row_count(schema_name, table_name)
        fd = await self._verify_fd_sql(
            schema_name, table_name, determinant, dependent, row_count
        )

        if fd and fd.confidence >= self.min_confidence:
            return fd
        return None

    async def _verify_fd_sql(
        self,
        schema: str,
        table: str,
        lhs: List[str],
        rhs: str,
        total_rows: int,
    ) -> Optional[FunctionalDependency]:
        """
        Verify FD using SQL: X -> Y holds if for each X value, there's only one Y value.

        The verification works by:
        1. Grouping rows by the determinant (LHS) columns
        2. Counting how many distinct values of the dependent (RHS) exist per group
        3. Any group with >1 distinct RHS value is a violation

        Confidence = 1 - (violation_groups / total_groups)
        Support = (non_violating_groups / total_groups)

        Args:
            schema: Schema name
            table: Table name
            lhs: Determinant columns
            rhs: Dependent column
            total_rows: Total row count (for context)

        Returns:
            FunctionalDependency with metrics, or None on error
        """
        # Build column references with proper quoting
        lhs_cols = ", ".join(f'"{col}"' for col in lhs)
        rhs_col = f'"{rhs}"'

        # Count violations: groups where LHS is same but RHS differs
        violation_query = f"""
            SELECT COUNT(*) as violations FROM (
                SELECT {lhs_cols}
                FROM "{schema}"."{table}"
                WHERE {rhs_col} IS NOT NULL
                GROUP BY {lhs_cols}
                HAVING COUNT(DISTINCT {rhs_col}) > 1
            ) violation_groups
        """

        try:
            result = await self.db.execute_query(violation_query)
            violations = result[0]["violations"] if result else 0

            # Get number of distinct LHS groups (excluding null RHS)
            # Using a concatenation approach for composite keys
            if len(lhs) == 1:
                group_expr = f'"{lhs[0]}"'
            else:
                # Concatenate with a delimiter unlikely to appear in data
                group_expr = " || '|||' || ".join(
                    f'COALESCE("{col}"::text, \'\')' for col in lhs
                )

            group_query = f"""
                SELECT COUNT(*) as groups FROM (
                    SELECT DISTINCT {lhs_cols}
                    FROM "{schema}"."{table}"
                    WHERE {rhs_col} IS NOT NULL
                ) distinct_groups
            """
            group_result = await self.db.execute_query(group_query)
            total_groups = group_result[0]["groups"] if group_result else 0

            if total_groups == 0:
                return None

            # Calculate confidence and support
            confidence = 1.0 - (violations / total_groups) if total_groups > 0 else 0.0
            support = (total_groups - violations) / total_groups if total_groups > 0 else 0.0

            return FunctionalDependency(
                determinant=lhs,
                dependent=rhs,
                confidence=round(confidence, 4),
                support=round(support, 4),
                violations=violations,
                is_trivial=(rhs in lhs),
                is_partial=False,  # Will be classified later
                is_transitive=False,  # Will be classified later
            )

        except Exception as e:
            logger.warning(f"Error verifying FD {lhs} -> {rhs}: {e}")
            return None

    def _has_smaller_determinant(
        self,
        dependent: str,
        determinant: FrozenSet[str],
        found_deps: Dict[str, Set[FrozenSet[str]]],
    ) -> bool:
        """
        Check if a smaller determinant already determines the dependent.

        This is a key optimization in TANE: if {A} -> C holds,
        we don't need to check {A, B} -> C.

        Args:
            dependent: The dependent column (RHS)
            determinant: The current determinant set being checked
            found_deps: Map of dependent -> set of determinants that determine it

        Returns:
            True if a proper subset of determinant already determines dependent
        """
        for existing_det in found_deps.get(dependent, set()):
            if existing_det < determinant:  # Proper subset
                return True
        return False

    def _is_minimal_fd(
        self,
        fd: FunctionalDependency,
        existing_fds: List[FunctionalDependency],
    ) -> bool:
        """
        Check if FD is minimal (no subset of determinant also determines dependent).

        A minimal FD has no redundant columns in its determinant.
        For example, if {A} -> C holds, then {A, B} -> C is not minimal.

        Args:
            fd: The FD to check
            existing_fds: List of already discovered FDs

        Returns:
            True if no proper subset of fd's determinant also determines fd's dependent
        """
        fd_det_set = set(fd.determinant)

        for existing in existing_fds:
            if existing.dependent == fd.dependent:
                existing_det_set = set(existing.determinant)
                # If existing determinant is a proper subset, fd is not minimal
                if existing_det_set < fd_det_set:
                    return False

        return True

    def _classify_fds(
        self,
        fds: List[FunctionalDependency],
        all_columns: List[str],
    ) -> List[FunctionalDependency]:
        """
        Classify FDs as partial or transitive.

        Partial dependency (2NF violation):
        - Occurs when a non-prime attribute depends on part of a candidate key
        - Example: In (A, B) -> C, D and A -> D, D is partially dependent

        Transitive dependency (3NF violation):
        - Occurs when A -> B and B -> C, implying A -> C transitively
        - Example: student_id -> department and department -> building
                   means student_id -> building is transitive

        Args:
            fds: List of functional dependencies to classify
            all_columns: All columns in the table

        Returns:
            The same FDs with is_partial and is_transitive flags set
        """
        # Build a map of what each column set determines
        determines: Dict[FrozenSet[str], Set[str]] = {}
        for fd in fds:
            key = frozenset(fd.determinant)
            if key not in determines:
                determines[key] = set()
            determines[key].add(fd.dependent)

        # Also build reverse map: what determines each column
        determined_by: Dict[str, List[FrozenSet[str]]] = {}
        for fd in fds:
            if fd.dependent not in determined_by:
                determined_by[fd.dependent] = []
            determined_by[fd.dependent].append(frozenset(fd.determinant))

        # Check for transitive dependencies
        for fd in fds:
            det_set = frozenset(fd.determinant)

            # Check if any column in determinant is itself determined by another column
            # This indicates transitivity: A -> B and B -> C means A -> C is transitive
            for col in fd.determinant:
                if col in determined_by:
                    for other_det in determined_by[col]:
                        # If something else determines a column in our determinant,
                        # and that something is not our determinant, we might be transitive
                        if other_det != det_set and not other_det.issuperset(det_set):
                            fd.is_transitive = True
                            break
                if fd.is_transitive:
                    break

        # Check for partial dependencies
        # Find potential keys (single columns or small sets that determine many columns)
        potential_key_cols = set()
        for fd in fds:
            if len(fd.determinant) == 1 and fd.confidence == 1.0:
                # Single column determining something might be part of a key
                det_set = frozenset(fd.determinant)
                # Check if it determines most columns
                determined = determines.get(det_set, set())
                if len(determined) >= len(all_columns) * 0.3:
                    potential_key_cols.add(fd.determinant[0])

        # Mark partial dependencies
        for fd in fds:
            if len(fd.determinant) > 1:
                # Check if part of the determinant alone determines the dependent
                for i, col in enumerate(fd.determinant):
                    single_det = frozenset([col])
                    if fd.dependent in determines.get(single_det, set()):
                        fd.is_partial = True
                        break

        return fds

    def compute_closure(
        self,
        attributes: Set[str],
        fds: List[FunctionalDependency],
    ) -> Set[str]:
        """
        Compute the closure of a set of attributes under FDs.

        The closure X+ is all attributes that can be determined from X
        using the given functional dependencies. This is computed by
        repeatedly applying FDs until no new attributes are added.

        Algorithm:
        1. Initialize closure with input attributes
        2. Repeat:
           a. For each FD X -> Y where X is subset of closure
           b. Add Y to closure
        3. Until no changes

        This is useful for:
        - Determining if a set of columns is a superkey (closure = all columns)
        - Checking if an FD is implied by other FDs
        - Finding candidate keys

        Args:
            attributes: Starting set of attributes (column names)
            fds: List of functional dependencies

        Returns:
            Closure set including all determined attributes

        Example:
            >>> closure = detector.compute_closure({"student_id"}, fds)
            >>> # Returns all columns that student_id determines
        """
        closure = set(attributes)
        changed = True

        while changed:
            changed = False
            for fd in fds:
                # If the FD's determinant is a subset of the closure
                if set(fd.determinant).issubset(closure):
                    # Add the dependent to the closure if not already present
                    if fd.dependent not in closure:
                        closure.add(fd.dependent)
                        changed = True

        return closure

    def is_superkey(
        self,
        attributes: Set[str],
        all_columns: List[str],
        fds: List[FunctionalDependency],
    ) -> bool:
        """
        Check if a set of attributes is a superkey.

        A superkey is a set of columns whose closure equals all columns,
        meaning it can uniquely identify any row.

        Args:
            attributes: Set of column names to check
            all_columns: All columns in the table
            fds: List of functional dependencies

        Returns:
            True if attributes form a superkey
        """
        closure = self.compute_closure(attributes, fds)
        return set(all_columns).issubset(closure)

    def find_candidate_keys(
        self,
        columns: List[str],
        fds: List[FunctionalDependency],
    ) -> List[Set[str]]:
        """
        Find all candidate keys using the discovered FDs.

        A candidate key is a minimal superkey - a set of columns that:
        1. Can determine all other columns (is a superkey)
        2. Has no proper subset that is also a superkey (is minimal)

        This uses the closure computation to test candidate sets.

        Args:
            columns: All columns in the table
            fds: List of functional dependencies

        Returns:
            List of candidate keys, each as a set of column names
        """
        all_cols = set(columns)
        candidate_keys: List[Set[str]] = []

        # Start with single columns, then pairs, etc.
        for size in range(1, len(columns) + 1):
            for combo in combinations(columns, size):
                attrs = set(combo)

                # Skip if a subset is already a candidate key
                if any(ck < attrs for ck in candidate_keys):
                    continue

                # Check if this is a superkey
                if self.is_superkey(attrs, columns, fds):
                    candidate_keys.append(attrs)

            # If we found keys at this size, we have all minimal keys
            if candidate_keys and size == min(len(ck) for ck in candidate_keys):
                # Continue to find all keys of the same size
                pass
            elif candidate_keys:
                # Found all minimal keys, no need to check larger sets
                break

        return candidate_keys

    async def find_violations(
        self,
        schema_name: str,
        table_name: str,
        fd: FunctionalDependency,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Find actual rows that violate an FD.

        This is useful for understanding why an FD has low confidence
        and for data quality analysis. Returns sample rows where the
        same determinant values have different dependent values.

        Args:
            schema_name: Database schema name
            table_name: Table name
            fd: The functional dependency to check
            limit: Maximum number of violation rows to return

        Returns:
            List of dicts representing violating rows, each containing
            the determinant and dependent column values
        """
        lhs_cols = ", ".join(f'"{col}"' for col in fd.determinant)
        rhs_col = f'"{fd.dependent}"'

        # Build column list for selection
        select_cols = ", ".join(f't."{col}"' for col in fd.determinant)
        select_cols += f", t.{rhs_col}"

        # Find groups with violations, then get sample rows from those groups
        query = f"""
            WITH violation_groups AS (
                SELECT {lhs_cols}
                FROM "{schema_name}"."{table_name}"
                WHERE {rhs_col} IS NOT NULL
                GROUP BY {lhs_cols}
                HAVING COUNT(DISTINCT {rhs_col}) > 1
            )
            SELECT {select_cols}
            FROM "{schema_name}"."{table_name}" t
            INNER JOIN violation_groups v ON {self._build_join_condition("t", "v", fd.determinant)}
            ORDER BY {", ".join(f't."{col}"' for col in fd.determinant)}
            LIMIT {limit}
        """

        try:
            return await self.db.execute_query(query)
        except Exception as e:
            logger.warning(f"Error finding violations for {fd}: {e}")
            return []

    def _build_join_condition(
        self, left_alias: str, right_alias: str, columns: List[str]
    ) -> str:
        """Build a JOIN condition for multiple columns."""
        conditions = [
            f'{left_alias}."{col}" = {right_alias}."{col}"' for col in columns
        ]
        return " AND ".join(conditions)

    async def analyze_normalization(
        self,
        schema_name: str,
        table_name: str,
        fds: Optional[List[FunctionalDependency]] = None,
    ) -> Dict[str, Any]:
        """
        Analyze the normalization level of a table based on FDs.

        Checks:
        - 1NF: Assumed if data is in relational table
        - 2NF: No partial dependencies (non-key depends on part of key)
        - 3NF: No transitive dependencies (non-key depends on non-key)
        - BCNF: Every determinant is a superkey

        Args:
            schema_name: Database schema name
            table_name: Table name
            fds: Pre-computed FDs (will discover if not provided)

        Returns:
            Dict with normalization analysis:
            - current_form: "1NF", "2NF", "3NF", or "BCNF"
            - violations: List of FDs violating each form
            - recommendations: Suggestions for normalization
        """
        if fds is None:
            fds = await self.discover_fds(schema_name, table_name)

        columns = await self._get_column_names(schema_name, table_name)

        result = {
            "current_form": "1NF",
            "is_2nf": True,
            "is_3nf": True,
            "is_bcnf": True,
            "partial_dependencies": [],
            "transitive_dependencies": [],
            "bcnf_violations": [],
            "candidate_keys": [],
            "recommendations": [],
        }

        if not fds:
            result["current_form"] = "BCNF"
            result["recommendations"].append(
                "No functional dependencies found. Table may already be normalized "
                "or lacks sufficient data for FD detection."
            )
            return result

        # Find candidate keys
        candidate_keys = self.find_candidate_keys(columns, fds)
        result["candidate_keys"] = [list(ck) for ck in candidate_keys]

        # Check each FD against normalization rules
        for fd in fds:
            det_set = set(fd.determinant)

            # Check BCNF: determinant must be a superkey
            is_superkey = self.is_superkey(det_set, columns, fds)
            if not is_superkey:
                result["is_bcnf"] = False
                result["bcnf_violations"].append(str(fd))

            # Check 3NF: no transitive dependencies
            if fd.is_transitive:
                result["is_3nf"] = False
                result["transitive_dependencies"].append(str(fd))

            # Check 2NF: no partial dependencies
            if fd.is_partial:
                result["is_2nf"] = False
                result["partial_dependencies"].append(str(fd))

        # Determine current normal form
        if result["is_bcnf"]:
            result["current_form"] = "BCNF"
        elif result["is_3nf"]:
            result["current_form"] = "3NF"
        elif result["is_2nf"]:
            result["current_form"] = "2NF"
        else:
            result["current_form"] = "1NF"

        # Generate recommendations
        if result["partial_dependencies"]:
            result["recommendations"].append(
                f"To achieve 2NF, remove partial dependencies by splitting the table. "
                f"Affected FDs: {', '.join(result['partial_dependencies'][:3])}"
            )

        if result["transitive_dependencies"]:
            result["recommendations"].append(
                f"To achieve 3NF, remove transitive dependencies by creating "
                f"separate tables. Affected FDs: {', '.join(result['transitive_dependencies'][:3])}"
            )

        if result["bcnf_violations"] and result["is_3nf"]:
            result["recommendations"].append(
                f"To achieve BCNF, ensure all determinants are superkeys. "
                f"This may require decomposing the table further."
            )

        return result

    async def _get_column_names(self, schema: str, table: str) -> List[str]:
        """Get column names from information_schema."""
        query = f"""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = '{schema}' AND table_name = '{table}'
            ORDER BY ordinal_position
        """
        try:
            result = await self.db.execute_query(query)
            return [r["column_name"] for r in result]
        except Exception as e:
            logger.error(f"Failed to get column names for {schema}.{table}: {e}")
            return []

    async def _get_row_count(self, schema: str, table: str) -> int:
        """Get row count for a table."""
        query = f'SELECT COUNT(*) as count FROM "{schema}"."{table}"'
        try:
            result = await self.db.execute_query(query)
            return result[0]["count"] if result else 0
        except Exception as e:
            logger.warning(f"Could not get row count for {schema}.{table}: {e}")
            return 0
