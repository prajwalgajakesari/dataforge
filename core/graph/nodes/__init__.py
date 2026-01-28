"""
Modular workflow nodes for the Data Modeling Agent.

This package provides modular, reusable workflow nodes for the LangGraph-based
data modeling workflow. Each module focuses on a specific phase of the modeling
process:

- discovery: Schema and table discovery from data sources
- profiling: Data profiling and statistical analysis
- analysis: Dependency detection and relationship inference
- design: Model design generation using LLM
- generation: Code generation (dbt, SQL, SQLAlchemy)

Each node function accepts and returns a ModelingState, enabling composable
workflow construction with LangGraph.

Example Usage:
    >>> from core.graph.nodes import discover_schemas, discover_tables, profile_tables
    >>> from core.graph.nodes import analyze_dependencies, create_design, generate_output
    >>>
    >>> # Build workflow with nodes
    >>> state = await discover_schemas(state, mcp_client)
    >>> state = await discover_tables(state, mcp_client)
    >>> state = await profile_tables(state, profiler)
    >>> state = await analyze_dependencies(state, fd_detector)
    >>> state = await create_design(state, llm_client)
    >>> state = await generate_output(state)
"""

from core.graph.nodes.discovery import (
    discover_schemas,
    discover_tables,
    select_schema,
    get_table_summary,
    filter_tables_by_pattern,
)
from core.graph.nodes.profiling import (
    profile_tables,
    get_profiling_summary,
    identify_quality_issues,
)
from core.graph.nodes.analysis import (
    analyze_dependencies,
    infer_relationships,
    analyze_keys,
    enrich_with_type_inference,
    get_analysis_summary,
)
from core.graph.nodes.design import (
    create_design,
    validate_design,
    get_design_summary,
)
from core.graph.nodes.generation import (
    generate_output,
    validate_output,
    get_generation_summary,
    get_file_by_category,
    write_files_to_disk,
)

__all__ = [
    # Discovery nodes
    "discover_schemas",
    "discover_tables",
    "select_schema",
    "get_table_summary",
    "filter_tables_by_pattern",
    # Profiling nodes
    "profile_tables",
    "get_profiling_summary",
    "identify_quality_issues",
    # Analysis nodes
    "analyze_dependencies",
    "infer_relationships",
    "analyze_keys",
    "enrich_with_type_inference",
    "get_analysis_summary",
    # Design nodes
    "create_design",
    "validate_design",
    "get_design_summary",
    # Generation nodes
    "generate_output",
    "validate_output",
    "get_generation_summary",
    "get_file_by_category",
    "write_files_to_disk",
]
