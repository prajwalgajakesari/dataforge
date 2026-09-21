# DataForge examples with real output

Every command below was run from an empty directory containing copies of
`examples/sample_schema.json` and `examples/sample_star_design.json`, with
`DATAFORGE_HOME` pointing at the checkout and `DATAFORGE_WORKSPACE_DIR` pointing at a
scratch folder. Output is trimmed; long absolute paths are shortened.

## version and status

```console
$ uv run --project "$DATAFORGE_HOME" dataforge version
DataForge version 0.1.0
AI-powered data engineering platform

$ uv run --project "$DATAFORGE_HOME" dataforge status
DataForge Status
  Environment    development
  Log Level      INFO
  Workspace Dir  <DATAFORGE_WORKSPACE_DIR>
  Default Model  claude-opus-5
  API Key        Not set
MCP servers status coming soon...
```

`status` only reports `Set` or `Not set` for the key.

## normalize

```console
$ uv run --project "$DATAFORGE_HOME" dataforge normalize sample_schema.json --target 3NF --verbose --output out/normalized.json
Normalizing to 3NF
Current Normal Form: UNNORMALIZED
Target Normal Form: 3NF
Violations Found:
  - 1NF: 1
  - 2NF: 2
  - 3NF: 1
  - BCNF: 3

1NF Violations
  order_items  ARRAY_COLUMN  Column 'tags' has array type 'text[]', violating 1NF atomicity
2NF Violations
  order_items  Violation2NF  {product_id} -> {product_name}
  order_items  Violation2NF  {order_id} -> {customer_id}
3NF Violations
  order_items  Violation3NF  {customer_id} -> {customer_email}
BCNF Violations
  order_items  ViolationBCNF {product_id} -> {product_name}
  order_items  ViolationBCNF {order_id} -> {customer_id}
  order_items  ViolationBCNF {customer_id} -> {customer_email}
Output saved to: out/normalized.json
[exit 0]
```

`out/normalized.json` has keys `current_normal_form`, `target_normal_form`, `violations`
(`1nf`, `2nf`, `3nf`, `bcnf` lists with `table`, `type`, `description`), `original_tables`,
`normalization_steps` and `normalized_tables`.

## validate a schema file and a design file

```console
$ uv run --project "$DATAFORGE_HOME" dataforge validate sample_schema.json --type schema
Validation type: schema
Status: VALID   Errors: 0   Warnings: 0
[exit 0]

$ uv run --project "$DATAFORGE_HOME" dataforge validate sample_star_design.json --type design
Validation type: design
Status: VALID   Errors: 0   Warnings: 0
Info:
  i Strategy: star_schema, tables: 6, relationships: 2
  i [INFO]  Staging table has no relationships (expected)
[exit 0]
```

## generate a dbt project

```console
$ uv run --project "$DATAFORGE_HOME" dataforge generate sample_star_design.json --format dbt --output out/dbt_project
Generating dbt code
Code generation complete!
Format: dbt
Output directory: out/dbt_project
Files generated: 19
[exit 0]

$ find out/dbt_project -type f | sort
out/dbt_project/.dbt/profiles.yml
out/dbt_project/.gitignore
out/dbt_project/dbt_project.yml
out/dbt_project/models/docs.md
out/dbt_project/models/marts/dim_customer.sql
out/dbt_project/models/marts/dim_product.sql
out/dbt_project/models/marts/fct_orders.sql
out/dbt_project/models/marts/schema.yml
out/dbt_project/models/staging/schema.yml
out/dbt_project/models/staging/sources.yml
out/dbt_project/models/staging/stg_customers.sql
out/dbt_project/models/staging/stg_orders.sql
out/dbt_project/models/staging/stg_products.sql
out/dbt_project/packages.yml
out/dbt_project/README.md
```

"Files generated: 19" counts directories as well; there are 15 files.

## validate the generated project

```console
$ uv run --project "$DATAFORGE_HOME" dataforge validate out/dbt_project --type output
Validation type: output
Status: VALID   Errors: 0   Warnings: 1
Warnings:
  ! out/dbt_project: dbt compile skipped: dbt command not found - ensure dbt is installed
Info:
  i Files validated: 12
  i Valid files: 12
[exit 0]
```

With dbt available (`uvx --from dbt-postgres dbt deps --profiles-dir .dbt` then
`uvx --from dbt-postgres dbt parse --profiles-dir .dbt` inside `out/dbt_project`), the same
project parsed successfully with dbt-core 1.11 and the postgres adapter. dbt printed only
deprecation warnings about the `relationships` test argument layout in `schema.yml`.

## generate SQL DDL

```console
$ uv run --project "$DATAFORGE_HOME" dataforge generate sample_star_design.json --format sql --output out/ddl
Format: sql
Output directory: out/ddl
Files generated: 3
[exit 0]

$ ls out/ddl
dim_customer.sql  dim_product.sql  fact_orders.sql

$ cat out/ddl/fact_orders.sql
CREATE TABLE fact_orders (
    fact_order_key bigint PRIMARY KEY,
    dim_customer_key bigint,
    dim_product_key bigint,
    order_id integer,
    ordered_at timestamp,
    quantity integer,
    order_amount numeric(18,2)
);
```

## workspaces

```console
$ uv run --project "$DATAFORGE_HOME" dataforge init sales-mart --type dbt
Creating workspace: sales-mart
Workspace created successfully!
Path: <DATAFORGE_WORKSPACE_DIR>/sales_mart
Type: dbt
[exit 0]

$ uv run --project "$DATAFORGE_HOME" dataforge list
  sales-mart  dbt  <DATAFORGE_WORKSPACE_DIR>/sales_mart  2026-09-21 22:05
[exit 0]
```

## error paths you may see

```console
$ ANTHROPIC_API_KEY= uv run --project "$DATAFORGE_HOME" dataforge design "Sales mart" --strategy STAR_SCHEMA --input sample_schema.json
Generating STAR_SCHEMA Design
Error generating design: Anthropic API key is required
Design generation failed: 1
[exit 1]
```

With a key that the API rejects, the client logs
`LLM call failed (attempt 1/3): Error code: 401 ... 'invalid x-api-key'` three times and then
`Error generating design: Error code: 401 ...`.

```console
$ uv run --project "$DATAFORGE_HOME" dataforge analyze postgresql://localhost:1/nodb --schema public
Error connecting to database: Multiple exceptions: [Errno 61] Connect call failed ('::1', 1, 0, 0),
[Errno 61] Connect call failed ('127.0.0.1', 1)
Analysis failed: 1
[exit 1]
```

```console
$ uv run --project "$DATAFORGE_HOME" dataforge generate sample_star_design.json --format dbt --output out/dbt_project </dev/null
Warning: Output directory is not empty: out/dbt_project
Use --overwrite to overwrite existing files.
Continue anyway? [y/N]: Aborted.
[exit 1]
```

Use a new output directory or pass `--overwrite` when running non-interactively.
