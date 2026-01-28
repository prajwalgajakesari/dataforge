"""
Candidate Key Finder.

This module identifies candidate keys in database tables:
- Single-column candidate keys
- Composite candidate keys
- Primary key recommendations
- Surrogate key suggestions
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Protocol, Set, Tuple
from itertools import combinations

from core.models.analysis import CandidateKey, KeyAnalysis, ConfidenceLevel


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


class DatabaseConnector(Protocol):
    """Protocol for database connection."""

    async def execute_query(self, query: str) -> List[Dict[str, Any]]:
        """Execute a query and return results as list of dicts."""
        ...


class CandidateKeyFinder:
    """
    Finds candidate keys in database tables.

    A candidate key is a minimal set of columns that uniquely identifies rows.
    This class implements a bottom-up search algorithm that:
    1. First checks all single columns for uniqueness
    2. Then progressively checks combinations of increasing size
    3. Prunes superkeys to ensure minimality

    Usage:
        finder = CandidateKeyFinder(db_connector)
        analysis = await finder.analyze_keys("public", "orders")

        # Get recommended primary key
        print(analysis.recommended_primary_key)

        # Get all candidate keys
        for key in analysis.candidate_keys:
            print(f"{key.columns}: uniqueness={key.uniqueness}")
    """

    # Good primary key naming patterns
    PK_NAME_PATTERNS = frozenset(["id", "_id", "_pk", "key", "code", "uuid", "guid"])

    # Surrogate key naming suggestions
    SURROGATE_KEY_NAMES = ("id", "pk", "row_id", "surrogate_id")

    def __init__(
        self,
        db_connector: DatabaseConnector,
        max_key_columns: int = 4,
        uniqueness_threshold: float = 1.0,
        null_threshold: float = 0.0,
    ):
        """
        Initialize the key finder.

        Args:
            db_connector: Database connection for executing queries
            max_key_columns: Maximum number of columns to consider in composite keys.
                Higher values find more keys but increase computation exponentially.
            uniqueness_threshold: Required uniqueness ratio (1.0 = perfectly unique).
                Values below 1.0 allow approximate keys with some duplicates.
            null_threshold: Maximum allowed null percentage (0.0-100.0).
                Primary keys typically require 0.0 (no nulls allowed).
        """
        self.db = db_connector
        self.max_key_columns = max_key_columns
        self.uniqueness_threshold = uniqueness_threshold
        self.null_threshold = null_threshold

    async def analyze_keys(
        self,
        schema_name: str,
        table_name: str,
        columns: Optional[List[str]] = None,
    ) -> KeyAnalysis:
        """
        Perform complete key analysis on a table.

        This method:
        1. Retrieves existing primary key and unique constraints
        2. Discovers all candidate keys using bottom-up search
        3. Generates primary key recommendations

        Args:
            schema_name: Database schema name (e.g., 'public')
            table_name: Name of the table to analyze
            columns: Specific columns to consider. If None, all columns are analyzed.

        Returns:
            KeyAnalysis containing:
            - Existing primary key (if any)
            - Existing unique constraints
            - Discovered candidate keys
            - Primary key recommendation with reasoning

        Raises:
            Exception: If database queries fail
        """
        logger.info(f"Analyzing keys for {schema_name}.{table_name}")

        # Get existing constraints from database
        existing_pk = await self._get_primary_key(schema_name, table_name)
        unique_constraints = await self._get_unique_constraints(schema_name, table_name)

        # Get column list if not specified
        if not columns:
            columns = await self._get_columns(schema_name, table_name)

        if not columns:
            logger.warning(f"No columns found for {schema_name}.{table_name}")
            return KeyAnalysis(
                table_name=table_name,
                schema_name=schema_name,
                primary_key=existing_pk,
                unique_constraints=unique_constraints,
            )

        # Get row count for analysis
        row_count = await self._get_row_count(schema_name, table_name)

        if row_count == 0:
            logger.info(f"Table {schema_name}.{table_name} is empty")
            return KeyAnalysis(
                table_name=table_name,
                schema_name=schema_name,
                primary_key=existing_pk,
                unique_constraints=unique_constraints,
                key_recommendation_reason="Table is empty - cannot determine candidate keys",
            )

        # Find candidate keys using bottom-up search
        candidate_keys = await self._find_candidate_keys(
            schema_name, table_name, columns, row_count
        )

        # Generate primary key recommendation
        recommended_pk, reason = self._recommend_primary_key(
            candidate_keys, existing_pk, columns
        )

        logger.info(
            f"Found {len(candidate_keys)} candidate keys for {schema_name}.{table_name}"
        )

        return KeyAnalysis(
            table_name=table_name,
            schema_name=schema_name,
            primary_key=existing_pk,
            unique_constraints=unique_constraints,
            candidate_keys=candidate_keys,
            recommended_primary_key=recommended_pk,
            key_recommendation_reason=reason,
        )

    async def find_single_column_keys(
        self,
        schema_name: str,
        table_name: str,
        columns: Optional[List[str]] = None,
    ) -> List[CandidateKey]:
        """
        Find only single-column candidate keys (faster than full analysis).

        Useful when you only need simple keys and want to avoid the
        computational cost of checking composite keys.

        Args:
            schema_name: Database schema name
            table_name: Table to analyze
            columns: Specific columns to check (None = all)

        Returns:
            List of single-column candidate keys
        """
        if not columns:
            columns = await self._get_columns(schema_name, table_name)

        row_count = await self._get_row_count(schema_name, table_name)

        if row_count == 0:
            return []

        keys = []
        for col in columns:
            key = await self._check_key(schema_name, table_name, [col], row_count)
            if key:
                keys.append(key)

        return keys

    async def suggest_surrogate_key(
        self,
        schema_name: str,
        table_name: str,
    ) -> Dict[str, Any]:
        """
        Suggest a surrogate key when no natural key exists.

        Returns a dictionary with:
        - suggested_name: Recommended column name for surrogate key
        - data_type: Recommended data type
        - reason: Explanation for the suggestion

        Args:
            schema_name: Database schema name
            table_name: Table name

        Returns:
            Dictionary with surrogate key suggestion
        """
        # Check existing columns to avoid name conflicts
        existing_columns = await self._get_columns(schema_name, table_name)
        existing_lower = {c.lower() for c in existing_columns}

        # Find a non-conflicting name
        suggested_name = None
        for name in self.SURROGATE_KEY_NAMES:
            if name not in existing_lower:
                suggested_name = name
                break

        if not suggested_name:
            suggested_name = f"{table_name}_id"

        return {
            "suggested_name": suggested_name,
            "data_type": "BIGSERIAL",
            "reason": (
                f"No natural candidate key found. "
                f"Recommend adding surrogate key '{suggested_name}' "
                f"with auto-incrementing BIGSERIAL type for reliable row identification."
            ),
            "ddl_example": (
                f"ALTER TABLE {schema_name}.{table_name} "
                f"ADD COLUMN {suggested_name} BIGSERIAL PRIMARY KEY;"
            ),
        }

    async def _find_candidate_keys(
        self,
        schema: str,
        table: str,
        columns: List[str],
        row_count: int,
    ) -> List[CandidateKey]:
        """
        Find all candidate keys using bottom-up search with pruning.

        Algorithm:
        1. Start with single columns
        2. Track which column sets are already keys (superkeys)
        3. For each size k from 2 to max_key_columns:
           - Generate all k-combinations
           - Skip combinations that are supersets of known keys
           - Check remaining combinations for uniqueness

        This ensures minimality: no candidate key is a superset of another.
        """
        candidate_keys: List[CandidateKey] = []
        superkeys: Set[frozenset] = set()  # Track non-minimal keys

        # Phase 1: Check single columns first (fastest)
        logger.debug(f"Checking {len(columns)} single-column candidates")
        single_column_tasks = [
            self._check_key(schema, table, [col], row_count) for col in columns
        ]
        single_results = await asyncio.gather(*single_column_tasks, return_exceptions=True)

        for col, result in zip(columns, single_results):
            if isinstance(result, Exception):
                logger.warning(f"Error checking column {col}: {result}")
                continue
            if result:
                candidate_keys.append(result)
                superkeys.add(frozenset([col]))

        # Phase 2: Check composite keys (if needed and within limit)
        for size in range(2, min(self.max_key_columns + 1, len(columns) + 1)):
            combos_to_check = []

            for combo in combinations(columns, size):
                combo_set = frozenset(combo)

                # Skip if any subset is already a key (pruning superkeys)
                is_superkey = any(
                    existing.issubset(combo_set) for existing in superkeys
                )
                if is_superkey:
                    continue

                combos_to_check.append(combo)

            if not combos_to_check:
                logger.debug(f"No {size}-column combinations to check (all pruned)")
                continue

            logger.debug(f"Checking {len(combos_to_check)} {size}-column combinations")

            # Check combinations in parallel for better performance
            tasks = [
                self._check_key(schema, table, list(combo), row_count)
                for combo in combos_to_check
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for combo, result in zip(combos_to_check, results):
                if isinstance(result, Exception):
                    logger.warning(f"Error checking composite key {combo}: {result}")
                    continue
                if result:
                    candidate_keys.append(result)
                    superkeys.add(frozenset(combo))

        return candidate_keys

    async def _check_key(
        self,
        schema: str,
        table: str,
        columns: List[str],
        row_count: int,
    ) -> Optional[CandidateKey]:
        """
        Check if a column combination is a candidate key.

        A valid candidate key must have:
        1. Uniqueness >= threshold (typically 1.0 for perfect uniqueness)
        2. Null percentage <= threshold (typically 0.0 for no nulls)
        """
        # Build column reference string with proper quoting
        cols_quoted = ", ".join(f'"{c}"' for c in columns)
        cols_tuple = f"({cols_quoted})" if len(columns) > 1 else f'"{columns[0]}"'

        # Build null check condition
        null_conditions = " AND ".join(f'"{c}" IS NOT NULL' for c in columns)

        # Query for uniqueness check
        uniqueness_query = f"""
            SELECT
                COUNT(*) as total,
                COUNT(DISTINCT {cols_tuple}) as distinct_count
            FROM "{schema}"."{table}"
            WHERE {null_conditions}
        """

        try:
            result = await self.db.execute_query(uniqueness_query)
            if not result:
                return None

            total = result[0].get("total", 0)
            distinct = result[0].get("distinct_count", 0)

            if total == 0:
                return None

            uniqueness = distinct / total if total > 0 else 0

            # Query for null percentage
            null_check_conditions = " OR ".join(f'"{c}" IS NULL' for c in columns)
            null_query = f"""
                SELECT COUNT(*) as null_count
                FROM "{schema}"."{table}"
                WHERE {null_check_conditions}
            """
            null_result = await self.db.execute_query(null_query)
            null_count = null_result[0].get("null_count", 0) if null_result else 0
            null_pct = (null_count / row_count * 100) if row_count > 0 else 0

            # Check if this qualifies as a candidate key
            if uniqueness >= self.uniqueness_threshold and null_pct <= self.null_threshold:
                # Determine if recommended as primary key
                recommended = (
                    len(columns) == 1
                    and uniqueness == 1.0
                    and null_pct == 0
                    and self._is_good_pk_name(columns[0])
                )

                reason = self._generate_key_reason(columns, uniqueness, null_pct)

                return CandidateKey(
                    columns=columns,
                    is_minimal=True,  # Already filtered superkeys
                    uniqueness=round(uniqueness, 4),
                    null_percentage=round(null_pct, 2),
                    recommended_as_primary=recommended,
                    recommendation_reason=reason,
                )

        except Exception as e:
            logger.warning(f"Error checking key {columns}: {e}")

        return None

    def _generate_key_reason(
        self,
        columns: List[str],
        uniqueness: float,
        null_pct: float,
    ) -> Optional[str]:
        """Generate a human-readable reason for key recommendation."""
        if uniqueness != 1.0:
            return f"Near-unique with {uniqueness:.2%} uniqueness"

        if null_pct > 0:
            return f"Unique but has {null_pct:.1f}% nulls"

        if len(columns) == 1:
            col = columns[0]
            if self._is_good_pk_name(col):
                return f"Single column '{col}' is unique, non-null, follows naming convention"
            return f"Single column '{col}' is unique and non-null"

        return f"Composite key with {len(columns)} columns, all unique and non-null"

    def _is_good_pk_name(self, column_name: str) -> bool:
        """
        Check if column name follows good primary key naming conventions.

        Good PK names typically contain: id, _id, _pk, key, code, uuid, guid
        """
        name_lower = column_name.lower()
        return any(pattern in name_lower for pattern in self.PK_NAME_PATTERNS)

    def _recommend_primary_key(
        self,
        candidates: List[CandidateKey],
        existing_pk: Optional[List[str]],
        all_columns: List[str],
    ) -> Tuple[Optional[List[str]], Optional[str]]:
        """
        Generate primary key recommendation based on discovered candidates.

        Priority order:
        1. Use existing primary key if present
        2. Prefer single-column 'id' column
        3. Prefer single-column ending with '_id'
        4. Prefer other single-column keys with good naming
        5. Use smallest composite key
        6. Suggest surrogate key if no candidates
        """
        if existing_pk:
            return existing_pk, "Using existing primary key"

        if not candidates:
            return None, "No natural key found - consider adding surrogate key (id)"

        # Separate single and composite keys
        single_keys = [k for k in candidates if len(k.columns) == 1]
        composite_keys = [k for k in candidates if len(k.columns) > 1]

        if single_keys:
            # Priority 1: 'id' column
            for key in single_keys:
                if key.columns[0].lower() == "id":
                    return key.columns, "Natural 'id' column is unique and non-null"

            # Priority 2: Columns ending with '_id'
            for key in single_keys:
                if key.columns[0].lower().endswith("_id"):
                    return (
                        key.columns,
                        f"'{key.columns[0]}' is unique and follows naming convention",
                    )

            # Priority 3: Columns with good PK naming patterns
            for key in single_keys:
                if self._is_good_pk_name(key.columns[0]):
                    return (
                        key.columns,
                        f"'{key.columns[0]}' is unique, non-null, good naming convention",
                    )

            # Priority 4: First single key (highest uniqueness already)
            best = single_keys[0]
            return best.columns, f"'{best.columns[0]}' is unique and non-null"

        # Use smallest composite key
        if composite_keys:
            composite_keys.sort(key=lambda k: len(k.columns))
            best = composite_keys[0]
            cols_str = ", ".join(best.columns)
            return (
                best.columns,
                f"Composite key ({cols_str}) - smallest unique combination",
            )

        return None, "No natural key found - consider adding surrogate key (id)"

    async def _get_primary_key(
        self, schema: str, table: str
    ) -> Optional[List[str]]:
        """Get existing primary key columns from database catalog."""
        query = f"""
            SELECT kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            WHERE tc.table_schema = '{schema}'
                AND tc.table_name = '{table}'
                AND tc.constraint_type = 'PRIMARY KEY'
            ORDER BY kcu.ordinal_position
        """
        try:
            result = await self.db.execute_query(query)
            if result:
                return [r["column_name"] for r in result]
        except Exception as e:
            logger.warning(f"Error getting primary key for {schema}.{table}: {e}")
        return None

    async def _get_unique_constraints(
        self, schema: str, table: str
    ) -> List[List[str]]:
        """Get existing unique constraints from database catalog."""
        query = f"""
            SELECT tc.constraint_name, kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            WHERE tc.table_schema = '{schema}'
                AND tc.table_name = '{table}'
                AND tc.constraint_type = 'UNIQUE'
            ORDER BY tc.constraint_name, kcu.ordinal_position
        """
        try:
            result = await self.db.execute_query(query)

            # Group columns by constraint name
            constraints: Dict[str, List[str]] = {}
            for row in result:
                name = row["constraint_name"]
                if name not in constraints:
                    constraints[name] = []
                constraints[name].append(row["column_name"])

            return list(constraints.values())
        except Exception as e:
            logger.warning(f"Error getting unique constraints for {schema}.{table}: {e}")
        return []

    async def _get_columns(self, schema: str, table: str) -> List[str]:
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
            logger.warning(f"Error getting columns for {schema}.{table}: {e}")
        return []

    async def _get_row_count(self, schema: str, table: str) -> int:
        """Get table row count."""
        query = f'SELECT COUNT(*) as count FROM "{schema}"."{table}"'
        try:
            result = await self.db.execute_query(query)
            return result[0]["count"] if result else 0
        except Exception as e:
            logger.warning(f"Error getting row count for {schema}.{table}: {e}")
        return 0


async def analyze_table_keys(
    db_connector: DatabaseConnector,
    schema_name: str,
    table_name: str,
    max_key_columns: int = 4,
) -> KeyAnalysis:
    """
    Convenience function for quick key analysis.

    Args:
        db_connector: Database connection
        schema_name: Schema name
        table_name: Table name
        max_key_columns: Maximum columns in composite key

    Returns:
        KeyAnalysis with discovered keys and recommendations

    Example:
        analysis = await analyze_table_keys(db, "public", "orders")
        print(f"Recommended PK: {analysis.recommended_primary_key}")
    """
    finder = CandidateKeyFinder(
        db_connector=db_connector,
        max_key_columns=max_key_columns,
    )
    return await finder.analyze_keys(schema_name, table_name)
