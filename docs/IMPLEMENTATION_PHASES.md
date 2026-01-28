# DataForge Schema Normalization - Implementation Phases

> **Project**: Auto Schema Creation System Revamp
> **Goal**: Transform raw data into properly normalized schemas using data engineering best practices
> **Created**: January 2026

---

## Overview

This document outlines the phased implementation plan for revamping the DataForge backend architecture. Each phase has specific milestones with commit checkpoints.

```
Current State                          Target State
─────────────                          ────────────
┌──────────┐                           ┌──────────────────────────────────┐
│ Discover │                           │ Discover → Profile → Analyze →  │
│ Profile  │  ───────────────────────▶ │ Detect FDs → Normalize →        │
│ LLM Only │                           │ Design → Generate → Validate    │
│ Generate │                           │ (with algorithmic analysis)     │
└──────────┘                           └──────────────────────────────────┘
```

---

## Phase 1: Foundation Layer (Domain Models & Enhanced Profiling)

### Objective
Establish core domain models and enhance the data profiling system with statistical analysis.

### Directory Structure to Create
```
core/
├── models/                    # NEW
│   ├── __init__.py
│   ├── schema.py             # Schema, Table, Column models
│   ├── analysis.py           # Analysis result models
│   ├── design.py             # Design specification models
│   └── types.py              # Semantic type definitions
│
├── analysis/                  # NEW
│   ├── __init__.py
│   └── profiler.py           # Enhanced data profiler
```

### Tasks

#### 1.1 Create Domain Models (`core/models/`)
- [ ] **schema.py**: `Column`, `Table`, `Schema`, `ForeignKey`, `Index`, `Constraint` models
- [ ] **types.py**: `SemanticType`, `DatabaseType`, `PatternType` enums and models
- [ ] **analysis.py**: `ColumnProfile`, `TableProfile`, `SchemaAnalysis`, `FunctionalDependency`
- [ ] **design.py**: `ModelDesign`, `StarSchemaDesign`, `NormalizedDesign`, `DataVaultDesign`

#### 1.2 Create Enhanced Profiler (`core/analysis/profiler.py`)
- [ ] `EnhancedProfiler` class with async database operations
- [ ] Statistical analysis: null%, distinct%, min/max/mean/median/stddev
- [ ] Distribution analysis: histograms, percentiles, outliers
- [ ] String analysis: min/max/avg length, empty count
- [ ] Sample collection: random samples, top/bottom values
- [ ] Data quality scoring (0-100)

### Commit Milestone
```
feat(core): add domain models and enhanced profiler

- Add Pydantic models for schema representation (Column, Table, Schema)
- Add semantic type system with 20+ type definitions
- Add analysis result models (ColumnProfile, TableProfile)
- Add EnhancedProfiler with statistical analysis
- Add data quality scoring algorithm
```

### Success Criteria
- [ ] All models pass Pydantic validation
- [ ] Profiler can analyze 1M row table via sampling in <30s
- [ ] Unit tests for all models and profiler methods

---

## Phase 2: Analysis Engine (Type Inference, FD Detection, Key Finding)

### Objective
Build algorithmic analysis capabilities to detect patterns, functional dependencies, and candidate keys.

### Directory Structure to Create
```
core/
├── analysis/                  # EXPAND
│   ├── __init__.py
│   ├── profiler.py           # (from Phase 1)
│   ├── type_inference.py     # Semantic type detection
│   ├── pattern_detector.py   # Regex pattern matching
│   ├── fd_detector.py        # Functional dependency detection
│   ├── key_finder.py         # Candidate key identification
│   └── relationship_inferrer.py # Relationship discovery
```

### Tasks

#### 2.1 Pattern Detector (`core/analysis/pattern_detector.py`)
- [ ] Regex patterns for: email, phone, URL, UUID, IP, dates, credit card, SSN, zip, currency, JSON
- [ ] Pattern matching with confidence scoring (HIGH >95%, MEDIUM 80-95%, LOW <80%)
- [ ] Batch pattern detection across columns

#### 2.2 Type Inference Engine (`core/analysis/type_inference.py`)
- [ ] Semantic type hierarchy (identifier, personal, temporal, financial, status)
- [ ] Name-based inference rules (column name patterns)
- [ ] Data-based inference (patterns + statistics)
- [ ] Multi-signal scoring algorithm

#### 2.3 Functional Dependency Detector (`core/analysis/fd_detector.py`)
- [ ] TANE-inspired FD discovery algorithm
- [ ] SQL-based FD verification queries
- [ ] Composite FD detection
- [ ] Transitive closure computation
- [ ] FD violation reporting

