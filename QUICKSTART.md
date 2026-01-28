# DataForge Quick Start Guide

Get up and running with DataForge in 5 minutes!

## 📋 Prerequisites

Before starting, ensure you have:
- Python 3.11+ installed
- [uv](https://github.com/astral-sh/uv) - Fast Python package installer
- Git installed
- An Anthropic API key ([Get one here](https://console.anthropic.com/))
- Access to a database (PostgreSQL, MySQL, Snowflake, etc.)

## 🚀 Installation

### Step 1: Install uv

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or with Homebrew
brew install uv

# Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### Step 2: Clone and Setup

```bash
# Clone the repository
git clone https://github.com/your-org/dataforge.git
cd dataforge

# Install dependencies (uv creates .venv automatically)
uv sync
```

### Step 3: Configure Environment

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env and add your API key
# Required: ANTHROPIC_API_KEY
# Optional: Database credentials for your sources
```

Minimal `.env` configuration:
```bash
ANTHROPIC_API_KEY=sk-ant-api03-...your-key-here
DATAFORGE_ENV=development
```

### Step 4: Verify Installation

```bash
# Check that DataForge is installed correctly
uv run python -m interfaces.cli.main version

# Check status
uv run python -m interfaces.cli.main status
```

## 🎯 Your First Project

### Create a Workspace

```bash
# Initialize a new dbt project workspace
uv run python -m interfaces.cli.main init my-first-project --type dbt
```

This creates a new workspace at `~/dataforge-workspaces/my-first-project/`

### List Workspaces

```bash
# See all your workspaces
uv run python -m interfaces.cli.main list
```

## 🔧 Configure Data Sources

DataForge uses MCP (Model Context Protocol) servers to connect to data sources.

### Option 1: Edit Configuration File

```bash
# Edit the MCP servers configuration
# This file is created automatically on first run
nano ~/.dataforge/mcp-servers.yml
```

Example configuration:
```yaml
version: "1.0"
servers:
  - name: postgres
    type: database
    version: "1.0.0"
    capabilities: [query, execute, schema]
    connection_config:
      host: localhost
      port: 5432
      database: mydb
      user: postgres
      password: mypassword
    enabled: true
```

### Option 2: Use Environment Variables

Add to your `.env`:
```bash
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
POSTGRES_DATABASE=mydb
```

## 💬 Start Using DataForge

### Interactive Chat (Coming Soon)

```bash
uv run python -m interfaces.cli.main chat
```

### API Server

```bash
# Start the API server
uv run python -m api.server

# In another terminal, test it
curl http://localhost:8000/health
```

## 📚 What's Next?

1. **Read the Documentation**
   - [Architecture Guide](docs/architecture.md)
   - [MCP Integration Guide](docs/mcp_guide.md)
   - [User Guide](docs/user_guide.md)

2. **Explore Examples**
   - Check out the `examples/` directory
   - Try the sample projects

3. **Run Tests**
   ```bash
   uv sync --extra test
   uv run pytest
   ```

4. **Start Generating Models**
   - Connect your data sources
   - Describe what you want to build
   - Let DataForge generate production-ready code!

## 🐛 Troubleshooting

### "Module not found" errors

Make sure dependencies are installed:
```bash
uv sync
```

### API key not working

Verify your API key is set correctly:
```bash
uv run python -m interfaces.cli.main status
```

Should show "API Key: ✓ Set"

### Can't connect to database

Check your database credentials and ensure:
1. The database is running
2. Network access is allowed
3. Credentials in `.env` are correct

## 💡 Tips

- Use `--help` with any command to see all options
- Check logs at `~/.dataforge/` for debugging
- Join our community for support and discussions

## 🆘 Getting Help

- **Documentation**: [Full docs](docs/)
- **Issues**: [GitHub Issues](https://github.com/your-org/dataforge/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-org/dataforge/discussions)

---

**Ready to build? Let's go!** 🚀
