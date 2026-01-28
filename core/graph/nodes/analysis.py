"""
Analysis nodes for the data modeling workflow.

This module provides nodes for analyzing database structures,
detecting functional dependencies, finding candidate keys,
and inferring relationships between tables.

Nodes:
    - analyze_dependencies: Detect functional dependencies in tables
    - infer_relationships: Infer implicit relationships between tables
    - analyze_keys: Find candidate keys and recommend primary keys
"""

from typing import Any, Dict, List, Optional, TYPE_CHECKING

from core.utils.logger import get_logger

if TYPE_CHECKING:
    from core.graph.modeling_graph import ModelingState
    from core.analysis import (
        FunctionalDependencyDetector,
        CandidateKeyFinder,
        RelationshipInferrer,
        TypeInferenceEngine,
    )
    from core.analysis.fd_detector import DatabaseConnector

logger = get_logger(__name__)


async def analyze_dependencies(
    state: "ModelingState",
    fd_detector: "FunctionalDependencyDetector",
    max_tables: int = 5,
) -> "ModelingState":
    """
    Analyze functional dependencies in discovered tables.

    This node uses the FunctionalDependencyDetector to discover
    functional dependencies, which inform normalization decisions
    and help identify candidate keys.

    Args:
        state: Current modeling workflow state with discovered_tables populated
        fd_detector: FunctionalDependencyDetector instance
        max_tables: Maximum number of tables to analyze (default: 5)

    Returns:
        Updated ModelingState with dependency analysis results

    State Updates:
        - functional_dependencies: Dict mapping table names to FD lists
        - normalization_analysis: Dict with normalization level info per table
        - current_step: Set to "analyze_dependencies"
        - progress: Updated based on current progress
        - warnings: Appended for tables that fail analysis
    """
    logger.info("Analyzing functional dependencies...")

    try:
        fd_results: Dict[str, List[Dict[str, Any]]] = {}
        normalization_results: Dict[str, Dict[str, Any]] = {}

        tables_to_analyze = state.get("discovered_tables", [])[:max_tables]

        for table in tables_to_analyze:
            table_name = table["name"]
            schema_name = table.get("schema", "public")

            try:
                logger.debug(f"Analyzing FDs for: {schema_name}.{table_name}")

                # Discover functional dependencies
                fds = await fd_detector.discover_fds(
                    schema_name=schema_name,
                    table_name=table_name,
                )

                # Convert FDs to serializable dicts
                fd_results[table_name] = [
                    {
                        "determinant": fd.determinant,
                        "dependent": fd.dependent,
                        "confidence": fd.confidence,
                        "support": fd.support,
                        "violations": fd.violations,
                        "is_trivial": fd.is_trivial,
                        "is_partial": fd.is_partial,
                        "is_transitive": fd.is_transitive,
                    }
                    for fd in fds
                ]

                # Analyze normalization level
                norm_analysis = await fd_detector.analyze_normalization(
                    schema_name=schema_name,
                    table_name=table_name,
                    fds=fds,
                )
                normalization_results[table_name] = norm_analysis

                logger.debug(
                    f"Found {len(fds)} FDs in {table_name}, "
                    f"current form: {norm_analysis.get('current_form', 'unknown')}"
                )

            except Exception as e:
                logger.warning(f"Could not analyze FDs for {table_name}: {e}")
                state["warnings"].append(f"FD analysis failed for {table_name}: {e}")

        # Store results in state
        state["functional_dependencies"] = fd_results
        state["normalization_analysis"] = normalization_results
        state["current_step"] = "analyze_dependencies"

        # Update progress (between 0.5 and 0.6)
        current_progress = state.get("progress", 0.5)
        state["progress"] = max(current_progress, 0.55)

        logger.info(f"Analyzed FDs for {len(fd_results)} tables")

    except Exception as e:
        logger.error(f"Dependency analysis failed: {e}")
        state["errors"].append(f"Dependency analysis failed: {e}")

    return state


