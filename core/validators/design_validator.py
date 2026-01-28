"""
Data model design validator.

This module provides validation for data model designs, ensuring they conform
to the rules and best practices of their chosen modeling strategy (Star Schema,
3NF, Data Vault, etc.).

The validator checks for:
- Strategy-specific requirements (fact tables, dimensions, hubs, etc.)
- Common design issues (orphan tables, circular references, naming)
- Key coverage and relationship integrity
- Design metrics and quality scores
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

from core.models.schema import Table, Column, ForeignKeyRelationship
from core.models.design import (
    ModelDesign,
    DesignedTable,
    TableRole,
    ColumnRole,
    ModelingStrategy,
)
from core.models.analysis import FunctionalDependency, CandidateKey


class IssueSeverity(str, Enum):
    """Severity level for design issues."""

    ERROR = "error"      # Critical issue that must be fixed
    WARNING = "warning"  # Important issue that should be addressed
    INFO = "info"        # Informational note or suggestion


class IssueCategory(str, Enum):
    """Category of design issue."""

    SCHEMA_STRUCTURE = "schema_structure"
    RELATIONSHIP = "relationship"
    KEY_CONSTRAINT = "key_constraint"
    NAMING = "naming"
    NORMALIZATION = "normalization"
    STRATEGY_COMPLIANCE = "strategy_compliance"
    DATA_VAULT = "data_vault"
    STAR_SCHEMA = "star_schema"


@dataclass
class DesignIssue:
    """
    Represents an issue found during design validation.

    Attributes:
        severity: How critical the issue is (error/warning/info).
        category: Classification of the issue type.
        table_name: Name of the table where issue was found (if applicable).
        description: Human-readable description of the issue.
        fix_suggestion: Suggested action to resolve the issue.
    """

    severity: IssueSeverity
    category: IssueCategory
    table_name: Optional[str]
    description: str
    fix_suggestion: Optional[str] = None

    def __str__(self) -> str:
        """Return a formatted string representation."""
        table_info = f" [{self.table_name}]" if self.table_name else ""
        return f"[{self.severity.value.upper()}]{table_info} {self.description}"


@dataclass
class DesignValidationReport:
    """
    Complete validation report for a model design.

    Attributes:
        strategy: The modeling strategy being validated against.
        is_valid: Whether the design passes validation (no errors).
        issues: List of all issues found during validation.
        metrics: Dictionary of design metrics and statistics.
    """

    strategy: ModelingStrategy
    is_valid: bool
    issues: List[DesignIssue] = field(default_factory=list)
    metrics: Dict[str, any] = field(default_factory=dict)

    @property
    def error_count(self) -> int:
        """Count of error-level issues."""
        return sum(1 for i in self.issues if i.severity == IssueSeverity.ERROR)

    @property
    def warning_count(self) -> int:
        """Count of warning-level issues."""
        return sum(1 for i in self.issues if i.severity == IssueSeverity.WARNING)

    @property
    def info_count(self) -> int:
        """Count of info-level issues."""
        return sum(1 for i in self.issues if i.severity == IssueSeverity.INFO)

    def get_issues_by_severity(self, severity: IssueSeverity) -> List[DesignIssue]:
        """Get all issues of a specific severity level."""
        return [i for i in self.issues if i.severity == severity]

    def get_issues_by_category(self, category: IssueCategory) -> List[DesignIssue]:
        """Get all issues of a specific category."""
        return [i for i in self.issues if i.category == category]

    def get_issues_for_table(self, table_name: str) -> List[DesignIssue]:
        """Get all issues related to a specific table."""
        return [i for i in self.issues if i.table_name == table_name]


class DesignValidator:
    """
    Validates data model designs against their chosen modeling strategy.

    This validator checks that designs conform to the rules and best practices
    of the specified modeling strategy, identifies common design issues, and
    calculates design quality metrics.

    Example:
        >>> validator = DesignValidator(ModelingStrategy.STAR_SCHEMA)
        >>> report = validator.validate_design(my_design)
        >>> if not report.is_valid:
        ...     for issue in report.get_issues_by_severity(IssueSeverity.ERROR):
        ...         print(issue)
    """

    def __init__(self, strategy: ModelingStrategy):
        """
        Initialize the validator with a modeling strategy.

        Args:
            strategy: The modeling strategy to validate against.
        """
        self.strategy = strategy

    def validate_design(
        self,
        design: ModelDesign,
        functional_dependencies: Optional[List[FunctionalDependency]] = None,
    ) -> DesignValidationReport:
        """
        Validate a model design and return a comprehensive report.

        This method runs all applicable validations based on the modeling
        strategy and collects all issues found.

        Args:
            design: The model design to validate.
            functional_dependencies: Optional list of FDs for 3NF validation.

        Returns:
            A DesignValidationReport containing all issues and metrics.
        """
        issues: List[DesignIssue] = []

        # Run common validations
        issues.extend(self._check_orphan_tables(design))
        issues.extend(self._check_circular_references(design))
        issues.extend(self._check_naming_consistency(design))
        issues.extend(self._check_key_coverage(design))

        # Run strategy-specific validations
        if self.strategy == ModelingStrategy.STAR_SCHEMA:
            issues.extend(self._validate_star_schema(design))
        elif self.strategy == ModelingStrategy.SNOWFLAKE:
            issues.extend(self._validate_star_schema(design, allow_snowflake=True))
        elif self.strategy == ModelingStrategy.NORMALIZED_3NF:
            issues.extend(self._validate_3nf(design, functional_dependencies or []))
        elif self.strategy == ModelingStrategy.DATA_VAULT:
            issues.extend(self._validate_data_vault(design))
        elif self.strategy == ModelingStrategy.ONE_BIG_TABLE:
            issues.extend(self._validate_one_big_table(design))

        # Calculate metrics
        metrics = self._calculate_metrics(design)

        # Determine overall validity (no errors)
        is_valid = not any(i.severity == IssueSeverity.ERROR for i in issues)

        return DesignValidationReport(
            strategy=self.strategy,
            is_valid=is_valid,
            issues=issues,
            metrics=metrics,
        )

    # =========================================================================
    # Strategy-Specific Validations
    # =========================================================================

    def _validate_star_schema(
        self,
        design: ModelDesign,
        allow_snowflake: bool = False,
    ) -> List[DesignIssue]:
        """
        Validate star schema design requirements.

        Checks:
        - At least one fact table exists
        - Facts have foreign keys to all dimensions
        - Dimensions have surrogate keys
        - No snowflaking (unless allow_snowflake=True)

        Args:
            design: The model design to validate.
            allow_snowflake: If True, allow dimension-to-dimension relationships.

        Returns:
            List of design issues found.
        """
        issues: List[DesignIssue] = []

        facts = design.get_facts()
        dimensions = design.get_dimensions()

        # Check for at least one fact table
        if not facts:
            issues.append(DesignIssue(
                severity=IssueSeverity.ERROR,
                category=IssueCategory.STAR_SCHEMA,
                table_name=None,
                description="Star schema must have at least one fact table",
                fix_suggestion="Add a fact table with role=TableRole.FACT containing measures and dimension keys",
            ))

        # Check for at least one dimension
        if not dimensions:
            issues.append(DesignIssue(
                severity=IssueSeverity.WARNING,
                category=IssueCategory.STAR_SCHEMA,
                table_name=None,
                description="Star schema should have dimension tables",
                fix_suggestion="Add dimension tables with role=TableRole.DIMENSION containing descriptive attributes",
            ))

        # Build dimension name set for FK validation
        dimension_names = {d.name for d in dimensions}

        # Validate each fact table
        for fact in facts:
            # Check that fact has measures
            measure_cols = fact.get_columns_by_role(ColumnRole.MEASURE)
            if not measure_cols and not fact.measures:
                issues.append(DesignIssue(
                    severity=IssueSeverity.WARNING,
                    category=IssueCategory.STAR_SCHEMA,
                    table_name=fact.name,
                    description="Fact table has no measures defined",
                    fix_suggestion="Add measure columns with role=ColumnRole.MEASURE for aggregation",
                ))

            # Check that fact has foreign keys to dimensions
            fk_cols = fact.get_columns_by_role(ColumnRole.FOREIGN_KEY)
            referenced_dims = {
                col.references_table for col in fk_cols
                if col.references_table in dimension_names
            }

            missing_dims = dimension_names - referenced_dims
            if missing_dims and dimensions:
                issues.append(DesignIssue(
                    severity=IssueSeverity.WARNING,
                    category=IssueCategory.STAR_SCHEMA,
                    table_name=fact.name,
                    description=f"Fact table missing FK to dimensions: {', '.join(sorted(missing_dims))}",
                    fix_suggestion="Add foreign key columns referencing all dimension tables",
                ))

            # Check grain is defined
            if not fact.grain:
                issues.append(DesignIssue(
                    severity=IssueSeverity.INFO,
                    category=IssueCategory.STAR_SCHEMA,
                    table_name=fact.name,
                    description="Fact table grain not documented",
                    fix_suggestion="Define the grain property describing what each row represents",
                ))

        # Validate each dimension table
        for dim in dimensions:
            # Check for surrogate key
            surrogate_cols = dim.get_columns_by_role(ColumnRole.SURROGATE_KEY)
            if not surrogate_cols:
                issues.append(DesignIssue(
                    severity=IssueSeverity.WARNING,
                    category=IssueCategory.STAR_SCHEMA,
                    table_name=dim.name,
                    description="Dimension table missing surrogate key",
                    fix_suggestion="Add an auto-generated surrogate key column with role=ColumnRole.SURROGATE_KEY",
                ))

            # Check for natural/business key
            natural_cols = dim.get_columns_by_role(ColumnRole.NATURAL_KEY)
            business_cols = dim.get_columns_by_role(ColumnRole.BUSINESS_KEY)
            if not natural_cols and not business_cols:
                issues.append(DesignIssue(
                    severity=IssueSeverity.INFO,
                    category=IssueCategory.STAR_SCHEMA,
                    table_name=dim.name,
                    description="Dimension table has no natural or business key defined",
                    fix_suggestion="Identify and mark the natural business key columns",
                ))

        # Check for snowflaking (dimension-to-dimension relationships)
        if not allow_snowflake:
            for rel in design.relationships:
                from_table = design.get_table(rel.from_table)
                to_table = design.get_table(rel.to_table)

                if (from_table and to_table and
                    from_table.role == TableRole.DIMENSION and
                    to_table.role == TableRole.DIMENSION):
                    issues.append(DesignIssue(
                        severity=IssueSeverity.WARNING,
                        category=IssueCategory.STAR_SCHEMA,
                        table_name=rel.from_table,
                        description=f"Snowflaking detected: {rel.from_table} -> {rel.to_table}",
                        fix_suggestion="Consider denormalizing into a single dimension for query performance",
                    ))

        return issues

    def _validate_3nf(
        self,
        design: ModelDesign,
        fds: List[FunctionalDependency],
    ) -> List[DesignIssue]:
        """
        Validate Third Normal Form (3NF) design requirements.

        Checks:
        - No transitive dependencies
        - No partial dependencies
        - All determinants are candidate keys or superkeys

        Args:
            design: The model design to validate.
            fds: List of functional dependencies to check.

        Returns:
            List of design issues found.
        """
        issues: List[DesignIssue] = []

        # Group FDs by table (using dependent column to infer table)
        table_fds: Dict[str, List[FunctionalDependency]] = {}
        for fd in fds:
            # Try to find which table this FD belongs to
            for table in design.tables:
                col_names = {c.name for c in table.columns}
                if fd.dependent in col_names and all(d in col_names for d in fd.determinant):
                    if table.name not in table_fds:
                        table_fds[table.name] = []
                    table_fds[table.name].append(fd)
                    break

        # Validate each table
        for table in design.tables:
            table_fd_list = table_fds.get(table.name, [])
            pk_cols = set(table.primary_key_columns)

            for fd in table_fd_list:
                determinant_set = set(fd.determinant)

                # Check for partial dependencies (2NF violation)
                if fd.is_partial:
                    issues.append(DesignIssue(
                        severity=IssueSeverity.ERROR,
                        category=IssueCategory.NORMALIZATION,
                        table_name=table.name,
                        description=f"Partial dependency: {fd} - dependent on part of primary key",
                        fix_suggestion=f"Move {fd.dependent} to a separate table with key {fd.determinant}",
                    ))

                # Check for transitive dependencies (3NF violation)
                if fd.is_transitive:
                    issues.append(DesignIssue(
                        severity=IssueSeverity.ERROR,
                        category=IssueCategory.NORMALIZATION,
                        table_name=table.name,
                        description=f"Transitive dependency: {fd} - non-key determines non-key",
                        fix_suggestion=f"Create a new table for {fd.determinant} -> {fd.dependent}",
                    ))

                # Check that determinant is candidate key or superkey
                if not fd.is_trivial and not fd.is_partial and not fd.is_transitive:
                    if determinant_set != pk_cols and not determinant_set.issuperset(pk_cols):
                        # Check if determinant could be a candidate key
                        is_likely_key = self._is_likely_candidate_key(table, fd.determinant)
                        if not is_likely_key:
                            issues.append(DesignIssue(
                                severity=IssueSeverity.WARNING,
                                category=IssueCategory.NORMALIZATION,
                                table_name=table.name,
                                description=f"Non-key determinant: {fd.determinant} -> {fd.dependent}",
                                fix_suggestion="Verify determinant is a candidate key or extract to separate table",
                            ))

        # Check for tables with no primary key
        for table in design.tables:
            if not table.primary_key_columns:
                issues.append(DesignIssue(
                    severity=IssueSeverity.ERROR,
                    category=IssueCategory.NORMALIZATION,
                    table_name=table.name,
                    description="Table has no primary key defined",
                    fix_suggestion="Every 3NF table must have a primary key",
                ))

        return issues

    def _validate_data_vault(self, design: ModelDesign) -> List[DesignIssue]:
        """
        Validate Data Vault design requirements.

        Checks:
        - Hubs have business keys
        - Links connect multiple hubs
        - Satellites are attached to hub or link
        - Proper hash keys are present

        Args:
            design: The model design to validate.

        Returns:
            List of design issues found.
        """
        issues: List[DesignIssue] = []

        hubs = design.get_hubs()
        links = design.get_links()
        satellites = design.get_satellites()

        # Check for at least one hub
        if not hubs:
            issues.append(DesignIssue(
                severity=IssueSeverity.ERROR,
                category=IssueCategory.DATA_VAULT,
                table_name=None,
                description="Data Vault must have at least one hub table",
                fix_suggestion="Add hub tables with role=TableRole.HUB for core business entities",
            ))

        # Validate each hub
        hub_names = {h.name for h in hubs}
        for hub in hubs:
            # Check for business key
            business_key_cols = hub.get_columns_by_role(ColumnRole.BUSINESS_KEY)
            if not business_key_cols:
                issues.append(DesignIssue(
                    severity=IssueSeverity.ERROR,
                    category=IssueCategory.DATA_VAULT,
                    table_name=hub.name,
                    description="Hub table missing business key",
                    fix_suggestion="Add business key column(s) with role=ColumnRole.BUSINESS_KEY",
                ))

            # Check for hash key (surrogate)
            surrogate_cols = hub.get_columns_by_role(ColumnRole.SURROGATE_KEY)
            if not surrogate_cols:
                issues.append(DesignIssue(
                    severity=IssueSeverity.WARNING,
                    category=IssueCategory.DATA_VAULT,
                    table_name=hub.name,
                    description="Hub table missing hash key (surrogate key)",
                    fix_suggestion="Add a hash-based surrogate key for efficient joins",
                ))

            # Check for load date (audit column)
            audit_cols = hub.get_columns_by_role(ColumnRole.AUDIT)
            if not audit_cols:
                issues.append(DesignIssue(
                    severity=IssueSeverity.INFO,
                    category=IssueCategory.DATA_VAULT,
                    table_name=hub.name,
                    description="Hub table missing audit columns (load_date, record_source)",
                    fix_suggestion="Add audit columns with role=ColumnRole.AUDIT",
                ))

        # Validate each link
        for link in links:
            # Check that link connects multiple hubs
            fk_cols = link.get_columns_by_role(ColumnRole.FOREIGN_KEY)
            connected_hubs = {
                col.references_table for col in fk_cols
                if col.references_table in hub_names
            }

            if len(connected_hubs) < 2:
                issues.append(DesignIssue(
                    severity=IssueSeverity.ERROR,
                    category=IssueCategory.DATA_VAULT,
                    table_name=link.name,
                    description=f"Link table must connect at least 2 hubs, found {len(connected_hubs)}",
                    fix_suggestion="Add foreign keys to at least 2 hub tables",
                ))

            # Check for hash key
            surrogate_cols = link.get_columns_by_role(ColumnRole.SURROGATE_KEY)
            if not surrogate_cols:
                issues.append(DesignIssue(
                    severity=IssueSeverity.WARNING,
                    category=IssueCategory.DATA_VAULT,
                    table_name=link.name,
                    description="Link table missing hash key",
                    fix_suggestion="Add a hash-based surrogate key derived from connected hub keys",
                ))

        # Validate each satellite
        link_names = {l.name for l in links}
        parent_names = hub_names | link_names

        for sat in satellites:
            # Check that satellite is attached to a hub or link
            fk_cols = sat.get_columns_by_role(ColumnRole.FOREIGN_KEY)
            parent_refs = {
                col.references_table for col in fk_cols
                if col.references_table in parent_names
            }

            if not parent_refs:
                issues.append(DesignIssue(
                    severity=IssueSeverity.ERROR,
                    category=IssueCategory.DATA_VAULT,
                    table_name=sat.name,
                    description="Satellite must reference a hub or link table",
                    fix_suggestion="Add a foreign key column referencing the parent hub or link",
                ))
            elif len(parent_refs) > 1:
                issues.append(DesignIssue(
                    severity=IssueSeverity.WARNING,
                    category=IssueCategory.DATA_VAULT,
                    table_name=sat.name,
                    description="Satellite references multiple parents - consider splitting",
                    fix_suggestion="A satellite should typically reference only one hub or link",
                ))

            # Check for audit columns
            audit_cols = sat.get_columns_by_role(ColumnRole.AUDIT)
            if not audit_cols:
                issues.append(DesignIssue(
                    severity=IssueSeverity.INFO,
                    category=IssueCategory.DATA_VAULT,
                    table_name=sat.name,
                    description="Satellite missing audit columns (load_date, load_end_date)",
                    fix_suggestion="Add audit columns for temporal tracking",
                ))

            # Check for descriptive attributes
            attr_cols = sat.get_columns_by_role(ColumnRole.ATTRIBUTE)
            if not attr_cols:
                issues.append(DesignIssue(
                    severity=IssueSeverity.WARNING,
                    category=IssueCategory.DATA_VAULT,
                    table_name=sat.name,
                    description="Satellite has no attribute columns",
                    fix_suggestion="Add descriptive attribute columns that change over time",
                ))

        return issues

    def _validate_one_big_table(self, design: ModelDesign) -> List[DesignIssue]:
        """
        Validate One Big Table (OBT) design requirements.

        This is a fully denormalized approach, so we mainly check for
        completeness and warn about potential issues.

        Args:
            design: The model design to validate.

        Returns:
            List of design issues found.
        """
        issues: List[DesignIssue] = []

        if len(design.tables) > 1:
            issues.append(DesignIssue(
                severity=IssueSeverity.WARNING,
                category=IssueCategory.STRATEGY_COMPLIANCE,
                table_name=None,
                description=f"One Big Table design has {len(design.tables)} tables",
                fix_suggestion="Consider consolidating into a single denormalized table",
            ))

        for table in design.tables:
            # Check for very wide tables
            if table.column_count > 100:
                issues.append(DesignIssue(
                    severity=IssueSeverity.WARNING,
                    category=IssueCategory.STRATEGY_COMPLIANCE,
                    table_name=table.name,
                    description=f"Table has {table.column_count} columns - may impact query performance",
                    fix_suggestion="Monitor query performance and consider column pruning",
                ))

            # Check for primary key
            if not table.primary_key_columns:
                issues.append(DesignIssue(
                    severity=IssueSeverity.ERROR,
                    category=IssueCategory.KEY_CONSTRAINT,
                    table_name=table.name,
                    description="Table missing primary key",
                    fix_suggestion="Add a primary key for row identification",
                ))

        return issues

    # =========================================================================
    # Common Validations
    # =========================================================================

    def _check_orphan_tables(self, design: ModelDesign) -> List[DesignIssue]:
        """
        Check for tables with no relationships to other tables.

        Args:
            design: The model design to validate.

        Returns:
            List of design issues for orphan tables.
        """
        issues: List[DesignIssue] = []

        if len(design.tables) <= 1:
            return issues

        # Build set of connected tables
        connected_tables: Set[str] = set()
        for rel in design.relationships:
            connected_tables.add(rel.from_table)
            connected_tables.add(rel.to_table)

        # Find orphans
        for table in design.tables:
            if table.name not in connected_tables:
                # Staging tables are often orphans intentionally
                if table.role == TableRole.STAGING:
                    issues.append(DesignIssue(
                        severity=IssueSeverity.INFO,
                        category=IssueCategory.RELATIONSHIP,
                        table_name=table.name,
                        description="Staging table has no relationships (expected)",
                        fix_suggestion=None,
                    ))
                else:
                    issues.append(DesignIssue(
                        severity=IssueSeverity.WARNING,
                        category=IssueCategory.RELATIONSHIP,
                        table_name=table.name,
                        description="Table has no relationships to other tables",
                        fix_suggestion="Add relationships or verify this is intentional",
                    ))

        return issues

    def _check_circular_references(self, design: ModelDesign) -> List[DesignIssue]:
        """
        Check for circular reference chains in relationships.

        Uses DFS to detect cycles in the relationship graph.

        Args:
            design: The model design to validate.

        Returns:
            List of design issues for circular references.
        """
        issues: List[DesignIssue] = []

        # Build adjacency list
        graph: Dict[str, List[str]] = {}
        for table in design.tables:
            graph[table.name] = []

        for rel in design.relationships:
            if rel.from_table in graph:
                graph[rel.from_table].append(rel.to_table)

        # DFS to find cycles
        visited: Set[str] = set()
        rec_stack: Set[str] = set()
        cycles_found: List[List[str]] = []

        def dfs(node: str, path: List[str]) -> None:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor, path.copy())
                elif neighbor in rec_stack:
                    # Found cycle
                    cycle_start = path.index(neighbor) if neighbor in path else -1
                    if cycle_start >= 0:
                        cycle = path[cycle_start:] + [neighbor]
                        cycles_found.append(cycle)

            rec_stack.discard(node)

        for table_name in graph:
            if table_name not in visited:
                dfs(table_name, [])

        # Report cycles
        seen_cycles: Set[frozenset] = set()
        for cycle in cycles_found:
            cycle_set = frozenset(cycle)
            if cycle_set not in seen_cycles:
                seen_cycles.add(cycle_set)
                cycle_str = " -> ".join(cycle)
                issues.append(DesignIssue(
                    severity=IssueSeverity.WARNING,
                    category=IssueCategory.RELATIONSHIP,
                    table_name=cycle[0],
                    description=f"Circular reference detected: {cycle_str}",
                    fix_suggestion="Review relationship design - cycles may cause issues with referential integrity",
                ))

        return issues

    def _check_naming_consistency(self, design: ModelDesign) -> List[DesignIssue]:
        """
        Check for naming consistency across the design.

        Validates:
        - Consistent case usage (snake_case preferred)
        - Table name prefixes/suffixes match roles
        - Column naming patterns

        Args:
            design: The model design to validate.

        Returns:
            List of design issues for naming problems.
        """
        issues: List[DesignIssue] = []

        # Expected prefixes/suffixes by role
        role_patterns = {
            TableRole.FACT: (["fact_", "fct_"], ["_fact", "_fct"]),
            TableRole.DIMENSION: (["dim_"], ["_dim"]),
            TableRole.HUB: (["hub_", "h_"], ["_hub", "_h"]),
            TableRole.LINK: (["link_", "lnk_", "l_"], ["_link", "_lnk", "_l"]),
            TableRole.SATELLITE: (["sat_", "s_"], ["_sat", "_s"]),
            TableRole.STAGING: (["stg_", "staging_"], ["_stg", "_staging"]),
        }

        for table in design.tables:
            table_lower = table.name.lower()

            # Check snake_case
            if table.name != table.name.lower() and "_" not in table.name:
                issues.append(DesignIssue(
                    severity=IssueSeverity.INFO,
                    category=IssueCategory.NAMING,
                    table_name=table.name,
                    description="Table name not in snake_case format",
                    fix_suggestion=f"Consider renaming to: {self._to_snake_case(table.name)}",
                ))

            # Check role-based naming
            if table.role in role_patterns:
                prefixes, suffixes = role_patterns[table.role]
                has_prefix = any(table_lower.startswith(p) for p in prefixes)
                has_suffix = any(table_lower.endswith(s) for s in suffixes)

                if not has_prefix and not has_suffix:
                    issues.append(DesignIssue(
                        severity=IssueSeverity.INFO,
                        category=IssueCategory.NAMING,
                        table_name=table.name,
                        description=f"Table name doesn't follow {table.role.value} naming convention",
                        fix_suggestion=f"Consider prefix: {prefixes[0]} or suffix: {suffixes[0]}",
                    ))

            # Check column naming
            for col in table.columns:
                if col.name != col.name.lower() and "_" not in col.name:
                    issues.append(DesignIssue(
                        severity=IssueSeverity.INFO,
                        category=IssueCategory.NAMING,
                        table_name=table.name,
                        description=f"Column '{col.name}' not in snake_case format",
                        fix_suggestion=f"Consider: {self._to_snake_case(col.name)}",
                    ))

        return issues

    def _check_key_coverage(self, design: ModelDesign) -> List[DesignIssue]:
        """
        Check that all tables have appropriate key coverage.

        Validates:
        - All tables have a primary key
        - Foreign keys reference existing tables
        - Foreign key columns have proper role assigned

        Args:
            design: The model design to validate.

        Returns:
            List of design issues for key problems.
        """
        issues: List[DesignIssue] = []

        table_names = {t.name for t in design.tables}

        for table in design.tables:
            # Check for primary key
            pk_cols = table.primary_key_columns
            if not pk_cols:
                # Staging tables might not have PKs
                severity = (
                    IssueSeverity.INFO if table.role == TableRole.STAGING
                    else IssueSeverity.WARNING
                )
                issues.append(DesignIssue(
                    severity=severity,
                    category=IssueCategory.KEY_CONSTRAINT,
                    table_name=table.name,
                    description="Table has no primary key defined",
                    fix_suggestion="Mark appropriate column(s) with is_primary_key=True",
                ))

            # Check FK references
            fk_cols = table.get_columns_by_role(ColumnRole.FOREIGN_KEY)
            for fk in fk_cols:
                if fk.references_table and fk.references_table not in table_names:
                    issues.append(DesignIssue(
                        severity=IssueSeverity.ERROR,
                        category=IssueCategory.KEY_CONSTRAINT,
                        table_name=table.name,
                        description=f"FK column '{fk.name}' references non-existent table '{fk.references_table}'",
                        fix_suggestion="Add the referenced table or correct the reference",
                    ))

            # Check for FK columns without proper role
            for col in table.columns:
                if col.references_table and col.role != ColumnRole.FOREIGN_KEY:
                    issues.append(DesignIssue(
                        severity=IssueSeverity.INFO,
                        category=IssueCategory.KEY_CONSTRAINT,
                        table_name=table.name,
                        description=f"Column '{col.name}' has reference but role is not FOREIGN_KEY",
                        fix_suggestion="Set role=ColumnRole.FOREIGN_KEY for FK columns",
                    ))

        # Check relationships reference existing tables
        for rel in design.relationships:
            if rel.from_table not in table_names:
                issues.append(DesignIssue(
                    severity=IssueSeverity.ERROR,
                    category=IssueCategory.RELATIONSHIP,
                    table_name=None,
                    description=f"Relationship references non-existent table '{rel.from_table}'",
                    fix_suggestion="Add the table or remove the relationship",
                ))

            if rel.to_table not in table_names:
                issues.append(DesignIssue(
                    severity=IssueSeverity.ERROR,
                    category=IssueCategory.RELATIONSHIP,
                    table_name=None,
                    description=f"Relationship references non-existent table '{rel.to_table}'",
                    fix_suggestion="Add the table or remove the relationship",
                ))

        return issues

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _calculate_metrics(self, design: ModelDesign) -> Dict[str, any]:
        """
        Calculate design quality metrics.

        Args:
            design: The model design to analyze.

        Returns:
            Dictionary of metric names to values.
        """
        table_count = len(design.tables)

        if table_count == 0:
            return {
                "table_count": 0,
                "avg_columns_per_table": 0,
                "relationship_count": 0,
                "relationship_density": 0,
                "tables_with_pk": 0,
                "tables_with_pk_percentage": 0,
            }

        total_columns = sum(len(t.columns) for t in design.tables)
        avg_columns = total_columns / table_count if table_count > 0 else 0

        relationship_count = len(design.relationships)
        max_relationships = table_count * (table_count - 1)  # Directed graph max
        relationship_density = (
            relationship_count / max_relationships if max_relationships > 0 else 0
        )

        tables_with_pk = sum(1 for t in design.tables if t.primary_key_columns)
        pk_percentage = (tables_with_pk / table_count * 100) if table_count > 0 else 0

        # Count tables by role
        role_counts = {}
        for table in design.tables:
            role = table.role.value
            role_counts[role] = role_counts.get(role, 0) + 1

        return {
            "table_count": table_count,
            "total_columns": total_columns,
            "avg_columns_per_table": round(avg_columns, 2),
            "relationship_count": relationship_count,
            "relationship_density": round(relationship_density, 4),
            "tables_with_pk": tables_with_pk,
            "tables_with_pk_percentage": round(pk_percentage, 2),
            "role_distribution": role_counts,
        }

    def _is_likely_candidate_key(
        self,
        table: DesignedTable,
        columns: List[str],
    ) -> bool:
        """
        Heuristically check if columns could be a candidate key.

        Args:
            table: The table containing the columns.
            columns: Column names to check.

        Returns:
            True if columns appear to be a candidate key.
        """
        col_set = set(columns)

        for col in table.columns:
            if col.name in col_set:
                # Keys typically have key-like roles
                if col.role in {
                    ColumnRole.SURROGATE_KEY,
                    ColumnRole.NATURAL_KEY,
                    ColumnRole.BUSINESS_KEY,
                }:
                    return True
                # Non-nullable unique columns suggest key
                if not col.is_nullable and col.is_primary_key:
                    return True

        return False

    @staticmethod
    def _to_snake_case(name: str) -> str:
        """
        Convert a name to snake_case.

        Args:
            name: The name to convert.

        Returns:
            Snake case version of the name.
        """
        result = []
        for i, char in enumerate(name):
            if char.isupper() and i > 0:
                result.append("_")
            result.append(char.lower())
        return "".join(result)
