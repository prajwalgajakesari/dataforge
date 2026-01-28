"""
Data profiling nodes for the data modeling workflow.

This module provides nodes for profiling discovered tables,
collecting statistics, detecting patterns, and calculating
data quality scores.

Nodes:
    - profile_tables: Profile all discovered tables with enhanced analysis
"""

from typing import Any, Dict, List, Optional, TYPE_CHECKING

from core.utils.logger import get_logger

if TYPE_CHECKING:
    from core.graph.modeling_graph import ModelingState
    from core.analysis import EnhancedProfiler, DatabaseConnector

logger = get_logger(__name__)


async def profile_tables(
    state: "ModelingState",
    profiler: "EnhancedProfiler",
    max_tables: int = 10,
    sample_size: int = 10000,
) -> "ModelingState":
    """
    Profile discovered tables with comprehensive data analysis.

    This node uses the EnhancedProfiler to collect detailed statistics,
    detect patterns, and calculate quality scores for each table.

    Args:
        state: Current modeling workflow state with discovered_tables populated
        profiler: EnhancedProfiler instance configured with database connection
        max_tables: Maximum number of tables to profile (default: 10)
        sample_size: Number of rows to sample per table (default: 10000)

    Returns:
        Updated ModelingState with profiling results

    State Updates:
        - data_profiles: Dict mapping table names to profile data
        - current_step: Set to "profile_data"
        - progress: Set to 0.5
        - warnings: Appended for tables that fail profiling
        - errors: Appended if all profiling fails
        - status: Set to "failed" if all profiling fails

    Profile Data Structure:
        Each table profile contains:
        - row_count: Total rows in table
        - column_count: Number of columns
        - columns: List of column profiles with statistics
        - quality_scores: Overall quality metrics
        - potential_keys: Detected candidate keys
        - potential_fks: Detected foreign key candidates
    """
    logger.info("Profiling data...")

    try:
        profiles: Dict[str, Dict[str, Any]] = {}

        # Limit tables to profile
        tables_to_profile = state.get("discovered_tables", [])[:max_tables]

        if not tables_to_profile:
            logger.warning("No tables to profile")
            state["data_profiles"] = {}
            state["current_step"] = "profile_data"
            state["progress"] = 0.5
            return state

        for table in tables_to_profile:
            table_name = table["name"]
            schema_name = table.get("schema", "public")

            try:
                logger.debug(f"Profiling table: {schema_name}.{table_name}")

                table_profile = await profiler.profile_table(
                    schema_name=schema_name,
                    table_name=table_name,
                    sample_size=sample_size,
                )

                # Convert profile to serializable dict
                profiles[table_name] = _profile_to_dict(table_profile)

                logger.debug(
                    f"Profiled {table_name}: {table_profile.column_count} columns, "
                    f"quality score: {table_profile.overall_quality_score}"
                )

            except Exception as e:
                logger.warning(f"Could not profile table {table_name}: {e}")
                state["warnings"].append(f"Could not profile {table_name}: {e}")

        state["data_profiles"] = profiles
        state["current_step"] = "profile_data"
        state["progress"] = 0.5

        logger.info(f"Profiled {len(profiles)} tables")

    except Exception as e:
        logger.error(f"Data profiling failed: {e}")
        state["errors"].append(f"Data profiling failed: {e}")
        state["status"] = "failed"

    return state


def _profile_to_dict(table_profile: Any) -> Dict[str, Any]:
    """
    Convert a TableProfile object to a serializable dictionary.

    Args:
        table_profile: TableProfile object from EnhancedProfiler

    Returns:
        Dictionary representation of the profile
    """
    return {
        "table_name": table_profile.table_name,
        "schema_name": table_profile.schema_name,
        "row_count": table_profile.row_count,
        "column_count": table_profile.column_count,
        "has_primary_key": table_profile.has_primary_key,
        "primary_key_columns": table_profile.primary_key_columns,
        "potential_foreign_keys": table_profile.potential_foreign_keys,
        "quality_scores": {
            "overall": table_profile.overall_quality_score,
            "completeness": table_profile.completeness_score,
            "uniqueness": table_profile.uniqueness_score,
            "consistency": table_profile.consistency_score,
        },
        "profiling_duration_ms": table_profile.profiling_duration_ms,
        "sample_size_used": table_profile.sample_size_used,
        "columns": [
            _column_profile_to_dict(col) for col in table_profile.columns
        ],
    }


