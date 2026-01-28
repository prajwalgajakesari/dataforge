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
- Access to at least one data source (Postgres, MySQL, Snowflake, etc.)

### Installation

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh
# Or on macOS/Linux: brew install uv
# Or on Windows: powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Clone the repository
git clone https://github.com/your-org/dataforge.git
cd dataforge

# Install dependencies (uv automatically creates and manages virtual environment)
uv sync

# Or install with development dependencies
uv sync --extra dev

# Activate the virtual environment (optional - uv run handles this)
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### Configuration

1. **Copy the example environment file:**
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` and add your credentials:**
   ```bash
   # Required
   ANTHROPIC_API_KEY=your_api_key_here

   # Add credentials for your data sources
   POSTGRES_HOST=localhost
   POSTGRES_USER=postgres
   POSTGRES_PASSWORD=your_password
   # ... etc
   ```

3. **Configure MCP servers** (optional):

   DataForge will create a default configuration at `~/.dataforge/mcp-servers.yml`.
   Edit this file to enable the data sources you want to use.

### Usage

```bash
# Run commands with uv (no need to activate venv)
uv run dataforge chat

# Or activate venv first
source .venv/bin/activate
dataforge chat

# Use specific commands
uv run dataforge init my-project --type dbt
uv run dataforge generate model --source postgres --requirements "Create a customer analytics mart"
```

### Example Workflow

```bash
# 1. Initialize a new workspace
uv run dataforge init sales-analytics --type dbt

# 2. Connect your data source (interactive)
uv run dataforge source add postgres

# 3. Generate models through conversation
uv run dataforge chat

> "I need a sales analytics data mart with customer dimensions and order facts"

# DataForge will:
# - Discover your database schemas
# - Analyze the data
# - Design an optimal star schema
# - Generate dbt models
# - Create documentation
# - Commit everything to git

# 4. Review the generated code
cd ~/dataforge-workspaces/sales-analytics
dbt run
dbt test
```

---

## 📁 Project Structure

```
dataforge/
├── core/                      # Core business logic
│   ├── agents/               # AI agents for different tasks
│   │   ├── base.py          # Base agent interface
│   │   ├── modeling.py      # Data modeling agent
│   │   └── ...
│   ├── mcp/                  # MCP integration layer
│   │   ├── registry.py      # MCP server registry
│   │   ├── client.py        # Universal MCP client
│   │   └── servers/         # Built-in MCP servers
│   ├── workspace/            # Workspace management
│   │   ├── manager.py       # File and git operations
│   │   └── templates/       # Project templates
│   ├── generators/           # Code generators
│   │   ├── dbt_generator.py
│   │   └── ...
│   └── utils/                # Utilities
│       ├── config.py        # Configuration
│       └── logger.py        # Logging
│
├── interfaces/               # User interfaces
│   ├── cli/                 # Command-line interface
│   └── ...
│
├── api/                      # API server (FastAPI)
│   ├── server.py
│   └── routes/
│
├── tests/                    # Test suite
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
└── docs/                     # Documentation
```

---

## 🔧 Development

### Setup Development Environment

```bash
# Install with all dependencies (dev, test, docs)
uv sync --all-extras

# Install pre-commit hooks
uv run pre-commit install

# Run tests
uv run pytest

# Run with coverage
uv run pytest --cov=core --cov=interfaces --cov=api

# Format code
uv run black .
uv run ruff check . --fix

# Type checking
uv run mypy core/ interfaces/ api/
```

### Running Tests

```bash
# All tests
uv run pytest

# Specific test file
uv run pytest tests/unit/test_agents.py

# With verbose output
uv run pytest -v

# Stop on first failure
uv run pytest -x
```

### Building Documentation

```bash
# Install docs dependencies
pip install -e ".[docs]"

# Serve docs locally
cd docs
mkdocs serve

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
- ✅ Core agent system (LangGraph)
- ✅ MCP registry and client
- ✅ Workspace manager
- 🚧 Data modeling agent
- 🚧 dbt generator
- 🚧 CLI interface
- 📅 DDL generator
- 📅 Data profiling
- 📅 Schema discovery

### Phase 2: Enhanced Capabilities (Q2 2025)
- VSCode extension
- Pipeline generation (Airflow)
- 10+ MCP servers for various sources
- Advanced modeling (Data Vault, OBT)
- Visual lineage diagrams

### Phase 3: Full Stack (Q3-Q4 2025)
- Infrastructure automation (Terraform)
- Web dashboard
- Team collaboration features
- CI/CD integration
- Enterprise features

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
