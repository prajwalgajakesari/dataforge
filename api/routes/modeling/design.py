"""
Model design endpoints.

This module provides endpoints for generating and managing
data model designs using LLM.
"""

from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status

from api.models import (
    DesignRequest,
    DesignResponse,
    DesignUpdateRequest,
    ErrorResponse,
    ModelingStrategy,
    SessionStatus,
)
from api.dependencies import get_mcp_registry, get_session_store, SessionStore
from core.mcp.registry import MCPRegistry
from core.utils.llm_client import LLMClient
from core.utils.logger import get_logger
from core.prompts import modeling as prompts

logger = get_logger(__name__)

router = APIRouter()


@router.post(
    "/sessions/{session_id}/design",
    response_model=DesignResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Session not found"},
        400: {"model": ErrorResponse, "description": "Insufficient data for design"},
        503: {"model": ErrorResponse, "description": "Service unavailable"},
    },
    summary="Generate model design",
    description="Generate a data model design using LLM based on discovered schemas and profiling data.",
    response_description="Generated model design",
)
async def generate_design(
    session_id: str,
    request: DesignRequest = DesignRequest(),
    mcp_registry: MCPRegistry = Depends(get_mcp_registry),
    session_store: SessionStore = Depends(get_session_store),
) -> DesignResponse:
    """
    Generate a model design for a session.

    Uses an LLM to generate a data model design based on the
    discovered schemas, tables, and profiling data. The design
    follows the session's modeling strategy (Star Schema, 3NF, or Data Vault).

    Args:
        session_id: The session identifier
        request: Design options (strategy override, custom instructions)

    Returns:
        Generated model design with reasoning

    Raises:
        HTTPException: 404 if session not found, 400 if insufficient data
    """
    session = await session_store.get(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found",
        )

    state = session.state

    # Validate we have enough data
    if not state.get("discovered_tables"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No tables discovered. Run discovery first.",
        )

    # Update session status
    state["status"] = SessionStatus.IN_PROGRESS.value
    state["current_step"] = "designing_model"
    session.updated_at = datetime.utcnow()

    try:
        # Determine modeling strategy
        strategy = request.modeling_strategy or ModelingStrategy(state.get("modeling_strategy", "STAR_SCHEMA"))
        if isinstance(strategy, str):
            strategy = ModelingStrategy(strategy)

        # Build state for prompt generation
        modeling_state = {
            "requirements": state.get("requirements", ""),
            "modeling_strategy": strategy.value,
            "discovered_tables": state.get("discovered_tables", []),
            "data_profiles": state.get("data_profiles", {}),
        }

        # Build prompt based on strategy
        if strategy == ModelingStrategy.NORMALIZED_3NF:
            prompt = prompts.build_normalized_3nf_prompt(modeling_state)
            system = "You are an expert data architect specializing in 3NF and relational database design. Eliminate redundancy."
        elif strategy == ModelingStrategy.DATA_VAULT:
            prompt = prompts.build_data_vault_prompt(modeling_state)
            system = "You are an expert in Data Vault 2.0 methodology. Focus on Hubs, Links, and Satellites."
        else:
            # Default to Star Schema
            prompt = prompts.build_star_schema_prompt(modeling_state)
            system = "You are an expert data modeler specializing in dimensional modeling and star schemas."

        # Add custom instructions if provided
        if request.custom_instructions:
            prompt += f"\n\nAdditional Instructions:\n{request.custom_instructions}"

        # Generate design using LLM
        llm_client = LLMClient()

        # Import response models
        from core.graph.modeling_graph import (
            StarSchemaDesign,
            NormalizedDesign,
            DataVaultDesign,
        )

        if strategy == ModelingStrategy.NORMALIZED_3NF:
            response_model = NormalizedDesign
        elif strategy == ModelingStrategy.DATA_VAULT:
            response_model = DataVaultDesign
        else:
            response_model = StarSchemaDesign

        design, response = await llm_client.generate_structured(
            prompt=prompt,
            response_model=response_model,
            system=system,
            temperature=0.0,
        )

        # Update session state
        design_dict = design.model_dump()
        state["model_design"] = design_dict

        state["current_step"] = "model_designed"
        state["progress"] = 0.7
        session.updated_at = datetime.utcnow()

        await session_store.set(session_id, session)

        logger.info(f"Generated {strategy.value} design for session {session_id}")

        return DesignResponse(
            session_id=session_id,
            modeling_strategy=strategy,
            design=design_dict,
            reasoning=design.reasoning if hasattr(design, "reasoning") else None,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Model design failed: {e}")
        state["status"] = SessionStatus.FAILED.value
        state.setdefault("errors", []).append(f"Model design failed: {str(e)}")
        session.updated_at = datetime.utcnow()
        await session_store.set(session_id, session)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Model design failed: {str(e)}",
        )


@router.get(
    "/sessions/{session_id}/design",
    response_model=DesignResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Session not found"},
    },
    summary="Get current design",
    description="Get the current model design for a session.",
    response_description="Current model design",
)
async def get_design(
    session_id: str,
    session_store: SessionStore = Depends(get_session_store),
) -> DesignResponse:
    """
    Get the current model design for a session.

    Returns the model design that was previously generated
    during the design phase.

    Args:
        session_id: The session identifier

    Returns:
        Current model design

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

    design = state.get("model_design", {})
    strategy = state.get("modeling_strategy", "STAR_SCHEMA")
    if isinstance(strategy, str):
        strategy = ModelingStrategy(strategy)

    return DesignResponse(
        session_id=session_id,
        modeling_strategy=strategy,
        design=design,
        reasoning=design.get("reasoning") if design else None,
    )


@router.put(
    "/sessions/{session_id}/design",
    response_model=DesignResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Session not found"},
    },
    summary="Update design manually",
    description="Manually update the model design for a session.",
    response_description="Updated model design",
)
async def update_design(
    session_id: str,
    request: DesignUpdateRequest,
    session_store: SessionStore = Depends(get_session_store),
) -> DesignResponse:
    """
    Manually update the model design for a session.

    Allows manual modifications to the generated design
    before code generation.

    Args:
        session_id: The session identifier
        request: The updated design

    Returns:
        Updated model design

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

    # Update the design
    state["model_design"] = request.model_design
    session.updated_at = datetime.utcnow()

    await session_store.set(session_id, session)

    strategy = state.get("modeling_strategy", "STAR_SCHEMA")
    if isinstance(strategy, str):
        strategy = ModelingStrategy(strategy)

    logger.info(f"Updated design for session {session_id}")

    return DesignResponse(
        session_id=session_id,
        modeling_strategy=strategy,
        design=request.model_design,
        reasoning=request.model_design.get("reasoning"),
    )
