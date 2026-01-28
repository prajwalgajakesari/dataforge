# Implementation Guide

## Overview

This document provides a comprehensive guide to the DataForge implementation, focusing on the four main components that have been implemented:

1. **DBTGenerator** - dbt project generation
2. **PostgresMCP** - PostgreSQL schema discovery
3. **LangGraph Workflow** - Modeling agent orchestration
4. **LLM Client** - Anthropic Claude integration

## Architecture

### Component Diagram

```
┌─────────────────────────────────────────────┐
│         DataModelingAgent                   │
│  (Orchestrates the entire workflow)         │
└─────────────┬───────────────────────────────┘
              │
              ├──> ModelingWorkflow (LangGraph)
              │    ├─> discover_schemas
              │    ├─> select_schema
              │    ├─> discover_tables
              │    ├─> profile_data
              │    ├─> design_model
              │    ├─> generate_dbt
              │    └─> validate
              │
              ├──> PostgresMCP
              │    ├─> Schema Discovery
              │    ├─> Table Discovery
              │    └─> Data Profiling
              │
              ├──> LLMClient (Claude)
              │    ├─> Model Design
              │    ├─> Schema Selection
              │    └─> Structured Output
              │
              └──> DBTGenerator
                   ├─> Project Configuration
                   ├─> Source Definitions
                   ├─> Staging Models
                   ├─> Dimension Models
                   └─> Fact Models
```

## Component Details

### 1. LLM Client (`core/utils/llm_client.py`)

The LLM Client provides a unified interface for interacting with Anthropic's Claude models.

#### Features

- **Automatic retries** with exponential backoff
- **Token usage tracking** and cost estimation
- **Structured output** support via Pydantic models
- **Streaming** support for real-time responses
- **Multiple models** (Sonnet, Opus, Haiku)

#### Usage Example

```python
from core.utils.llm_client import LLMClient

# Initialize client
client = LLMClient(
    model="claude-3-5-sonnet-20241022",
    temperature=0.0,
    max_tokens=4096,
)

# Simple text generation
response = await client.generate(
    prompt="Design a data model for e-commerce",
    system="You are a data modeling expert",
)

print(response.content)
print(f"Cost: ${response.usage.cost_usd:.4f}")

# Structured output
from pydantic import BaseModel

class ModelDesign(BaseModel):
    tables: list[str]
    relationships: list[str]

design, response = await client.generate_structured(
    prompt="Design a simple e-commerce schema",
    response_model=ModelDesign,
)

print(design.tables)  # Validated Pydantic model
```

#### Configuration

Set in `.env` or environment:

```bash
ANTHROPIC_API_KEY=your_key_here
DEFAULT_MODEL=claude-3-5-sonnet-20241022
MODEL_TEMPERATURE=0.0
MODEL_MAX_TOKENS=4096
```

#### Cost Tracking

The client automatically tracks token usage and costs:

```python
# After multiple calls
usage = client.get_total_usage()
print(f"Total tokens: {usage.total_tokens:,}")
print(f"Total cost: ${usage.cost_usd:.4f}")
```

---

### 2. DBT Generator (`core/generators/dbt_generator.py`)

Generates complete dbt projects from model design specifications.

#### Features

- **Complete project structure** (dbt_project.yml, profiles.yml, etc.)
- **Source definitions** with tests
- **Staging models** with best practices
- **Dimension models** with surrogate keys
- **Fact models** with grain documentation
- **Schema YAML** with tests and descriptions
- **Documentation** generation

#### Usage Example

```python
from core.generators.dbt_generator import (
    DBTGenerator,
    ModelDesign,
    SourceDefinition,
    TableDefinition,
    ColumnDefinition,
    StagingModelDefinition,
    DimensionModelDefinition,
    FactModelDefinition,
)

# Define your model design
design = ModelDesign(
    project_name="ecommerce_analytics",
    sources=[
        SourceDefinition(
            name="postgres",
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
                        ),
                        ColumnDefinition(
                            name="email",
                            data_type="varchar",
                        ),
                    ],
                )
            ],
        )
    ],
    staging_models=[...],
    dimension_models=[...],
    fact_models=[...],
)

# Generate project
generator = DBTGenerator(
    project_name="ecommerce_analytics",
    target_dir="./my_dbt_project",
)

files = generator.generate_project(design)

# Write to disk
generator.write_to_disk()
```

#### Generated Structure

```
my_dbt_project/
├── dbt_project.yml
├── packages.yml
├── .gitignore
├── README.md
├── .dbt/
│   └── profiles.yml
└── models/
    ├── docs.md
    ├── staging/
    │   ├── sources.yml
    │   ├── schema.yml
    │   └── stg_*.sql
    └── marts/
        ├── schema.yml
        ├── dim_*.sql
        └── fct_*.sql
```

#### Best Practices Implemented

