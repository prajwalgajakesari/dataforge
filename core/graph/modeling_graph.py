"""
LangGraph workflow for Data Modeling Agent.

This module defines the state graph for the data modeling workflow,
orchestrating the steps from schema discovery to dbt project generation.
"""

from typing import Any, AsyncIterator, Dict, List, Literal, TypedDict, Optional

from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field

from core.agents.base import AgentEvent, AgentState, TaskStatus
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
from core.mcp.servers.postgres_mcp import PostgresColumn, PostgresMCP, PostgresTable
from core.utils.llm_client import LLMClient
from core.utils.logger import get_logger
from core.prompts import modeling as prompts

logger = get_logger(__name__)


class ModelingState(TypedDict):
    """State for the modeling workflow."""

    # Input
    requirements: str
    data_source: str
    workspace_path: str
    modeling_strategy: Literal["STAR_SCHEMA", "NORMALIZED_3NF", "DATA_VAULT"]
    auto_generate: bool

    # Discovery
    available_schemas: List[Dict[str, Any]]
    selected_schema: str
    discovered_tables: List[Dict[str, Any]]
    data_profiles: Dict[str, List[Dict[str, Any]]]

    # Design
    model_design: Dict[str, Any]

    # Generation
    generated_files: Dict[str, str]

    # Status
    current_step: str
    status: str
    errors: List[str]
    warnings: List[str]
    progress: float


class StarSchemaDesign(BaseModel):
    """LLM output for star schema design."""
    
    reasoning: str
    staging_models: List[Dict[str, Any]]
    dimensions: List[Dict[str, Any]]
    facts: List[Dict[str, Any]]


class NormalizedDesign(BaseModel):
    """LLM output for Normalized (3NF) design."""
    
    reasoning: str
    entities: List[Dict[str, Any]] = Field(description="List of normalized entities (tables)")
    relationships: List[Dict[str, Any]] = Field(description="List of relationships between entities")


class DataVaultDesign(BaseModel):
    """LLM output for Data Vault 2.0 design."""
    
    reasoning: str
    hubs: List[Dict[str, Any]]
    links: List[Dict[str, Any]]
    satellites: List[Dict[str, Any]]


class ModelingWorkflow:
    """
    LangGraph workflow for data modeling.

    This workflow orchestrates the end-to-end data modeling process:
    1. Discover schemas and tables from data source
    2. Profile sample data
    3. Design schema (Star, 3NF, or Data Vault) with LLM
    4. Generate dbt project
    5. Validate and document

    The workflow is implemented as a StateGraph with nodes for each step
    and conditional edges for error handling and decision making.
    """

    def __init__(
        self,
        mcp_client: PostgresMCP,
        llm_client: LLMClient,
        workspace_path: str,
    ):
        """
        Initialize the modeling workflow.

        Args:
            mcp_client: PostgreSQL MCP client for schema discovery
            llm_client: LLM client for model design
            workspace_path: Path to workspace for file generation
        """
        self.mcp_client = mcp_client
        self.llm_client = llm_client
        self.workspace_path = workspace_path
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph state graph."""
        # Create graph
        workflow = StateGraph(ModelingState)

        # Add nodes
        workflow.add_node("discover_schemas", self.discover_schemas_node)
        workflow.add_node("select_schema", self.select_schema_node)
        workflow.add_node("discover_tables", self.discover_tables_node)
        workflow.add_node("profile_data", self.profile_data_node)
        workflow.add_node("design_model", self.design_model_node)
        workflow.add_node("generate_dbt", self.generate_dbt_node)
        workflow.add_node("validate", self.validate_node)
        workflow.add_node("handle_error", self.handle_error_node)

        # Set entry point
        workflow.set_entry_point("discover_schemas")

        # Add edges
        workflow.add_edge("discover_schemas", "select_schema")
        workflow.add_edge("select_schema", "discover_tables")
        workflow.add_edge("discover_tables", "profile_data")
        workflow.add_edge("profile_data", "design_model")
        
        # Conditional edge for generation
        workflow.add_conditional_edges(
            "design_model",
            self.should_generate,
            {
                "continue": "generate_dbt",
                "stop": END,
            }
        )
        
        workflow.add_edge("generate_dbt", "validate")

        # Conditional edge for validation
        workflow.add_conditional_edges(
            "validate",
            self.should_continue,
            {
                "end": END,
                "error": "handle_error",
            },
        )

        workflow.add_edge("handle_error", END)

        return workflow.compile()

    async def discover_schemas_node(self, state: ModelingState) -> ModelingState:
        """Discover available schemas from the database."""
        logger.info("Discovering schemas...")

        try:
            schemas = await self.mcp_client.discover_schemas(exclude_system=True)

            state["available_schemas"] = [
                {
                    "name": schema.schema_name,
                    "table_count": len(schema.tables),
                }
                for schema in schemas
            ]

            state["current_step"] = "discover_schemas"
            state["progress"] = 0.1

            logger.info(f"Discovered {len(schemas)} schemas")

        except Exception as e:
            logger.error(f"Schema discovery failed: {e}")
            state["errors"].append(f"Schema discovery failed: {e}")
            state["status"] = "failed"

        return state

    async def select_schema_node(self, state: ModelingState) -> ModelingState:
        """Select the most relevant schema using LLM."""
        logger.info("Selecting relevant schema...")

        try:
            # Use LLM to select the most relevant schema
            prompt = f"""Given the user's requirements and available schemas, select the most relevant schema to use.

