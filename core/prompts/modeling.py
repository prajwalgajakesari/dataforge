"""
Prompts for data modeling strategies.
"""

from typing import Dict, Any, List

def build_star_schema_prompt(state: Dict[str, Any]) -> str:
    """Build prompt for Star Schema design."""
    prompt = f"""Design a star schema data model based on the following information:

## User Requirements
{state['requirements']}

## Available Tables
"""
    prompt += _format_tables(state["discovered_tables"])
    prompt += _format_profiles(state.get("data_profiles"))

    prompt += """

## Task
Design a complete star schema with:

1. **Staging Models**: One per source table, with basic cleanup and renaming
2. **Dimension Models**: Business entities (customers, products, dates, etc.)
3. **Fact Models**: Business events/transactions with measures and foreign keys to dimensions

For each model, specify:
- name: Model name (without prefix)
- source_models: List of upstream models
- columns: List of columns with name, data_type, description, is_primary_key, is_nullable
- description: What this model represents

For fact models, also specify:
- grain: The level of detail (e.g., "one row per order")
- measures: List of numeric columns for aggregation
- dimensions: List of dimension foreign keys

Consider:
- Data relationships and foreign keys
- Slowly changing dimensions (use type 1 for now)
- Appropriate grain for facts
- Clear, business-friendly naming

Return your design as structured JSON.
"""
    return prompt

def build_normalized_3nf_prompt(state: Dict[str, Any]) -> str:
    """Build prompt for Normalized (3NF) design."""
    prompt = f"""Design a Normalized (3NF) data model based on the following information:

## User Requirements
{state['requirements']}

## Available Tables
"""
    prompt += _format_tables(state["discovered_tables"])
    prompt += _format_profiles(state.get("data_profiles"))

    prompt += """

## Task
Design a highly normalized (3NF) relational schema that eliminates redundancy and ensures data integrity.

1. **Entities**: Identify core business entities and their attributes. Break down complex objects into atomic tables.
2. **Relationships**: Define strict 1:1, 1:N, or M:N relationships using foreign keys.
3. **Normalization**:
    - Ensure atomic values (1NF).
    - Remove partial dependencies (2NF).
    - Remove transitive dependencies (3NF).

For each table, specify:
- name: Table name (snake_case)
- columns: List of columns with strict data types and constraints
- primary_key: Column(s) forming the PK
- foreign_keys: List of relationships to other tables

Return your design as structured JSON.
"""
    return prompt

def build_data_vault_prompt(state: Dict[str, Any]) -> str:
    """Build prompt for Data Vault 2.0 design."""
    prompt = f"""Design a Data Vault 2.0 model based on the following information:

## User Requirements
{state['requirements']}

## Available Tables
"""
    prompt += _format_tables(state["discovered_tables"])
    prompt += _format_profiles(state.get("data_profiles"))

    prompt += """

## Task
Design a Data Vault 2.0 raw vault schema.

1. **Hubs**: Business keys (e.g., Customer ID, Order ID). Contains Hash Key, Load Date, Record Source, Business Key.
2. **Links**: Relationships/Associations between Hubs. Contains Hash Key, Load Date, Record Source, and Foreign Hash Keys.
3. **Satellites**: Descriptive attributes for Hubs or Links. Contains Hash Key, Load Date, Record Source, Hash Diff, and attributes.

For each entity type (Hub, Link, Sat), specify:
- name: Model name (snake_case, e.g., hub_customer)
- type: 'hub', 'link', or 'sat'
- business_keys: List of columns (for Hubs)
- foreign_keys: List of Hub hash keys (for Links)
- attributes: List of descriptive columns (for Sats)

Return your design as structured JSON.
"""
    return prompt

def _format_tables(tables: List[Dict[str, Any]]) -> str:
    """Format table info for prompts."""
    output = ""
    for table in tables:
        output += f"\n### {table['name']} ({table.get('row_count', 'unknown')} rows)\n"
        output += "Columns:\n"
        for col in table["columns"][:15]:  # Extended to 15 columns
            pk_marker = " (PK)" if col["is_primary_key"] else ""
            fk_marker = (
                f" (FK -> {col['foreign_key_table']})" if col["is_foreign_key"] else ""
            )
            output += f"- {col['name']}: {col['data_type']}{pk_marker}{fk_marker}\n"
    return output

def _format_profiles(profiles: Dict[str, Any]) -> str:
    """Format data profiles for prompts."""
    if not profiles:
        return ""
    
    output = "\n## Data Profiles\n"
    for table_name, table_profiles in list(profiles.items())[:3]:
        output += f"\n### {table_name}\n"
        for profile in table_profiles[:5]:
            output += f"- {profile['column_name']}: {profile['null_percentage']}% null"
            if profile.get("distinct_count"):
                output += f", {profile['distinct_count']} distinct values"
            output += "\n"
    return output
