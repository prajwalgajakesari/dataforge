"""
Comprehensive prompts for data modeling strategies.

This module provides detailed prompts for all phases of data modeling:
- Schema Discovery: Selecting relevant schemas and tables
- Analysis: Profiling summaries, relationship inference, key recommendations
- Design: Star schema, normalized 3NF, and Data Vault modeling
- Validation: Design review and fix suggestions
- Generation: DDL, dbt models, and documentation

Each prompt is designed to work with structured LLM outputs and
references the domain models defined in core/models/.
"""

from typing import Any, Dict, List, Optional

# Import models for type hints in helper functions
# These are imported conditionally to avoid circular imports
try:
    from core.models.schema import Table, Column
    from core.models.analysis import (
        TableProfile,
        FunctionalDependency,
        CandidateKey,
        ColumnStatistics,
    )
except ImportError:
    # Models may not be available in all contexts
    Table = Any
    Column = Any
    TableProfile = Any
    FunctionalDependency = Any
    CandidateKey = Any
    ColumnStatistics = Any


# =============================================================================
# SCHEMA DISCOVERY PROMPTS
# =============================================================================

SCHEMA_SELECTION_PROMPT = """You are a data modeling expert helping to identify relevant database schemas for analysis.

## Context
The user has provided requirements for building a data model. Multiple database schemas are available, and you need to help identify which schemas contain data relevant to the requirements.

## User Requirements
{requirements}

## Available Schemas
{schemas}

## Task
Analyze the available schemas and determine which ones are most relevant to the user's requirements. Consider:

1. **Direct Relevance**: Schemas that directly contain tables matching the business domain (e.g., "sales" schema for sales analytics)
2. **Supporting Data**: Schemas that provide reference data, lookup tables, or supporting entities
3. **Exclusions**: Schemas that are clearly irrelevant (e.g., system schemas, unrelated domains)

For each relevant schema, explain:
- Why it's relevant to the requirements
- What types of data it likely contains
- Priority level (high/medium/low)

## Output Format
Return your analysis as JSON with this structure:
```json
{{
    "selected_schemas": [
        {{
            "schema_name": "string",
            "relevance_reason": "string",
            "priority": "high|medium|low",
            "expected_data_types": ["list", "of", "data", "types"]
        }}
    ],
    "excluded_schemas": [
        {{
            "schema_name": "string",
            "exclusion_reason": "string"
        }}
    ],
    "recommendations": "Overall recommendations for schema selection"
}}
```
"""

TABLE_RELEVANCE_PROMPT = """You are a data modeling expert helping to identify tables relevant to specific analytical requirements.

## Context
The user wants to build a data model for specific analytical purposes. You need to identify which tables from the available schemas are relevant and how they should be used.

## User Requirements
{requirements}

## Available Tables
{tables_context}

## Task
Analyze each table and determine its relevance to the requirements. For each table, consider:

1. **Primary Purpose**: Is this a core table for the analysis or a supporting reference table?
2. **Data Content**: Based on column names and types, what business entities does it represent?
3. **Relationships**: How might this table relate to other tables? (Look for _id columns, naming patterns)
4. **Data Volume**: Consider row counts when assessing importance and join strategies
5. **Usage Pattern**: Will this be a fact table, dimension table, or excluded?

Classify tables into:
- **Core Tables**: Essential for the analysis, likely to become facts or key dimensions
- **Reference Tables**: Lookup/reference data for enrichment
- **Excluded Tables**: Not relevant to the requirements

## Output Format
Return your analysis as JSON:
```json
{{
    "core_tables": [
        {{
            "table_name": "string",
            "schema_name": "string",
            "purpose": "string",
            "likely_role": "fact|dimension|bridge",
            "key_columns": ["list", "of", "important", "columns"],
            "relevance_score": 0.0-1.0
        }}
    ],
    "reference_tables": [
        {{
            "table_name": "string",
            "schema_name": "string",
            "purpose": "string",
            "linked_to": ["list", "of", "core", "tables"],
            "relevance_score": 0.0-1.0
        }}
    ],
    "excluded_tables": [
        {{
            "table_name": "string",
            "exclusion_reason": "string"
        }}
    ],
    "relationship_hints": [
        {{
            "from_table": "string",
            "to_table": "string",
            "relationship_type": "string",
            "join_columns": "string"
        }}
    ]
}}
```
"""


# =============================================================================
# ANALYSIS PROMPTS
# =============================================================================

DATA_PROFILING_SUMMARY_PROMPT = """You are a data quality analyst summarizing profiling results for a data modeling project.

## Context
Data profiling has been completed on the source tables. You need to synthesize the results into actionable insights for the data modeling team.

## User Requirements
{requirements}

## Profiling Results
{profile_context}

## Task
Analyze the profiling results and provide a comprehensive summary covering:

1. **Data Quality Assessment**
   - Overall quality score across tables
   - Tables with significant data quality issues
   - Columns with high null percentages (>20%)
   - Columns with low cardinality that might be enums/categories
   - Columns with uniqueness issues

2. **Pattern Detection**
   - Columns containing emails, phones, dates stored as strings
   - Columns that appear to be codes or identifiers
   - Columns with consistent patterns (semantic types)

3. **Statistical Insights**
   - Numeric columns suitable for measures (aggregations)
   - Text columns suitable for dimensions
   - Date/time columns for time-based analysis
   - Potential outliers or anomalies

4. **Key Candidates**
   - Columns that appear to be primary keys (unique, not null)
   - Columns that appear to be foreign keys (naming patterns, value distributions)
   - Composite key candidates

5. **Recommendations**
   - Data cleaning requirements before modeling
   - Columns that need type conversion
   - Potential data quality rules to implement

## Output Format
Return your analysis as JSON:
```json
{{
    "overall_quality_score": 0.0-100.0,
    "table_summaries": [
        {{
            "table_name": "string",
            "quality_score": 0.0-100.0,
            "row_count": 0,
            "key_findings": ["list", "of", "findings"],
            "quality_issues": ["list", "of", "issues"],
            "recommended_role": "fact|dimension|staging"
        }}
    ],
    "quality_issues": [
        {{
            "table_name": "string",
            "column_name": "string",
            "issue_type": "high_nulls|low_cardinality|inconsistent_format|outliers",
            "severity": "high|medium|low",
            "description": "string",
            "recommendation": "string"
        }}
    ],
    "semantic_types_detected": [
        {{
            "table_name": "string",
            "column_name": "string",
            "detected_type": "email|phone|date|uuid|currency|etc",
            "confidence": 0.0-1.0
        }}
    ],
    "key_candidates": [
        {{
            "table_name": "string",
            "columns": ["list"],
            "key_type": "primary|natural|foreign",
            "confidence": 0.0-1.0,
            "reasoning": "string"
        }}
    ],
    "measure_candidates": [
        {{
            "table_name": "string",
            "column_name": "string",
            "data_type": "string",
            "suggested_aggregations": ["sum", "avg", "count"]
        }}
    ],
    "cleaning_recommendations": ["list", "of", "recommendations"]
}}
```
"""

