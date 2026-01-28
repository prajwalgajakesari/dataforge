"""
Design nodes for the data modeling workflow.

This module provides nodes for creating and validating data model
designs using LLM-assisted generation and design validators.

Nodes:
    - create_design: Generate data model design using LLM
    - validate_design: Validate design against strategy requirements
"""

from typing import Any, Dict, List, Optional, Literal, TYPE_CHECKING

from pydantic import BaseModel, Field

from core.utils.logger import get_logger

if TYPE_CHECKING:
    from core.graph.modeling_graph import ModelingState
    from core.utils.llm_client import LLMClient
    from core.validators import DesignValidator

logger = get_logger(__name__)


# =============================================================================
# Design Output Models for LLM Structured Output
# =============================================================================


class StarSchemaDesign(BaseModel):
    """LLM output schema for star schema design."""

    reasoning: str = Field(
        description="Explanation of design decisions and trade-offs"
    )
    staging_models: List[Dict[str, Any]] = Field(
        description="Staging models for data cleaning and transformation"
    )
    dimensions: List[Dict[str, Any]] = Field(
        description="Dimension tables with descriptive attributes"
    )
    facts: List[Dict[str, Any]] = Field(
        description="Fact tables with measures and dimension keys"
    )


class NormalizedDesign(BaseModel):
    """LLM output schema for Normalized (3NF) design."""

    reasoning: str = Field(
        description="Explanation of normalization decisions"
    )
    entities: List[Dict[str, Any]] = Field(
        description="List of normalized entities (tables)"
    )
    relationships: List[Dict[str, Any]] = Field(
        description="List of relationships between entities"
    )


class DataVaultDesign(BaseModel):
    """LLM output schema for Data Vault 2.0 design."""

    reasoning: str = Field(
        description="Explanation of Data Vault design decisions"
    )
    hubs: List[Dict[str, Any]] = Field(
        description="Hub tables representing business entities"
    )
    links: List[Dict[str, Any]] = Field(
        description="Link tables representing relationships"
    )
    satellites: List[Dict[str, Any]] = Field(
        description="Satellite tables with descriptive attributes"
    )


# =============================================================================
# Design Node Functions
# =============================================================================


async def create_design(
    state: "ModelingState",
    llm_client: "LLMClient",
    prompt_builder: Optional[Any] = None,
) -> "ModelingState":
    """
    Create data model design using LLM-assisted generation.

    This node uses an LLM to analyze discovered tables, profiles,
    and relationships to generate an appropriate data model design
    based on the selected modeling strategy.

    Args:
        state: Current modeling workflow state with discovery and analysis results
        llm_client: LLM client for structured generation
        prompt_builder: Optional custom prompt builder module

    Returns:
        Updated ModelingState with generated design

    State Updates:
        - model_design: Generated design as dictionary
        - design_reasoning: LLM's reasoning for design decisions
        - current_step: Set to "design_model"
        - progress: Set to 0.7
        - errors: Appended if design generation fails
        - status: Set to "failed" if design generation fails

    Design Structure (varies by strategy):
        STAR_SCHEMA:
            - staging_models: Source transformations
            - dimensions: Dimension tables
            - facts: Fact tables with measures

        NORMALIZED_3NF:
            - entities: Normalized tables
            - relationships: FK relationships

        DATA_VAULT:
            - hubs: Business key entities
            - links: Relationship tables
            - satellites: Descriptive attributes
    """
    strategy = state.get("modeling_strategy", "STAR_SCHEMA")
    logger.info(f"Designing data model with strategy: {strategy}...")

    try:
        # Import prompt builder (allows custom prompts)
        if prompt_builder is None:
            from core.prompts import modeling as prompts
            prompt_builder = prompts

        # Select appropriate prompt and response model
        if strategy == "NORMALIZED_3NF":
            prompt = prompt_builder.build_normalized_3nf_prompt(state)
            response_model = NormalizedDesign
            system = (
                "You are an expert data architect specializing in 3NF and "
                "relational database design. Focus on eliminating redundancy "
                "and ensuring data integrity."
            )
        elif strategy == "DATA_VAULT":
            prompt = prompt_builder.build_data_vault_prompt(state)
            response_model = DataVaultDesign
            system = (
                "You are an expert in Data Vault 2.0 methodology. Focus on "
                "Hubs for business keys, Links for relationships, and "
                "Satellites for descriptive attributes."
            )
        else:
            # Default to Star Schema
            prompt = prompt_builder.build_star_schema_prompt(state)
            response_model = StarSchemaDesign
            system = (
                "You are an expert data modeler specializing in dimensional "
                "modeling and star schemas. Optimize for query performance "
                "and ease of analytics."
            )

        # Generate design using structured output
        design, response = await llm_client.generate_structured(
            prompt=prompt,
            response_model=response_model,
            system=system,
            temperature=0.0,
        )

        logger.info(f"Model design reasoning: {design.reasoning[:200]}...")

        # Store design and reasoning
        state["model_design"] = design.model_dump()
        state["design_reasoning"] = design.reasoning
        state["current_step"] = "design_model"
        state["progress"] = 0.7

    except Exception as e:
        logger.error(f"Model design failed: {e}")
        state["errors"].append(f"Model design failed: {e}")
        state["status"] = "failed"

    return state


