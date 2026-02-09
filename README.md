# DataForge

> **AI-Powered Data Engineering Platform**

DataForge is an intelligent data engineering platform that enables you to build complete data infrastructure through natural conversation. Generate production-ready dbt models, data pipelines, and infrastructure code using AI agents.

**Think of it as "Claude Code for Data Engineers"**

---

## 🎯 Vision

Transform data engineering from manual, time-consuming work into a conversational, AI-driven experience. Describe your data needs in plain English, and DataForge generates production-ready code automatically.

## ✨ Features

### Phase 1: MVP - Data Modeling (Current)
- 🤖 **AI-Powered Data Modeling**: Conversational interface to design dimensional models
- 📊 **Automatic Schema Discovery**: Connect to databases and analyze schemas automatically
- 🔍 **Data Profiling**: Profile data quality, patterns, and relationships
- 🎨 **dbt Project Generation**: Generate complete dbt projects with models, tests, and docs
- 🏗️ **Star Schema Design**: Automatically design facts and dimensions
- 📝 **DDL Generation**: Create table definitions for your target warehouse
- 🔄 **Git Integration**: All generated code is version controlled

### Coming Soon
- **Phase 2**: Pipeline generation (Airflow DAGs), VSCode extension
- **Phase 3**: Infrastructure automation (Terraform), web dashboard, team collaboration

---

## 🏗️ Architecture

DataForge is built on a modern, agent-based architecture:

```
┌─────────────────────────────────────────────────┐
│           Interface Layer                        │
│   CLI · VSCode Extension · Web Dashboard         │
└─────────────────┬───────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────┐
│         Agent Orchestration (LangGraph)          │
│   Modeling Agent · Pipeline Agent · Infra Agent │
└─────────────────┬───────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────┐
│         MCP Integration Layer                    │
│   Postgres · MySQL · Snowflake · BigQuery       │
│   dbt · Airflow · Git · Terraform                │
└─────────────────┬───────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────┐
│       Workspace Management                       │
│   File System · Git Ops · Templates              │
└──────────────────────────────────────────────────┘
```

### Key Components