RELATIONSHIP_INFERENCE_PROMPT = """You are a data modeling expert inferring relationships between tables based on analysis results.

## Context
You have analyzed source tables and need to infer the relationships between them for building a data model. Use column names, data types, value distributions, and foreign key hints to identify relationships.

## User Requirements
{requirements}

## Tables and Analysis
{tables_context}

## Analysis Results
{analysis_context}

## Task
Infer relationships between tables by analyzing:

1. **Explicit Foreign Keys**: Any declared FK constraints
2. **Naming Conventions**: Columns ending in _id, _key, _code that match other table names
3. **Value Overlap**: Columns with similar value distributions across tables
4. **Data Types**: Matching data types that suggest relationships
5. **Cardinality**: Determine 1:1, 1:N, or N:M based on distinct counts

For each relationship, determine:
- The relationship direction (which table references which)
- Cardinality (1:1, 1:N, N:M)
- Whether it's required (based on null percentages)
- Confidence level in the inference

Consider both:
- Direct relationships (explicit FKs or clear naming matches)
- Inferred relationships (semantic similarity, value overlap)

## Output Format
Return your analysis as JSON:
```json
{{
    "relationships": [
        {{
            "relationship_name": "string",
            "from_table": "string",
            "from_column": "string",
            "to_table": "string",
            "to_column": "string",
            "cardinality": "1:1|1:N|N:1|N:M",
            "is_required": true|false,
            "inference_type": "explicit_fk|naming_convention|value_overlap|semantic",
            "confidence": 0.0-1.0,
            "evidence": "string explaining why this relationship was inferred"
        }}
    ],
    "table_graph": {{
        "central_tables": ["list of tables with most relationships"],
        "leaf_tables": ["list of tables with few/no outgoing relationships"],
        "bridge_tables": ["list of tables connecting other tables (M:N)"]
    }},
    "potential_issues": [
        {{
            "issue": "string",
            "affected_tables": ["list"],
            "recommendation": "string"
        }}
    ],
    "relationship_summary": "Natural language summary of the data model structure"
}}
```
"""

KEY_RECOMMENDATION_PROMPT = """You are a data modeling expert recommending primary and foreign key structures for a data model.

## Context
Based on table analysis and functional dependency discovery, you need to recommend the optimal key structures for each table in the data model.

## User Requirements
{requirements}

## Tables
{tables_context}

## Functional Dependencies Discovered
{fd_context}

## Candidate Keys Discovered
{key_context}

## Task
For each table, recommend the optimal key structure considering:

1. **Primary Key Selection**
   - Prefer single-column keys over composite keys when possible
   - Prefer integer/bigint surrogate keys for fact tables
   - Prefer natural keys for small dimension/lookup tables
   - Consider stability (values that don't change)
   - Consider uniqueness and null handling

2. **Surrogate Key Recommendations**
   - When to use surrogate keys vs natural keys
   - Naming conventions (id, _sk suffix for surrogate keys)
   - Data type recommendations (bigint, uuid)

3. **Foreign Key Recommendations**
   - Which columns should reference which tables
   - Referential integrity considerations
   - Cascade vs restrict on delete/update

4. **Composite Key Analysis**
   - When composite keys are appropriate
   - Breaking down composite natural keys into surrogates

## Output Format
Return your recommendations as JSON:
```json
{{
    "table_key_recommendations": [
        {{
            "table_name": "string",
            "primary_key": {{
                "columns": ["list"],
                "key_type": "surrogate|natural|composite",
                "data_type": "bigint|uuid|varchar",
                "recommendation_reason": "string"
            }},
            "alternate_keys": [
                {{
                    "columns": ["list"],
                    "purpose": "string"
                }}
            ],
            "foreign_keys": [
                {{
                    "columns": ["list"],
                    "references_table": "string",
                    "references_columns": ["list"],
                    "on_delete": "CASCADE|RESTRICT|SET NULL",
                    "on_update": "CASCADE|RESTRICT",
                    "is_required": true|false
                }}
            ],
            "unique_constraints": [
                {{
                    "columns": ["list"],
                    "purpose": "string"
                }}
            ]
        }}
    ],
    "surrogate_key_strategy": {{
        "recommended_type": "bigint|uuid",
        "naming_convention": "string",
        "generation_method": "sequence|uuid_generate_v4|identity"
    }},
    "normalization_notes": ["list of notes about key implications for normalization"],
    "warnings": ["list of potential issues or considerations"]
}}
```
"""


# =============================================================================
# DESIGN PROMPTS
# =============================================================================

