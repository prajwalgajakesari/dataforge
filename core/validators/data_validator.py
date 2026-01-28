"""
Data quality validation for database tables and columns.

This module provides comprehensive data quality validation including:
- Null percentage checks
- Uniqueness validation
- Value range validation
- Pattern compliance checks
- Referential integrity validation
- PII exposure detection

The validator can be configured with custom rules and thresholds,
and produces detailed reports with actionable quality scores.
"""

import fnmatch
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, List, Optional, Set

from core.models.schema import Table, Column
from core.models.analysis import ColumnProfile, TableProfile, ColumnStatistics
from core.models.types import SemanticType, PII_TYPES


class CheckType(str, Enum):
    """Types of data quality checks."""

    NULL_PERCENTAGE = "null_percentage"
    UNIQUENESS = "uniqueness"
    VALUE_RANGE = "value_range"
    PATTERN_COMPLIANCE = "pattern_compliance"
    REFERENTIAL_INTEGRITY = "referential_integrity"
    PII_EXPOSURE = "pii_exposure"
    MIN_LENGTH = "min_length"
    MAX_LENGTH = "max_length"
    NON_NEGATIVE = "non_negative"
    FORMAT = "format"


class Severity(str, Enum):
    """Severity levels for data quality issues."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class DataQualityRule:
    """
    A rule for checking data quality.

    Attributes:
        rule_name: Human-readable name for the rule.
        column_pattern: Glob pattern to match column names (e.g., "*_id", "email*").
        check_type: Type of quality check to perform.
        threshold: Threshold value for the check (interpretation depends on check_type).
        severity: Severity level if the rule is violated.
        description: Optional description of what the rule validates.
        enabled: Whether the rule is active.
    """

    rule_name: str
    column_pattern: str
    check_type: CheckType
    threshold: float
    severity: Severity = Severity.MEDIUM
    description: str = ""
    enabled: bool = True

    def matches_column(self, column_name: str) -> bool:
        """Check if a column name matches this rule's pattern."""
        return fnmatch.fnmatch(column_name.lower(), self.column_pattern.lower())


@dataclass
class DataQualityIssue:
    """
    A specific data quality issue found during validation.

    Attributes:
        table: Name of the table where the issue was found.
        column: Name of the column with the issue.
        rule_violated: Name of the rule that was violated.
        actual_value: The actual value or metric found.
        expected_value: The expected value or threshold.
        severity: Severity level of the issue.
        message: Human-readable description of the issue.
        check_type: Type of check that found the issue.
    """

    table: str
    column: str
    rule_violated: str
    actual_value: Any
    expected_value: Any
    severity: Severity
    message: str = ""
    check_type: CheckType = CheckType.NULL_PERCENTAGE


@dataclass
class DataValidationReport:
    """
    Complete data validation report for a table.

    Attributes:
        table_name: Name of the validated table.
        total_checks: Total number of quality checks performed.
        passed: Number of checks that passed.
        failed: Number of checks that failed.
        issues: List of specific quality issues found.
        score: Overall data quality score (0-100).
        columns_checked: Number of columns that were checked.
        rules_applied: List of rule names that were applied.
    """

    table_name: str = ""
    total_checks: int = 0
    passed: int = 0
    failed: int = 0
    issues: List[DataQualityIssue] = field(default_factory=list)
    score: float = 100.0
    columns_checked: int = 0
    rules_applied: List[str] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        """Calculate the pass rate as a percentage."""
        if self.total_checks == 0:
            return 100.0
        return round((self.passed / self.total_checks) * 100, 2)

    @property
    def critical_issues(self) -> List[DataQualityIssue]:
        """Get only critical severity issues."""
        return [i for i in self.issues if i.severity == Severity.CRITICAL]

    @property
    def high_issues(self) -> List[DataQualityIssue]:
        """Get only high severity issues."""
        return [i for i in self.issues if i.severity == Severity.HIGH]

    def add_issue(self, issue: DataQualityIssue) -> None:
        """Add an issue and update counts."""
        self.issues.append(issue)
        self.failed += 1

    def add_passed(self) -> None:
        """Record a passed check."""
        self.passed += 1

    def calculate_score(self) -> float:
        """
        Calculate the overall data quality score.

        Score is weighted by severity:
        - Critical issues: -20 points each
        - High issues: -10 points each
        - Medium issues: -5 points each
        - Low issues: -2 points each
        - Info issues: -0.5 points each
        """
        score = 100.0

        severity_weights = {
            Severity.CRITICAL: 20.0,
            Severity.HIGH: 10.0,
            Severity.MEDIUM: 5.0,
            Severity.LOW: 2.0,
            Severity.INFO: 0.5,
        }

        for issue in self.issues:
            score -= severity_weights.get(issue.severity, 5.0)

        self.score = max(0.0, min(100.0, score))
        return self.score