def _column_profile_to_dict(column_profile: Any) -> Dict[str, Any]:
    """
    Convert a ColumnProfile object to a serializable dictionary.

    Args:
        column_profile: ColumnProfile object

    Returns:
        Dictionary representation of the column profile
    """
    stats = column_profile.statistics

    result = {
        "column_name": column_profile.column_name,
        "inferred_semantic_type": column_profile.inferred_semantic_type,
        "semantic_type_confidence": (
            column_profile.semantic_type_confidence.value
            if column_profile.semantic_type_confidence
            else None
        ),
        "sample_values": column_profile.sample_values[:5],  # Limit samples
        "statistics": {
            "data_type": stats.data_type,
            "total_count": stats.total_count,
            "null_count": stats.null_count,
            "null_percentage": stats.null_percentage,
            "distinct_count": stats.distinct_count,
            "distinct_percentage": stats.distinct_percentage,
            "is_unique": stats.is_unique,
            "quality_score": stats.quality_score,
        },
    }

    # Add numeric stats if available
    if stats.min_value is not None:
        result["statistics"]["min_value"] = stats.min_value
        result["statistics"]["max_value"] = stats.max_value
        result["statistics"]["mean_value"] = stats.mean_value
        result["statistics"]["stddev_value"] = stats.stddev_value
        result["statistics"]["median_value"] = stats.median_value

    # Add string stats if available
    if stats.min_length is not None:
        result["statistics"]["min_length"] = stats.min_length
        result["statistics"]["max_length"] = stats.max_length
        result["statistics"]["avg_length"] = stats.avg_length
        result["statistics"]["empty_count"] = stats.empty_count

    # Add detected patterns
    if stats.patterns:
        result["patterns"] = [
            {
                "type": p.pattern_type.value,
                "match_count": p.match_count,
                "match_percentage": p.match_percentage,
                "confidence": p.confidence.value,
            }
            for p in stats.patterns[:3]  # Limit to top 3 patterns
        ]

    # Add top values
    if stats.top_values:
        result["top_values"] = stats.top_values[:5]  # Limit to top 5

    return result


def get_profiling_summary(profiles: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate a summary of profiling results.

    Args:
        profiles: Dict mapping table names to profile data

    Returns:
        Summary statistics across all profiled tables
    """
    if not profiles:
        return {
            "tables_profiled": 0,
            "total_columns": 0,
            "average_quality": 0,
        }

    total_columns = sum(p["column_count"] for p in profiles.values())
    quality_scores = [
        p["quality_scores"]["overall"]
        for p in profiles.values()
        if p["quality_scores"]["overall"] is not None
    ]

    avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0

    return {
        "tables_profiled": len(profiles),
        "total_columns": total_columns,
        "average_quality": round(avg_quality, 2),
        "tables_with_pk": sum(1 for p in profiles.values() if p["has_primary_key"]),
        "quality_breakdown": {
            "high_quality": sum(1 for q in quality_scores if q >= 80),
            "medium_quality": sum(1 for q in quality_scores if 50 <= q < 80),
            "low_quality": sum(1 for q in quality_scores if q < 50),
        },
    }


def identify_quality_issues(
    profiles: Dict[str, Dict[str, Any]],
    quality_threshold: float = 70.0,
) -> List[Dict[str, Any]]:
    """
    Identify tables and columns with quality issues.

    Args:
        profiles: Dict mapping table names to profile data
        quality_threshold: Minimum acceptable quality score (0-100)

    Returns:
        List of quality issues with table/column details
    """
    issues = []

    for table_name, profile in profiles.items():
        table_quality = profile["quality_scores"]["overall"]

        # Check table-level quality
        if table_quality and table_quality < quality_threshold:
            issues.append({
                "table": table_name,
                "column": None,
                "issue": "low_table_quality",
                "score": table_quality,
                "message": f"Table quality score {table_quality:.1f} below threshold {quality_threshold}",
            })

        # Check missing primary key
        if not profile["has_primary_key"]:
            issues.append({
                "table": table_name,
                "column": None,
                "issue": "missing_primary_key",
                "score": None,
                "message": "Table has no identifiable primary key",
            })

        # Check column-level issues
        for col in profile.get("columns", []):
            stats = col.get("statistics", {})

            # High null percentage
            null_pct = stats.get("null_percentage", 0)
            if null_pct > 50:
                issues.append({
                    "table": table_name,
                    "column": col["column_name"],
                    "issue": "high_null_percentage",
                    "score": null_pct,
                    "message": f"Column has {null_pct:.1f}% null values",
                })

            # Low column quality
            col_quality = stats.get("quality_score", 100)
            if col_quality < quality_threshold:
                issues.append({
                    "table": table_name,
                    "column": col["column_name"],
                    "issue": "low_column_quality",
                    "score": col_quality,
                    "message": f"Column quality score {col_quality:.1f} below threshold",
                })

    return issues