- **Agents**: Specialized AI agents for different tasks (modeling, pipelines, infrastructure)
- **MCP Integration**: Universal protocol for connecting to data sources and tools
- **Workspace Manager**: File system and git operations for generated code
- **Code Generators**: Template-based code generation for dbt, Airflow, Terraform

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11 or higher
- [uv](https://github.com/astral-sh/uv) - Fast Python package installer
- Git
- Anthropic API key (for Claude)
- Access to at least one data source (PostgreSQL connection)
- Node.js 18+ (only if running the web frontend)

### Installation

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh
# Or on macOS: brew install uv

# Clone the repository
git clone https://github.com/your-org/dataforge.git
cd dataforge

# Install dependencies (uv automatically creates and manages virtual environment)
uv sync

# Or install with development dependencies
uv sync --extra dev

# Activate the virtual environment (optional - uv run handles this automatically)
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### Configuration

1. **Copy the example environment file:**
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` and add your credentials:**
   ```bash
   # Required - your Anthropic API key
   ANTHROPIC_API_KEY=your_api_key_here

   # Database connection (the database you want to model)
   POSTGRES_HOST=localhost
   POSTGRES_PORT=5432
   POSTGRES_USER=postgres
   POSTGRES_PASSWORD=your_password
   POSTGRES_DATABASE=your_database
   ```

3. **Configure MCP servers** (optional):

   DataForge will create a default configuration at `~/.dataforge/mcp-servers.yml`.
   Edit this file to register additional data sources.

---

## 🖥️ Running DataForge

DataForge can be used in three ways: **CLI**, **API server**, or **Web UI**.

### Option 1: CLI

The CLI provides six commands for the full data modeling workflow:

```bash
# Check configuration and connected services
uv run dataforge status

# Start an interactive chat session for conversational modeling
uv run dataforge chat

# Analyze a database schema (profiling, FD detection, key discovery)
uv run dataforge analyze postgresql://user:pass@localhost/mydb \
  --schema public \
  --output table

# Normalize a schema to a target normal form
uv run dataforge normalize schema.json --target 3NF --verbose

# Design a data model from requirements using LLM
uv run dataforge design "Build a star schema for e-commerce analytics" \
  --strategy STAR_SCHEMA \
  --input analysis.json \
  --output design.json

# Generate dbt or SQL code from a design file
uv run dataforge generate design.json --format dbt --output ./my_dbt_project

# Validate a schema, design, or generated output
uv run dataforge validate ./my_dbt_project --type output

# Initialize a new workspace
uv run dataforge init my-project --type dbt

# List existing workspaces
uv run dataforge list
```

### Option 2: API Server (FastAPI)

```bash
# Start the API server (runs at http://localhost:8000)
uv run uvicorn api.server:app --reload

# Or run directly
uv run python -m api.server
```

Once running:
- **Swagger docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Option 3: Web Frontend

```bash
# Install frontend dependencies
cd web
npm install

# Start the dev server (runs at http://localhost:5173)
npm run dev

# Build for production
npm run build
```

> **Note:** The web frontend requires the API server to be running.

---

## 📖 Usage Workflows

### End-to-End CLI Workflow

```bash
# Step 1: Analyze your database to profile tables, find keys and dependencies
uv run dataforge analyze postgresql://user:pass@localhost/sales \
  --schema public \
  --output table \
  --output-file analysis.json

# Step 2: (Optional) Check normalization violations
uv run dataforge normalize analysis.json --target 3NF --verbose

# Step 3: Design a data model using LLM
#   Strategies: STAR_SCHEMA, NORMALIZED_3NF, DATA_VAULT
uv run dataforge design "Sales analytics mart with customer dimensions and order facts" \
  --strategy STAR_SCHEMA \
  --input analysis.json \
  --output design.json

# Step 4: Generate dbt project from the design
uv run dataforge generate design.json --format dbt --output ./sales_dbt

# Step 5: Validate the generated output
uv run dataforge validate ./sales_dbt --type output

# Step 6: Run your dbt project
cd sales_dbt
dbt run
dbt test
```

### API Workflow

Use the REST API to drive the same pipeline programmatically:

| Step | Method | Endpoint | Description |
|------|--------|----------|-------------|
| 1 | `POST` | `/api/v1/modeling/sessions/` | Create a session (project name, requirements, data source, strategy) |
| 2 | `POST` | `/api/v1/modeling/sessions/{id}/discover` | Discover database schemas |
| 3 | `GET` | `/api/v1/modeling/sessions/{id}/tables` | List discovered tables |
| 4 | `POST` | `/api/v1/modeling/sessions/{id}/profile` | Profile data quality and statistics |
| 5 | `POST` | `/api/v1/modeling/sessions/{id}/design` | Design model with LLM |
| 6 | `POST` | `/api/v1/modeling/sessions/{id}/generate` | Generate dbt code |
| 7 | `GET` | `/api/v1/modeling/sessions/{id}/files` | List generated files |
| 8 | `GET` | `/api/v1/modeling/sessions/{id}/files/{path}` | Get file content |

Example with `curl`:

```bash
# Create a session
curl -X POST http://localhost:8000/api/v1/modeling/sessions/ \
  -H "Content-Type: application/json" \
  -d '{
    "project_name": "sales_analytics",
    "requirements": "Build a star schema for e-commerce sales",
    "data_source": "postgres",
    "modeling_strategy": "STAR_SCHEMA"
  }'

# Run discovery (replace SESSION_ID with the id from the response above)
curl -X POST http://localhost:8000/api/v1/modeling/sessions/SESSION_ID/discover