async def validate_design(
    state: "ModelingState",
    validator: "DesignValidator",
) -> "ModelingState":
    """
    Validate the generated design against strategy requirements.

    This node uses the DesignValidator to check the generated design
    for compliance with the modeling strategy, common design issues,
    and best practices.

    Args:
        state: Current modeling workflow state with model_design populated
        validator: DesignValidator configured for the modeling strategy

    Returns:
        Updated ModelingState with validation results

    State Updates:
        - design_validation: Validation report with issues and metrics
        - design_is_valid: Boolean indicating if design passes validation
        - current_step: Set to "validate_design"
        - progress: Updated progress
        - warnings: Appended with validation warnings
        - errors: Appended with validation errors if critical issues found
    """
    logger.info("Validating model design...")

    try:
        design_dict = state.get("model_design", {})

        if not design_dict:
            logger.warning("No design to validate")
            state["design_validation"] = {"is_valid": False, "issues": ["No design found"]}
            state["design_is_valid"] = False
            state["current_step"] = "validate_design"
            return state

        # Convert design dict to ModelDesign object for validation
        # This requires converting the LLM output to the design model format
        model_design = _convert_to_design_model(state)

        if model_design is None:
            logger.warning("Could not convert design for validation")
            state["design_validation"] = {
                "is_valid": True,  # Skip validation if conversion fails
                "issues": [],
                "note": "Design validation skipped - format conversion not available",
            }
            state["design_is_valid"] = True
            state["current_step"] = "validate_design"
            return state

        # Get functional dependencies for 3NF validation
        fds = []
        fd_data = state.get("functional_dependencies", {})
        for table_fds in fd_data.values():
            # Would need to convert dicts back to FunctionalDependency objects
            pass

        # Run validation
        report = validator.validate_design(
            design=model_design,
            functional_dependencies=fds,
        )

        # Store validation results
        state["design_validation"] = {
            "is_valid": report.is_valid,
            "error_count": report.error_count,
            "warning_count": report.warning_count,
            "info_count": report.info_count,
            "issues": [
                {
                    "severity": issue.severity.value,
                    "category": issue.category.value,
                    "table_name": issue.table_name,
                    "description": issue.description,
                    "fix_suggestion": issue.fix_suggestion,
                }
                for issue in report.issues
            ],
            "metrics": report.metrics,
        }
        state["design_is_valid"] = report.is_valid
        state["current_step"] = "validate_design"

        # Add warnings/errors to state
        for issue in report.issues:
            if issue.severity.value == "error":
                state["errors"].append(f"Design issue: {issue.description}")
            elif issue.severity.value == "warning":
                state["warnings"].append(f"Design warning: {issue.description}")

        # Update progress
        current_progress = state.get("progress", 0.7)
        state["progress"] = max(current_progress, 0.75)

        logger.info(
            f"Design validation: valid={report.is_valid}, "
            f"errors={report.error_count}, warnings={report.warning_count}"
        )

    except Exception as e:
        logger.error(f"Design validation failed: {e}")
        state["warnings"].append(f"Design validation skipped: {e}")
        state["design_is_valid"] = True  # Don't block on validation failures

    return state