STAR_SCHEMA_DESIGN_PROMPT = """You are an expert data architect designing a star schema data model optimized for analytical queries and business intelligence.

## Context
You are designing a star schema (dimensional model) that will serve as the foundation for a data warehouse or data mart. The star schema should optimize query performance for analytical workloads while maintaining data integrity and ease of understanding for business users.

## User Requirements
{requirements}

## Available Source Tables
{tables_context}

## Data Profiles
{profile_context}

## Analysis Results
{analysis_context}

## Star Schema Design Principles

### Fact Table Design
1. **Identify Transactional Data**: Facts represent business events or transactions (orders, payments, clicks, etc.)
2. **Define the Grain**: The grain is the most atomic level of detail. Each row should represent exactly one occurrence of the grain (e.g., "one row per order line item")
3. **Select Measures**: Identify numeric, additive columns suitable for aggregation (amounts, quantities, counts)
4. **Measure Types**:
   - Additive: Can be summed across all dimensions (revenue, quantity)
   - Semi-additive: Can be summed across some dimensions (account balance - not across time)
   - Non-additive: Cannot be summed (ratios, percentages - must be calculated from additive components)
5. **Foreign Keys**: Include one foreign key to each relevant dimension
6. **Degenerate Dimensions**: Include transaction identifiers (order_number) directly in the fact table

### Dimension Table Design
1. **Identify Descriptive Entities**: Dimensions provide context for facts (who, what, where, when, how)
2. **Surrogate Keys**: Use integer surrogate keys as primary keys (dim_customer_key, not customer_id)
3. **Natural Keys**: Preserve the original business key as a separate column
4. **Denormalization**: Flatten hierarchies into the dimension table for query performance
5. **Slowly Changing Dimensions (SCD)**:
   - **Type 0**: Fixed attributes that never change (birth date)
   - **Type 1**: Overwrite old values, no history (address corrections)
   - **Type 2**: Add new rows with version tracking (track full history with effective_date, expiry_date, is_current)
   - **Type 3**: Add columns for previous values (current_city, previous_city)
6. **Date Dimension**: Always create a comprehensive date dimension with fiscal calendars, holidays, etc.
7. **Junk Dimensions**: Combine low-cardinality flags and indicators into a single dimension

### Bridge Tables
1. **Many-to-Many Relationships**: Create bridge tables to handle M:N relationships
2. **Weighting Factors**: Include allocation percentages when needed

## Design Requirements

Design a complete star schema including:

1. **Staging Models**: One per source table with:
   - Basic data type casting
   - Column renaming to business-friendly names
   - Null handling
   - Source system reference (source_system, load_timestamp)

2. **Dimension Tables** (prefix with `dim_`):
   - Surrogate key (bigint, primary key)
   - Natural key (original business key)
   - Descriptive attributes (denormalized)
   - SCD columns if Type 2 (effective_date, expiry_date, is_current)
   - Audit columns (created_at, updated_at)

3. **Fact Tables** (prefix with `fact_`):
   - Surrogate key (bigint, primary key)
   - Foreign keys to all related dimensions
   - Degenerate dimensions (transaction IDs)
   - Measures (numeric values for aggregation)
   - Audit columns (created_at, source_system)

4. **Bridge Tables** (prefix with `bridge_`):
   - For any M:N relationships between facts and dimensions

## Output Format
Return your design as JSON with this structure:
```json
{{
    "model_name": "string",
    "strategy": "star_schema",
    "design_notes": "Overall design rationale",
    "assumptions": ["list", "of", "assumptions", "made"],
    "warnings": ["list", "of", "caveats", "or", "concerns"],
    "staging_models": [
        {{
            "name": "stg_source_table_name",
            "source_tables": ["source_table"],
            "description": "Staging layer for source_table",
            "columns": [
                {{
                    "name": "column_name",
                    "source_column": "original_name",
                    "data_type": "varchar|integer|timestamp|etc",
                    "transformation": "SQL expression or null",
                    "description": "Business description"
                }}
            ]
        }}
    ],
    "dimensions": [
        {{
            "name": "dim_entity_name",
            "source_tables": ["list", "of", "sources"],
            "description": "Dimension description",
            "scd_type": 0|1|2|3,
            "columns": [
                {{
                    "name": "dim_entity_key",
                    "data_type": "bigint",
                    "role": "surrogate_key",
                    "is_primary_key": true,
                    "is_nullable": false,
                    "description": "Surrogate key"
                }},
                {{
                    "name": "entity_id",
                    "data_type": "varchar",
                    "role": "natural_key",
                    "is_nullable": false,
                    "description": "Original business key"
                }}
            ],
            "unique_constraints": [["entity_id"]],
            "indexes": ["entity_id"]
        }}
    ],
    "facts": [
        {{
            "name": "fact_business_event",
            "source_tables": ["list", "of", "sources"],
            "description": "Fact table description",
            "grain": "one row per specific event",
            "columns": [
                {{
                    "name": "fact_event_key",
                    "data_type": "bigint",
                    "role": "surrogate_key",
                    "is_primary_key": true,
                    "description": "Surrogate key"
                }},
                {{
                    "name": "dim_customer_key",
                    "data_type": "bigint",
                    "role": "foreign_key",
                    "references_table": "dim_customer",
                    "references_column": "dim_customer_key",
                    "description": "Customer dimension FK"
                }}
            ],
            "measures": [
                {{
                    "name": "order_amount",
                    "data_type": "numeric(18,2)",
                    "aggregation_type": "additive",
                    "description": "Order total amount"
                }}
            ],
            "dimension_keys": ["dim_customer_key", "dim_product_key", "dim_date_key"],
            "degenerate_dimensions": ["order_number"],
            "indexes": ["dim_date_key", "dim_customer_key"]
        }}
    ],
    "bridges": [
        {{
            "name": "bridge_order_promotion",
            "fact_table": "fact_orders",
            "dimension_table": "dim_promotion",
            "description": "Many promotions per order",
            "columns": [
                {{
                    "name": "fact_order_key",
                    "data_type": "bigint",
                    "role": "foreign_key"
                }},
                {{
                    "name": "dim_promotion_key",
                    "data_type": "bigint",
                    "role": "foreign_key"
                }},
                {{
                    "name": "allocation_factor",
                    "data_type": "numeric(5,4)",
                    "description": "Weighting factor for allocation"
                }}
            ]
        }}
    ],
    "relationships": [
        {{
            "name": "fact_orders_to_dim_customer",
            "from_table": "fact_orders",
            "from_columns": ["dim_customer_key"],
            "to_table": "dim_customer",
            "to_columns": ["dim_customer_key"],
            "cardinality": "N:1",
            "is_required": true
        }}
    ],
    "date_dimension_config": {{
        "include_fiscal_calendar": true,
        "fiscal_year_start_month": 1,
        "include_holidays": true,
        "holiday_country": "US",
        "date_range_start": "2020-01-01",
        "date_range_end": "2030-12-31"
    }}
}}
```
"""

NORMALIZED_3NF_DESIGN_PROMPT = """You are an expert data architect designing a fully normalized (Third Normal Form) relational data model optimized for data integrity, minimal redundancy, and transactional operations.

## Context
You are designing a 3NF (Third Normal Form) normalized schema that eliminates data redundancy and ensures data integrity through proper normalization. This design is ideal for OLTP systems, operational data stores, or as a staging area before dimensional modeling.

## User Requirements
{requirements}

## Available Source Tables
{tables_context}

## Data Profiles
{profile_context}

## Analysis Results (Functional Dependencies)
{analysis_context}

## Normalization Principles

### First Normal Form (1NF)
1. **Atomic Values**: Each column contains only atomic (indivisible) values
2. **No Repeating Groups**: No arrays or lists within a single column
3. **Unique Rows**: Each row is unique (has a primary key)

### Second Normal Form (2NF)
1. **Must be in 1NF**
2. **No Partial Dependencies**: Every non-key attribute must depend on the entire primary key
3. **For composite keys**: All attributes must depend on ALL columns of the key, not just some

### Third Normal Form (3NF)
1. **Must be in 2NF**
2. **No Transitive Dependencies**: Non-key attributes cannot depend on other non-key attributes
3. **Every attribute depends on "the key, the whole key, and nothing but the key"**

### Identifying Normalization Violations

**Partial Dependency Example (2NF violation)**:
- Table: OrderDetails(OrderID, ProductID, ProductName, Quantity)
- ProductName depends only on ProductID, not on the full key (OrderID, ProductID)
- Fix: Move ProductName to a separate Products table

**Transitive Dependency Example (3NF violation)**:
- Table: Employee(EmployeeID, DepartmentID, DepartmentName, DepartmentManager)
- DepartmentName depends on DepartmentID, not directly on EmployeeID
- Fix: Move DepartmentName to a separate Departments table

## Design Requirements

Analyze the source tables and design a fully normalized 3NF schema:

1. **Identify Functional Dependencies**: From the analysis results, identify all FDs
2. **Decompose Tables**: Break down tables to eliminate redundancy
3. **Preserve Dependencies**: Ensure all functional dependencies are preserved
4. **Create Junction Tables**: For many-to-many relationships

For each table, specify:

1. **Entity Tables** (core business entities):
   - Primary key (prefer natural keys where stable, surrogate where not)
   - All attributes that depend fully on the primary key
   - Foreign keys to related entities
   - Constraints (NOT NULL, UNIQUE, CHECK)

2. **Junction/Association Tables** (for M:N relationships):
   - Composite primary key from both foreign keys
   - Any relationship attributes
   - Indexes for both foreign keys

3. **Lookup/Reference Tables** (for controlled vocabularies):
   - Simple primary key
   - Name/description columns
   - Active/inactive flags if applicable

## Output Format
Return your design as JSON:
```json
{{
    "model_name": "string",
    "strategy": "normalized_3nf",
    "design_notes": "Overall design rationale and normalization decisions",
    "assumptions": ["list of assumptions"],
    "warnings": ["list of potential issues"],
    "functional_dependencies_addressed": [
        {{
            "original_table": "string",
            "fd": "A, B -> C, D",
            "violation_type": "partial|transitive|none",
            "resolution": "Description of how it was resolved"
        }}
    ],
    "entities": [
        {{
            "name": "entity_name",
            "description": "Business purpose of this entity",
            "source_tables": ["list", "of", "source", "tables"],
            "columns": [
                {{
                    "name": "column_name",
                    "data_type": "varchar(100)|integer|timestamp|etc",
                    "is_primary_key": true|false,
                    "is_nullable": false|true,
                    "is_unique": false|true,
                    "default_value": "value or null",
                    "check_constraint": "SQL expression or null",
                    "description": "Business description"
                }}
            ],
            "primary_key": ["column_names"],
            "unique_constraints": [
                {{
                    "name": "uq_entity_field",
                    "columns": ["column_names"]
                }}
            ],
            "check_constraints": [
                {{
                    "name": "chk_entity_rule",
                    "expression": "SQL expression"
                }}
            ],
            "indexes": [
                {{
                    "name": "idx_entity_field",
                    "columns": ["column_names"],
                    "is_unique": false
                }}
            ]
        }}
    ],
    "junction_tables": [
        {{
            "name": "entity1_entity2",
            "description": "Links entity1 to entity2 (M:N)",
            "entity1": "entity1_name",
            "entity2": "entity2_name",
            "columns": [
                {{
                    "name": "entity1_id",
                    "data_type": "integer",
                    "is_primary_key": true,
                    "references_table": "entity1",
                    "references_column": "id"
                }},
                {{
                    "name": "entity2_id",
                    "data_type": "integer",
                    "is_primary_key": true,
                    "references_table": "entity2",
                    "references_column": "id"
                }}
            ],
            "relationship_attributes": [
                {{
                    "name": "attribute_name",
                    "data_type": "type",
                    "description": "Attribute of the relationship"
                }}
            ]
        }}
    ],
    "lookup_tables": [
        {{
            "name": "lookup_name",
            "description": "Reference data for X",
            "columns": [
                {{
                    "name": "code",
                    "data_type": "varchar(10)",
                    "is_primary_key": true
                }},
                {{
                    "name": "name",
                    "data_type": "varchar(100)",
                    "is_nullable": false
                }},
                {{
                    "name": "is_active",
                    "data_type": "boolean",
                    "default_value": "true"
                }}
            ],
            "initial_data": [
                {{"code": "X", "name": "Example", "is_active": true}}
            ]
        }}
    ],
    "foreign_keys": [
        {{
            "name": "fk_child_parent",
            "from_table": "child_table",
            "from_columns": ["parent_id"],
            "to_table": "parent_table",
            "to_columns": ["id"],
            "on_delete": "RESTRICT|CASCADE|SET NULL",
            "on_update": "CASCADE"
        }}
    ],
    "normalization_summary": {{
        "tables_decomposed": [
            {{
                "original_table": "string",
                "resulting_tables": ["list"],
                "reason": "description of normalization applied"
            }}
        ],
        "redundancy_eliminated": ["list of redundant data patterns removed"],
        "integrity_improvements": ["list of integrity improvements"]
    }}
}}
```
"""