# Continue through profile -> design -> generate...
```

### Interactive Chat

For a conversational experience:

```bash
uv run dataforge chat
```

Within the chat, describe what you need in plain English:
> "I need a sales analytics data mart with customer dimensions and order facts"

DataForge will walk through discovery, profiling, design, and generation interactively.

### Modeling Strategies

| Strategy | CLI Flag | What It Produces | dbt Generation |
|----------|----------|------------------|----------------|
| **Star Schema** | `STAR_SCHEMA` | Staging models, dimensions, fact tables | Supported |
| **Normalized 3NF** | `NORMALIZED_3NF` | Entities + relationships | Design only |
| **Data Vault 2.0** | `DATA_VAULT` | Hubs, links, satellites | Design only |

### Output Formats

The `generate` command supports:
- **`dbt`** - Complete dbt project (models, sources, tests, docs, `dbt_project.yml`)
- **`sql`** - Raw DDL `CREATE TABLE` statements

---

## 📁 Project Structure

```
dataforge/
├── core/                          # Core business logic
│   ├── agents/                   # AI agents (base + modeling)
│   ├── analysis/                 # Data analysis modules
│   │   ├── profiler.py          # Enhanced data profiling
│   │   ├── fd_detector.py       # Functional dependency detection
│   │   ├── key_finder.py        # Candidate key discovery
│   │   ├── relationship_inferrer.py  # Relationship inference
│   │   ├── pattern_detector.py  # Pattern detection
│   │   └── type_inference.py    # Semantic type inference
│   ├── normalization/            # Normalization engine
│   │   ├── violations.py        # Violation detection (1NF-BCNF)
│   │   ├── normalizer_1nf.py   # 1NF normalizer
│   │   ├── normalizer_2nf.py   # 2NF normalizer
│   │   ├── normalizer_3nf.py   # 3NF normalizer
│   │   └── decomposer.py       # Table decomposition
│   ├── generators/               # Code generators
│   │   ├── dbt_generator.py     # dbt project generation
│   │   ├── generator_3nf.py     # 3NF SQL generation
│   │   └── generator_data_vault.py  # Data Vault generation
│   ├── validators/               # Validation layer
│   │   ├── schema_validator.py  # Schema validation
│   │   ├── design_validator.py  # Design validation
│   │   ├── output_validator.py  # Output validation
│   │   └── data_validator.py    # Data validation
│   ├── graph/                    # LangGraph workflow
│   │   ├── modeling_graph.py    # Main workflow orchestration
│   │   └── nodes/               # Modular graph nodes
│   ├── mcp/                      # MCP integration layer
│   │   ├── registry.py          # MCP server registry
│   │   ├── client.py            # Universal MCP client
│   │   └── servers/             # Built-in MCP servers (Postgres)
│   ├── models/                   # Data models (Pydantic)
│   ├── prompts/                  # LLM prompt templates
│   ├── workspace/                # Workspace and git management
│   └── utils/                    # Config, LLM client, logging
│
├── interfaces/                    # User interfaces
│   └── cli/                      # Typer CLI application
│       ├── main.py              # CLI commands
│       └── chat.py              # Interactive chat mode
│
├── api/                           # REST API (FastAPI)
│   ├── server.py                 # FastAPI app and lifespan
│   ├── dependencies.py           # Dependency injection
│   ├── models/                   # API request/response models
│   └── routes/                   # API routes
│       ├── modeling/            # Modeling endpoints
│       │   ├── sessions.py     # Session CRUD
│       │   ├── discovery.py    # Schema discovery
│       │   ├── profiling.py    # Data profiling
│       │   ├── design.py       # Model design
│       │   └── generation.py   # Code generation
│       └── health.py            # Health check
│
├── web/                           # React frontend (Vite + TypeScript)
│   ├── src/                      # React source code
│   └── package.json
│
├── tests/                         # Test suite
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── .env.example                   # Environment variable template
└── pyproject.toml                 # Python project configuration
```

---

## 🔧 Development

### Setup Development Environment

```bash
# Install with all dependencies (dev, test, docs)
uv sync --all-extras

# Install pre-commit hooks
uv run pre-commit install
```

### Running the Full Stack Locally

```bash
# Terminal 1: Start the API server
uv run uvicorn api.server:app --reload
# -> http://localhost:8000 (Swagger at /docs)

