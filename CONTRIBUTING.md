# Contributing to DataForge

Thank you for your interest in contributing to DataForge! This document provides guidelines and instructions for contributing.

## 🎯 Project Vision

DataForge aims to be the "Claude Code for Data Engineers" - an AI-powered platform that transforms natural language requirements into production-ready data infrastructure.

## 🚀 Getting Started

### 1. Fork and Clone

```bash
# Fork the repo on GitHub, then:
git clone https://github.com/YOUR_USERNAME/dataforge.git
cd dataforge
```

### 2. Set Up Development Environment

```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install all dependencies (uv creates .venv automatically)
uv sync --all-extras

# Install pre-commit hooks
uv run pre-commit install
```

### 3. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix
```

## 📋 Development Workflow

### Before You Code

1. **Check existing issues** - See if someone is already working on it
2. **Create an issue** - Describe what you plan to work on
3. **Get feedback** - Wait for maintainer feedback before starting large changes

### While Coding

1. **Follow the style guide** (see below)
2. **Write tests** - All new code should have tests
3. **Update documentation** - Keep docs in sync with code
4. **Commit frequently** - Small, focused commits are better

### Code Style

We use automated formatters and linters:

```bash
# Format code
uv run black .

# Lint code
uv run ruff check . --fix

# Type check
uv run mypy core/ interfaces/ api/

# All checks (runs automatically on commit)
uv run pre-commit run --all-files
```

**Style Guidelines:**
- Line length: 100 characters
- Use type hints for all function signatures
- Write docstrings for all public functions/classes
- Follow PEP 8 naming conventions

### Testing

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/unit/test_agents.py

# Run with coverage
uv run pytest --cov=core --cov=interfaces --cov=api

# Run only fast tests (skip slow integration tests)
uv run pytest -m "not slow"
```

**Testing Guidelines:**
- Write unit tests for all new functions/classes
- Write integration tests for cross-component functionality
- Aim for >80% code coverage
- Use fixtures from conftest.py
- Mock external dependencies (APIs, databases)

### Documentation

```bash
# Serve docs locally
cd docs
uv run mkdocs serve

# Build docs
uv run mkdocs build
```

**Documentation Guidelines:**
- Update README.md for major changes
- Add docstrings to all public APIs
- Update relevant docs/ files
- Include code examples where appropriate

## 🏗️ Project Structure

### Adding a New Agent

1. Create agent file in `core/agents/your_agent.py`
2. Inherit from `BaseDataEngineeringAgent`
3. Implement required methods
4. Add tests in `tests/unit/test_your_agent.py`
5. Update `core/agents/__init__.py`

Example:
```python
from core.agents.base import BaseDataEngineeringAgent, AgentCapability

class YourAgent(BaseDataEngineeringAgent):
    def _get_agent_type(self) -> AgentType:
        return AgentType.YOUR_TYPE

    def _define_capabilities(self) -> List[AgentCapability]:
        return [...]

    async def can_handle(self, task: Dict) -> bool:
        # Implementation

    async def execute(self, state: AgentState) -> AgentState:
        # Implementation
```

### Adding a New MCP Server

1. Create server file in `core/mcp/servers/your_server.py`
2. Implement connection and operations
3. Add configuration to mcp-servers.yml template
4. Add tests in `tests/integration/test_mcp_your_server.py`

### Adding a New CLI Command

1. Add command in `interfaces/cli/commands/your_command.py`
2. Register in `interfaces/cli/main.py`
3. Add tests in `tests/e2e/test_cli.py`
4. Update CLI documentation

### Adding a New API Endpoint

1. Create route in `api/routes/your_route.py`
2. Register in `api/server.py`
3. Add tests in `tests/integration/test_api.py`
4. Update API documentation

## 🐛 Reporting Bugs

### Before Reporting

1. Check if the bug has already been reported
2. Try to reproduce with the latest version
3. Collect relevant information (logs, environment, etc.)

### Bug Report Template

```markdown
**Description**
Clear description of the bug

**To Reproduce**
Steps to reproduce:
1.
2.
3.

**Expected Behavior**
What you expected to happen

**Actual Behavior**
What actually happened

**Environment**
- OS: [e.g., macOS 14.0]
- Python version: [e.g., 3.11.5]
- DataForge version: [e.g., 0.1.0]

**Logs**
```
Paste relevant logs here
```

**Additional Context**
Any other relevant information
```

## 💡 Feature Requests

We love feature ideas! Please:

1. **Check existing issues** - Someone might have already suggested it
2. **Describe the problem** - What are you trying to solve?
3. **Propose a solution** - How do you envision it working?
4. **Consider alternatives** - Are there other ways to solve this?

## 📝 Pull Request Process

### Before Submitting

- [ ] Tests pass: `pytest`
- [ ] Linting passes: `pre-commit run --all-files`
- [ ] Documentation updated
- [ ] CHANGELOG.md updated (if applicable)
- [ ] No merge conflicts

### PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
Describe testing done

## Checklist
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] Code follows style guide
- [ ] All tests pass
```

### Review Process

1. Automated checks run (CI/CD)
2. Maintainer reviews code
3. Address feedback
4. Approval and merge

## 🎨 Code Review Guidelines

### As a Contributor

- Be responsive to feedback
- Ask questions if unclear
- Be patient - reviews take time
- Learn from the process

### As a Reviewer

- Be constructive and kind
- Explain the "why" behind suggestions
- Approve promptly when ready
- Welcome first-time contributors

## 📦 Release Process

(For maintainers)

1. Update version in `pyproject.toml`
2. Update CHANGELOG.md
3. Create release branch
4. Run full test suite
5. Tag release: `git tag v0.1.0`
6. Push tag: `git push origin v0.1.0`
7. Create GitHub release
8. Publish to PyPI (when ready)

## 🏆 Recognition

Contributors are recognized in:
- CHANGELOG.md
- GitHub contributors page
- Annual thank-you posts

## 🤝 Code of Conduct

### Our Pledge

We are committed to providing a welcoming and inclusive experience for everyone.

### Our Standards

**Positive behavior:**
- Using welcoming and inclusive language
- Being respectful of differing viewpoints
- Gracefully accepting constructive criticism
- Focusing on what is best for the community

**Unacceptable behavior:**
- Harassment, trolling, or insulting comments
- Personal or political attacks
- Publishing others' private information
- Other conduct which could reasonably be considered inappropriate

### Enforcement

Report issues to: conduct@dataforge.dev

## 📚 Resources

- [Architecture Documentation](docs/architecture.md)
- [API Reference](docs/api_reference.md)
- [Development Roadmap](plan.md)
- [Project Setup](PROJECT_SETUP.md)

## ❓ Questions?

- **GitHub Discussions**: For questions and discussions
- **GitHub Issues**: For bugs and feature requests
- **Email**: dev@dataforge.dev

## 🙏 Thank You!

Every contribution, no matter how small, makes a difference. Thank you for helping make DataForge better!

---

**Happy coding!** 🚀
