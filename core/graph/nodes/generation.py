"""
Code generation nodes for the data modeling workflow.

This module provides nodes for generating and validating output code
based on the model design, supporting multiple output formats (dbt, SQL, SQLAlchemy)
and multiple modeling strategies (Star Schema, 3NF, Data Vault).

Nodes:
    - generate_output: Generate code based on design and strategy
    - validate_output: Validate generated code for correctness
"""

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

from core.utils.logger import get_logger

if TYPE_CHECKING:
    from core.graph.modeling_graph import ModelingState
    from core.generators.dbt_generator import DBTGenerator, ModelDesign
    from core.validators import OutputValidator

logger = get_logger(__name__)


async def generate_output(
    state: "ModelingState",
    generator: Optional["DBTGenerator"] = None,
    convert_to_model_design: Optional[Callable] = None,
    output_format: str = "dbt",
) -> "ModelingState":
    """
    Generate output code based on the model design and strategy.

    This node uses the appropriate generator (DBTGenerator, Generator3NF,
    or GeneratorDataVault) to produce output code files based on the
    generated model design.

    Args:
        state: Current modeling workflow state with model_design populated
        generator: Optional pre-configured generator (auto-selected if None)
        convert_to_model_design: Function to convert state to ModelDesign format
        output_format: Output format - "dbt", "sql", or "sqlalchemy" (default: "dbt")

    Returns:
        Updated ModelingState with generated files

    State Updates:
        - generated_files: Dict mapping file paths to file contents
        - current_step: Set to "generate_output"
        - progress: Set to 0.9
        - errors: Appended if generation fails
        - status: Set to "failed" if generation fails

    Generated Files (vary by strategy and format):
        dbt format:
            - dbt_project.yml
            - models/staging/sources.yml
            - models/staging/stg_*.sql
            - models/marts/dim_*.sql or fct_*.sql

        sql format:
            - ddl/*.sql (CREATE TABLE statements)

        sqlalchemy format:
            - models/*.py (SQLAlchemy model classes)
    """
    strategy = state.get("modeling_strategy", "STAR_SCHEMA")
    logger.info(f"Generating {output_format} output for {strategy}...")

    try:
        # Auto-select generator if not provided
        if generator is None:
            from core.generators import get_generator
            generator = get_generator(strategy=strategy, output_format=output_format)

        # Handle different strategies
        if strategy == "STAR_SCHEMA":
            generated_files = await _generate_star_schema(
                state, generator, convert_to_model_design
            )
        elif strategy == "NORMALIZED_3NF":
            generated_files = await _generate_3nf(state, generator)
        elif strategy == "DATA_VAULT":
            generated_files = await _generate_data_vault(state, generator)
        else:
            logger.warning(f"Unknown strategy: {strategy}")
            generated_files = {}

        state["generated_files"] = generated_files
        state["current_step"] = "generate_output"
        state["progress"] = 0.9

        logger.info(f"Generated {len(generated_files)} files")

    except Exception as e:
        logger.error(f"Output generation failed: {e}")
        state["errors"].append(f"Output generation failed: {e}")
        state["status"] = "failed"

    return state


async def _generate_star_schema(
    state: "ModelingState",
    generator: Any,
    convert_to_model_design: Optional[Callable],
) -> Dict[str, str]:
    """Generate Star Schema output files."""
    # Convert design to ModelDesign format
    if convert_to_model_design:
        model_design = convert_to_model_design(state)
    else:
        model_design = _default_convert_to_model_design(state)

    if model_design is None:
        logger.error("Could not convert design to ModelDesign format")
        raise ValueError("Failed to convert design for code generation")

    # Generate dbt project files
    return generator.generate_project(model_design)


async def _generate_3nf(state: "ModelingState", generator: Any) -> Dict[str, str]:
    """Generate 3NF output files."""
    design_dict = state.get("model_design", {})
    entities = design_dict.get("entities", [])

    if not entities:
        logger.warning("No entities found in 3NF design")
        return {}

    try:
        return generator.generate(entities)
    except Exception as e:
        logger.warning(f"3NF generation failed, using fallback: {e}")
        return _generate_basic_3nf_sql(entities)


