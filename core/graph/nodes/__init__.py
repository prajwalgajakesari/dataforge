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
"""

from core.graph.nodes.discovery import (
    discover_schemas,
    discover_tables,
    select_schema,
)
from core.graph.nodes.profiling import (
    profile_tables,
)
from core.graph.nodes.analysis import (
    analyze_dependencies,
    infer_relationships,
    analyze_keys,
)
from core.graph.nodes.design import (
    create_design,
    validate_design,
)
from core.graph.nodes.generation import (
    generate_output,
    validate_output,
)

__all__ = [
    # Discovery nodes
    "discover_schemas",
    "discover_tables",
    "select_schema",
    # Profiling nodes
    "profile_tables",
    # Analysis nodes
    "analyze_dependencies",
    "infer_relationships",
    "analyze_keys",
    # Design nodes
    "create_design",
    "validate_design",
    # Generation nodes
    "generate_output",
    "validate_output",
]