#### 2.4 Candidate Key Finder (`core/analysis/key_finder.py`)
- [ ] Single-column candidate key detection
- [ ] Composite key detection (when needed)
- [ ] Primary key selection heuristics
- [ ] Uniqueness and non-null validation

#### 2.5 Relationship Inferrer (`core/analysis/relationship_inferrer.py`)
- [ ] Naming convention matching (`user_id` → `users.id`)
- [ ] Data overlap analysis (value subset detection)
- [ ] Cardinality matching validation
- [ ] Confidence scoring for inferred relationships

### Commit Milestone
```
feat(analysis): add analysis engine with FD detection and type inference

- Add pattern detector with 15+ regex patterns
- Add semantic type inference with name/data signals
- Add TANE-inspired functional dependency detector
- Add candidate key finder with composite key support
- Add relationship inferrer for implicit FK detection
```

### Success Criteria
- [ ] FD detection accuracy >95% on test datasets
- [ ] Type inference correctly identifies 90%+ of common types
- [ ] Key finder identifies all PKs in test schemas
- [ ] Relationship inferrer finds 80%+ of implicit relationships

---

## Phase 3: Normalization Engine (Violation Detection & Decomposition)

### Objective
Implement normalization theory (1NF through BCNF) with violation detection and automatic schema decomposition.

### Directory Structure to Create
```
core/
├── normalization/             # NEW
│   ├── __init__.py
│   ├── violations.py         # Violation detection (1NF, 2NF, 3NF, BCNF)
│   ├── decomposer.py         # Table decomposition logic
│   ├── normalizer_1nf.py     # First normal form
│   ├── normalizer_2nf.py     # Second normal form
│   ├── normalizer_3nf.py     # Third normal form
│   └── normalizer_bcnf.py    # Boyce-Codd normal form
```

### Tasks

#### 3.1 Violation Detector (`core/normalization/violations.py`)
- [ ] **1NF violations**: multi-valued columns, repeating groups, JSON arrays, delimited strings
- [ ] **2NF violations**: partial dependencies (for composite PKs)
- [ ] **3NF violations**: transitive dependencies
- [ ] **BCNF violations**: non-superkey determinants
- [ ] Violation severity scoring

#### 3.2 Schema Decomposer (`core/normalization/decomposer.py`)
- [ ] FD-based decomposition algorithm
- [ ] Lossless join property validation
- [ ] Dependency preservation validation
- [ ] Migration DDL generation
- [ ] Data migration query generation

#### 3.3 Normalizers (1NF, 2NF, 3NF, BCNF)
- [ ] **1NF Normalizer**: Split multi-valued columns, extract repeating groups
- [ ] **2NF Normalizer**: Remove partial dependencies via decomposition
- [ ] **3NF Normalizer**: Remove transitive dependencies via decomposition
- [ ] **BCNF Normalizer**: Ensure all determinants are superkeys

### Commit Milestone
```
feat(normalization): add normalization engine with violation detection

- Add violation detector for 1NF/2NF/3NF/BCNF
- Add schema decomposer with lossless join validation
- Add normalizers for each normal form
- Add migration DDL and data migration query generation
```

### Success Criteria
- [ ] Correctly identifies all normalization violations in test datasets
- [ ] Decomposition preserves all data (lossless join)
- [ ] Decomposition preserves all FDs (dependency preservation)
- [ ] Generated migration DDL executes without errors

---

## Phase 4: Generator Enhancements (Join Logic & Multi-Strategy)

### Objective
Fix placeholder SQL generation and implement code generation for all modeling strategies (Star, 3NF, Data Vault).

### Directory Structure to Modify
```
core/
├── generators/                # EXPAND
│   ├── __init__.py
│   ├── dbt_generator.py      # MODIFY: Fix placeholders
│   ├── join_generator.py     # NEW: Actual join logic
│   ├── star_schema_gen.py    # NEW: Star schema specific
│   ├── normalized_gen.py     # NEW: 3NF specific
│   └── data_vault_gen.py     # NEW: Data Vault specific
```

### Tasks

#### 4.1 Join Generator (`core/generators/join_generator.py`)
- [ ] Generate proper JOIN clauses from relationships
- [ ] Infer JOIN type (INNER, LEFT, RIGHT) from cardinality/nulls
- [ ] Handle composite foreign keys
- [ ] Generate surrogate key joins for dimensions

