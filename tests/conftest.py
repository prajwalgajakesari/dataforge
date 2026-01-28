"""
Pytest configuration and fixtures for DataForge tests.
"""

import pytest
from pathlib import Path
import tempfile
import shutil

@pytest.fixture
def temp_workspace():
    """Create a temporary workspace directory for testing."""
    temp_dir = tempfile.mkdtemp(prefix="dataforge_test_")
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def mock_mcp_registry():
    """Mock MCP registry for testing."""
    from core.mcp.registry import MCPRegistry

    # Create registry with test config
    registry = MCPRegistry(config_path=None)
    return registry


@pytest.fixture
def mock_workspace_manager(temp_workspace):
    """Mock workspace manager for testing."""
    from core.workspace.manager import WorkspaceManager

    manager = WorkspaceManager(base_path=str(temp_workspace))
    return manager


@pytest.fixture
def sample_agent_state():
    """Sample agent state for testing."""
    from core.agents.base import AgentState, AgentType

    return AgentState(
        user_id="test_user",
        agent_type=AgentType.MODELING,
        workspace_path="/tmp/test_workspace",
        requirements="Create a customer analytics data mart"
    )