DATA_VAULT_DESIGN_PROMPT = """You are an expert data architect designing a Data Vault 2.0 model optimized for enterprise data warehousing with full historical tracking, auditability, and agile adaptation to change.

## Context
You are designing a Data Vault 2.0 raw vault that will serve as the central repository for enterprise data integration. Data Vault separates business keys (Hubs), relationships (Links), and descriptive context (Satellites) to maximize flexibility, auditability, and historical tracking.

## User Requirements
{requirements}

## Available Source Tables
{tables_context}

## Data Profiles
{profile_context}

## Analysis Results
{analysis_context}

## Data Vault 2.0 Principles

### Core Concepts

1. **Hubs** - Contain unique business keys
   - Represent core business entities (Customer, Product, Order)
   - Contains: hash key, business key, load date, record source
   - Never changes once loaded (insert-only)
   - No descriptive attributes

2. **Links** - Represent relationships between hubs
   - Connect two or more hubs (or a hub to itself)
   - Contains: hash key, hub hash keys, load date, record source
   - Never changes once loaded (insert-only)
   - Can include degenerate attributes (transaction IDs)

3. **Satellites** - Contain descriptive attributes and history
   - Attached to a hub or link
   - Contains: parent hash key, hash diff, load date, load end date, record source, attributes
   - New row inserted when any attribute changes
   - Provides full temporal history

### Data Vault 2.0 Enhancements

1. **Hash Keys**: Use MD5 or SHA-1 hashes for consistent key generation
   - Hub hash: hash of business key
   - Link hash: hash of all hub hash keys concatenated
   - Hash diff: hash of all satellite attributes (for change detection)

2. **Load Date**: The timestamp when the record was loaded (not source system date)

3. **Record Source**: Identifies where the data came from (source system + table)

4. **Same-As Links**: Handle when same business entity exists in multiple systems

5. **Effectivity Satellites**: Track when relationships are valid (start/end dates)

6. **Multi-Active Satellites**: Multiple concurrent versions of satellite data

### Naming Conventions
- Hubs: `hub_<entity>` (e.g., hub_customer, hub_product)
- Links: `lnk_<entity1>_<entity2>` (e.g., lnk_customer_order)
- Satellites: `sat_<parent>_<context>` (e.g., sat_customer_details, sat_customer_demographics)
- Hash keys: `<entity>_hk` (e.g., customer_hk)
- Business keys: `<entity>_bk` (e.g., customer_bk)

## Design Requirements

Design a complete Data Vault 2.0 raw vault:

1. **Identify Business Keys**: Find the unique identifiers for each business entity
2. **Create Hubs**: One hub per distinct business entity
3. **Create Links**: Represent all relationships between entities
4. **Create Satellites**: Capture all descriptive attributes with history
5. **Handle Special Cases**: Same-as links, effectivity satellites, multi-active satellites

For each component, include all required Data Vault columns plus appropriate attributes.

## Output Format
Return your design as JSON:
```json
{{
    "model_name": "string",
    "strategy": "data_vault",
    "design_notes": "Overall design rationale",
    "assumptions": ["list of assumptions"],
    "warnings": ["list of caveats"],
    "hash_algorithm": "MD5|SHA1|SHA256",
    "business_key_analysis": [
        {{
            "entity": "string",
            "business_key_columns": ["list"],
            "source_table": "string",
            "key_stability": "high|medium|low",
            "notes": "string"
        }}
    ],
    "hubs": [
        {{
            "name": "hub_entity_name",
            "description": "Hub for entity_name",
            "source_tables": ["list"],
            "columns": [
                {{
                    "name": "entity_hk",
                    "data_type": "char(32)",
                    "role": "hash_key",
                    "is_primary_key": true,
                    "hash_source": "entity_bk",
                    "description": "Hash of business key"
                }},
                {{
                    "name": "entity_bk",
                    "data_type": "varchar(100)",
                    "role": "business_key",
                    "is_nullable": false,
                    "description": "Business key from source"
                }},
                {{
                    "name": "load_date",
                    "data_type": "timestamp",
                    "role": "audit",
                    "is_nullable": false,
                    "description": "Date/time record was loaded"
                }},
                {{
                    "name": "record_source",
                    "data_type": "varchar(100)",
                    "role": "audit",
                    "is_nullable": false,
                    "description": "Source system identifier"
                }}
            ],
            "unique_constraints": [["entity_bk"]]
        }}
    ],
    "links": [
        {{
            "name": "lnk_entity1_entity2",
            "description": "Relationship between entity1 and entity2",
            "link_type": "standard|same_as|hierarchical",
            "source_tables": ["list"],
            "columns": [
                {{
                    "name": "entity1_entity2_hk",
                    "data_type": "char(32)",
                    "role": "hash_key",
                    "is_primary_key": true,
                    "hash_source": ["entity1_hk", "entity2_hk"],
                    "description": "Hash of hub hash keys"
                }},
                {{
                    "name": "entity1_hk",
                    "data_type": "char(32)",
                    "role": "foreign_key",
                    "references_hub": "hub_entity1",
                    "description": "FK to hub_entity1"
                }},
                {{
                    "name": "entity2_hk",
                    "data_type": "char(32)",
                    "role": "foreign_key",
                    "references_hub": "hub_entity2",
                    "description": "FK to hub_entity2"
                }},
                {{
                    "name": "load_date",
                    "data_type": "timestamp",
                    "role": "audit"
                }},
                {{
                    "name": "record_source",
                    "data_type": "varchar(100)",
                    "role": "audit"
                }}
            ],
            "degenerate_attributes": [
                {{
                    "name": "transaction_id",
                    "data_type": "varchar(50)",
                    "description": "Original transaction identifier"
                }}
            ],
            "connected_hubs": ["hub_entity1", "hub_entity2"]
        }}
    ],
    "satellites": [
        {{
            "name": "sat_entity_context",
            "description": "Context attributes for entity",
            "parent_type": "hub|link",
            "parent_name": "hub_entity",
            "satellite_type": "standard|effectivity|multi_active|status_tracking",
            "source_tables": ["list"],
            "columns": [
                {{
                    "name": "entity_hk",
                    "data_type": "char(32)",
                    "role": "hash_key",
                    "is_primary_key": true,
                    "references_parent": "hub_entity",
                    "description": "Parent hub hash key"
                }},
                {{
                    "name": "load_date",
                    "data_type": "timestamp",
                    "role": "audit",
                    "is_primary_key": true,
                    "description": "Load timestamp (part of PK)"
                }},
                {{
                    "name": "load_end_date",
                    "data_type": "timestamp",
                    "role": "audit",
                    "is_nullable": true,
                    "description": "When record was superseded"
                }},
                {{
                    "name": "hash_diff",
                    "data_type": "char(32)",
                    "role": "hash_diff",
                    "hash_source": ["attribute1", "attribute2"],
                    "description": "Hash of all attributes for change detection"
                }},
                {{
                    "name": "record_source",
                    "data_type": "varchar(100)",
                    "role": "audit"
                }}
            ],
            "attributes": [
                {{
                    "name": "attribute1",
                    "data_type": "varchar(100)",
                    "source_column": "original_column",
                    "description": "Business attribute"
                }}
            ]
        }}
    ],
    "effectivity_satellites": [
        {{
            "name": "sat_lnk_entity1_entity2_eff",
            "description": "Tracks validity period of relationship",
            "parent_link": "lnk_entity1_entity2",
            "columns": [
                {{
                    "name": "entity1_entity2_hk",
                    "data_type": "char(32)",
                    "is_primary_key": true
                }},
                {{
                    "name": "load_date",
                    "data_type": "timestamp",
                    "is_primary_key": true
                }},
                {{
                    "name": "effective_from",
                    "data_type": "timestamp",
                    "description": "When relationship became valid"
                }},
                {{
                    "name": "effective_to",
                    "data_type": "timestamp",
                    "is_nullable": true,
                    "description": "When relationship ended (null=current)"
                }}
            ]
        }}
    ],
    "loading_patterns": {{
        "hub_loading": "Insert if business key not exists",
        "link_loading": "Insert if combination not exists",
        "satellite_loading": "Insert if hash_diff differs from latest record"
    }},
    "pit_tables": [
        {{
            "name": "pit_entity",
            "description": "Point-in-time table for entity with all satellites",
            "hub": "hub_entity",
            "satellites": ["sat_entity_details", "sat_entity_demographics"],
            "columns": [
                "entity_hk",
                "snapshot_date",
                "sat_entity_details_load_date",
                "sat_entity_demographics_load_date"
            ]
        }}
    ],
    "bridge_tables": [
        {{
            "name": "bridge_entity_hierarchy",
            "description": "Flattened hierarchy for entity",
            "hub": "hub_entity",
            "hierarchy_link": "lnk_entity_parent"
        }}
    ]
}}
```
"""


