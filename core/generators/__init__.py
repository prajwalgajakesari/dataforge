"""Code generators for DataForge.

This module provides code generators for different data modeling strategies:
- Star Schema (default): DBTGenerator for dimensional modeling
- 3NF (Third Normal Form): Generator3NF for normalized relational models
- Data Vault: GeneratorDataVault for hub-link-satellite architecture
"""

from core.generators.dbt_generator import (
    ColumnDefinition,
    DBTGenerator,
    DimensionModelDefinition,
    FactModelDefinition,
    ModelDesign,
    SourceDefinition,
    StagingModelDefinition,
    TableDefinition,
)
from core.generators.generator_3nf import Generator3NF
from core.generators.generator_data_vault import (
    GeneratorDataVault,
    Hub,
    Link,
    Satellite,
    PointInTimeTable,
    BridgeTable,
    DataVaultModel,
    HashAlgorithm,
    DataVaultLayer,
)

__all__ = [
    # DBT Generator (Star Schema)
    "DBTGenerator",
    "ModelDesign",
    "SourceDefinition",
    "TableDefinition",
    "ColumnDefinition",
    "StagingModelDefinition",
    "DimensionModelDefinition",
    "FactModelDefinition",
    # 3NF Generator
    "Generator3NF",
    # Data Vault Generator
    "GeneratorDataVault",
    "Hub",
    "Link",
    "Satellite",
    "PointInTimeTable",
    "BridgeTable",
    "DataVaultModel",
    "HashAlgorithm",
    "DataVaultLayer",
    # Factory function
    "get_generator",
]


def get_generator(strategy: str, output_format: str = "dbt"):
    """
    Factory function to get the appropriate generator for a modeling strategy.

    Args:
        strategy: The data modeling strategy to use. Valid options are:
            - "STAR_SCHEMA": Dimensional modeling with facts and dimensions
            - "NORMALIZED_3NF": Third Normal Form relational modeling
            - "DATA_VAULT": Hub-Link-Satellite architecture
        output_format: The output format for generated code. Valid options are:
            - "sql": Raw SQL DDL statements
            - "dbt": dbt models with Jinja templates (default)
            - "sqlalchemy": SQLAlchemy ORM models

    Returns:
        Generator instance configured for the specified strategy and format.

    Raises:
        ValueError: If an unknown strategy or output format is provided.

    Examples:
        >>> generator = get_generator("STAR_SCHEMA", "dbt")
        >>> generator = get_generator("NORMALIZED_3NF", "sql")
        >>> generator = get_generator("DATA_VAULT", "sqlalchemy")
    """
    strategy = strategy.upper()
    output_format = output_format.lower()

    valid_strategies = {"STAR_SCHEMA", "NORMALIZED_3NF", "DATA_VAULT"}
    valid_formats = {"sql", "dbt", "sqlalchemy"}

    if strategy not in valid_strategies:
        raise ValueError(
            f"Unknown strategy: {strategy}. "
            f"Valid options are: {', '.join(sorted(valid_strategies))}"
        )

    if output_format not in valid_formats:
        raise ValueError(
            f"Unknown output format: {output_format}. "
            f"Valid options are: {', '.join(sorted(valid_formats))}"
        )

    if strategy == "STAR_SCHEMA":
        return DBTGenerator(output_format=output_format)
    elif strategy == "NORMALIZED_3NF":
        return Generator3NF(output_format=output_format)
    elif strategy == "DATA_VAULT":
        # Data Vault generator handles its own output formats via separate methods
        # (generate for DDL, generate_dbtvault_models for dbt with dbtvault macros)
        return GeneratorDataVault()
    else:
        # This should never be reached due to validation above
        raise ValueError(f"Unhandled strategy: {strategy}")
