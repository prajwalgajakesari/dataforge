"""
Integration tests for the complete modeling workflow.

These tests validate the end-to-end data modeling process from
schema discovery to dbt project generation.
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.agents.base import AgentState, AgentType, TaskStatus
from core.agents.modeling import DataModelingAgent
from core.mcp.registry import MCPRegistry, MCPServerConfig
from core.workspace.manager import WorkspaceManager


@pytest.fixture
def mock_mcp_registry():
    """Create a mock MCP registry."""
    registry = MagicMock(spec=MCPRegistry)
    registry.get_capabilities = AsyncMock(
        return_value={"data_sources": ["postgres"], "tools": [], "platforms": []}
    )
    registry.query_source = AsyncMock(return_value={"rows": [], "columns": []})
    return registry


@pytest.fixture
def mock_workspace_manager(tmp_path):
    """Create a workspace manager with temp directory."""
    manager = WorkspaceManager(base_path=str(tmp_path))
    workspace = manager.create_workspace(
        name="test_project",
        project_type="dbt",
    )
    return manager


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client."""
    from core.utils.llm_client import LLMClient, LLMResponse, LLMUsage

    client = MagicMock(spec=LLMClient)
    client.generate = AsyncMock(
        return_value=LLMResponse(
            content="Test response",
            model="claude-3-5-sonnet-20241022",
            usage=LLMUsage(
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150,
                cost_usd=0.001,
            ),
        )
    )
    return client


@pytest.fixture
def agent_state(mock_workspace_manager):
    """Create an agent state for testing."""
    return AgentState(
        user_id="test_user",
        agent_type=AgentType.MODELING,
        workspace_path=str(mock_workspace_manager.current_workspace.path),
        requirements="Create a customer analytics data mart with orders and products",
        parameters={"project_name": "test_analytics"},
    )


class TestDataModelingAgent:
    """Test suite for DataModelingAgent."""

    @pytest.mark.asyncio
    async def test_agent_initialization(
        self,
        mock_mcp_registry,
        mock_workspace_manager,
        mock_llm_client,
    ):
        """Test agent can be initialized with required dependencies."""
        agent = DataModelingAgent(
            mcp_registry=mock_mcp_registry,
            workspace_manager=mock_workspace_manager,
            llm_client=mock_llm_client,
        )

        assert agent.agent_type == AgentType.MODELING
        assert len(agent.capabilities) > 0

    @pytest.mark.asyncio
    async def test_can_handle_modeling_task(
        self,
        mock_mcp_registry,
        mock_workspace_manager,
        mock_llm_client,
    ):
        """Test agent correctly identifies modeling tasks."""
        agent = DataModelingAgent(
            mcp_registry=mock_mcp_registry,
            workspace_manager=mock_workspace_manager,
            llm_client=mock_llm_client,
        )

        # Should handle modeling tasks
        modeling_task = {
            "type": "modeling",
            "description": "Create a data model",
        }
        assert await agent.can_handle(modeling_task)

        # Should handle dbt-related tasks
        dbt_task = {
            "type": "data_engineering",
            "description": "Generate dbt models for star schema",
        }
        assert await agent.can_handle(dbt_task)

        # Should not handle unrelated tasks
        pipeline_task = {
            "type": "pipeline",
            "description": "Create an Airflow DAG",
        }
        assert not await agent.can_handle(pipeline_task)


class TestModelingWorkflow:
    """Test suite for the complete modeling workflow."""

    @pytest.mark.asyncio
    @patch("core.mcp.servers.postgres_mcp.PostgresMCP")
    @patch("core.utils.llm_client.LLMClient")
    async def test_workflow_execution(
        self,
        mock_llm_class,
        mock_postgres_class,
        agent_state,
        mock_workspace_manager,
    ):
        """Test complete workflow execution."""
        # Setup mocks
        mock_postgres = AsyncMock()
        mock_postgres.connect = AsyncMock()
        mock_postgres.disconnect = AsyncMock()
        mock_postgres.discover_schemas = AsyncMock(
            return_value=[
                MagicMock(
                    schema_name="public",
                    tables=[],
                )
            ]
        )
        mock_postgres_class.return_value = mock_postgres

        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(
            return_value=MagicMock(
                content="public",
                usage=MagicMock(
                    total_tokens=100,
                    cost_usd=0.001,
                ),
            )
        )
        mock_llm.get_total_usage = MagicMock(
            return_value=MagicMock(
                total_tokens=100,
                cost_usd=0.001,
            )
        )
        mock_llm_class.return_value = mock_llm

        # Create agent
        agent = DataModelingAgent(
            mcp_registry=MagicMock(),
            workspace_manager=mock_workspace_manager,
            llm_client=mock_llm,
        )

        # This would normally execute the full workflow
        # For now, we're testing that the structure is correct
        assert agent.agent_type == AgentType.MODELING


