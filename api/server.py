"""
FastAPI server for DataForge.

This module provides the REST API and WebSocket endpoints for DataForge.
"""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from core.mcp.registry import MCPRegistry
from core.utils.config import settings
from core.utils.logger import setup_logger

logger = setup_logger("dataforge.api", level=settings.dataforge_log_level)


# Global registry instance
mcp_registry: MCPRegistry | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Lifespan context manager for FastAPI.
    Handles startup and shutdown events.
    """
    global mcp_registry

    # Startup
    logger.info("Starting DataForge API server")

    # Initialize MCP registry
    mcp_registry = MCPRegistry()
    await mcp_registry.initialize()
    logger.info("MCP registry initialized")

    yield

    # Shutdown
    logger.info("Shutting down DataForge API server")
    if mcp_registry:
        await mcp_registry.shutdown()


# Create FastAPI app
app = FastAPI(
    title="DataForge API",
    description="AI-powered data engineering platform API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "DataForge API",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    mcp_status = {}
    if mcp_registry:
        mcp_status = mcp_registry.get_server_status()

    return {
        "status": "healthy",
        "mcp_servers": len(mcp_status),
        "environment": settings.dataforge_env,
    }


@app.get("/api/v1/capabilities")
async def get_capabilities():
    """Get available capabilities from MCP servers."""
    if not mcp_registry:
        return JSONResponse(
            status_code=503,
            content={"error": "MCP registry not initialized"}
        )

    capabilities = await mcp_registry.get_capabilities()
    return capabilities


@app.get("/api/v1/servers")
async def list_servers():
    """List all registered MCP servers."""
    if not mcp_registry:
        return JSONResponse(
            status_code=503,
            content={"error": "MCP registry not initialized"}
        )

    return mcp_registry.get_server_status()



# -----------------------------------------------------------------------------
# Modeling Routes
# -----------------------------------------------------------------------------

from pydantic import BaseModel
from typing import Dict, Any, Optional
import uuid

# In-memory session store (replace with Redis/Database in production)
modeling_sessions: Dict[str, Any] = {}

class CreateProjectRequest(BaseModel):
    project_name: str
    requirements: str
    data_source: str = "postgres"
    modeling_strategy: str = "STAR_SCHEMA"

class DesignRequest(BaseModel):
    modeling_strategy: Optional[str] = None

@app.post("/api/v1/modeling/create")
async def create_modeling_session(request: CreateProjectRequest):
    """Initialize a new modeling session."""
    if not mcp_registry:
        return JSONResponse(status_code=503, content={"error": "MCP registry not initialized"})

    session_id = str(uuid.uuid4())
    
    # Initialize workflow components
    from core.graph.modeling_graph import ModelingWorkflow
    from core.utils.llm_client import LLMClient
    from core.mcp.servers.postgres_mcp import PostgresMCP 
    
    # Get server config from registry
    server_config = mcp_registry.servers.get(request.data_source)
    if not server_config:
         return JSONResponse(status_code=404, content={"error": f"Source {request.data_source} not found in registry"})

    # Initialize MCP client
    # In a full multi-provider setup, we'd select the class based on config.type
    if server_config.type == 'database':
        mcp_client = PostgresMCP(config=server_config)
    else:
        return JSONResponse(status_code=400, content={"error": f"Unsupported source type: {server_config.type}"})

    # Initialize workflow
    workflow = ModelingWorkflow(
        mcp_client=mcp_client,
        llm_client=LLMClient(),
        workspace_path=settings.default_workspace_path
    )
    
    # Run first step: Discovery
    initial_state = await workflow.run(
        requirements=request.requirements,
        data_source=request.data_source,
        project_name=request.project_name,
        modeling_strategy=request.modeling_strategy
    )

    modeling_sessions[session_id] = {
        "workflow": workflow,
        "state": initial_state
    }
    
    return {
        "session_id": session_id,
        "state": initial_state
    }

@app.post("/api/v1/modeling/{session_id}/generate")
async def generate_code(session_id: str):
    """Trigger code generation for a session."""
    if session_id not in modeling_sessions:
        return JSONResponse(status_code=404, content={"error": "Session not found"})
    
    session_data = modeling_sessions[session_id]
    workflow = session_data["workflow"]
    current_state = session_data["state"]
    
    # Trigger generation manually
    try:
        new_state = await workflow.generate_code(current_state)
        modeling_sessions[session_id]["state"] = new_state
        return {
            "status": "generated",
            "state": new_state
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/v1/modeling/{session_id}/state")
async def get_session_state(session_id: str):
    """Get current state of a session."""
    if session_id not in modeling_sessions:
        return JSONResponse(status_code=404, content={"error": "Session not found"})
    
    return modeling_sessions[session_id]["state"]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api.server:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
        log_level=settings.dataforge_log_level.lower(),
    )