# =============================================================================
# VALIDATION PROMPTS
# =============================================================================

DESIGN_REVIEW_PROMPT = """You are a senior data architect reviewing a data model design for quality, completeness, and adherence to best practices.

## Context
A data model has been designed and needs review before implementation. You should identify issues, suggest improvements, and validate against requirements.

## Original Requirements
{requirements}

## Data Model Design
{design_json}

## Review Criteria

### Structural Integrity
1. **Primary Keys**: Every table must have a primary key defined
2. **Foreign Keys**: All relationships must have proper FK definitions
3. **Data Types**: Appropriate data types for all columns
4. **Naming Conventions**: Consistent and descriptive naming

### Design Quality
1. **Normalization/Denormalization**: Appropriate for the strategy chosen
2. **Grain Definition**: Fact tables have clear grain statements
3. **SCD Strategy**: Dimensions have appropriate SCD types defined
4. **Relationship Cardinality**: All relationships have cardinality defined

### Completeness
1. **Requirements Coverage**: All requirements are addressed
2. **Audit Columns**: Appropriate tracking columns exist
3. **Documentation**: All tables and columns have descriptions

### Performance Considerations
1. **Indexing**: Appropriate indexes suggested
2. **Partitioning**: Large tables have partitioning strategy
3. **Query Patterns**: Design supports expected query patterns

### Best Practices
1. **Surrogate Keys**: Used appropriately for dimension tables
2. **Date Dimensions**: Comprehensive date dimension exists
3. **Conformed Dimensions**: Reusable across fact tables
4. **No Orphan Tables**: All tables are connected to the model

## Output Format
Return your review as JSON:
```json
{{
    "overall_score": 0-100,
    "overall_assessment": "summary of design quality",
    "requirements_coverage": {{
        "fully_addressed": ["list of requirements met"],
        "partially_addressed": ["list with gaps noted"],
        "not_addressed": ["list of missing requirements"]
    }},
    "critical_issues": [
        {{
            "issue_type": "missing_pk|missing_fk|data_type|naming|etc",
            "table": "affected table",
            "column": "affected column or null",
            "description": "detailed description",
            "recommendation": "how to fix"
        }}
    ],
    "warnings": [
        {{
            "issue_type": "category",
            "location": "table or general",
            "description": "potential issue",
            "recommendation": "suggestion"
        }}
    ],
    "suggestions": [
        {{
            "category": "performance|usability|maintainability|etc",
            "description": "improvement suggestion",
            "priority": "high|medium|low"
        }}
    ],
    "best_practice_violations": [
        {{
            "practice": "name of best practice",
            "violation": "what was violated",
            "location": "where",
            "recommendation": "how to fix"
        }}
    ],
    "positive_aspects": ["list of things done well"],
    "approval_status": "approved|approved_with_conditions|needs_revision",
    "conditions_for_approval": ["if applicable, list conditions"]
}}
```
"""

FIX_SUGGESTION_PROMPT = """You are a data modeling expert providing specific fixes for issues identified in a data model design review.

## Context
A data model design has been reviewed and issues were identified. You need to provide specific, actionable fixes for each issue.

## Original Design
{design_json}

## Issues Identified
{issues_json}

## Task
For each issue, provide:
1. A specific fix with exact changes needed
2. Updated JSON for the affected components
3. Any related changes needed elsewhere in the model
4. Impact assessment of the change

## Output Format
Return your fixes as JSON:
```json
{{
    "fixes": [
        {{
            "issue_reference": "identifier or description of the issue",
            "fix_type": "add|modify|remove|restructure",
            "affected_components": ["list of tables/columns affected"],
            "changes": [
                {{
                    "component_type": "table|column|relationship|constraint",
                    "component_name": "name",
                    "action": "add|modify|remove",
                    "before": {{}},
                    "after": {{}},
                    "explanation": "why this change"
                }}
            ],
            "related_changes": [
                {{
                    "component": "name",
                    "change_needed": "description",
                    "reason": "why related change is needed"
                }}
            ],
            "impact_assessment": {{
                "breaking_changes": true|false,
                "data_migration_needed": true|false,
                "downstream_impact": ["list of affected downstream components"],
                "complexity": "low|medium|high"
            }},
            "implementation_notes": "additional guidance for implementing the fix"
        }}
    ],
    "updated_design_fragments": {{
        "tables": [
            {{}}
        ],
        "relationships": [
            {{}}
        ]
    }},
    "implementation_order": ["ordered list of fixes to apply"],
    "testing_recommendations": ["list of tests to verify fixes"]
}}
```
"""


