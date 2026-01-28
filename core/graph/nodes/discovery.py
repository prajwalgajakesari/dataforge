"""
Schema and table discovery nodes for the data modeling workflow.

This module provides nodes for discovering database schemas and tables
from various data sources using MCP (Model Context Protocol) servers.

Nodes:
    - discover_schemas: Discover available schemas from the database
    - discover_tables: Discover tables within a selected schema
    - select_schema: Select the most relevant schema using LLM
"""

from typing import Any, Dict, List, Optional, TYPE_CHECKING

from core.utils.logger import get_logger

if TYPE_CHECKING:
    from core.graph.modeling_graph import ModelingState
    from core.mcp.servers.postgres_mcp import PostgresMCP
    from core.utils.llm_client import LLMClient

logger = get_logger(__name__)


async def discover_schemas(
    state: "ModelingState",
    mcp_client: "PostgresMCP",
) -> "ModelingState":
    """
    Discover available schemas from the database.

    This node queries the database to find all available schemas,
    excluding system schemas by default. It populates the
    available_schemas field in the state.

    Args:
        state: Current modeling workflow state
        mcp_client: PostgreSQL MCP client for database operations

    Returns:
        Updated ModelingState with discovered schemas

    State Updates:
        - available_schemas: List of schema info dicts (name, table_count)
        - current_step: Set to "discover_schemas"
        - progress: Set to 0.1
        - errors: Appended if discovery fails
        - status: Set to "failed" if discovery fails
    """
    logger.info("Discovering schemas...")

    try:
        schemas = await mcp_client.discover_schemas(exclude_system=True)

        state["available_schemas"] = [
            {
                "name": schema.schema_name,
                "table_count": len(schema.tables),
            }
            for schema in schemas
        ]

        state["current_step"] = "discover_schemas"
        state["progress"] = 0.1

        logger.info(f"Discovered {len(schemas)} schemas")

    except Exception as e:
        logger.error(f"Schema discovery failed: {e}")
        state["errors"].append(f"Schema discovery failed: {e}")
        state["status"] = "failed"

    return state


async def select_schema(
    state: "ModelingState",
    llm_client: "LLMClient",
) -> "ModelingState":
    """
    Select the most relevant schema using LLM analysis.

    This node uses an LLM to analyze the user's requirements against
    the available schemas and select the most appropriate one for
    the modeling task.

    Args:
        state: Current modeling workflow state with available_schemas populated
        llm_client: LLM client for AI-assisted selection

    Returns:
        Updated ModelingState with selected schema

    State Updates:
        - selected_schema: Name of the selected schema
        - current_step: Set to "select_schema"
        - progress: Set to 0.2
        - errors: Appended if selection fails
        - status: Set to "failed" if selection fails
    """
    logger.info("Selecting relevant schema...")

    try:
        # Build prompt for schema selection
        schema_list = "\n".join(
            f"- {s['name']} ({s['table_count']} tables)"
            for s in state["available_schemas"]
        )

        prompt = f"""Given the user's requirements and available schemas, select the most relevant schema to use.

User Requirements:
{state['requirements']}

Available Schemas:
{schema_list}

Respond with ONLY the schema name, nothing else.
"""

        response = await llm_client.generate(
            prompt=prompt,
            system="You are a data modeling expert. Select the most relevant schema based on the requirements.",
            temperature=0.0,
        )

        selected = response.content.strip()

        # Validate selection against available schemas
        available_names = [s["name"] for s in state["available_schemas"]]
        if selected not in available_names:
            logger.warning(
                f"LLM selected invalid schema '{selected}', defaulting to first available"
            )
            selected = available_names[0] if available_names else "public"

        state["selected_schema"] = selected
        state["current_step"] = "select_schema"
        state["progress"] = 0.2

        logger.info(f"Selected schema: {selected}")

    except Exception as e:
        logger.error(f"Schema selection failed: {e}")
        state["errors"].append(f"Schema selection failed: {e}")
        state["status"] = "failed"

    return state


async def discover_tables(
    state: "ModelingState",
    mcp_client: "PostgresMCP",
) -> "ModelingState":
    """
    Discover tables within the selected schema.

    This node queries the database to find all tables in the selected
    schema, including their columns, data types, and key information.

    Args:
        state: Current modeling workflow state with selected_schema populated
        mcp_client: PostgreSQL MCP client for database operations

    Returns:
        Updated ModelingState with discovered tables

    State Updates:
        - discovered_tables: List of table info dicts with columns
        - current_step: Set to "discover_tables"
        - progress: Set to 0.3
        - errors: Appended if discovery fails
        - status: Set to "failed" if discovery fails
    """
    schema_name = state.get("selected_schema", "public")
    logger.info(f"Discovering tables in schema: {schema_name}...")

    try:
        tables = await mcp_client.discover_tables(schema_name)

        state["discovered_tables"] = [
            {
                "schema": table.table_schema,
                "name": table.table_name,
                "type": table.table_type,
                "row_count": table.row_count,
                "columns": [
                    {
                        "name": col.column_name,
                        "data_type": col.data_type,
                        "is_nullable": col.is_nullable,
                        "is_primary_key": col.is_primary_key,
                        "is_foreign_key": col.is_foreign_key,
                        "foreign_key_table": col.foreign_key_table,
                        "foreign_key_column": col.foreign_key_column,
                    }
                    for col in table.columns
                ],
            }
            for table in tables
        ]

        state["current_step"] = "discover_tables"
        state["progress"] = 0.3

        logger.info(f"Discovered {len(tables)} tables")

    except Exception as e:
        logger.error(f"Table discovery failed: {e}")
        state["errors"].append(f"Table discovery failed: {e}")
        state["status"] = "failed"

    return state


def get_table_summary(tables: List[Dict[str, Any]]) -> str:
    """
    Generate a summary of discovered tables for logging or display.

    Args:
        tables: List of table dictionaries from discovered_tables

    Returns:
        Formatted string summarizing the tables
    """
    if not tables:
        return "No tables discovered"

    lines = []
    for table in tables[:10]:  # Limit to first 10 for summary
        col_count = len(table.get("columns", []))
        row_count = table.get("row_count", "unknown")
        lines.append(f"  - {table['name']}: {col_count} columns, {row_count} rows")

    if len(tables) > 10:
        lines.append(f"  ... and {len(tables) - 10} more tables")

    return "\n".join(lines)


def filter_tables_by_pattern(
    tables: List[Dict[str, Any]],
    include_patterns: Optional[List[str]] = None,
    exclude_patterns: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Filter tables by name patterns.

    Args:
        tables: List of table dictionaries
        include_patterns: Patterns to include (if any match)
        exclude_patterns: Patterns to exclude (if any match)

    Returns:
        Filtered list of tables
    """
    import re

    result = tables

    if include_patterns:
        result = [
            t for t in result
            if any(re.search(p, t["name"], re.IGNORECASE) for p in include_patterns)
        ]

    if exclude_patterns:
        result = [
            t for t in result
            if not any(re.search(p, t["name"], re.IGNORECASE) for p in exclude_patterns)
        ]

    return result
