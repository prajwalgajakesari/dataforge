"""
dbt Project Generator for DataForge.

Generates complete dbt projects including:
- Project configuration (dbt_project.yml)
- Source definitions (models/staging/sources.yml)
- Staging models (models/staging/*.sql)
- Mart models - facts and dimensions (models/marts/*.sql)
- Schema definitions with tests (models/*/schema.yml)
- Documentation (models/docs.md)
- Profiles configuration
"""

import warnings
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from jinja2 import Template
from pydantic import BaseModel, Field

from core.models.schema import ForeignKeyRelationship
from core.utils.logger import get_logger

logger = get_logger(__name__)


# Pydantic warns because these models have a field named "schema" (dbt terminology).
# The field does not interfere with anything, so silence the warning.
warnings.filterwarnings("ignore", message='Field name "schema"', category=UserWarning)

class ColumnDefinition(BaseModel):
    """Definition of a database column."""

    name: str
    data_type: str
    description: Optional[str] = None
    is_nullable: bool = True
    is_primary_key: bool = False
    is_foreign_key: bool = False
    foreign_key_table: Optional[str] = None
    foreign_key_column: Optional[str] = None


class TableDefinition(BaseModel):
    """Definition of a database table."""

    name: str
    schema: str
    columns: List[ColumnDefinition]
    description: Optional[str] = None
    row_count: Optional[int] = None


class SourceDefinition(BaseModel):
    """Definition of a dbt source."""

    name: str
    database: Optional[str] = None
    schema: str
    tables: List[TableDefinition]
    description: Optional[str] = None


class StagingModelDefinition(BaseModel):
    """Definition of a staging model."""

    name: str
    source_table: TableDefinition
    columns: List[ColumnDefinition]
    description: str


class DimensionModelDefinition(BaseModel):
    """Definition of a dimension model."""

    name: str
    source_models: List[str]
    columns: List[ColumnDefinition]
    description: str
    slowly_changing_type: int = 1  # SCD Type 1, 2, or 3


class FactModelDefinition(BaseModel):
    """Definition of a fact model."""

    name: str
    source_models: List[str]
    grain: str
    columns: List[ColumnDefinition]
    measures: List[str]
    dimensions: List[str]
    description: str


class ModelDesign(BaseModel):
    """Complete data model design specification."""

    project_name: str
    sources: List[SourceDefinition]
    staging_models: List[StagingModelDefinition]
    dimension_models: List[DimensionModelDefinition]
    fact_models: List[FactModelDefinition]
    target_database: str = "analytics"
    target_schema: str = "analytics"