# =============================================================================
# GENERATION PROMPTS
# =============================================================================

DDL_GENERATION_PROMPT = """You are a database engineer generating production-ready SQL DDL statements from a data model design.

## Context
A data model has been designed and approved. You need to generate the SQL DDL (Data Definition Language) statements to create this model in the target database.

## Data Model Design
{design_json}

## Target Database
Database: {database_type}
Schema: {schema_name}

## DDL Requirements

1. **Schema Creation**: Create schema if not exists
2. **Table Creation**: CREATE TABLE statements with all columns
3. **Primary Keys**: Defined in CREATE TABLE or as ALTER TABLE
4. **Foreign Keys**: As ALTER TABLE statements (after all tables created)
5. **Indexes**: CREATE INDEX statements for performance
6. **Constraints**: CHECK constraints, UNIQUE constraints
7. **Comments**: COMMENT ON TABLE/COLUMN for documentation

## DDL Best Practices

1. **Order of Operations**:
   - Create schema
   - Create tables (lookup/reference first, then dimensions, then facts)
   - Add foreign key constraints
   - Create indexes

2. **Naming Conventions**:
   - Primary keys: `pk_<table_name>`
   - Foreign keys: `fk_<table>_<referenced_table>`
   - Indexes: `idx_<table>_<columns>`
   - Unique constraints: `uq_<table>_<columns>`
   - Check constraints: `chk_<table>_<purpose>`

3. **Data Types** (PostgreSQL):
   - Use `bigint` for surrogate keys
   - Use `varchar(n)` with appropriate lengths
   - Use `numeric(p,s)` for money/precise decimals
   - Use `timestamptz` for timestamps
   - Use `text` for unbounded strings

## Output Format
Return the DDL as JSON:
```json
{{
    "database_type": "postgresql|mysql|snowflake|etc",
    "schema_name": "string",
    "ddl_statements": [
        {{
            "order": 1,
            "type": "schema|table|constraint|index|comment",
            "object_name": "name",
            "statement": "SQL statement",
            "dependencies": ["list of objects this depends on"],
            "notes": "any special notes"
        }}
    ],
    "rollback_statements": [
        {{
            "order": 1,
            "statement": "DROP statement for rollback"
        }}
    ],
    "migration_script": "Combined script with transaction handling",
    "estimated_execution_time": "estimate based on complexity"
}}
```
"""

DBT_MODEL_PROMPT = """You are a dbt developer generating production-ready dbt models from a data model design.

## Context
A data model has been designed and needs to be implemented as dbt models. Generate complete dbt model files with proper Jinja templating, tests, and documentation.

## Data Model Design
{design_json}

## dbt Project Context
Project Name: {project_name}
Target Database: {database_type}
Source Schema: {source_schema}
Target Schema: {target_schema}

## dbt Best Practices

### Model Organization
```
models/
  staging/           # Source-conformed models
    stg_*.sql
  intermediate/      # Transformation logic
    int_*.sql
  marts/            # Business-layer models
    dim_*.sql
    fact_*.sql
    bridge_*.sql
```

### Model Structure
1. **Config Block**: materialization, schema, tags
2. **CTEs**: Clean, logical transformation steps
3. **Final Select**: Explicit column list
4. **Documentation**: model descriptions, column descriptions

### Jinja Patterns
- `{{ source('source_name', 'table_name') }}` for raw sources
- `{{ ref('model_name') }}` for upstream models
- `{{ config(...) }}` for model configuration
- `{% set %}` for variable definitions
- `{{ dbt_utils.generate_surrogate_key([...]) }}` for surrogate keys

### Testing
- `unique` and `not_null` on primary keys
- `relationships` for foreign keys
- `accepted_values` for enums
- Custom tests for business logic

## Output Format
Return the dbt models as JSON:
```json
{{
    "project_structure": {{
        "sources": [
            {{
                "file_path": "models/staging/_sources.yml",
                "content": "YAML content for source definitions"
            }}
        ],
        "staging_models": [
            {{
                "file_path": "models/staging/stg_table_name.sql",
                "model_name": "stg_table_name",
                "content": "SQL with Jinja",
                "config": {{
                    "materialized": "view|table|incremental",
                    "schema": "staging"
                }}
            }}
        ],
        "mart_models": [
            {{
                "file_path": "models/marts/dim_entity.sql",
                "model_name": "dim_entity",
                "content": "SQL with Jinja",
                "config": {{
                    "materialized": "table",
                    "schema": "marts"
                }}
            }}
        ],
        "schema_files": [
            {{
                "file_path": "models/marts/_schema.yml",
                "content": "YAML content with tests and documentation"
            }}
        ]
    }},
    "macros": [
        {{
            "file_path": "macros/generate_date_dimension.sql",
            "content": "Macro SQL"
        }}
    ],
    "seeds": [
        {{
            "file_path": "seeds/lookup_data.csv",
            "content": "CSV content for static data"
        }}
    ],
    "tests": [
        {{
            "file_path": "tests/assert_business_rule.sql",
            "content": "Custom test SQL"
        }}
    ],
    "documentation": {{
        "overview_md": "docs/overview.md content",
        "model_docs": {{"model_name": "markdown documentation"}}
    }}
}}
```
"""