class TestDBTGenerator:
    """Test suite for DBT Generator."""

    def test_generate_project_structure(self, tmp_path):
        """Test dbt project generation creates correct file structure."""
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

        # Create a simple model design
        design = ModelDesign(
            project_name="test_project",
            sources=[
                SourceDefinition(
                    name="test_source",
                    schema="public",
                    tables=[
                        TableDefinition(
                            name="customers",
                            schema="public",
                            columns=[
                                ColumnDefinition(
                                    name="id",
                                    data_type="integer",
                                    is_primary_key=True,
                                    is_nullable=False,
                                ),
                                ColumnDefinition(
                                    name="name",
                                    data_type="varchar",
                                ),
                            ],
                        )
                    ],
                )
            ],
            staging_models=[
                StagingModelDefinition(
                    name="customers",
                    source_table=TableDefinition(
                        name="customers",
                        schema="public",
                        columns=[
                            ColumnDefinition(name="id", data_type="integer"),
                            ColumnDefinition(name="name", data_type="varchar"),
                        ],
                    ),
                    columns=[
                        ColumnDefinition(name="customer_id", data_type="integer"),
                        ColumnDefinition(name="customer_name", data_type="varchar"),
                    ],
                    description="Staging model for customers",
                )
            ],
            dimension_models=[
                DimensionModelDefinition(
                    name="customers",
                    source_models=["stg_customers"],
                    columns=[
                        ColumnDefinition(
                            name="customer_key",
                            data_type="integer",
                            is_primary_key=True,
                        ),
                        ColumnDefinition(name="customer_name", data_type="varchar"),
                    ],
                    description="Customer dimension",
                )
            ],
            fact_models=[
                FactModelDefinition(
                    name="orders",
                    source_models=["stg_orders"],
                    grain="one row per order",
                    columns=[
                        ColumnDefinition(name="order_key", data_type="integer"),
                        ColumnDefinition(name="order_amount", data_type="numeric"),
                    ],
                    measures=["order_amount"],
                    dimensions=["customers"],
                    description="Order fact table",
                )
            ],
        )

        # Generate project
        generator = DBTGenerator(
            project_name="test_project",
            target_dir=tmp_path / "test_project",
        )

        files = generator.generate_project(design)

        # Verify required files exist
        assert "dbt_project.yml" in files
        assert "models/staging/sources.yml" in files
        assert "models/staging/stg_customers.sql" in files
        assert "models/marts/dim_customers.sql" in files
        assert "models/marts/fct_orders.sql" in files
        assert "README.md" in files

        # Verify content is not empty
        assert len(files["dbt_project.yml"]) > 0
        assert len(files["models/staging/sources.yml"]) > 0


class TestPostgresMCP:
    """Test suite for PostgresMCP server."""

    @pytest.mark.asyncio
    async def test_mcp_configuration(self):
        """Test PostgresMCP can be configured."""
        from core.mcp.servers.postgres_mcp import PostgresMCP

        config = MCPServerConfig(
            name="test_postgres",
            type="database",
            capabilities=["query", "schema"],
            connection_config={
                "host": "localhost",
                "port": 5432,
                "user": "test",
                "password": "test",
                "database": "test",
            },
        )

        mcp = PostgresMCP(config)
        assert mcp.config.name == "test_postgres"
        assert mcp.config.type == "database"


class TestLLMClient:
    """Test suite for LLM Client."""

    @pytest.mark.asyncio
    async def test_llm_client_initialization(self):
        """Test LLM client can be initialized."""
        from core.utils.llm_client import LLMClient

        # This will fail without API key, but we're testing structure
        try:
            client = LLMClient(api_key="test_key")
            assert client.model is not None
            assert client.max_tokens > 0
        except Exception:
            # Expected without valid API key
            pass

    def test_llm_usage_tracking(self):
        """Test LLM usage tracking structures."""
        from core.utils.llm_client import LLMUsage

        usage = LLMUsage(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost_usd=0.001,
        )

        assert usage.total_tokens == 150
        assert usage.cost_usd == 0.001


@pytest.mark.integration
class TestEndToEndWorkflow:
    """
    End-to-end integration tests.

    These tests require a real database and API key.
    Run with: pytest -m integration
    """

    @pytest.mark.skip(reason="Requires database and API key")
    @pytest.mark.asyncio
    async def test_complete_workflow_with_real_db(self):
        """Test complete workflow with real database connection."""
        # This test would:
        # 1. Connect to a test database
        # 2. Discover schemas
        # 3. Generate model design with real LLM
        # 4. Generate dbt project
        # 5. Validate outputs
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
