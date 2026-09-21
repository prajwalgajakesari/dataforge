# DataForge

Profile a PostgreSQL schema, check its normal forms, ask Claude for a star schema, 3NF or
Data Vault design, and generate a dbt project. From the terminal, or from Claude Code.

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue?style=flat-square)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json&style=flat-square)](https://github.com/astral-sh/uv)
[![Claude Code plugin](https://img.shields.io/badge/Claude%20Code-plugin-d97757?style=flat-square)](skills/dataforge/SKILL.md)
[![Status: alpha](https://img.shields.io/badge/status-alpha-orange?style=flat-square)](#status)

## What it does

- **Profiles a live PostgreSQL schema** (`analyze`): row counts, null rates, distinct counts,
  semantic types, functional dependencies and candidate keys, saved as JSON.
- **Finds normal form violations** (`normalize`): array and JSON columns and repeating groups
  (1NF), partial dependencies (2NF), transitive dependencies (3NF), non-superkey
  determinants (BCNF).
- **Designs a model with Claude** (`design`): star schema, normalized 3NF or Data Vault 2.0,
  returned as a JSON design you can edit.
- **Generates code** (`generate`): a complete dbt project for star schema designs (models,
  sources, tests, docs, `dbt_project.yml`), or one `CREATE TABLE` file per table for any
  strategy.
- **Validates every artifact** (`validate`): schema files, design files, and generated
  projects. The output validator parses SQL, checks `ref()` targets and YAML, and runs
  `dbt compile` when dbt is installed.
- **Works offline where it can**: `normalize`, `generate` and `validate` need neither a
  database nor an API key.
- Also included: a chat REPL, a FastAPI server with a session based flow, a LangGraph
  workflow that chains the steps, and a Claude Code skill so Claude can run all of this.

## How it works

```text
 input                 command      core module                          output
 ---------------------- ----------  -----------------------------------  ----------------------
 postgresql:// URL  --> analyze  -> core/analysis (profiler, fd_detector, -> analysis.json
                                    key_finder)
 analysis/schema.json > normalize-> core/normalization/violations         -> violation report
 requirements + file -> design   -> core/prompts + core/utils/llm_client   -> design.json
                                    (Anthropic API)
 design.json        --> generate -> core/generators/dbt_generator or DDL -> dbt project / *.sql
 any of the above   --> validate -> core/validators                       -> VALID / INVALID
```

The CLI (`interfaces/cli/main.py`, Typer) calls these modules directly. The same steps are
wired into a LangGraph state machine in `core/graph/modeling_graph.py`, which the API and the
example script use to run discovery, profiling, design and generation in one pass.

## Quick start

```bash
git clone https://github.com/prajwalgajakesari/dataforge.git
cd dataforge
uv sync
cp .env.example .env        # optional; set ANTHROPIC_API_KEY here for the design step
uv run dataforge version
```

First command, no database or API key needed:

```bash
uv run dataforge normalize examples/sample_schema.json --target 3NF --verbose
```

```text
Normalizing to 3NF

+---------------------- Normalization Analysis -----------------------+
| Current Normal Form: UNNORMALIZED                                   |
| Target Normal Form: 3NF                                             |
| Violations Found:                                                   |
|   - 1NF: 1                                                          |
|   - 2NF: 2                                                          |
|   - 3NF: 1                                                          |
|   - BCNF: 3                                                         |
+---------------------------------------------------------------------+
                            2NF Violations
| Table       | Type         | Description                                                  |
| order_items | Violation2NF | 2NF Violation in order_items: {product_id} -> {product_name} |
| order_items | Violation2NF | 2NF Violation in order_items: {order_id} -> {customer_id}    |
```

Then turn a design into a dbt project and validate it:

```bash
uv run dataforge validate examples/sample_star_design.json --type design
uv run dataforge generate examples/sample_star_design.json --format dbt --output ./out/sales_dbt
uv run dataforge validate ./out/sales_dbt --type output
```

The generated project parses with dbt 1.11 (`dbt deps` then `dbt parse`, using the included
`.dbt/profiles.yml`). See [docs/getting-started.md](docs/getting-started.md) for the full
walkthrough, including the database and Claude steps.

## CLI reference

| Command | Needs API key | Needs database | What it does |
|---|---|---|---|
| `dataforge analyze URL [--schema S] [--table T ...] [--output json\|yaml\|table] [--output-file F] [--sample-size N]` | no | PostgreSQL | Profile tables, detect FDs and candidate keys |
| `dataforge normalize FILE [--target 1NF\|2NF\|3NF\|BCNF] [--verbose] [--output F]` | no | no | Report normal form violations and required steps |
| `dataforge design "REQUIREMENTS or file" [--strategy STAR_SCHEMA\|NORMALIZED_3NF\|DATA_VAULT] [--input F] [--output F] [--model M]` | yes | no | Ask Claude for a design as JSON |
| `dataforge generate DESIGN [--format dbt\|sql] [--output DIR] [--overwrite]` | no | no | Write a dbt project (star schema) or DDL files |
| `dataforge validate PATH [--type schema\|design\|output] [--strict] [--output F]` | no | no | Validate a file or generated project; exit 1 when invalid |
| `dataforge chat [--workspace DIR]` | yes | no | Interactive REPL with `/schema`, `/analyze`, `/design`, `/generate`, `/validate`, `/save`, `/load` |
| `dataforge init NAME [--type dbt]` | no | no | Create a git initialised workspace under `DATAFORGE_WORKSPACE_DIR` |
| `dataforge list` | no | no | List workspaces |
| `dataforge status` | no | no | Show configuration; reports whether the API key is set |
| `dataforge version` | no | no | Print the version |

Full `--help` output for every command is in
[skills/dataforge/references/cli-reference.md](skills/dataforge/references/cli-reference.md).

## Use with Claude Code

DataForge ships a Claude Code skill (`skills/dataforge/SKILL.md`) and plugin manifests.

### 1. Clone and symlink (fastest, no marketplace needed)

```bash
git clone https://github.com/prajwalgajakesari/dataforge ~/repos/dataforge
(cd ~/repos/dataforge && uv sync)
ln -s ~/repos/dataforge/skills/dataforge ~/.claude/skills/dataforge
```

### 2. As a Claude Code plugin

```text
/plugin marketplace add prajwalgajakesari/dataforge
/plugin install dataforge
```

With the skill loaded, ask Claude things like "profile the `public` schema of my Postgres
database and tell me what is not in 3NF", "design a star schema for these tables", or
"generate a dbt project from this design and validate it". The skill tells Claude the exact
commands, how to read the outputs, and its guardrails: never print secrets, confirm before
anything writes to a database, and keep generated code in a git tracked directory.

## Project layout

```text
dataforge/
  interfaces/cli/        Typer CLI (main.py) and chat REPL (chat.py)
  core/
    analysis/            profiler, fd_detector, key_finder, type_inference, pattern_detector
    normalization/       violations (1NF to BCNF), normalizers, decomposer
    generators/          dbt_generator, generator_3nf, generator_data_vault
    validators/          schema, design, output, data validators
    prompts/             design prompts for Claude
    graph/               LangGraph workflow and nodes
    agents/              agent wrapper around the workflow
    mcp/                 registry and client scaffolding; servers/postgres_mcp.py (asyncpg)
    models/              Pydantic models: schema, analysis, design
    utils/               settings, Anthropic client, logging
    workspace/           workspace directories with git init
  api/                   FastAPI server, routes, in memory session store
  web/                   React + Vite prototype (not wired to the API yet)
  skills/dataforge/      Claude Code skill and CLI reference
  .claude-plugin/        plugin.json and marketplace.json
  examples/              sample_schema.json, sample_star_design.json, workflow script
  scripts/               offline demo of the pipeline
  docs/                  getting started guide and design documents
  tests/                 unit, integration and e2e suites
```

## Development

```bash
uv sync --all-extras
uv run pytest                       # 24 passed, 1 skipped (needs a database and API key)
uv run ruff check core interfaces api
uv run black --check core interfaces api
uv run mypy core interfaces api
uv run uvicorn api.server:app --reload    # http://localhost:8000/docs
cd web && npm install && npm run dev      # http://localhost:5173
```

The ruff and mypy configuration in `pyproject.toml` is stricter than the current code; expect
pre-existing findings.

## Status

Alpha. The pieces below are separated by what has been exercised.

### Works today

- `normalize`, `generate --format dbt|sql`, `validate` (schema, design, output), `init`,
  `list`, `status`, `version`, all run from files with no external services.
- `analyze` against PostgreSQL via asyncpg, including FD and candidate key detection.
- `design` and `chat` with an Anthropic key. Default model id is
  `claude-3-5-sonnet-20241022`; set `DEFAULT_MODEL` or `--model` if that id is retired for
  your account.
- dbt generation for star schema designs; the sample output passes `dbt parse`.
- FastAPI server with health, MCP listing and session routes for discover, profile, design and
  generate. Sessions are in memory. Discovery needs a PostgreSQL server enabled in
  `~/.dataforge/mcp-servers.yml`.

### Planned or partial

- MCP registry and client are scaffolding with `TODO`s; PostgreSQL is the only connector.
  MySQL, Snowflake and BigQuery drivers are dependencies only.
- dbt generation for 3NF and Data Vault from the CLI (today: DDL via `--format sql`; the
  generator classes exist and are used by the LangGraph workflow).
- `normalize` reports violations and steps but does not rewrite tables yet.
- `generate --format sqlalchemy`, `init --template`, and non-Postgres URLs in `analyze` are
  accepted by the parser but not implemented.
- Web UI wiring to the API.
- Airflow and Terraform generation: no code exists yet, despite the `init --type` help text.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Issues and pull requests are welcome at
https://github.com/prajwalgajakesari/dataforge/issues.

## License

MIT. See [LICENSE](LICENSE).