DOCUMENTATION_PROMPT = """You are a technical writer generating comprehensive documentation for a data model.

## Context
A data model has been designed and implemented. Generate complete documentation suitable for data engineers, analysts, and business stakeholders.

## Data Model Design
{design_json}

## Documentation Requirements

Generate documentation that includes:

1. **Executive Summary**: High-level overview for business stakeholders
2. **Data Model Overview**: Visual description and key concepts
3. **Table Catalog**: Detailed documentation for each table
4. **Relationship Diagram Description**: Explanation of relationships
5. **Data Dictionary**: Column-level details
6. **Usage Guide**: Common query patterns
7. **Maintenance Guide**: ETL/ELT considerations

## Output Format
Return documentation as JSON:
```json
{{
    "executive_summary": {{
        "title": "Data Model Documentation",
        "purpose": "Business purpose of this data model",
        "key_entities": ["list of main business entities"],
        "key_metrics": ["list of key measures/KPIs"],
        "stakeholders": ["list of intended users"]
    }},
    "model_overview": {{
        "strategy": "Star Schema|3NF|Data Vault",
        "description": "Detailed description of the modeling approach",
        "design_decisions": ["list of key design decisions and rationale"],
        "assumptions": ["list of assumptions made"],
        "limitations": ["known limitations"]
    }},
    "table_catalog": [
        {{
            "table_name": "string",
            "business_name": "Human-readable name",
            "description": "Detailed description",
            "role": "fact|dimension|hub|link|satellite|staging",
            "grain": "One row per...",
            "row_count_estimate": "estimate or range",
            "update_frequency": "real-time|daily|weekly|etc",
            "source_systems": ["list of sources"],
            "owner": "Team or person responsible",
            "sla": "Data freshness SLA"
        }}
    ],
    "data_dictionary": [
        {{
            "table_name": "string",
            "column_name": "string",
            "data_type": "string",
            "business_name": "Human-readable name",
            "description": "Detailed description",
            "is_nullable": true|false,
            "is_pii": true|false,
            "is_pci": true|false,
            "example_values": ["example1", "example2"],
            "business_rules": ["list of rules"],
            "source_column": "original source column"
        }}
    ],
    "relationships": [
        {{
            "name": "relationship name",
            "description": "What this relationship represents",
            "from_table": "source table",
            "to_table": "target table",
            "cardinality": "1:1|1:N|N:1|N:M",
            "business_meaning": "What this means in business terms"
        }}
    ],
    "common_queries": [
        {{
            "name": "Query name",
            "description": "What this query answers",
            "sql": "Example SQL",
            "use_case": "When to use this"
        }}
    ],
    "maintenance_guide": {{
        "etl_overview": "Description of data flow",
        "refresh_schedule": "When data is updated",
        "dependencies": ["upstream dependencies"],
        "monitoring": ["what to monitor"],
        "troubleshooting": ["common issues and solutions"]
    }},
    "glossary": [
        {{
            "term": "Business term",
            "definition": "Definition",
            "related_columns": ["list of columns using this term"]
        }}
    ],
    "version_history": [
        {{
            "version": "1.0",
            "date": "YYYY-MM-DD",
            "changes": ["list of changes"],
            "author": "name"
        }}
    ]
}}
```
"""


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def format_table_context(tables: List[Dict[str, Any]]) -> str:
    """
    Format table information for inclusion in prompts.

    Converts a list of table dictionaries or Table objects into a
    human-readable markdown format suitable for LLM prompts.

    Args:
        tables: List of table dictionaries with keys:
            - name: Table name
            - schema_name: Schema name (optional)
            - row_count: Number of rows (optional)
            - columns: List of column dictionaries

    Returns:
        Formatted markdown string describing the tables.

    Example:
        >>> tables = [{"name": "orders", "row_count": 10000, "columns": [...]}]
        >>> context = format_table_context(tables)
    """
    if not tables:
        return "No tables available."

    output_lines = []

    for table in tables:
        # Handle both dict and Pydantic model
        if hasattr(table, 'model_dump'):
            table = table.model_dump()

        name = table.get('name', 'Unknown')
        schema = table.get('schema_name', 'public')
        row_count = table.get('row_count', 'unknown')
        columns = table.get('columns', [])

        output_lines.append(f"\n### {schema}.{name} ({row_count:,} rows)" if isinstance(row_count, int) else f"\n### {schema}.{name} ({row_count} rows)")
        output_lines.append("")
        output_lines.append("| Column | Type | Nullable | Key | Description |")
        output_lines.append("|--------|------|----------|-----|-------------|")

        for col in columns[:25]:  # Limit to 25 columns for prompt size
            if hasattr(col, 'model_dump'):
                col = col.model_dump()

            col_name = col.get('name', 'Unknown')
            data_type = col.get('data_type', 'unknown')
            nullable = "Yes" if col.get('is_nullable', True) else "No"

            # Determine key type
            key_markers = []
            if col.get('is_primary_key', False):
                key_markers.append("PK")
            if col.get('is_foreign_key', False):
                fk_ref = col.get('foreign_key_table', '')
                key_markers.append(f"FK->{fk_ref}" if fk_ref else "FK")
            if col.get('is_unique', False) and not col.get('is_primary_key', False):
                key_markers.append("UQ")
            key_str = ", ".join(key_markers) if key_markers else "-"

            description = col.get('description', '-') or '-'
            # Truncate long descriptions
            if len(description) > 50:
                description = description[:47] + "..."

            output_lines.append(f"| {col_name} | {data_type} | {nullable} | {key_str} | {description} |")

        if len(columns) > 25:
            output_lines.append(f"| ... | ... | ... | ... | ({len(columns) - 25} more columns) |")

    return "\n".join(output_lines)


def format_profile_context(profiles: Dict[str, Any]) -> str:
    """
    Format data profiling results for inclusion in prompts.

    Converts profiling data into a human-readable format with key statistics
    and quality indicators.

    Args:
        profiles: Dictionary mapping table names to TableProfile objects
            or profile dictionaries containing column statistics.

    Returns:
        Formatted markdown string with profiling summaries.

    Example:
        >>> profiles = {"orders": TableProfile(...)}
        >>> context = format_profile_context(profiles)
    """
    if not profiles:
        return "\n## Data Profiles\nNo profiling data available."

    output_lines = ["\n## Data Profiles"]

    for table_name, table_profile in profiles.items():
        # Handle both dict and Pydantic model
        if hasattr(table_profile, 'model_dump'):
            table_profile = table_profile.model_dump()

        row_count = table_profile.get('row_count', 0)
        quality_score = table_profile.get('overall_quality_score', 100)
        completeness = table_profile.get('completeness_score', 100)

        output_lines.append(f"\n### {table_name}")
        output_lines.append(f"- **Rows**: {row_count:,}" if isinstance(row_count, int) else f"- **Rows**: {row_count}")
        output_lines.append(f"- **Quality Score**: {quality_score:.1f}%")
        output_lines.append(f"- **Completeness**: {completeness:.1f}%")
        output_lines.append("")

        # Column statistics
        columns = table_profile.get('columns', [])
        if columns:
            output_lines.append("**Column Statistics:**")
            output_lines.append("| Column | Type | Nulls % | Distinct | Unique | Top Value |")
            output_lines.append("|--------|------|---------|----------|--------|-----------|")

            for col_profile in columns[:15]:  # Limit columns
                if hasattr(col_profile, 'model_dump'):
                    col_profile = col_profile.model_dump()

                col_name = col_profile.get('column_name', 'Unknown')
                stats = col_profile.get('statistics', {})
                if hasattr(stats, 'model_dump'):
                    stats = stats.model_dump()

                data_type = stats.get('data_type', 'unknown')
                null_pct = stats.get('null_percentage', 0)
                distinct = stats.get('distinct_count', 0)
                is_unique = "Yes" if stats.get('is_unique', False) else "No"

                # Get top value if available
                top_values = stats.get('top_values', [])
                top_val = str(top_values[0].get('value', '-'))[:20] if top_values else '-'

                output_lines.append(f"| {col_name} | {data_type} | {null_pct:.1f}% | {distinct:,} | {is_unique} | {top_val} |")

            if len(columns) > 15:
                output_lines.append(f"| ... | ... | ... | ... | ... | ({len(columns) - 15} more) |")

    return "\n".join(output_lines)


