"""
Schema discovery endpoints.

This module provides endpoints for discovering database schemas
and tables within a modeling session.
"""

from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status

from api.models import (
    DiscoverRequest,
    DiscoveryResponse,
    ErrorResponse,
    SchemaInfo,
    SessionStatus,
    TableInfo,
    TablesResponse,
)
from api.dependencies import get_mcp_registry, get_session_store, SessionData, SessionStore
from core.mcp.registry import MCPRegistry
from core.mcp.servers.postgres_mcp import PostgresMCP
from core.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


async def _get_mcp_client(
    session: SessionData,
    mcp_registry: MCPRegistry,
) -> PostgresMCP:
    """
    Get or create an MCP client for the session's data source.

    Args:
        session: The session data
        mcp_registry: The MCP registry

    Returns:
        PostgresMCP client instance

    Raises:
        HTTPException: If data source is not found or unsupported
    """
    data_source = session.state.get("data_source", "")
    server_config = mcp_registry.servers.get(data_source)

    if not server_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data source '{data_source}' not found",
        )

    if server_config.type != "database":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Data source '{data_source}' is not a database",
        )

    # Create MCP client (currently only PostgresMCP supported)
    return PostgresMCP(config=server_config)


@router.post(
    "/sessions/{session_id}/discover",
    response_model=DiscoveryResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Session not found"},
        503: {"model": ErrorResponse, "description": "MCP registry not available"},
    },
    summary="Run schema discovery",
    description="Discover available database schemas and select the most relevant one.",
    response_description="Discovered schemas and selected schema",
)
async def discover_schemas(
    session_id: str,
    request: DiscoverRequest = DiscoverRequest(),
    mcp_registry: MCPRegistry = Depends(get_mcp_registry),
    session_store: SessionStore = Depends(get_session_store),
) -> DiscoveryResponse:
    """
    Run schema discovery for a session.

    Discovers available schemas from the connected database and
    uses an LLM to select the most relevant schema based on
    the session's requirements.

    Args:
        session_id: The session identifier
        request: Discovery options (filters, exclude system schemas)

    Returns:
        Discovered schemas and the selected schema

    Raises:
        HTTPException: 404 if session not found, 503 if registry unavailable
    """
    if not mcp_registry:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MCP registry not initialized",
        )

    session = await session_store.get(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found",
        )

    # Update session status
    session.state["status"] = SessionStatus.IN_PROGRESS.value
    session.state["current_step"] = "discovering_schemas"
    session.updated_at = datetime.utcnow()

    try:
        # Get MCP client
        mcp_client = await _get_mcp_client(session, mcp_registry)

        # Discover schemas
        schemas = await mcp_client.discover_schemas(
            exclude_system=request.exclude_system
        )

        # Convert to schema info
        schema_list: List[SchemaInfo] = []
        for schema in schemas:
            # Apply filter if provided
            if request.schema_filter:
                import re
                if not re.match(request.schema_filter, schema.schema_name):
                    continue

            schema_list.append(
                SchemaInfo(
                    name=schema.schema_name,
                    table_count=len(schema.tables),
                )
            )

        # Update session state
        session.state["available_schemas"] = [
            {"name": s.name, "table_count": s.table_count}
            for s in schema_list
        ]

        # Select first schema by default (LLM selection can be added later)
        selected_schema = schema_list[0].name if schema_list else None
        session.state["selected_schema"] = selected_schema or ""

        session.state["current_step"] = "schemas_discovered"
        session.state["progress"] = 0.2
        session.updated_at = datetime.utcnow()

        await session_store.set(session_id, session)

        logger.info(f"Discovered {len(schema_list)} schemas for session {session_id}")

        return DiscoveryResponse(
            session_id=session_id,
            schemas=schema_list,
            selected_schema=selected_schema,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Schema discovery failed: {e}")
        session.state["status"] = SessionStatus.FAILED.value
        session.state.setdefault("errors", []).append(f"Schema discovery failed: {str(e)}")
        session.updated_at = datetime.utcnow()
        await session_store.set(session_id, session)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Schema discovery failed: {str(e)}",
        )


@router.get(
    "/sessions/{session_id}/schemas",
    response_model=DiscoveryResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Session not found"},
    },
    summary="Get discovered schemas",
    description="Get the schemas that were discovered for a session.",
    response_description="Previously discovered schemas",
)
async def get_schemas(
    session_id: str,
    session_store: SessionStore = Depends(get_session_store),
) -> DiscoveryResponse:
    """
    Get discovered schemas for a session.

    Returns the schemas that were previously discovered during
    the discovery phase.

    Args:
        session_id: The session identifier

    Returns:
        Discovered schemas and selected schema

    Raises:
        HTTPException: 404 if session not found
    """
    session = await session_store.get(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found",
        )

    state = session.state

    schema_list = [
        SchemaInfo(name=s["name"], table_count=s["table_count"])
        for s in state.get("available_schemas", [])
    ]

    return DiscoveryResponse(
        session_id=session_id,
        schemas=schema_list,
        selected_schema=state.get("selected_schema"),
    )


@router.get(
    "/sessions/{session_id}/tables",
    response_model=TablesResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Session not found"},
        400: {"model": ErrorResponse, "description": "No schema selected"},
        503: {"model": ErrorResponse, "description": "MCP registry not available"},
    },
    summary="Get discovered tables",
    description="Get the tables discovered in the selected schema.",
    response_description="Tables in the selected schema",
)
async def get_tables(
    session_id: str,
    mcp_registry: MCPRegistry = Depends(get_mcp_registry),
    session_store: SessionStore = Depends(get_session_store),
) -> TablesResponse:
    """
    Get discovered tables for a session.

    Discovers tables in the selected schema if not already done,
    or returns previously discovered tables.

    Args:
        session_id: The session identifier

    Returns:
        Tables in the selected schema

    Raises:
        HTTPException: 404 if session not found, 400 if no schema selected
    """
    if not mcp_registry:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MCP registry not initialized",
        )

    session = await session_store.get(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found",
        )

    state = session.state

    selected_schema = state.get("selected_schema")
    if not selected_schema:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No schema selected. Run discovery first.",
        )

    # Check if tables already discovered
    if state.get("discovered_tables"):
        tables = [
            TableInfo(
                schema=t["schema"],
                name=t["name"],
                type=t["type"],
                row_count=t.get("row_count"),
                columns=t.get("columns", []),
            )
            for t in state["discovered_tables"]
        ]
        return TablesResponse(
            session_id=session_id,
            schema_name=selected_schema,
            tables=tables,
        )

    # Discover tables
    try:
        mcp_client = await _get_mcp_client(session, mcp_registry)
        discovered_tables = await mcp_client.discover_tables(selected_schema)

        # Convert to table info
        table_list: List[TableInfo] = []
        state_tables = []

        for table in discovered_tables:
            table_dict = {
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
            state_tables.append(table_dict)
            table_list.append(
                TableInfo(
                    schema=table.table_schema,
                    name=table.table_name,
                    type=table.table_type,
                    row_count=table.row_count,
                    columns=table_dict["columns"],
                )
            )

        # Update session state
        state["discovered_tables"] = state_tables
        state["current_step"] = "tables_discovered"
        state["progress"] = 0.3
        session.updated_at = datetime.utcnow()

        await session_store.set(session_id, session)

        logger.info(f"Discovered {len(table_list)} tables for session {session_id}")

        return TablesResponse(
            session_id=session_id,
            schema_name=selected_schema,
            tables=table_list,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Table discovery failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Table discovery failed: {str(e)}",
        )