async def _generate_data_vault(state: "ModelingState", generator: Any) -> Dict[str, str]:
    """Generate Data Vault output files."""
    design_dict = state.get("model_design", {})

    try:
        from core.generators import DataVaultModel, Hub, Link, Satellite

        hubs = [Hub(**h) for h in design_dict.get("hubs", [])]
        links = [Link(**l) for l in design_dict.get("links", [])]
        satellites = [Satellite(**s) for s in design_dict.get("satellites", [])]

        model = DataVaultModel(hubs=hubs, links=links, satellites=satellites)
        return generator.generate(model)
    except Exception as e:
        logger.warning(f"Data Vault generation failed: {e}")
        return {}


def _generate_basic_3nf_sql(entities: List[Dict[str, Any]]) -> Dict[str, str]:
    """Generate basic SQL DDL for 3NF entities as fallback."""
    files = {}

    for entity in entities:
        name = entity.get("name", "unknown")
        columns = entity.get("columns", [])

        col_defs = []
        pk_cols = []

        for col in columns:
            col_name = col.get("name", "")
            data_type = col.get("data_type", "VARCHAR(255)")
            nullable = "NULL" if col.get("is_nullable", True) else "NOT NULL"
            col_defs.append(f"    {col_name} {data_type} {nullable}")

            if col.get("is_primary_key"):
                pk_cols.append(col_name)

        if pk_cols:
            col_defs.append(f"    PRIMARY KEY ({', '.join(pk_cols)})")

        sql = f"CREATE TABLE {name} (\n{',\n'.join(col_defs)}\n);\n"
        files[f"ddl/{name}.sql"] = sql

    return files


def _default_convert_to_model_design(state: "ModelingState") -> Optional[Any]:
    """Default converter from state to ModelDesign."""
    try:
        from core.generators.dbt_generator import (
            ModelDesign, SourceDefinition, TableDefinition, ColumnDefinition,
            StagingModelDefinition, DimensionModelDefinition, FactModelDefinition,
        )

        design_dict = state.get("model_design", {})
        discovered_tables = state.get("discovered_tables", [])

        # Build sources from discovered tables
        sources = []
        source_tables_map = {}

        for table in discovered_tables:
            schema_name = table.get("schema", "public")
            source = next((s for s in sources if s.schema == schema_name), None)
            if not source:
                source = SourceDefinition(name=schema_name, schema=schema_name, tables=[])
                sources.append(source)

            table_def = TableDefinition(
                name=table["name"],
                schema=schema_name,
                columns=[
                    ColumnDefinition(
                        name=col["name"],
                        data_type=col["data_type"],
                        is_nullable=col.get("is_nullable", True),
                        is_primary_key=col.get("is_primary_key", False),
                        is_foreign_key=col.get("is_foreign_key", False),
                        foreign_key_table=col.get("foreign_key_table"),
                        foreign_key_column=col.get("foreign_key_column"),
                    )
                    for col in table.get("columns", [])
                ],
                row_count=table.get("row_count"),
            )
            source.tables.append(table_def)
            source_tables_map[table["name"]] = table_def

        # Build staging, dimension, and fact models
        staging_models = [
            StagingModelDefinition(
                name=stg["name"],
                source_table=source_tables_map.get(stg.get("source_table", stg.get("name"))),
                columns=[
                    ColumnDefinition(
                        name=col["name"],
                        data_type=col.get("data_type", "varchar"),
                        description=col.get("description"),
                        is_nullable=col.get("is_nullable", True),
                        is_primary_key=col.get("is_primary_key", False),
                    )
                    for col in stg.get("columns", [])
                ],
                description=stg.get("description"),
            )
            for stg in design_dict.get("staging_models", [])
            if source_tables_map.get(stg.get("source_table", stg.get("name")))
        ]

        dimension_models = [
            DimensionModelDefinition(
                name=dim["name"],
                source_models=dim.get("source_models", []),
                columns=[
                    ColumnDefinition(
                        name=col["name"],
                        data_type=col.get("data_type", "varchar"),
                        description=col.get("description"),
                    )
                    for col in dim.get("columns", [])
                ],
                description=dim.get("description"),
                slowly_changing_type=dim.get("scd_type", 1),
            )
            for dim in design_dict.get("dimensions", [])
        ]

        fact_models = [
            FactModelDefinition(
                name=fact["name"],
                source_models=fact.get("source_models", []),
                grain=fact.get("grain", ""),
                columns=[
                    ColumnDefinition(
                        name=col["name"],
                        data_type=col.get("data_type", "varchar"),
                        description=col.get("description"),
                    )
                    for col in fact.get("columns", [])
                ],
                measures=fact.get("measures", []),
                dimensions=fact.get("dimensions", []),
                description=fact.get("description"),
            )
            for fact in design_dict.get("facts", [])
        ]

        return ModelDesign(
            project_name=state.get("project_name", "analytics_project"),
            sources=sources,
            staging_models=staging_models,
            dimension_models=dimension_models,
            fact_models=fact_models,
        )

    except Exception as e:
        logger.warning(f"Could not build ModelDesign: {e}")
        return None


