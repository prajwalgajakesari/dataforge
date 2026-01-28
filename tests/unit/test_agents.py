"""
Unit tests for DataForge agents.
"""

import pytest

from core.agents.base import AgentState, AgentType, TaskStatus
from core.agents.modeling import DataModelingAgent


class TestDataModelingAgent:
    """Tests for the DataModelingAgent."""

    def test_agent_type(self, mock_mcp_registry, mock_workspace_manager):
        """Test that agent returns correct type."""
        agent = DataModelingAgent(
            mcp_registry=mock_mcp_registry,
            workspace_manager=mock_workspace_manager,
            llm_client=None,
        )
        assert agent.agent_type == AgentType.MODELING

    def test_agent_capabilities(self, mock_mcp_registry, mock_workspace_manager):
        """Test that agent defines capabilities."""
        agent = DataModelingAgent(
            mcp_registry=mock_mcp_registry,
            workspace_manager=mock_workspace_manager,
            llm_client=None,
        )
        capabilities = agent.get_capabilities()
        assert len(capabilities) > 0
        assert any(cap.name == "schema_discovery" for cap in capabilities)
        assert any(cap.name == "dbt_generation" for cap in capabilities)

    @pytest.mark.asyncio
    async def test_can_handle_modeling_task(self, mock_mcp_registry, mock_workspace_manager):
        """Test that agent can identify modeling tasks."""
        agent = DataModelingAgent(
            mcp_registry=mock_mcp_registry,
            workspace_manager=mock_workspace_manager,
            llm_client=None,
        )

        # Should handle modeling tasks
        assert await agent.can_handle({"type": "modeling"})
        assert await agent.can_handle({"description": "create dbt models"})
        assert await agent.can_handle({"description": "design star schema"})

        # Should not handle other tasks
        assert not await agent.can_handle({"type": "infrastructure"})


class TestAgentState:
    """Tests for AgentState."""

    def test_agent_state_initialization(self, sample_agent_state):
        """Test agent state initialization."""
        assert sample_agent_state.status == TaskStatus.PENDING
        assert sample_agent_state.progress == 0.0
        assert len(sample_agent_state.errors) == 0

    def test_agent_state_error_handling(self, sample_agent_state):
        """Test error handling in agent state."""
        sample_agent_state.add_error("Test error")
        assert len(sample_agent_state.errors) == 1
        assert sample_agent_state.errors[0] == "Test error"

    def test_agent_state_progress_update(self, sample_agent_state):
        """Test progress updates in agent state."""
        sample_agent_state.update_progress("testing", 0.5)
        assert sample_agent_state.current_step == "testing"
        assert sample_agent_state.progress == 0.5
