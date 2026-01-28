"""
Session management endpoints.

This module provides endpoints for creating, retrieving, listing,
and deleting modeling sessions.
"""

from datetime import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from api.models import (
    CreateSessionRequest,
    ErrorResponse,
    ModelingStrategy,
    SessionListResponse,
    SessionResponse,
    SessionStatus,
)
from api.dependencies import (
    get_mcp_registry,
    get_session_store,
    SessionData,
    SessionStore,
)
from core.mcp.registry import MCPRegistry
from core.utils.config import settings
from core.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.post(
    "/",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"model": ErrorResponse, "description": "Data source not found"},
        400: {"model": ErrorResponse, "description": "Invalid request"},
        503: {"model": ErrorResponse, "description": "MCP registry not available"},
    },
    summary="Create modeling session",
    description="Initialize a new data modeling session with the specified configuration.",
    response_description="Created session information",
)
async def create_session(
    request: CreateSessionRequest,
    mcp_registry: MCPRegistry = Depends(get_mcp_registry),
    session_store: SessionStore = Depends(get_session_store),
) -> SessionResponse:
    """
    Create a new modeling session.

    Initializes a modeling session with the specified project name,
    requirements, data source, and modeling strategy. The session
    can then be used to run discovery, profiling, design, and generation.

    Args:
        request: Session creation parameters

    Returns:
        Created session information

    Raises:
        HTTPException: 404 if data source not found, 503 if registry unavailable
    """
    if not mcp_registry:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MCP registry not initialized",
        )

    # Validate data source exists
    server_config = mcp_registry.servers.get(request.data_source)
    if not server_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data source '{request.data_source}' not found in registry",
        )

    # Validate data source type
    if server_config.type != "database":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Data source '{request.data_source}' is not a database type",
        )

    # Create session
    session_id = str(uuid.uuid4())
    now = datetime.utcnow()

    session_data = SessionData(
        session_id=session_id,
        project_name=request.project_name,
        created_at=now,
        updated_at=now,
        workflow=None,
        state={
            "requirements": request.requirements,
            "data_source": request.data_source,
            "modeling_strategy": request.modeling_strategy.value,
            "status": SessionStatus.PENDING.value,
            "current_step": "initialized",
            "progress": 0.0,
            "errors": [],
            "warnings": [],
            "available_schemas": [],
            "selected_schema": "",
            "discovered_tables": [],
            "data_profiles": {},
            "model_design": {},
            "generated_files": {},
        },
        metadata={},
    )

    await session_store.set(session_id, session_data)

    logger.info(f"Created session {session_id} for project {request.project_name}")

    return SessionResponse(
        session_id=session_id,
        project_name=request.project_name,
        data_source=request.data_source,
        modeling_strategy=request.modeling_strategy,
        status=SessionStatus.PENDING,
        current_step="initialized",
        progress=0.0,
        created_at=now,
        updated_at=now,
        errors=[],
        warnings=[],
    )


@router.get(
    "/{session_id}",
    response_model=SessionResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Session not found"},
    },
    summary="Get session",
    description="Retrieve the current state of a modeling session.",
    response_description="Session information and status",
)
async def get_session(
    session_id: str,
    session_store: SessionStore = Depends(get_session_store),
) -> SessionResponse:
    """
    Get the current state of a modeling session.

    Args:
        session_id: The unique identifier of the session

    Returns:
        Current session information and status

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

    return SessionResponse(
        session_id=session.session_id,
        project_name=session.project_name,
        data_source=state.get("data_source", ""),
        modeling_strategy=ModelingStrategy(state.get("modeling_strategy", "STAR_SCHEMA")),
        status=SessionStatus(state.get("status", "pending")),
        current_step=state.get("current_step", "initialized"),
        progress=state.get("progress", 0.0),
        created_at=session.created_at,
        updated_at=session.updated_at,
        errors=state.get("errors", []),
        warnings=state.get("warnings", []),
    )


@router.delete(
    "/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: {"model": ErrorResponse, "description": "Session not found"},
    },
    summary="Delete session",
    description="Delete a modeling session and clean up associated resources.",
    response_description="No content on success",
)
async def delete_session(
    session_id: str,
    session_store: SessionStore = Depends(get_session_store),
) -> None:
    """
    Delete a modeling session.

    Removes the session and cleans up any associated resources.
    Generated files are not deleted.

    Args:
        session_id: The unique identifier of the session to delete

    Raises:
        HTTPException: 404 if session not found
    """
    deleted = await session_store.delete(session_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found",
        )

    logger.info(f"Deleted session {session_id}")


@router.get(
    "/",
    response_model=SessionListResponse,
    summary="List sessions",
    description="Get a list of all modeling sessions.",
    response_description="List of sessions with pagination info",
)
async def list_sessions(
    session_store: SessionStore = Depends(get_session_store),
) -> SessionListResponse:
    """
    List all modeling sessions.

    Returns a list of all active sessions with their current status.

    Returns:
        List of sessions and total count
    """
    session_ids = await session_store.list_sessions()
    sessions = []

    for session_id in session_ids:
        session = await session_store.get(session_id)
        if session is None:
            continue

        state = session.state
        sessions.append(
            SessionResponse(
                session_id=session.session_id,
                project_name=session.project_name,
                data_source=state.get("data_source", ""),
                modeling_strategy=ModelingStrategy(state.get("modeling_strategy", "STAR_SCHEMA")),
                status=SessionStatus(state.get("status", "pending")),
                current_step=state.get("current_step", "initialized"),
                progress=state.get("progress", 0.0),
                created_at=session.created_at,
                updated_at=session.updated_at,
                errors=state.get("errors", []),
                warnings=state.get("warnings", []),
            )
        )

    return SessionListResponse(
        sessions=sessions,
        total=len(sessions),
    )
