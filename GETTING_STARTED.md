# Getting Started with DataForge Data Modeling

Welcome! This guide will help you generate your first dbt project using DataForge in under 5 minutes.

## Prerequisites

Before starting, ensure you have:

- ✅ Python 3.11 or higher
- ✅ [uv](https://github.com/astral-sh/uv) package installer
- ✅ PostgreSQL database with sample data (or another supported database)
- ✅ Anthropic API key ([get one here](https://console.anthropic.com/))

## Quick Start (5 minutes)

### Step 1: Installation (1 minute)

```bash
# Clone the repository
git clone https://github.com/your-org/dataforge.git
cd dataforge

# Install dependencies
uv sync

# Activate virtual environment (optional - uv run handles this)
source .venv/bin/activate
```

### Step 2: Configuration (2 minutes)

```bash
# Copy example environment file
cp .env.example .env

# Edit .env and add your credentials
nano .env  # or use your preferred editor
```

**Minimum required configuration:**

```bash
# Required: Your Anthropic API key
ANTHROPIC_API_KEY=sk-ant-your-key-here

# Required: PostgreSQL connection details
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=your_user
POSTGRES_PASSWORD=your_password
POSTGRES_DATABASE=your_database
```

### Step 3: Run Your First Project (2 minutes)

```bash
# Run the example workflow
uv run python examples/modeling_workflow_example.py
```

**That's it!** DataForge will:
1. ✨ Connect to your database
2. 🔍 Discover your schemas and tables
3. 🤖 Use AI to design an optimal data model
4. 📊 Generate a complete dbt project
5. 💾 Save everything to a workspace with git

### Step 4: Review Your Generated Project

```bash
# Navigate to your generated project
cd ~/dataforge-workspaces/ecommerce_analytics

# Explore the structure
tree models/

# Review generated models
cat models/marts/fct_orders.sql
```

## What You Get

After running the workflow, you'll have a complete dbt project:

```
ecommerce_analytics/
├── dbt_project.yml          ✅ Project configuration
├── packages.yml             ✅ Dependencies (dbt_utils, etc.)
├── models/
│   ├── staging/            ✅ Clean source data
│   │   ├── sources.yml
│   │   ├── schema.yml
│   │   ├── stg_customers.sql
│   │   └── stg_orders.sql
│   └── marts/              ✅ Analytics-ready models
│       ├── schema.yml
│       ├── dim_customers.sql
│       ├── dim_products.sql
│       └── fct_orders.sql
└── README.md               ✅ Documentation
```

## Running Your dbt Project

Once generated, you can run your dbt project:

```bash
# Install dbt if you haven't already
pip install dbt-core dbt-postgres

# Install dbt dependencies
dbt deps

# Run your models
dbt run

# Run tests
dbt test

# Generate and view documentation
dbt docs generate
dbt docs serve
```

## Customize Your Models

### Change the Requirements

Edit `examples/modeling_workflow_example.py` and modify the `requirements` string:

```python
requirements = """
Create a sales analytics data mart with:

1. Customer Dimension:
   - Demographics and segments
   - Lifetime value

2. Product Dimension:
   - Product details and categories

3. Sales Fact:
   - Transaction details
   - Revenue and quantities
   - Grain: one row per order line item
"""
```

Then run the example again:

```bash
uv run python examples/modeling_workflow_example.py
```

### Use Different Database

To use MySQL, Snowflake, or another database:

1. **Configure the MCP server** in `~/.dataforge/mcp-servers.yml`:

```yaml
servers:
  - name: mysql
    type: database
    capabilities: [query, execute, schema]
    connection_config:
      host: ${MYSQL_HOST}
      user: ${MYSQL_USER}
      password: ${MYSQL_PASSWORD}
      database: ${MYSQL_DATABASE}
    enabled: true
```

2. **Set environment variables:**

```bash
export MYSQL_HOST=localhost
export MYSQL_USER=root
export MYSQL_PASSWORD=password
export MYSQL_DATABASE=analytics
```

3. **Update the example** to use MySQL instead of Postgres

## Interactive CLI (Coming Soon)

Soon you'll be able to use the interactive CLI:

```bash
# Start interactive session
uv run dataforge chat

> "I want to create an analytics mart for my e-commerce data"

# DataForge will guide you through the process interactively
```

## Common Workflows

### Workflow 1: Generate from Existing Database

```bash
# 1. Point to your database
export POSTGRES_DATABASE=production_db

# 2. Run with your requirements
uv run python examples/modeling_workflow_example.py

# 3. Review and deploy
cd ~/dataforge-workspaces/my_project
dbt run
```

### Workflow 2: Iterative Development

```python
# Create initial version
state = await agent.execute(initial_state)

# Review generated models
# ... make manual adjustments if needed ...

# Re-run with refined requirements
refined_state = await agent.execute(refined_state)
```

### Workflow 3: Streaming Progress

```python
# Get real-time updates during generation
async for state in workflow.stream(requirements="..."):
    print(f"Progress: {state['progress']:.0%}")
    print(f"Current step: {state['current_step']}")
```

## Configuration Options

### Model Generation Options

```python
parameters = {
    "project_name": "my_analytics",
    "target_database": "analytics",
    "target_schema": "marts",
    "staging_schema": "staging",
}
```

### LLM Options

```python
from core.utils.llm_client import LLMClient

client = LLMClient(
    model="claude-3-5-sonnet-20241022",  # or "claude-3-5-haiku-20241022"
    temperature=0.0,                      # 0.0 for deterministic
    max_tokens=4096,
)
```

### MCP Options

Configure in `~/.dataforge/mcp-servers.yml`:

```yaml
servers:
  - name: postgres
    timeout: 60              # Connection timeout
    health_check_interval: 60
    retry_policy:
      max_retries: 3
      backoff_factor: 2
```

## Troubleshooting

### Issue: "API key not found"

**Solution:**
```bash
export ANTHROPIC_API_KEY=your_key_here
# Or add to .env file
```

### Issue: "Database connection failed"

**Solution:**
- Check credentials in `.env`
- Verify database is running
- Check network connectivity
- Test connection: `psql -h localhost -U postgres`

### Issue: "No schemas discovered"

**Solution:**
- Verify database has tables
- Check user permissions
- Try: `SELECT * FROM information_schema.tables LIMIT 1;`

### Issue: "Generated SQL has errors"

**Solution:**
- Review model design in output
- Check data types mapping
- Manually edit generated SQL
- Adjust requirements and re-run

### Issue: "Cost too high"

**Solution:**
- Use Claude Haiku for cheaper generation
- Limit number of tables to profile
- Use smaller sample sizes
- Cache schema discovery results

## Next Steps

Now that you have your first project:

1. **Read the Implementation Guide**: [docs/IMPLEMENTATION_GUIDE.md](docs/IMPLEMENTATION_GUIDE.md)
2. **Explore Examples**: [examples/](examples/)
3. **Run Tests**: `uv run pytest tests/`
4. **Customize Your Workflow**: Edit the example scripts
5. **Add New Data Sources**: Configure additional MCP servers
6. **Deploy to Production**: Set up CI/CD for your dbt project

## Learning Resources

- **Architecture Overview**: [README.md](README.md)
- **Implementation Details**: [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)
- **API Documentation**: [docs/api_reference.md](docs/api_reference.md)
- **Contributing Guide**: [CONTRIBUTING.md](CONTRIBUTING.md)

## Getting Help

- **Issues**: [GitHub Issues](https://github.com/your-org/dataforge/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-org/dataforge/discussions)
- **Examples**: Check the [examples/](examples/) directory

## Tips for Success

✅ **Start Simple**: Begin with a small database (5-10 tables)
✅ **Be Specific**: Provide clear requirements about your desired model
✅ **Iterate**: Generate, review, refine, and regenerate
✅ **Review Output**: Always review generated SQL before running in production
✅ **Monitor Costs**: Check LLM usage statistics after each run
✅ **Version Control**: All generated projects include git initialization
✅ **Test Thoroughly**: Run `dbt test` before deploying

## What's Next?

After mastering the basics:

- 🚀 Try advanced modeling patterns (Data Vault, OBT)
- 🔧 Create custom MCP servers for your data sources
- 🎨 Customize dbt project templates
- 📊 Generate Airflow DAGs (coming soon)
- ☁️ Deploy infrastructure with Terraform (coming soon)
- 🌐 Use the web interface (coming soon)

---

**Happy Data Modeling! 🎉**

Questions? Check the [docs/](docs/) directory or open an issue.

---

**Made with ❤️ by the DataForge team**
