# Schema Normalization & Auto Schema Creation Plan

> **Document Purpose**: Comprehensive analysis and implementation plan for building a robust auto schema creation system that converts raw data into properly normalized schemas using data engineering best practices.

---

## Table of Contents

1. [Current State Analysis](#current-state-analysis)
2. [Data Engineering Best Practices](#data-engineering-best-practices)
3. [Testing Strategy](#testing-strategy)
4. [Skills/Tools Needed](#skillstools-needed)
5. [Implementation Plan](#implementation-plan)
6. [Data Flow Architecture](#data-flow-architecture)

---

## Current State Analysis

### What's Currently Implemented

The DataForge platform has a functional but incomplete auto schema creation pipeline:

#### 1. **Schema Discovery** (`core/mcp/servers/postgres_mcp.py`)
- **Working**:
  - Schema enumeration from `information_schema.schemata`
  - Table discovery with row counts and sizes
  - Column metadata extraction (types, nullability, defaults)
  - Primary key detection via `table_constraints`
  - Foreign key relationship discovery
  - Basic data profiling (null %, distinct counts, min/max/avg, samples)

- **Limitations**:
  - Only PostgreSQL supported (MySQL, Snowflake, BigQuery stubs exist)
  - No composite key handling
  - No index discovery
  - No check constraint discovery
  - No unique constraint discovery (beyond PK)
  - Profiling is basic - no pattern detection, no data quality scoring

#### 2. **Model Design via LLM** (`core/graph/modeling_graph.py`, `core/prompts/modeling.py`)
- **Working**:
  - Three modeling strategies: Star Schema, Normalized 3NF, Data Vault
  - LangGraph workflow with 8 nodes for orchestration
  - Structured output via Pydantic models
  - Basic prompt templates that include table/column metadata

- **Limitations**:
  - **LLM does ALL the normalization work** - no algorithmic analysis
  - Prompts are vague ("eliminate redundancy") without specific rules
  - No functional dependency detection
  - No candidate key identification
  - Only profiling first 5 tables, 15 columns
  - No data pattern recognition passed to LLM
  - 3NF and Data Vault strategies have **NO code generation** (only Star Schema works)

#### 3. **DBT Code Generation** (`core/generators/dbt_generator.py`)
- **Working**:
  - Complete dbt project structure generation
  - Source definitions, staging models, marts
  - Schema YAML with tests (unique, not_null, relationships)
  - Documentation generation
  - Jinja template usage for surrogate keys

- **Limitations**:
  - Only works for Star Schema design
  - Generated SQL has placeholder join logic (`-- Add join logic here`)
  - No incremental model support
  - No snapshot (SCD Type 2) implementation
  - Hardcoded to PostgreSQL profiles
  - No data type conversion/mapping logic

#### 4. **Validation** (`core/validators/`)
- **Status**: **EMPTY** - module exists but has no implementation
- No schema validation
- No data quality validation
- No generated code validation

---

### What's Broken/Problematic

| Issue | Severity | Location | Description |
|-------|----------|----------|-------------|
| **LLM-Only Normalization** | Critical | `modeling_graph.py:324-364` | Normalization is entirely prompt-based with no deterministic analysis. LLM may produce inconsistent results. |
| **No Functional Dependency Detection** | Critical | N/A | Cannot algorithmically identify FDs for proper normalization |
| **Incomplete Join Logic** | High | `dbt_generator.py:375-381` | Generated dimension/fact models have placeholder comments instead of actual joins |
| **No Type Inference** | High | N/A | Raw database types passed through without semantic inference (e.g., detecting email, phone, URL patterns) |
| **Limited Profiling** | High | `postgres_mcp.py:370-477` | No pattern detection, cardinality ratio analysis, or statistical distribution analysis |
| **Empty Validators** | High | `core/validators/` | No validation of inputs, designs, or outputs |
| **3NF/Data Vault Not Implemented** | Medium | `modeling_graph.py:370-376` | Code generation skipped for non-star-schema strategies |
| **Single Database Support** | Medium | `postgres_mcp.py` | Only PostgreSQL; MySQL/Snowflake/BigQuery are stubs |
| **No Relationship Inference** | Medium | N/A | Can only use explicit FK constraints; can't infer relationships from naming conventions or data patterns |
| **Hardcoded Sample Limits** | Low | `prompts/modeling.py:121,137` | Only 15 columns, 3 tables in profiles passed to LLM |

---

### Gaps Analysis

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     CURRENT VS IDEAL STATE                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  CURRENT PIPELINE:                                                       │
│  ┌──────────┐    ┌──────────┐    ┌─────────────┐    ┌──────────────┐   │
│  │ Discover │───▶│  Profile │───▶│ LLM Design  │───▶│ Generate dbt │   │
│  │  Schema  │    │  (basic) │    │ (all logic) │    │ (incomplete) │   │
│  └──────────┘    └──────────┘    └─────────────┘    └──────────────┘   │
│                                                                          │
│  MISSING COMPONENTS (shown in red):                                      │
│  ┌──────────┐    ┌──────────┐    ┌─────────────┐    ┌──────────────┐   │
│  │  Type    │    │ Pattern  │    │  FD/Key    │    │ Relationship │    │
│  │ Inference│    │ Detection│    │ Analysis   │    │  Inference   │    │
│  └──────────┘    └──────────┘    └─────────────┘    └──────────────┘   │
│                                                                          │
│  ┌──────────┐    ┌──────────┐    ┌─────────────┐    ┌──────────────┐   │
│  │ Quality  │    │Validation│    │ Join Logic │    │  Multi-DB    │    │
│  │ Scoring  │    │  Layer   │    │ Generation │    │   Support    │    │
│  └──────────┘    └──────────┘    └─────────────┘    └──────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Data Engineering Best Practices

### Step-by-Step Process for Raw Data to Normalized Schema

A data engineer follows a systematic process to transform raw data into a well-designed normalized schema:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    DATA NORMALIZATION WORKFLOW                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  PHASE 1: DATA DISCOVERY & PROFILING                                        │
│  ────────────────────────────────────                                        │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐     │
│  │   Extract   │──▶│   Profile   │──▶│   Analyze   │──▶│  Document   │     │
│  │   Metadata  │   │    Data     │   │  Patterns   │   │  Findings   │     │
│  └─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘     │
│                                                                              │
│  PHASE 2: SEMANTIC ANALYSIS                                                  │
│  ──────────────────────────                                                  │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐     │
│  │   Infer     │──▶│  Identify   │──▶│   Detect    │──▶│    Find     │     │
│  │   Types     │   │   Keys      │   │    FDs      │   │   Entities  │     │
│  └─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘     │
│                                                                              │
│  PHASE 3: NORMALIZATION                                                      │
│  ─────────────────────                                                       │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐     │
│  │   Apply     │──▶│   Apply     │──▶│   Apply     │──▶│  Validate   │     │
│  │    1NF      │   │    2NF      │   │   3NF/BCNF  │   │   Design    │     │
│  └─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘     │
│                                                                              │
│  PHASE 4: PHYSICAL DESIGN                                                    │
│  ───────────────────────                                                     │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐     │
│  │   Define    │──▶│    Add      │──▶│   Create    │──▶│  Generate   │     │
│  │   Indexes   │   │ Constraints │   │   Schema    │   │    DDL      │     │
│  └─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Phase 1: Data Discovery & Profiling

#### 1.1 Extract Metadata
```python
# What to extract for each table:
metadata = {
    "table_name": str,
    "schema": str,
    "columns": [
        {
            "name": str,
            "data_type": str,        # Raw database type
            "is_nullable": bool,
            "default_value": any,
            "max_length": int,        # For varchar/char
            "precision": int,         # For numeric
            "scale": int,             # For numeric
            "ordinal_position": int,
        }
    ],
    "constraints": {
        "primary_keys": [...],
        "foreign_keys": [...],
        "unique_constraints": [...],
        "check_constraints": [...],
    },
    "indexes": [...],
    "row_count": int,
    "size_bytes": int,
}
```

#### 1.2 Profile Data (Statistical Analysis)
```python
# Per-column profiling:
column_profile = {
    # Basic Statistics
    "null_count": int,
    "null_percentage": float,
    "distinct_count": int,
    "distinct_percentage": float,    # Cardinality ratio
    "total_count": int,

    # Type-Specific Stats
    "min_value": any,
    "max_value": any,
    "mean": float,                   # Numeric only
    "median": float,                 # Numeric only
    "std_dev": float,                # Numeric only
    "mode": any,                     # Most frequent value

    # Distribution
    "histogram": [...],              # Value distribution
    "percentiles": {...},            # P25, P50, P75, P90, P99
    "outlier_count": int,

    # String-Specific
    "min_length": int,
    "max_length": int,
    "avg_length": float,
    "empty_string_count": int,

    # Samples
    "sample_values": [...],          # Random sample
    "top_values": [...],             # Most frequent with counts
    "bottom_values": [...],          # Least frequent
}
```

#### 1.3 Analyze Patterns (Critical for Type Inference)
```python
# Pattern detection rules:
patterns = {
    "email": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
    "phone_us": r"^\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}$",
    "phone_intl": r"^\+\d{1,3}[-.\s]?\d{4,14}$",
    "url": r"^https?://[^\s/$.?#].[^\s]*$",
    "uuid": r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    "ip_v4": r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$",
    "date_iso": r"^\d{4}-\d{2}-\d{2}$",
    "datetime_iso": r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}",
    "credit_card": r"^\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}$",
    "ssn": r"^\d{3}-\d{2}-\d{4}$",
    "zip_us": r"^\d{5}(-\d{4})?$",
    "currency": r"^\$?\d+(\.\d{2})?$",
    "percentage": r"^\d+(\.\d+)?%$",
    "boolean_text": r"^(true|false|yes|no|y|n|1|0)$",
    "json": r"^\{.*\}$|^\[.*\]$",
}

# Pattern matching confidence:
pattern_result = {
    "column_name": str,
    "detected_pattern": str,         # e.g., "email"
    "match_percentage": float,       # % of non-null values matching
    "confidence": str,               # HIGH (>95%), MEDIUM (80-95%), LOW (<80%)
}
```

### Phase 2: Semantic Analysis

#### 2.1 Type Inference Rules
```python
# Semantic type hierarchy:
SEMANTIC_TYPES = {
    "identifier": {
        "primary_key": ["id", "pk", "_id", "key"],
        "foreign_key": ["_id", "_fk", "_key"],
        "natural_key": ["code", "number", "sku", "upc"],
    },
    "personal": {
        "name": ["name", "first_name", "last_name", "full_name"],
        "email": ["email", "email_address", "mail"],
        "phone": ["phone", "mobile", "telephone", "fax"],
        "address": ["address", "street", "city", "state", "zip", "postal"],
    },
    "temporal": {
        "created_at": ["created_at", "created_date", "created_on", "insert_date"],
        "updated_at": ["updated_at", "modified_at", "modified_date", "last_updated"],
        "deleted_at": ["deleted_at", "deleted_date", "removed_at"],
        "event_time": ["timestamp", "event_time", "occurred_at"],
    },
    "financial": {
        "amount": ["amount", "price", "cost", "total", "subtotal", "fee"],
        "quantity": ["quantity", "qty", "count", "units"],
        "currency": ["currency", "currency_code"],
    },
    "status": {
        "status": ["status", "state", "stage"],
        "is_active": ["is_active", "active", "enabled", "is_enabled"],
        "is_deleted": ["is_deleted", "deleted", "archived"],
    },
}

# Inference algorithm:
def infer_semantic_type(column_name, data_type, profile, patterns):
    """
    Priority order:
    1. Pattern match (if high confidence)
    2. Column name match
    3. Data characteristics
    4. Fallback to raw type
    """
    pass
```

#### 2.2 Key Identification Algorithm
```python
# Candidate Key Detection:
def find_candidate_keys(table_profile):
    """
    A candidate key must be:
    1. Unique (distinct_count == total_count)
    2. Non-null (null_count == 0)
    3. Minimal (no subset is also a key)
    """
    candidates = []

    # Single-column candidates
    for col in columns:
        if col.distinct_count == col.total_count and col.null_count == 0:
            candidates.append([col.name])

    # Multi-column candidates (composite keys)
    # Only check if no single-column key found
    if not candidates:
        for combo in combinations(columns, 2):
            # Query: SELECT COUNT(DISTINCT (col1, col2)) FROM table
            pass

    return candidates

# Primary Key Selection:
def select_primary_key(candidates, semantic_types):
    """
    Priority:
    1. Existing PK constraint
    2. Column named 'id' or '<table>_id'
    3. Smallest candidate key
    4. Integer over string
    """
    pass
```

#### 2.3 Functional Dependency Detection
```python
# FD Detection Algorithm:
def detect_functional_dependencies(table, sample_size=10000):
    """
    Functional Dependency: X -> Y means X uniquely determines Y

    Algorithm:
    1. For each pair of columns (X, Y):
       - GROUP BY X and check if Y has single value per group
       - If COUNT(DISTINCT Y) == 1 for all groups, X -> Y

    2. Transitive closure:
       - If X -> Y and Y -> Z, then X -> Z

    Returns: List of FDs like [('customer_id', 'customer_name'), ...]
    """
    fds = []

    for x_col in columns:
        for y_col in columns:
            if x_col != y_col:
                # SQL: SELECT {x}, COUNT(DISTINCT {y}) as cnt
                #      FROM table GROUP BY {x} HAVING cnt > 1
                # If no rows returned, X -> Y holds
                query = f"""
                    SELECT COUNT(*) as violations FROM (
                        SELECT {x_col}, COUNT(DISTINCT {y_col}) as cnt
                        FROM {table}
                        GROUP BY {x_col}
                        HAVING COUNT(DISTINCT {y_col}) > 1
                    ) t
                """
                # If violations == 0, FD holds
                pass

    return fds
```

#### 2.4 Entity Recognition
```python
# Entity Detection Heuristics:
def identify_entities(tables, fds, relationships):
    """
    Entities are typically:
    1. Tables with a clear primary key
    2. Tables referenced by foreign keys
    3. Tables with descriptive (non-transactional) data

    Facts/Events are:
    1. Tables with multiple FKs to other tables
    2. Tables with timestamps and measures
    3. High cardinality tables

    Link/Bridge tables are:
    1. Tables with only FKs (no descriptive attributes)
    2. Implement M:N relationships
    """
    entities = []
    facts = []
    links = []

    for table in tables:
        fk_count = count_foreign_keys(table)
        has_measures = has_numeric_non_fk_columns(table)
        has_timestamp = has_temporal_columns(table)

        if fk_count >= 2 and has_measures and has_timestamp:
            facts.append(table)
        elif fk_count >= 2 and not has_measures:
            links.append(table)
        else:
            entities.append(table)

    return entities, facts, links
```

### Phase 3: Normalization Theory & Application

#### 3.1 First Normal Form (1NF)
```
RULE: Each column contains atomic (indivisible) values; no repeating groups.

VIOLATIONS TO DETECT:
├── Multi-valued columns (comma-separated lists)
│   Example: tags = "red,blue,green"
│   Fix: Create separate tag table with FK relationship
│
├── Repeating column groups
│   Example: phone1, phone2, phone3
│   Fix: Create separate phone table
│
├── JSON/Array columns (in relational context)
│   Example: metadata = '{"a": 1, "b": 2}'
│   Fix: Extract to separate columns or table
│
└── Nested data structures
    Fix: Flatten into separate tables

DETECTION ALGORITHM:
1. Check for delimiter patterns in string columns (,|;|\t|\n)
2. Look for numbered column suffixes (*_1, *_2, *_3)
3. Identify JSON/JSONB columns
4. Check for array data types
```

#### 3.2 Second Normal Form (2NF)
```
RULE: 1NF + No partial dependencies (every non-key attribute depends on the WHOLE key)

ONLY APPLIES TO: Tables with composite primary keys

VIOLATION EXAMPLE:
┌─────────────────────────────────────────────────────────────────┐
│ OrderItems (order_id, product_id, quantity, product_name)       │
├─────────────────────────────────────────────────────────────────┤
│ PK: (order_id, product_id)                                      │
│ product_name depends only on product_id, NOT on order_id        │
│ This is a PARTIAL DEPENDENCY                                    │
└─────────────────────────────────────────────────────────────────┘

FIX:
┌────────────────────────────┐    ┌────────────────────────────┐
│ OrderItems                 │    │ Products                   │
├────────────────────────────┤    ├────────────────────────────┤
│ order_id (PK, FK)          │    │ product_id (PK)            │
│ product_id (PK, FK)        │───▶│ product_name               │
│ quantity                   │    └────────────────────────────┘
└────────────────────────────┘

DETECTION ALGORITHM:
1. Identify tables with composite PKs
2. For each non-key column, test FD against each PK component
3. If FD holds for subset of PK, it's a partial dependency
```

#### 3.3 Third Normal Form (3NF)
```
RULE: 2NF + No transitive dependencies (non-key attributes don't depend on other non-key attributes)

VIOLATION EXAMPLE:
┌─────────────────────────────────────────────────────────────────┐
│ Employees (emp_id, emp_name, dept_id, dept_name, dept_location) │
├─────────────────────────────────────────────────────────────────┤
│ emp_id -> dept_id (direct)                                      │
│ dept_id -> dept_name, dept_location (transitive via dept_id)    │
│ Therefore: emp_id -> dept_name is TRANSITIVE                    │
└─────────────────────────────────────────────────────────────────┘

FIX:
┌────────────────────────────┐    ┌────────────────────────────┐
│ Employees                  │    │ Departments                │
├────────────────────────────┤    ├────────────────────────────┤
│ emp_id (PK)                │    │ dept_id (PK)               │
│ emp_name                   │    │ dept_name                  │
│ dept_id (FK)               │───▶│ dept_location              │
└────────────────────────────┘    └────────────────────────────┘

DETECTION ALGORITHM:
1. Find all FDs: X -> Y where X is non-key
2. Check if X is determined by the PK
3. If PK -> X -> Y (chain), Y has transitive dependency
```

#### 3.4 Boyce-Codd Normal Form (BCNF)
```
RULE: For every FD X -> Y, X must be a superkey

DIFFERENCE FROM 3NF:
- 3NF allows: X -> Y where Y is part of a candidate key
- BCNF forbids this

VIOLATION EXAMPLE:
┌─────────────────────────────────────────────────────────────────┐
│ StudentCourses (student_id, course_id, instructor)              │
├─────────────────────────────────────────────────────────────────┤
│ Constraint: Each instructor teaches only one course             │
│ FD: instructor -> course_id                                     │
│ But instructor is not a superkey (doesn't determine student_id) │
└─────────────────────────────────────────────────────────────────┘

FIX: Decompose based on the offending FD
```

### Phase 4: Relationship Inference (When No Explicit FKs)

```python
# Relationship inference heuristics:
def infer_relationships(tables):
    """
    When explicit foreign keys don't exist, infer from:

    1. Naming conventions:
       - column named 'user_id' in 'orders' -> FK to 'users.id'
       - column named 'order_user_id' -> FK to 'users.id' or 'order_users.id'

    2. Data overlap analysis:
       - If column A values are subset of column B values, A might reference B

    3. Join pattern analysis (if query logs available):
       - Frequently joined columns are likely related

    4. Cardinality matching:
       - FK column cardinality <= PK column cardinality
    """
    inferred = []

    for table in tables:
        for column in table.columns:
            # Pattern: {entity}_id
            match = re.match(r'^(.+)_id$', column.name)
            if match:
                entity = match.group(1)
                target_table = pluralize(entity)  # user -> users
                if target_table in tables:
                    inferred.append({
                        "from_table": table.name,
                        "from_column": column.name,
                        "to_table": target_table,
                        "to_column": "id",
                        "confidence": "HIGH" if data_overlap > 0.95 else "MEDIUM"
                    })

    return inferred
```

---

## Testing Strategy

### Test Categories

#### 1. Unit Tests

| Component | Test Cases | Priority |
|-----------|------------|----------|
| **Type Inference** | Email detection, phone detection, date parsing, UUID detection, boolean text | High |
| **Pattern Matching** | Regex accuracy, false positive rate, edge cases (empty, null, partial match) | High |
| **FD Detection** | Simple FD, composite FD, no FD, transitive FD | Critical |
| **Key Detection** | Single PK, composite PK, no candidate key, multiple candidates | Critical |
| **1NF Violations** | CSV columns, repeating groups, JSON arrays | High |
| **2NF Violations** | Partial dependencies with composite keys | High |
| **3NF Violations** | Transitive dependencies | High |
| **Relationship Inference** | Naming convention match, data overlap, no match | Medium |

#### 2. Integration Tests

```python
# Test fixtures for different scenarios:
TEST_SCENARIOS = {
    "e_commerce": {
        "description": "Classic e-commerce schema",
        "tables": ["users", "orders", "order_items", "products", "categories"],
        "expected_entities": ["users", "products", "categories"],
        "expected_facts": ["orders", "order_items"],
        "expected_relationships": 5,
    },
    "denormalized_flat": {
        "description": "Single flat table with all data",
        "tables": ["sales_report"],
        "expected_1nf_violations": 2,
        "expected_3nf_violations": 5,
        "expected_decomposition_tables": 4,
    },
    "already_normalized": {
        "description": "Well-designed 3NF schema",
        "tables": ["customers", "addresses", "orders"],
        "expected_violations": 0,
        "expected_changes": 0,
    },
    "data_vault_source": {
        "description": "Source for Data Vault modeling",
        "tables": ["customer_orders_flat"],
        "expected_hubs": 2,
        "expected_links": 1,
        "expected_satellites": 2,
    },
}
```

#### 3. Edge Case Tests

```python
# Edge cases to handle:
EDGE_CASES = [
    # Data Quality Issues
    "all_nulls_column",           # Column is 100% null
    "single_value_column",        # All rows have same value
    "high_cardinality_text",      # Nearly unique text (descriptions)
    "mixed_type_column",          # Numbers stored as text

    # Schema Issues
    "no_primary_key",             # Table without PK
    "composite_pk_many_cols",     # PK with 5+ columns
    "circular_fk",                # A -> B -> A
    "self_referencing_fk",        # parent_id -> id

    # Naming Issues
    "inconsistent_naming",        # Mix of camelCase, snake_case, UPPERCASE
    "reserved_words",             # Column named 'order', 'user', 'group'
    "unicode_names",              # Non-ASCII column names

    # Size Issues
    "empty_table",                # 0 rows
    "huge_table",                 # 100M+ rows (sampling required)
    "wide_table",                 # 500+ columns
]
```

#### 4. Golden File Tests

```python
# Snapshot testing for deterministic outputs:
def test_normalization_golden_files():
    """
    Compare generated schema against known-good outputs.

    Structure:
    tests/golden/
    ├── ecommerce/
    │   ├── input_schema.json
    │   ├── expected_analysis.json
    │   ├── expected_normalized_schema.json
    │   └── expected_dbt_files/
    │       ├── dbt_project.yml
    │       ├── models/staging/stg_orders.sql
    │       └── ...
    """
    pass
```

#### 5. Property-Based Tests

```python
# Using hypothesis for property-based testing:
from hypothesis import given, strategies as st

@given(st.lists(st.integers(min_value=1), min_size=10, max_size=1000))
def test_key_detection_unique_column_is_candidate(data):
    """Property: Any column with all unique values is a candidate key."""
    # Create mock table with this data
    # Assert that column is identified as candidate key
    pass

@given(st.data())
def test_normalization_preserves_data(data):
    """Property: Normalizing then denormalizing preserves original data."""
    pass
```

### Test Data Generation

```python
# Synthetic test data generators:
class TestDataGenerator:
    """Generate realistic test data for various scenarios."""

    @staticmethod
    def generate_denormalized_orders(n_rows=1000):
        """Generate flat order table with redundancy."""
        return pd.DataFrame({
            "order_id": range(n_rows),
            "customer_id": np.random.randint(1, 100, n_rows),
            "customer_name": [...],      # Redundant: depends on customer_id
            "customer_email": [...],     # Redundant: depends on customer_id
            "product_id": np.random.randint(1, 50, n_rows),
            "product_name": [...],       # Redundant: depends on product_id
            "product_category": [...],   # Redundant: depends on product_id
            "quantity": np.random.randint(1, 10, n_rows),
            "unit_price": [...],         # Redundant: depends on product_id
            "order_date": [...],
        })

    @staticmethod
    def generate_with_violations(violation_type: str):
        """Generate data with specific normalization violations."""
        pass
```

---

## Skills/Tools Needed

### MCP Tools to Create

#### 1. **Schema Analyzer MCP** (`core/mcp/tools/schema_analyzer.py`)
```python
class SchemaAnalyzerMCP:
    """
    MCP tool for comprehensive schema analysis.

    Operations:
    - analyze_schema: Full analysis of a database schema
    - detect_violations: Find normalization violations
    - suggest_decomposition: Recommend table splits
    - infer_relationships: Find implicit relationships
    """

    async def analyze_schema(self, schema_name: str) -> SchemaAnalysis:
        """
        Returns:
            SchemaAnalysis with:
            - Table profiles
            - Detected FDs
            - Candidate keys
            - Normalization violations
            - Relationship graph
        """
        pass
```

#### 2. **Type Inferencer MCP** (`core/mcp/tools/type_inferencer.py`)
```python
class TypeInferencerMCP:
    """
    MCP tool for semantic type inference.

    Operations:
    - infer_column_type: Infer semantic type for a column
    - detect_patterns: Find data patterns
    - validate_type: Validate data against inferred type
    """

    async def infer_column_type(
        self,
        schema: str,
        table: str,
        column: str
    ) -> SemanticType:
        """
        Returns semantic type with confidence score.
        """
        pass
```

#### 3. **FD Detector MCP** (`core/mcp/tools/fd_detector.py`)
```python
class FDDetectorMCP:
    """
    MCP tool for functional dependency detection.

    Operations:
    - detect_fds: Find all FDs in a table
    - check_fd: Verify if a specific FD holds
    - find_keys: Identify candidate keys
    - compute_closure: Compute attribute closure
    """

    async def detect_fds(
        self,
        schema: str,
        table: str,
        sample_size: int = 10000
    ) -> List[FunctionalDependency]:
        pass
```

#### 4. **Normalizer MCP** (`core/mcp/tools/normalizer.py`)
```python
class NormalizerMCP:
    """
    MCP tool for schema normalization.

    Operations:
    - normalize_to_1nf: Fix 1NF violations
    - normalize_to_2nf: Fix 2NF violations
    - normalize_to_3nf: Fix 3NF violations
    - normalize_to_bcnf: Fix BCNF violations
    - generate_migration: Create migration scripts
    """

    async def normalize_to_3nf(
        self,
        schema_analysis: SchemaAnalysis
    ) -> NormalizationResult:
        """
        Returns:
            - Proposed new schema
            - Table decompositions
            - Migration DDL
            - Data migration queries
        """
        pass
```

### Python Libraries to Use

| Library | Purpose | Current Status |
|---------|---------|----------------|
| `pandas` | Data profiling, sampling | Available |
| `sqlalchemy` | Database abstraction | Available |
| `asyncpg` | Async PostgreSQL | Available |
| `pydantic` | Data validation | Available |
| `networkx` | Relationship graphs | **Add** |
| `scipy.stats` | Statistical analysis | **Add** |
| `rapidfuzz` | Fuzzy string matching | **Add** |
| `phonenumbers` | Phone validation | **Add** |
| `email-validator` | Email validation | **Add** |
| `python-dateutil` | Date parsing | **Add** |
| `great_expectations` | Data quality | **Consider** |

### New Core Components

```
core/
├── analysis/                    # NEW: Analysis engines
│   ├── __init__.py
│   ├── profiler.py             # Enhanced data profiling
│   ├── type_inference.py       # Semantic type detection
│   ├── pattern_detector.py     # Regex pattern matching
│   ├── fd_detector.py          # Functional dependency detection
│   ├── key_finder.py           # Candidate key identification
│   └── relationship_inferrer.py # Relationship discovery
│
├── normalization/               # NEW: Normalization logic
│   ├── __init__.py
│   ├── violations.py           # Violation detection
│   ├── decomposer.py           # Table decomposition
│   ├── normalizer_1nf.py       # 1NF normalization
│   ├── normalizer_2nf.py       # 2NF normalization
│   ├── normalizer_3nf.py       # 3NF normalization
│   └── normalizer_bcnf.py      # BCNF normalization
│
├── validators/                  # EXPANDED: Validation logic
│   ├── __init__.py
│   ├── schema_validator.py     # Schema validation
│   ├── data_validator.py       # Data quality validation
│   ├── design_validator.py     # Model design validation
│   └── output_validator.py     # Generated code validation
│
└── models/                      # NEW: Domain models
    ├── __init__.py
    ├── schema.py               # Schema representation
    ├── analysis.py             # Analysis results
    ├── design.py               # Design specifications
    └── types.py                # Semantic type definitions
```

---

## Implementation Plan

### Phase 1: Foundation (Week 1-2)

#### 1.1 Create Domain Models
```python
# core/models/schema.py
class Column(BaseModel):
    name: str
    data_type: DatabaseType
    semantic_type: Optional[SemanticType]
    is_nullable: bool
    is_primary_key: bool
    is_foreign_key: bool
    foreign_key_ref: Optional[ForeignKeyRef]
    constraints: List[Constraint]
    profile: Optional[ColumnProfile]

class Table(BaseModel):
    name: str
    schema: str
    columns: List[Column]
    primary_key: List[str]
    foreign_keys: List[ForeignKey]
    indexes: List[Index]
    row_count: int
    functional_dependencies: List[FunctionalDependency]
    candidate_keys: List[List[str]]

class Schema(BaseModel):
    name: str
    tables: List[Table]
    relationships: List[Relationship]
    analysis: Optional[SchemaAnalysis]
```

#### 1.2 Enhanced Profiler
```python
# core/analysis/profiler.py
class EnhancedProfiler:
    """
    Comprehensive data profiling with statistical analysis.
    """

    async def profile_column(
        self,
        schema: str,
        table: str,
        column: str,
        sample_size: int = 10000
    ) -> ColumnProfile:
        """Full statistical profile of a column."""
        pass

    async def profile_table(
        self,
        schema: str,
        table: str,
        sample_size: int = 10000
    ) -> TableProfile:
        """Profile all columns in a table."""
        pass

    async def get_data_quality_score(
        self,
        profile: ColumnProfile
    ) -> DataQualityScore:
        """
        Score data quality (0-100) based on:
        - Completeness (null %)
        - Uniqueness (distinct %)
        - Validity (pattern match %)
        - Consistency (outlier %)
        """
        pass
```

### Phase 2: Analysis Engine (Week 3-4)

#### 2.1 Type Inference System
```python
# core/analysis/type_inference.py
class TypeInferenceEngine:
    """
    Infer semantic types from data patterns and column names.
    """

    def __init__(self):
        self.pattern_rules = self._load_pattern_rules()
        self.name_rules = self._load_name_rules()

    async def infer_type(
        self,
        column_name: str,
        data_type: str,
        sample_values: List[Any],
        profile: ColumnProfile
    ) -> SemanticType:
        """
        Multi-signal type inference:
        1. Pattern matching on sample values
        2. Column name matching
        3. Statistical characteristics
        4. Combination scoring
        """
        pass
```

#### 2.2 Functional Dependency Detector
```python
# core/analysis/fd_detector.py
class FDDetector:
    """
    Detect functional dependencies using database queries.
    """

    async def detect_all_fds(
        self,
        db: DatabaseConnection,
        schema: str,
        table: str,
        columns: List[str],
        sample_size: int = 50000
    ) -> List[FunctionalDependency]:
        """
        Algorithm: TANE-inspired FD discovery
        1. Find single-column FDs
        2. Prune using transitivity
        3. Find composite FDs only where needed
        """
        pass

    async def verify_fd(
        self,
        db: DatabaseConnection,
        schema: str,
        table: str,
        determinant: List[str],
        dependent: str
    ) -> FDVerification:
        """Verify a specific FD holds (or report violations)."""
        pass
```

### Phase 3: Normalization Engine (Week 5-6)

#### 3.1 Violation Detector
```python
# core/normalization/violations.py
class ViolationDetector:
    """
    Detect normalization violations at all levels.
    """

    async def detect_1nf_violations(
        self,
        table: Table,
        profiles: Dict[str, ColumnProfile]
    ) -> List[Violation1NF]:
        """
        Detect:
        - Multi-valued columns
        - Repeating groups
        - Non-atomic values
        """
        pass

    async def detect_2nf_violations(
        self,
        table: Table,
        fds: List[FunctionalDependency]
    ) -> List[Violation2NF]:
        """
        Detect partial dependencies (only for composite PKs).
        """
        pass

    async def detect_3nf_violations(
        self,
        table: Table,
        fds: List[FunctionalDependency]
    ) -> List[Violation3NF]:
        """
        Detect transitive dependencies.
        """
        pass
```

#### 3.2 Schema Decomposer
```python
# core/normalization/decomposer.py
class SchemaDecomposer:
    """
    Decompose tables to eliminate normalization violations.
    """

    def decompose_for_3nf(
        self,
        table: Table,
        violations: List[Violation3NF]
    ) -> DecompositionResult:
        """
        Create new tables to eliminate transitive dependencies.

        Algorithm:
        1. Group FDs by determinant
        2. Create new table for each non-key determinant
        3. Keep FK to maintain relationship
        4. Generate migration DDL
        """
        pass

    def validate_decomposition(
        self,
        original: Table,
        decomposed: List[Table]
    ) -> ValidationResult:
        """
        Verify decomposition preserves:
        - All data (lossless join)
        - All FDs (dependency preservation)
        """
        pass
```

### Phase 4: Generator Enhancements (Week 7-8)

#### 4.1 Join Logic Generator
```python
# core/generators/join_generator.py
class JoinGenerator:
    """
    Generate actual SQL join logic instead of placeholders.
    """

    def generate_joins(
        self,
        target_table: Table,
        source_tables: List[Table],
        relationships: List[Relationship]
    ) -> str:
        """
        Generate proper JOIN clauses based on relationships.
        """
        pass

    def infer_join_type(
        self,
        relationship: Relationship,
        source_profile: TableProfile,
        target_profile: TableProfile
    ) -> JoinType:
        """
        Determine JOIN type (INNER, LEFT, RIGHT) based on:
        - Relationship cardinality
        - Null patterns
        - Business rules
        """
        pass
```

#### 4.2 Multi-Strategy Code Generator
```python
# core/generators/strategy_generator.py
class StrategyGenerator:
    """
    Generate code for all modeling strategies.
    """

    def generate_star_schema(
        self,
        design: StarSchemaDesign,
        relationships: List[Relationship]
    ) -> Dict[str, str]:
        """Generate dbt models for star schema."""
        pass

    def generate_normalized_3nf(
        self,
        design: NormalizedDesign,
        relationships: List[Relationship]
    ) -> Dict[str, str]:
        """Generate dbt models for 3NF schema."""
        pass

    def generate_data_vault(
        self,
        design: DataVaultDesign,
        relationships: List[Relationship]
    ) -> Dict[str, str]:
        """Generate dbt models for Data Vault."""
        pass
```

### Phase 5: Validation & Testing (Week 9-10)

#### 5.1 Comprehensive Validators
```python
# core/validators/schema_validator.py
class SchemaValidator:
    """Validate schema designs before generation."""

    def validate_design(
        self,
        design: ModelDesign,
        source_schema: Schema
    ) -> ValidationResult:
        """
        Validate:
        - All source columns accounted for
        - No orphan tables
        - Valid relationships
        - Proper key definitions
        - Type compatibility
        """
        pass

# core/validators/output_validator.py
class OutputValidator:
    """Validate generated code."""

    def validate_dbt_project(
        self,
        files: Dict[str, str]
    ) -> ValidationResult:
        """
        Validate:
        - YAML syntax
        - SQL syntax
        - Model references (ref())
        - Source references (source())
        - Test definitions
        - Circular dependencies
        """
        pass

    def validate_sql_syntax(
        self,
        sql: str,
        dialect: str = "postgres"
    ) -> ValidationResult:
        """Parse SQL and check for syntax errors."""
        pass
```

### Phase 6: Integration & Workflow (Week 11-12)

#### 6.1 Enhanced Workflow
```python
# core/graph/enhanced_modeling_graph.py
class EnhancedModelingWorkflow:
    """
    New workflow with proper analysis nodes.
    """

    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(ModelingState)

        # Discovery (existing)
        workflow.add_node("discover_schemas", self.discover_schemas)
        workflow.add_node("select_schema", self.select_schema)
        workflow.add_node("discover_tables", self.discover_tables)

        # NEW: Enhanced Profiling
        workflow.add_node("profile_data", self.profile_data_enhanced)
        workflow.add_node("infer_types", self.infer_semantic_types)

        # NEW: Analysis
        workflow.add_node("detect_fds", self.detect_functional_dependencies)
        workflow.add_node("find_keys", self.find_candidate_keys)
        workflow.add_node("detect_violations", self.detect_normalization_violations)
        workflow.add_node("infer_relationships", self.infer_relationships)

        # Design (enhanced)
        workflow.add_node("design_model", self.design_model_with_analysis)
        workflow.add_node("validate_design", self.validate_design)

        # Generation (enhanced)
        workflow.add_node("generate_code", self.generate_code_all_strategies)
        workflow.add_node("validate_output", self.validate_generated_code)

        # ... edges ...

        return workflow.compile()
```

---

## Data Flow Architecture

### Complete System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DATAFORGE ARCHITECTURE                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        USER INTERFACES                               │   │
│  │  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────────────┐  │   │
│  │  │   CLI   │    │   Web   │    │ VSCode  │    │   REST API      │  │   │
│  │  │  (typer)│    │ (React) │    │Extension│    │   (FastAPI)     │  │   │
│  │  └────┬────┘    └────┬────┘    └────┬────┘    └────────┬────────┘  │   │
│  └───────┼──────────────┼──────────────┼─────────────────┼────────────┘   │
│          └──────────────┴──────────────┴─────────────────┘                 │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     ORCHESTRATION LAYER                              │   │
│  │  ┌───────────────────────────────────────────────────────────────┐  │   │
│  │  │                   LangGraph Workflow                          │  │   │
│  │  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐         │  │   │
│  │  │  │Discover │─▶│ Profile │─▶│ Analyze │─▶│ Design  │         │  │   │
│  │  │  └─────────┘  └─────────┘  └─────────┘  └────┬────┘         │  │   │
│  │  │                                              │               │  │   │
│  │  │  ┌─────────┐  ┌─────────┐  ┌─────────┐      │               │  │   │
│  │  │  │Complete │◀─│Validate │◀─│Generate │◀─────┘               │  │   │
│  │  │  └─────────┘  └─────────┘  └─────────┘                      │  │   │
│  │  └───────────────────────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│          ┌─────────────────────────┼─────────────────────────┐             │
│          │                         │                         │              │
│          ▼                         ▼                         ▼              │
│  ┌───────────────┐    ┌────────────────────┐    ┌──────────────────────┐  │
│  │   ANALYSIS    │    │    NORMALIZATION    │    │     GENERATION       │  │
│  │    ENGINE     │    │       ENGINE        │    │       ENGINE         │  │
│  ├───────────────┤    ├────────────────────┤    ├──────────────────────┤  │
│  │ ├─Profiler    │    │ ├─ViolationDetector│    │ ├─DBTGenerator       │  │
│  │ ├─TypeInfer   │    │ ├─Decomposer       │    │ ├─JoinGenerator      │  │
│  │ ├─FDDetector  │    │ ├─Normalizer1NF    │    │ ├─StarSchemaGen      │  │
│  │ ├─KeyFinder   │    │ ├─Normalizer2NF    │    │ ├─NormalizedGen      │  │
│  │ └─RelInfer    │    │ ├─Normalizer3NF    │    │ └─DataVaultGen       │  │
│  │               │    │ └─NormalizerBCNF   │    │                      │  │
│  └───────────────┘    └────────────────────┘    └──────────────────────┘  │
│          │                         │                         │              │
│          └─────────────────────────┼─────────────────────────┘             │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         MCP LAYER                                    │   │
│  │  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────────┐    │   │
│  │  │ Postgres  │  │  MySQL    │  │ Snowflake │  │   BigQuery    │    │   │
│  │  │   MCP     │  │   MCP     │  │   MCP     │  │     MCP       │    │   │
│  │  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘  └───────┬───────┘    │   │
│  │        │              │              │                │             │   │
│  │  ┌─────┴──────────────┴──────────────┴────────────────┴─────┐      │   │
│  │  │                    MCP Registry                          │      │   │
│  │  │           (Connection pooling, Health checks)            │      │   │
│  │  └──────────────────────────────────────────────────────────┘      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                       DATA SOURCES                                   │   │
│  │  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────────┐    │   │
│  │  │PostgreSQL │  │   MySQL   │  │ Snowflake │  │   BigQuery    │    │   │
│  │  │   DB      │  │    DB     │  │    DW     │  │     DW        │    │   │
│  │  └───────────┘  └───────────┘  └───────────┘  └───────────────┘    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Detailed Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DATA FLOW DIAGRAM                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  USER REQUEST                                                                │
│  "Create analytics model for e-commerce data"                               │
│       │                                                                      │
│       ▼                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  1. SCHEMA DISCOVERY                                                 │   │
│  │     Input: Connection config, schema pattern                         │   │
│  │     Output: List of schemas, tables, columns, constraints            │   │
│  │                                                                       │   │
│  │     ┌─────────────┐      ┌─────────────┐      ┌─────────────┐       │   │
│  │     │ Query       │      │ Parse       │      │ Build       │       │   │
│  │     │ info_schema │─────▶│ Results     │─────▶│ Schema      │       │   │
│  │     │             │      │             │      │ Model       │       │   │
│  │     └─────────────┘      └─────────────┘      └──────┬──────┘       │   │
│  └──────────────────────────────────────────────────────┼───────────────┘   │
│                                                          │                   │
│                                                          ▼                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  2. DATA PROFILING                                                   │   │
│  │     Input: Schema model                                              │   │
│  │     Output: Statistical profiles for each column                     │   │
│  │                                                                       │   │
│  │     For each column:                                                  │   │
│  │     ┌─────────────┐      ┌─────────────┐      ┌─────────────┐       │   │
│  │     │ Sample      │      │ Calculate   │      │ Detect      │       │   │
│  │     │ Data        │─────▶│ Statistics  │─────▶│ Patterns    │       │   │
│  │     │ (10K rows)  │      │ (nulls,dist)│      │ (regex)     │       │   │
│  │     └─────────────┘      └─────────────┘      └──────┬──────┘       │   │
│  └──────────────────────────────────────────────────────┼───────────────┘   │
│                                                          │                   │
│                                                          ▼                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  3. SEMANTIC ANALYSIS                                                │   │
│  │     Input: Profiles                                                  │   │
│  │     Output: Semantic types, FDs, candidate keys, relationships       │   │
│  │                                                                       │   │
│  │     ┌─────────────┐      ┌─────────────┐      ┌─────────────┐       │   │
│  │     │ Infer       │      │ Detect      │      │ Find        │       │   │
│  │     │ Semantic    │      │ Functional  │      │ Candidate   │       │   │
│  │     │ Types       │      │ Deps        │      │ Keys        │       │   │
│  │     └──────┬──────┘      └──────┬──────┘      └──────┬──────┘       │   │
│  │            │                    │                    │               │   │
│  │            └────────────────────┼────────────────────┘               │   │
│  │                                 │                                    │   │
│  │     ┌─────────────┐      ┌──────▼──────┐                            │   │
│  │     │ Infer       │      │ Build       │                            │   │
│  │     │ Relations   │◀─────│ Analysis    │                            │   │
│  │     │             │      │ Report      │                            │   │
│  │     └──────┬──────┘      └─────────────┘                            │   │
│  └────────────┼─────────────────────────────────────────────────────────┘   │
│               │                                                              │
│               ▼                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  4. NORMALIZATION ANALYSIS                                           │   │
│  │     Input: FDs, Keys, Schema                                         │   │
│  │     Output: Violations, Proposed decompositions                      │   │
│  │                                                                       │   │
│  │     ┌─────────────┐      ┌─────────────┐      ┌─────────────┐       │   │
│  │     │ Check 1NF   │      │ Check 2NF   │      │ Check 3NF   │       │   │
│  │     │ Violations  │─────▶│ Violations  │─────▶│ Violations  │       │   │
│  │     │             │      │             │      │             │       │   │
│  │     └─────────────┘      └─────────────┘      └──────┬──────┘       │   │
│  │                                                       │              │   │
│  │                                               ┌───────▼───────┐      │   │
│  │                                               │ Generate      │      │   │
│  │                                               │ Decomposition │      │   │
│  │                                               │ Plan          │      │   │
│  │                                               └───────┬───────┘      │   │
│  └───────────────────────────────────────────────────────┼──────────────┘   │
│                                                          │                   │
│                                                          ▼                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  5. LLM-ASSISTED DESIGN                                              │   │
│  │     Input: Analysis report, user requirements, strategy              │   │
│  │     Output: Model design (Star/3NF/DataVault)                        │   │
│  │                                                                       │   │
│  │     ┌─────────────┐      ┌─────────────┐      ┌─────────────┐       │   │
│  │     │ Build       │      │ Call LLM    │      │ Parse       │       │   │
│  │     │ Enhanced    │─────▶│ with        │─────▶│ Structured  │       │   │
│  │     │ Prompt      │      │ Analysis    │      │ Output      │       │   │
│  │     └─────────────┘      └─────────────┘      └──────┬──────┘       │   │
│  │                                                       │              │   │
│  │     Note: LLM now receives:                          │              │   │
│  │     - Full FD analysis                               │              │   │
│  │     - Key recommendations                            │              │   │
│  │     - Violation report                               │              │   │
│  │     - Relationship graph                             │              │   │
│  │     - Semantic type mappings                         │              │   │
│  └───────────────────────────────────────────────────────┼──────────────┘   │
│                                                          │                   │
│                                                          ▼                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  6. DESIGN VALIDATION                                                │   │
│  │     Input: Proposed design                                           │   │
│  │     Output: Validated design or rejection with reasons               │   │
│  │                                                                       │   │
│  │     ┌─────────────┐      ┌─────────────┐      ┌─────────────┐       │   │
│  │     │ Check       │      │ Verify      │      │ Validate    │       │   │
│  │     │ Completeness│─────▶│ Relations   │─────▶│ Keys        │       │   │
│  │     │             │      │             │      │             │       │   │
│  │     └─────────────┘      └─────────────┘      └──────┬──────┘       │   │
│  └───────────────────────────────────────────────────────┼──────────────┘   │
│                                                          │                   │
│                                                          ▼                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  7. CODE GENERATION                                                  │   │
│  │     Input: Validated design, relationships                           │   │
│  │     Output: Complete dbt project                                     │   │
│  │                                                                       │   │
│  │     ┌─────────────┐      ┌─────────────┐      ┌─────────────┐       │   │
│  │     │ Generate    │      │ Generate    │      │ Generate    │       │   │
│  │     │ Sources     │─────▶│ Staging     │─────▶│ Marts       │       │   │
│  │     │ YAML        │      │ Models      │      │ (with joins)│       │   │
│  │     └─────────────┘      └─────────────┘      └──────┬──────┘       │   │
│  │                                                       │              │   │
│  │     ┌─────────────┐      ┌─────────────┐             │              │   │
│  │     │ Generate    │      │ Generate    │             │              │   │
│  │     │ Schema      │◀─────│ Tests       │◀────────────┘              │   │
│  │     │ Docs        │      │             │                            │   │
│  │     └──────┬──────┘      └─────────────┘                            │   │
│  └────────────┼─────────────────────────────────────────────────────────┘   │
│               │                                                              │
│               ▼                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  8. OUTPUT VALIDATION                                                │   │
│  │     Input: Generated files                                           │   │
│  │     Output: Validated project or errors                              │   │
│  │                                                                       │   │
│  │     ┌─────────────┐      ┌─────────────┐      ┌─────────────┐       │   │
│  │     │ Validate    │      │ Validate    │      │ Check       │       │   │
│  │     │ YAML        │─────▶│ SQL         │─────▶│ References  │       │   │
│  │     │ Syntax      │      │ Syntax      │      │ (ref/src)   │       │   │
│  │     └─────────────┘      └─────────────┘      └──────┬──────┘       │   │
│  └───────────────────────────────────────────────────────┼──────────────┘   │
│                                                          │                   │
│                                                          ▼                   │
│  OUTPUT                                                                      │
│  Complete dbt project with:                                                  │
│  - dbt_project.yml                                                           │
│  - models/staging/*.sql (with actual SQL)                                   │
│  - models/marts/*.sql (with actual JOINs)                                   │
│  - models/**/schema.yml (with tests)                                        │
│  - README.md                                                                 │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Component Interaction Sequence

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      COMPONENT INTERACTION SEQUENCE                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  User        API       Workflow    Analysis    Normalizer   Generator       │
│   │           │           │           │            │            │           │
│   │──request──▶           │           │            │            │           │
│   │           │──start───▶│           │            │            │           │
│   │           │           │──discover─▶           │            │           │
│   │           │           │◀──schema──│            │            │           │
│   │           │           │──profile──▶           │            │           │
│   │           │           │◀──stats───│            │            │           │
│   │           │           │──analyze──▶           │            │           │
│   │           │           │◀──FDs/keys│            │            │           │
│   │           │           │──────────check───────▶│            │           │
│   │           │           │◀─────────violations──│            │           │
│   │           │           │──────────design (LLM)──────────────│           │
│   │           │           │◀─────────model design──────────────│           │
│   │           │           │──────────────────────generate─────▶│           │
│   │           │           │◀─────────────────────────files────│           │
│   │           │◀──result──│           │            │            │           │
│   │◀──output──│           │           │            │            │           │
│   │           │           │           │            │            │           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Implementation Priorities

### Critical Path (Must Have)

| Priority | Component | Effort | Impact |
|----------|-----------|--------|--------|
| P0 | FD Detection | Medium | Enables proper normalization |
| P0 | Key Finding | Medium | Required for FD detection |
| P0 | Violation Detection | Medium | Core normalization feature |
| P0 | Join Generation | Medium | Fixes placeholder SQL |
| P1 | Type Inference | Medium | Better semantic understanding |
| P1 | Design Validation | Low | Catch errors early |
| P1 | Output Validation | Low | Ensure quality |

### Nice to Have

| Priority | Component | Effort | Impact |
|----------|-----------|--------|--------|
| P2 | Relationship Inference | High | Handles implicit FKs |
| P2 | 3NF/Data Vault Generation | Medium | Complete all strategies |
| P2 | Multi-DB Support | High | Broader applicability |
| P3 | Data Quality Scoring | Medium | Better profiling |
| P3 | Incremental Models | Medium | Production optimization |

---

## Success Criteria

### Functional Requirements
- [ ] FD detection accuracy > 95% on test datasets
- [ ] Correct identification of all normalization violations
- [ ] Generated SQL executes without syntax errors
- [ ] All source columns present in final model
- [ ] Relationship graph correctly represents FK relationships

### Non-Functional Requirements
- [ ] Analysis of 100-table schema < 5 minutes
- [ ] FD detection scales to 1M row tables via sampling
- [ ] Generated code follows dbt best practices
- [ ] Clear error messages for validation failures

### Test Coverage
- [ ] Unit test coverage > 80%
- [ ] Integration tests for all workflows
- [ ] Golden file tests for deterministic outputs
- [ ] Edge case coverage for all identified scenarios

---

## Appendix: Reference Materials

### Normalization Theory
- Codd, E.F. (1970). "A Relational Model of Data for Large Shared Data Banks"
- Date, C.J. "An Introduction to Database Systems" (Chapter on Normalization)

### dbt Best Practices
- dbt Labs Style Guide
- dbt Best Practices for Dimensional Modeling

### Data Profiling Standards
- ISO 8000 (Data Quality)
- DAMA-DMBOK (Data Management Body of Knowledge)

---

*Document Version: 1.0*
*Last Updated: January 2026*
*Author: DataForge Analysis Agent*
