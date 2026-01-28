"""
LangGraph workflow for Data Modeling Agent.

This module defines the state graph for the data modeling workflow,
orchestrating the steps from schema discovery to dbt project generation.

The workflow uses modular nodes from core.graph.nodes for:
- Discovery: Schema and table discovery
- Profiling: Data profiling and statistics
- Analysis: Dependency detection and relationship inference
- Design: LLM-assisted model design
- Generation: dbt project generation
- Validation: Output validation
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

# Import modular nodes
from core.graph.nodes import (
    discover_schemas,
    discover_tables,
    select_schema,
    profile_tables,
    analyze_dependencies,
    infer_relationships,
    analyze_keys,
    create_design,
    validate_design,
    generate_output,
    validate_output,
)

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

    # Analysis (new fields for enhanced analysis)
    functional_dependencies: Dict[str, List[Dict]]  # table -> list of FD dicts
    normalization_analysis: Dict[str, Dict[str, Any]]  # table -> normalization info
    candidate_keys: Dict[str, List[Dict]]  # table -> list of candidate key dicts
    key_analysis: Dict[str, Dict[str, Any]]  # table -> key analysis results
    inferred_relationships: List[Dict]  # list of relationship dicts
    semantic_types: Dict[str, Dict[str, str]]  # table -> column -> SemanticType

    # Design
    model_design: Dict[str, Any]
    design_reasoning: str  # LLM reasoning for design decisions
    design_is_valid: bool  # Result of design validation

    # Generation
    generated_files: Dict[str, str]

    # Validation (new fields for validation results)
    schema_validation: Dict[str, Any]  # Schema validation report
    design_validation: Dict[str, Any]  # Design validation report
    output_validation: Dict[str, Any]  # Output validation report

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

        # Add nodes - using modular nodes where available
        workflow.add_node("discover_schemas", self.discover_schemas_node)
        workflow.add_node("select_schema", self.select_schema_node)
        workflow.add_node("discover_tables", self.discover_tables_node)
        workflow.add_node("profile_data", self.profile_data_node)
        workflow.add_node("analyze_data", self.analyze_data_node)  # New analysis step
        workflow.add_node("design_model", self.design_model_node)
        workflow.add_node("validate_design", self.validate_design_node)  # New design validation
        workflow.add_node("generate_dbt", self.generate_dbt_node)
        workflow.add_node("validate", self.validate_node)
        workflow.add_node("handle_error", self.handle_error_node)

        # Set entry point
        workflow.set_entry_point("discover_schemas")

        # Add edges - updated flow with analysis and validation steps
        workflow.add_edge("discover_schemas", "select_schema")
        workflow.add_edge("select_schema", "discover_tables")
        workflow.add_edge("discover_tables", "profile_data")
        workflow.add_edge("profile_data", "analyze_data")  # New: profiling -> analysis
        workflow.add_edge("analyze_data", "design_model")  # New: analysis -> design

        # Conditional edge after design - validate or skip
        workflow.add_conditional_edges(
            "design_model",
            self.should_validate_design,
            {
                "validate": "validate_design",
                "skip": "generate_dbt",
                "stop": END,
            }
        )

        # Conditional edge after design validation
        workflow.add_conditional_edges(
            "validate_design",
            self.check_design_validation,
            {
                "continue": "generate_dbt",
                "retry": "design_model",  # Re-design if validation fails
                "stop": END,
            }
        )

        workflow.add_edge("generate_dbt", "validate")

        # Conditional edge for output validation
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
            state["progress"] = 0.4

            logger.info(f"Profiled {len(profiles)} tables")

        except Exception as e:
            logger.error(f"Data profiling failed: {e}")
            state["errors"].append(f"Data profiling failed: {e}")
            state["status"] = "failed"

        return state

    async def analyze_data_node(self, state: ModelingState) -> ModelingState:
        """
        Analyze data for functional dependencies, keys, and relationships.

        This node combines analysis from multiple sub-nodes:
        - Functional dependency detection
        - Candidate key discovery
        - Relationship inference
        """
        logger.info("Analyzing data dependencies and relationships...")

        try:
            # Initialize analysis result fields
            state["functional_dependencies"] = {}
            state["normalization_analysis"] = {}
            state["candidate_keys"] = {}
            state["key_analysis"] = {}
            state["inferred_relationships"] = []
            state["semantic_types"] = {}

            schema_name = state.get("selected_schema", "public")
            tables = state.get("discovered_tables", [])

            # Skip if no tables
            if not tables:
                logger.warning("No tables to analyze")
                state["current_step"] = "analyze_data"
                state["progress"] = 0.5
                return state

            # Analyze each table for FDs and keys (simplified version)
            for table in tables[:5]:  # Limit to 5 tables
                table_name = table["name"]
                columns = table.get("columns", [])

                try:
                    # Extract potential keys from column metadata
                    pk_columns = [
                        col["name"] for col in columns if col.get("is_primary_key")
                    ]
                    fk_columns = [
                        col for col in columns if col.get("is_foreign_key")
                    ]

                    # Store key analysis
                    state["key_analysis"][table_name] = {
                        "primary_key": pk_columns if pk_columns else None,
                        "foreign_keys": [
                            {
                                "column": col["name"],
                                "references_table": col.get("foreign_key_table"),
                                "references_column": col.get("foreign_key_column"),
                            }
                            for col in fk_columns
                        ],
                        "candidate_keys": [
                            {
                                "columns": pk_columns,
                                "is_minimal": True,
                                "uniqueness": 1.0,
                            }
                        ] if pk_columns else [],
                    }

                    # Store semantic type inference
                    state["semantic_types"][table_name] = {
                        col["name"]: self._infer_semantic_type(col)
                        for col in columns
                    }

                except Exception as e:
                    logger.warning(f"Could not analyze table {table_name}: {e}")
                    state["warnings"].append(f"Analysis failed for {table_name}: {e}")

            # Infer relationships from FK metadata
            for table in tables:
                table_name = table["name"]
                for col in table.get("columns", []):
                    if col.get("is_foreign_key") and col.get("foreign_key_table"):
                        state["inferred_relationships"].append({
                            "from_table": table_name,
                            "from_column": col["name"],
                            "to_table": col["foreign_key_table"],
                            "to_column": col.get("foreign_key_column", "id"),
                            "cardinality": "1:N",
                            "confidence": "high",
                            "is_explicit_fk": True,
                        })

            state["current_step"] = "analyze_data"
            state["progress"] = 0.5

            logger.info(
                f"Analyzed {len(state['key_analysis'])} tables, "
                f"found {len(state['inferred_relationships'])} relationships"
            )

        except Exception as e:
            logger.error(f"Data analysis failed: {e}")
            state["errors"].append(f"Data analysis failed: {e}")
            # Don't fail the workflow on analysis errors - continue with design
            state["warnings"].append("Proceeding with limited analysis data")

        return state

    def _infer_semantic_type(self, column: Dict[str, Any]) -> str:
        """Infer semantic type from column metadata."""
        name = column.get("name", "").lower()
        data_type = column.get("data_type", "").lower()

        # Primary/Foreign key detection
        if column.get("is_primary_key"):
            return "primary_key"
        if column.get("is_foreign_key"):
            return "foreign_key"

        # Common patterns
        if "email" in name:
            return "email"
        if "phone" in name or "mobile" in name:
            return "phone"
        if name.endswith("_at") or name.endswith("_date") or "timestamp" in data_type:
            return "timestamp"
        if "price" in name or "amount" in name or "cost" in name:
            return "currency"
        if name.startswith("is_") or name.startswith("has_") or "boolean" in data_type:
            return "boolean"
        if "uuid" in data_type:
            return "uuid"
        if name.endswith("_id"):
            return "foreign_key"

        return "unknown"

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

            # Enhance prompt with analysis results if available
            prompt = self._enhance_prompt_with_analysis(prompt, state)

            # Use LLM to design the model
            design, response = await self.llm_client.generate_structured(
                prompt=prompt,
                response_model=response_model,
                system=system,
                temperature=0.0,
            )

            logger.info(f"Model design reasoning: {design.reasoning}")

            state["model_design"] = design.model_dump()
            state["design_reasoning"] = design.reasoning
            state["current_step"] = "design_model"
            state["progress"] = 0.7

        except Exception as e:
            logger.error(f"Model design failed: {e}")
            state["errors"].append(f"Model design failed: {e}")
            state["status"] = "failed"

        return state

    def _enhance_prompt_with_analysis(
        self, prompt: str, state: ModelingState
    ) -> str:
        """Enhance the design prompt with analysis results."""
        additions = []

        # Add relationship information
        relationships = state.get("inferred_relationships", [])
        if relationships:
            rel_lines = ["## Inferred Relationships"]
            for rel in relationships[:10]:  # Limit to 10
                from_col = f"{rel['from_table']}.{rel['from_column']}"
                to_col = f"{rel['to_table']}.{rel['to_column']}"
                rel_type = "FK" if rel.get("is_explicit_fk") else "inferred"
                rel_lines.append(f"- {from_col} -> {to_col} ({rel_type})")
            if len(relationships) > 10:
                rel_lines.append(f"  ... and {len(relationships) - 10} more")
            additions.append("\n".join(rel_lines))

        # Add key analysis summary
        key_analysis = state.get("key_analysis", {})
        if key_analysis:
            key_lines = ["## Key Analysis"]
            for table_name, analysis in key_analysis.items():
                pk = analysis.get("primary_key")
                if pk:
                    key_lines.append(f"- {table_name}: PK = {', '.join(pk)}")
            additions.append("\n".join(key_lines))

        # Add semantic type hints
        semantic_types = state.get("semantic_types", {})
        if semantic_types:
            type_lines = ["## Column Semantic Types"]
            for table_name, columns in list(semantic_types.items())[:5]:
                important_cols = [
                    f"{col}: {stype}"
                    for col, stype in columns.items()
                    if stype not in ("unknown", "attribute")
                ]
                if important_cols:
                    type_lines.append(f"- {table_name}: {', '.join(important_cols[:5])}")
            additions.append("\n".join(type_lines))

        if additions:
            return prompt + "\n\n" + "\n\n".join(additions)
        return prompt

    async def validate_design_node(self, state: ModelingState) -> ModelingState:
        """Validate the generated model design."""
        logger.info("Validating model design...")

        try:
            design = state.get("model_design", {})
            strategy = state.get("modeling_strategy", "STAR_SCHEMA")

            issues = []
            metrics = {}

            if strategy == "STAR_SCHEMA":
                # Validate star schema design
                staging = design.get("staging_models", [])
                dimensions = design.get("dimensions", [])
                facts = design.get("facts", [])

                if not facts:
                    issues.append("Star schema should have at least one fact table")
                if not dimensions:
                    issues.append("Star schema should have dimension tables")

                metrics = {
                    "staging_count": len(staging),
                    "dimension_count": len(dimensions),
                    "fact_count": len(facts),
                }

            elif strategy == "DATA_VAULT":
                # Validate data vault design
                hubs = design.get("hubs", [])
                links = design.get("links", [])
                satellites = design.get("satellites", [])

                if not hubs:
                    issues.append("Data Vault must have at least one hub")

                metrics = {
                    "hub_count": len(hubs),
                    "link_count": len(links),
                    "satellite_count": len(satellites),
                }

            elif strategy == "NORMALIZED_3NF":
                # Validate 3NF design
                entities = design.get("entities", [])
                relationships = design.get("relationships", [])

                if not entities:
                    issues.append("3NF design should have entities")

                metrics = {
                    "entity_count": len(entities),
                    "relationship_count": len(relationships),
                }

            is_valid = len(issues) == 0

            state["design_validation"] = {
                "is_valid": is_valid,
                "issues": issues,
                "metrics": metrics,
                "strategy": strategy,
            }
            state["design_is_valid"] = is_valid

            if issues:
                for issue in issues:
                    state["warnings"].append(f"Design validation: {issue}")

            state["current_step"] = "validate_design"
            state["progress"] = 0.75

            logger.info(f"Design validation: valid={is_valid}, issues={len(issues)}")

        except Exception as e:
            logger.error(f"Design validation failed: {e}")
            state["warnings"].append(f"Design validation skipped: {e}")
            state["design_is_valid"] = True  # Don't block on validation failures
            state["design_validation"] = {"is_valid": True, "error": str(e)}

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

    def should_validate_design(
        self, state: ModelingState
    ) -> Literal["validate", "skip", "stop"]:
        """Determine if design should be validated before generation."""
        # If no design was generated, stop
        if not state.get("model_design"):
            return "stop"

        # If auto_generate is disabled, skip to end
        if not state.get("auto_generate", False):
            return "stop"

        # Validate the design if we have analysis data
        if state.get("functional_dependencies") or state.get("inferred_relationships"):
            return "validate"

        # Skip validation if no analysis data available
        return "skip"

    def check_design_validation(
        self, state: ModelingState
    ) -> Literal["continue", "retry", "stop"]:
        """Check design validation results and decide next step."""
        validation = state.get("design_validation", {})

        # If validation passed, continue to generation
        if validation.get("is_valid", True):
            return "continue"

        # Check if we should retry (only once to avoid infinite loops)
        retry_count = state.get("_design_retry_count", 0)
        if retry_count < 1 and validation.get("issues"):
            # Set retry count to prevent infinite loops
            state["_design_retry_count"] = retry_count + 1
            logger.info("Design validation failed, retrying design generation...")
            return "retry"

        # If auto_generate is disabled or max retries reached, stop
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
        # Initialize state with all required fields
        initial_state: ModelingState = {
            # Input
            "requirements": requirements,
            "data_source": data_source,
            "workspace_path": self.workspace_path,
            "project_name": project_name,
            "modeling_strategy": modeling_strategy,
            "auto_generate": auto_generate,
            # Discovery
            "available_schemas": [],
            "selected_schema": "",
            "discovered_tables": [],
            "data_profiles": {},
            # Analysis (new fields)
            "functional_dependencies": {},
            "normalization_analysis": {},
            "candidate_keys": {},
            "key_analysis": {},
            "inferred_relationships": [],
            "semantic_types": {},
            # Design
            "model_design": {},
            "design_reasoning": "",
            "design_is_valid": False,
            # Generation
            "generated_files": {},
            # Validation (new fields)
            "schema_validation": {},
            "design_validation": {},
            "output_validation": {},
            # Status
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
        # Initialize state with all required fields
        initial_state: ModelingState = {
            # Input
            "requirements": requirements,
            "data_source": data_source,
            "workspace_path": self.workspace_path,
            "project_name": project_name,
            "modeling_strategy": modeling_strategy,
            "auto_generate": False,  # Default for streaming
            # Discovery
            "available_schemas": [],
            "selected_schema": "",
            "discovered_tables": [],
            "data_profiles": {},
            # Analysis (new fields)
            "functional_dependencies": {},
            "normalization_analysis": {},
            "candidate_keys": {},
            "key_analysis": {},
            "inferred_relationships": [],
            "semantic_types": {},
            # Design
            "model_design": {},
            "design_reasoning": "",
            "design_is_valid": False,
            # Generation
            "generated_files": {},
            # Validation (new fields)
            "schema_validation": {},
            "design_validation": {},
            "output_validation": {},
            # Status
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
