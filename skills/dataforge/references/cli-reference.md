# DataForge CLI reference

Generated from the real `--help` output of `uv run dataforge` (DataForge 0.1.0).
Run any command with `--help` to see the live version.

| Command | Needs `ANTHROPIC_API_KEY` | Needs a database | Purpose |
|---|---|---|---|
| `version` | no | no | Print the version |
| `status` | no | no | Show configuration and whether the API key is set |
| `init` | no | no | Create a git-initialised workspace directory |
| `list` | no | no | List workspaces |
| `analyze` | no | yes (PostgreSQL) | Profile tables, detect functional dependencies and candidate keys |
| `normalize` | no | no | Detect 1NF/2NF/3NF/BCNF violations in a schema or analysis file |
| `design` | yes | no | Ask Claude for a star schema, 3NF or Data Vault design as JSON |
| `generate` | no | no | Write a dbt project or SQL DDL from a design file |
| `validate` | no | no | Validate a schema file, a design file, or a generated project |
| `chat` | yes | no | Interactive REPL over the same steps |

## `dataforge --help`

```text

 Usage: dataforge [OPTIONS] COMMAND [ARGS]...

 AI-powered data engineering platform

╭─ Options ────────────────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                          │
╰──────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────────────╮
│ version     Show DataForge version.                                                  │
│ init        Initialize a new DataForge workspace.                                    │
│ list        List all DataForge workspaces.                                           │
│ chat        Start an interactive chat session with DataForge.                        │
│ status      Show status of DataForge and connected services.                         │
│ analyze     Analyze database schema and data quality.                                │
│ normalize   Normalize schema to target normal form.                                  │
│ design      Generate data model design from requirements.                            │
│ generate    Generate code from data model design.                                    │
│ validate    Validate schema, design, or generated output.                            │
╰──────────────────────────────────────────────────────────────────────────────────────╯

```

## `dataforge version --help`

```text

 Usage: dataforge version [OPTIONS]

 Show DataForge version.

╭─ Options ────────────────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                          │
╰──────────────────────────────────────────────────────────────────────────────────────╯

```

## `dataforge init --help`

```text

 Usage: dataforge init [OPTIONS] NAME

 Initialize a new DataForge workspace.

╭─ Arguments ──────────────────────────────────────────────────────────────────────────╮
│ *    name      TEXT  Name of the workspace [required]                                │
╰──────────────────────────────────────────────────────────────────────────────────────╯
╭─ Options ────────────────────────────────────────────────────────────────────────────╮
│ --type      -t      TEXT  Project type (dbt, airflow, terraform, multi)              │
│                           [default: dbt]                                             │
│ --template          TEXT  Template to use                                            │
│ --help                    Show this message and exit.                                │
╰──────────────────────────────────────────────────────────────────────────────────────╯

```

## `dataforge list --help`

```text

 Usage: dataforge list [OPTIONS]

 List all DataForge workspaces.

╭─ Options ────────────────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                          │
╰──────────────────────────────────────────────────────────────────────────────────────╯

```

## `dataforge chat --help`

```text

 Usage: dataforge chat [OPTIONS]

 Start an interactive chat session with DataForge.

 The chat interface provides a conversational way to:
 - Explore and analyze database schemas
 - Design data models (Star Schema, 3NF, Data Vault)
 - Generate DDL, dbt models, and documentation

 Use /help within the chat for available commands.

╭─ Options ────────────────────────────────────────────────────────────────────────────╮
│ --workspace  -w      TEXT  Path to workspace directory (uses current directory if    │
│                            not specified)                                            │
│ --help                     Show this message and exit.                               │
╰──────────────────────────────────────────────────────────────────────────────────────╯

```

## `dataforge status --help`

```text

 Usage: dataforge status [OPTIONS]

 Show status of DataForge and connected services.

╭─ Options ────────────────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                          │
╰──────────────────────────────────────────────────────────────────────────────────────╯

```

## `dataforge analyze --help`

```text

 Usage: dataforge analyze [OPTIONS] CONNECTION

 Analyze database schema and data quality.

 Performs comprehensive analysis including:
 - Schema discovery (tables, columns, constraints)
 - Data profiling (statistics, patterns, quality scores)
 - Functional dependency detection
 - Candidate key discovery

 Examples:
     dataforge analyze postgresql://user:pass@localhost/db
     dataforge analyze postgresql://localhost/db --schema public --table orders
 customers
     dataforge analyze my-mcp-server --output table

╭─ Arguments ──────────────────────────────────────────────────────────────────────────╮
│ *    connection      TEXT  Database connection string or MCP server name [required]  │
╰──────────────────────────────────────────────────────────────────────────────────────╯
╭─ Options ────────────────────────────────────────────────────────────────────────────╮
│ --schema       -s      TEXT     Schema to analyze                                    │
│ --table        -t      TEXT     Specific tables to analyze                           │
│ --output       -o      TEXT     Output format (json, yaml, table) [default: json]    │
│ --output-file  -f      TEXT     Output file path                                     │
│ --sample-size          INTEGER  Sample size for profiling [default: 10000]           │
│ --help                          Show this message and exit.                          │
╰──────────────────────────────────────────────────────────────────────────────────────╯

```

