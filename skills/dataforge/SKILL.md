---
name: dataforge
description: Drive the DataForge CLI to profile a PostgreSQL schema, detect functional dependencies and normal form violations (1NF to BCNF), design a star schema, 3NF or Data Vault model with Claude, and generate a dbt project or SQL DDL. Use when the user wants to profile a database schema, design a dimensional or star schema, normalize a schema to 3NF, build a Data Vault, or generate a dbt project from a schema file or a database connection.
---

# DataForge

DataForge is a Python CLI (`dataforge`, run with `uv run dataforge`) for data modeling.
It reads a PostgreSQL schema or a schema file, reports normal form violations, asks Claude for
a model design, and writes a dbt project or `CREATE TABLE` DDL that you can validate.
Only the `design` and `chat` commands call Claude. Only `analyze` needs a database.

## Prerequisites

- `uv` and Python 3.11+ on the machine.
- A checkout of https://github.com/prajwalgajakesari/dataforge with `uv sync` run once.
- Environment variable names (never print their values):
  - `ANTHROPIC_API_KEY` for `design` and `chat`.
  - `DEFAULT_MODEL` (optional) to override the default model id; `--model` works too.
  - `DATAFORGE_WORKSPACE_DIR` (optional) for where `init` creates workspaces.
- A PostgreSQL connection URL only if the user wants to profile a live database.

Locate or prepare the CLI first. `DATAFORGE_HOME` below is the checkout path; shell state
does not persist between tool calls, so put the `export` (or the literal path) in every
command, or `cd` into the checkout and use plain `uv run dataforge`.

```bash
export DATAFORGE_HOME=/path/to/dataforge
# Clone once if it is not there yet
[ -d "$DATAFORGE_HOME" ] || git clone https://github.com/prajwalgajakesari/dataforge "$DATAFORGE_HOME"
(cd "$DATAFORGE_HOME" && uv sync)
uv run --project "$DATAFORGE_HOME" dataforge version   # prints: DataForge version 0.1.0
uv run --project "$DATAFORGE_HOME" dataforge status    # config summary; the key value is never shown
```

`uvx --from "$DATAFORGE_HOME" dataforge <command>` also works if you prefer an isolated tool
environment.

`references/cli-reference.md` holds the full `--help` output of every command.
`references/examples.md` shows the commands below with their real output.

## Workflow

Work in a directory the user controls and that is tracked by git. Put outputs under a
fresh subdirectory such as `./out/`.

1. Get a schema or analysis file.
   - From a live PostgreSQL database (read only queries against `information_schema` and
     `SELECT ... LIMIT` samples):
     ```bash
     uv run --project "$DATAFORGE_HOME" dataforge analyze "postgresql://USER:PASSWORD@HOST:5432/DB" --schema public --output table --output-file out/analysis.json
     ```
     Add `--table orders --table customers` to restrict tables and `--sample-size 1000` to
     profile faster. Only `postgresql://` URLs work; a server name fails with
     `MCP server connections not yet implemented`. The saved file masks the password.
   - Without a database, use a file with a top level `tables` list (columns with `name`,
     `data_type`, `is_primary_key`) and optional `functional_dependencies` and
     `candidate_keys`. `examples/sample_schema.json` in the repo is a working template.

2. Check normal forms.
   ```bash
   uv run --project "$DATAFORGE_HOME" dataforge normalize out/analysis.json --target 3NF --verbose --output out/normalized.json
   ```
   Prints the current normal form and counts of 1NF, 2NF, 3NF and BCNF violations, with a
   table per level when `--verbose` is set. `--target` accepts `1NF`, `2NF`, `3NF`, `BCNF`.
   The JSON output lists each violation and the normalization steps required. It does not
   yet rewrite the tables; use the report to inform the design.