# Default data quality rules for common patterns
DEFAULT_RULES: List[DataQualityRule] = [
    # ID columns should have no nulls and be unique
    DataQualityRule(
        rule_name="id_no_nulls",
        column_pattern="*_id",
        check_type=CheckType.NULL_PERCENTAGE,
        threshold=0.0,
        severity=Severity.CRITICAL,
        description="ID columns should have no null values",
    ),
    DataQualityRule(
        rule_name="id_uniqueness",
        column_pattern="*_id",
        check_type=CheckType.UNIQUENESS,
        threshold=100.0,
        severity=Severity.HIGH,
        description="ID columns should have unique values",
    ),
    DataQualityRule(
        rule_name="pk_no_nulls",
        column_pattern="id",
        check_type=CheckType.NULL_PERCENTAGE,
        threshold=0.0,
        severity=Severity.CRITICAL,
        description="Primary key columns should have no null values",
    ),
    DataQualityRule(
        rule_name="pk_uniqueness",
        column_pattern="id",
        check_type=CheckType.UNIQUENESS,
        threshold=100.0,
        severity=Severity.CRITICAL,
        description="Primary key columns should have unique values",
    ),

    # Email columns should match email pattern
    DataQualityRule(
        rule_name="email_format",
        column_pattern="*email*",
        check_type=CheckType.PATTERN_COMPLIANCE,
        threshold=95.0,  # 95% should match email pattern
        severity=Severity.MEDIUM,
        description="Email columns should contain valid email formats",
    ),

    # Date columns should be within reasonable range
    DataQualityRule(
        rule_name="date_reasonable_range",
        column_pattern="*date*",
        check_type=CheckType.VALUE_RANGE,
        threshold=100.0,
        severity=Severity.LOW,
        description="Date columns should be within reasonable range (1900-2100)",
    ),
    DataQualityRule(
        rule_name="created_at_range",
        column_pattern="created_at",
        check_type=CheckType.VALUE_RANGE,
        threshold=100.0,
        severity=Severity.LOW,
        description="Created timestamps should be within reasonable range",
    ),
    DataQualityRule(
        rule_name="updated_at_range",
        column_pattern="updated_at",
        check_type=CheckType.VALUE_RANGE,
        threshold=100.0,
        severity=Severity.LOW,
        description="Updated timestamps should be within reasonable range",
    ),

    # Amount/price columns should be non-negative
    DataQualityRule(
        rule_name="amount_non_negative",
        column_pattern="*amount*",
        check_type=CheckType.NON_NEGATIVE,
        threshold=100.0,
        severity=Severity.HIGH,
        description="Amount columns should contain non-negative values",
    ),
    DataQualityRule(
        rule_name="price_non_negative",
        column_pattern="*price*",
        check_type=CheckType.NON_NEGATIVE,
        threshold=100.0,
        severity=Severity.HIGH,
        description="Price columns should contain non-negative values",
    ),
    DataQualityRule(
        rule_name="cost_non_negative",
        column_pattern="*cost*",
        check_type=CheckType.NON_NEGATIVE,
        threshold=100.0,
        severity=Severity.HIGH,
        description="Cost columns should contain non-negative values",
    ),
    DataQualityRule(
        rule_name="total_non_negative",
        column_pattern="*total*",
        check_type=CheckType.NON_NEGATIVE,
        threshold=100.0,
        severity=Severity.MEDIUM,
        description="Total columns should contain non-negative values",
    ),

    # Phone columns should match phone pattern
    DataQualityRule(
        rule_name="phone_format",
        column_pattern="*phone*",
        check_type=CheckType.PATTERN_COMPLIANCE,
        threshold=90.0,
        severity=Severity.LOW,
        description="Phone columns should contain valid phone formats",
    ),

    # URL columns should match URL pattern
    DataQualityRule(
        rule_name="url_format",
        column_pattern="*url*",
        check_type=CheckType.PATTERN_COMPLIANCE,
        threshold=95.0,
        severity=Severity.LOW,
        description="URL columns should contain valid URL formats",
    ),

    # UUID columns should match UUID pattern
    DataQualityRule(
        rule_name="uuid_format",
        column_pattern="*uuid*",
        check_type=CheckType.PATTERN_COMPLIANCE,
        threshold=100.0,
        severity=Severity.HIGH,
        description="UUID columns should contain valid UUID formats",
    ),

    # Status columns should have reasonable null rates
    DataQualityRule(
        rule_name="status_completeness",
        column_pattern="*status*",
        check_type=CheckType.NULL_PERCENTAGE,
        threshold=5.0,  # Max 5% nulls
        severity=Severity.MEDIUM,
        description="Status columns should be mostly complete",
    ),

    # Name columns should have reasonable length
    DataQualityRule(
        rule_name="name_min_length",
        column_pattern="*name*",
        check_type=CheckType.MIN_LENGTH,
        threshold=1.0,
        severity=Severity.LOW,
        description="Name columns should have at least 1 character",
    ),
]