class DBTGenerator:
    """
    Generator for complete dbt projects.

    This class takes a model design specification and generates all necessary
    dbt project files including SQL models, YAML configurations, and documentation.
    """

    def __init__(self, project_name: str, target_dir: Optional[Path] = None):
        """
        Initialize the dbt generator.

        Args:
            project_name: Name of the dbt project
            target_dir: Target directory for generation (creates temp dir if not provided)
        """
        self.project_name = project_name
        self.target_dir = target_dir or Path(f"./{project_name}")
        self.generated_files: Dict[str, str] = {}

    def generate_project(self, design: ModelDesign) -> Dict[str, str]:
        """
        Generate complete dbt project from design specification.

        Args:
            design: Model design specification

        Returns:
            Dictionary mapping file paths to file contents
        """
        logger.info(f"Generating dbt project: {self.project_name}")

        # Generate project files
        self.generated_files = {}

        # 1. dbt_project.yml
        self.generated_files["dbt_project.yml"] = self._generate_project_yml(design)

        # 2. profiles.yml (for reference, not part of project)
        self.generated_files[".dbt/profiles.yml"] = self._generate_profiles_yml(design)

        # 3. packages.yml
        self.generated_files["packages.yml"] = self._generate_packages_yml()

        # 4. Sources
        self.generated_files["models/staging/sources.yml"] = self._generate_sources_yml(design)

        # 5. Staging models
        for staging_model in design.staging_models:
            model_path = f"models/staging/stg_{staging_model.name}.sql"
            self.generated_files[model_path] = self._generate_staging_model(staging_model)

        # 6. Staging schema.yml
        self.generated_files["models/staging/schema.yml"] = self._generate_staging_schema_yml(
            design
        )

        # 7. Dimension models
        for dim_model in design.dimension_models:
            model_path = f"models/marts/dim_{dim_model.name}.sql"
            self.generated_files[model_path] = self._generate_dimension_model(dim_model)

        # 8. Fact models
        for fact_model in design.fact_models:
            model_path = f"models/marts/fct_{fact_model.name}.sql"
            self.generated_files[model_path] = self._generate_fact_model(fact_model)

        # 9. Marts schema.yml
        self.generated_files["models/marts/schema.yml"] = self._generate_marts_schema_yml(design)

        # 10. Documentation
        self.generated_files["models/docs.md"] = self._generate_documentation(design)

        # 11. .gitignore
        self.generated_files[".gitignore"] = self._generate_gitignore()

        # 12. README.md
        self.generated_files["README.md"] = self._generate_readme(design)

        logger.info(f"Generated {len(self.generated_files)} files for dbt project")
        return self.generated_files

    def _generate_project_yml(self, design: ModelDesign) -> str:
        """Generate dbt_project.yml."""
        config = {
            "name": self.project_name,
            "version": "1.0.0",
            "config-version": 2,
            "profile": self.project_name,
            "model-paths": ["models"],
            "analysis-paths": ["analyses"],
            "test-paths": ["tests"],
            "seed-paths": ["seeds"],
            "macro-paths": ["macros"],
            "snapshot-paths": ["snapshots"],
            "target-path": "target",
            "clean-targets": ["target", "dbt_packages"],
            "models": {
                self.project_name: {
                    "staging": {
                        "+materialized": "view",
                        "+schema": "staging",
                    },
                    "marts": {
                        "+materialized": "table",
                        "+schema": design.target_schema,
                    },
                }
            },
            "vars": {
                "target_database": design.target_database,
                "target_schema": design.target_schema,
            },
        }

        return yaml.dump(config, default_flow_style=False, sort_keys=False)

    def _generate_profiles_yml(self, design: ModelDesign) -> str:
        """Generate profiles.yml for local development."""
        profiles = {
            self.project_name: {
                "target": "dev",
                "outputs": {
                    "dev": {
                        "type": "postgres",
                        "host": "{{ env_var('DBT_HOST', 'localhost') }}",
                        "port": "{{ env_var('DBT_PORT', '5432') | as_number }}",
                        "user": "{{ env_var('DBT_USER', 'postgres') }}",
                        "password": "{{ env_var('DBT_PASSWORD', '') }}",
                        "dbname": "{{ env_var('DBT_DATABASE', 'analytics') }}",
                        "schema": design.target_schema,
                        "threads": 4,
                    },
                    "prod": {
                        "type": "postgres",
                        "host": "{{ env_var('DBT_HOST') }}",
                        "port": "{{ env_var('DBT_PORT', '5432') | as_number }}",
                        "user": "{{ env_var('DBT_USER') }}",
                        "password": "{{ env_var('DBT_PASSWORD') }}",
                        "dbname": "{{ env_var('DBT_DATABASE') }}",
                        "schema": design.target_schema,
                        "threads": 8,
                    },
                },
            }
        }

        return yaml.dump(profiles, default_flow_style=False, sort_keys=False)

    def _generate_packages_yml(self) -> str:
        """Generate packages.yml with common dbt packages."""
        packages = {
            "packages": [
                {"package": "dbt-labs/dbt_utils", "version": "1.1.1"},
                {"package": "calogica/dbt_expectations", "version": "0.10.0"},
            ]
        }

        return yaml.dump(packages, default_flow_style=False, sort_keys=False)

    def _generate_sources_yml(self, design: ModelDesign) -> str:
        """Generate sources.yml defining source tables."""
        sources_config = {"version": 2, "sources": []}

        for source in design.sources:
            source_config = {
                "name": source.name,
                "schema": source.schema,
                "description": source.description or f"Source: {source.name}",
                "tables": [],
            }

            if source.database:
                source_config["database"] = source.database

            for table in source.tables:
                table_config = {
                    "name": table.name,
                    "description": table.description or f"Table: {table.name}",
                    "columns": [
                        {
                            "name": col.name,
                            "description": col.description or "",
                            "tests": self._generate_column_tests(col),
                        }
                        for col in table.columns
                    ],
                }

                source_config["tables"].append(table_config)

            sources_config["sources"].append(source_config)

        return yaml.dump(sources_config, default_flow_style=False, sort_keys=False)

    def _generate_staging_model(self, model: StagingModelDefinition) -> str:
        """Generate SQL for a staging model."""
        template = Template(
            """{{ '{{' }} config(
    materialized='view',
    schema='staging'
) {{ '}}' }}

with source as (
    select * from {{ '{{' }} source('{{ source_name }}', '{{ table_name }}') {{ '}}' }}
),

renamed as (
    select
        -- Primary Key
{% for col in pk_columns %}
        {{ col.name }}{{ "," if (not loop.last) or other_columns else "" }}
{% endfor %}

        -- Attributes
{% for col in other_columns %}
        {{ col.name }}{{ "," if not loop.last else "" }}{% if col.description %}  -- {{ col.description }}{% endif %}
{% endfor %}

    from source
)

select * from renamed

-- Generated by DataForge on {{ timestamp }}
"""
        )

        pk_columns = [col for col in model.columns if col.is_primary_key]
        other_columns = [col for col in model.columns if not col.is_primary_key]

        return template.render(
            source_name=model.source_table.schema,
            table_name=model.source_table.name,
            pk_columns=pk_columns,
            other_columns=other_columns,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

    def _generate_dimension_model(
        self,
        model: DimensionModelDefinition,
        foreign_keys: Optional[List[ForeignKeyRelationship]] = None,
    ) -> str:
        """
        Generate SQL for a dimension model.

        Args:
            model: Dimension model definition.
            foreign_keys: Optional list of FK relationships for join generation.

        Returns:
            Generated SQL string.
        """
        # Generate join clauses from FK definitions
        join_clauses = ""
        if foreign_keys and len(model.source_models) > 1:
            base_model = model.source_models[0]
            base_alias = base_model.split("_")[1] if "_" in base_model else base_model
            for source_model in model.source_models[1:]:
                join_clause = self._generate_join_clause(
                    base_table=base_model,
                    join_table=source_model,
                    foreign_keys=foreign_keys,
                    join_type="left join",
                )
                if join_clause:
                    join_clauses += f"\n    {join_clause}"
                else:
                    # Fallback: generate commented placeholder if no FK found
                    join_alias = source_model.split("_")[1] if "_" in source_model else source_model
                    join_clauses += f"\n    -- left join {join_alias} on <add join condition>"

        template = Template(
            """{{ '{{' }} config(
    materialized='table',
    schema={{ target_schema }}
) {{ '}}' }}

{% for source_model in source_models %}
{{ 'with ' if loop.first else '' }}{{ source_model.split('_')[1] if '_' in source_model else source_model }} as (
    select * from {{ '{{' }} ref('{{ source_model }}') {{ '}}' }}
),
{% endfor %}

joined as (
    select
        -- Surrogate Key
        {{ '{{ dbt_utils.generate_surrogate_key([' }}
            {%- for col in pk_columns -%}
            '{{ col.name }}'{{ ', ' if not loop.last else '' }}
            {%- endfor -%}
        {{ ']) }}' }} as {{ model_name }}_key,

        -- Natural Key
{% for col in pk_columns %}
        {{ col.name }}{{ "," if (not loop.last) or other_columns else "" }}
{% endfor %}

        -- Attributes
{% for col in other_columns %}
        {{ col.name }}{{ "," if not loop.last else "" }}{% if col.description %}  -- {{ col.description }}{% endif %}
{% endfor %}

    from {{ source_models[0].split('_')[1] if '_' in source_models[0] else source_models[0] }}{{ join_clauses }}
)

select * from joined

-- Generated by DataForge on {{ timestamp }}
"""
        )

        pk_columns = [col for col in model.columns if col.is_primary_key]
        other_columns = [col for col in model.columns if not col.is_primary_key]

        return template.render(
            model_name=model.name,
            target_schema="var('target_schema')",
            source_models=model.source_models,
            pk_columns=pk_columns,
            other_columns=other_columns,
            join_clauses=join_clauses,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

    def _generate_fact_model(
        self,
        model: FactModelDefinition,
        foreign_keys: Optional[List[ForeignKeyRelationship]] = None,
    ) -> str:
        """
        Generate SQL for a fact model.

        Args:
            model: Fact model definition.
            foreign_keys: Optional list of FK relationships for join generation.

        Returns:
            Generated SQL string.
        """
        # Generate join clauses from FK definitions
        join_clauses = ""
        if foreign_keys and len(model.source_models) > 1:
            base_model = model.source_models[0]
            for source_model in model.source_models[1:]:
                join_clause = self._generate_join_clause(
                    base_table=base_model,
                    join_table=source_model,
                    foreign_keys=foreign_keys,
                    join_type="left join",
                )
                if join_clause:
                    join_clauses += f"\n    {join_clause}"
                else:
                    # Fallback: generate commented placeholder if no FK found
                    join_alias = source_model.split("_")[1] if "_" in source_model else source_model
                    join_clauses += f"\n    -- left join {join_alias} on <add join condition>"

        template = Template(
            """{{ '{{' }} config(
    materialized='table',
    schema={{ target_schema }}
) {{ '}}' }}

{% for source_model in source_models %}
{{ 'with ' if loop.first else '' }}{{ source_model.split('_')[1] if '_' in source_model else source_model }} as (
    select * from {{ '{{' }} ref('{{ source_model }}') {{ '}}' }}
),
{% endfor %}

fact as (
    select
        -- Surrogate Key
        {{ '{{ dbt_utils.generate_surrogate_key([' }}
            {%- for col in pk_columns -%}
            '{{ col.name }}'{{ ', ' if not loop.last else '' }}
            {%- endfor -%}
        {{ ']) }}' }} as {{ model_name }}_key,

        -- Foreign Keys (Dimensions)
{% for dim in dimensions %}
        {{ dim if dim.endswith('_key') else dim ~ '_key' }}{{ "," if (not loop.last) or measures else "" }}
{% endfor %}

        -- Measures
{% for measure in measures %}
        {{ measure }}{{ "," if not loop.last else "" }}
{% endfor %}

    from {{ source_models[0].split('_')[1] if '_' in source_models[0] else source_models[0] }}{{ join_clauses }}
)

select * from fact

-- Grain: {{ grain }}
-- Generated by DataForge on {{ timestamp }}
"""
        )

        pk_columns = [col for col in model.columns if col.is_primary_key]

        return template.render(
            model_name=model.name,
            target_schema="var('target_schema')",
            source_models=model.source_models,
            pk_columns=pk_columns,
            dimensions=model.dimensions,
            measures=model.measures,
            grain=model.grain,
            join_clauses=join_clauses,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

    def _generate_join_clause(
        self,
        base_table: str,
        join_table: str,
        foreign_keys: List[ForeignKeyRelationship],
        join_type: str = "left join",
    ) -> str:
        """
        Generate proper join clause from FK definitions.

        Args:
            base_table: The base/left table in the join (can be model name like 'stg_orders').
            join_table: The table to join (can be model name like 'stg_customers').
            foreign_keys: List of FK relationships to search for join conditions.
            join_type: Type of join (e.g., 'left join', 'inner join').

        Returns:
            Generated join clause string, or empty string if no matching FK found.
        """
        if not foreign_keys:
            return ""

        # Extract table names from model names (e.g., 'stg_orders' -> 'orders')
        base_name = base_table.split("_", 1)[1] if "_" in base_table else base_table
        join_name = join_table.split("_", 1)[1] if "_" in join_table else join_table

        # Get alias for the join table (used in SQL)
        join_alias = join_table.split("_")[1] if "_" in join_table else join_table
        base_alias = base_table.split("_")[1] if "_" in base_table else base_table

        # Search for matching FK relationship
        matching_fk: Optional[ForeignKeyRelationship] = None

        for fk in foreign_keys:
            # Check if FK goes from base_table to join_table
            if (
                fk.from_table.lower() == base_name.lower()
                and fk.to_table.lower() == join_name.lower()
            ):
                matching_fk = fk
                break
            # Check reverse direction (join_table FK points to base_table)
            if (
                fk.from_table.lower() == join_name.lower()
                and fk.to_table.lower() == base_name.lower()
            ):
                matching_fk = fk.reverse()
                break

        if not matching_fk:
            return ""

        # Build join condition(s)
        conditions = []
        for from_col, to_col in zip(matching_fk.from_columns, matching_fk.to_columns):
            conditions.append(f"{base_alias}.{from_col} = {join_alias}.{to_col}")

        join_condition = " and ".join(conditions)

        return f"{join_type} {join_alias} on {join_condition}"

    def _generate_staging_schema_yml(self, design: ModelDesign) -> str:
        """Generate schema.yml for staging models."""
        schema_config = {"version": 2, "models": []}

        for model in design.staging_models:
            model_config = {
                "name": f"stg_{model.name}",
                "description": model.description,
                "columns": [
                    {
                        "name": col.name,
                        "description": col.description or "",
                        "tests": self._generate_column_tests(col),
                    }
                    for col in model.columns
                ],
            }

            schema_config["models"].append(model_config)

        return yaml.dump(schema_config, default_flow_style=False, sort_keys=False)

    def _generate_marts_schema_yml(self, design: ModelDesign) -> str:
        """Generate schema.yml for marts models."""
        schema_config = {"version": 2, "models": []}

        # Dimension models
        for model in design.dimension_models:
            model_config = {
                "name": f"dim_{model.name}",
                "description": model.description,
                "columns": [
                    {
                        "name": col.name,
                        "description": col.description or "",
                        "tests": self._generate_column_tests(col),
                    }
                    for col in model.columns
                ],
            }

            schema_config["models"].append(model_config)

        # Fact models
        for model in design.fact_models:
            model_config = {
                "name": f"fct_{model.name}",
                "description": f"{model.description}\n\nGrain: {model.grain}",
                "columns": [
                    {
                        "name": col.name,
                        "description": col.description or "",
                        "tests": self._generate_column_tests(col),
                    }
                    for col in model.columns
                ],
            }

            schema_config["models"].append(model_config)

        return yaml.dump(schema_config, default_flow_style=False, sort_keys=False)

    def _generate_column_tests(self, col: ColumnDefinition) -> List[str]:
        """Generate dbt tests for a column."""
        tests = []

        if col.is_primary_key:
            tests.append("unique")
            tests.append("not_null")
        elif not col.is_nullable:
            tests.append("not_null")

        if col.is_foreign_key and col.foreign_key_table:
            tests.append(
                {
                    "relationships": {
                        "to": f"ref('{col.foreign_key_table}')",
                        "field": col.foreign_key_column or "id",
                    }
                }
            )

        return tests

    def _generate_documentation(self, design: ModelDesign) -> str:
        """Generate docs.md with project documentation."""
        # Build documentation parts separately to avoid f-string issues with {% %}
        overview_start = "{% docs __overview__ %}\n\n"
        overview_end = "\n{% enddocs %}\n"

        doc_body = f"""# {self.project_name}

## Overview
This dbt project was generated by DataForge on {datetime.now().strftime("%Y-%m-%d")}.

## Project Structure

### Staging Layer
The staging layer contains cleaned and standardized versions of source tables:

"""

        for model in design.staging_models:
            doc_body += f"- **stg_{model.name}**: {model.description}\n"

        doc_body += "\n### Marts Layer\n\n#### Dimensions\n"

        for model in design.dimension_models:
            doc_body += f"- **dim_{model.name}**: {model.description}\n"

        doc_body += "\n#### Facts\n"

        for model in design.fact_models:
            doc_body += f"- **fct_{model.name}**: {model.description} (Grain: {model.grain})\n"

        doc_body += """

## Usage

```bash
# Install dependencies
dbt deps

# Run all models
dbt run

# Run tests
dbt test

# Generate documentation
dbt docs generate
dbt docs serve
```

## Configuration

Set the following environment variables:

- `DBT_HOST`: Database host
- `DBT_PORT`: Database port
- `DBT_USER`: Database user
- `DBT_PASSWORD`: Database password
- `DBT_DATABASE`: Target database name
"""

        return overview_start + doc_body + overview_end

    def _generate_gitignore(self) -> str:
        """Generate .gitignore for dbt project."""
        return """# dbt
target/
dbt_packages/
logs/
dbt_modules/

# Python
__pycache__/
*.py[cod]
.venv/
venv/

# Environment
.env
.env.local

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db
"""

    def _generate_readme(self, design: ModelDesign) -> str:
        """Generate README.md for the project."""
        return f"""# {self.project_name}

**Generated by DataForge** on {datetime.now().strftime("%Y-%m-%d")}

## Overview

This is a dbt project for {design.target_database} data warehouse modeling.

### Models

- **{len(design.staging_models)} staging models**: Clean and standardize source data
- **{len(design.dimension_models)} dimension models**: Business entities
- **{len(design.fact_models)} fact models**: Business events and metrics

## Quick Start

### Prerequisites

- Python 3.11+
- dbt-core
- Database adapter (dbt-postgres, dbt-snowflake, etc.)

### Installation

```bash
# Install dbt
pip install dbt-core dbt-postgres  # or your database adapter

# Install project dependencies
dbt deps
```

### Configuration

1. Copy `.dbt/profiles.yml` to `~/.dbt/profiles.yml`
2. Update with your database credentials
3. Or set environment variables:

```bash
export DBT_HOST="localhost"
export DBT_PORT="5432"
export DBT_USER="your_user"
export DBT_PASSWORD="your_password"
export DBT_DATABASE="analytics"
```

### Running the Project

```bash
# Run all models
dbt run

# Run specific model
dbt run --select stg_customers

# Run with full refresh
dbt run --full-refresh

# Run tests
dbt test

# Generate and serve documentation
dbt docs generate
dbt docs serve
```

## Project Structure

```
{self.project_name}/
├── dbt_project.yml          # Project configuration
├── packages.yml             # dbt package dependencies
├── models/
│   ├── staging/            # Staging models
│   │   ├── sources.yml     # Source definitions
│   │   ├── schema.yml      # Staging tests and docs
│   │   └── stg_*.sql       # Staging transformations
│   ├── marts/              # Analytics-ready models
│   │   ├── schema.yml      # Marts tests and docs
│   │   ├── dim_*.sql       # Dimension tables
│   │   └── fct_*.sql       # Fact tables
│   └── docs.md             # Project documentation
└── README.md               # This file
```

## Data Model

### Grain

{design.fact_models[0].grain if design.fact_models else "One row per business event"}

### Dimensions

{chr(10).join(f"- {dim.name}: {dim.description}" for dim in design.dimension_models)}

### Facts

{chr(10).join(f"- {fact.name}: {fact.description}" for fact in design.fact_models)}

## Development

### Adding New Models

1. Create SQL file in appropriate directory
2. Add documentation to schema.yml
3. Add tests
4. Run and test: `dbt run --select your_model && dbt test --select your_model`

### Best Practices

- Use CTEs for readability
- Add tests for all models
- Document all columns
- Follow naming conventions (stg_, dim_, fct_)
- Use `ref()` for dependencies
- Use `source()` for raw tables

## Support

For issues or questions, contact your DataForge administrator.

---

**Generated by DataForge** - AI-Powered Data Engineering Platform
"""

    def write_to_disk(self, target_dir: Optional[Path] = None) -> Path:
        """
        Write all generated files to disk.

        Args:
            target_dir: Directory to write files (uses self.target_dir if not provided)

        Returns:
            Path to the created project directory
        """
        output_dir = target_dir or self.target_dir
        output_dir = Path(output_dir).resolve()

        logger.info(f"Writing dbt project to: {output_dir}")

        for file_path, content in self.generated_files.items():
            full_path = output_dir / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)

            with open(full_path, "w") as f:
                f.write(content)

            logger.debug(f"Wrote file: {file_path}")

        logger.info(f"Successfully wrote {len(self.generated_files)} files")
        return output_dir