User Requirements:
{state['requirements']}

Available Schemas:
{chr(10).join(f"- {s['name']} ({s['table_count']} tables)" for s in state['available_schemas'])}

Respond with ONLY the schema name, nothing else.
"""

            response = await self.llm_client.generate(
                prompt=prompt,
                system="You are a data modeling expert. Select the most relevant schema based on the requirements.",
                temperature=0.0,
            )

            selected = response.content.strip()

            # Validate selection
            available_names = [s["name"] for s in state["available_schemas"]]
            if selected not in available_names:
                # Default to first schema
                selected = available_names[0] if available_names else "public"

            state["selected_schema"] = selected
            state["current_step"] = "select_schema"
            state["progress"] = 0.2

            logger.info(f"Selected schema: {selected}")

        except Exception as e:
            logger.error(f"Schema selection failed: {e}")
            state["errors"].append(f"Schema selection failed: {e}")
            state["status"] = "failed"

        return state

    async def discover_tables_node(self, state: ModelingState) -> ModelingState:
        """Discover tables in the selected schema."""
        logger.info(f"Discovering tables in schema: {state['selected_schema']}...")

        try:
            tables = await self.mcp_client.discover_tables(state["selected_schema"])

            state["discovered_tables"] = [
                {
                    "schema": table.table_schema,
                    "name": table.table_name,
                    "type": table.table_type,
                    "row_count": table.row_count,
                    "columns": [
                        {
                            "name": col.column_name,
                            "data_type": col.data_type,
                            "is_nullable": col.is_nullable,
                            "is_primary_key": col.is_primary_key,
                            "is_foreign_key": col.is_foreign_key,
                            "foreign_key_table": col.foreign_key_table,
                            "foreign_key_column": col.foreign_key_column,
                        }
                        for col in table.columns
                    ],
                }
                for table in tables
            ]

            state["current_step"] = "discover_tables"
            state["progress"] = 0.3

            logger.info(f"Discovered {len(tables)} tables")

        except Exception as e:
            logger.error(f"Table discovery failed: {e}")
            state["errors"].append(f"Table discovery failed: {e}")
            state["status"] = "failed"

        return state

    async def profile_data_node(self, state: ModelingState) -> ModelingState:
        """Profile data for selected tables."""
        logger.info("Profiling data...")

        try:
            profiles = {}

            # Profile up to 5 tables (or all if fewer)
            tables_to_profile = state["discovered_tables"][:5]

            for table in tables_to_profile:
                table_name = table["name"]
                schema_name = table["schema"]

                try:
                    table_profiles = await self.mcp_client.profile_table(
                        schema_name=schema_name,
                        table_name=table_name,
                        sample_size=100,
                    )

                    profiles[table_name] = [p.model_dump() for p in table_profiles]

                except Exception as e:
                    logger.warning(f"Could not profile table {table_name}: {e}")
                    state["warnings"].append(f"Could not profile {table_name}: {e}")

            state["data_profiles"] = profiles
            state["current_step"] = "profile_data"
            state["progress"] = 0.5

            logger.info(f"Profiled {len(profiles)} tables")

        except Exception as e:
            logger.error(f"Data profiling failed: {e}")
            state["errors"].append(f"Data profiling failed: {e}")
            state["status"] = "failed"

        return state

    async def design_model_node(self, state: ModelingState) -> ModelingState:
        """Design schema using LLM based on strategy."""
        logger.info(f"Designing data model with strategy: {state['modeling_strategy']}...")

        try:
            strategy = state["modeling_strategy"]
            
            if strategy == "NORMALIZED_3NF":
                prompt = prompts.build_normalized_3nf_prompt(state)
                response_model = NormalizedDesign
                system = "You are an expert data architect specializing in 3NF and relational database design. Eliminate redundancy."
            elif strategy == "DATA_VAULT":
                prompt = prompts.build_data_vault_prompt(state)
                response_model = DataVaultDesign
                system = "You are an expert in Data Vault 2.0 methodology. Focus on Hubs, Links, and Satellites."
            else:
                # Default to Star Schema
                prompt = prompts.build_star_schema_prompt(state)
                response_model = StarSchemaDesign
                system = "You are an expert data modeler specializing in dimensional modeling and star schemas."

            # Use LLM to design the model
            design, response = await self.llm_client.generate_structured(
                prompt=prompt,
                response_model=response_model,
                system=system,
                temperature=0.0,
            )

            logger.info(f"Model design reasoning: {design.reasoning}")
            
            state["model_design"] = design.model_dump()
            state["current_step"] = "design_model"
            state["progress"] = 0.7

        except Exception as e:
            logger.error(f"Model design failed: {e}")
            state["errors"].append(f"Model design failed: {e}")
            state["status"] = "failed"

        return state

    async def generate_dbt_node(self, state: ModelingState) -> ModelingState:
        """Generate dbt project from design."""
        logger.info("Generating dbt project...")

        # Skip generation for non-star-schema for now (as DBTGenerator is specialized for Star Schema)
        if state["modeling_strategy"] != "STAR_SCHEMA":
             logger.info(f"Skipping dbt generation for {state['modeling_strategy']} (Not yet implemented)")
             state["current_step"] = "generate_dbt"
             state["progress"] = 0.9
             return state

        try:
            # Convert design to ModelDesign format
            model_design = self._convert_to_model_design(state)

            # Generate dbt project
            generator = DBTGenerator(
                project_name=state.get("project_name", "analytics_project"),
                target_dir=state["workspace_path"],
            )

            generated_files = generator.generate_project(model_design)

            state["generated_files"] = generated_files
            state["current_step"] = "generate_dbt"
            state["progress"] = 0.9

            logger.info(f"Generated {len(generated_files)} files")

        except Exception as e:
            logger.error(f"dbt generation failed: {e}")
            state["errors"].append(f"dbt generation failed: {e}")
            state["status"] = "failed"

        return state

    async def validate_node(self, state: ModelingState) -> ModelingState:
        """Validate generated files."""
        logger.info("Validating generated files...")

        try:
            # Skip validation if no files generated (non-star implementation)
            if not state.get("generated_files"):
                state["status"] = "completed"
                state["progress"] = 1.0
                return state

            # Basic validation
            required_files = ["dbt_project.yml", "models/staging/sources.yml"]

            for required in required_files:
                if required not in state["generated_files"]:
                    state["errors"].append(f"Missing required file: {required}")

            if not state["errors"]:
                state["status"] = "completed"
                state["progress"] = 1.0
                logger.info("Validation successful")
            else:
                state["status"] = "failed"
                logger.error(f"Validation failed: {state['errors']}")

            state["current_step"] = "validate"

        except Exception as e:
            logger.error(f"Validation failed: {e}")
            state["errors"].append(f"Validation failed: {e}")
            state["status"] = "failed"

        return state

    async def handle_error_node(self, state: ModelingState) -> ModelingState:
        """Handle errors in the workflow."""
        logger.error(f"Workflow failed at step {state['current_step']}")
        logger.error(f"Errors: {state['errors']}")

        state["status"] = "failed"
        return state

    def should_continue(self, state: ModelingState) -> Literal["end", "error"]:
        """Determine if workflow should continue or handle error."""
        if state["status"] == "completed":
            return "end"
        elif state["errors"]:
            return "error"
        return "end"

    def should_generate(self, state: ModelingState) -> Literal["continue", "stop"]:
        """Determine if we should proceed to generation."""
        if state.get("auto_generate", False):
            return "continue"
        return "stop"

    def _convert_to_model_design(self, state: ModelingState) -> ModelDesign:
        """Convert LLM design output to ModelDesign format."""
        
        # Only implemented for StarSchemaDesign currently
        if state["modeling_strategy"] != "STAR_SCHEMA":
             raise NotImplementedError("Only Star Schema supported for code generation")

        design_dict = state["model_design"]

        # Create source definitions
        sources = []
        source_tables_map = {}

        for table in state["discovered_tables"]:
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
                        is_nullable=col["is_nullable"],
                        is_primary_key=col["is_primary_key"],
                        is_foreign_key=col["is_foreign_key"],
                        foreign_key_table=col.get("foreign_key_table"),
                        foreign_key_column=col.get("foreign_key_column"),
                    )
                    for col in table["columns"]
                ],
                row_count=table.get("row_count"),
            )

            source.tables.append(table_def)
            source_tables_map[table["name"]] = table_def

        # Create staging models
        staging_models = []
        for stg in design_dict["staging_models"]:
            # Find source table
            source_table = source_tables_map.get(stg.get("source_table", stg["name"]))
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
                        for col in stg["columns"]
                    ],
                    description=stg["description"],
                )
            )

        # Create dimension models
        dimension_models = []
        for dim in design_dict["dimensions"]:
            dimension_models.append(
                DimensionModelDefinition(
                    name=dim["name"],
                    source_models=dim["source_models"],
                    columns=[
                        ColumnDefinition(
                            name=col["name"],
                            data_type=col["data_type"],
                            description=col.get("description"),
                            is_nullable=col.get("is_nullable", True),
                            is_primary_key=col.get("is_primary_key", False),
                        )
                        for col in dim["columns"]
                    ],
                    description=dim["description"],
                    slowly_changing_type=dim.get("scd_type", 1),
                )
            )

        # Create fact models
        fact_models = []
        for fact in design_dict["facts"]:
            fact_models.append(
                FactModelDefinition(
                    name=fact["name"],
                    source_models=fact["source_models"],
                    grain=fact["grain"],
                    columns=[
                        ColumnDefinition(
                            name=col["name"],
                            data_type=col["data_type"],
                            description=col.get("description"),
                            is_nullable=col.get("is_nullable", True),
                            is_primary_key=col.get("is_primary_key", False),
                        )
                        for col in fact["columns"]
                    ],
                    measures=fact["measures"],
                    dimensions=fact["dimensions"],
                    description=fact["description"],
                )
            )

        return ModelDesign(
            project_name=state.get("project_name", "analytics_project"),
            sources=sources,
            staging_models=staging_models,
            dimension_models=dimension_models,
            fact_models=fact_models,
        )

    async def run(
        self,
        requirements: str,
        data_source: str = "postgres",
        project_name: str = "analytics_project",
        modeling_strategy: Literal["STAR_SCHEMA", "NORMALIZED_3NF", "DATA_VAULT"] = "STAR_SCHEMA",
        auto_generate: bool = False,
    ) -> ModelingState:
        """
        Run the modeling workflow.

        Args:
            requirements: User requirements for the data model
            data_source: Name of the data source to use
            project_name: Name for the generated dbt project
            modeling_strategy: Strategy to use for modeling

        Returns:
            Final state with generated files
        """
        # Initialize state
        initial_state: ModelingState = {
            "requirements": requirements,
            "data_source": data_source,
            "workspace_path": self.workspace_path,
            "project_name": project_name,
            "modeling_strategy": modeling_strategy,
            "auto_generate": auto_generate,
            "available_schemas": [],
            "selected_schema": "",
            "discovered_tables": [],
            "data_profiles": {},
            "model_design": {},
            "generated_files": {},
            "current_step": "initialized",
            "status": "pending",
            "errors": [],
            "warnings": [],
            "progress": 0.0,
        }

        # Run the graph
        logger.info(f"Starting modeling workflow ({modeling_strategy})...")
        final_state = await self.graph.ainvoke(initial_state)

        logger.info(f"Workflow completed with status: {final_state['status']}")
        return final_state


    async def stream(
        self,
        requirements: str,
        data_source: str = "postgres",
        project_name: str = "analytics_project",
        modeling_strategy: Literal["STAR_SCHEMA", "NORMALIZED_3NF", "DATA_VAULT"] = "STAR_SCHEMA",
    ) -> AsyncIterator[ModelingState]:
        """
        Stream the modeling workflow with updates at each step.

        Args:
            requirements: User requirements for the data model
            data_source: Name of the data source to use
            project_name: Name for the generated dbt project
            modeling_strategy: Strategy to use for modeling

        Yields:
            State updates at each step
        """
        # Initialize state
        initial_state: ModelingState = {
            "requirements": requirements,
            "data_source": data_source,
            "workspace_path": self.workspace_path,
            "project_name": project_name,
            "modeling_strategy": modeling_strategy,
            "available_schemas": [],
            "selected_schema": "",
            "discovered_tables": [],
            "data_profiles": {},
            "model_design": {},
            "generated_files": {},
            "current_step": "initialized",
            "status": "pending",
            "errors": [],
            "warnings": [],
            "progress": 0.0,
        }

        # Stream the graph
        logger.info(f"Starting modeling workflow ({modeling_strategy}) with streaming...")

        async for state in self.graph.astream(initial_state):
            # LangGraph astream yields (node_name, state) tuples
            if isinstance(state, tuple):
                node_name, node_state = state
                yield node_state
            else:
                yield state

    # Helper to allow resuming/triggering generation manually
    async def generate_code(self, state: ModelingState) -> ModelingState:
        """Manually trigger code generation from a state."""
        return await self.generate_dbt_node(state)