## `dataforge normalize --help`

```text

 Usage: dataforge normalize [OPTIONS] INPUT_FILE

 Normalize schema to target normal form.

 Analyzes the input schema for normalization violations and
 applies decomposition to achieve the target normal form.

 Examples:
     dataforge normalize schema.json --target 3NF
     dataforge normalize analysis.yaml --target BCNF --output normalized.json

╭─ Arguments ──────────────────────────────────────────────────────────────────────────╮
│ *    input_file      TEXT  Path to schema/analysis file [required]                   │
╰──────────────────────────────────────────────────────────────────────────────────────╯
╭─ Options ────────────────────────────────────────────────────────────────────────────╮
│ --target   -t      TEXT  Target normal form (1NF, 2NF, 3NF, BCNF) [default: 3NF]     │
│ --output   -o      TEXT  Output file path                                            │
│ --verbose  -v            Show detailed violation info                                │
│ --help                   Show this message and exit.                                 │
╰──────────────────────────────────────────────────────────────────────────────────────╯

```

## `dataforge design --help`

```text

 Usage: dataforge design [OPTIONS] REQUIREMENTS

 Generate data model design from requirements.

 Uses LLM to generate a data model design based on business
 requirements and optionally an input schema analysis.

 Examples:
     dataforge design "Build a star schema for e-commerce analytics"
     dataforge design requirements.txt --strategy DATA_VAULT --input analysis.json
     dataforge design "Customer 360 view" --strategy NORMALIZED_3NF --output
 design.json

╭─ Arguments ──────────────────────────────────────────────────────────────────────────╮
│ *    requirements      TEXT  Business requirements or path to requirements file      │
│                              [required]                                              │
╰──────────────────────────────────────────────────────────────────────────────────────╯
╭─ Options ────────────────────────────────────────────────────────────────────────────╮
│ --strategy  -s      TEXT  Modeling strategy (STAR_SCHEMA, NORMALIZED_3NF,            │
│                           DATA_VAULT)                                                │
│                           [default: STAR_SCHEMA]                                     │
│ --input     -i      TEXT  Input schema file                                          │
│ --output    -o      TEXT  Output design file                                         │
│ --model     -m      TEXT  LLM model to use                                           │
│ --help                    Show this message and exit.                                │
╰──────────────────────────────────────────────────────────────────────────────────────╯

```

## `dataforge generate --help`

```text

 Usage: dataforge generate [OPTIONS] DESIGN_FILE

 Generate code from data model design.

 Generates SQL DDL, dbt models, or SQLAlchemy models from
 a data model design file.

 Examples:
     dataforge generate design.json --format dbt --output ./dbt_project
     dataforge generate design.yaml --format sql --output ./sql

╭─ Arguments ──────────────────────────────────────────────────────────────────────────╮
│ *    design_file      TEXT  Path to design file [required]                           │
╰──────────────────────────────────────────────────────────────────────────────────────╯
╭─ Options ────────────────────────────────────────────────────────────────────────────╮
│ --output     -o      TEXT  Output directory [default: ./output]                      │
│ --format     -f      TEXT  Output format (sql, dbt, sqlalchemy) [default: dbt]       │
│ --overwrite                Overwrite existing files                                  │
│ --help                     Show this message and exit.                               │
╰──────────────────────────────────────────────────────────────────────────────────────╯

```

## `dataforge validate --help`

```text

 Usage: dataforge validate [OPTIONS] PATH

 Validate schema, design, or generated output.

 Performs validation checks appropriate to the content type:
 - schema: Validates table structure, keys, data types
 - design: Validates model design completeness and best practices
 - output: Validates generated code syntax and conventions

 Examples:
     dataforge validate schema.json --type schema
     dataforge validate design.yaml --type design --strict
     dataforge validate ./dbt_project --type output

╭─ Arguments ──────────────────────────────────────────────────────────────────────────╮
│ *    path      TEXT  Path to validate (schema, design, or generated output)          │
│                      [required]                                                      │
╰──────────────────────────────────────────────────────────────────────────────────────╯
╭─ Options ────────────────────────────────────────────────────────────────────────────╮
│ --type    -t      TEXT  Validation type (schema, design, output)                     │
│ --strict                Fail on warnings                                             │
│ --output  -o      TEXT  Output report file                                           │
│ --help                  Show this message and exit.                                  │
╰──────────────────────────────────────────────────────────────────────────────────────╯

```