3. Design the model with Claude (needs `ANTHROPIC_API_KEY`).
   ```bash
   uv run --project "$DATAFORGE_HOME" dataforge design "One sentence of business requirements" --strategy STAR_SCHEMA --input out/analysis.json --output out/design.json
   ```
   `--strategy` is `STAR_SCHEMA`, `NORMALIZED_3NF` or `DATA_VAULT`. The requirements
   argument may also be a path to a text file. The command prints a table of generated
   tables plus token usage and cost, and writes the design JSON. If the user already has a
   design file, skip this step.

4. Validate the design.
   ```bash
   uv run --project "$DATAFORGE_HOME" dataforge validate out/design.json --type design
   ```
   Exit code 0 and `Status: VALID` mean no errors. Star schema checks include at least one
   fact, dimensions with surrogate keys, and foreign keys that point at existing dimensions.

5. Generate code.
   ```bash
   uv run --project "$DATAFORGE_HOME" dataforge generate out/design.json --format dbt --output out/dbt_project      # star schema designs
   uv run --project "$DATAFORGE_HOME" dataforge generate out/design.json --format sql --output out/ddl              # any strategy, one CREATE TABLE per file
   ```
   The dbt output contains `dbt_project.yml`, `packages.yml`, `.dbt/profiles.yml`,
   `models/staging/` (sources, schema, `stg_*.sql`), `models/marts/` (schema, `dim_*.sql`,
   `fct_*.sql`), `models/docs.md` and a `README.md`. Use an empty output directory or pass
   `--overwrite`; otherwise the command asks for confirmation and aborts in a
   non-interactive shell. `--format sqlalchemy` is listed in the help but not implemented.

6. Validate the generated project.
   ```bash
   uv run --project "$DATAFORGE_HOME" dataforge validate out/dbt_project --type output
   ```
   Checks SQL syntax after stripping Jinja, `ref()` targets, and the YAML files. If the
   `dbt` binary is on the path it also runs `dbt compile`; otherwise it warns
   `dbt compile skipped`. For a stronger check without a database:
   ```bash
   (cd out/dbt_project && uvx --from dbt-postgres dbt deps --profiles-dir .dbt && uvx --from dbt-postgres dbt parse --profiles-dir .dbt)
   ```

7. Optional: keep the result in a DataForge workspace.
   ```bash
   uv run --project "$DATAFORGE_HOME" dataforge init sales-mart --type dbt     # creates <DATAFORGE_WORKSPACE_DIR>/sales_mart with git init
   uv run --project "$DATAFORGE_HOME" dataforge list
   ```

Report back to the user with the violation counts, the list of generated tables, the output
directory, and the validation status. Quote file paths, not file contents, unless asked.

## Guardrails

- Never print secrets. Do not `cat` `.env` files. Pass connection URLs as quoted arguments
  and do not echo them. Refer to variables by name only.
- DataForge only reads from databases. Before running anything that writes to a database
  (for example `dbt run` on the generated project), confirm with the user.
- Keep generated code inside a git tracked directory the user owns so changes can be reviewed
  with `git diff`. Never generate into a directory that already has unrelated content.
- Treat the design step as a draft. Show the user the generated tables before generating
  code and let them adjust the design JSON.
- `design` and `chat` cost API tokens. Say so before running them repeatedly.

## Troubleshooting

| Error | Meaning and fix |
|---|---|
| `Anthropic API key is required` | `ANTHROPIC_API_KEY` is not set in the environment or `.env` |
| `Error code: 401 ... invalid x-api-key` | The key is wrong or revoked; the client retries three times then fails |
| `Error connecting to database: Multiple exceptions: [Errno 61] Connect call failed` | Wrong host or port, or the database is down |
| `MCP server connections not yet implemented` | `analyze` received a server name; pass a `postgresql://` URL |
| `Output directory is not empty ... Continue anyway?` | Use a new directory or `--overwrite` |
| `dbt compile skipped: dbt command not found` | Warning only; install dbt or use the `uvx` command above |
| `Unknown model for pricing` | Cost reporting only; set `DEFAULT_MODEL` or `--model` to a model id you use |
| `No tables found in input file` | The file lacks a top level `tables` list |
| `Star schema must have at least one fact table` | The design has no `facts` entry, or the file is not a design file |
