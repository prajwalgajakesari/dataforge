"""
Example: Complete Data Modeling Workflow

This example demonstrates how to use DataForge to:
1. Connect to a PostgreSQL database
2. Discover schemas and tables
3. Design a star schema using AI
4. Generate a complete dbt project
5. Write to workspace with git integration

Prerequisites:
- PostgreSQL database with sample data
- Anthropic API key set in environment
- Environment variables configured (see .env.example)
"""

import asyncio
from pathlib import Path

from core.agents.base import AgentState, AgentType
from core.agents.modeling import DataModelingAgent
from core.mcp.registry import MCPRegistry
from core.utils.config import settings
from core.utils.llm_client import LLMClient
from core.utils.logger import get_logger
from core.workspace.manager import WorkspaceManager

logger = get_logger(__name__)


async def main():
    """Run the complete modeling workflow example."""
    logger.info("=" * 80)
    logger.info("DataForge - Data Modeling Workflow Example")
    logger.info("=" * 80)

    # Step 1: Initialize workspace
    logger.info("\n[1/5] Initializing workspace...")

    workspace_manager = WorkspaceManager()
    workspace = workspace_manager.create_workspace(
        name="ecommerce_analytics",
        project_type="dbt",
    )

    logger.info(f"✓ Created workspace: {workspace.path}")

    # Step 2: Initialize MCP Registry
    logger.info("\n[2/5] Initializing MCP registry...")

    mcp_registry = MCPRegistry()
    await mcp_registry.initialize()

    # Check available data sources
    capabilities = await mcp_registry.get_capabilities()
    logger.info(f"✓ Available data sources: {capabilities['data_sources']}")

    if not capabilities["data_sources"]:
        logger.warning(
            "⚠ No data sources available. Please configure MCP servers in ~/.dataforge/mcp-servers.yml"
        )
        return

    # Step 3: Initialize LLM Client
    logger.info("\n[3/5] Initializing LLM client...")

    try:
        llm_client = LLMClient()
        logger.info(f"✓ Using model: {llm_client.model}")
    except ValueError as e:
        logger.error(f"✗ Failed to initialize LLM client: {e}")
        logger.error("Please set ANTHROPIC_API_KEY in your environment")
        return

    # Step 4: Create and configure modeling agent
    logger.info("\n[4/5] Creating data modeling agent...")

    agent = DataModelingAgent(
        mcp_registry=mcp_registry,
        workspace_manager=workspace_manager,
        llm_client=llm_client,
    )

    logger.info(f"✓ Agent capabilities: {[cap.name for cap in agent.capabilities]}")

    # Step 5: Execute modeling workflow
    logger.info("\n[5/5] Executing modeling workflow...")
    logger.info("-" * 80)

    # Define requirements
    requirements = """
    Create an e-commerce analytics data mart with the following:

    1. Customer Dimension:
       - Customer demographics
       - Registration and lifetime value
       - Customer segments

    2. Product Dimension:
       - Product details
       - Category hierarchy
       - Pricing information

    3. Date Dimension:
       - Standard date attributes
       - Fiscal calendar

    4. Order Fact:
       - Order transactions
       - Order items and quantities
       - Revenue and discounts
       - Links to customer, product, and date dimensions
       - Grain: one row per order line item
    """

    # Create agent state
    state = AgentState(
        user_id="example_user",
        agent_type=AgentType.MODELING,
        workspace_path=str(workspace.path),
        requirements=requirements,
        parameters={
            "project_name": "ecommerce_analytics",
            "target_database": "analytics",
            "target_schema": "ecommerce",
        },
    )

    try:
        # Execute the workflow
        logger.info("Starting model generation...")
        result_state = await agent.execute(state)

        # Check results
        logger.info("-" * 80)
        logger.info("\n✓ Modeling workflow completed!")

        if result_state.status.value == "completed":
            logger.info(f"\nGenerated {len(result_state.generated_artifacts)} files:")

            # Show generated files
            for file_path in sorted(result_state.generated_artifacts.keys()):
                logger.info(f"  - {file_path}")

            # Show model design summary
            model_design = result_state.discovered_context.get("model_design", {})
            if model_design:
                logger.info(f"\nModel Design Summary:")
                logger.info(
                    f"  Staging Models: {len(model_design.get('staging_models', []))}"
                )
                logger.info(
                    f"  Dimensions: {len(model_design.get('dimensions', []))}"
                )
                logger.info(f"  Facts: {len(model_design.get('facts', []))}")

            # Show workspace info
            logger.info(f"\nWorkspace Location:")
            logger.info(f"  {workspace.path}")

            # Next steps
            logger.info("\nNext Steps:")
            logger.info(f"  1. cd {workspace.path}")
            logger.info("  2. Review generated dbt project")
            logger.info("  3. Configure ~/.dbt/profiles.yml with your database credentials")
            logger.info("  4. Run: dbt deps")
            logger.info("  5. Run: dbt run")
            logger.info("  6. Run: dbt test")

            # Show LLM usage
            usage = llm_client.get_total_usage()
            logger.info(f"\nLLM Usage:")
            logger.info(f"  Total Tokens: {usage.total_tokens:,}")
            logger.info(f"  Cost: ${usage.cost_usd:.4f}")

        else:
            logger.error("\n✗ Workflow failed!")
            logger.error(f"Errors: {result_state.errors}")

            if result_state.warnings:
                logger.warning(f"Warnings: {result_state.warnings}")

    except Exception as e:
        logger.error(f"\n✗ Workflow failed with exception: {e}", exc_info=True)

    finally:
        # Cleanup
        await mcp_registry.shutdown()
        logger.info("\n✓ Cleaned up resources")


