# Examples

Files in this directory let you try DataForge without a database or an API key.

| File | What it is | Used by |
|---|---|---|
| `sample_schema.json` | Two tables (`order_items`, `customers`) with functional dependencies and candidate keys, in the shape `dataforge analyze` writes. `order_items` deliberately violates 1NF, 2NF and 3NF. | `dataforge normalize`, `dataforge validate --type schema`, `dataforge design --input` |
| `sample_star_design.json` | A small star schema (three staging models, two dimensions, one fact) in the shape `dataforge design --strategy STAR_SCHEMA` writes. | `dataforge generate`, `dataforge validate --type design` |
| `modeling_workflow_example.py` | Runs the full LangGraph workflow: connect to PostgreSQL, discover, profile, design with Claude, write a dbt project into a workspace. Needs `ANTHROPIC_API_KEY` and the `POSTGRES_*` variables. | `uv run python examples/modeling_workflow_example.py` |

## Offline walkthrough

Run from the repository root.

```bash
# Check the sample schema for normal form violations
uv run dataforge normalize examples/sample_schema.json --target 3NF --verbose

# Validate the sample design, then turn it into a dbt project
uv run dataforge validate examples/sample_star_design.json --type design
uv run dataforge generate examples/sample_star_design.json --format dbt --output ./out/sales_dbt
uv run dataforge validate ./out/sales_dbt --type output

# Or emit plain CREATE TABLE statements
uv run dataforge generate examples/sample_star_design.json --format sql --output ./out/sales_sql
```

The generated project parses with dbt. From inside the output directory:

```bash
uvx --from dbt-postgres dbt deps --profiles-dir .dbt
uvx --from dbt-postgres dbt parse --profiles-dir .dbt
```

`scripts/demo_workflow.py` is a scripted, offline demonstration of the same pipeline using
the Python API directly with a mocked schema: `uv run python scripts/demo_workflow.py`.

## With a database and Claude

```bash
uv run dataforge analyze postgresql://USER:PASSWORD@HOST:5432/DB --schema public --output-file analysis.json
uv run dataforge design "Sales mart with customer and product dimensions" \
  --strategy STAR_SCHEMA --input analysis.json --output design.json
uv run dataforge generate design.json --format dbt --output ./sales_dbt
```

See `../docs/getting-started.md` for configuration and troubleshooting.
