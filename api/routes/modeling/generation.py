"""
Code generation endpoints.

This module provides endpoints for generating dbt code
from model designs.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status

from api.models import (
    ErrorResponse,
    FileContentResponse,
    FileListResponse,
    GeneratedFile,
    GenerateRequest,
    GenerationResponse,
    ModelingStrategy,
    SessionStatus,
)
from api.dependencies import get_session_store, SessionData, SessionStore
from core.generators.dbt_generator import (
    ColumnDefinition,
    DBTGenerator,
    DimensionModelDefinition,
    FactModelDefinition,
    ModelDesign,
    SourceDefinition,
    StagingModelDefinition,
    TableDefinition,
)
from core.utils.config import settings
from core.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


def _convert_to_model_design(session: SessionData) -> ModelDesign:
    """
    Convert session state to ModelDesign format.

    Args:
        session: The session data

    Returns:
        ModelDesign object for code generation
    """
    state = session.state
    design_dict = state.get("model_design", {})

    strategy = state.get("modeling_strategy", "STAR_SCHEMA")
    if isinstance(strategy, str):
        strategy = ModelingStrategy(strategy)

    # Only Star Schema generation is currently supported
    if strategy != ModelingStrategy.STAR_SCHEMA:
        raise ValueError(f"Code generation not yet supported for {strategy.value}")

    # Create source definitions
    sources: List[SourceDefinition] = []
    source_tables_map: Dict[str, TableDefinition] = {}

    for table in state.get("discovered_tables", []):
        schema_name = table["schema"]

        # Find or create source
        source = next((s for s in sources if s.schema == schema_name), None)
        if not source:
            source = SourceDefinition(
                name=schema_name,
                schema=schema_name,
                tables=[],
            )
            sources.append(source)

        # Create table definition
        table_def = TableDefinition(
            name=table["name"],
            schema=schema_name,
            columns=[
                ColumnDefinition(
                    name=col["name"],
                    data_type=col["data_type"],
                    is_nullable=col.get("is_nullable", True),
                    is_primary_key=col.get("is_primary_key", False),
                    is_foreign_key=col.get("is_foreign_key", False),
                    foreign_key_table=col.get("foreign_key_table"),
                    foreign_key_column=col.get("foreign_key_column"),
                )
                for col in table.get("columns", [])
            ],
            row_count=table.get("row_count"),
        )

        source.tables.append(table_def)
        source_tables_map[table["name"]] = table_def

    # Create staging models
    staging_models: List[StagingModelDefinition] = []
    for stg in design_dict.get("staging_models", []):
        source_table = source_tables_map.get(stg.get("source_table", stg.get("name", "")))
        if not source_table:
            continue

        staging_models.append(
            StagingModelDefinition(
                name=stg["name"],
                source_table=source_table,
                columns=[
                    ColumnDefinition(
                        name=col["name"],
                        data_type=col["data_type"],
                        description=col.get("description"),
                        is_nullable=col.get("is_nullable", True),
                        is_primary_key=col.get("is_primary_key", False),
                    )
                    for col in stg.get("columns", [])
                ],
                description=stg.get("description", ""),
            )
        )

    # Create dimension models
    dimension_models: List[DimensionModelDefinition] = []
    for dim in design_dict.get("dimensions", []):
        dimension_models.append(
            DimensionModelDefinition(
                name=dim["name"],
                source_models=dim.get("source_models", []),
                columns=[
                    ColumnDefinition(
                        name=col["name"],
                        data_type=col["data_type"],
                        description=col.get("description"),
                        is_nullable=col.get("is_nullable", True),
                        is_primary_key=col.get("is_primary_key", False),
                    )
                    for col in dim.get("columns", [])
                ],
                description=dim.get("description", ""),
                slowly_changing_type=dim.get("scd_type", 1),
            )
        )

    # Create fact models
    fact_models: List[FactModelDefinition] = []
    for fact in design_dict.get("facts", []):
        fact_models.append(
            FactModelDefinition(
                name=fact["name"],
                source_models=fact.get("source_models", []),
                grain=fact.get("grain", ""),
                columns=[
                    ColumnDefinition(
                        name=col["name"],
                        data_type=col["data_type"],
                        description=col.get("description"),
                        is_nullable=col.get("is_nullable", True),
                        is_primary_key=col.get("is_primary_key", False),
                    )
                    for col in fact.get("columns", [])
                ],
                measures=fact.get("measures", []),
                dimensions=fact.get("dimensions", []),
                description=fact.get("description", ""),
            )
        )

    return ModelDesign(
        project_name=session.project_name or "analytics_project",
        sources=sources,
        staging_models=staging_models,
        dimension_models=dimension_models,
        fact_models=fact_models,
    )


@router.post(
    "/sessions/{session_id}/generate",
    response_model=GenerationResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Session not found"},
        400: {"model": ErrorResponse, "description": "No design available"},
    },
    summary="Generate dbt code",
    description="Generate dbt project code from the model design.",
    response_description="Generation result with file list",
)
async def generate_code(
    session_id: str,
    request: GenerateRequest = GenerateRequest(),
    session_store: SessionStore = Depends(get_session_store),
) -> GenerationResponse:
    """
    Generate dbt code for a session.

    Generates a complete dbt project including models, sources,
    tests, and documentation based on the model design.

    Args:
        session_id: The session identifier
        request: Generation options

    Returns:
        Generation result with list of created files

    Raises:
        HTTPException: 404 if session not found, 400 if no design available
    """
    session = await session_store.get(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found",
        )

    state = session.state

    # Validate design exists
    if not state.get("model_design"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No model design available. Run design first.",
        )

    # Check modeling strategy
    strategy = state.get("modeling_strategy", "STAR_SCHEMA")
    if isinstance(strategy, str):
        strategy = ModelingStrategy(strategy)

    if strategy != ModelingStrategy.STAR_SCHEMA:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Code generation not yet supported for {strategy.value}",
        )

    # Update session status
    state["status"] = SessionStatus.RUNNING.value
    state["current_step"] = "generating_code"
    session.updated_at = datetime.utcnow()

    try:
        # Convert to ModelDesign
        model_design = _convert_to_model_design(session)

        # Determine output directory
        project_name = session.project_name or "analytics_project"
        output_dir = os.path.join(settings.default_workspace_path, project_name)

        # Generate dbt project
        generator = DBTGenerator(
            project_name=project_name,
            target_dir=output_dir,
        )

        generated_files = generator.generate_project(model_design)

        # Convert to file info
        file_list: List[GeneratedFile] = []
        for file_path, content in generated_files.items():
            # Determine file type
            if file_path.endswith(".sql"):
                file_type = "sql"
            elif file_path.endswith(".yml") or file_path.endswith(".yaml"):
                file_type = "yaml"
            elif file_path.endswith(".md"):
                file_type = "markdown"
            else:
                file_type = "text"

            file_list.append(
                GeneratedFile(
                    path=file_path,
                    size_bytes=len(content.encode("utf-8")),
                    file_type=file_type,
                )
            )

        # Update session state
        state["generated_files"] = generated_files
        state["current_step"] = "code_generated"
        state["status"] = SessionStatus.COMPLETED.value
        state["progress"] = 1.0
        session.updated_at = datetime.utcnow()

        await session_store.set(session_id, session)

        logger.info(f"Generated {len(file_list)} files for session {session_id}")

        return GenerationResponse(
            session_id=session_id,
            status="generated",
            files=file_list,
            output_directory=output_dir,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Code generation failed: {e}")
        state["status"] = SessionStatus.FAILED.value
        state.setdefault("errors", []).append(f"Code generation failed: {str(e)}")
        session.updated_at = datetime.utcnow()
        await session_store.set(session_id, session)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Code generation failed: {str(e)}",
        )


@router.get(
    "/sessions/{session_id}/files",
    response_model=FileListResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Session not found"},
    },
    summary="List generated files",
    description="List all files generated for a session.",
    response_description="List of generated files",
)
async def list_files(
    session_id: str,
    session_store: SessionStore = Depends(get_session_store),
) -> FileListResponse:
    """
    List generated files for a session.

    Returns a list of all files that were generated during
    the code generation phase.

    Args:
        session_id: The session identifier

    Returns:
        List of generated files

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

    generated_files = state.get("generated_files", {})

    file_list: List[GeneratedFile] = []
    for file_path, content in generated_files.items():
        if file_path.endswith(".sql"):
            file_type = "sql"
        elif file_path.endswith(".yml") or file_path.endswith(".yaml"):
            file_type = "yaml"
        elif file_path.endswith(".md"):
            file_type = "markdown"
        else:
            file_type = "text"

        file_list.append(
            GeneratedFile(
                path=file_path,
                size_bytes=len(content.encode("utf-8")),
                file_type=file_type,
            )
        )

    return FileListResponse(
        session_id=session_id,
        files=file_list,
        total=len(file_list),
    )


@router.get(
    "/sessions/{session_id}/files/{path:path}",
    response_model=FileContentResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Session or file not found"},
    },
    summary="Get file content",
    description="Get the content of a specific generated file.",
    response_description="File content",
)
async def get_file_content(
    session_id: str,
    path: str,
    session_store: SessionStore = Depends(get_session_store),
) -> FileContentResponse:
    """
    Get the content of a generated file.

    Args:
        session_id: The session identifier
        path: The file path within the generated project

    Returns:
        File content

    Raises:
        HTTPException: 404 if session or file not found
    """
    session = await session_store.get(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found",
        )

    state = session.state

    generated_files = state.get("generated_files", {})

    if path not in generated_files:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File '{path}' not found",
        )

    content = generated_files[path]

    if path.endswith(".sql"):
        file_type = "sql"
    elif path.endswith(".yml") or path.endswith(".yaml"):
        file_type = "yaml"
    elif path.endswith(".md"):
        file_type = "markdown"
    else:
        file_type = "text"

    return FileContentResponse(
        path=path,
        content=content,
        file_type=file_type,
    )