def format_analysis_context(
    fds: Optional[List[Dict[str, Any]]] = None,
    keys: Optional[List[Dict[str, Any]]] = None,
    relationships: Optional[List[Dict[str, Any]]] = None
) -> str:
    """
    Format analysis results (FDs, keys, relationships) for prompts.

    Converts functional dependencies, candidate keys, and relationship
    analysis into a readable format for LLM consumption.

    Args:
        fds: List of FunctionalDependency objects or dictionaries.
        keys: List of CandidateKey objects or dictionaries.
        relationships: List of RelationshipAnalysis objects or dictionaries.

    Returns:
        Formatted markdown string with analysis results.

    Example:
        >>> fds = [FunctionalDependency(determinant=["a"], dependent="b")]
        >>> context = format_analysis_context(fds=fds)
    """
    output_lines = ["\n## Analysis Results"]

    # Functional Dependencies
    if fds:
        output_lines.append("\n### Functional Dependencies")
        output_lines.append("| Determinant | Dependent | Confidence | Type |")
        output_lines.append("|-------------|-----------|------------|------|")

        for fd in fds[:20]:  # Limit to 20
            if hasattr(fd, 'model_dump'):
                fd = fd.model_dump()

            determinant = ", ".join(fd.get('determinant', []))
            dependent = fd.get('dependent', '')
            confidence = fd.get('confidence', 1.0)

            fd_type = []
            if fd.get('is_partial', False):
                fd_type.append("Partial")
            if fd.get('is_transitive', False):
                fd_type.append("Transitive")
            if fd.get('is_trivial', False):
                fd_type.append("Trivial")
            type_str = ", ".join(fd_type) if fd_type else "Standard"

            output_lines.append(f"| {determinant} | {dependent} | {confidence:.2f} | {type_str} |")

        if len(fds) > 20:
            output_lines.append(f"| ... | ... | ... | ({len(fds) - 20} more FDs) |")
    else:
        output_lines.append("\n### Functional Dependencies")
        output_lines.append("No functional dependencies analyzed.")

    # Candidate Keys
    if keys:
        output_lines.append("\n### Candidate Keys")
        output_lines.append("| Table | Key Columns | Uniqueness | Recommended |")
        output_lines.append("|-------|-------------|------------|-------------|")

        for key in keys[:15]:
            if hasattr(key, 'model_dump'):
                key = key.model_dump()

            # Try to get table name from context
            table = key.get('table_name', '-')
            columns = ", ".join(key.get('columns', []))
            uniqueness = key.get('uniqueness', 1.0)
            recommended = "Yes" if key.get('recommended_as_primary', False) else "No"

            output_lines.append(f"| {table} | ({columns}) | {uniqueness:.2%} | {recommended} |")
    else:
        output_lines.append("\n### Candidate Keys")
        output_lines.append("No candidate keys analyzed.")

    # Relationships
    if relationships:
        output_lines.append("\n### Discovered Relationships")
        output_lines.append("| From | To | Cardinality | Confidence |")
        output_lines.append("|------|-----|-------------|------------|")

        for rel in relationships[:15]:
            if hasattr(rel, 'model_dump'):
                rel = rel.model_dump()

            from_ref = f"{rel.get('from_table', '')}.{rel.get('from_column', '')}"
            to_ref = f"{rel.get('to_table', '')}.{rel.get('to_column', '')}"
            cardinality = rel.get('cardinality', 'N:1')
            confidence = rel.get('confidence', 'medium')
            if isinstance(confidence, float):
                confidence = f"{confidence:.0%}"

            output_lines.append(f"| {from_ref} | {to_ref} | {cardinality} | {confidence} |")
    else:
        output_lines.append("\n### Discovered Relationships")
        output_lines.append("No relationships analyzed.")

    return "\n".join(output_lines)


def format_schemas_context(schemas: List[Dict[str, Any]]) -> str:
    """
    Format available schemas for the schema selection prompt.

    Args:
        schemas: List of schema dictionaries with name and metadata.

    Returns:
        Formatted markdown string listing available schemas.
    """
    if not schemas:
        return "No schemas available."

    output_lines = []
    for schema in schemas:
        name = schema.get('name', 'Unknown')
        table_count = schema.get('table_count', 0)
        description = schema.get('description', 'No description')

        output_lines.append(f"- **{name}**: {table_count} tables - {description}")

    return "\n".join(output_lines)


# =============================================================================
# LEGACY PROMPT BUILDERS (for backward compatibility)
# =============================================================================

def build_star_schema_prompt(state: Dict[str, Any]) -> str:
    """
    Build prompt for Star Schema design.

    This is a convenience function that formats the STAR_SCHEMA_DESIGN_PROMPT
    with the provided state dictionary.

    Args:
        state: Dictionary containing:
            - requirements: User requirements string
            - discovered_tables: List of table dictionaries
            - data_profiles: Optional profiling results

    Returns:
        Formatted prompt string ready for LLM.
    """
    requirements = state.get('requirements', 'No requirements provided.')
    tables = state.get('discovered_tables', [])
    profiles = state.get('data_profiles', {})
    analysis = state.get('analysis_results', {})

    tables_context = format_table_context(tables)
    profile_context = format_profile_context(profiles) if profiles else ""
    analysis_context = format_analysis_context(
        fds=analysis.get('functional_dependencies'),
        keys=analysis.get('candidate_keys'),
        relationships=analysis.get('relationships')
    ) if analysis else ""

    return STAR_SCHEMA_DESIGN_PROMPT.format(
        requirements=requirements,
        tables_context=tables_context,
        profile_context=profile_context,
        analysis_context=analysis_context
    )


def build_normalized_3nf_prompt(state: Dict[str, Any]) -> str:
    """
    Build prompt for Normalized (3NF) design.

    This is a convenience function that formats the NORMALIZED_3NF_DESIGN_PROMPT
    with the provided state dictionary.

    Args:
        state: Dictionary containing:
            - requirements: User requirements string
            - discovered_tables: List of table dictionaries
            - data_profiles: Optional profiling results
            - analysis_results: Optional FD and key analysis

    Returns:
        Formatted prompt string ready for LLM.
    """
    requirements = state.get('requirements', 'No requirements provided.')
    tables = state.get('discovered_tables', [])
    profiles = state.get('data_profiles', {})
    analysis = state.get('analysis_results', {})

    tables_context = format_table_context(tables)
    profile_context = format_profile_context(profiles) if profiles else ""
    analysis_context = format_analysis_context(
        fds=analysis.get('functional_dependencies'),
        keys=analysis.get('candidate_keys'),
        relationships=analysis.get('relationships')
    ) if analysis else ""

    return NORMALIZED_3NF_DESIGN_PROMPT.format(
        requirements=requirements,
        tables_context=tables_context,
        profile_context=profile_context,
        analysis_context=analysis_context
    )


def build_data_vault_prompt(state: Dict[str, Any]) -> str:
    """
    Build prompt for Data Vault 2.0 design.

    This is a convenience function that formats the DATA_VAULT_DESIGN_PROMPT
    with the provided state dictionary.

    Args:
        state: Dictionary containing:
            - requirements: User requirements string
            - discovered_tables: List of table dictionaries
            - data_profiles: Optional profiling results
            - analysis_results: Optional analysis results

    Returns:
        Formatted prompt string ready for LLM.
    """
    requirements = state.get('requirements', 'No requirements provided.')
    tables = state.get('discovered_tables', [])
    profiles = state.get('data_profiles', {})
    analysis = state.get('analysis_results', {})

    tables_context = format_table_context(tables)
    profile_context = format_profile_context(profiles) if profiles else ""
    analysis_context = format_analysis_context(
        fds=analysis.get('functional_dependencies'),
        keys=analysis.get('candidate_keys'),
        relationships=analysis.get('relationships')
    ) if analysis else ""

    return DATA_VAULT_DESIGN_PROMPT.format(
        requirements=requirements,
        tables_context=tables_context,
        profile_context=profile_context,
        analysis_context=analysis_context
    )


# Legacy helper functions for backward compatibility
def _format_tables(tables: List[Dict[str, Any]]) -> str:
    """Legacy function - use format_table_context instead."""
    return format_table_context(tables)


def _format_profiles(profiles: Dict[str, Any]) -> str:
    """Legacy function - use format_profile_context instead."""
    return format_profile_context(profiles)
