"""
3NF Schema Code Generator for DataForge.

Generates normalized database schemas in multiple output formats:
- SQL DDL (CREATE TABLE, ALTER TABLE, CREATE INDEX)
- dbt models with refs and schema tests
- SQLAlchemy ORM models

The generator takes a ModelDesign and produces properly normalized 3NF
schemas with referential integrity, appropriate indexes, and documentation.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Set

import yaml

from core.models.design import (
    ColumnRole,
    DesignedColumn,
    DesignedRelationship,
    DesignedTable,
    ModelDesign,
    TableRole,
)
from core.models.schema import (
    Column,
    Constraint,
    ForeignKeyRelationship,
    ReferentialAction,
    Table,
)


class Generator3NF:
    """
    Generator for 3NF normalized database schemas.

    This generator produces normalized database DDL and model definitions
    from a ModelDesign specification. It supports multiple output formats
    including raw SQL, dbt models, and SQLAlchemy ORM classes.

    Attributes:
        output_format: Target output format ('sql', 'dbt', 'sqlalchemy').
        schema_name: Default schema name for generated tables.
        include_comments: Whether to include documentation comments.

    Example:
        >>> generator = Generator3NF(output_format="sql")
        >>> files = generator.generate(model_design)
        >>> for filename, content in files.items():
        ...     print(f"Generated: {filename}")
    """

    # SQL type mapping from internal types to PostgreSQL types
    TYPE_MAPPING: Dict[str, str] = {
        # Integers
        "int": "INTEGER",
        "integer": "INTEGER",
        "bigint": "BIGINT",
        "smallint": "SMALLINT",
        "tinyint": "SMALLINT",
        "serial": "SERIAL",
        "bigserial": "BIGSERIAL",
        # Floating point
        "float": "DOUBLE PRECISION",
        "double": "DOUBLE PRECISION",
        "real": "REAL",
        "decimal": "DECIMAL",
        "numeric": "NUMERIC",
        "money": "MONEY",
        # Text
        "string": "VARCHAR(255)",
        "str": "VARCHAR(255)",
        "text": "TEXT",
        "varchar": "VARCHAR",
        "char": "CHAR",
        "character": "CHARACTER",
        # Boolean
        "bool": "BOOLEAN",
        "boolean": "BOOLEAN",
        # Date/Time
        "date": "DATE",
        "time": "TIME",
        "datetime": "TIMESTAMP",
        "timestamp": "TIMESTAMP",
        "timestamptz": "TIMESTAMP WITH TIME ZONE",
        "interval": "INTERVAL",
        # Binary
        "bytes": "BYTEA",
        "bytea": "BYTEA",
        "binary": "BYTEA",
        "blob": "BYTEA",
        # JSON
        "json": "JSONB",
        "jsonb": "JSONB",
        # UUID
        "uuid": "UUID",
        # Arrays
        "array": "TEXT[]",
    }

    # Default referential actions based on relationship type
    DEFAULT_ON_DELETE: Dict[str, ReferentialAction] = {
        "1:1": ReferentialAction.CASCADE,
        "1:N": ReferentialAction.RESTRICT,
        "N:1": ReferentialAction.SET_NULL,
        "N:M": ReferentialAction.CASCADE,
    }

    DEFAULT_ON_UPDATE: Dict[str, ReferentialAction] = {
        "1:1": ReferentialAction.CASCADE,
        "1:N": ReferentialAction.CASCADE,
        "N:1": ReferentialAction.CASCADE,
        "N:M": ReferentialAction.CASCADE,
    }

    def __init__(
        self,
        output_format: str = "sql",
        schema_name: str = "public",
        include_comments: bool = True,
    ) -> None:
        """
        Initialize the 3NF generator.

        Args:
            output_format: Output format - 'sql', 'dbt', or 'sqlalchemy'.
            schema_name: Default schema name for tables.
            include_comments: Whether to include documentation comments.

        Raises:
            ValueError: If output_format is not supported.
        """
        supported_formats = {"sql", "dbt", "sqlalchemy"}
        if output_format not in supported_formats:
            raise ValueError(
                f"Unsupported output format: {output_format}. "
                f"Supported formats: {supported_formats}"
            )

        self.output_format = output_format
        self.schema_name = schema_name
        self.include_comments = include_comments
        self._generated_constraint_names: Set[str] = set()

    def generate(self, design: ModelDesign) -> Dict[str, str]:
        """
        Generate code from a ModelDesign specification.

        Args:
            design: The model design to generate code from.

        Returns:
            Dictionary mapping filenames to file contents.
        """
        self._generated_constraint_names.clear()

        if self.output_format == "sql":
            return self._generate_sql(design)
        elif self.output_format == "dbt":
            return self._generate_dbt(design)
        elif self.output_format == "sqlalchemy":
            return self._generate_sqlalchemy(design)
        else:
            raise ValueError(f"Unsupported format: {self.output_format}")

    # =========================================================================
    # SQL DDL Generation
    # =========================================================================

    def _generate_sql(self, design: ModelDesign) -> Dict[str, str]:
        """Generate SQL DDL files from design."""
        files: Dict[str, str] = {}

        # Generate header
        header = self._generate_sql_header(design)

        # Generate CREATE TABLE statements
        create_tables: List[str] = []
        for table in design.tables:
            create_tables.append(self._generate_create_table(table))

        # Generate ALTER TABLE for foreign keys (separate for dependency ordering)
        alter_tables: List[str] = []
        for table in design.tables:
            fk_statements = self._generate_foreign_keys(table, design.tables)
            alter_tables.extend(fk_statements)

        # Generate indexes
        indexes: List[str] = []
        for table in design.tables:
            idx_statements = self._generate_indexes(table)
            indexes.extend(idx_statements)

        # Combine into single DDL file
        ddl_content = header + "\n\n"
        ddl_content += "-- =============================================================================\n"
        ddl_content += "-- CREATE TABLES\n"
        ddl_content += "-- =============================================================================\n\n"
        ddl_content += "\n\n".join(create_tables)
        ddl_content += "\n\n"

        if alter_tables:
            ddl_content += "-- =============================================================================\n"
            ddl_content += "-- FOREIGN KEY CONSTRAINTS\n"
            ddl_content += "-- =============================================================================\n\n"
            ddl_content += "\n".join(alter_tables)
            ddl_content += "\n\n"

        if indexes:
            ddl_content += "-- =============================================================================\n"
            ddl_content += "-- INDEXES\n"
            ddl_content += "-- =============================================================================\n\n"
            ddl_content += "\n".join(indexes)
            ddl_content += "\n"

        files["schema.sql"] = ddl_content

        # Generate rollback script
        files["rollback.sql"] = self._generate_rollback_sql(design)

        return files

    def _generate_sql_header(self, design: ModelDesign) -> str:
        """Generate SQL file header with metadata."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        header = f"""-- =============================================================================
