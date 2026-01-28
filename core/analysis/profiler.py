"""
Enhanced data profiler for comprehensive column and table analysis.

This module provides deep data profiling capabilities including:
- Statistical analysis (min, max, mean, median, stddev, percentiles)
- Distribution analysis (histograms, top values, outliers)
- Pattern detection (email, phone, URL, UUID, dates, etc.)
- String analysis (length stats, empty count)
- Data quality scoring (0-100)
"""

import re
import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple, Protocol, runtime_checkable
from datetime import datetime

from core.models.analysis import (
    ColumnStatistics,
    ColumnProfile,
    TableProfile,
    PatternMatch,
    PatternType,
    ConfidenceLevel,
)


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


# Pattern definitions for detection (15+ patterns)
PATTERNS: Dict[PatternType, re.Pattern] = {
    PatternType.EMAIL: re.compile(
        r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    ),
    PatternType.PHONE: re.compile(
        r"^[\+]?[(]?[0-9]{3}[)]?[-\s\.]?[0-9]{3}[-\s\.]?[0-9]{4,6}$"
    ),
    PatternType.URL: re.compile(r"^https?://[^\s/$.?#].[^\s]*$"),
    PatternType.UUID: re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I
    ),
    PatternType.IP_ADDRESS: re.compile(
        r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}"
        r"(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
    ),
    PatternType.DATE_ISO: re.compile(r"^\d{4}-\d{2}-\d{2}$"),
    PatternType.CREDIT_CARD: re.compile(
        r"^(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13})$"
    ),
    PatternType.ZIP_CODE: re.compile(r"^\d{5}(?:-\d{4})?$"),
    PatternType.JSON: re.compile(r"^[\[\{].*[\]\}]$", re.DOTALL),
    PatternType.NUMERIC_ID: re.compile(r"^\d+$"),
    PatternType.SSN: re.compile(r"^\d{3}-\d{2}-\d{4}$"),
    PatternType.MAC_ADDRESS: re.compile(
        r"^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$"
    ),
    PatternType.SLUG: re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$"),
    PatternType.CURRENCY: re.compile(r"^\$?\d{1,3}(?:,\d{3})*(?:\.\d{2})?$"),
    PatternType.PERCENTAGE: re.compile(r"^\d+(?:\.\d+)?%$"),
}


@runtime_checkable
class DatabaseConnector(Protocol):
    """Protocol for database connection to execute profiling queries."""

    async def execute_query(self, query: str) -> List[Dict[str, Any]]:
        """Execute a query and return results as list of dicts."""
        ...

    async def get_sample(
        self, table: str, schema: str, limit: int
    ) -> List[Dict[str, Any]]:
        """Get a sample of rows from a table."""
        ...


