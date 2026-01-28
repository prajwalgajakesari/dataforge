"""
Relationship Inferrer.

This module discovers implicit relationships between tables:
- Naming convention matching (user_id -> users.id)
- Data overlap analysis (value subset detection)
- Cardinality inference (1:1, 1:N, N:M)
- Confidence scoring
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Protocol, Set, Tuple, runtime_checkable
from dataclasses import dataclass

from core.models.analysis import RelationshipAnalysis, ConfidenceLevel
from core.models.schema import ForeignKeyRelationship


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
    """Protocol for database connection."""

    async def execute_query(self, query: str) -> List[Dict[str, Any]]:
        """Execute a query and return results as list of dicts."""
        ...


@dataclass
class TableColumn:
    """Reference to a specific column in a table."""

    schema_name: str
    table_name: str
    column_name: str
    data_type: str
    is_primary_key: bool = False
    is_unique: bool = False
    is_nullable: bool = True


@dataclass
class RelationshipCandidate:
    """A potential relationship between two columns."""

    from_column: TableColumn
    to_column: TableColumn
    match_reason: str
    name_similarity: float = 0.0
    data_overlap: float = 0.0


class RelationshipInferrer:
    """
    Infers implicit relationships between tables.

    Uses multiple heuristics:
    1. Naming conventions (_id suffix, table_id pattern)
    2. Data type compatibility
    3. Value overlap analysis
    4. Cardinality analysis

    Usage:
        inferrer = RelationshipInferrer(db_connector)
        relationships = await inferrer.infer_relationships(
            schema_name="public",
            tables=["orders", "customers", "products"]
        )
    """

    # Common singular to plural mappings for irregular nouns
    IRREGULAR_PLURALS: Dict[str, str] = {
        "person": "people",
        "child": "children",
        "man": "men",
        "woman": "women",
        "foot": "feet",
        "tooth": "teeth",
        "goose": "geese",
        "mouse": "mice",
        "ox": "oxen",
        "datum": "data",
        "medium": "media",
        "analysis": "analyses",
        "crisis": "crises",
        "axis": "axes",
        "thesis": "theses",
        "category": "categories",
        "company": "companies",
        "country": "countries",
        "city": "cities",
        "activity": "activities",
        "entry": "entries",
        "entity": "entities",
        "address": "addresses",
        "status": "statuses",
        "class": "classes",
        "process": "processes",
        "index": "indices",
    }

    def __init__(
        self,
        db_connector: DatabaseConnector,
        min_overlap_threshold: float = 0.8,
        sample_size: int = 1000,
    ):
        """
        Initialize the relationship inferrer.

        Args:
            db_connector: Database connection for executing queries
            min_overlap_threshold: Minimum value overlap to consider relationship (0-1)
            sample_size: Sample size for overlap analysis
        """
        self.db = db_connector
        self.min_overlap_threshold = min_overlap_threshold
        self.sample_size = sample_size

        # Build reverse mapping for plural lookups
        self._plural_to_singular: Dict[str, str] = {
            v: k for k, v in self.IRREGULAR_PLURALS.items()
        }

    async def infer_relationships(
        self,
        schema_name: str,
        tables: Optional[List[str]] = None,
    ) -> List[RelationshipAnalysis]:
        """
        Infer relationships between tables in a schema.

        Args:
            schema_name: Schema to analyze
            tables: Specific tables to analyze (None = all tables in schema)

        Returns:
            List of inferred relationships with confidence scores
        """
        logger.info(f"Inferring relationships in schema '{schema_name}'")

        # Get tables if not specified
        if not tables:
            tables = await self._get_tables(schema_name)

        if not tables:
            logger.warning(f"No tables found in schema '{schema_name}'")
            return []

        logger.info(f"Analyzing {len(tables)} tables: {', '.join(tables[:5])}{'...' if len(tables) > 5 else ''}")

        # Get column info for all tables in parallel
        table_columns: Dict[str, List[TableColumn]] = {}
        column_tasks = [
            self._get_column_info(schema_name, table) for table in tables
        ]
        results = await asyncio.gather(*column_tasks, return_exceptions=True)

        for table, result in zip(tables, results):
            if isinstance(result, Exception):
                logger.warning(f"Failed to get columns for table '{table}': {result}")
                continue
            table_columns[table] = result

        if not table_columns:
            logger.warning("No table columns could be retrieved")
            return []

        # Get existing foreign keys (to avoid duplicates)
        existing_fks = await self._get_existing_fks(schema_name, list(table_columns.keys()))

        # Find candidates based on naming conventions
        candidates = self._find_naming_candidates(table_columns)
        logger.info(f"Found {len(candidates)} relationship candidates based on naming conventions")

        # Verify candidates with data analysis
        relationships: List[RelationshipAnalysis] = []
        for candidate in candidates:
            # Skip if already an explicit FK
            if self._is_existing_fk(candidate, existing_fks):
                logger.debug(
                    f"Skipping {candidate.from_column.column_name} -> "
                    f"{candidate.to_column.table_name}: already an explicit FK"
                )
                continue

            analysis = await self._analyze_relationship(candidate)
            if analysis and analysis.confidence != ConfidenceLevel.LOW:
                relationships.append(analysis)

        logger.info(f"Found {len(relationships)} implicit relationships")
        return relationships

    async def infer_all_relationships(
        self,
        schema_name: str,
        tables: Optional[List[str]] = None,
        include_explicit: bool = True,
    ) -> List[RelationshipAnalysis]:
        """
        Infer all relationships (both implicit and explicit).

        Args:
            schema_name: Schema to analyze
            tables: Specific tables to analyze (None = all)
            include_explicit: Whether to include explicit FK relationships

        Returns:
            Combined list of all relationships
        """
        # Get implicit relationships
        implicit = await self.infer_relationships(schema_name, tables)

        if not include_explicit:
            return implicit

        # Get explicit FK relationships
        if not tables:
            tables = await self._get_tables(schema_name)

        existing_fks = await self._get_existing_fks(schema_name, tables)

        explicit: List[RelationshipAnalysis] = []
        for from_table, from_col, to_table, to_col in existing_fks:
            # For explicit FKs, we can do a quick overlap check
            overlap = await self._calculate_overlap_quick(
                schema_name, from_table, from_col, schema_name, to_table, to_col
            )

            explicit.append(
                RelationshipAnalysis(
                    from_table=from_table,
                    from_column=from_col,
                    to_table=to_table,
                    to_column=to_col,
                    value_overlap_percentage=round(overlap * 100, 2),
                    cardinality="1:N",  # Default for FK
                    is_nullable=True,  # Would need more info
                    null_percentage=0.0,
                    confidence=ConfidenceLevel.HIGH,
                    is_explicit_fk=True,
                )
            )

        return implicit + explicit

    def _find_naming_candidates(
        self,
        table_columns: Dict[str, List[TableColumn]],
    ) -> List[RelationshipCandidate]:
        """
        Find relationship candidates based on naming conventions.

        Patterns detected:
        - column_id -> columns.id (e.g., customer_id -> customers.id)
        - column_name -> column_names.id (plural matching)
        - column -> columns.id (singular to plural)
        """
        candidates: List[RelationshipCandidate] = []

        # For each table, look for columns that might reference other tables
        for from_table, columns in table_columns.items():
            for col in columns:
                # Skip primary keys - they don't reference other tables
                if col.is_primary_key:
                    continue

                # Pattern 1: _id suffix pattern (e.g., customer_id -> customers)
                if col.column_name.endswith("_id"):
                    potential_table = col.column_name[:-3]  # Remove _id suffix
                    self._try_match_table(
                        col,
                        potential_table,
                        from_table,
                        table_columns,
                        candidates,
                        "Naming convention: _id suffix",
                        0.95,
                    )

                # Pattern 2: _fk suffix (explicit foreign key naming)
                elif col.column_name.endswith("_fk"):
                    potential_table = col.column_name[:-3]
                    self._try_match_table(
                        col,
                        potential_table,
                        from_table,
                        table_columns,
                        candidates,
                        "Naming convention: _fk suffix",
                        0.9,
                    )

                # Pattern 3: column name matches table name (e.g., orders.customer -> customers.id)
                else:
                    self._try_match_table(
                        col,
                        col.column_name,
                        from_table,
                        table_columns,
                        candidates,
                        "Naming convention: table name match",
                        0.85,
                    )

        return candidates

    def _try_match_table(
        self,
        col: TableColumn,
        potential_table: str,
        from_table: str,
        table_columns: Dict[str, List[TableColumn]],
        candidates: List[RelationshipCandidate],
        reason: str,
        similarity: float,
    ) -> None:
        """Try to match a potential table reference and add to candidates."""
        for to_table, to_cols in table_columns.items():
            if to_table == from_table:
                continue

            # Check various name matching patterns
            if self._names_match(potential_table, to_table):
                # Find PK of target table
                pk_col = self._find_primary_key(to_cols)
                if pk_col:
                    candidates.append(
                        RelationshipCandidate(
                            from_column=col,
                            to_column=pk_col,
                            match_reason=f"{reason}: {col.column_name} -> {to_table}",
                            name_similarity=similarity,
                        )
                    )

    def _names_match(self, singular: str, table_name: str) -> bool:
        """
        Check if a singular name matches a table name (considering pluralization).

        Args:
            singular: Singular form (e.g., "customer", "category")
            table_name: Table name to match against (e.g., "customers", "categories")

        Returns:
            True if names match
        """
        singular_lower = singular.lower()
        table_lower = table_name.lower()

        # Exact match
        if singular_lower == table_lower:
            return True

        # Check irregular plurals
        if singular_lower in self.IRREGULAR_PLURALS:
            if self.IRREGULAR_PLURALS[singular_lower] == table_lower:
                return True

        # Check reverse (table is singular, matching plural form)
        if table_lower in self._plural_to_singular:
            if self._plural_to_singular[table_lower] == singular_lower:
                return True

        # Regular plural patterns
        plural_forms = self._get_plural_forms(singular_lower)
        if table_lower in plural_forms:
            return True

        # Check if table name is singular form of our potential plural
        singular_forms = self._get_singular_forms(table_lower)
        if singular_lower in singular_forms:
            return True

        return False

    def _get_plural_forms(self, singular: str) -> Set[str]:
        """Get possible plural forms of a singular word."""
        forms = {singular}

        # Standard -s suffix
        forms.add(singular + "s")

        # Words ending in s, x, z, ch, sh -> add -es
        if singular.endswith(("s", "x", "z", "ch", "sh")):
            forms.add(singular + "es")

        # Words ending in consonant + y -> replace y with -ies
        if len(singular) > 1 and singular.endswith("y"):
            if singular[-2] not in "aeiou":
                forms.add(singular[:-1] + "ies")

        # Words ending in f or fe -> replace with -ves
        if singular.endswith("f"):
            forms.add(singular[:-1] + "ves")
        elif singular.endswith("fe"):
            forms.add(singular[:-2] + "ves")

        return forms

    def _get_singular_forms(self, plural: str) -> Set[str]:
        """Get possible singular forms of a plural word."""
        forms = {plural}

        # Remove -s suffix
        if plural.endswith("s") and not plural.endswith("ss"):
            forms.add(plural[:-1])

        # Remove -es suffix
        if plural.endswith("es"):
            forms.add(plural[:-2])

        # Words ending in -ies -> replace with -y
        if plural.endswith("ies"):
            forms.add(plural[:-3] + "y")

        # Words ending in -ves -> replace with -f or -fe
        if plural.endswith("ves"):
            forms.add(plural[:-3] + "f")
            forms.add(plural[:-3] + "fe")

        return forms

    def _find_primary_key(self, columns: List[TableColumn]) -> Optional[TableColumn]:
        """Find the primary key column in a list."""
        # First, look for explicit primary key
        for col in columns:
            if col.is_primary_key:
                return col

        # Fallback: look for 'id' column (common convention)
        for col in columns:
            if col.column_name.lower() == "id":
                return col

        # Secondary fallback: look for unique not-null column named like a key
        for col in columns:
            if col.is_unique and not col.is_nullable:
                name_lower = col.column_name.lower()
                if name_lower.endswith("_id") or name_lower == "uuid" or name_lower == "guid":
                    return col

        return None

    async def _analyze_relationship(
        self,
        candidate: RelationshipCandidate,
    ) -> Optional[RelationshipAnalysis]:
        """
        Analyze a candidate relationship for validity.

        Performs:
        1. Data type compatibility check
        2. Value overlap analysis
        3. Cardinality determination
        4. Null percentage calculation
        5. Confidence scoring
        """
        from_col = candidate.from_column
        to_col = candidate.to_column

        # Check data type compatibility
        if not self._types_compatible(from_col.data_type, to_col.data_type):
            logger.debug(
                f"Type mismatch: {from_col.column_name} ({from_col.data_type}) "
                f"-> {to_col.column_name} ({to_col.data_type})"
            )
            return None

        # Calculate value overlap
        overlap_pct = await self._calculate_overlap(from_col, to_col)

        if overlap_pct < self.min_overlap_threshold:
            logger.debug(
                f"Low overlap ({overlap_pct:.2%}): {from_col.column_name} -> {to_col.column_name}"
            )
            return None

        # Determine cardinality
        cardinality = await self._determine_cardinality(from_col, to_col)

        # Calculate null percentage in FK column
        null_pct = await self._get_null_percentage(from_col)

        # Determine confidence level
        confidence = self._calculate_confidence(
            candidate.name_similarity,
            overlap_pct,
            from_col.is_unique,
        )

        return RelationshipAnalysis(
            from_table=from_col.table_name,
            from_column=from_col.column_name,
            to_table=to_col.table_name,
            to_column=to_col.column_name,
            value_overlap_percentage=round(overlap_pct * 100, 2),
            cardinality=cardinality,
            is_nullable=from_col.is_nullable,
            null_percentage=null_pct,
            confidence=confidence,
            is_explicit_fk=False,
        )

    def _types_compatible(self, type1: str, type2: str) -> bool:
        """
        Check if two data types are compatible for a relationship.

        Types are compatible if they can hold the same values.
        """
        # Normalize types (remove precision/scale info)
        type1_lower = type1.lower().split("(")[0].strip()
        type2_lower = type2.lower().split("(")[0].strip()

        # Exact match
        if type1_lower == type2_lower:
            return True

        # Compatible integer types
        int_types = {
            "integer", "int", "int4", "bigint", "int8",
            "smallint", "int2", "serial", "bigserial", "smallserial",
        }
        if type1_lower in int_types and type2_lower in int_types:
            return True

        # Compatible string types
        str_types = {
            "varchar", "character varying", "text",
            "char", "character", "bpchar", "name",
        }
        if type1_lower in str_types and type2_lower in str_types:
            return True

        # UUID types
        if "uuid" in type1_lower and "uuid" in type2_lower:
            return True

        # Numeric types with different precision
        numeric_types = {"numeric", "decimal", "real", "double precision", "float", "float4", "float8"}
        if type1_lower in numeric_types and type2_lower in numeric_types:
            return True

        return False

    async def _calculate_overlap(
        self,
        from_col: TableColumn,
        to_col: TableColumn,
    ) -> float:
        """
        Calculate what percentage of FK values exist in PK.

        A high overlap indicates a valid foreign key relationship.
        """
        return await self._calculate_overlap_quick(
            from_col.schema_name,
            from_col.table_name,
            from_col.column_name,
            to_col.schema_name,
            to_col.table_name,
            to_col.column_name,
        )

    async def _calculate_overlap_quick(
        self,
        from_schema: str,
        from_table: str,
        from_column: str,
        to_schema: str,
        to_table: str,
        to_column: str,
    ) -> float:
        """Calculate overlap between two columns."""
        query = f"""
            SELECT
                COUNT(DISTINCT f."{from_column}") as fk_distinct,
                COUNT(DISTINCT CASE
                    WHEN t."{to_column}" IS NOT NULL
                    THEN f."{from_column}"
                END) as matched
            FROM "{from_schema}"."{from_table}" f
            LEFT JOIN "{to_schema}"."{to_table}" t
                ON f."{from_column}" = t."{to_column}"
            WHERE f."{from_column}" IS NOT NULL
        """

        try:
            result = await self.db.execute_query(query)
            if result:
                fk_distinct = result[0].get("fk_distinct", 0) or 0
                matched = result[0].get("matched", 0) or 0
                return matched / fk_distinct if fk_distinct > 0 else 0.0
        except Exception as e:
            logger.warning(
                f"Error calculating overlap for {from_table}.{from_column} -> "
                f"{to_table}.{to_column}: {e}"
            )

        return 0.0

    async def _determine_cardinality(
        self,
        from_col: TableColumn,
        to_col: TableColumn,
    ) -> str:
        """
        Determine relationship cardinality (1:1, 1:N, N:M).

        - 1:1: FK column is unique (each FK value appears once)
        - 1:N: FK column can have duplicates (default FK behavior)
        - N:M: Would require a junction table (detected elsewhere)
        """
        # Check if FK column is unique (would make it 1:1)
        if from_col.is_unique:
            return "1:1"

        # Check average references per PK value
        query = f"""
            SELECT AVG(cnt) as avg_refs, MAX(cnt) as max_refs
            FROM (
                SELECT "{from_col.column_name}", COUNT(*) as cnt
                FROM "{from_col.schema_name}"."{from_col.table_name}"
                WHERE "{from_col.column_name}" IS NOT NULL
                GROUP BY "{from_col.column_name}"
            ) t
        """

        try:
            result = await self.db.execute_query(query)
            if result and result[0].get("avg_refs"):
                avg = float(result[0]["avg_refs"])
                if avg <= 1.1:  # Allow small variance
                    return "1:1"
                else:
                    return "1:N"
        except Exception as e:
            logger.warning(f"Error determining cardinality: {e}")

        return "1:N"  # Default assumption for FK relationships

    async def _get_null_percentage(self, col: TableColumn) -> float:
        """Get null percentage for a column."""
        query = f"""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN "{col.column_name}" IS NULL THEN 1 ELSE 0 END) as nulls
            FROM "{col.schema_name}"."{col.table_name}"
        """

        try:
            result = await self.db.execute_query(query)
            if result:
                total = result[0].get("total", 0) or 0
                nulls = result[0].get("nulls", 0) or 0
                return round((nulls / total * 100) if total > 0 else 0.0, 2)
        except Exception as e:
            logger.warning(f"Error getting null percentage for {col.column_name}: {e}")

        return 0.0

    def _calculate_confidence(
        self,
        name_similarity: float,
        overlap: float,
        is_unique: bool,
    ) -> ConfidenceLevel:
        """
        Calculate confidence level for the inferred relationship.

        Scoring factors:
        - Name similarity (40% weight): How well column names match conventions
        - Value overlap (50% weight): How many FK values exist in PK
        - Uniqueness (10% penalty): Unique FKs are unusual (might be wrong direction)
        """
        # Calculate weighted score
        score = (name_similarity * 0.4) + (overlap * 0.5)

        # Slight penalty for unique columns (unusual for FK)
        if is_unique:
            score -= 0.05

        # Apply 10% bonus for non-unique (typical FK behavior)
        if not is_unique:
            score += 0.1

        # Clamp score
        score = max(0.0, min(1.0, score))

        if score >= 0.85:
            return ConfidenceLevel.HIGH
        elif score >= 0.65:
            return ConfidenceLevel.MEDIUM
        else:
            return ConfidenceLevel.LOW

    def _is_existing_fk(
        self,
        candidate: RelationshipCandidate,
        existing_fks: Set[Tuple[str, str, str, str]],
    ) -> bool:
        """Check if candidate matches an existing FK constraint."""
        key = (
            candidate.from_column.table_name,
            candidate.from_column.column_name,
            candidate.to_column.table_name,
            candidate.to_column.column_name,
        )
        return key in existing_fks

    async def _get_existing_fks(
        self,
        schema: str,
        tables: List[str],
    ) -> Set[Tuple[str, str, str, str]]:
        """Get existing foreign key relationships from database schema."""
        if not tables:
            return set()

        tables_str = ", ".join(f"'{t}'" for t in tables)
        query = f"""
            SELECT
                tc.table_name as from_table,
                kcu.column_name as from_column,
                ccu.table_name as to_table,
                ccu.column_name as to_column
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage ccu
                ON tc.constraint_name = ccu.constraint_name
                AND tc.table_schema = ccu.table_schema
            WHERE tc.table_schema = '{schema}'
                AND tc.table_name IN ({tables_str})
                AND tc.constraint_type = 'FOREIGN KEY'
        """

        try:
            result = await self.db.execute_query(query)
            return {
                (r["from_table"], r["from_column"], r["to_table"], r["to_column"])
                for r in result
            }
        except Exception as e:
            logger.warning(f"Error getting existing FKs: {e}")
            return set()

    async def _get_tables(self, schema: str) -> List[str]:
        """Get all base tables in a schema."""
        query = f"""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = '{schema}'
                AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """

        try:
            result = await self.db.execute_query(query)
            return [r["table_name"] for r in result]
        except Exception as e:
            logger.error(f"Error getting tables for schema '{schema}': {e}")
            return []

    async def _get_column_info(
        self,
        schema: str,
        table: str,
    ) -> List[TableColumn]:
        """Get column info for a table including PK/unique status."""
        query = f"""
            SELECT
                c.column_name,
                c.data_type,
                c.is_nullable = 'YES' as is_nullable,
                COALESCE(pk.is_pk, false) as is_primary_key,
                COALESCE(uq.is_unique, false) as is_unique
            FROM information_schema.columns c
            LEFT JOIN (
                SELECT kcu.column_name, true as is_pk
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                    AND tc.table_schema = kcu.table_schema
                WHERE tc.table_schema = '{schema}'
                    AND tc.table_name = '{table}'
                    AND tc.constraint_type = 'PRIMARY KEY'
            ) pk ON c.column_name = pk.column_name
            LEFT JOIN (
                SELECT kcu.column_name, true as is_unique
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                    AND tc.table_schema = kcu.table_schema
                WHERE tc.table_schema = '{schema}'
                    AND tc.table_name = '{table}'
                    AND tc.constraint_type = 'UNIQUE'
            ) uq ON c.column_name = uq.column_name
            WHERE c.table_schema = '{schema}' AND c.table_name = '{table}'
            ORDER BY c.ordinal_position
        """

        try:
            result = await self.db.execute_query(query)
            return [
                TableColumn(
                    schema_name=schema,
                    table_name=table,
                    column_name=r["column_name"],
                    data_type=r["data_type"],
                    is_primary_key=bool(r.get("is_primary_key", False)),
                    is_unique=bool(r.get("is_unique", False)),
                    is_nullable=bool(r.get("is_nullable", True)),
                )
                for r in result
            ]
        except Exception as e:
            logger.error(f"Error getting column info for {schema}.{table}: {e}")
            return []

    def to_foreign_key_relationships(
        self,
        analyses: List[RelationshipAnalysis],
        schema_name: str = "public",
    ) -> List[ForeignKeyRelationship]:
        """
        Convert RelationshipAnalysis results to ForeignKeyRelationship models.

        This is useful for integrating inferred relationships into the schema model.

        Args:
            analyses: List of RelationshipAnalysis from inference
            schema_name: Default schema name for relationships

        Returns:
            List of ForeignKeyRelationship models
        """
        relationships = []

        for analysis in analyses:
            if analysis.confidence == ConfidenceLevel.LOW:
                continue  # Skip low confidence

            name = f"fk_{analysis.from_table}_{analysis.from_column}_inferred"

            relationships.append(
                ForeignKeyRelationship(
                    name=name,
                    from_schema=schema_name,
                    from_table=analysis.from_table,
                    from_columns=[analysis.from_column],
                    to_schema=schema_name,
                    to_table=analysis.to_table,
                    to_columns=[analysis.to_column],
                    cardinality=analysis.cardinality,
                    is_nullable=analysis.is_nullable,
                    is_identifying=False,  # Inferred relationships are not identifying
                )
            )

        return relationships
