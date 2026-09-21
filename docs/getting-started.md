# Getting started

This guide takes you from a clone to a generated dbt project. Every command here was run
while writing this document.

## Prerequisites

- Python 3.11 or newer
- [uv](https://github.com/astral-sh/uv)
- Git
- Optional: a PostgreSQL database to profile (`analyze`)
- Optional: an Anthropic API key for the design step (`design`, `chat`)
- Optional: Node.js 18+ for the web prototype

## Install

```bash
git clone https://github.com/prajwalgajakesari/dataforge.git
cd dataforge
uv sync                 # runtime only
uv sync --all-extras    # plus dev, test and docs extras
uv run dataforge version
```

## Configure

Settings come from environment variables or a `.env` file in the working directory
(see `core/utils/config.py`). Copy the template and fill in what you need:

```bash
cp .env.example .env
```

| Variable | Needed for | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | `design`, `chat`, API design route | Required for anything that calls Claude |
| `DEFAULT_MODEL` | same | Defaults to `claude-3-5-sonnet-20241022`. Set a current model id if that one is retired for your account, or pass `--model` |
| `DATAFORGE_WORKSPACE_DIR` | `init`, `list` | Defaults to `~/dataforge-workspaces` |
| `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DATABASE` | API discovery, MCP config | The CLI `analyze` command takes a connection URL instead |
| `API_HOST`, `API_PORT`, `CORS_ORIGINS` | API server | Defaults: `0.0.0.0`, `8000`, localhost origins |

Check what is loaded without printing any values:

```bash
uv run dataforge status
```

## Walkthrough without a database or API key

```bash
# 1. Find normal form violations in a schema or analysis file
uv run dataforge normalize examples/sample_schema.json --target 3NF --verbose --output ./out/normalized.json

# 2. Validate a design file
uv run dataforge validate examples/sample_star_design.json --type design

# 3. Generate a dbt project from the design
uv run dataforge generate examples/sample_star_design.json --format dbt --output ./out/sales_dbt

# 4. Validate the generated project
uv run dataforge validate ./out/sales_dbt --type output
```

Step 1 reports one 1NF, two 2NF, one 3NF and three BCNF violations for the sample. Step 3
writes 15 files: `dbt_project.yml`, `packages.yml`, `.dbt/profiles.yml`, staging and marts
models, `sources.yml`, two `schema.yml` files, `models/docs.md`, `README.md` and a
`.gitignore`. Step 4 reports `VALID` and warns that `dbt compile` was skipped if dbt is not
installed. To run dbt itself against the output:

```bash
cd out/sales_dbt
uvx --from dbt-postgres dbt deps --profiles-dir .dbt
uvx --from dbt-postgres dbt parse --profiles-dir .dbt
```

## Walkthrough with PostgreSQL and Claude

```bash
# Profile tables, detect functional dependencies and candidate keys
uv run dataforge analyze postgresql://USER:PASSWORD@HOST:5432/DB \
  --schema public --output table --output-file analysis.json

# Check normal forms on the real analysis
uv run dataforge normalize analysis.json --target 3NF --verbose

# Ask Claude for a design (STAR_SCHEMA, NORMALIZED_3NF or DATA_VAULT)
uv run dataforge design "Sales mart with customer and product dimensions" \
  --strategy STAR_SCHEMA --input analysis.json --output design.json

# Generate and validate
uv run dataforge generate design.json --format dbt --output ./sales_dbt
uv run dataforge validate ./sales_dbt --type output
```

Only `postgresql://` URLs work in `analyze` today. The password in the URL is masked in the
saved analysis file. Star schema designs become full dbt projects. 3NF and Data Vault designs
can be emitted as `CREATE TABLE` files with `--format sql`.

## Interactive chat

```bash
uv run dataforge chat
```

Slash commands inside the session: `/schema`, `/analyze`, `/design`, `/generate`,
`/validate`, `/save`, `/load`, `/context`, `/clear`, `/help`, `/exit`. The chat needs
`ANTHROPIC_API_KEY`.

## Workspaces

```bash
uv run dataforge init sales-mart --type dbt
uv run dataforge list
```

`init` creates `<DATAFORGE_WORKSPACE_DIR>/sales_mart`, runs `git init` and writes a
`.gitignore`. `--type` is recorded as metadata only, and `--template` is not implemented yet.

## API server

```bash
uv run uvicorn api.server:app --reload
# Swagger UI: http://localhost:8000/docs
curl http://localhost:8000/api/v1/health
```

Routes live under `/api/v1`: health and capabilities, MCP server listing and test, and a
session based modeling flow (`POST /modeling/sessions/`, then `discover`, `profile`,
`design`, `generate`, `files`). Sessions are held in memory. Discovery and profiling need a
PostgreSQL server enabled in `~/.dataforge/mcp-servers.yml`; the file is created with
disabled placeholders the first time the registry starts. Design needs `ANTHROPIC_API_KEY`.

## Web prototype

```bash
cd web && npm install && npm run dev   # http://localhost:5173
```

The UI is a prototype and is not connected to the API yet.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `Anthropic API key is required` | Set `ANTHROPIC_API_KEY` in the environment or `.env` |
| `Error code: 401 ... invalid x-api-key` | The key is wrong or revoked. The client retries three times, then fails |
| `Error connecting to database: Multiple exceptions: [Errno 61] Connect call failed` | Nothing is listening at that host and port |
| `MCP server connections not yet implemented` | `analyze` was given a server name. Pass a `postgresql://` URL |
| `Output directory is not empty` prompt | Use a new directory or pass `--overwrite`. In non-interactive shells the prompt aborts |
| `dbt compile skipped: dbt command not found` warning | Install dbt (`uvx --from dbt-postgres dbt --version`) to enable compile checks |
| `Unknown model for pricing` | The model id is not in the small pricing table. Output is fine; reported cost will be zero |
| `No tables found in input file` | `normalize` needs a top level `tables` list, as written by `analyze` |