async def infer_relationships(
    state: "ModelingState",
    relationship_inferrer: "RelationshipInferrer",
) -> "ModelingState":
    """
    Infer implicit relationships between tables.

    This node uses the RelationshipInferrer to detect foreign key
    relationships based on naming conventions, data overlap, and
    cardinality analysis.

    Args:
        state: Current modeling workflow state with discovered_tables populated
        relationship_inferrer: RelationshipInferrer instance

    Returns:
        Updated ModelingState with inferred relationships

    State Updates:
        - inferred_relationships: List of relationship dictionaries
        - current_step: Set to "infer_relationships"
        - progress: Updated based on current progress
        - warnings: Appended for any inference issues
    """
    logger.info("Inferring relationships...")

    try:
        schema_name = state.get("selected_schema", "public")
        table_names = [t["name"] for t in state.get("discovered_tables", [])]

        if not table_names:
            logger.warning("No tables available for relationship inference")
            state["inferred_relationships"] = []
            state["current_step"] = "infer_relationships"
            return state

        # Infer all relationships (implicit and explicit)
        relationships = await relationship_inferrer.infer_all_relationships(
            schema_name=schema_name,
            tables=table_names,
            include_explicit=True,
        )

        # Convert to serializable dicts
        state["inferred_relationships"] = [
            {
                "from_table": rel.from_table,
                "from_column": rel.from_column,
                "to_table": rel.to_table,
                "to_column": rel.to_column,
                "cardinality": rel.cardinality,
                "confidence": rel.confidence.value,
                "is_nullable": rel.is_nullable,
                "null_percentage": rel.null_percentage,
                "value_overlap_percentage": rel.value_overlap_percentage,
                "is_explicit_fk": rel.is_explicit_fk,
            }
            for rel in relationships
        ]

        state["current_step"] = "infer_relationships"

        # Update progress (between 0.55 and 0.65)
        current_progress = state.get("progress", 0.55)
        state["progress"] = max(current_progress, 0.6)

        logger.info(
            f"Inferred {len(relationships)} relationships "
            f"({sum(1 for r in relationships if r.is_explicit_fk)} explicit, "
            f"{sum(1 for r in relationships if not r.is_explicit_fk)} implicit)"
        )

    except Exception as e:
        logger.error(f"Relationship inference failed: {e}")
        state["errors"].append(f"Relationship inference failed: {e}")

    return state


async def analyze_keys(
    state: "ModelingState",
    key_finder: "CandidateKeyFinder",
    max_tables: int = 10,
) -> "ModelingState":
    """
    Analyze candidate keys for discovered tables.

    This node uses the CandidateKeyFinder to identify candidate keys
    and provide primary key recommendations for each table.

    Args:
        state: Current modeling workflow state with discovered_tables populated
        key_finder: CandidateKeyFinder instance
        max_tables: Maximum number of tables to analyze (default: 10)

    Returns:
        Updated ModelingState with key analysis results

    State Updates:
        - key_analysis: Dict mapping table names to key analysis results
        - current_step: Set to "analyze_keys"
        - progress: Updated based on current progress
        - warnings: Appended for tables that fail key analysis
    """
    logger.info("Analyzing candidate keys...")

    try:
        key_results: Dict[str, Dict[str, Any]] = {}

        tables_to_analyze = state.get("discovered_tables", [])[:max_tables]

        for table in tables_to_analyze:
            table_name = table["name"]
            schema_name = table.get("schema", "public")

            try:
                logger.debug(f"Analyzing keys for: {schema_name}.{table_name}")

                analysis = await key_finder.analyze_keys(
                    schema_name=schema_name,
                    table_name=table_name,
                )

                key_results[table_name] = {
                    "primary_key": analysis.primary_key,
                    "unique_constraints": analysis.unique_constraints,
                    "candidate_keys": [
                        {
                            "columns": ck.columns,
                            "is_minimal": ck.is_minimal,
                            "uniqueness": ck.uniqueness,
                            "null_percentage": ck.null_percentage,
                            "recommended_as_primary": ck.recommended_as_primary,
                            "recommendation_reason": ck.recommendation_reason,
                        }
                        for ck in analysis.candidate_keys
                    ],
                    "recommended_primary_key": analysis.recommended_primary_key,
                    "key_recommendation_reason": analysis.key_recommendation_reason,
                }

                logger.debug(
                    f"Found {len(analysis.candidate_keys)} candidate keys for {table_name}"
                )

            except Exception as e:
                logger.warning(f"Could not analyze keys for {table_name}: {e}")
                state["warnings"].append(f"Key analysis failed for {table_name}: {e}")

        state["key_analysis"] = key_results
        state["current_step"] = "analyze_keys"

        # Update progress (between 0.6 and 0.65)
        current_progress = state.get("progress", 0.6)
        state["progress"] = max(current_progress, 0.65)

        logger.info(f"Analyzed keys for {len(key_results)} tables")

    except Exception as e:
        logger.error(f"Key analysis failed: {e}")
        state["errors"].append(f"Key analysis failed: {e}")

    return state


