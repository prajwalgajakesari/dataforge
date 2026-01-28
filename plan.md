# Technical Implementation Document: DataForge
## Automated Data Engineering Platform

**Version:** 1.0  
**Date:** October 12, 2025  
**Status:** Design Phase

---

## Executive Summary

DataForge is an AI-powered data engineering platform that enables users to build complete data infrastructure through natural conversation. Starting with automated data modeling (Phase 1), expanding to ETL pipeline generation (Phase 2), and culminating in full-stack data infrastructure automation (Phase 3).

**Core Vision:** "Claude Code for Data Engineers"

**Primary User Flow:**
```
User describes requirements in natural language
    ↓
AI Agent analyzes available data sources
    ↓
Generates production-ready code (dbt, Airflow, Terraform)
    ↓
Deploys to target infrastructure
```

---

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Core Components](#core-components)
3. [Agent System Design](#agent-system-design)
4. [MCP Integration Layer](#mcp-integration-layer)
5. [Data Flow & Workflows](#data-flow--workflows)
6. [Interface Specifications](#interface-specifications)
7. [Code Generation Engines](#code-generation-engines)
8. [Implementation Phases](#implementation-phases)
9. [Technical Stack](#technical-stack)
10. [Security & Compliance](#security--compliance)
11. [Testing Strategy](#testing-strategy)
12. [Deployment Architecture](#deployment-architecture)

---

## 1. System Architecture

### 1.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Interface Layer                             │
│  ┌──────────────┐  ┌──────────┐  ┌──────────────────────────┐  │
│  │   VSCode     │  │   CLI    │  │   Web Dashboard          │  │
│  │  Extension   │  │  (Typer) │  │   (React - Optional)     │  │
│  └──────┬───────┘  └────┬─────┘  └───────────┬──────────────┘  │
└─────────┼────────────────┼────────────────────┼─────────────────┘
          │                │                    │
          └────────────────┴────────────────────┘
                           │
                  ┌────────▼─────────┐
                  │   API Gateway    │
                  │   (FastAPI)      │
                  │   + WebSocket    │
                  └────────┬─────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                  Agent Orchestration Layer                       │
│                     (LangGraph Core)                             │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │            Multi-Agent System                            │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌─────────────────┐ │   │
│  │  │  Modeling    │ │  Pipeline    │ │  Infrastructure │ │   │
│  │  │  Agent       │ │  Agent       │ │  Agent          │ │   │
│  │  │  (Phase 1)   │ │  (Phase 2)   │ │  (Phase 3)      │ │   │
│  │  └──────────────┘ └──────────────┘ └─────────────────┘ │   │
│  │                                                          │   │
│  │  ┌──────────────────────────────────────────────────┐  │   │
│  │  │       Shared Agent Capabilities                   │  │   │
│  │  │  • Planning & Reasoning (LLM-powered)            │  │   │
│  │  │  • Code Generation                                │  │   │
│  │  │  • Validation & Testing                           │  │   │
│  │  │  • Documentation Generation                       │  │   │
│  │  │  • Error Recovery & Retry Logic                   │  │   │
│  │  └──────────────────────────────────────────────────┘  │   │
│  │                                                          │   │
│  │  ┌──────────────────────────────────────────────────┐  │   │
│  │  │       Orchestrator Agent                          │  │   │
│  │  │  • Routes complex tasks to specialized agents    │  │   │
│  │  │  • Manages inter-agent communication             │  │   │
│  │  │  • Coordinates parallel execution                │  │   │
│  │  └──────────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                  MCP Integration Layer                           │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐    │
│  │              MCP Registry & Router                      │    │
│  │  • Server Discovery & Health Monitoring                │    │
│  │  • Capability Mapping                                  │    │
│  │  • Request Routing                                     │    │
│  │  • Version Management                                  │    │
│  │  • Error Handling & Circuit Breaking                   │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │ Database │  │   API    │  │   File   │  │  Tool        │  │
│  │   MCPs   │  │   MCPs   │  │   MCPs   │  │  MCPs        │  │
│  │          │  │          │  │          │  │              │  │
│  │ postgres │  │ stripe   │  │ s3       │  │ dbt          │  │
│  │ mysql    │  │ salesfrc │  │ gcs      │  │ airflow      │  │
│  │ snowflake│  │ hubspot  │  │ azure    │  │ terraform    │  │
│  │ bigquery │  │ rest_api │  │ local_fs │  │ git          │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────┘  │
└──────────────────────────────────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│              Workspace Management Layer                          │
│                                                                  │
│  ┌──────────────────┐  ┌────────────────┐  ┌────────────────┐ │
│  │  File System Ops │  │  Git Operations│  │  Project       │ │
│  │  • Create/Edit   │  │  • Commit      │  │  Templates     │ │
│  │  • Delete/Move   │  │  • Branch      │  │  • dbt         │ │
│  │  • Watch Changes │  │  • Push/Pull   │  │  • Airflow     │ │
│  │  • Permissions   │  │  • PR Creation │  │  • Terraform   │ │
│  └──────────────────┘  └────────────────┘  └────────────────┘ │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │           State Management & Persistence                  │  │
│  │  • Workspace metadata (SQLite/PostgreSQL)                │  │
│  │  • Agent conversation history                            │  │
│  │  • Generated artifacts tracking                          │  │
│  │  • User preferences & settings                           │  │
│  └──────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                 External Infrastructure                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │ Data     │  │ Data     │  │ Orchestr │  │ Version      │  │
│  │ Sources  │  │ Warehouse│  │ -ation   │  │ Control      │  │
│  │          │  │          │  │          │  │              │  │
│  │ DBs      │  │ Snowflake│  │ Airflow  │  │ GitHub       │  │
│  │ APIs     │  │ BigQuery │  │ Dagster  │  │ GitLab       │  │
│  │ Files    │  │ Redshift │  │ Prefect  │  │ Bitbucket    │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

### 1.2 Design Principles

1. **Agent-First Architecture**: AI agents are the primary actors, not just assistants
2. **MCP as Universal Abstraction**: All external interactions go through MCP servers
3. **Workspace as Source of Truth**: All generated artifacts live in git-tracked workspaces
4. **Modular & Extensible**: New capabilities via new agents and MCP servers
5. **Interface Agnostic**: Same backend serves CLI, VSCode, and Web
6. **Production Ready**: Generated code is deployable, not prototypes

---

## 2. Core Components

### 2.1 Agent Orchestration Layer

**Technology:** LangGraph + Claude API

**Responsibilities:**
- Parse and understand user requirements
- Coordinate between specialized agents
- Manage conversation state
- Execute multi-step workflows
- Handle errors and retries
- Provide streaming updates to interfaces

**Key Classes:**

```python
# core/agents/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any, List
from pydantic import BaseModel

class AgentCapability(BaseModel):
    """Describes what an agent can do"""
    name: str
    description: str
    required_mcps: List[str]
    output_types: List[str]  # dbt, airflow, terraform, etc.

class AgentState(BaseModel):
    """Shared state across agent execution"""
    conversation_id: str
    user_id: str
    workspace_path: str
    requirements: str
    conversation_history: List[Dict]
    discovered_context: Dict[str, Any]
    generated_artifacts: Dict[str, str]
    current_step: str
    errors: List[str]
    metadata: Dict[str, Any]

class BaseDataEngineeringAgent(ABC):
    """Base class for all specialized agents"""
    
    def __init__(
        self, 
        mcp_registry: 'MCPRegistry',
        workspace_manager: 'WorkspaceManager',
        llm_client: 'LLMClient'
    ):
        self.mcp_registry = mcp_registry
        self.workspace = workspace_manager
        self.llm = llm_client
        self.capabilities = self._define_capabilities()
    
    @abstractmethod
    def _define_capabilities(self) -> List[AgentCapability]:
        """Define what this agent can do"""
        pass
    
    @abstractmethod
    async def can_handle(self, task: Dict) -> bool:
        """Determine if this agent can handle the task"""
        pass
    
    @abstractmethod
    async def execute(self, state: AgentState) -> AgentState:
        """Execute the agent's workflow"""
        pass
    
    async def discover_context(self, state: AgentState) -> Dict:
        """Discover relevant context from workspace and MCPs"""
        pass
    
    async def generate_code(self, spec: Dict) -> Dict[str, str]:
        """Generate code artifacts based on specification"""
        pass
    
    async def validate(self, artifacts: Dict[str, str]) -> List[str]:
        """Validate generated artifacts"""
        pass
    
    async def document(self, artifacts: Dict[str, str]) -> str:
        """Generate documentation for artifacts"""
        pass
```

### 2.2 MCP Integration Layer

**Technology:** Custom MCP client implementation

**Responsibilities:**
- Discover and register MCP servers
- Route requests to appropriate servers
- Handle authentication and connection pooling
- Provide unified interface to agents
- Monitor server health
- Cache responses for efficiency

**Key Classes:**

```python
# core/mcp/registry.py
from typing import Dict, List, Optional, Any
from pydantic import BaseModel
import asyncio

class MCPServerConfig(BaseModel):
    """Configuration for an MCP server"""
    name: str
    type: str  # database, api, file, tool
    version: str
    capabilities: List[str]
    connection_config: Dict[str, Any]
    health_check_interval: int = 60  # seconds
    timeout: int = 30
    retry_policy: Dict[str, int]

class MCPCapability(BaseModel):
    """What an MCP server can do"""
    capability_type: str  # query, execute, read, write
    operations: List[str]
    schema_support: bool
    streaming_support: bool

class MCPRegistry:
    """
    Central registry for all MCP servers.
    Handles discovery, health monitoring, and routing.
    """
    
    def __init__(self, config_path: str = "~/.dataforge/mcp-servers.yml"):
        self.servers: Dict[str, MCPServerConfig] = {}
        self.clients: Dict[str, 'MCPClient'] = {}
        self.health_status: Dict[str, bool] = {}
        self._load_config(config_path)
    
    async def discover_servers(self) -> List[str]:
        """
        Auto-discover MCP servers from:
        1. User config (~/.dataforge/mcp-servers.yml)
        2. Project config (.dataforge/mcp-servers.yml)
        3. Environment variables
        4. System-wide registry
        """
        pass
    
    async def register_server(self, config: MCPServerConfig) -> bool:
        """Register a new MCP server"""
        pass
    
    async def get_capabilities(self) -> Dict[str, List[str]]:
        """
        Returns map of available capabilities:
        {
            "data_sources": ["postgres", "mysql", "snowflake", "stripe"],
            "tools": ["dbt", "airflow", "git"],
            "platforms": ["aws", "gcp"]
        }
        """
        pass
    
    async def query_source(
        self, 
        source_name: str, 
        query: str,
        params: Optional[Dict] = None
    ) -> Dict:
        """Execute a query against a data source MCP"""
        pass
    
    async def execute_tool(
        self,
        tool_name: str,
        command: str,
        args: Dict
    ) -> Dict:
        """Execute a command via tool MCP"""
        pass
    
    async def health_check(self, server_name: str) -> bool:
        """Check if an MCP server is healthy"""
        pass
    
    async def _monitor_health(self):
        """Background task to monitor all server health"""
        pass

class MCPClient:
    """
    Universal client for interacting with MCP servers.
    Handles protocol specifics, retries, and error handling.
    """
    
    def __init__(self, config: MCPServerConfig):
        self.config = config
        self.connection = None
        self._setup_connection()
    
    async def connect(self) -> bool:
        """Establish connection to MCP server"""
        pass
    
    async def execute(
        self, 
        operation: str, 
        params: Dict
    ) -> Dict:
        """Execute an operation on the MCP server"""
        pass
    
    async def stream(
        self,
        operation: str,
        params: Dict
    ) -> AsyncIterator[Dict]:
        """Stream results from MCP server"""
        pass
    
    async def disconnect(self):
        """Close connection to MCP server"""
        pass
```

### 2.3 Workspace Management Layer

**Technology:** Python pathlib + GitPython

**Responsibilities:**
- Create and manage project workspaces
- File system operations
- Git integration (commit, branch, push)
- Template management
- State persistence

**Key Classes:**

```python
# core/workspace/manager.py
from pathlib import Path
from typing import Dict, Optional, List
import git
from pydantic import BaseModel

class WorkspaceConfig(BaseModel):
    """Configuration for a workspace"""
    workspace_id: str
    name: str
    path: Path
    project_type: str  # dbt, airflow, terraform, multi
    git_repo: Optional[str]
    git_branch: str = "main"
    created_at: str
    metadata: Dict

class WorkspaceManager:
    """
    Manages file system operations and git integration.
    Each workspace is a self-contained project directory.
    """
    
    def __init__(self, base_path: str = "~/dataforge-workspaces"):
        self.base_path = Path(base_path).expanduser()
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.current_workspace: Optional[WorkspaceConfig] = None
    
    def create_workspace(
        self,
        name: str,
        project_type: str,
        template: Optional[str] = None
    ) -> WorkspaceConfig:
        """
        Create a new workspace from template.
        
        Templates:
        - dbt_project
        - airflow_project
        - terraform_project
        - full_stack (all of the above)
        """
        pass
    
    def load_workspace(self, workspace_id: str) -> WorkspaceConfig:
        """Load an existing workspace"""
        pass
    
    def write_file(
        self,
        relative_path: str,
        content: str,
        auto_commit: bool = False
    ) -> Path:
        """Write a file to the workspace"""
        pass
    
    def read_file(self, relative_path: str) -> str:
        """Read a file from the workspace"""
        pass
    
    def delete_file(self, relative_path: str):
        """Delete a file from the workspace"""
        pass
    
    def list_files(
        self,
        pattern: Optional[str] = None,
        recursive: bool = True
    ) -> List[Path]:
        """List files in workspace"""
        pass
    
    # Git operations
    def git_init(self) -> git.Repo:
        """Initialize git repository"""
        pass
    
    def git_commit(self, message: str, files: Optional[List[str]] = None):
        """Commit changes"""
        pass
    
    def git_branch(self, branch_name: str):
        """Create and checkout new branch"""
        pass
    
    def git_push(self, remote: str = "origin", branch: Optional[str] = None):
        """Push changes to remote"""
        pass
    
    def apply_template(self, template_name: str):
        """Apply a project template to workspace"""
        pass
    
    def get_workspace_summary(self) -> Dict:
        """Get summary of workspace contents"""
        pass
```

---

## 3. Agent System Design

### 3.1 Data Modeling Agent (Phase 1 - MVP)

**Purpose:** Generate data models from requirements and source data

**LangGraph Workflow:**

```python
# core/graph/modeling_graph.py
from langgraph.graph import StateGraph, END
from typing import TypedDict, List, Dict, Optional

class ModelingState(TypedDict):
    # Inputs
    user_requirements: str
    sources: List[Dict]  # MCP connection configs
    target_platform: str  # snowflake, bigquery, postgres
    
    # Discovery phase
    discovered_schemas: Dict
    profiling_results: Dict
    relationships: List[Dict]
    
    # Understanding phase
    parsed_requirements: Dict
    business_entities: List[str]
    metrics: List[Dict]
    dimensions: List[str]
    grain: str
    
    # Design phase
    architecture_type: str  # star, snowflake, OBT, data_vault
    model_design: Dict
    
    # Generation phase
    generated_dbt: Dict
    generated_ddl: List[str]
    generated_docs: str
    tests: List[Dict]
    
    # State management
    current_step: str
    errors: List[str]
    iteration_count: int
    user_feedback: Optional[str]

def create_modeling_graph():
    """Create the data modeling workflow graph"""
    
    workflow = StateGraph(ModelingState)
    
    # Add nodes
    workflow.add_node("connect_sources", connect_and_validate_sources)
    workflow.add_node("discover_schemas", deep_schema_discovery)
    workflow.add_node("profile_data", profile_data_quality)
    workflow.add_node("infer_relationships", infer_table_relationships)
    workflow.add_node("parse_requirements", understand_user_needs)
    workflow.add_node("match_data", match_requirements_to_available_data)
    workflow.add_node("design_model", design_data_model_architecture)
    workflow.add_node("generate_dbt", generate_dbt_project)
    workflow.add_node("generate_ddl", generate_ddl_scripts)
    workflow.add_node("generate_docs", generate_documentation)
    workflow.add_node("validate", validate_all_artifacts)
    workflow.add_node("review", present_to_user_for_review)
    
    # Define edges
    workflow.add_edge("connect_sources", "discover_schemas")
    workflow.add_edge("discover_schemas", "profile_data")
    workflow.add_edge("profile_data", "infer_relationships")
    workflow.add_edge("infer_relationships", "parse_requirements")
    
    # Conditional: if requirements are clear, continue; else ask questions
    workflow.add_conditional_edges(
        "parse_requirements",
        lambda state: "match_data" if state["parsed_requirements"]["confidence"] > 0.8 
                     else "parse_requirements",  # loop back with clarifying questions
        {
            "match_data": "match_data",
            "parse_requirements": "parse_requirements"
        }
    )
    
    workflow.add_conditional_edges(
        "match_data",
        lambda state: "design_model" if state["parsed_requirements"]["matched"]
                     else "parse_requirements",  # missing data, clarify requirements
        {
            "design_model": "design_model",
            "parse_requirements": "parse_requirements"
        }
    )
    
    workflow.add_edge("design_model", "generate_dbt")
    workflow.add_edge("generate_dbt", "generate_ddl")
    workflow.add_edge("generate_ddl", "generate_docs")
    workflow.add_edge("generate_docs", "validate")
    
    # Conditional: if validation passes, show to user; else fix errors
    workflow.add_conditional_edges(
        "validate",
        lambda state: "review" if not state["errors"]
                     else "design_model",  # fix and regenerate
        {
            "review": "review",
            "design_model": "design_model"
        }
    )
    
    # Conditional: if user approves, done; else iterate
    workflow.add_conditional_edges(
        "review",
        lambda state: END if state["user_feedback"] == "approved"
                     else "design_model",  # incorporate feedback
        {
            END: END,
            "design_model": "design_model"
        }
    )
    
    workflow.set_entry_point("connect_sources")
    
    return workflow.compile()
```

**Node Implementations:**

```python
# Node: connect_and_validate_sources
async def connect_and_validate_sources(state: ModelingState) -> ModelingState:
    """
    Connect to all specified data sources via MCP and validate connectivity.
    """
    mcp_registry = get_mcp_registry()
    
    for source in state["sources"]:
        try:
            # Test connection via MCP
            mcp_name = source["mcp_server"]
            is_healthy = await mcp_registry.health_check(mcp_name)
            
            if not is_healthy:
                state["errors"].append(f"Cannot connect to {mcp_name}")
                continue
            
            # Get basic info
            info = await mcp_registry.query_source(
                mcp_name,
                "SELECT 1"  # basic connectivity test
            )
            
            logger.info(f"✓ Connected to {mcp_name}")
            
        except Exception as e:
            state["errors"].append(f"Connection failed for {source['name']}: {str(e)}")
    
    state["current_step"] = "connect_sources"
    return state

# Node: deep_schema_discovery
async def deep_schema_discovery(state: ModelingState) -> ModelingState:
    """
    Discover schemas from all connected sources.
    Extract tables, columns, types, constraints.
    """
    mcp_registry = get_mcp_registry()
    discovered = {}
    
    for source in state["sources"]:
        mcp_name = source["mcp_server"]
        
        # Get schema metadata
        schema_query = """
        SELECT 
            table_schema,
            table_name,
            column_name,
            data_type,
            is_nullable,
            column_default,
            character_maximum_length
        FROM information_schema.columns
        WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
        ORDER BY table_schema, table_name, ordinal_position
        """
        
        result = await mcp_registry.query_source(mcp_name, schema_query)
        
        # Parse into structured format
        tables = parse_schema_result(result)
        
        # Get row counts
        for table in tables:
            count_query = f"SELECT COUNT(*) FROM {table['schema']}.{table['name']}"
            count_result = await mcp_registry.query_source(mcp_name, count_query)
            table['row_count'] = count_result['rows'][0][0]
        
        discovered[source['name']] = {
            'source': source,
            'tables': tables
        }
    
    state["discovered_schemas"] = discovered
    state["current_step"] = "discover_schemas"
    return state

# Node: profile_data_quality
async def profile_data_quality(state: ModelingState) -> ModelingState:
    """
    Profile data quality for each table:
    - Null percentages
    - Cardinality
    - Value distributions
    - Pattern detection (emails, IDs, dates)
    """
    mcp_registry = get_mcp_registry()
    profiles = {}
    
    for source_name, source_data in state["discovered_schemas"].items():
        mcp_name = source_data['source']['mcp_server']
        profiles[source_name] = {}
        
        for table in source_data['tables']:
            table_fqn = f"{table['schema']}.{table['name']}"
            
            # Profile each column
            column_profiles = []
            for col in table['columns']:
                profile_query = f"""
                SELECT 
                    COUNT(*) as total_rows,
                    COUNT({col['name']}) as non_null_count,
                    COUNT(DISTINCT {col['name']}) as distinct_count
                FROM {table_fqn}
                """
                
                result = await mcp_registry.query_source(mcp_name, profile_query)
                
                row = result['rows'][0]
                total = row[0]
                non_null = row[1]
                distinct = row[2]
                
                column_profiles.append({
                    'column': col['name'],
                    'type': col['type'],
                    'null_percent': (total - non_null) / total * 100 if total > 0 else 0,
                    'cardinality': distinct,
                    'is_unique': distinct == non_null,
                    'is_key_candidate': distinct == total
                })
            
            profiles[source_name][table['name']] = {
                'row_count': table['row_count'],
                'columns': column_profiles
            }
    
    state["profiling_results"] = profiles
    state["current_step"] = "profile_data"
    return state

# Node: infer_table_relationships
async def infer_table_relationships(state: ModelingState) -> ModelingState:
    """
    Infer relationships between tables:
    1. Declared foreign keys
    2. Column name matching (customer_id -> customer.id)
    3. Value overlap analysis
    4. Cardinality analysis
    """
    relationships = []
    
    # Get all tables across sources
    all_tables = []
    for source_name, source_data in state["discovered_schemas"].items():
        for table in source_data['tables']:
            all_tables.append({
                'source': source_name,
                'schema': table['schema'],
                'name': table['name'],
                'columns': table['columns']
            })
    
    # Check each table pair for relationships
    for i, table1 in enumerate(all_tables):
        for table2 in all_tables[i+1:]:
            # Check for FK declarations first
            fks = check_foreign_keys(table1, table2)
            relationships.extend(fks)
            
            # Infer relationships via column names
            inferred = infer_relationships_by_name(table1, table2)
            relationships.extend(inferred)
    
    # Use LLM to validate and enrich relationships
    enriched_relationships = await enrich_relationships_with_llm(
        relationships,
        state["discovered_schemas"]
    )
    
    state["relationships"] = enriched_relationships
    state["current_step"] = "infer_relationships"
    return state

# Node: understand_user_needs
async def parse_requirements(state: ModelingState) -> ModelingState:
    """
    Use LLM to parse natural language requirements into structured format.
    """
    llm = get_llm_client()
    
    prompt = f"""
    You are a senior data engineer analyzing requirements.
    
    User Requirements:
    {state["user_requirements"]}
    
    Available Data Sources:
    {format_schemas_for_llm(state["discovered_schemas"])}
    
    Data Relationships:
    {format_relationships_for_llm(state["relationships"])}
    
    Extract and return as JSON:
    {{
        "business_entities": ["list of main entities like customer, order, product"],
        "metrics": [
            {{
                "name": "monthly_recurring_revenue",
                "description": "...",
                "calculation": "SUM(subscription_amount) WHERE status = 'active'",
                "required_tables": ["subscriptions"]
            }}
        ],
        "dimensions": ["time", "geography", "customer_segment"],
        "grain": "one row per subscription per day",
        "time_requirements": {{
            "historical": true,
            "scd_type": 2,
            "snapshot_frequency": "daily"
        }},
        "special_requirements": ["partitioning", "incremental loads"],
        "confidence": 0.95
    }}
    
    If requirements are unclear, set confidence < 0.8 and include:
    "clarifying_questions": ["question 1", "question 2"]
    """
    
    response = await llm.structured_output(prompt, ModelingRequirements)
    
    state["parsed_requirements"] = response.dict()
    state["business_entities"] = response.business_entities
    state["metrics"] = response.metrics
    state["dimensions"] = response.dimensions
    state["grain"] = response.grain
    state["current_step"] = "parse_requirements"
    
    return state

# Node: match_requirements_to_available_data
async def match_requirements_to_available_data(state: ModelingState) -> ModelingState:
    """
    Verify that available data can satisfy requirements.
    Identify gaps.
    """
    llm = get_llm_client()
    
    prompt = f"""
    Requirements:
    {json.dumps(state["parsed_requirements"], indent=2)}
    
    Available Data:
    {format_schemas_for_llm(state["discovered_schemas"])}
    
    For each required metric and dimension:
    1. Identify which tables/columns can provide the data
    2. Note any missing data
    3. Suggest transformations needed
    
    Return as JSON:
    {{
        "matched": true/false,
        "coverage": {{
            "metric_name": {{
                "source_tables": ["table1", "table2"],
                "source_columns": ["col1", "col2"],
                "transformation_needed": "aggregation/join/calculation",
                "confidence": 0.9
            }}
        }},
        "gaps": ["list of missing data"],
        "recommendations": ["suggestions for user"]
    }}
    """
    
    matching = await llm.structured_output(prompt, DataMatching)
    
    state["parsed_requirements"]["matched"] = matching.matched
    state["parsed_requirements"]["coverage"] = matching.coverage
    
    if not matching.matched:
        state["errors"].append(f"Data gaps found: {matching.gaps}")
    
    state["current_step"] = "match_data"
    return state

# Node: design_data_model_architecture
async def design_data_model_architecture(state: ModelingState) -> ModelingState:
    """
    Design the data model architecture.
    Decide on: star schema, OBT, data vault, etc.
    """
    llm = get_llm_client()
    requirements = state["parsed_requirements"]
    
    # Decision logic for architecture type
    if len(requirements["metrics"]) > 3 and len(requirements["dimensions"]) > 5:
        # Many metrics and dimensions -> star schema
        architecture = "star_schema"
    elif requirements.get("time_requirements", {}).get("scd_type") == 2:
        # SCD Type 2 needed -> star schema with SCD
        architecture = "star_schema_scd"
    elif requirements.get("compliance") or requirements.get("auditability"):
        # Audit requirements -> data vault
        architecture = "data_vault"
    else:
        # Let LLM decide
        decision_prompt = f"""
        Based on these requirements, what data modeling architecture is best?
        
        Requirements: {json.dumps(requirements, indent=2)}
        
        Options:
        - star_schema: fact table + dimension tables, best for BI/analytics
        - snowflake_schema: normalized dimensions, better for large dimensions
        - one_big_table: denormalized, best for simple queries
        - data_vault: hub/link/satellite, best for audit/compliance
        
        Return: {{"architecture": "...", "reasoning": "..."}}
        """
        decision = await llm.structured_output(decision_prompt, ArchitectureDecision)
        architecture = decision.architecture
    
    # Now design the actual model based on architecture
    if architecture.startswith("star_schema"):
        model = await design_star_schema(state)
    elif architecture == "data_vault":
        model = await design_data_vault(state)
    elif architecture == "one_big_table":
        model = await design_obt(state)
    
    state["architecture_type"] = architecture
    state["model_design"] = model
    state["current_step"] = "design_model"
    
    return state

async def design_star_schema(state: ModelingState) -> Dict:
    """
    Design a star schema:
    - Identify fact table(s)
    - Design dimension tables
    - Define relationships
    - Add surrogate keys
    """
    llm = get_llm_client()
    requirements = state["parsed_requirements"]
    
    prompt = f"""
    Design a star schema for these requirements:
    
    Metrics: {json.dumps(requirements["metrics"], indent=2)}
    Dimensions: {requirements["dimensions"]}
    Grain: {requirements["grain"]}
    
    Available source data:
    {format_schemas_for_llm(state["discovered_schemas"])}
    
    Design a star schema with:
    1. One or more fact tables (with grain, measures, foreign keys to dimensions)
    2. Dimension tables (with surrogate keys, attributes, SCD type if needed)
    3. Staging models to prepare source data
    4. Intermediate models for complex transformations
    
    Return as JSON following this structure:
    {{
        "staging_models": [...],
        "intermediate_models": [...],
        "dimension_tables": [...],
        "fact_tables": [...]
    }}
    """
    
    design = await llm.structured_output(prompt, StarSchemaDesign)
    return design.dict()

# Node: generate_dbt_project
async def generate_dbt_project(state: ModelingState) -> ModelingState:
    """
    Generate complete dbt project from model design.
    """
    from core.generators.dbt_generator import DBTGenerator
    
    generator = DBTGenerator(
        workspace=get_workspace_manager(),
        target_platform=state["target_platform"]
    )
    
    dbt_project = generator.generate_project(
        model_design=state["model_design"],
        sources=state["sources"],
        project_name=state.get("project_name", "analytics")
    )
    
    state["generated_dbt"] = dbt_project
    state["current_step"] = "generate_dbt"
    
    return state

# Node: generate_ddl_scripts
async def generate_ddl_scripts(state: ModelingState) -> ModelingState:
    """
    Generate DDL scripts for creating tables in target database.
    """
    from core.generators.ddl_generator import DDLGenerator
    
    generator = DDLGenerator(target_platform=state["target_platform"])
    
    ddl_scripts = generator.generate_ddl(
        model_design=state["model_design"]
    )
    
    state["generated_ddl"] = ddl_scripts
    state["current_step"] = "generate_ddl"
    
    return state

# Node: generate_documentation
async def generate_documentation(state: ModelingState) -> ModelingState:
    """
    Generate documentation:
    - README
    - Data lineage diagram (Mermaid)
    - Model descriptions
    - Column descriptions
    """
    from core.generators.doc_generator import DocGenerator
    
    generator = DocGenerator()
    
    docs = generator.generate_docs(
        model_design=state["model_design"],
        requirements=state["parsed_requirements"],
        architecture=state["architecture_type"]
    )
    
    state["generated_docs"] = docs
    state["current_step"] = "generate_docs"
    
    return state

# Node: validate_all_artifacts
async def validate_all_artifacts(state: ModelingState) -> ModelingState:
    """
    Validate all generated artifacts:
    - Parse dbt models for syntax errors
    - Validate SQL
    - Check for circular dependencies
    - Validate naming conventions
    """
    errors = []
    
    # Validate dbt project
    from core.validators.dbt_validator import DBTValidator
    dbt_validator = DBTValidator()
    dbt_errors = await dbt_validator.validate(state["generated_dbt"])
    errors.extend(dbt_errors)
    
    # Validate DDL
    from core.validators.sql_validator import SQLValidator
    sql_validator = SQLValidator(state["target_platform"])
    for ddl in state["generated_ddl"]:
        sql_errors = await sql_validator.validate(ddl)
        errors.extend(sql_errors)
    
    state["errors"] = errors
    state["current_step"] = "validate"
    
    return state

# Node: present_to_user_for_review
async def present_to_user_for_review(state: ModelingState) -> ModelingState:
    """
    Present generated artifacts to user for review.
    This is where we pause and wait for user feedback.
    """
    # Write all artifacts to workspace
    workspace = get_workspace_manager()
    
    for file_path, content in state["generated_dbt"].items():
        workspace.write_file(file_path, content)
    
    for i, ddl in enumerate(state["generated_ddl"]):
        workspace.write_file(f"ddl/table_{i}.sql", ddl)
    
    workspace.write_file("docs/README.md", state["generated_docs"])
    
    # Generate summary for user
    summary = f"""
    ✓ Generated {state["architecture_type"]} data model
    ✓ Created {len(state["model_design"].get("fact_tables", []))} fact table(s)
    ✓ Created {len(state["model_design"].get("dimension_tables", []))} dimension table(s)
    ✓ Generated {len(state["generated_dbt"])} dbt models
    ✓ Generated DDL scripts for {state["target_platform"]}
    ✓ Created documentation
    
    Workspace: {workspace.current_workspace.path}
    
    Review the generated code and provide feedback.
    """
    
    state["current_step"] = "review"
    state["summary"] = summary
    
    # This is where we'd wait for user input in the actual implementation
    # The graph will pause here until user provides feedback
    
    return state
```

### 3.2 Pipeline Agent (Phase 2)

**Purpose:** Generate ETL/ELT pipelines

**Capabilities:**
- Generate Airflow DAGs
- Generate Dagster assets
- Generate Prefect flows
- Schedule configuration
- Dependency management
- Error handling & retry logic
- Monitoring setup

**Workflow:**
```
Requirements → Source/Target Analysis → Pipeline Design → 
Code Generation → Testing → Deployment Config
```

### 3.3 Infrastructure Agent (Phase 3)

**Purpose:** Provision and configure data infrastructure

**Capabilities:**
- Generate Terraform configurations
- Provision cloud warehouses (Snowflake, BigQuery, Redshift)
- Set up data lakes (S3, GCS, ADLS)
- Configure networking and access control
- Cost optimization recommendations

### 3.4 Orchestrator Agent

**Purpose:** Coordinate multiple agents for complex tasks

**Example Complex Task:**
```
User: "Build me a complete analytics stack for my e-commerce business"

Orchestrator Plan:
1. Infrastructure Agent: Provision Snowflake warehouse
2. Modeling Agent: Design dimensional model (orders, customers, products)
3. Pipeline Agent: Create daily ingestion DAGs from Postgres + Stripe
4. Integration Agent: Setup dbt Cloud, Monte Carlo for data quality
5. Deploy everything and run initial load
```

---

## 4. MCP Integration Layer

### 4.1 MCP Server Types

**Database MCPs:**
```yaml
# Example: PostgreSQL MCP Server Config
name: postgres_production
type: database
version: 1.0.0
capabilities:
  - schema_discovery
  - query_execution
  - data_profiling
  - relationship_inference
connection:
  host: prod-db.example.com
  port: 5432
  database: production
  credentials: ${POSTGRES_CREDS}  # from vault
health_check:
  interval: 60
  timeout: 10
  query: "SELECT 1"
```

**API MCPs:**
```yaml
# Example: Stripe MCP Server
name: stripe_api
type: api
version: 1.0.0
capabilities:
  - data_extraction
  - schema_discovery
  - pagination
  - incremental_sync
connection:
  base_url: https://api.stripe.com/v1
  auth_type: bearer_token
  credentials: ${STRIPE_API_KEY}
endpoints:
  - customers
  - subscriptions
  - invoices
  - charges
rate_limiting:
  requests_per_second: 100
  burst: 200
```

**Tool MCPs:**
```yaml
# Example: dbt MCP Server
name: dbt_cloud
type: tool
version: 1.0.0
capabilities:
  - run_models
  - test_models
  - generate_docs
  - parse_manifest
  - get_run_status
connection:
  api_url: https://cloud.getdbt.com/api/v2
  account_id: ${DBT_ACCOUNT_ID}
  credentials: ${DBT_API_KEY}
operations:
  - run
  - test
  - compile
  - docs_generate
```

### 4.2 MCP Communication Protocol

**Request Format:**
```json
{
  "operation": "query",
  "params": {
    "query": "SELECT * FROM customers LIMIT 10",
    "timeout": 30
  },
  "metadata": {
    "request_id": "uuid",
    "timestamp": "2025-10-12T10:30:00Z",
    "user_id": "user-123"
  }
}
```

**Response Format:**
```json
{
  "status": "success",
  "data": {
    "columns": ["id", "name", "email"],
    "rows": [[1, "John", "john@example.com"]],
    "row_count": 10
  },
  "metadata": {
    "execution_time_ms": 245,
    "request_id": "uuid"
  }
}
```

---

## 5. Data Flow & Workflows

### 5.1 End-to-End Data Modeling Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. User Interaction                                              │
│    User: "Connect to my Postgres DB and create an MRR model"   │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. Request Processing (API Gateway)                             │
│    - Parse user input                                           │
│    - Create conversation session                                │
│    - Initialize agent state                                     │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. Agent Orchestration (LangGraph)                              │
│    - Route to DataModelingAgent                                 │
│    - Execute workflow graph                                     │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. Data Discovery (via MCP)                                     │
│    MCP Registry → Postgres MCP → Query information_schema       │
│    - Get all tables, columns, types                             │
│    - Profile data (row counts, nulls, cardinality)              │
│    - Infer relationships                                        │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. Requirements Understanding (LLM)                             │
│    Claude API processes:                                        │
│    - User requirements: "MRR model"                             │
│    - Available data schemas                                     │
│    → Extracts: entities (subscriptions, customers),             │
│                metrics (MRR = SUM(amount) WHERE active),        │
│                dimensions (time, product, customer_segment)     │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. Data Matching                                                │
│    - Match requirements to discovered data                      │
│    - Verify all needed data exists                              │
│    - Identify transformations needed                            │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 7. Model Design (LLM + Business Rules)                         │
│    Decision: Star schema is best for this use case             │
│    Design:                                                      │
│    - fact_mrr (grain: subscription per month)                   │
│    - dim_customer (SCD Type 2)                                  │
│    - dim_product                                                │
│    - dim_date                                                   │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 8. Code Generation                                              │
│    DBT Generator creates:                                       │
│    - models/staging/stg_subscriptions.sql                       │
│    - models/marts/fact_mrr.sql                                  │
│    - models/marts/dim_customer.sql                              │
│    - models/marts/dim_product.sql                               │
│    - schema.yml (with tests & docs)                             │
│    - dbt_project.yml                                            │
│                                                                 │
│    DDL Generator creates:                                       │
│    - CREATE TABLE statements for Snowflake                      │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 9. Validation                                                   │
│    - Parse all SQL for syntax errors                            │
│    - Check dbt project structure                                │
│    - Validate naming conventions                                │
│    - Check for circular dependencies                            │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 10. Workspace Write                                             │
│     WorkspaceManager writes to:                                 │
│     ~/dataforge-workspaces/mrr-analytics/                       │
│     ├── dbt_project.yml                                         │
│     ├── models/                                                 │
│     ├── tests/                                                  │
│     ├── docs/                                                   │
│     └── README.md                                               │
│                                                                 │
│     Git: Initial commit created                                 │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 11. User Review                                                 │
│     Interface shows:                                            │
│     - Summary of generated model                                │
│     - File tree                                                 │
│     - Lineage diagram                                           │
│     - Options: Approve / Request changes / Deploy               │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 12. Deployment (Optional)                                       │
│     If user chooses to deploy:                                  │
│     - Via dbt MCP: Run dbt models                               │
│     - Via Snowflake MCP: Execute DDL                            │
│     - Setup monitoring via Elementary MCP                       │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Streaming Response Flow

For real-time user feedback during agent execution:

```python
# interfaces/api/websocket.py
from fastapi import WebSocket
import asyncio

async def stream_agent_execution(websocket: WebSocket, task_id: str):
    """
    Stream agent execution progress to client via WebSocket
    """
    await websocket.accept()
    
    # Create agent execution task
    agent = DataModelingAgent(...)
    
    async for event in agent.execute_with_streaming(task_id):
        # Stream events back to client
        await websocket.send_json({
            "type": event.type,  # "step_start", "step_complete", "thinking", "error"
            "step": event.step_name,
            "message": event.message,
            "data": event.data,
            "timestamp": event.timestamp
        })
    
    await websocket.close()
```

---

## 6. Interface Specifications

### 6.1 CLI Interface

**Installation:**
```bash
pip install dataforge-cli
dataforge auth login
```

**Commands:**

```bash
# Initialize new project
dataforge init my-analytics-project \
  --type dbt \
  --template star-schema

# Start interactive session
dataforge chat

# Generate from command
dataforge generate \
  --sources postgres://localhost/mydb,stripe://api \
  --requirement "Create MRR analysis model with customer churn" \
  --target snowflake \
  --output ./my-project

# Connect to data source
dataforge source add \
  --name production_db \
  --type postgres \
  --host db.example.com \
  --database prod

# List sources
dataforge source list

# Deploy generated code
dataforge deploy \
  --workspace ./my-project \
  --target production

# Validate project
dataforge validate ./my-project

# Get project status
dataforge status

# Open UI
dataforge ui
```

**Interactive Chat Mode:**
```
$ dataforge chat

DataForge v1.0.0
Chat mode - describe what you want to build

You: Connect to my Postgres database at localhost
Agent: ✓ Connected to Postgres at localhost
       Found 15 tables across 2 schemas
       
       What would you like to build?

You: I need an analytics model for tracking user engagement
Agent: 🤔 Analyzing your data...
       
       I found these relevant tables:
       - users (50K rows)
       - events (2M rows)
       - sessions (500K rows)
       
       For user engagement, I'm thinking:
       - Daily active users (DAU)
       - Weekly active users (WAU)
       - Session duration metrics
       - Event frequency by user
       
       Should I proceed with a star schema design?

You: Yes, and add cohort analysis

Agent: ✓ Designing model with cohort analysis...
       ✓ Generating dbt project...
       ✓ Creating 12 models...
       ✓ Writing to workspace...
       
       Done! Generated at: ~/dataforge-workspaces/user-engagement/
       
       📊 Summary:
       - 3 staging models
       - 4 dimension tables (including dim_cohort)
       - 2 fact tables
       - 8 data tests
       
       Commands:
       $ cd ~/dataforge-workspaces/user-engagement
       $ dbt run
       $ dbt test

You: Show me the lineage

Agent: [Displays Mermaid diagram in terminal]

You: Perfect, commit this

Agent: ✓ Git commit created: "Initial user engagement model"
       ✓ Branch: feature/user-engagement-model
       
       Push to remote?

You: Yes

Agent: ✓ Pushed to origin/feature/user-engagement-model
       
       Create PR?

You: Yes

Agent: ✓ Pull request created: #42
       → https://github.com/yourorg/analytics/pull/42
```

### 6.2 VSCode Extension

**Features:**

1. **Chat Panel** (like GitHub Copilot)
   - Side panel for conversation
   - Context-aware (knows open files)
   - Can reference code in workspace

2. **File Generation**
   - Generates files directly in workspace
   - Uses VSCode's file system API
   - Integrates with VSCode's git

3. **Inline Suggestions**
   - Suggest improvements to existing models
   - Auto-complete for dbt syntax
   - Explain SQL queries

4. **Lineage Visualization**
   - Custom webview for DAG visualization
   - Click to navigate to model files
   - Show upstream/downstream dependencies

**Extension Architecture:**

```typescript
// vscode/extension.ts
import * as vscode from 'vscode';

export function activate(context: vscode.ExtensionContext) {
    // Register chat panel
    const chatPanel = new DataForgeChatPanel(context);
    
    // Register commands
    context.subscriptions.push(
        vscode.commands.registerCommand('dataforge.chat', () => {
            chatPanel.show();
        }),
        
        vscode.commands.registerCommand('dataforge.generate', async () => {
            const requirement = await vscode.window.showInputBox({
                prompt: 'Describe what you want to build'
            });
            
            if (requirement) {
                await chatPanel.sendMessage(requirement);
            }
        }),
        
        vscode.commands.registerCommand('dataforge.showLineage', () => {
            const lineagePanel = new LineagePanel(context);
            lineagePanel.show();
        })
    );
}

class DataForgeChatPanel {
    private panel: vscode.WebviewPanel;
    private apiClient: DataForgeAPIClient;
    
    constructor(context: vscode.ExtensionContext) {
        this.panel = vscode.window.createWebviewPanel(
            'dataforgeChat',
            'DataForge',
            vscode.ViewColumn.Beside,
            { enableScripts: true }
        );
        
        this.apiClient = new DataForgeAPIClient();
        this.setupWebview();
    }
    
    async sendMessage(message: string) {
        // Stream response from API
        const stream = this.apiClient.streamGeneration(message);
        
        for await (const event of stream) {
            // Update webview with streaming response
            this.panel.webview.postMessage({
                type: 'agentEvent',
                event: event
            });
            
            // If files generated, create them in workspace
            if (event.type === 'file_generated') {
                await this.createFile(event.path, event.content);
            }
        }
    }
    
    private async createFile(path: string, content: string) {
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
        if (!workspaceFolder) return;
        
        const uri = vscode.Uri.joinPath(workspaceFolder.uri, path);
        await vscode.workspace.fs.writeFile(
            uri,
            Buffer.from(content, 'utf8')
        );
        
        // Open the file
        const doc = await vscode.workspace.openTextDocument(uri);
        await vscode.window.showTextDocument(doc);
    }
}
```

### 6.3 Web Dashboard (Optional - Phase 3)

**Purpose:** Visualization and team collaboration

**Pages:**

1. **Projects Dashboard**
   - List all projects
   - Project status
   - Recent activity

2. **Project Detail**
   - Lineage visualization (interactive DAG)
   - Model catalog
   - Data quality metrics
   - Cost analysis

3. **Team Management**
   - User permissions
   - Shared workspaces
   - Audit logs

---

## 7. Code Generation Engines

### 7.1 dbt Generator

```python
# core/generators/dbt_generator.py
from pathlib import Path
from typing import Dict, List
from jinja2 import Template

class DBTGenerator:
    """
    Generates complete dbt projects from model designs.
    """
    
    def __init__(self, workspace: WorkspaceManager, target_platform: str):
        self.workspace = workspace
        self.target_platform = target_platform
        self.templates = self._load_templates()
    
    def generate_project(
        self,
        model_design: Dict,
        sources: List[Dict],
        project_name: str
    ) -> Dict[str, str]:
        """
        Generate complete dbt project structure.
        
        Returns dict of {file_path: content}
        """
        files = {}
        
        # 1. Project configuration
        files['dbt_project.yml'] = self._generate_project_yml(project_name)
        files['profiles.yml'] = self._generate_profiles_yml(sources)
        files['packages.yml'] = self._generate_packages_yml()
        
        # 2. Source definitions
        files['models/staging/_sources.yml'] = self._generate_sources_yml(sources)
        
        # 3. Staging models
        for staging_model in model_design['staging_models']:
            path = f"models/staging/{staging_model['name']}.sql"
            files[path] = self._generate_staging_model(staging_model)
        
        # 4. Intermediate models
        for int_model in model_design['intermediate_models']:
            path = f"models/intermediate/{int_model['name']}.sql"
            files[path] = self._generate_intermediate_model(int_model)
        
        # 5. Mart models (facts and dimensions)
        for dim in model_design['dimension_tables']:
            path = f"models/marts/{dim['mart']}/{dim['name']}.sql"
            files[path] = self._generate_dimension_model(dim)
        
        for fact in model_design['fact_tables']:
            path = f"models/marts/{fact['mart']}/{fact['name']}.sql"
            files[path] = self._generate_fact_model(fact)
        
        # 6. Schema definitions (tests, docs)
        files['models/staging/_staging.yml'] = self._generate_staging_yml(
            model_design['staging_models']
        )
        
        files['models/marts/_marts.yml'] = self._generate_marts_yml(
            model_design['dimension_tables'],
            model_design['fact_tables']
        )
        
        # 7. Macros
        files['macros/generate_surrogate_key.sql'] = self._generate_surrogate_key_macro()
        
        # 8. Tests
        for test in model_design.get('custom_tests', []):
            path = f"tests/{test['name']}.sql"
            files[path] = test['sql']
        
        # 9. Documentation
        files['README.md'] = self._generate_readme(model_design, project_name)
        files['docs/overview.md'] = self._generate_overview_doc(model_design)
        
        return files
    
    def _generate_staging_model(self, model: Dict) -> str:
        """Generate a staging model SQL file"""
        template = self.templates['staging_model']
        
        return template.render(
            model_name=model['name'],
            source_table=model['source_table'],
            columns=model['columns'],
            transformations=model.get('transformations', [])
        )
    
    def _generate_dimension_model(self, dim: Dict) -> str:
        """Generate a dimension table model"""
        template = self.templates['dimension_model']
        
        return template.render(
            dimension_name=dim['name'],
            source_models=dim['source_models'],
            natural_key=dim['natural_key'],
            attributes=dim['attributes'],
            scd_type=dim.get('scd_type', 1)
        )
    
    def _generate_fact_model(self, fact: Dict) -> str:
        """Generate a fact table model"""
        template = self.templates['fact_model']
        
        return template.render(
            fact_name=fact['name'],
            grain=fact['grain'],
            source_models=fact['source_models'],
            dimensions=fact['dimensions'],
            measures=fact['measures']
        )
```

**Example Generated dbt Model:**

```sql
-- models/marts/finance/fact_mrr.sql
{{
    config(
        materialized='incremental',
        unique_key='mrr_id',
        partition_by={
            "field": "date_month",
            "data_type": "date",
            "granularity": "month"
        }
    )
}}

with subscriptions as (
    select * from {{ ref('stg_stripe__subscriptions') }}
),

customers as (
    select * from {{ ref('dim_customer') }}
),

products as (
    select * from {{ ref('dim_product') }}
),

date_spine as (
    select * from {{ ref('dim_date') }}
    where date_day >= '2020-01-01'
),

subscription_periods as (
    select
        s.subscription_id,
        s.customer_id,
        s.product_id,
        s.status,
        s.amount,
        s.currency,
        s.billing_period,
        s.start_date,
        s.end_date,
        d.date_day,
        d.date_month
    from subscriptions s
    cross join date_spine d
    where d.date_day >= s.start_date
      and (s.end_date is null or d.date_day <= s.end_date)
      and s.status = 'active'
    
    {% if is_incremental() %}
        and d.date_day >= (select max(date_day) from {{ this }})
    {% endif %}
),

final as (
    select
        {{ dbt_utils.generate_surrogate_key([
            'sp.subscription_id',
            'sp.date_month'
        ]) }} as mrr_id,
        
        sp.date_month,
        sp.subscription_id,
        
        -- Foreign keys to dimensions
        c.customer_key,
        p.product_key,
        
        -- Measures
        sp.amount as mrr_amount,
        sp.currency,
        
        -- Metadata
        current_timestamp() as _loaded_at
    
    from subscription_periods sp
    left join customers c
        on sp.customer_id = c.customer_id
        and sp.date_day between c.valid_from and c.valid_to
    left join products p
        on sp.product_id = p.product_id
    
    group by 1,2,3,4,5,6,7
)

select * from final
```

### 7.2 DDL Generator

```python
# core/generators/ddl_generator.py

class DDLGenerator:
    """Generate CREATE TABLE DDL for various database platforms"""
    
    def __init__(self, target_platform: str):
        self.target_platform = target_platform
        self.type_mappings = self._load_type_mappings()
    
    def generate_ddl(self, model_design: Dict) -> List[str]:
        """Generate DDL for all tables in the model"""
        ddl_scripts = []
        
        # Generate for dimensions
        for dim in model_design['dimension_tables']:
            ddl = self._generate_dimension_ddl(dim)
            ddl_scripts.append(ddl)
        
        # Generate for facts
        for fact in model_design['fact_tables']:
            ddl = self._generate_fact_ddl(fact)
            ddl_scripts.append(ddl)
        
        return ddl_scripts
    
    def _generate_dimension_ddl(self, dim: Dict) -> str:
        """Generate DDL for a dimension table"""
        
        # Start with CREATE TABLE
        ddl = f"CREATE TABLE {dim['schema']}.{dim['name']} (\n"
        
        # Surrogate key
        ddl += f"    {dim['name']}_key BIGINT NOT NULL,\n"
        
        # Natural key
        ddl += f"    {dim['natural_key']['name']} {self._map_type(dim['natural_key']['type'])} NOT NULL,\n"
        
        # Attributes
        for attr in dim['attributes']:
            nullable = "NULL" if attr.get('nullable', True) else "NOT NULL"
            ddl += f"    {attr['name']} {self._map_type(attr['type'])} {nullable},\n"
        
        # SCD Type 2 columns if needed
        if dim.get('scd_type') == 2:
            ddl += "    valid_from TIMESTAMP NOT NULL,\n"
            ddl += "    valid_to TIMESTAMP,\n"
            ddl += "    is_current BOOLEAN DEFAULT TRUE,\n"
        
        # Metadata columns
        ddl += "    _loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,\n"
        ddl += "    _updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,\n"
        
        # Primary key
        ddl += f"    PRIMARY KEY ({dim['name']}_key)\n"
        ddl += ");\n\n"
        
        # Indexes
        ddl += f"CREATE INDEX idx_{dim['name']}_{dim['natural_key']['name']} "
        ddl += f"ON {dim['schema']}.{dim['name']} ({dim['natural_key']['name']});\n"
        
        if dim.get('scd_type') == 2:
            ddl += f"CREATE INDEX idx_{dim['name']}_scd "
            ddl += f"ON {dim['schema']}.{dim['name']} (is_current, valid_from, valid_to);\n"
        
        return ddl
    
    def _map_type(self, generic_type: str) -> str:
        """Map generic type to platform-specific type"""
        mappings = {
            'snowflake': {
                'string': 'VARCHAR',
                'integer': 'NUMBER',
                'decimal': 'DECIMAL',
                'boolean': 'BOOLEAN',
                'timestamp': 'TIMESTAMP_NTZ',
                'date': 'DATE'
            },
            'bigquery': {
                'string': 'STRING',
                'integer': 'INT64',
                'decimal': 'NUMERIC',
                'boolean': 'BOOL',
                'timestamp': 'TIMESTAMP',
                'date': 'DATE'
            },
            'postgres': {
                'string': 'VARCHAR',
                'integer': 'BIGINT',
                'decimal': 'NUMERIC',
                'boolean': 'BOOLEAN',
                'timestamp': 'TIMESTAMP',
                'date': 'DATE'
            }
        }
        
        return mappings[self.target_platform].get(generic_type, 'VARCHAR')
```

---

## 8. Implementation Phases

### Phase 1: MVP - Data Modeling (Months 1-3)

**Goal:** CLI tool that can generate dbt projects from conversation

**Deliverables:**
- ✅ Core agent system (LangGraph)
- ✅ 3 MCP servers (Postgres, MySQL, Snowflake)
- ✅ Data Modeling Agent (basic star schema)
- ✅ dbt Generator
- ✅ DDL Generator
- ✅ CLI interface
- ✅ Workspace management
- ✅ Documentation

**Success Metrics:**
- Generate working dbt project in <5 minutes
- 90% of generated models run successfully with `dbt run`
- User requires <30 minutes to review and deploy

**Sprint Breakdown:**

**Sprint 1-2 (Weeks 1-4): Foundation**
- Project structure setup
- MCP Registry implementation
- Basic MCP servers (Postgres, MySQL, Snowflake)
- Workspace Manager
- LangGraph basic flow

**Sprint 3-4 (Weeks 5-8): Core Agent**
- Schema discovery logic
- Data profiling
- Requirements parsing with LLM
- Basic model design (star schema only)
- dbt generator (staging + simple marts)

**Sprint 5-6 (Weeks 9-12): Polish & Launch**
- CLI interface
- End-to-end testing
- Documentation
- Error handling
- Beta release

### Phase 2: Enhanced Capabilities (Months 4-6)

**Goal:** VSCode extension + Pipeline generation + More sources

**Deliverables:**
- ✅ VSCode extension
- ✅ Pipeline Agent (Airflow DAGs)
- ✅ 10+ MCP servers (APIs, SaaS tools)
- ✅ Advanced model types (OBT, Data Vault)
- ✅ Incremental model generation
- ✅ Visual lineage
- ✅ Iterative refinement

**Success Metrics:**
- 500+ active users
- Generate pipelines in <10 minutes
- 80% user satisfaction score

### Phase 3: Full Stack (Months 7-12)

**Goal:** Complete data infrastructure automation

**Deliverables:**
- ✅ Infrastructure Agent (Terraform)
- ✅ Orchestrator Agent (multi-agent coordination)
- ✅ Web dashboard
- ✅ Team collaboration features
- ✅ CI/CD integration
- ✅ Monitoring & observability setup
- ✅ Enterprise features

**Success Metrics:**
- 2000+ active users
- $500K ARR
- Enterprise customers

---

## 9. Technical Stack

### 9.1 Backend

```yaml
Language: Python 3.11+

Core Libraries:
  - langgraph: ^0.2.0          # Agent orchestration
  - anthropic: ^0.25.0         # Claude API
  - pydantic: ^2.7.0           # Data validation
  - fastapi: ^0.111.0          # API server
  - uvicorn: ^0.30.0           # ASGI server
  - websockets: ^12.0          # Real-time communication
  
Database & Data:
  - sqlalchemy: ^2.0.0         # Database abstraction
  - psycopg2-binary: ^2.9.0    # Postgres driver
  - pymysql: ^1.1.0            # MySQL driver
  - snowflake-connector-python: ^3.10.0
  - google-cloud-bigquery: ^3.21.0
  
Code Generation:
  - jinja2: ^3.1.0             # Templating
  - black: ^24.4.0             # Code formatting
  - sqlparse: ^0.5.0           # SQL parsing
  
Git & Files:
  - gitpython: ^3.1.0          # Git operations
  - pathlib: builtin           # File operations
  
Testing:
  - pytest: ^8.2.0
  - pytest-asyncio: ^0.23.0
  - pytest-cov: ^5.0.0
  
Monitoring:
  - structlog: ^24.1.0         # Structured logging
  - prometheus-client: ^0.20.0  # Metrics
```

### 9.2 Frontend

```yaml
CLI:
  - typer: ^0.12.0             # CLI framework
  - rich: ^13.7.0              # Terminal UI
  - textual: ^0.63.0           # TUI framework

VSCode Extension:
  - typescript: ^5.4.0
  - @types/vscode: ^1.89.0
  - vscode-languageclient: ^9.0.0
  
Web Dashboard (Optional):
  - react: ^18.3.0
  - typescript: ^5.4.0
  - vite: ^5.2.0
  - tailwindcss: ^3.4.0
  - react-flow: ^11.11.0       # Lineage visualization
  - shadcn-ui: ^latest         # UI components
```

### 9.3 Infrastructure

```yaml
Development:
  - docker: ^26.0.0
  - docker-compose: ^2.27.0
  
Deployment:
  - kubernetes: ^1.30.0        # Orchestration (Phase 3)
  - helm: ^3.15.0              # K8s package manager
  
CI/CD:
  - github-actions: latest
  
Observability:
  - datadog: ^latest           # APM & logs (Phase 3)
  - sentry: ^latest            # Error tracking
```

---

## 10. Security & Compliance

### 10.1 Credential Management

**Storage:**
```python
# core/security/credentials.py
from cryptography.fernet import Fernet
import keyring
import json

class CredentialManager:
    """
    Secure credential storage using OS keyring.
    Credentials are encrypted at rest.
    """
    
    def __init__(self):
        self.service_name = "dataforge"
        self._encryption_key = self._get_or_create_encryption_key()
        self.cipher = Fernet(self._encryption_key)
    
    def store_credential(
        self,
        source_name: str,
        credential_type: str,  # password, api_key, oauth_token
        value: str
    ):
        """Store encrypted credential in OS keyring"""
        encrypted = self.cipher.encrypt(value.encode())
        keyring.set_password(
            self.service_name,
            f"{source_name}:{credential_type}",
            encrypted.decode()
        )
    
    def get_credential(
        self,
        source_name: str,
        credential_type: str
    ) -> str:
        """Retrieve and decrypt credential"""
        encrypted = keyring.get_password(
            self.service_name,
            f"{source_name}:{credential_type}"
        )
        
        if not encrypted:
            raise ValueError(f"Credential not found: {source_name}:{credential_type}")
        
        decrypted = self.cipher.decrypt(encrypted.encode())
        return decrypted.decode()
    
    def delete_credential(self, source_name: str, credential_type: str):
        """Remove credential from keyring"""
        keyring.delete_password(
            self.service_name,
            f"{source_name}:{credential_type}"
        )
```

### 10.2 Data Privacy

**PII Detection:**
```python
# core/security/pii_detector.py

class PIIDetector:
    """
    Detect PII columns in discovered schemas.
    Recommend encryption/masking strategies.
    """
    
    PII_PATTERNS = {
        'email': r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
        'phone': r'^\+?[\d\s\-\(\)]+$',
        'ssn': r'^\d{3}-\d{2}-\d{4}$',
        'credit_card': r'^\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}$'
    }
    
    PII_KEYWORDS = [
        'email', 'phone', 'ssn', 'social_security',
        'credit_card', 'password', 'address', 'dob',
        'date_of_birth', 'driver_license'
    ]
    
    def detect_pii_columns(self, tables: List[Dict]) -> List[Dict]:
        """
        Identify columns that likely contain PII.
        Returns list of {table, column, pii_type, confidence}
        """
        pii_findings = []
        
        for table in tables:
            for column in table['columns']:
                # Check column name
                pii_type = self._check_column_name(column['name'])
                
                if pii_type:
                    pii_findings.append({
                        'table': table['name'],
                        'column': column['name'],
                        'pii_type': pii_type,
                        'confidence': 0.9,
                        'recommendation': 'Consider encryption or hashing'
                    })
        
        return pii_findings
```

### 10.3 Audit Logging

```python
# core/security/audit_log.py

class AuditLogger:
    """
    Log all sensitive operations for compliance.
    """
    
    def log_data_access(
        self,
        user_id: str,
        source_name: str,
        operation: str,  # query, export, modify
        metadata: Dict
    ):
        """Log data access for audit trail"""
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'user_id': user_id,
            'source': source_name,
            'operation': operation,
            'metadata': metadata,
            'ip_address': get_client_ip()
        }
        
        # Write to audit log (append-only)
        self._write_audit_log(log_entry)
    
    def log_code_generation(
        self,
        user_id: str,
        project_id: str,
        artifacts_generated: List[str]
    ):
        """Log code generation events"""
        pass
```

---

## 11. Testing Strategy

### 11.1 Unit Tests

```python
# tests/unit/test_dbt_generator.py
import pytest
from core.generators.dbt_generator import DBTGenerator

def test_generate_staging_model():
    """Test staging model generation"""
    generator = DBTGenerator(workspace=mock_workspace, target_platform='snowflake')
    
    model = {
        'name': 'stg_customers',
        'source_table': 'raw.customers',
        'columns': [
            {'name': 'customer_id', 'type': 'integer'},
            {'name': 'email', 'type': 'string'}
        ]
    }
    
    sql = generator._generate_staging_model(model)
    
    assert 'stg_customers' in sql
    assert 'source(\'raw\', \'customers\')' in sql
    assert 'customer_id' in sql
    assert 'email' in sql

def test_generate_fact_model():
    """Test fact table generation"""
    # ... test implementation
```

### 11.2 Integration Tests

```python
# tests/integration/test_end_to_end.py
import pytest
from core.agents.modeling import DataModelingAgent

@pytest.mark.asyncio
async def test_complete_modeling_workflow():
    """Test complete workflow from requirements to dbt project"""
    
    # Setup test database with sample data
    test_db = setup_test_postgres()
    
    # Create agent
    agent = DataModelingAgent(
        mcp_registry=test_mcp_registry,
        workspace_manager=test_workspace,
        llm_client=test_llm_client
    )
    
    # Execute workflow
    state = ModelingState(
        user_requirements="Create a sales analytics model",
        sources=[{
            'name': 'test_db',
            'mcp_server': 'test_postgres',
            'type': 'postgres'
        }],
        target_platform='snowflake'
    )
    
    result = await agent.execute(state)
    
    # Assertions
    assert result['generated_dbt'] is not None
    assert 'models/staging' in result['generated_dbt']
    assert len(result['errors']) == 0
    
    # Validate generated dbt project actually works
    dbt_result = run_dbt_project(result['generated_dbt'])
    assert dbt_result.success
```

### 11.3 E2E Tests

```python
# tests/e2e/test_cli.py
import subprocess

def test_cli_generate_command():
    """Test CLI generate command end-to-end"""
    
    result = subprocess.run([
        'dataforge', 'generate',
        '--sources', 'postgres://testdb',
        '--requirement', 'Create customer analytics model',
        '--output', '/tmp/test-project'
    ], capture_output=True)
    
    assert result.returncode == 0
    assert Path('/tmp/test-project/dbt_project.yml').exists()
    assert Path('/tmp/test-project/models').exists()
```

---

## 12. Deployment Architecture

### 12.1 Local Development

```yaml
# docker-compose.yml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - DATABASE_URL=postgresql://user:pass@db:5432/dataforge
    volumes:
      - ./core:/app/core
      - ./interfaces:/app/interfaces
    depends_on:
      - db
      - redis

  db:
    image: postgres:16
    environment:
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
      - POSTGRES_DB=dataforge
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7
    ports:
      - "6379:6379"

volumes:
  postgres_data:
```

### 12.2 Production (Phase 3)

```
┌─────────────────────────────────────────────────────────────┐
│                      Load Balancer                           │
│                    (AWS ALB / GCP LB)                        │
└────────────────────────┬────────────────────────────────────┘
                         │
         ┌───────────────┴────────────────┐
         │                                │
┌────────▼────────┐              ┌───────▼────────┐
│  API Service    │              │  API Service   │
│  (ECS/GKE)      │              │  (ECS/GKE)     │
│  - FastAPI      │              │  - FastAPI     │
│  - Agent System │              │  - Agent System│
└────────┬────────┘              └───────┬────────┘
         │                                │
         └───────────────┬────────────────┘
                         │
         ┌───────────────┴────────────────┐
         │                                │
┌────────▼────────┐              ┌───────▼────────┐
│   PostgreSQL    │              │     Redis      │
│   (RDS/CloudSQL)│              │   (ElastiCache)│
│   - Metadata    │              │   - Cache      │
│   - State       │              │   - Sessions   │
└─────────────────┘              └────────────────┘

Observability:
- Datadog (APM, Logs, Metrics)
- Sentry (Error Tracking)
- CloudWatch/Stackdriver

Storage:
- S3/GCS (Generated artifacts)
- Secrets Manager (Credentials)
```

---

## Appendix A: File Structure

```
dataforge/
├── README.md
├── pyproject.toml
├── setup.py
├── requirements.txt
├── .env.example
├── .gitignore
│
├── core/
│   ├── __init__.py
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base.py                    # BaseDataEngineeringAgent
│   │   ├── modeling.py                # DataModelingAgent
│   │   ├── pipeline.py                # PipelineAgent (Phase 2)
│   │   ├── infrastructure.py          # InfrastructureAgent (Phase 3)
│   │   └── orchestrator.py            # OrchestratorAgent
│   │
│   ├── mcp/
│   │   ├── __init__.py
│   │   ├── registry.py                # MCPRegistry
│   │   ├── client.py                  # MCPClient
│   │   └── servers/                   # Built-in MCP servers
│   │       ├── __init__.py
│   │       ├── postgres.py
│   │       ├── mysql.py
│   │       ├── snowflake.py
│   │       ├── dbt.py
│   │       └── ...
│   │
│   ├── workspace/
│   │   ├── __init__.py
│   │   ├── manager.py                 # WorkspaceManager
│   │   ├── git_ops.py                 # Git operations
│   │   └── templates/                 # Project templates
│   │       ├── dbt_project/
│   │       ├── airflow_project/
│   │       └── terraform_project/
│   │
│   ├── generators/
│   │   ├── __init__.py
│   │   ├── dbt_generator.py           # DBTGenerator
│   │   ├── ddl_generator.py           # DDLGenerator
│   │   ├── dag_generator.py           # AirflowDAGGenerator (Phase 2)
│   │   ├── terraform_generator.py     # TerraformGenerator (Phase 3)
│   │   └── doc_generator.py           # DocGenerator
│   │
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── modeling_graph.py          # LangGraph for modeling
│   │   ├── pipeline_graph.py          # LangGraph for pipelines
│   │   └── orchestration_graph.py     # Multi-agent orchestration
│   │
│   ├── validators/
│   │   ├── __init__.py
│   │   ├── dbt_validator.py
│   │   ├── sql_validator.py
│   │   └── terraform_validator.py
│   │
│   ├── security/
│   │   ├── __init__.py
│   │   ├── credentials.py             # CredentialManager
│   │   ├── pii_detector.py            # PIIDetector
│   │   └── audit_log.py               # AuditLogger
│   │
│   └── utils/
│       ├── __init__.py
│       ├── llm_client.py              # Claude API client
│       ├── logger.py
│       └── config.py
│
├── interfaces/
│   ├── __init__.py
│   │
│   ├── cli/
│   │   ├── __init__.py
│   │   ├── main.py                    # CLI entry point
│   │   ├── commands/
│   │   │   ├── __init__.py
│   │   │   ├── init.py
│   │   │   ├── generate.py
│   │   │   ├── deploy.py
│   │   │   ├── source.py
│   │   │   └── chat.py
│   │   └── ui/                        # Rich/Textual components
│   │       ├── __init__.py
│   │       ├── chat_interface.py
│   │       └── progress.py
│   │
│   ├── vscode/                        # VSCode extension (Phase 2)
│   │   ├── package.json
│   │   ├── tsconfig.json
│   │   ├── src/
│   │   │   ├── extension.ts
│   │   │   ├── chat_panel.ts
│   │   │   ├── lineage_view.ts
│   │   │   └── api_client.ts
│   │   └── webview/
│   │       └── index.html
│   │
│   └── web/                           # Web dashboard (Phase 3)
│       ├── package.json
│       ├── vite.config.ts
│       ├── src/
│       │   ├── App.tsx
│       │   ├── pages/
│       │   ├── components/
│       │   └── api/
│       └── public/
│
├── api/
│   ├── __init__.py
│   ├── server.py                      # FastAPI application
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── agent.py                   # Agent execution endpoints
│   │   ├── workspace.py               # Workspace management
│   │   ├── mcp.py                     # MCP operations
│   │   └── auth.py                    # Authentication
│   ├── websocket.py                   # WebSocket for streaming
│   └── middleware.py
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── unit/
│   │   ├── test_agents.py
│   │   ├── test_generators.py
│   │   ├── test_mcp.py
│   │   └── test_workspace.py
│   ├── integration/
│   │   ├── test_modeling_workflow.py
│   │   └── test_mcp_integration.py
│   └── e2e/
│       ├── test_cli.py
│       └── test_api.py
│
├── docs/
│   ├── README.md
│   ├── architecture.md
│   ├── mcp_guide.md
│   ├── api_reference.md
│   └── user_guide.md
│
├── examples/
│   ├── basic_modeling/
│   ├── complex_pipeline/
│   └── full_stack/
│
├── docker/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── docker-compose.dev.yml
│
└── deployment/                        # Phase 3
    ├── kubernetes/
    ├── terraform/
    └── helm/
```

---

## Appendix B: API Reference

### REST API Endpoints

```
POST   /api/v1/agent/execute
POST   /api/v1/workspace/create
GET    /api/v1/workspace/{id}
POST   /api/v1/workspace/{id}/files
GET    /api/v1/mcp/servers
POST   /api/v1/mcp/query
WS     /api/v1/agent/stream
```

### WebSocket Protocol

```json
// Client → Server
{
  "type": "execute_agent",
  "agent_type": "modeling",
  "params": {
    "requirements": "Create MRR model",
    "sources": [...]
  }
}

// Server → Client (streaming events)
{
  "type": "step_start",
  "step": "discover_schemas",
  "message": "Connecting to Postgres...",
  "timestamp": "2025-10-12T10:30:00Z"
}

{
  "type": "thinking",
  "message": "Analyzing 15 tables...",
  "data": {...}
}

{
  "type": "file_generated",
  "path": "models/staging/stg_customers.sql",
  "content": "..."
}

{
  "type": "complete",
  "summary": "Generated 12 models successfully",
  "workspace_path": "/path/to/workspace"
}
```

---

## Appendix C: Configuration Files

### MCP Server Configuration

```yaml
# ~/.dataforge/mcp-servers.yml

servers:
  - name: production_postgres
    type: database
    subtype: postgres
    version: 1.0.0
    connection:
      host: prod-db.example.com
      port: 5432
      database: production
      user: ${POSTGRES_USER}
      password: ${POSTGRES_PASSWORD}
    capabilities:
      - schema_discovery
      - query_execution
      - data_profiling
    health_check:
      interval: 60
      timeout: 10
  
  - name: stripe_api
    type: api
    subtype: rest
    version: 1.0.0
    connection:
      base_url: https://api.stripe.com/v1
      auth_type: bearer
      api_key: ${STRIPE_API_KEY}
    capabilities:
      - data_extraction
      - schema_discovery
    rate_limit:
      requests_per_second: 100
```

### DataForge Configuration

```yaml
# ~/.dataforge/config.yml

workspace:
  base_path: ~/dataforge-workspaces
  default_git_branch: main
  auto_commit: true

llm:
  provider: anthropic
  model: claude-sonnet-4-20250514
  max_tokens: 8000
  temperature: 0.2

generators:
  dbt:
    default_materialization: table
    test_severity: warn
    docs_enabled: true
  
  sql:
    formatting: true
    style: standard

security:
  credential_storage: keyring  # or: vault, env
  audit_logging: true

logging:
  level: INFO
  format: json
  file: ~/.dataforge/logs/dataforge.log
```

---

## Appendix D: Roadmap

### Q4 2025 (Months 1-3): MVP

- ✅ Core agent system
- ✅ MCP framework
- ✅ Data Modeling Agent
- ✅ CLI interface
- ✅ 3 database connectors
- 🎯 Beta launch
- 🎯 50 beta users

### Q1 2026 (Months 4-6): Enhanced

- VSCode extension
- Pipeline Agent
- 10+ data sources
- Visual lineage
- 🎯 500 active users
- 🎯 First paying customers

### Q2-Q3 2026 (Months 7-12): Scale

- Infrastructure Agent
- Multi-agent orchestration
- Web dashboard
- Enterprise features
- 🎯 2000 active users
- 🎯 $500K ARR

### 2027+: Platform

- Marketplace for MCP servers
- Collaborative features
- Advanced analytics
- Multi-cloud support
- 🎯 10,000 active users
- 🎯 $5M ARR

---

**Document Status:** Design Phase  
**Last Updated:** October 12, 2025  
**Next Review:** After MVP completion

---

This technical implementation document serves as the blueprint for building DataForge. It should be treated as a living document and updated as implementation progresses and new insights emerge.