"""
Data profiling endpoints.

This module provides endpoints for profiling data in discovered tables.
"""

from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status

from api.models import (
    ColumnProfile,
    ErrorResponse,
    ProfileRequest,
    ProfilingResponse,
    SessionStatus,
    TableProfile,
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
    """Get or create an MCP client for the session's data source."""
    data_source = session.state.get("data_source", "")
    server_config = mcp_registry.servers.get(data_source)

    if not server_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data source '{data_source}' not found",
        )

    return PostgresMCP(config=server_config)


@router.post(
    "/sessions/{session_id}/profile",
    response_model=ProfilingResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Session not found"},
        400: {"model": ErrorResponse, "description": "No tables discovered"},
        503: {"model": ErrorResponse, "description": "MCP registry not available"},
    },
    summary="Run data profiling",
    description="Profile data in discovered tables to understand data quality and patterns.",
    response_description="Profiling results for each table",
)
async def profile_data(
    session_id: str,
    request: ProfileRequest = ProfileRequest(),
    mcp_registry: MCPRegistry = Depends(get_mcp_registry),
    session_store: SessionStore = Depends(get_session_store),
) -> ProfilingResponse:
    """
    Run data profiling for a session.

    Profiles the data in discovered tables to gather statistics
    like null counts, distinct counts, min/max values, and sample data.

    Args:
        session_id: The session identifier
        request: Profiling options (tables to profile, sample size)

    Returns:
        Profiling results for each table

    Raises:
        HTTPException: 404 if session not found, 400 if no tables discovered
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

    # Validate tables exist
    discovered_tables = state.get("discovered_tables", [])
    if not discovered_tables:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No tables discovered. Run discovery first.",
        )

    # Update session status
    state["status"] = SessionStatus.IN_PROGRESS.value
    state["current_step"] = "profiling_data"
    session.updated_at = datetime.utcnow()

    try:
        mcp_client = await _get_mcp_client(session, mcp_registry)

        # Determine which tables to profile
        if request.tables:
            tables_to_profile = [
                t for t in discovered_tables
                if t["name"] in request.tables
            ]
        else:
            # Profile up to 10 tables by default
            tables_to_profile = discovered_tables[:10]

        profiles: Dict[str, TableProfile] = {}

        for table in tables_to_profile:
            table_name = table["name"]
            schema_name = table["schema"]

            try:
                table_profiles = await mcp_client.profile_table(
                    schema_name=schema_name,
                    table_name=table_name,
                    sample_size=request.sample_size,
                )

                columns: List[ColumnProfile] = []
                for profile in table_profiles:
                    columns.append(
                        ColumnProfile(
                            column_name=profile.column_name,
                            data_type=profile.data_type,
                            null_count=profile.null_count,
                            distinct_count=profile.distinct_count,
                            min_value=profile.min_value,
                            max_value=profile.max_value,
                            sample_values=profile.sample_values or [],
                        )
                    )

                profiles[table_name] = TableProfile(
                    table_name=table_name,
                    row_count=table.get("row_count", 0),
                    columns=columns,
                )

            except Exception as e:
                logger.warning(f"Could not profile table {table_name}: {e}")
                state.setdefault("warnings", []).append(f"Could not profile {table_name}: {str(e)}")

        # Update session state
        state["data_profiles"] = {
            name: {
                "table_name": profile.table_name,
                "row_count": profile.row_count,
                "columns": [
                    {
                        "column_name": col.column_name,
                        "data_type": col.data_type,
                        "null_count": col.null_count,
                        "distinct_count": col.distinct_count,
                        "min_value": col.min_value,
                        "max_value": col.max_value,
                        "sample_values": col.sample_values,
                    }
                    for col in profile.columns
                ],
            }
            for name, profile in profiles.items()
        }

        state["current_step"] = "data_profiled"
        state["progress"] = 0.5
        session.updated_at = datetime.utcnow()

        await session_store.set(session_id, session)

        logger.info(f"Profiled {len(profiles)} tables for session {session_id}")

        return ProfilingResponse(
            session_id=session_id,
            profiles=profiles,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Data profiling failed: {e}")
        state["status"] = SessionStatus.FAILED.value
        state.setdefault("errors", []).append(f"Data profiling failed: {str(e)}")
        session.updated_at = datetime.utcnow()
        await session_store.set(session_id, session)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Data profiling failed: {str(e)}",
        )


@router.get(
    "/sessions/{session_id}/profiles",
    response_model=ProfilingResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Session not found"},
    },
    summary="Get profiling results",
    description="Get the data profiling results for a session.",
    response_description="Previously computed profiling results",
)
async def get_profiles(
    session_id: str,
    session_store: SessionStore = Depends(get_session_store),
) -> ProfilingResponse:
    """
    Get profiling results for a session.

    Returns the profiling data that was previously computed
    during the profiling phase.

    Args:
        session_id: The session identifier

    Returns:
        Profiling results for profiled tables

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

    profiles_data = state.get("data_profiles", {})
    profiles: Dict[str, TableProfile] = {}

    for table_name, profile_dict in profiles_data.items():
        profiles[table_name] = TableProfile(
            table_name=profile_dict["table_name"],
            row_count=profile_dict["row_count"],
            columns=[
                ColumnProfile(
                    column_name=col["column_name"],
                    data_type=col["data_type"],
                    null_count=col["null_count"],
                    distinct_count=col["distinct_count"],
                    min_value=col.get("min_value"),
                    max_value=col.get("max_value"),
                    sample_values=col.get("sample_values", []),
                )
                for col in profile_dict.get("columns", [])
            ],
        )

    return ProfilingResponse(
        session_id=session_id,
        profiles=profiles,
    )