# Common regex patterns for validation
VALIDATION_PATTERNS = {
    "email": re.compile(
        r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    ),
    "phone": re.compile(
        r"^[\+]?[(]?[0-9]{1,4}[)]?[-\s\.]?[(]?[0-9]{1,4}[)]?[-\s\.]?[0-9]{1,9}$"
    ),
    "url": re.compile(
        r"^https?://[^\s/$.?#].[^\s]*$",
        re.IGNORECASE
    ),
    "uuid": re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        re.IGNORECASE
    ),
    "ip_address": re.compile(
        r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}"
        r"(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
    ),
    "credit_card": re.compile(
        r"^(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|"
        r"3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})$"
    ),
    "zip_code": re.compile(
        r"^\d{5}(?:[-\s]\d{4})?$"
    ),
    "ssn": re.compile(
        r"^\d{3}-?\d{2}-?\d{4}$"
    ),
}


class DataValidator:
    """
    Validates data quality for database tables and columns.

    The validator applies a set of configurable rules to check data quality
    metrics like null percentages, uniqueness, value ranges, and pattern
    compliance. It produces detailed reports with quality scores.

    Attributes:
        rules: List of data quality rules to apply.
        fail_threshold: Maximum failure rate before validation fails (0.0-1.0).
        check_pii: Whether to check for PII exposure.
        custom_patterns: Additional regex patterns for validation.

    Example:
        >>> validator = DataValidator()
        >>> report = validator.validate_table(table, profile)
        >>> print(f"Quality score: {report.score}")
        >>> for issue in report.issues:
        ...     print(f"  {issue.column}: {issue.message}")
    """

    def __init__(
        self,
        rules: Optional[List[DataQualityRule]] = None,
        fail_threshold: float = 0.1,
        check_pii: bool = True,
        custom_patterns: Optional[dict] = None,
    ):
        """
        Initialize the data validator.

        Args:
            rules: List of quality rules to apply. Uses DEFAULT_RULES if None.
            fail_threshold: Maximum failure rate (0.0-1.0) before validation fails.
            check_pii: Whether to check for PII exposure issues.
            custom_patterns: Additional regex patterns for pattern validation.
        """
        self.rules = rules if rules is not None else DEFAULT_RULES.copy()
        self.fail_threshold = min(1.0, max(0.0, fail_threshold))
        self.check_pii = check_pii
        self.patterns = VALIDATION_PATTERNS.copy()
        if custom_patterns:
            self.patterns.update(custom_patterns)

    def validate_table(
        self,
        table: Table,
        profile: TableProfile,
    ) -> DataValidationReport:
        """
        Validate data quality for an entire table.

        Applies all matching rules to each column and aggregates results
        into a comprehensive validation report.

        Args:
            table: The table schema definition.
            profile: The profiled statistics for the table.

        Returns:
            DataValidationReport with all validation results.
        """
        report = DataValidationReport(table_name=table.name)

        # Track which rules are applied
        applied_rules: Set[str] = set()

        for column in table.columns:
            col_profile = profile.get_column(column.name)
            if col_profile is None:
                continue

            report.columns_checked += 1

            # Validate this column
            issues = self.validate_column(column, col_profile)

            for issue in issues:
                report.add_issue(issue)
                applied_rules.add(issue.rule_violated)

            # Count passed checks (checks that didn't produce issues)
            matching_rules = [r for r in self.rules if r.enabled and r.matches_column(column.name)]
            passed_count = len(matching_rules) - len(issues)
            for _ in range(max(0, passed_count)):
                report.add_passed()

        # Update total checks
        report.total_checks = report.passed + report.failed
        report.rules_applied = list(applied_rules)

        # Calculate final score
        report.calculate_score()

        return report

    def validate_column(
        self,
        column: Column,
        col_profile: ColumnProfile,
    ) -> List[DataQualityIssue]:
        """
        Validate data quality for a single column.

        Applies all matching rules to the column and returns any issues found.

        Args:
            column: The column schema definition.
            col_profile: The profiled statistics for the column.

        Returns:
            List of DataQualityIssue objects for any violated rules.
        """
        issues: List[DataQualityIssue] = []
        stats = col_profile.statistics

        for rule in self.rules:
            if not rule.enabled:
                continue

            if not rule.matches_column(column.name):
                continue

            issue = self._apply_rule(column, col_profile, stats, rule)
            if issue:
                issues.append(issue)

        # Check for PII exposure if enabled
        if self.check_pii:
            pii_issue = self._check_pii_exposure(column, col_profile)
            if pii_issue:
                issues.append(pii_issue)

        return issues

    def _apply_rule(
        self,
        column: Column,
        col_profile: ColumnProfile,
        stats: ColumnStatistics,
        rule: DataQualityRule,
    ) -> Optional[DataQualityIssue]:
        """Apply a single rule to a column."""
        if rule.check_type == CheckType.NULL_PERCENTAGE:
            return self._check_null_percentage(
                col_profile, stats, rule.threshold, rule
            )
        elif rule.check_type == CheckType.UNIQUENESS:
            return self._check_uniqueness(col_profile, stats, column, rule)
        elif rule.check_type == CheckType.VALUE_RANGE:
            return self._check_value_range(col_profile, stats, column, rule)
        elif rule.check_type == CheckType.PATTERN_COMPLIANCE:
            return self._check_pattern_compliance(col_profile, stats, rule)
        elif rule.check_type == CheckType.NON_NEGATIVE:
            return self._check_non_negative(col_profile, stats, column, rule)
        elif rule.check_type == CheckType.MIN_LENGTH:
            return self._check_min_length(col_profile, stats, rule)
        elif rule.check_type == CheckType.MAX_LENGTH:
            return self._check_max_length(col_profile, stats, rule)

        return None

    def _check_null_percentage(
        self,
        col_profile: ColumnProfile,
        stats: ColumnStatistics,
        threshold: float,
        rule: DataQualityRule,
    ) -> Optional[DataQualityIssue]:
        """
        Check if null percentage exceeds threshold.

        Args:
            col_profile: Column profile with statistics.
            stats: Column statistics.
            threshold: Maximum allowed null percentage.
            rule: The rule being applied.

        Returns:
            DataQualityIssue if null percentage exceeds threshold.
        """
        null_pct = stats.null_percentage

        if null_pct > threshold:
            return DataQualityIssue(
                table=col_profile.table_name,
                column=col_profile.column_name,
                rule_violated=rule.rule_name,
                actual_value=round(null_pct, 2),
                expected_value=threshold,
                severity=rule.severity,
                check_type=CheckType.NULL_PERCENTAGE,
                message=f"Null percentage ({null_pct:.2f}%) exceeds threshold ({threshold}%)",
            )

        return None

    def _check_uniqueness(
        self,
        col_profile: ColumnProfile,
        stats: ColumnStatistics,
        column: Column,
        rule: DataQualityRule,
    ) -> Optional[DataQualityIssue]:
        """
        Check if uniqueness meets threshold.

        For columns that should be unique (like IDs), checks that the
        distinct percentage is at or above the threshold.

        Args:
            col_profile: Column profile with statistics.
            stats: Column statistics.
            column: Column schema definition.
            rule: The rule being applied.

        Returns:
            DataQualityIssue if uniqueness is below threshold.
        """
        # Calculate uniqueness as percentage of distinct non-null values
        if stats.total_count == 0 or stats.non_null_count == 0:
            return None

        uniqueness_pct = (stats.distinct_count / stats.non_null_count) * 100

        if uniqueness_pct < rule.threshold:
            return DataQualityIssue(
                table=col_profile.table_name,
                column=col_profile.column_name,
                rule_violated=rule.rule_name,
                actual_value=round(uniqueness_pct, 2),
                expected_value=rule.threshold,
                severity=rule.severity,
                check_type=CheckType.UNIQUENESS,
                message=f"Uniqueness ({uniqueness_pct:.2f}%) below threshold ({rule.threshold}%)",
            )

        return None

    def _check_value_range(
        self,
        col_profile: ColumnProfile,
        stats: ColumnStatistics,
        column: Column,
        rule: DataQualityRule,
    ) -> Optional[DataQualityIssue]:
        """
        Check if values are within expected range.

        For numeric columns, checks min/max values.
        For date columns, checks reasonable date ranges.

        Args:
            col_profile: Column profile with statistics.
            stats: Column statistics.
            column: Column schema definition.
            rule: The rule being applied.

        Returns:
            DataQualityIssue if values are out of expected range.
        """
        # For date/timestamp columns, check reasonable range
        if column.is_temporal():
            # Check if min/max values exist and are reasonable
            # We consider 1900-2100 as reasonable for most use cases
            min_year = 1900
            max_year = 2100

            if stats.min_value is not None:
                try:
                    # Try to extract year from the value
                    min_val_str = str(stats.min_value)
                    if len(min_val_str) >= 4:
                        year = int(min_val_str[:4])
                        if year < min_year:
                            return DataQualityIssue(
                                table=col_profile.table_name,
                                column=col_profile.column_name,
                                rule_violated=rule.rule_name,
                                actual_value=stats.min_value,
                                expected_value=f">= {min_year}",
                                severity=rule.severity,
                                check_type=CheckType.VALUE_RANGE,
                                message=f"Date value {stats.min_value} before {min_year}",
                            )
                except (ValueError, TypeError):
                    pass

            if stats.max_value is not None:
                try:
                    max_val_str = str(stats.max_value)
                    if len(max_val_str) >= 4:
                        year = int(max_val_str[:4])
                        if year > max_year:
                            return DataQualityIssue(
                                table=col_profile.table_name,
                                column=col_profile.column_name,
                                rule_violated=rule.rule_name,
                                actual_value=stats.max_value,
                                expected_value=f"<= {max_year}",
                                severity=rule.severity,
                                check_type=CheckType.VALUE_RANGE,
                                message=f"Date value {stats.max_value} after {max_year}",
                            )
                except (ValueError, TypeError):
                    pass

        return None

    def _check_pattern_compliance(
        self,
        col_profile: ColumnProfile,
        stats: ColumnStatistics,
        rule: DataQualityRule,
    ) -> Optional[DataQualityIssue]:
        """
        Check if values comply with expected pattern.

        Checks the detected patterns in the column profile to determine
        if the column values match expected formats (email, phone, etc.).

        Args:
            col_profile: Column profile with statistics.
            stats: Column statistics.
            rule: The rule being applied.

        Returns:
            DataQualityIssue if pattern compliance is below threshold.
        """
        # Determine which pattern to check based on column name
        expected_pattern = None
        column_lower = col_profile.column_name.lower()

        if "email" in column_lower:
            expected_pattern = "email"
        elif "phone" in column_lower or "mobile" in column_lower:
            expected_pattern = "phone"
        elif "url" in column_lower or "link" in column_lower:
            expected_pattern = "url"
        elif "uuid" in column_lower or "guid" in column_lower:
            expected_pattern = "uuid"
        elif "ip" in column_lower and "address" in column_lower:
            expected_pattern = "ip_address"

        if expected_pattern is None:
            return None

        # Check if pattern was detected in the profiling
        pattern_match_pct = 0.0
        for pattern in stats.patterns:
            if pattern.pattern_type.value.lower() == expected_pattern:
                pattern_match_pct = pattern.match_percentage
                break

        # If we have sample values and no pattern was detected, check manually
        if pattern_match_pct == 0.0 and col_profile.sample_values:
            regex = self.patterns.get(expected_pattern)
            if regex:
                matches = sum(
                    1 for v in col_profile.sample_values
                    if v and regex.match(str(v))
                )
                if len(col_profile.sample_values) > 0:
                    pattern_match_pct = (matches / len(col_profile.sample_values)) * 100

        if pattern_match_pct < rule.threshold:
            return DataQualityIssue(
                table=col_profile.table_name,
                column=col_profile.column_name,
                rule_violated=rule.rule_name,
                actual_value=round(pattern_match_pct, 2),
                expected_value=rule.threshold,
                severity=rule.severity,
                check_type=CheckType.PATTERN_COMPLIANCE,
                message=(
                    f"Pattern compliance for {expected_pattern} "
                    f"({pattern_match_pct:.2f}%) below threshold ({rule.threshold}%)"
                ),
            )

        return None

    def _check_non_negative(
        self,
        col_profile: ColumnProfile,
        stats: ColumnStatistics,
        column: Column,
        rule: DataQualityRule,
    ) -> Optional[DataQualityIssue]:
        """
        Check if numeric values are non-negative.

        Args:
            col_profile: Column profile with statistics.
            stats: Column statistics.
            column: Column schema definition.
            rule: The rule being applied.

        Returns:
            DataQualityIssue if negative values are found.
        """
        if not column.is_numeric():
            return None

        if stats.min_value is not None:
            try:
                min_val = float(stats.min_value)
                if min_val < 0:
                    return DataQualityIssue(
                        table=col_profile.table_name,
                        column=col_profile.column_name,
                        rule_violated=rule.rule_name,
                        actual_value=min_val,
                        expected_value=">= 0",
                        severity=rule.severity,
                        check_type=CheckType.NON_NEGATIVE,
                        message=f"Column contains negative values (min: {min_val})",
                    )
            except (ValueError, TypeError):
                pass

        return None

    def _check_min_length(
        self,
        col_profile: ColumnProfile,
        stats: ColumnStatistics,
        rule: DataQualityRule,
    ) -> Optional[DataQualityIssue]:
        """
        Check if string values meet minimum length.

        Args:
            col_profile: Column profile with statistics.
            stats: Column statistics.
            rule: The rule being applied.

        Returns:
            DataQualityIssue if minimum length is violated.
        """
        if stats.min_length is not None and stats.min_length < rule.threshold:
            return DataQualityIssue(
                table=col_profile.table_name,
                column=col_profile.column_name,
                rule_violated=rule.rule_name,
                actual_value=stats.min_length,
                expected_value=f">= {rule.threshold}",
                severity=rule.severity,
                check_type=CheckType.MIN_LENGTH,
                message=f"Minimum length ({stats.min_length}) below threshold ({rule.threshold})",
            )

        return None

    def _check_max_length(
        self,
        col_profile: ColumnProfile,
        stats: ColumnStatistics,
        rule: DataQualityRule,
    ) -> Optional[DataQualityIssue]:
        """
        Check if string values meet maximum length constraint.

        Args:
            col_profile: Column profile with statistics.
            stats: Column statistics.
            rule: The rule being applied.

        Returns:
            DataQualityIssue if maximum length is exceeded.
        """
        if stats.max_length is not None and stats.max_length > rule.threshold:
            return DataQualityIssue(
                table=col_profile.table_name,
                column=col_profile.column_name,
                rule_violated=rule.rule_name,
                actual_value=stats.max_length,
                expected_value=f"<= {rule.threshold}",
                severity=rule.severity,
                check_type=CheckType.MAX_LENGTH,
                message=f"Maximum length ({stats.max_length}) exceeds threshold ({rule.threshold})",
            )

        return None

    def _check_referential_integrity(
        self,
        col_profile: ColumnProfile,
        referenced_values: Set[Any],
    ) -> Optional[DataQualityIssue]:
        """
        Check referential integrity against a set of valid values.

        Verifies that all values in a foreign key column exist in the
        referenced table's primary key column.

        Args:
            col_profile: Column profile with statistics.
            referenced_values: Set of valid values from the referenced column.

        Returns:
            DataQualityIssue if referential integrity is violated.
        """
        if not col_profile.sample_values or not referenced_values:
            return None

        # Check what percentage of sample values exist in referenced set
        valid_count = sum(
            1 for v in col_profile.sample_values
            if v is not None and v in referenced_values
        )

        non_null_samples = [v for v in col_profile.sample_values if v is not None]
        if not non_null_samples:
            return None

        integrity_pct = (valid_count / len(non_null_samples)) * 100

        if integrity_pct < 100.0:
            invalid_values = [
                v for v in col_profile.sample_values
                if v is not None and v not in referenced_values
            ][:5]  # Show first 5 invalid values

            return DataQualityIssue(
                table=col_profile.table_name,
                column=col_profile.column_name,
                rule_violated="referential_integrity",
                actual_value=round(integrity_pct, 2),
                expected_value=100.0,
                severity=Severity.HIGH,
                check_type=CheckType.REFERENTIAL_INTEGRITY,
                message=(
                    f"Referential integrity violation: {100 - integrity_pct:.2f}% of values "
                    f"not found in referenced table. Examples: {invalid_values}"
                ),
            )

        return None

    def _check_pii_exposure(
        self,
        column: Column,
        col_profile: ColumnProfile,
    ) -> Optional[DataQualityIssue]:
        """
        Check for potential PII data exposure.

        Identifies columns that may contain personally identifiable information
        based on semantic type or column name patterns.

        Args:
            column: Column schema definition.
            col_profile: Column profile with statistics.

        Returns:
            DataQualityIssue if PII exposure is detected.
        """
        # Check if semantic type indicates PII
        semantic_type_str = column.semantic_type or col_profile.inferred_semantic_type

        if semantic_type_str:
            try:
                semantic_type = SemanticType(semantic_type_str)
                if semantic_type in PII_TYPES:
                    return DataQualityIssue(
                        table=col_profile.table_name,
                        column=col_profile.column_name,
                        rule_violated="pii_detected",
                        actual_value=semantic_type.value,
                        expected_value="non-PII",
                        severity=Severity.INFO,
                        check_type=CheckType.PII_EXPOSURE,
                        message=(
                            f"Column contains PII data of type '{semantic_type.value}'. "
                            "Consider encryption or masking."
                        ),
                    )
            except ValueError:
                pass

        # Check column name patterns for PII indicators
        pii_patterns = [
            (r"ssn|social.?security", "SSN"),
            (r"credit.?card|card.?number", "credit card"),
            (r"passport", "passport"),
            (r"driver.?license|license.?number", "driver's license"),
            (r"tax.?id|ein|itin", "tax ID"),
            (r"medical.?record|health.?id", "medical record"),
            (r"bank.?account|routing.?number", "bank account"),
        ]

        column_lower = column.name.lower()
        for pattern, pii_type in pii_patterns:
            if re.search(pattern, column_lower):
                return DataQualityIssue(
                    table=col_profile.table_name,
                    column=col_profile.column_name,
                    rule_violated="pii_detected",
                    actual_value=pii_type,
                    expected_value="non-PII",
                    severity=Severity.HIGH,
                    check_type=CheckType.PII_EXPOSURE,
                    message=(
                        f"Column name suggests sensitive PII data ({pii_type}). "
                        "Verify and apply appropriate security measures."
                    ),
                )

        return None

    def add_rule(self, rule: DataQualityRule) -> None:
        """Add a new validation rule."""
        self.rules.append(rule)

    def remove_rule(self, rule_name: str) -> bool:
        """
        Remove a rule by name.

        Returns:
            True if rule was found and removed, False otherwise.
        """
        for i, rule in enumerate(self.rules):
            if rule.rule_name == rule_name:
                self.rules.pop(i)
                return True
        return False

    def disable_rule(self, rule_name: str) -> bool:
        """
        Disable a rule by name.

        Returns:
            True if rule was found and disabled, False otherwise.
        """
        for rule in self.rules:
            if rule.rule_name == rule_name:
                rule.enabled = False
                return True
        return False

    def enable_rule(self, rule_name: str) -> bool:
        """
        Enable a rule by name.

        Returns:
            True if rule was found and enabled, False otherwise.
        """
        for rule in self.rules:
            if rule.rule_name == rule_name:
                rule.enabled = True
                return True
        return False

    def get_rules_for_column(self, column_name: str) -> List[DataQualityRule]:
        """Get all rules that would apply to a column."""
        return [
            rule for rule in self.rules
            if rule.enabled and rule.matches_column(column_name)
        ]


def create_custom_rule(
    name: str,
    pattern: str,
    check: CheckType,
    threshold: float,
    severity: Severity = Severity.MEDIUM,
    description: str = "",
) -> DataQualityRule:
    """
    Factory function to create a custom data quality rule.

    Args:
        name: Human-readable name for the rule.
        pattern: Glob pattern to match column names.
        check: Type of quality check to perform.
        threshold: Threshold value for the check.
        severity: Severity level if violated.
        description: Optional description.

    Returns:
        Configured DataQualityRule instance.

    Example:
        >>> rule = create_custom_rule(
        ...     name="high_null_rate",
        ...     pattern="*optional*",
        ...     check=CheckType.NULL_PERCENTAGE,
        ...     threshold=50.0,
        ...     severity=Severity.LOW,
        ...     description="Optional columns can have up to 50% nulls"
        ... )
    """
    return DataQualityRule(
        rule_name=name,
        column_pattern=pattern,
        check_type=check,
        threshold=threshold,
        severity=severity,
        description=description,
    )