# Terminal 2: Start the web frontend
cd web && npm install && npm run dev
# -> http://localhost:5173
```

### Running Tests

```bash
# All tests
uv run pytest

# Specific test file
uv run pytest tests/unit/test_agents.py

# With verbose output
uv run pytest -v

# With coverage
uv run pytest --cov=core --cov=interfaces --cov=api

# Stop on first failure
uv run pytest -x
```

### Code Quality

```bash
# Format code
uv run black .
uv run ruff check . --fix

# Type checking
uv run mypy core/ interfaces/ api/
```

### Building Documentation

```bash
# Install docs dependencies
uv sync --extra docs

# Serve docs locally
cd docs && mkdocs serve

# Build static site
mkdocs build
```

---

## 🔌 Extending DataForge

### Adding a New MCP Server

1. Create a new server implementation in `core/mcp/servers/`:
   ```python
   # core/mcp/servers/your_source.py
   from core.mcp.client import MCPClient

   class YourSourceMCP(MCPClient):
       # Implement connection and operations
       pass
   ```

2. Register it in `~/.dataforge/mcp-servers.yml`:
   ```yaml
   servers:
     - name: your_source
       type: database
       capabilities: [query, schema]
       connection_config:
         host: ${YOUR_SOURCE_HOST}
         # ... etc
   ```

### Creating Custom Templates

1. Add a template directory in `core/workspace/templates/`:
   ```
   templates/
   └── your_template/
       ├── template.yml       # Template metadata
       ├── dbt_project.yml
       └── models/
   ```

2. Use it when creating workspaces:
   ```python
   workspace.create_workspace(
       name="my-project",
       project_type="dbt",
       template="your_template"
   )
   ```

---

## 📚 Documentation

- **[Architecture Guide](docs/architecture.md)** - Detailed system architecture
- **[MCP Integration Guide](docs/mcp_guide.md)** - Working with MCP servers
- **[API Reference](docs/api_reference.md)** - API documentation
- **[User Guide](docs/user_guide.md)** - Complete user guide

---

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Development Workflow

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests and linting
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

---

## 📋 Roadmap

### Phase 1: MVP - Data Modeling (Current)
- ✅ Core agent system (LangGraph workflow)
- ✅ MCP registry and PostgreSQL client
- ✅ Workspace manager with git integration
- ✅ Schema discovery and table introspection
- ✅ Data profiling (statistics, quality scores, semantic types)
- ✅ Functional dependency detection and candidate key discovery
- ✅ Normalization engine (1NF through BCNF violation detection)
- ✅ LLM-powered model design (Star Schema, 3NF, Data Vault)
- ✅ dbt project generation (Star Schema)
- ✅ DDL/SQL generation
- ✅ Validation layer (schema, design, output)
- ✅ CLI with analyze, normalize, design, generate, validate, chat commands
- ✅ REST API (FastAPI) with session-based workflow
- ✅ React web frontend

### Phase 2: Enhanced Capabilities
- 📅 VSCode extension
- 📅 Pipeline generation (Airflow)
- 📅 Additional MCP servers (MySQL, Snowflake, BigQuery)
- 📅 dbt generation for 3NF and Data Vault strategies
- 📅 Visual lineage diagrams

### Phase 3: Full Stack
- 📅 Infrastructure automation (Terraform)
- 📅 Team collaboration features
- 📅 CI/CD integration
- 📅 Enterprise features

---

## 🔒 Security

- All credentials are encrypted at rest
- PII detection to prevent accidental exposure
- Audit logging for all operations
- No data is sent to external services except the LLM API

See our [Security Policy](SECURITY.md) for more details.

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- Built with [LangGraph](https://github.com/langchain-ai/langgraph) for agent orchestration
- Powered by [Anthropic Claude](https://www.anthropic.com/) for AI capabilities
- Inspired by the amazing work of the dbt community

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/your-org/dataforge/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-org/dataforge/discussions)
- **Email**: support@dataforge.dev

---

## 🌟 Star History

If you find DataForge useful, please consider giving it a star on GitHub!

---

**Made with ❤️ by the DataForge team**