async def example_with_custom_config():
    """
    Alternative example with custom configuration.

    This shows how to customize the workflow with specific parameters.
    """
    from core.mcp.registry import MCPServerConfig

    # Create custom PostgreSQL configuration
    custom_postgres_config = MCPServerConfig(
        name="custom_postgres",
        type="database",
        capabilities=["query", "execute", "schema"],
        connection_config={
            "host": "localhost",
            "port": 5432,
            "user": "analytics_user",
            "password": "secure_password",
            "database": "production_db",
        },
        enabled=True,
        timeout=60,
    )

    logger.info("Using custom PostgreSQL configuration")
    logger.info(f"  Host: {custom_postgres_config.connection_config['host']}")
    logger.info(f"  Database: {custom_postgres_config.connection_config['database']}")


async def example_with_streaming():
    """
    Example showing streaming workflow updates.

    This demonstrates how to get real-time updates during the workflow.
    """
    from core.graph.modeling_graph import ModelingWorkflow
    from core.mcp.servers.postgres_mcp import PostgresMCP
    from core.mcp.registry import MCPServerConfig

    logger.info("Example: Streaming Workflow Updates")

    # Setup (simplified for example)
    postgres_config = MCPServerConfig(
        name="postgres",
        type="database",
        capabilities=["query", "schema"],
        connection_config={
            "host": settings.postgres_host,
            "port": settings.postgres_port,
            "user": settings.postgres_user,
            "password": settings.postgres_password,
            "database": settings.postgres_database,
        },
        enabled=True,
    )

    postgres_mcp = PostgresMCP(postgres_config)
    await postgres_mcp.connect()

    llm_client = LLMClient()

    workspace_path = Path("./test_workspace")
    workspace_path.mkdir(exist_ok=True)

    workflow = ModelingWorkflow(
        mcp_client=postgres_mcp,
        llm_client=llm_client,
        workspace_path=str(workspace_path),
    )

    # Stream workflow updates
    requirements = "Create a simple customer analytics mart"

    async for state in workflow.stream(requirements=requirements):
        logger.info(f"Step: {state['current_step']} - Progress: {state['progress']:.0%}")

        if state["errors"]:
            logger.error(f"Errors: {state['errors']}")

    await postgres_mcp.disconnect()


if __name__ == "__main__":
    # Run the main example
    asyncio.run(main())

    # Uncomment to run alternative examples:
    # asyncio.run(example_with_custom_config())
    # asyncio.run(example_with_streaming())