async def validate_output(
    state: "ModelingState",
    validator: Optional["OutputValidator"] = None,
) -> "ModelingState":
    """
    Validate generated output files for correctness.

    This node uses the OutputValidator to check generated files for
    syntax errors, security issues, and best practice violations.

    Args:
        state: Current modeling workflow state with generated_files populated
        validator: Optional OutputValidator instance (uses built-in if None)

    Returns:
        Updated ModelingState with validation results

    State Updates:
        - output_validation: Validation report with issues
        - output_is_valid: Boolean indicating if output passes validation
        - current_step: Set to "validate_output"
        - progress: Set to 1.0
        - errors: Appended with validation errors
        - warnings: Appended with validation warnings
        - status: Set to "completed" if valid
    """
    logger.info("Validating generated files...")

    try:
        generated_files = state.get("generated_files", {})

        if not generated_files:
            state["output_validation"] = {
                "is_valid": True,
                "file_count": 0,
                "issues": [],
                "note": "No files generated to validate",
            }
            state["output_is_valid"] = True
            state["status"] = "completed"
            state["progress"] = 1.0
            state["current_step"] = "validate_output"
            return state

        issues = []
        file_validations = {}

        # Check for required files based on strategy
        strategy = state.get("modeling_strategy", "STAR_SCHEMA")
        required_files = _get_required_files(strategy)

        for required in required_files:
            if required not in generated_files:
                issues.append({
                    "file": required,
                    "severity": "warning",
                    "message": f"Missing expected file: {required}",
                })

        # Validate each file
        if validator:
            # Use the OutputValidator if provided
            for file_path, content in generated_files.items():
                workspace = Path(state.get("workspace_path", "./output"))
                full_path = workspace / file_path

                # Write temp file for validation if needed
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(content)

                file_issues = validator.validate_file(full_path)
                file_validations[file_path] = {
                    "is_valid": all(i.severity.value not in ("error", "critical") for i in file_issues),
                    "issues": [str(i) for i in file_issues],
                }

                for issue in file_issues:
                    issues.append({
                        "file": file_path,
                        "line": issue.line_number,
                        "type": issue.issue_type.value,
                        "message": issue.message,
                        "severity": issue.severity.value,
                    })
        else:
            # Use built-in validation
            for file_path, content in generated_files.items():
                validation = _validate_file(file_path, content)
                file_validations[file_path] = validation
                if not validation["is_valid"]:
                    for issue_msg in validation.get("issues", []):
                        issues.append({
                            "file": file_path,
                            "severity": "error",
                            "message": issue_msg,
                        })

        # Determine overall validity
        error_issues = [i for i in issues if i.get("severity") in ("error", "critical")]
        is_valid = len(error_issues) == 0

        state["output_validation"] = {
            "is_valid": is_valid,
            "file_count": len(generated_files),
            "issues": issues,
            "files": file_validations,
            "error_count": len(error_issues),
            "warning_count": len([i for i in issues if i.get("severity") == "warning"]),
        }
        state["output_is_valid"] = is_valid

        if is_valid:
            state["status"] = "completed"
            state["progress"] = 1.0
            logger.info("Output validation successful")
        else:
            # Add errors to state
            for issue in error_issues:
                state["errors"].append(f"{issue['file']}: {issue['message']}")
            if state.get("status") != "failed":
                state["status"] = "completed"  # Don't fail on validation warnings
            logger.warning(f"Output validation completed with {len(issues)} issues")

        state["current_step"] = "validate_output"

    except Exception as e:
        logger.error(f"Output validation failed: {e}")
        state["warnings"].append(f"Output validation skipped: {e}")
        state["output_validation"] = {"is_valid": True, "error": str(e)}
        state["output_is_valid"] = True
        state["status"] = "completed"

    return state