#### 4.2 Star Schema Generator (`core/generators/star_schema_gen.py`)
- [ ] Fact table generation with proper FK joins
- [ ] Dimension table generation with SCD Type 1/2 support
- [ ] Bridge table generation for M:N relationships
- [ ] Conformed dimension handling

#### 4.3 Normalized (3NF) Generator (`core/generators/normalized_gen.py`)
- [ ] Entity table generation with proper relationships
- [ ] Junction table generation for M:N
- [ ] Referential integrity constraints
- [ ] Index recommendations

#### 4.4 Data Vault Generator (`core/generators/data_vault_gen.py`)
- [ ] Hub generation (business keys)
- [ ] Link generation (relationships)
- [ ] Satellite generation (descriptive attributes)
- [ ] Point-in-time (PIT) tables
- [ ] Bridge tables

#### 4.5 Update dbt_generator.py
- [ ] Remove placeholder comments (`-- Add join logic here`)
- [ ] Integrate with join_generator
- [ ] Add incremental model support
- [ ] Add snapshot (SCD Type 2) templates
- [ ] Multi-database profile support

### Commit Milestone
```
feat(generators): add complete code generation for all strategies

- Add JoinGenerator with proper SQL join clauses
- Add StarSchemaGenerator with fact/dimension models
- Add NormalizedGenerator for 3NF schemas
- Add DataVaultGenerator with hub/link/satellite models
- Update dbt_generator to remove placeholders
```

### Success Criteria
- [ ] Generated SQL executes without syntax errors
- [ ] All strategies produce complete, runnable dbt projects
- [ ] Join logic correctly reflects relationship cardinality
- [ ] Generated tests (unique, not_null, relationships) pass

---

## Phase 5: Validation Layer

### Objective
Implement comprehensive validation at every stage: input, design, and output.

### Directory Structure to Create
```
core/
├── validators/                # EXPAND (currently empty)
│   ├── __init__.py
│   ├── schema_validator.py   # Input schema validation
│   ├── data_validator.py     # Data quality validation
│   ├── design_validator.py   # Model design validation
│   └── output_validator.py   # Generated code validation
```

### Tasks

#### 5.1 Schema Validator (`core/validators/schema_validator.py`)
- [ ] Connection validation
- [ ] Schema existence validation
- [ ] Table/column accessibility validation
- [ ] Permission validation

#### 5.2 Data Validator (`core/validators/data_validator.py`)
- [ ] Data quality rules engine
- [ ] Completeness checks (null thresholds)
- [ ] Uniqueness checks (duplicate detection)
- [ ] Referential integrity checks
- [ ] Data type consistency checks

#### 5.3 Design Validator (`core/validators/design_validator.py`)
- [ ] All source columns accounted for
- [ ] No orphan tables in design
- [ ] Valid relationship definitions
- [ ] Proper key definitions
- [ ] Type compatibility checks

#### 5.4 Output Validator (`core/validators/output_validator.py`)
- [ ] YAML syntax validation
- [ ] SQL syntax validation (using sqlparse)
- [ ] dbt ref() and source() validation
- [ ] Circular dependency detection
- [ ] Test definition validation

### Commit Milestone
```
feat(validators): add comprehensive validation layer

- Add SchemaValidator for input validation
- Add DataValidator with quality rules engine
- Add DesignValidator for model design checks
- Add OutputValidator for generated code validation
```

### Success Criteria
- [ ] Catches 100% of invalid inputs before processing
- [ ] Design validation prevents invalid schemas
- [ ] Output validation catches all SQL syntax errors
- [ ] Clear, actionable error messages

---

## Phase 6: Integration & Enhanced Workflow

### Objective
Integrate all components into a cohesive LangGraph workflow with proper node sequencing.

### Directory Structure to Modify
```
core/
├── graph/
│   ├── __init__.py
│   ├── modeling_graph.py     # MAJOR REFACTOR
│   └── nodes/                # NEW: Modular nodes
│       ├── __init__.py
│       ├── discovery.py      # Schema discovery nodes
│       ├── profiling.py      # Data profiling nodes
│       ├── analysis.py       # Analysis nodes (FD, keys, types)
│       ├── normalization.py  # Normalization nodes
│       ├── design.py         # LLM design nodes
│       ├── generation.py     # Code generation nodes
│       └── validation.py     # Validation nodes
│
├── prompts/
│   ├── __init__.py
│   └── modeling.py           # ENHANCE: Better prompts with analysis
```

### Tasks