- CTEs for readability
- Surrogate keys using `dbt_utils.generate_surrogate_key()`
- Consistent naming (stg_, dim_, fct_ prefixes)
- Comprehensive testing (unique, not_null, relationships)
- Grain documentation for facts
- Schema descriptions
- README with setup instructions

---

### 3. PostgresMCP (`core/mcp/servers/postgres_mcp.py`)

MCP server implementation for PostgreSQL databases.

#### Features

- **Schema discovery** with system schema filtering
- **Table discovery** with metadata (row counts, sizes)
- **Column discovery** with constraints (PK, FK)
- **Data profiling** (null%, distinct counts, min/max/avg)
- **Query execution** with parameter binding
- **Connection pooling** for performance
- **Health checks** for monitoring

#### Usage Example

```python
from core.mcp.servers.postgres_mcp import PostgresMCP
from core.mcp.registry import MCPServerConfig

# Configure connection
config = MCPServerConfig(
    name="postgres",
    type="database",
    capabilities=["query", "execute", "schema"],
    connection_config={
        "host": "localhost",
        "port": 5432,
        "user": "postgres",
        "password": "password",
        "database": "analytics",
    },
    enabled=True,
)

# Initialize and connect
mcp = PostgresMCP(config)
await mcp.connect()

# Discover schemas
schemas = await mcp.discover_schemas(exclude_system=True)
for schema in schemas:
    print(f"Schema: {schema.schema_name}")
    print(f"Tables: {len(schema.tables)}")

# Discover tables
tables = await mcp.discover_tables("public")
for table in tables:
    print(f"Table: {table.table_name}")
    print(f"Columns: {len(table.columns)}")
    print(f"Rows: {table.row_count}")

# Profile data
profiles = await mcp.profile_table(
    schema_name="public",
    table_name="customers",
    sample_size=1000,
)

for profile in profiles:
    print(f"Column: {profile.column_name}")
    print(f"Null %: {profile.null_percentage}%")
    print(f"Distinct: {profile.distinct_count}")

# Execute queries
result = await mcp.execute_query(
    query="SELECT * FROM customers LIMIT 10",
    fetch_size=10,
)

print(f"Rows: {result['row_count']}")
print(f"Columns: {result['columns']}")

# Cleanup
await mcp.disconnect()
```

#### MCP Protocol Operations

The PostgresMCP implements these MCP operations:

- `discover_schemas`: List all schemas
- `discover_tables`: List tables in schema
- `discover_columns`: Get column metadata
- `profile_table`: Get data statistics
- `query`: Execute SELECT queries

---

### 4. LangGraph Workflow (`core/graph/modeling_graph.py`)

Orchestrates the modeling workflow as a state graph.

#### Features

- **State management** across steps
- **Error handling** with recovery
- **Progress tracking** (0-100%)
- **Streaming updates** for real-time feedback
- **Conditional edges** for decision making
- **Checkpointing** support (future)

#### Workflow Steps

1. **discover_schemas**: Find available database schemas
2. **select_schema**: Use LLM to select relevant schema
3. **discover_tables**: Get table metadata
4. **profile_data**: Sample and analyze data
5. **design_model**: Use LLM to design star schema
6. **generate_dbt**: Create dbt project files
7. **validate**: Check generated files
8. **handle_error**: Error recovery

#### Usage Example

```python
from core.graph.modeling_graph import ModelingWorkflow
from core.mcp.servers.postgres_mcp import PostgresMCP
from core.utils.llm_client import LLMClient

# Initialize components
postgres_mcp = PostgresMCP(config)
await postgres_mcp.connect()

llm_client = LLMClient()

# Create workflow
workflow = ModelingWorkflow(
    mcp_client=postgres_mcp,
    llm_client=llm_client,
    workspace_path="./workspace",
)

# Run workflow
state = await workflow.run(
    requirements="Create a customer analytics data mart",
    data_source="postgres",
    project_name="analytics",
)

# Check results
if state["status"] == "completed":
    print(f"Generated {len(state['generated_files'])} files")
    print(f"Model design: {state['model_design']}")
else:
    print(f"Errors: {state['errors']}")
```

#### Streaming Updates

```python
# Stream workflow updates
async for state in workflow.stream(
    requirements="Create analytics mart",
):
    print(f"Step: {state['current_step']}")
    print(f"Progress: {state['progress']:.0%}")

    if state['errors']:
        print(f"Errors: {state['errors']}")
```

#### State Schema

```python
class ModelingState(TypedDict):
    # Input
    requirements: str
    data_source: str
    workspace_path: str

    # Discovery
    available_schemas: List[Dict]
    selected_schema: str
    discovered_tables: List[Dict]
    data_profiles: Dict[str, List[Dict]]

    # Design
    model_design: Dict

    # Generation
    generated_files: Dict[str, str]

    # Status
    current_step: str
    status: str
    errors: List[str]
    warnings: List[str]
    progress: float
```

---

## Complete Workflow Integration

### DataModelingAgent