def enrich_with_type_inference(
    state: "ModelingState",
    type_engine: "TypeInferenceEngine",
) -> "ModelingState":
    """
    Enrich column information with semantic type inference.

    This is a synchronous helper that adds inferred semantic types
    to the discovered tables based on column names, data types,
    and profiling patterns.

    Args:
        state: Current modeling workflow state
        type_engine: TypeInferenceEngine instance

    Returns:
        Updated ModelingState with enriched column type information

    State Updates:
        - discovered_tables: Columns enriched with semantic_type info
    """
    logger.info("Enriching columns with semantic type inference...")

    profiles = state.get("data_profiles", {})

    for table in state.get("discovered_tables", []):
        table_name = table["name"]
        table_profile = profiles.get(table_name, {})
        column_profiles = {
            cp["column_name"]: cp for cp in table_profile.get("columns", [])
        }

        for col in table.get("columns", []):
            col_name = col["name"]
            col_profile = column_profiles.get(col_name, {})

            # Get statistics from profile
            statistics = col_profile.get("statistics", {})

            # Build stats object for type inference
            # (simplified - in production would use actual ColumnStatistics)
            patterns = col_profile.get("patterns", [])

            # Infer type
            result = type_engine.infer_type(
                column_name=col_name,
                data_type=col.get("data_type", ""),
                pattern_matches=None,  # Would convert patterns to PatternMatch objects
                sample_values=col_profile.get("sample_values", []),
            )

            # Add inferred info to column
            col["semantic_type"] = result.inferred_type.value
            col["semantic_confidence"] = result.confidence.value
            col["is_pii"] = result.is_pii
            col["is_sensitive"] = result.is_sensitive
            col["semantic_category"] = result.category.value

    logger.info("Enriched columns with semantic types")
    return state


def get_analysis_summary(state: "ModelingState") -> Dict[str, Any]:
    """
    Generate a summary of all analysis results.

    Args:
        state: ModelingState with analysis results

    Returns:
        Summary dictionary with key metrics
    """
    fd_results = state.get("functional_dependencies", {})
    norm_results = state.get("normalization_analysis", {})
    rel_results = state.get("inferred_relationships", [])
    key_results = state.get("key_analysis", {})

    # Count FDs
    total_fds = sum(len(fds) for fds in fd_results.values())
    partial_fds = sum(
        sum(1 for fd in fds if fd.get("is_partial", False))
        for fds in fd_results.values()
    )
    transitive_fds = sum(
        sum(1 for fd in fds if fd.get("is_transitive", False))
        for fds in fd_results.values()
    )

    # Normalization summary
    norm_forms = {}
    for table, analysis in norm_results.items():
        form = analysis.get("current_form", "unknown")
        norm_forms[form] = norm_forms.get(form, 0) + 1

    # Relationship summary
    explicit_rels = sum(1 for r in rel_results if r.get("is_explicit_fk", False))
    implicit_rels = len(rel_results) - explicit_rels

    # Key summary
    tables_with_pk = sum(
        1 for k in key_results.values() if k.get("primary_key")
    )
    tables_with_candidates = sum(
        1 for k in key_results.values() if k.get("candidate_keys")
    )

    return {
        "functional_dependencies": {
            "total": total_fds,
            "partial": partial_fds,
            "transitive": transitive_fds,
            "tables_analyzed": len(fd_results),
        },
        "normalization": {
            "form_distribution": norm_forms,
        },
        "relationships": {
            "total": len(rel_results),
            "explicit": explicit_rels,
            "implicit": implicit_rels,
        },
        "keys": {
            "tables_analyzed": len(key_results),
            "tables_with_pk": tables_with_pk,
            "tables_with_candidates": tables_with_candidates,
        },
    }
