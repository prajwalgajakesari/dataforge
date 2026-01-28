"""
Data Modeling Agent for DataForge.

This agent is responsible for:
- Analyzing data sources and schemas
- Profiling data
- Designing dimensional models (star schema, snowflake, data vault)
- Generating dbt models
- Creating documentation
"""

from pathlib import Path
from typing import Any, Dict, List

from core.agents.base import (
    AgentCapability,
    AgentState,
    AgentType,
    BaseDataEngineeringAgent,
    TaskStatus,
)
from core.graph.modeling_graph import ModelingWorkflow
from core.mcp.servers.postgres_mcp import PostgresMCP
from core.utils.llm_client import LLMClient
from core.utils.logger import get_logger

logger = get_logger(__name__)


class DataModelingAgent(BaseDataEngineeringAgent):
    """
    Agent specialized in data modeling and dbt project generation.

    This agent can:
    1. Discover and analyze data sources
    2. Profile data for quality and patterns
    3. Design dimensional models (star schema)
    4. Generate dbt staging models
    5. Generate dbt mart models (facts and dimensions)
    6. Create tests and documentation
    7. Generate DDL for target warehouse
    """

    def _get_agent_type(self) -> AgentType:
        """Return the agent type."""
        return AgentType.MODELING

    def _define_capabilities(self) -> List[AgentCapability]:
        """Define modeling agent capabilities."""
        return [
            AgentCapability(
                name="schema_discovery",
                description="Discover schemas from databases via MCP",
                required_mcps=["postgres", "mysql", "snowflake", "bigquery"],
                output_types=["schema_metadata"],
            ),
            AgentCapability(
                name="data_profiling",
                description="Profile data for quality, patterns, and relationships",
                required_mcps=["database"],
                output_types=["profile_report"],
            ),
            AgentCapability(
                name="dimensional_modeling",
                description="Design star schema models (facts and dimensions)",
                required_mcps=[],
                output_types=["model_design"],
            ),
            AgentCapability(
                name="dbt_generation",
                description="Generate complete dbt project with models, tests, and docs",
                required_mcps=[],
                output_types=["dbt"],
            ),
            AgentCapability(
                name="ddl_generation",
                description="Generate DDL for target data warehouse",
                required_mcps=[],
                output_types=["sql"],
            ),
        ]

    async def can_handle(self, task: Dict[str, Any]) -> bool:
        """
        Determine if this agent can handle the task.

        Args:
            task: Task with type and requirements

        Returns:
            True if task is data modeling related
        """
        task_type = task.get("type", "").lower()
        keywords = [
            "model",
            "dbt",
            "dimension",
            "fact",
            "star schema",
            "data warehouse",
            "mart",
            "staging",
        ]
        return task_type in ["modeling", "data_modeling"] or any(
            kw in task.get("description", "").lower() for kw in keywords
        )

    async def execute(self, state: AgentState) -> AgentState:
        """
        Execute the data modeling workflow using LangGraph.

        This method now uses the ModelingWorkflow (LangGraph) to orchestrate
        the entire data modeling process from schema discovery to dbt generation.

        Args:
            state: Current agent state

        Returns:
            Updated state with generated artifacts
        """
        state.status = TaskStatus.IN_PROGRESS
        state.update_progress("starting", 0.0)

        try:
            # Initialize PostgresMCP client
            logger.info("Initializing PostgreSQL MCP client...")
            postgres_config = await self._get_postgres_config()
            postgres_mcp = PostgresMCP(postgres_config)
            await postgres_mcp.connect()

            # Initialize LLM client
            logger.info("Initializing LLM client...")
            llm_client = LLMClient()

            # Create modeling workflow
            logger.info("Creating modeling workflow...")
            workflow = ModelingWorkflow(
                mcp_client=postgres_mcp,
                llm_client=llm_client,
                workspace_path=state.workspace_path,
            )

            # Run the workflow
            logger.info("Running modeling workflow...")
            workflow_state = await workflow.run(
                requirements=state.requirements,
                data_source="postgres",
                project_name=state.parameters.get("project_name", "analytics_project"),
            )

            # Update agent state from workflow state
            state.discovered_context["schemas"] = workflow_state["available_schemas"]
            state.discovered_context["tables"] = workflow_state["discovered_tables"]
            state.discovered_context["profiles"] = workflow_state["data_profiles"]
            state.discovered_context["model_design"] = workflow_state["model_design"]
            state.generated_artifacts.update(workflow_state["generated_files"])

            # Update status
            if workflow_state["status"] == "completed":
                state.status = TaskStatus.COMPLETED
                state.update_progress("completed", 1.0)
                logger.info("Modeling workflow completed successfully")
            else:
                state.status = TaskStatus.FAILED
                state.errors.extend(workflow_state["errors"])
                logger.error(f"Modeling workflow failed: {workflow_state['errors']}")

            # Write to workspace
            if self.workspace and state.status == TaskStatus.COMPLETED:
                logger.info("Writing artifacts to workspace...")
                await self._write_to_workspace(state)

            # Cleanup
            await postgres_mcp.disconnect()

            # Log usage statistics
            usage = llm_client.get_total_usage()
            logger.info(
                f"Total LLM usage: {usage.total_tokens} tokens, ${usage.cost_usd:.4f}"
            )

        except Exception as e:
            logger.error(f"Execution failed: {str(e)}", exc_info=True)
            state.add_error(f"Execution failed: {str(e)}")
            state.status = TaskStatus.FAILED
            raise

        return state

    async def _get_postgres_config(self) -> Any:
        """Get PostgreSQL MCP server configuration."""
        from core.mcp.registry import MCPServerConfig
        from core.utils.config import settings

        # Get config from MCP registry or create from settings
        postgres_config = MCPServerConfig(
            name="postgres",
            type="database",
            capabilities=["query", "execute", "schema"],
            connection_config={
                "host": settings.postgres_host,
                "port": settings.postgres_port,
                "user": settings.postgres_user,
                "password": settings.postgres_password,
                "database": settings.postgres_database,
            },
            enabled=True,
        )

        return postgres_config

    async def _discover_sources(self, state: AgentState) -> None:
        """
        Discover available data sources from MCP registry.

        Args:
            state: Current agent state
        """
        # Get available database MCPs
        capabilities = await self.mcp_registry.get_capabilities()
        data_sources = capabilities.get("data_sources", [])

        state.data_sources = [{"name": ds, "type": "database"} for ds in data_sources]
        state.discovered_context["available_sources"] = data_sources

    async def _query_schemas(self, state: AgentState) -> None:
        """
        Query schemas from discovered data sources.

        Args:
            state: Current agent state
        """
        schemas = {}

        # For each data source, query its schema
        for source in state.data_sources:
            source_name = source["name"]
            try:
                # Query schema via MCP
                schema_info = await self.mcp_registry.query_source(
                    source_name,
                    "SELECT * FROM information_schema.tables LIMIT 10",
                )
                schemas[source_name] = schema_info
            except Exception as e:
                state.add_warning(f"Could not query schema for {source_name}: {str(e)}")

        state.schemas = schemas
        state.discovered_context["schemas"] = schemas

    async def _profile_data(self, state: AgentState) -> None:
        """
        Profile sample data from sources.

        Args:
            state: Current agent state
        """
        profiles = {}

        for source_name, schema in state.schemas.items():
            # Sample data and compute statistics
            # This would use the MCP to query sample data
            profiles[source_name] = {
                "row_count": 0,  # Placeholder
                "column_stats": {},
                "data_quality": {},
            }

        state.profiles = profiles
        state.discovered_context["profiles"] = profiles

    async def _design_model(self, state: AgentState) -> Dict[str, Any]:
        """
        Design dimensional model using LLM.

        This method uses Claude to:
        1. Understand the user requirements
        2. Analyze the available schemas
        3. Design appropriate facts and dimensions
        4. Define transformations

        Args:
            state: Current agent state

        Returns:
            Model design specification
        """
        # Build prompt for LLM
        prompt = self._build_modeling_prompt(state)

        # Call LLM (placeholder - actual implementation would use llm_client)
        # response = await self.llm.generate(prompt)

        # For now, return a simple star schema design
        design = {
            "model_type": "star_schema",
            "staging_models": [],
            "dimension_tables": [],
            "fact_tables": [],
            "relationships": [],
        }

        return design

    async def _generate_dbt_project(
        self,
        state: AgentState,
        model_design: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        Generate dbt project files.

        Args:
            state: Current agent state
            model_design: Model design specification

        Returns:
            Dictionary of file paths to contents
        """
        # This would use the DBTGenerator class
        # For now, return placeholder
        return {
            "dbt_project.yml": "name: my_project\nversion: 1.0.0\n",
            "models/schema.yml": "version: 2\nmodels: []\n",
        }

    async def _write_to_workspace(self, state: AgentState) -> None:
        """
        Write generated artifacts to workspace.

        Args:
            state: Current agent state
        """
        for file_path, content in state.generated_artifacts.items():
            self.workspace.write_file(file_path, content)

    def _build_modeling_prompt(self, state: AgentState) -> str:
        """
        Build prompt for LLM modeling task.

        Args:
            state: Current agent state

        Returns:
            Prompt string
        """
        prompt = f"""
You are a data modeling expert. Design a dimensional model based on:

User Requirements:
{state.requirements}

Available Sources:
{state.data_sources}

Schemas:
{state.schemas}

Design a star schema with appropriate facts and dimensions.
Return a JSON specification.
"""
        return prompt

    async def validate(self, artifacts: Dict[str, str]) -> List[str]:
        """
        Validate generated dbt artifacts.

        Args:
            artifacts: Generated dbt files

        Returns:
            List of validation errors
        """
        errors = []

        # Check required files
        required_files = ["dbt_project.yml"]
        for required in required_files:
            if required not in artifacts:
                errors.append(f"Missing required file: {required}")

        # Additional validation would use DBTValidator class

        return errors

    async def document(self, artifacts: Dict[str, str]) -> str:
        """
        Generate documentation for the dbt project.

        Args:
            artifacts: Generated dbt files

        Returns:
            README markdown
        """
        doc = """# dbt Project

## Overview
This dbt project was generated by DataForge.

## Structure
- `models/staging/` - Staging models
- `models/marts/` - Dimensional models (facts and dimensions)

## Usage
```bash
dbt run
dbt test
```

## Generated by DataForge
"""
        return doc