class EnhancedProfiler:
    """
    Enhanced data profiler with comprehensive analysis capabilities.

    Features:
    - Async database operations for performance
    - Statistical analysis (min, max, mean, median, stddev)
    - Distribution analysis (histograms, percentiles, outliers)
    - Pattern detection (15+ patterns)
    - String analysis (length stats)
    - Data quality scoring
    - Parallel column profiling

    Usage:
        profiler = EnhancedProfiler(db_connector)
        profile = await profiler.profile_table("public", "customers", sample_size=10000)
    """

    # Numeric data types for PostgreSQL
    NUMERIC_TYPES = frozenset(
        {
            "integer",
            "bigint",
            "smallint",
            "decimal",
            "numeric",
            "real",
            "double precision",
            "float",
            "int",
            "int2",
            "int4",
            "int8",
            "float4",
            "float8",
            "serial",
            "bigserial",
            "smallserial",
        }
    )

    # String data types for PostgreSQL
    STRING_TYPES = frozenset(
        {
            "text",
            "varchar",
            "char",
            "character varying",
            "character",
            "bpchar",
            "name",
        }
    )

    def __init__(
        self,
        db_connector: DatabaseConnector,
        sample_size: int = 10000,
        histogram_buckets: int = 20,
    ):
        """
        Initialize the profiler.

        Args:
            db_connector: Database connection for executing queries
            sample_size: Default number of rows to sample for analysis
            histogram_buckets: Number of buckets for histogram generation
        """
        self.db = db_connector
        self.default_sample_size = sample_size
        self.histogram_buckets = histogram_buckets

    async def profile_table(
        self,
        schema_name: str,
        table_name: str,
        columns: Optional[List[str]] = None,
        sample_size: Optional[int] = None,
    ) -> TableProfile:
        """
        Profile an entire table with all columns.

        Args:
            schema_name: Schema containing the table
            table_name: Name of the table to profile
            columns: Specific columns to profile (None = all)
            sample_size: Number of rows to sample (None = use default)

        Returns:
            TableProfile with complete analysis results
        """
        start_time = datetime.utcnow()
        sample_size = sample_size or self.default_sample_size

        logger.info(
            f"Profiling table {schema_name}.{table_name} with sample size {sample_size}"
        )

        try:
            # Get row count
            row_count = await self._get_row_count(schema_name, table_name)

            # Get column info
            column_info = await self._get_column_info(schema_name, table_name)

            if not column_info:
                logger.warning(
                    f"No columns found for table {schema_name}.{table_name}"
                )
                return TableProfile(
                    table_name=table_name,
                    schema_name=schema_name,
                    row_count=row_count,
                    column_count=0,
                    columns=[],
                )

            # Filter columns if specified
            if columns:
                column_info = [c for c in column_info if c["name"] in columns]

            # Profile each column in parallel for performance
            column_profiles = await asyncio.gather(
                *[
                    self.profile_column(
                        schema_name,
                        table_name,
                        col["name"],
                        col["data_type"],
                        row_count,
                        sample_size,
                    )
                    for col in column_info
                ],
                return_exceptions=True,
            )

            # Filter out exceptions and log them
            valid_profiles = []
            for i, profile in enumerate(column_profiles):
                if isinstance(profile, Exception):
                    logger.error(
                        f"Failed to profile column {column_info[i]['name']}: {profile}"
                    )
                else:
                    valid_profiles.append(profile)

            # Calculate table-level metrics
            duration_ms = int(
                (datetime.utcnow() - start_time).total_seconds() * 1000
            )

            # Calculate quality scores
            completeness = self._calculate_completeness(valid_profiles)
            uniqueness = self._calculate_uniqueness(valid_profiles)
            consistency = self._calculate_consistency(valid_profiles)
            overall_quality = (completeness + uniqueness + consistency) / 3

            # Detect potential primary key
            pk_columns = [
                p.column_name
                for p in valid_profiles
                if p.statistics.is_unique and p.statistics.null_percentage == 0
            ]

            # Detect potential foreign keys
            potential_fks = self._detect_potential_foreign_keys(valid_profiles)

            return TableProfile(
                table_name=table_name,
                schema_name=schema_name,
                row_count=row_count,
                column_count=len(valid_profiles),
                columns=valid_profiles,
                has_primary_key=len(pk_columns) > 0,
                primary_key_columns=pk_columns[:1],  # Take first unique non-null
                potential_foreign_keys=potential_fks,
                overall_quality_score=round(overall_quality, 2),
                completeness_score=round(completeness, 2),
                uniqueness_score=round(uniqueness, 2),
                consistency_score=round(consistency, 2),
                profiling_duration_ms=duration_ms,
                sample_size_used=sample_size,
            )

        except Exception as e:
            logger.error(f"Failed to profile table {schema_name}.{table_name}: {e}")
            raise

    async def profile_column(
        self,
        schema_name: str,
        table_name: str,
        column_name: str,
        data_type: str,
        total_rows: int,
        sample_size: int,
    ) -> ColumnProfile:
        """
        Profile a single column with full statistics.

        Args:
            schema_name: Schema name
            table_name: Table name
            column_name: Column to profile
            data_type: Column data type
            total_rows: Total rows in table
            sample_size: Number of rows to sample

        Returns:
            ColumnProfile with complete analysis
        """
        logger.debug(f"Profiling column {column_name} (type: {data_type})")

        try:
            # Get basic statistics
            stats = await self._get_column_statistics(
                schema_name, table_name, column_name, data_type, total_rows
            )

            # Get sample values for pattern detection
            samples = await self._get_sample_values(
                schema_name, table_name, column_name, limit=100
            )

            # Detect patterns in string data
            patterns = await self._detect_patterns(
                schema_name, table_name, column_name, samples, sample_size
            )
            stats.patterns = patterns

            # Get histogram for numeric columns
            if self._is_numeric_type(data_type) and stats.min_value is not None:
                histogram = await self._get_histogram(
                    schema_name, table_name, column_name, stats.min_value, stats.max_value
                )
                stats.histogram = histogram

            # Calculate quality score
            stats.quality_score = self._calculate_column_quality(stats)

            # Infer semantic type
            semantic_type, confidence = self._infer_semantic_type(
                column_name, data_type, stats, patterns
            )

            return ColumnProfile(
                column_name=column_name,
                table_name=table_name,
                schema_name=schema_name,
                statistics=stats,
                inferred_semantic_type=semantic_type,
                semantic_type_confidence=confidence,
                sample_values=samples[:10],  # Limit samples in profile
                sample_size=sample_size,
            )

        except Exception as e:
            logger.error(f"Error profiling column {column_name}: {e}")
            raise

    async def _get_row_count(self, schema: str, table: str) -> int:
        """Get exact or estimated row count."""
        # Try exact count first (fast for small tables)
        query = f'SELECT COUNT(*) as count FROM "{schema}"."{table}"'
        try:
            result = await self.db.execute_query(query)
            return result[0]["count"] if result else 0
        except Exception as e:
            logger.warning(f"Could not get row count for {schema}.{table}: {e}")
            return 0

    async def _get_column_info(
        self, schema: str, table: str
    ) -> List[Dict[str, Any]]:
        """Get column names and types from information_schema."""
        query = f"""
            SELECT column_name as name, data_type
            FROM information_schema.columns
            WHERE table_schema = '{schema}' AND table_name = '{table}'
            ORDER BY ordinal_position
        """
        try:
            return await self.db.execute_query(query)
        except Exception as e:
            logger.error(f"Failed to get column info for {schema}.{table}: {e}")
            return []

    async def _get_column_statistics(
        self,
        schema: str,
        table: str,
        column: str,
        data_type: str,
        total_rows: int,
    ) -> ColumnStatistics:
        """Get comprehensive statistics for a column."""
        is_numeric = self._is_numeric_type(data_type)
        is_string = self._is_string_type(data_type)

        # Build statistics query based on data type
        # Use quoted identifiers to handle special characters
        col_ref = f'"{column}"'

        # Base query with count statistics
        query = f"""
            SELECT
                COUNT(*) as total_count,
                COUNT({col_ref}) as non_null_count,
                COUNT(DISTINCT {col_ref}) as distinct_count
        """

        if is_numeric:
            query += f""",
                MIN({col_ref}) as min_value,
                MAX({col_ref}) as max_value,
                AVG({col_ref}::numeric) as mean_value,
                STDDEV({col_ref}::numeric) as stddev_value,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY {col_ref}::numeric) as median_value,
                PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY {col_ref}::numeric) as percentile_25,
                PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY {col_ref}::numeric) as percentile_75,
                PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY {col_ref}::numeric) as percentile_90,
                PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY {col_ref}::numeric) as percentile_99
            """
        elif is_string:
            query += f""",
                MIN(LENGTH({col_ref})) as min_length,
                MAX(LENGTH({col_ref})) as max_length,
                AVG(LENGTH({col_ref})) as avg_length,
                SUM(CASE WHEN {col_ref} = '' THEN 1 ELSE 0 END) as empty_count
            """

        query += f' FROM "{schema}"."{table}"'

        try:
            result = await self.db.execute_query(query)
            row = result[0] if result else {}
        except Exception as e:
            logger.warning(f"Failed to get statistics for {column}: {e}")
            row = {}

        total = row.get("total_count", total_rows) or total_rows
        non_null = row.get("non_null_count", 0) or 0
        distinct = row.get("distinct_count", 0) or 0
        null_count = total - non_null

        stats = ColumnStatistics(
            column_name=column,
            data_type=data_type,
            total_count=total,
            null_count=null_count,
            null_percentage=round((null_count / total * 100) if total > 0 else 0, 2),
            distinct_count=distinct,
            distinct_percentage=round(
                (distinct / non_null * 100) if non_null > 0 else 0, 2
            ),
            is_unique=(distinct == non_null and non_null > 0),
        )

        if is_numeric:
            stats.min_value = row.get("min_value")
            stats.max_value = row.get("max_value")
            stats.mean_value = (
                float(row["mean_value"]) if row.get("mean_value") is not None else None
            )
            stats.stddev_value = (
                float(row["stddev_value"])
                if row.get("stddev_value") is not None
                else None
            )
            stats.median_value = (
                float(row["median_value"])
                if row.get("median_value") is not None
                else None
            )
            stats.percentile_25 = (
                float(row["percentile_25"])
                if row.get("percentile_25") is not None
                else None
            )
            stats.percentile_75 = (
                float(row["percentile_75"])
                if row.get("percentile_75") is not None
                else None
            )
            stats.percentile_90 = (
                float(row["percentile_90"])
                if row.get("percentile_90") is not None
                else None
            )
            stats.percentile_99 = (
                float(row["percentile_99"])
                if row.get("percentile_99") is not None
                else None
            )

        if is_string:
            stats.min_length = row.get("min_length")
            stats.max_length = row.get("max_length")
            stats.avg_length = (
                float(row["avg_length"]) if row.get("avg_length") is not None else None
            )
            stats.empty_count = row.get("empty_count", 0)

        # Get top values (frequency distribution)
        stats.top_values = await self._get_top_values(schema, table, column, total)

        return stats

    async def _get_top_values(
        self,
        schema: str,
        table: str,
        column: str,
        total_rows: int,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get the most frequent values in a column."""
        col_ref = f'"{column}"'
        query = f"""
            SELECT {col_ref} as value, COUNT(*) as count
            FROM "{schema}"."{table}"
            WHERE {col_ref} IS NOT NULL
            GROUP BY {col_ref}
            ORDER BY count DESC
            LIMIT {limit}
        """
        try:
            result = await self.db.execute_query(query)
            return [
                {
                    "value": r["value"],
                    "count": r["count"],
                    "percentage": round(r["count"] / total_rows * 100, 2)
                    if total_rows > 0
                    else 0,
                }
                for r in result
            ]
        except Exception as e:
            logger.warning(f"Failed to get top values for {column}: {e}")
            return []

    async def _get_histogram(
        self,
        schema: str,
        table: str,
        column: str,
        min_val: Any,
        max_val: Any,
    ) -> List[Dict[str, Any]]:
        """Generate histogram buckets for numeric column."""
        if min_val is None or max_val is None or min_val == max_val:
            return []

        col_ref = f'"{column}"'
        try:
            # Use width_bucket for histogram
            query = f"""
                SELECT
                    WIDTH_BUCKET({col_ref}::numeric, {min_val}::numeric, {max_val}::numeric + 1, {self.histogram_buckets}) as bucket,
                    COUNT(*) as count,
                    MIN({col_ref}) as bucket_min,
                    MAX({col_ref}) as bucket_max
                FROM "{schema}"."{table}"
                WHERE {col_ref} IS NOT NULL
                GROUP BY bucket
                ORDER BY bucket
            """
            result = await self.db.execute_query(query)
            return [
                {
                    "bucket": r["bucket"],
                    "count": r["count"],
                    "min": r["bucket_min"],
                    "max": r["bucket_max"],
                }
                for r in result
            ]
        except Exception as e:
            logger.warning(f"Failed to generate histogram for {column}: {e}")
            return []

    async def _get_sample_values(
        self,
        schema: str,
        table: str,
        column: str,
        limit: int = 100,
    ) -> List[Any]:
        """Get random sample values from a column."""
        col_ref = f'"{column}"'
        query = f"""
            SELECT DISTINCT {col_ref} as value
            FROM "{schema}"."{table}"
            WHERE {col_ref} IS NOT NULL
            ORDER BY RANDOM()
            LIMIT {limit}
        """
        try:
            result = await self.db.execute_query(query)
            return [r["value"] for r in result]
        except Exception as e:
            logger.warning(f"Failed to get sample values for {column}: {e}")
            return []

    async def _detect_patterns(
        self,
        schema: str,
        table: str,
        column: str,
        samples: List[Any],
        sample_size: int,
    ) -> List[PatternMatch]:
        """Detect data patterns in column values."""
        if not samples:
            return []

        patterns = []
        string_samples = [str(s) for s in samples if s is not None]

        if not string_samples:
            return []

        for pattern_type, regex in PATTERNS.items():
            matches = [s for s in string_samples if regex.match(s)]
            if matches:
                match_pct = len(matches) / len(string_samples) * 100

                # Determine confidence based on match percentage
                if match_pct > 95:
                    confidence = ConfidenceLevel.HIGH
                elif match_pct > 80:
                    confidence = ConfidenceLevel.MEDIUM
                else:
                    confidence = ConfidenceLevel.LOW

                patterns.append(
                    PatternMatch(
                        pattern_type=pattern_type,
                        match_count=len(matches),
                        total_count=len(string_samples),
                        match_percentage=round(match_pct, 2),
                        confidence=confidence,
                        sample_matches=matches[:5],
                    )
                )

        # Sort by match percentage descending
        patterns.sort(key=lambda p: p.match_percentage, reverse=True)
        return patterns

    def _infer_semantic_type(
        self,
        column_name: str,
        data_type: str,
        stats: ColumnStatistics,
        patterns: List[PatternMatch],
    ) -> Tuple[Optional[str], ConfidenceLevel]:
        """Infer semantic type from name, data type, and patterns."""
        name_lower = column_name.lower()

        # Check patterns first (highest confidence)
        high_confidence_patterns = [
            p for p in patterns if p.confidence == ConfidenceLevel.HIGH
        ]
        if high_confidence_patterns:
            return (
                high_confidence_patterns[0].pattern_type.value,
                ConfidenceLevel.HIGH,
            )

        # Name-based inference mappings
        name_mappings = {
            "email": "email",
            "e_mail": "email",
            "mail": "email",
            "phone": "phone",
            "telephone": "phone",
            "mobile": "phone",
            "cell": "phone",
            "created_at": "timestamp_created",
            "updated_at": "timestamp_updated",
            "deleted_at": "timestamp_deleted",
            "modified_at": "timestamp_updated",
            "_id": "foreign_key" if not stats.is_unique else "primary_key",
            "id": "primary_key"
            if stats.is_unique and stats.null_percentage == 0
            else None,
            "price": "currency",
            "cost": "currency",
            "amount": "currency",
            "total": "currency",
            "revenue": "currency",
            "name": "name",
            "first_name": "first_name",
            "last_name": "last_name",
            "full_name": "full_name",
            "address": "address",
            "street": "street_address",
            "city": "city",
            "state": "state",
            "province": "state",
            "country": "country",
            "zip": "zip_code",
            "postal": "zip_code",
            "zipcode": "zip_code",
            "status": "status",
            "state": "status",
            "type": "category",
            "category": "category",
            "flag": "boolean",
            "is_": "boolean",
            "has_": "boolean",
            "url": "url",
            "link": "url",
            "website": "url",
            "description": "text",
            "notes": "text",
            "comment": "text",
            "lat": "latitude",
            "latitude": "latitude",
            "lng": "longitude",
            "lon": "longitude",
            "longitude": "longitude",
            "uuid": "uuid",
            "guid": "uuid",
            "ssn": "ssn",
            "social_security": "ssn",
        }

        for key, semantic_type in name_mappings.items():
            if key in name_lower and semantic_type:
                return semantic_type, ConfidenceLevel.MEDIUM

        # Check medium confidence patterns
        medium_confidence_patterns = [
            p for p in patterns if p.confidence == ConfidenceLevel.MEDIUM
        ]
        if medium_confidence_patterns:
            return (
                medium_confidence_patterns[0].pattern_type.value,
                ConfidenceLevel.MEDIUM,
            )

        return None, ConfidenceLevel.LOW

    def _calculate_column_quality(self, stats: ColumnStatistics) -> float:
        """Calculate quality score (0-100) for a column."""
        score = 100.0
        issues = []

        # Penalize high null percentage
        if stats.null_percentage > 50:
            score -= 30
            issues.append(f"High null percentage: {stats.null_percentage}%")
        elif stats.null_percentage > 20:
            score -= 15
            issues.append(f"Moderate null percentage: {stats.null_percentage}%")
        elif stats.null_percentage > 5:
            score -= 5

        # Penalize single distinct value (constant column)
        if stats.distinct_count == 1 and stats.total_count > 10:
            score -= 20
            issues.append("Single distinct value (constant column)")

        # Penalize high cardinality in small datasets
        if stats.distinct_percentage > 99 and stats.total_count < 100:
            score -= 5
            issues.append("Very high cardinality (possible PII or random data)")

        # Penalize empty strings
        if stats.empty_count and stats.empty_count > stats.total_count * 0.1:
            score -= 10
            issues.append(f"High empty string count: {stats.empty_count}")

        # Bonus for unique columns (good for keys)
        if stats.is_unique and stats.null_percentage == 0:
            score = min(100, score + 5)

        stats.quality_issues = issues
        return max(0, round(score, 2))

    def _calculate_completeness(self, profiles: List[ColumnProfile]) -> float:
        """Calculate overall completeness score (non-null percentage)."""
        if not profiles:
            return 100.0
        total_non_null_pct = sum(
            100 - p.statistics.null_percentage for p in profiles
        )
        return total_non_null_pct / len(profiles)

    def _calculate_uniqueness(self, profiles: List[ColumnProfile]) -> float:
        """Calculate overall uniqueness score."""
        if not profiles:
            return 100.0
        # Average distinct percentage across columns
        total_distinct_pct = sum(p.statistics.distinct_percentage for p in profiles)
        return total_distinct_pct / len(profiles)

    def _calculate_consistency(self, profiles: List[ColumnProfile]) -> float:
        """Calculate consistency score based on pattern detection."""
        if not profiles:
            return 100.0

        consistency_scores = []
        for profile in profiles:
            if profile.statistics.patterns:
                # If patterns detected, highest match percentage indicates consistency
                best_match = max(
                    p.match_percentage for p in profile.statistics.patterns
                )
                consistency_scores.append(best_match)
            else:
                # No patterns to check, assume consistent
                consistency_scores.append(100.0)

        return sum(consistency_scores) / len(consistency_scores)

    def _detect_potential_foreign_keys(
        self, profiles: List[ColumnProfile]
    ) -> List[Dict[str, str]]:
        """Detect columns that might be foreign keys based on naming conventions."""
        potential_fks = []

        for profile in profiles:
            name_lower = profile.column_name.lower()

            # Common foreign key naming patterns
            if name_lower.endswith("_id") and not profile.statistics.is_unique:
                # Extract referenced table name
                ref_table = name_lower[:-3]  # Remove _id suffix
                if ref_table:
                    potential_fks.append(
                        {
                            "column": profile.column_name,
                            "potential_reference": ref_table,
                            "confidence": "medium",
                        }
                    )

            # Check for uuid patterns that might be foreign keys
            if (
                profile.inferred_semantic_type == "uuid"
                and not profile.statistics.is_unique
            ):
                potential_fks.append(
                    {
                        "column": profile.column_name,
                        "potential_reference": "unknown",
                        "confidence": "low",
                    }
                )

        return potential_fks

    def _is_numeric_type(self, data_type: str) -> bool:
        """Check if data type is numeric."""
        return data_type.lower() in self.NUMERIC_TYPES

    def _is_string_type(self, data_type: str) -> bool:
        """Check if data type is string/text."""
        return data_type.lower() in self.STRING_TYPES