-- {design.name} - 3NF Normalized Schema
-- Generated by DataForge on {timestamp}
-- Strategy: {design.strategy.value}
-- Version: {design.version}
-- =============================================================================

-- Schema: {self.schema_name}
-- Tables: {len(design.tables)}
-- Relationships: {len(design.relationships)}
"""
        if design.design_notes:
            header += f"--\n-- Notes: {design.design_notes}\n"

        return header

    def _generate_create_table(self, table: DesignedTable) -> str:
        """
        Generate CREATE TABLE DDL for a designed table.

        Args:
            table: The table design to generate DDL for.

        Returns:
            CREATE TABLE SQL statement.
        """
        lines: List[str] = []

        # Add table comment if enabled
        if self.include_comments and table.description:
            lines.append(f"-- {table.description}")

        # Table header
        qualified_name = f"{self.schema_name}.{table.name}"
        lines.append(f"CREATE TABLE {qualified_name} (")

        # Column definitions
        column_defs: List[str] = []
        pk_columns: List[str] = []

        for col in table.columns:
            col_def = self._generate_column_definition(col)
            column_defs.append(f"    {col_def}")

            if col.is_primary_key:
                pk_columns.append(col.name)

        # Add primary key constraint
        if pk_columns:
            pk_name = self._generate_constraint_name(
                table.name, "pk", pk_columns
            )
            pk_cols = ", ".join(pk_columns)
            column_defs.append(f"    CONSTRAINT {pk_name} PRIMARY KEY ({pk_cols})")

        # Add unique constraints for columns marked as unique (non-PK)
        for col in table.columns:
            if col.role == ColumnRole.NATURAL_KEY and not col.is_primary_key:
                uq_name = self._generate_constraint_name(
                    table.name, "uq", [col.name]
                )
                column_defs.append(f"    CONSTRAINT {uq_name} UNIQUE ({col.name})")

        lines.append(",\n".join(column_defs))
        lines.append(");")

        # Add table comment
        if self.include_comments and table.description:
            lines.append(
                f"\nCOMMENT ON TABLE {qualified_name} IS "
                f"'{self._escape_sql_string(table.description)}';"
            )

        # Add column comments
        if self.include_comments:
            for col in table.columns:
                if col.description:
                    lines.append(
                        f"COMMENT ON COLUMN {qualified_name}.{col.name} IS "
                        f"'{self._escape_sql_string(col.description)}';"
                    )

        return "\n".join(lines)

    def _generate_column_definition(self, column: DesignedColumn) -> str:
        """
        Generate column definition for CREATE TABLE.

        Args:
            column: The column design to generate definition for.

        Returns:
            Column definition string (e.g., "name VARCHAR(255) NOT NULL").
        """
        parts = [column.name, self._sql_type_mapping(column)]

        if not column.is_nullable:
            parts.append("NOT NULL")

        # Add default value if this is an audit column
        if column.role == ColumnRole.AUDIT:
            if "created" in column.name.lower():
                parts.append("DEFAULT CURRENT_TIMESTAMP")
            elif "updated" in column.name.lower():
                parts.append("DEFAULT CURRENT_TIMESTAMP")

        return " ".join(parts)

    def _generate_foreign_keys(
        self, table: DesignedTable, all_tables: List[DesignedTable]
    ) -> List[str]:
        """
        Generate ALTER TABLE statements for foreign key constraints.

        Args:
            table: The table to generate FK constraints for.
            all_tables: All tables in the design (for reference validation).

        Returns:
            List of ALTER TABLE SQL statements.
        """
        statements: List[str] = []
        qualified_table = f"{self.schema_name}.{table.name}"

        for col in table.columns:
            if col.role == ColumnRole.FOREIGN_KEY and col.references_table:
                fk_name = self._generate_constraint_name(
                    table.name, "fk", [col.name]
                )

                # Determine referential actions based on relationship type
                # Default to RESTRICT for delete and CASCADE for update
                on_delete = ReferentialAction.RESTRICT
                on_update = ReferentialAction.CASCADE

                # Check if the FK column is nullable
                if col.is_nullable:
                    on_delete = ReferentialAction.SET_NULL

                ref_table = f"{self.schema_name}.{col.references_table}"
                ref_col = col.references_column or "id"

                statement = (
                    f"ALTER TABLE {qualified_table}\n"
                    f"    ADD CONSTRAINT {fk_name}\n"
                    f"    FOREIGN KEY ({col.name})\n"
                    f"    REFERENCES {ref_table} ({ref_col})\n"
                    f"    ON DELETE {on_delete.value}\n"
                    f"    ON UPDATE {on_update.value};"
                )
                statements.append(statement)

        return statements

    def _generate_indexes(self, table: DesignedTable) -> List[str]:
        """
        Generate CREATE INDEX statements for a table.

        Indexes are created for:
        - Foreign key columns (for join performance)
        - Natural key columns (for lookup performance)
        - Commonly queried patterns

        Args:
            table: The table to generate indexes for.

        Returns:
            List of CREATE INDEX SQL statements.
        """
        statements: List[str] = []
        qualified_table = f"{self.schema_name}.{table.name}"

        # Index all foreign key columns
        for col in table.columns:
            if col.role == ColumnRole.FOREIGN_KEY:
                idx_name = self._generate_constraint_name(
                    table.name, "idx", [col.name]
                )
                statements.append(
                    f"CREATE INDEX {idx_name} ON {qualified_table} ({col.name});"
                )

        # Index natural keys that aren't already primary keys
        for col in table.columns:
            if col.role == ColumnRole.NATURAL_KEY and not col.is_primary_key:
                idx_name = self._generate_constraint_name(
                    table.name, "idx", [col.name, "natural"]
                )
                statements.append(
                    f"CREATE INDEX {idx_name} ON {qualified_table} ({col.name});"
                )

        # Add composite index for common query patterns on entity tables
        if table.role == TableRole.ENTITY:
            # Index audit columns for temporal queries
            audit_cols = [
                c.name for c in table.columns if c.role == ColumnRole.AUDIT
            ]
            if audit_cols:
                idx_name = self._generate_constraint_name(
                    table.name, "idx", ["audit"]
                )
                cols = ", ".join(audit_cols)
                statements.append(
                    f"CREATE INDEX {idx_name} ON {qualified_table} ({cols});"
                )

        return statements

    def _generate_rollback_sql(self, design: ModelDesign) -> str:
        """Generate rollback (DROP) script."""
        lines = [
            "-- =============================================================================",
            f"-- Rollback Script for {design.name}",
            f"-- Generated by DataForge on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "-- =============================================================================",
            "",
            "-- WARNING: This will DROP all tables and their data!",
            "",
        ]

        # Drop tables in reverse order (to handle FK dependencies)
        for table in reversed(design.tables):
            qualified_name = f"{self.schema_name}.{table.name}"
            lines.append(f"DROP TABLE IF EXISTS {qualified_name} CASCADE;")

        return "\n".join(lines)

    # =========================================================================
    # dbt Model Generation
    # =========================================================================

    def _generate_dbt(self, design: ModelDesign) -> Dict[str, str]:
        """Generate dbt models and schema files."""
        files: Dict[str, str] = {}

        # Generate staging models (1:1 with source tables)
        for table in design.tables:
            if table.role in (TableRole.STAGING, TableRole.ENTITY):
                model_name = f"stg_{table.name}"
                files[f"models/staging/{model_name}.sql"] = self._generate_dbt_staging_model(
                    table, design
                )

        # Generate mart models
        for table in design.tables:
            if table.role not in (TableRole.STAGING,):
                model_name = self._get_dbt_model_name(table)
                files[f"models/marts/{model_name}.sql"] = self._generate_dbt_model(
                    table, design
                )

        # Generate schema YAML files
        files["models/staging/schema.yml"] = self._generate_dbt_staging_schema(design)
        files["models/marts/schema.yml"] = self._generate_dbt_marts_schema(design)

        # Generate sources.yml
        files["models/staging/sources.yml"] = self._generate_dbt_sources(design)

        return files

    def _generate_dbt_staging_model(
        self, table: DesignedTable, design: ModelDesign
    ) -> str:
        """Generate a dbt staging model that is 1:1 with source table."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        source_name = design.source_schema or "raw"
        source_table = table.source_tables[0] if table.source_tables else table.name

        lines = [
            "{{",
            "    config(",
            "        materialized='view',",
            "        schema='staging'",
            "    )",
            "}}",
            "",
            f"-- Staging model for {table.name}",
            f"-- Generated by DataForge on {timestamp}",
            "",
            "with source as (",
            f"    select * from {{{{ source('{source_name}', '{source_table}') }}}}",
            "),",
            "",
            "renamed as (",
            "    select",
        ]

        # Add columns with proper formatting
        col_lines = []
        for i, col in enumerate(table.columns):
            col_line = f"        {col.name}"
            if col.description and self.include_comments:
                col_line += f"  -- {col.description}"
            if i < len(table.columns) - 1:
                col_line += ","
            col_lines.append(col_line)

        lines.extend(col_lines)
        lines.extend([
            "    from source",
            ")",
            "",
            "select * from renamed",
        ])

        return "\n".join(lines)

    def _generate_dbt_model(
        self, table: DesignedTable, design: ModelDesign
    ) -> str:
        """
        Generate a dbt model SQL file with proper ref() calls.

        Args:
            table: The table to generate model for.
            design: The full model design for relationship context.

        Returns:
            dbt model SQL content.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        lines = [
            "{{",
            "    config(",
            "        materialized='table',",
            f"        schema='{self.schema_name}'",
            "    )",
            "}}",
            "",
        ]

        # Add description as comment
        if table.description and self.include_comments:
            lines.append(f"-- {table.description}")
            if table.grain:
                lines.append(f"-- Grain: {table.grain}")
            lines.append("")

        # Find relationships for this table
        related_tables = self._get_related_tables(table, design)

        # Generate CTEs for related tables
        cte_names = []
        for i, (rel_table, rel_type) in enumerate(related_tables):
            ref_name = self._get_dbt_model_name_from_table_name(rel_table)
            cte_name = rel_table.replace("-", "_")
            cte_names.append(cte_name)

            if i == 0:
                lines.append("with")

            lines.append(f"{cte_name} as (")
            lines.append(f"    select * from {{{{ ref('{ref_name}') }}}}")

            if i < len(related_tables) - 1:
                lines.append("),")
            else:
                lines.append("),")

        # Add main table CTE
        main_ref = f"stg_{table.name}"
        if related_tables:
            lines.extend([
                "",
                "source as (",
                f"    select * from {{{{ ref('{main_ref}') }}}}",
                "),",
            ])
        else:
            lines.extend([
                "with source as (",
                f"    select * from {{{{ ref('{main_ref}') }}}}",
                "),",
            ])

        # Generate final select
        lines.extend([
            "",
            "final as (",
            "    select",
        ])

        # Add columns
        col_lines = []
        for i, col in enumerate(table.columns):
            col_line = f"        source.{col.name}"
            if i < len(table.columns) - 1:
                col_line += ","
            col_lines.append(col_line)

        lines.extend(col_lines)
        lines.extend([
            "    from source",
        ])

        # Add joins for related tables
        for rel_table, rel_type in related_tables:
            cte_name = rel_table.replace("-", "_")
            # Find the FK column for this relationship
            fk_col = self._find_fk_column(table, rel_table)
            if fk_col:
                lines.append(
                    f"    left join {cte_name} on source.{fk_col} = {cte_name}.id"
                )

        lines.extend([
            ")",
            "",
            "select * from final",
            "",
            f"-- Generated by DataForge on {timestamp}",
        ])

        return "\n".join(lines)

    def _generate_dbt_staging_schema(self, design: ModelDesign) -> str:
        """Generate schema.yml for staging models."""
        schema: Dict[str, Any] = {
            "version": 2,
            "models": [],
        }

        for table in design.tables:
            if table.role in (TableRole.STAGING, TableRole.ENTITY):
                model_config = {
                    "name": f"stg_{table.name}",
                    "description": table.description or f"Staging model for {table.name}",
                    "columns": self._generate_dbt_column_tests(table),
                }
                schema["models"].append(model_config)

        return yaml.dump(schema, default_flow_style=False, sort_keys=False)

    def _generate_dbt_marts_schema(self, design: ModelDesign) -> str:
        """Generate schema.yml for mart models with tests."""
        schema: Dict[str, Any] = {
            "version": 2,
            "models": [],
        }

        for table in design.tables:
            if table.role not in (TableRole.STAGING,):
                model_name = self._get_dbt_model_name(table)
                model_config = {
                    "name": model_name,
                    "description": table.description or f"Mart model: {table.name}",
                    "columns": self._generate_dbt_column_tests(table),
                }
                schema["models"].append(model_config)

        return yaml.dump(schema, default_flow_style=False, sort_keys=False)

    def _generate_dbt_column_tests(self, table: DesignedTable) -> List[Dict[str, Any]]:
        """Generate dbt column configurations with tests."""
        columns = []

        for col in table.columns:
            col_config: Dict[str, Any] = {
                "name": col.name,
                "description": col.description or "",
            }

            tests = []

            # Add tests based on column properties
            if col.is_primary_key:
                tests.extend(["unique", "not_null"])
            elif not col.is_nullable:
                tests.append("not_null")

            # Add relationship test for foreign keys
            if col.role == ColumnRole.FOREIGN_KEY and col.references_table:
                ref_model = self._get_dbt_model_name_from_table_name(col.references_table)
                tests.append({
                    "relationships": {
                        "to": f"ref('{ref_model}')",
                        "field": col.references_column or "id",
                    }
                })

            if tests:
                col_config["tests"] = tests

            columns.append(col_config)

        return columns

    def _generate_dbt_sources(self, design: ModelDesign) -> str:
        """Generate sources.yml for dbt."""
        source_name = design.source_schema or "raw"

        sources_config: Dict[str, Any] = {
            "version": 2,
            "sources": [
                {
                    "name": source_name,
                    "description": f"Source tables for {design.name}",
                    "schema": source_name,
                    "tables": [],
                }
            ],
        }

        for table in design.tables:
            source_table = table.source_tables[0] if table.source_tables else table.name
            table_config = {
                "name": source_table,
                "description": table.description or f"Source: {source_table}",
            }
            sources_config["sources"][0]["tables"].append(table_config)

        return yaml.dump(sources_config, default_flow_style=False, sort_keys=False)

    # =========================================================================
    # SQLAlchemy ORM Generation
    # =========================================================================

    def _generate_sqlalchemy(self, design: ModelDesign) -> Dict[str, str]:
        """Generate SQLAlchemy ORM models."""
        files: Dict[str, str] = {}
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Generate base module
        files["models/__init__.py"] = self._generate_sqlalchemy_init(design)
        files["models/base.py"] = self._generate_sqlalchemy_base()

        # Generate model for each table
        for table in design.tables:
            filename = f"models/{table.name}.py"
            files[filename] = self._generate_sqlalchemy_model(table, design)

        return files

    def _generate_sqlalchemy_init(self, design: ModelDesign) -> str:
        """Generate __init__.py for SQLAlchemy models package."""
        lines = [
            '"""',
            f"SQLAlchemy models for {design.name}.",
            "",
            f"Generated by DataForge on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            '"""',
            "",
            "from .base import Base",
            "",
        ]

        # Import all models
        for table in design.tables:
            class_name = self._to_class_name(table.name)
            lines.append(f"from .{table.name} import {class_name}")

        lines.append("")
        lines.append("__all__ = [")
        lines.append('    "Base",')
        for table in design.tables:
            class_name = self._to_class_name(table.name)
            lines.append(f'    "{class_name}",')
        lines.append("]")

        return "\n".join(lines)

    def _generate_sqlalchemy_base(self) -> str:
        """Generate base.py with SQLAlchemy declarative base."""
        return '''"""
SQLAlchemy declarative base for DataForge models.
"""

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import MetaData
from datetime import datetime


# Naming convention for constraints
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    metadata = MetaData(naming_convention=convention)
'''

    def _generate_sqlalchemy_model(
        self, table: DesignedTable, design: ModelDesign
    ) -> str:
        """Generate SQLAlchemy model for a single table."""
        class_name = self._to_class_name(table.name)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        lines = [
            '"""',
            f"SQLAlchemy model for {table.name}.",
            "",
            f"Generated by DataForge on {timestamp}",
            '"""',
            "",
            "from datetime import datetime",
            "from typing import Optional, List",
            "",
            "from sqlalchemy import ForeignKey, String, Integer, Text, Boolean, DateTime",
            "from sqlalchemy.orm import Mapped, mapped_column, relationship",
            "",
            "from .base import Base",
            "",
            "",
        ]

        # Generate class
        lines.append(f"class {class_name}(Base):")

        # Add docstring
        if table.description:
            lines.append(f'    """{table.description}"""')
        else:
            lines.append(f'    """Model for {table.name} table."""')
        lines.append("")

        # Add table name
        lines.append(f'    __tablename__ = "{table.name}"')
        lines.append("")

        # Add columns
        for col in table.columns:
            col_def = self._generate_sqlalchemy_column(col)
            lines.append(f"    {col_def}")

        # Add relationships
        relationships = self._get_table_relationships(table, design)
        if relationships:
            lines.append("")
            lines.append("    # Relationships")
            for rel_line in relationships:
                lines.append(f"    {rel_line}")

        # Add repr method
        lines.extend([
            "",
            "    def __repr__(self) -> str:",
            f'        return f"<{class_name}(id={{self.id}})">' if self._has_id_column(table) else f'        return f"<{class_name}>"',
        ])

        return "\n".join(lines)

    def _generate_sqlalchemy_column(self, column: DesignedColumn) -> str:
        """Generate SQLAlchemy column definition."""
        sa_type = self._get_sqlalchemy_type(column.data_type)
        python_type = self._get_python_type(column.data_type)

        # Build mapped_column arguments
        args = []

        # Add SQLAlchemy type
        args.append(sa_type)

        # Add ForeignKey if applicable
        if column.role == ColumnRole.FOREIGN_KEY and column.references_table:
            ref_col = column.references_column or "id"
            args.append(f'ForeignKey("{column.references_table}.{ref_col}")')

        # Add constraints
        if column.is_primary_key:
            args.append("primary_key=True")
        if not column.is_nullable and not column.is_primary_key:
            args.append("nullable=False")

        # Format the column definition
        if column.is_nullable and not column.is_primary_key:
            type_hint = f"Mapped[Optional[{python_type}]]"
        else:
            type_hint = f"Mapped[{python_type}]"

        args_str = ", ".join(args)
        return f"{column.name}: {type_hint} = mapped_column({args_str})"

    def _get_sqlalchemy_type(self, data_type: str) -> str:
        """Map data type to SQLAlchemy type."""
        base_type = data_type.lower().split("(")[0].strip()

        type_map = {
            "int": "Integer",
            "integer": "Integer",
            "bigint": "Integer",
            "smallint": "Integer",
            "serial": "Integer",
            "bigserial": "Integer",
            "varchar": "String",
            "string": "String(255)",
            "str": "String(255)",
            "text": "Text",
            "char": "String",
            "boolean": "Boolean",
            "bool": "Boolean",
            "date": "DateTime",
            "datetime": "DateTime",
            "timestamp": "DateTime",
            "float": "Float",
            "double": "Float",
            "decimal": "Numeric",
            "numeric": "Numeric",
            "uuid": "String(36)",
            "json": "JSON",
            "jsonb": "JSON",
        }

        return type_map.get(base_type, "String")

    def _get_python_type(self, data_type: str) -> str:
        """Map data type to Python type hint."""
        base_type = data_type.lower().split("(")[0].strip()

        type_map = {
            "int": "int",
            "integer": "int",
            "bigint": "int",
            "smallint": "int",
            "serial": "int",
            "bigserial": "int",
            "varchar": "str",
            "string": "str",
            "str": "str",
            "text": "str",
            "char": "str",
            "boolean": "bool",
            "bool": "bool",
            "date": "datetime",
            "datetime": "datetime",
            "timestamp": "datetime",
            "float": "float",
            "double": "float",
            "decimal": "float",
            "numeric": "float",
            "uuid": "str",
            "json": "dict",
            "jsonb": "dict",
        }

        return type_map.get(base_type, "str")

    def _get_table_relationships(
        self, table: DesignedTable, design: ModelDesign
    ) -> List[str]:
        """Generate relationship definitions for SQLAlchemy."""
        relationships = []

        # Find relationships where this table is the source (has FK)
        for rel in design.relationships:
            if rel.from_table == table.name:
                target_class = self._to_class_name(rel.to_table)
                rel_name = rel.to_table.lower()
                relationships.append(
                    f'{rel_name}: Mapped["{target_class}"] = relationship(back_populates="{table.name.lower()}s")'
                )

        # Find relationships where this table is the target (referenced by FK)
        for rel in design.relationships:
            if rel.to_table == table.name:
                source_class = self._to_class_name(rel.from_table)
                rel_name = f"{rel.from_table.lower()}s"
                relationships.append(
                    f'{rel_name}: Mapped[List["{source_class}"]] = relationship(back_populates="{table.name.lower()}")'
                )

        return relationships

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _sql_type_mapping(self, column: DesignedColumn) -> str:
        """
        Map internal column type to SQL type.

        Args:
            column: The column to map type for.

        Returns:
            SQL type string (e.g., "VARCHAR(255)", "INTEGER").
        """
        data_type = column.data_type.lower()

        # If type already has parentheses (e.g., "varchar(100)"), use as-is
        if "(" in data_type:
            base = data_type.split("(")[0]
            if base in self.TYPE_MAPPING:
                mapped = self.TYPE_MAPPING[base]
                # Extract the length/precision from original
                params = data_type.split("(")[1].rstrip(")")
                if "(" not in mapped:
                    return f"{mapped}({params})"
            return data_type.upper()

        # Map simple types
        if data_type in self.TYPE_MAPPING:
            return self.TYPE_MAPPING[data_type]

        # Default: return as-is in uppercase
        return data_type.upper()

    def _generate_constraint_name(
        self, table: str, constraint_type: str, columns: List[str]
    ) -> str:
        """
        Generate a unique constraint name.

        Args:
            table: Table name.
            constraint_type: Type of constraint (pk, fk, uq, idx, ck).
            columns: Column names involved in the constraint.

        Returns:
            Unique constraint name (e.g., "pk_users", "fk_orders_customer_id").
        """
        # Build base name
        col_part = "_".join(columns[:2])  # Limit column names to avoid too long names
        base_name = f"{constraint_type}_{table}_{col_part}"

        # Ensure uniqueness
        name = base_name
        counter = 1
        while name in self._generated_constraint_names:
            name = f"{base_name}_{counter}"
            counter += 1

        self._generated_constraint_names.add(name)
        return name

    def _escape_sql_string(self, value: str) -> str:
        """Escape single quotes in SQL strings."""
        return value.replace("'", "''")

    def _to_class_name(self, table_name: str) -> str:
        """Convert table name to PascalCase class name."""
        parts = table_name.replace("-", "_").split("_")
        return "".join(part.capitalize() for part in parts)

    def _get_dbt_model_name(self, table: DesignedTable) -> str:
        """Get dbt model name based on table role."""
        if table.role == TableRole.FACT:
            return f"fct_{table.name}"
        elif table.role == TableRole.DIMENSION:
            return f"dim_{table.name}"
        elif table.role == TableRole.STAGING:
            return f"stg_{table.name}"
        else:
            return table.name

    def _get_dbt_model_name_from_table_name(self, table_name: str) -> str:
        """Get dbt model reference name from table name."""
        # Simple heuristic - could be enhanced with table role lookup
        return f"stg_{table_name}"

    def _get_related_tables(
        self, table: DesignedTable, design: ModelDesign
    ) -> List[tuple]:
        """Get tables related to this table via foreign keys."""
        related = []

        for col in table.columns:
            if col.role == ColumnRole.FOREIGN_KEY and col.references_table:
                related.append((col.references_table, "reference"))

        return related

    def _find_fk_column(self, table: DesignedTable, ref_table: str) -> Optional[str]:
        """Find the FK column that references a given table."""
        for col in table.columns:
            if col.role == ColumnRole.FOREIGN_KEY and col.references_table == ref_table:
                return col.name
        return None

    def _has_id_column(self, table: DesignedTable) -> bool:
        """Check if table has an 'id' column."""
        return any(col.name.lower() == "id" for col in table.columns)