The `DataModelingAgent` orchestrates all components:

```python
from core.agents.modeling import DataModelingAgent
from core.agents.base import AgentState, AgentType

# Create agent
agent = DataModelingAgent(
    mcp_registry=mcp_registry,
    workspace_manager=workspace_manager,
    llm_client=llm_client,
)

# Create state
state = AgentState(
    user_id="user123",
    agent_type=AgentType.MODELING,
    workspace_path="./workspace",
    requirements="Create e-commerce analytics mart",
    parameters={"project_name": "ecommerce"},
)

# Execute
result = await agent.execute(state)

# Check results
if result.status == TaskStatus.COMPLETED:
    print(f"Generated files: {len(result.generated_artifacts)}")
    print(f"Model design: {result.discovered_context['model_design']}")
```

---

## Testing

### Unit Tests

```bash
# Run unit tests
uv run pytest tests/unit/

# With coverage
uv run pytest tests/unit/ --cov=core
```

### Integration Tests

```bash
# Run integration tests
uv run pytest tests/integration/

# Specific test
uv run pytest tests/integration/test_modeling_workflow.py -v
```

### End-to-End Tests

```bash
# Run with real database (requires setup)
uv run pytest -m integration

# Skip slow tests
uv run pytest -m "not slow"
```

---

## Configuration

### Environment Variables

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-xxx

# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=password
POSTGRES_DATABASE=analytics

# Optional
DEFAULT_MODEL=claude-3-5-sonnet-20241022
MODEL_TEMPERATURE=0.0
MODEL_MAX_TOKENS=4096
DATAFORGE_WORKSPACE_DIR=~/dataforge-workspaces
```

### MCP Configuration

Edit `~/.dataforge/mcp-servers.yml`:

```yaml
version: "1.0"
servers:
  - name: postgres
    type: database
    capabilities: [query, execute, schema]
    connection_config:
      host: ${POSTGRES_HOST}
      port: ${POSTGRES_PORT}
      database: ${POSTGRES_DATABASE}
      user: ${POSTGRES_USER}
      password: ${POSTGRES_PASSWORD}
    enabled: true
```

---

## Best Practices

### 1. Error Handling

Always wrap operations in try-except:

```python
try:
    result = await agent.execute(state)
except Exception as e:
    logger.error(f"Workflow failed: {e}", exc_info=True)
    # Handle error
```

### 2. Resource Cleanup

Always disconnect MCP clients:

```python
try:
    await mcp.connect()
    # Do work
finally:
    await mcp.disconnect()
```

### 3. Cost Monitoring

Track LLM usage:

```python
usage = llm_client.get_total_usage()
logger.info(f"Cost: ${usage.cost_usd:.4f}")

# Reset for next session
llm_client.reset_usage()
```

### 4. Workspace Management

Use workspace manager for file operations:

```python
workspace = workspace_manager.create_workspace(
    name="project",
    project_type="dbt",
)

# Write files
workspace_manager.write_file(
    "models/my_model.sql",
    content,
    auto_commit=True,
)
```

---

## Performance Optimization

### 1. Connection Pooling

PostgresMCP uses asyncpg connection pooling:

```python
# Pool size configuration
connection_config = {
    "min_size": 2,
    "max_size": 10,
    "timeout": 30,
}
```

### 2. Parallel Discovery

Discover multiple schemas in parallel:

```python
schemas = await asyncio.gather(
    *[mcp.discover_tables(schema) for schema in schema_names]
)
```

### 3. Sampling

Limit data profiling to samples:

```python
profiles = await mcp.profile_table(
    schema_name="public",
    table_name="large_table",
    sample_size=1000,  # Only sample 1000 rows
)
```

---

## Troubleshooting

### Common Issues

1. **API Key Not Found**
   ```
   ValueError: Anthropic API key is required
   ```
   Solution: Set `ANTHROPIC_API_KEY` environment variable

2. **Database Connection Failed**
   ```
   ConnectionError: PostgreSQL connection failed
   ```
   Solution: Check database credentials and network access

3. **LLM Response Not Valid JSON**
   ```
   ValueError: LLM did not return valid JSON
   ```
   Solution: Increase temperature or adjust prompt

4. **Workspace Already Exists**
   ```
   ValueError: Workspace 'name' already exists
   ```
   Solution: Choose different name or delete existing workspace

### Debug Mode

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

---

## Next Steps

1. **Add More MCP Servers**: MySQL, Snowflake, BigQuery
2. **Enhance Model Design**: Support for Data Vault, OBT patterns
3. **Add Validators**: SQL linting, schema validation
4. **Implement Checkpointing**: Resume failed workflows
5. **Add Streaming UI**: Real-time progress in web interface

---

## Support

- **Documentation**: See `/docs` directory
- **Examples**: See `/examples` directory
- **Issues**: GitHub Issues
- **Tests**: See `/tests` directory

---

**Last Updated**: 2025-01-12
**Version**: 1.0.0