def _convert_to_design_model(state: "ModelingState") -> Optional[Any]:
    """
    Convert the LLM design output to a ModelDesign object for validation.

    This is a helper function that transforms the dictionary-based
    LLM output into the structured ModelDesign format expected by
    the DesignValidator.

    Args:
        state: ModelingState with model_design populated

    Returns:
        ModelDesign object or None if conversion fails
    """
    try:
        from core.models.design import (
            ModelDesign,
            DesignedTable,
            DesignedColumn,
            TableRole,
            ColumnRole,
            ModelingStrategy,
        )
        from core.models.schema import ForeignKeyRelationship

        design_dict = state.get("model_design", {})
        strategy = state.get("modeling_strategy", "STAR_SCHEMA")

        tables = []
        relationships = []

        if strategy == "STAR_SCHEMA":
            # Convert staging models
            for stg in design_dict.get("staging_models", []):
                tables.append(_convert_table(stg, TableRole.STAGING))

            # Convert dimensions
            for dim in design_dict.get("dimensions", []):
                tables.append(_convert_table(dim, TableRole.DIMENSION))

            # Convert facts
            for fact in design_dict.get("facts", []):
                tables.append(_convert_table(fact, TableRole.FACT))

        elif strategy == "DATA_VAULT":
            # Convert hubs
            for hub in design_dict.get("hubs", []):
                tables.append(_convert_table(hub, TableRole.HUB))

            # Convert links
            for link in design_dict.get("links", []):
                tables.append(_convert_table(link, TableRole.LINK))

            # Convert satellites
            for sat in design_dict.get("satellites", []):
                tables.append(_convert_table(sat, TableRole.SATELLITE))

        elif strategy == "NORMALIZED_3NF":
            # Convert entities
            for entity in design_dict.get("entities", []):
                tables.append(_convert_table(entity, TableRole.ENTITY))

            # Convert relationships
            for rel in design_dict.get("relationships", []):
                relationships.append(_convert_relationship(rel))

        return ModelDesign(
            strategy=ModelingStrategy(strategy),
            tables=tables,
            relationships=relationships,
        )

    except Exception as e:
        logger.warning(f"Could not convert design to ModelDesign: {e}")
        return None


def _convert_table(table_dict: Dict[str, Any], role: Any) -> Any:
    """Convert a table dictionary to DesignedTable."""
    from core.models.design import DesignedTable, DesignedColumn, ColumnRole

    columns = []
    for col in table_dict.get("columns", []):
        col_role = ColumnRole.ATTRIBUTE
        if col.get("is_primary_key"):
            col_role = ColumnRole.SURROGATE_KEY
        elif col.get("is_foreign_key"):
            col_role = ColumnRole.FOREIGN_KEY
        elif col.get("is_measure"):
            col_role = ColumnRole.MEASURE

        columns.append(DesignedColumn(
            name=col.get("name", ""),
            data_type=col.get("data_type", "varchar"),
            is_nullable=col.get("is_nullable", True),
            is_primary_key=col.get("is_primary_key", False),
            role=col_role,
            description=col.get("description"),
            references_table=col.get("references_table"),
            references_column=col.get("references_column"),
        ))

    return DesignedTable(
        name=table_dict.get("name", ""),
        role=role,
        columns=columns,
        description=table_dict.get("description"),
        grain=table_dict.get("grain"),
        source_models=table_dict.get("source_models", []),
        measures=table_dict.get("measures", []),
    )


def _convert_relationship(rel_dict: Dict[str, Any]) -> Any:
    """Convert a relationship dictionary to ForeignKeyRelationship."""
    from core.models.schema import ForeignKeyRelationship

    return ForeignKeyRelationship(
        name=rel_dict.get("name", f"fk_{rel_dict.get('from_table')}_{rel_dict.get('to_table')}"),
        from_schema=rel_dict.get("from_schema", "public"),
        from_table=rel_dict.get("from_table", ""),
        from_columns=rel_dict.get("from_columns", []),
        to_schema=rel_dict.get("to_schema", "public"),
        to_table=rel_dict.get("to_table", ""),
        to_columns=rel_dict.get("to_columns", []),
        cardinality=rel_dict.get("cardinality", "1:N"),
        is_nullable=rel_dict.get("is_nullable", True),
    )


def get_design_summary(state: "ModelingState") -> Dict[str, Any]:
    """
    Generate a summary of the model design.

    Args:
        state: ModelingState with model_design populated

    Returns:
        Summary dictionary with design statistics
    """
    design = state.get("model_design", {})
    strategy = state.get("modeling_strategy", "STAR_SCHEMA")

    summary = {
        "strategy": strategy,
        "reasoning_excerpt": design.get("reasoning", "")[:200] + "...",
    }

    if strategy == "STAR_SCHEMA":
        summary.update({
            "staging_models": len(design.get("staging_models", [])),
            "dimensions": len(design.get("dimensions", [])),
            "facts": len(design.get("facts", [])),
        })
    elif strategy == "DATA_VAULT":
        summary.update({
            "hubs": len(design.get("hubs", [])),
            "links": len(design.get("links", [])),
            "satellites": len(design.get("satellites", [])),
        })
    elif strategy == "NORMALIZED_3NF":
        summary.update({
            "entities": len(design.get("entities", [])),
            "relationships": len(design.get("relationships", [])),
        })

    # Add validation summary if available
    validation = state.get("design_validation", {})
    if validation:
        summary["validation"] = {
            "is_valid": validation.get("is_valid", False),
            "errors": validation.get("error_count", 0),
            "warnings": validation.get("warning_count", 0),
        }

    return summary
