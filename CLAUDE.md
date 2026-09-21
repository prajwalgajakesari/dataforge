# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this is

DataForge is a Python 3.11+ CLI and library for AI-assisted data modeling. It profiles a
PostgreSQL schema, detects functional dependencies and normal-form violations, asks Claude for
a star schema, 3NF or Data Vault design, and generates a dbt project or SQL DDL from that
design. The CLI entry point is `dataforge` (Typer, defined in `interfaces/cli/main.py`).

Status is alpha. Read `README.md` "Status" before promising a capability.

## Repository layout

| Path | Purpose |
|---|---|
| `interfaces/cli/` | Typer CLI (`main.py`) and the interactive chat REPL (`chat.py`) |
| `core/analysis/` | Profiler, functional dependency detector, candidate key finder, type and pattern inference |
| `core/normalization/` | 1NF to BCNF violation detection and decomposition helpers |
| `core/generators/` | dbt project generator (star schema), 3NF and Data Vault generators |
| `core/validators/` | Schema, design, output and data validators |
| `core/prompts/` | Prompt templates for the design step |
| `core/graph/` | LangGraph workflow that chains discovery, profiling, design and generation |
| `core/agents/` | Agent wrapper around the workflow |
| `core/mcp/` | Registry and client scaffolding; `servers/postgres_mcp.py` is the only real connector |
| `core/models/` | Pydantic models for schemas, analysis results and designs |
| `core/utils/` | Settings (`config.py`), Anthropic client (`llm_client.py`), logging |
| `core/workspace/` | Workspace directories with git initialisation |
| `api/` | FastAPI server with session based modeling routes |
| `web/` | React + Vite prototype UI, not yet wired to the API |
| `examples/` | Sample schema and design files plus a full workflow script |
| `skills/dataforge/` | Claude Code skill that drives the CLI |
| `docs/` | Getting started guide and design documents |
| `tests/` | pytest suites (unit, integration, e2e) |

## Setup and commands

```bash
uv sync --all-extras                 # install runtime, dev, test and docs extras
uv run dataforge --help              # CLI help
uv run dataforge version
uv run pytest                        # full suite with coverage (pyproject addopts)
uv run pytest tests/unit -q          # quick unit run
uv run ruff check core interfaces api
uv run black --check core interfaces api
uv run mypy core interfaces api
uv run uvicorn api.server:app --reload   # API at http://localhost:8000/docs
```

Configuration is read from environment variables and a `.env` file by `core/utils/config.py`.
Names that matter: `ANTHROPIC_API_KEY`, `DEFAULT_MODEL`, `DATAFORGE_WORKSPACE_DIR`,
`POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DATABASE`.
Never read or print `.env`; use `uv run dataforge status` to check whether the key is set.

## Conventions

- Formatting: black, line length 100. Linting: ruff (rules E, W, F, I, B, C4, UP). Types: mypy
  with `disallow_untyped_defs`. All configured in `pyproject.toml`.
- Keep CLI commands runnable without a database or API key where possible. `normalize`,
  `generate` and `validate` work from files; only `analyze` needs PostgreSQL and only `design`
  and `chat` need Claude.
- Do not add a dependency without also updating `uv.lock` (`uv add <pkg>`).
- Generated code must be valid dbt. The sample design in `examples/` is checked with the
  output validator and with `dbt parse`.
- Tests live under `tests/`. Mock the LLM and the database; the one test that needs both is
  skipped by default.

## Driving DataForge as a skill

`skills/dataforge/SKILL.md` documents the verified end to end workflow and its guardrails.
Follow it when a user asks to profile, normalize, design or generate a data model.