#### 6.1 Modularize Workflow Nodes
- [ ] Extract discovery logic to `nodes/discovery.py`
- [ ] Extract profiling logic to `nodes/profiling.py`
- [ ] Create analysis nodes in `nodes/analysis.py`
- [ ] Create normalization nodes in `nodes/normalization.py`
- [ ] Extract design logic to `nodes/design.py`
- [ ] Extract generation logic to `nodes/generation.py`
- [ ] Create validation nodes in `nodes/validation.py`

#### 6.2 Refactor modeling_graph.py
- [ ] New workflow state with analysis results
- [ ] Add analysis nodes after profiling
- [ ] Add normalization detection before design
- [ ] Add validation nodes before/after generation
- [ ] Conditional routing based on analysis results

#### 6.3 Enhance Prompts (`core/prompts/modeling.py`)
- [ ] Include FD analysis in prompts
- [ ] Include key recommendations
- [ ] Include violation reports
- [ ] Include relationship graphs
- [ ] Include semantic type mappings
- [ ] Remove hardcoded limits (15 columns, 3 tables)

#### 6.4 API Integration
- [ ] Update FastAPI routes for new workflow
- [ ] Add progress streaming endpoints
- [ ] Add analysis results endpoints
- [ ] Add validation error endpoints

### Commit Milestone
```
feat(workflow): integrate all components into enhanced LangGraph workflow

- Modularize workflow into separate node files
- Add analysis and normalization nodes to workflow
- Add validation checkpoints throughout pipeline
- Enhance LLM prompts with algorithmic analysis results
- Update API endpoints for new workflow
```

### Success Criteria
- [ ] End-to-end workflow completes successfully
- [ ] Analysis results visible in workflow state
- [ ] Validation errors halt workflow with clear messages
- [ ] LLM receives rich context from algorithmic analysis
- [ ] API endpoints return proper progress updates

---

## Testing Strategy

### Test Structure
```
tests/
├── unit/
│   ├── models/               # Domain model tests
│   ├── analysis/             # Analysis engine tests
│   ├── normalization/        # Normalization tests
│   ├── generators/           # Generator tests
│   └── validators/           # Validator tests
│
├── integration/
│   ├── test_workflow.py      # Full workflow tests
│   └── test_strategies.py    # Strategy-specific tests
│
├── fixtures/
│   ├── schemas/              # Test schema definitions
│   ├── profiles/             # Sample profile data
│   └── expected/             # Golden file outputs
│
└── conftest.py               # Shared fixtures
```

### Test Data Scenarios
1. **e_commerce**: Classic normalized e-commerce (orders, products, customers)
2. **denormalized_flat**: Single flat table with all violations
3. **already_normalized**: Well-designed 3NF schema
4. **data_vault_source**: Source for Data Vault modeling
5. **edge_cases**: Empty tables, wide tables, circular FKs

---

## Dependency Additions

Add to `pyproject.toml`:
```toml
[project.dependencies]
# Existing...
networkx = "^3.2"          # Relationship graphs
scipy = "^1.11"            # Statistical analysis
rapidfuzz = "^3.5"         # Fuzzy string matching
phonenumbers = "^8.13"     # Phone validation
email-validator = "^2.1"   # Email validation
python-dateutil = "^2.8"   # Date parsing
sqlparse = "^0.4"          # SQL validation
```

---

## Execution Timeline

| Phase | Duration | Agents | Parallel Tasks |
|-------|----------|--------|----------------|
| Phase 1 | 2-3 days | 3-4 | Models, Profiler, Types |
| Phase 2 | 3-4 days | 4-5 | Pattern, Type, FD, Key, Relationship |
| Phase 3 | 2-3 days | 3-4 | Violations, Decomposer, Normalizers |
| Phase 4 | 3-4 days | 4-5 | Join, Star, 3NF, DataVault, dbt |
| Phase 5 | 2-3 days | 4 | Schema, Data, Design, Output validators |
| Phase 6 | 2-3 days | 3-4 | Nodes, Graph, Prompts, API |

**Total Estimated: 14-20 days with parallel agent execution**

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| FD detection performance on large tables | Sampling with confidence intervals |
| LLM inconsistency in design | Validation layer catches issues |
| Breaking existing functionality | Comprehensive test coverage before changes |
| Complex merge conflicts | Atomic commits per component |

---

## Next Steps

1. **Approve this plan** - Review and confirm phases
2. **Initialize swarm** - Set up multi-agent coordination
3. **Execute Phase 1** - Start with domain models
4. **Commit milestone** - Git commit after Phase 1 completion
5. **Iterate** - Continue through phases with commits

---

*Document Version: 1.0*
*Last Updated: January 2026*
