# DataForge Examples

This directory contains practical examples demonstrating how to use DataForge.

## Available Examples

### 1. Modeling Workflow Example ([modeling_workflow_example.py](modeling_workflow_example.py))

Complete demonstration of the data modeling workflow from database discovery to dbt project generation.

**What it demonstrates:**
- Workspace initialization
- MCP registry setup
- Data modeling agent execution
- Schema discovery
- AI-powered model design
- dbt project generation
- Error handling and logging
- Usage and cost tracking

**Prerequisites:**
```bash
# Set environment variables
export ANTHROPIC_API_KEY=your_api_key
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_USER=postgres
export POSTGRES_PASSWORD=password
export POSTGRES_DATABASE=analytics
```

**Run:**
```bash
uv run python examples/modeling_workflow_example.py
```

**Expected Output:**
- Workspace created at `~/dataforge-workspaces/ecommerce_analytics`
- Complete dbt project generated
- Model design summary
- LLM usage statistics
- Next steps instructions

### Alternative Examples in the Same File

#### Custom Configuration Example
Shows how to use custom PostgreSQL configuration:
```python
asyncio.run(example_with_custom_config())
```

#### Streaming Updates Example
Demonstrates real-time workflow progress:
```python
asyncio.run(example_with_streaming())
```

## Quick Start

1. **Install dependencies:**
   ```bash
   uv sync
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

3. **Run an example:**
   ```bash
   uv run python examples/modeling_workflow_example.py
   ```

## Example Output

```
================================================================================
DataForge - Data Modeling Workflow Example
================================================================================

[1/5] Initializing workspace...
✓ Created workspace: /Users/you/dataforge-workspaces/ecommerce_analytics

[2/5] Initializing MCP registry...
✓ Available data sources: ['postgres']

[3/5] Initializing LLM client...
✓ Using model: claude-3-5-sonnet-20241022

[4/5] Creating data modeling agent...
✓ Agent capabilities: ['schema_discovery', 'data_profiling', ...]

[5/5] Executing modeling workflow...
--------------------------------------------------------------------------------
Starting model generation...
Discovering schemas...
Discovered 3 schemas
Selecting relevant schema...
Selected schema: public
Discovering tables...
Discovered 12 tables
Profiling data...
Profiled 12 tables
Designing data model...
Designed 12 staging, 4 dimensions, 2 facts
Generating dbt project...
Generated 24 files
--------------------------------------------------------------------------------

✓ Modeling workflow completed!

Generated 24 files:
  - dbt_project.yml
  - models/staging/sources.yml
  - models/staging/stg_customers.sql
  - models/marts/dim_customers.sql
  - models/marts/fct_orders.sql
  ...

Model Design Summary:
  Staging Models: 12
  Dimensions: 4
  Facts: 2

Workspace Location:
  /Users/you/dataforge-workspaces/ecommerce_analytics

Next Steps:
  1. cd /Users/you/dataforge-workspaces/ecommerce_analytics
  2. Review generated dbt project
  3. Configure ~/.dbt/profiles.yml with your database credentials
  4. Run: dbt deps
  5. Run: dbt run
  6. Run: dbt test

LLM Usage:
  Total Tokens: 15,234
  Cost: $0.0456

✓ Cleaned up resources
```

## Customizing Examples

### Change Requirements

Edit the `requirements` string in the example:

```python
requirements = """
Create a custom analytics mart with:
1. Your dimension 1
2. Your dimension 2
3. Your fact table
"""
```

### Use Different Database

Configure different MCP server:

```python
custom_config = MCPServerConfig(
    name="mysql",
    type="database",
    connection_config={
        "host": "mysql-host",
        "user": "user",
        # ...
    },
)
```

### Add Custom Parameters

Pass additional parameters to the agent:

```python
state = AgentState(
    # ...
    parameters={
        "project_name": "my_project",
        "target_database": "analytics",
        "target_schema": "custom_schema",
        "materialize_as": "table",  # or "view"
    },
)
```

## Troubleshooting

### Error: "Anthropic API key is required"
**Solution:** Set `ANTHROPIC_API_KEY` environment variable

### Error: "No data sources available"
**Solution:** Configure MCP servers in `~/.dataforge/mcp-servers.yml`

### Error: "PostgreSQL connection failed"
**Solution:** Check database credentials and network access

### Warning: "Could not profile table X"
**Solution:** This is normal for large tables. Profiling is optional and failures won't stop the workflow.

## More Information

- **Implementation Guide**: [../docs/IMPLEMENTATION_GUIDE.md](../docs/IMPLEMENTATION_GUIDE.md)
- **Implementation Summary**: [../IMPLEMENTATION_SUMMARY.md](../IMPLEMENTATION_SUMMARY.md)
- **Full Documentation**: [../README.md](../README.md)
- **API Documentation**: [../docs/api_reference.md](../docs/api_reference.md)

## Contributing Examples

To add a new example:

1. Create a new Python file in this directory
2. Follow the structure of existing examples
3. Add comprehensive comments
4. Include error handling
5. Update this README
6. Test the example thoroughly

## License

MIT License - see [LICENSE](../LICENSE) for details.