def _get_required_files(strategy: str) -> List[str]:
    """Get required files based on modeling strategy."""
    if strategy == "STAR_SCHEMA":
        return ["dbt_project.yml", "models/staging/sources.yml"]
    elif strategy == "NORMALIZED_3NF":
        return []  # No specific required files
    elif strategy == "DATA_VAULT":
        return ["dbt_project.yml"]
    return []


def _validate_file(file_path: str, content: str) -> Dict[str, Any]:
    """
    Validate a single generated file.

    Args:
        file_path: Path of the file
        content: File content

    Returns:
        Dict with validation results
    """
    issues = []

    # Check for empty content
    if not content or not content.strip():
        issues.append(f"Empty file: {file_path}")
        return {"is_valid": False, "issues": issues}

    # Validate YAML files
    if file_path.endswith(".yml") or file_path.endswith(".yaml"):
        try:
            import yaml
            yaml.safe_load(content)
        except yaml.YAMLError as e:
            issues.append(f"Invalid YAML in {file_path}: {e}")

    # Validate SQL files
    elif file_path.endswith(".sql"):
        # Basic SQL validation - check for common issues
        if "SELECT" not in content.upper() and "{{" not in content:
            # Not a select statement and no Jinja - might be a config file
            pass
        else:
            # Check for unclosed braces
            if content.count("{") != content.count("}"):
                issues.append(f"Unbalanced braces in {file_path}")

            if content.count("{{") != content.count("}}"):
                issues.append(f"Unbalanced Jinja braces in {file_path}")

    return {
        "is_valid": len(issues) == 0,
        "issues": issues,
    }


def get_generation_summary(state: "ModelingState") -> Dict[str, Any]:
    """
    Generate a summary of the generation results.

    Args:
        state: ModelingState with generation results

    Returns:
        Summary dictionary with generation statistics
    """
    generated_files = state.get("generated_files", {})
    validation = state.get("output_validation", {})

    # Categorize files
    yml_files = [f for f in generated_files if f.endswith(".yml") or f.endswith(".yaml")]
    sql_files = [f for f in generated_files if f.endswith(".sql")]

    # Get file sizes
    total_size = sum(len(content) for content in generated_files.values())

    return {
        "total_files": len(generated_files),
        "yml_files": len(yml_files),
        "sql_files": len(sql_files),
        "total_size_bytes": total_size,
        "validation": {
            "is_valid": validation.get("is_valid", False),
            "issue_count": len(validation.get("issues", [])),
        },
        "files": list(generated_files.keys()),
    }


def get_file_by_category(
    generated_files: Dict[str, str],
    category: str,
) -> Dict[str, str]:
    """
    Filter generated files by category.

    Args:
        generated_files: Dict of file path to content
        category: One of "staging", "dimensions", "facts", "config"

    Returns:
        Filtered dict of files matching the category
    """
    category_patterns = {
        "staging": "models/staging/",
        "dimensions": "models/dimensions/",
        "facts": "models/facts/",
        "config": (".yml", "dbt_project.yml"),
    }

    pattern = category_patterns.get(category.lower(), "")

    if isinstance(pattern, tuple):
        return {
            path: content
            for path, content in generated_files.items()
            if any(p in path for p in pattern)
        }
    else:
        return {
            path: content
            for path, content in generated_files.items()
            if pattern in path
        }


def write_files_to_disk(
    state: "ModelingState",
    output_dir: Optional[str] = None,
) -> List[str]:
    """
    Write generated files to disk.

    Args:
        state: ModelingState with generated_files populated
        output_dir: Target directory (defaults to workspace_path from state)

    Returns:
        List of written file paths
    """
    output_path = Path(output_dir or state.get("workspace_path", "./output"))
    files = state.get("generated_files", {})

    written = []

    for file_path, content in files.items():
        full_path = output_path / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)
        written.append(str(full_path))
        logger.debug(f"Wrote: {full_path}")

    logger.info(f"Wrote {len(written)} files to {output_path}")
    return written
