"""
Output Validator for Generated Code.

Validates generated SQL, dbt models, and SQLAlchemy code for:
- Syntax correctness
- Security vulnerabilities (SQL injection risks)
- dbt-specific validations (Jinja, ref/source calls, YAML structure)
- Compilation verification
"""

import re
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import yaml

try:
    import sqlparse
    SQLPARSE_AVAILABLE = True
except ImportError:
    SQLPARSE_AVAILABLE = False

from core.generators.dbt_generator import DBTGenerator
from core.utils.logger import get_logger

logger = get_logger(__name__)


class IssueSeverity(Enum):
    """Severity levels for validation issues."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class IssueType(Enum):
    """Types of validation issues."""
    SYNTAX_ERROR = "syntax_error"
    SQL_INJECTION_RISK = "sql_injection_risk"
    MISSING_REF = "missing_ref"
    INVALID_JINJA = "invalid_jinja"
    YAML_ERROR = "yaml_error"
    CONFIG_ERROR = "config_error"
    COMPILATION_ERROR = "compilation_error"
    MISSING_FIELD = "missing_field"
    DEPRECATION = "deprecation"
    BEST_PRACTICE = "best_practice"


@dataclass
class OutputIssue:
    """Represents a single validation issue found in generated output."""
    file_path: str
    line_number: int
    issue_type: IssueType
    message: str
    severity: IssueSeverity
    suggestion: Optional[str] = None

    def __str__(self) -> str:
        """Human-readable representation of the issue."""
        loc = f"{self.file_path}:{self.line_number}" if self.line_number > 0 else self.file_path
        return f"[{self.severity.value.upper()}] {loc}: {self.message}"


@dataclass
class OutputValidationReport:
    """Complete validation report for generated output."""
    total_files: int
    valid_files: int
    issues: List[OutputIssue] = field(default_factory=list)
    can_compile: bool = True
    compilation_output: Optional[str] = None

    @property
    def error_count(self) -> int:
        """Count of error-level issues."""
        return sum(1 for i in self.issues if i.severity in (IssueSeverity.ERROR, IssueSeverity.CRITICAL))

    @property
    def warning_count(self) -> int:
        """Count of warning-level issues."""
        return sum(1 for i in self.issues if i.severity == IssueSeverity.WARNING)

    @property
    def is_valid(self) -> bool:
        """Whether the output passes validation (no errors/critical issues)."""
        return self.error_count == 0 and self.can_compile

    def summary(self) -> str:
        """Generate a human-readable summary."""
        status = "PASSED" if self.is_valid else "FAILED"
        return (
            f"Validation {status}: "
            f"{self.valid_files}/{self.total_files} files valid, "
            f"{self.error_count} errors, {self.warning_count} warnings"
        )


class OutputValidator:
    """
    Validator for generated code output.

    Supports validation of:
    - dbt projects (SQL models, YAML configs, Jinja templates)
    - Raw SQL files
    - SQLAlchemy models

    Provides both syntax validation and security analysis.
    """

    # Patterns that may indicate SQL injection vulnerabilities
    SQL_INJECTION_PATTERNS = [
        (r"'\s*\+\s*[a-zA-Z_]", "String concatenation detected - use parameterized queries"),
        (r'"\s*\+\s*[a-zA-Z_]', "String concatenation detected - use parameterized queries"),
        (r"f['\"].*\{.*\}.*['\"]", "f-string in SQL - use parameterized queries"),
        (r"\.format\s*\(", ".format() in SQL - use parameterized queries"),
        (r"%\s*\(.*\)", "%-formatting in SQL - use parameterized queries"),
        (r"EXEC\s*\(", "Dynamic EXEC detected - review for SQL injection"),
        (r"EXECUTE\s+IMMEDIATE", "EXECUTE IMMEDIATE detected - review for SQL injection"),
    ]

    # Required fields in dbt YAML files
    DBT_MODEL_REQUIRED_FIELDS = {"name"}
    DBT_SOURCE_REQUIRED_FIELDS = {"name", "tables"}
    DBT_COLUMN_REQUIRED_FIELDS = {"name"}

    # Jinja pattern matchers
    JINJA_BLOCK_PATTERN = re.compile(r"\{[%{].*?[%}]\}", re.DOTALL)
    REF_PATTERN = re.compile(r"\{\{\s*ref\s*\(\s*['\"]([^'\"]+)['\"]\s*\)\s*\}\}")
    SOURCE_PATTERN = re.compile(r"\{\{\s*source\s*\(\s*['\"]([^'\"]+)['\"]")
    CONFIG_PATTERN = re.compile(r"\{\{\s*config\s*\(", re.IGNORECASE)

    def __init__(self, output_type: str = "dbt", dry_run: bool = False):
        """
        Initialize the output validator.

        Args:
            output_type: Type of output to validate ("dbt", "sql", "sqlalchemy")
            dry_run: If True, skip external commands like dbt compile
        """
        self.output_type = output_type.lower()
        self.dry_run = dry_run
        self._available_models: Set[str] = set()

        if self.output_type not in ("dbt", "sql", "sqlalchemy"):
            raise ValueError(f"Unsupported output type: {output_type}")

        if not SQLPARSE_AVAILABLE:
            logger.warning(
                "sqlparse not installed. SQL syntax validation will be limited. "
                "Install with: pip install sqlparse"
            )

    def validate_output(self, output_path: Path) -> OutputValidationReport:
        """
        Validate all files in the output path.

        Args:
            output_path: Path to the output directory or file

        Returns:
            OutputValidationReport with validation results
        """
        output_path = Path(output_path).resolve()

        if not output_path.exists():
            return OutputValidationReport(
                total_files=0,
                valid_files=0,
                issues=[OutputIssue(
                    file_path=str(output_path),
                    line_number=0,
                    issue_type=IssueType.CONFIG_ERROR,
                    message=f"Output path does not exist: {output_path}",
                    severity=IssueSeverity.CRITICAL
                )],
                can_compile=False
            )

        # Collect files to validate
        if output_path.is_file():
            files_to_validate = [output_path]
        else:
            files_to_validate = self._collect_files(output_path)

        # First pass: collect available model names for ref validation
        if self.output_type == "dbt":
            self._available_models = self._collect_model_names(output_path)
            logger.debug(f"Found {len(self._available_models)} dbt models: {self._available_models}")

        # Validate each file
        all_issues: List[OutputIssue] = []
        valid_count = 0

        for file_path in files_to_validate:
            file_issues = self.validate_file(file_path)
            all_issues.extend(file_issues)

            # File is valid if no errors or critical issues
            file_errors = [i for i in file_issues
                          if i.severity in (IssueSeverity.ERROR, IssueSeverity.CRITICAL)]
            if not file_errors:
                valid_count += 1

        # Run compilation check for dbt projects
        can_compile = True
        compilation_output = None

        if self.output_type == "dbt" and output_path.is_dir() and not self.dry_run:
            can_compile, compilation_output = self._run_dbt_compile(output_path)
            if not can_compile:
                dbt_missing = bool(compilation_output) and "dbt command not found" in compilation_output
                all_issues.append(OutputIssue(
                    file_path=str(output_path),
                    line_number=0,
                    issue_type=IssueType.COMPILATION_ERROR,
                    message=(
                        f"dbt compile skipped: {compilation_output}"
                        if dbt_missing
                        else f"dbt compile failed: {compilation_output}"
                    ),
                    severity=IssueSeverity.WARNING if dbt_missing else IssueSeverity.ERROR,
                    suggestion=(
                        "Install dbt-core and an adapter (e.g. dbt-postgres) to enable compile checks"
                        if dbt_missing
                        else None
                    ),
                ))

        report = OutputValidationReport(
            total_files=len(files_to_validate),
            valid_files=valid_count,
            issues=all_issues,
            can_compile=can_compile,
            compilation_output=compilation_output
        )

        logger.info(report.summary())
        return report

    def validate_file(self, file_path: Path) -> List[OutputIssue]:
        """
        Validate a single file.

        Args:
            file_path: Path to the file to validate

        Returns:
            List of issues found in the file
        """
        file_path = Path(file_path).resolve()
        issues: List[OutputIssue] = []

        if not file_path.exists():
            issues.append(OutputIssue(
                file_path=str(file_path),
                line_number=0,
                issue_type=IssueType.CONFIG_ERROR,
                message="File does not exist",
                severity=IssueSeverity.ERROR
            ))
            return issues

        suffix = file_path.suffix.lower()

        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception as e:
            issues.append(OutputIssue(
                file_path=str(file_path),
                line_number=0,
                issue_type=IssueType.CONFIG_ERROR,
                message=f"Failed to read file: {e}",
                severity=IssueSeverity.ERROR
            ))
            return issues

        # Route to appropriate validator based on file type
        if suffix == ".sql":
            issues.extend(self._validate_sql_file(file_path, content))
        elif suffix in (".yml", ".yaml"):
            issues.extend(self._validate_yaml_file(file_path, content))
        elif suffix == ".py" and self.output_type == "sqlalchemy":
            issues.extend(self._validate_sqlalchemy_file(file_path, content))

        return issues

    def _collect_files(self, directory: Path) -> List[Path]:
        """Collect all relevant files from a directory."""
        files = []

        if self.output_type == "dbt":
            # Collect SQL and YAML files
            files.extend(directory.rglob("*.sql"))
            files.extend(directory.rglob("*.yml"))
            files.extend(directory.rglob("*.yaml"))
        elif self.output_type == "sql":
            files.extend(directory.rglob("*.sql"))
        elif self.output_type == "sqlalchemy":
            files.extend(directory.rglob("*.py"))

        # Exclude common non-source directories
        excluded_dirs = {"target", "dbt_packages", "logs", "__pycache__", ".git", "venv", ".venv"}
        files = [f for f in files if not any(ex in f.parts for ex in excluded_dirs)]

        return sorted(files)

    def _collect_model_names(self, project_path: Path) -> Set[str]:
        """Collect all model names from a dbt project for ref validation."""
        models = set()

        if not project_path.is_dir():
            return models

        models_dir = project_path / "models"
        if not models_dir.exists():
            return models

        for sql_file in models_dir.rglob("*.sql"):
            # Model name is the file stem
            models.add(sql_file.stem)

        return models

    # =========================================================================
    # SQL Validation
    # =========================================================================

    def _validate_sql_file(self, file_path: Path, content: str) -> List[OutputIssue]:
        """Validate a SQL file."""
        issues: List[OutputIssue] = []

        # For dbt files, validate Jinja syntax first
        if self.output_type == "dbt":
            issues.extend(self._validate_dbt_model(file_path, content))

        # Validate SQL syntax (strip Jinja for pure SQL validation)
        sql_content = self._strip_jinja(content) if self.output_type == "dbt" else content
        issues.extend(self._validate_sql_syntax(file_path, sql_content))

        # Check for SQL injection risks
        issues.extend(self._check_sql_injection_risks(file_path, content))

        return issues

    def _validate_sql_syntax(self, file_path: Path, sql: str) -> List[OutputIssue]:
        """
        Validate SQL syntax using sqlparse.

        Args:
            file_path: Path to the file being validated
            sql: SQL content to validate

        Returns:
            List of syntax issues found
        """
        issues: List[OutputIssue] = []

        if not SQLPARSE_AVAILABLE:
            return issues

        if not sql.strip():
            issues.append(OutputIssue(
                file_path=str(file_path),
                line_number=1,
                issue_type=IssueType.SYNTAX_ERROR,
                message="Empty SQL content",
                severity=IssueSeverity.WARNING
            ))
            return issues

        try:
            parsed = self._parse_sql(sql)

            if not parsed:
                issues.append(OutputIssue(
                    file_path=str(file_path),
                    line_number=1,
                    issue_type=IssueType.SYNTAX_ERROR,
                    message="Failed to parse SQL - may contain syntax errors",
                    severity=IssueSeverity.WARNING
                ))
                return issues

            # Check for common SQL issues
            for stmt in parsed:
                stmt_str = str(stmt).strip().upper()

                # Check for unclosed parentheses
                if stmt_str.count("(") != stmt_str.count(")"):
                    line_num = self._find_line_number(sql, "(")
                    issues.append(OutputIssue(
                        file_path=str(file_path),
                        line_number=line_num,
                        issue_type=IssueType.SYNTAX_ERROR,
                        message="Unbalanced parentheses detected",
                        severity=IssueSeverity.ERROR
                    ))

                # Check for SELECT without FROM (except for SELECT constants)
                if stmt_str.startswith("SELECT") and "FROM" not in stmt_str:
                    # Allow SELECT for constants/expressions without FROM
                    if not re.search(r"SELECT\s+[\d\'\"]", stmt_str):
                        issues.append(OutputIssue(
                            file_path=str(file_path),
                            line_number=1,
                            issue_type=IssueType.SYNTAX_ERROR,
                            message="SELECT statement without FROM clause",
                            severity=IssueSeverity.WARNING,
                            suggestion="Add a FROM clause or use a constant expression"
                        ))

                # Check for trailing commas before FROM
                if re.search(r",\s*FROM", stmt_str):
                    line_num = self._find_line_number(sql, ",\\s*FROM")
                    issues.append(OutputIssue(
                        file_path=str(file_path),
                        line_number=line_num,
                        issue_type=IssueType.SYNTAX_ERROR,
                        message="Trailing comma before FROM clause",
                        severity=IssueSeverity.ERROR
                    ))

        except Exception as e:
            issues.append(OutputIssue(
                file_path=str(file_path),
                line_number=1,
                issue_type=IssueType.SYNTAX_ERROR,
                message=f"SQL parsing error: {e}",
                severity=IssueSeverity.ERROR
            ))

        return issues

    def _check_sql_injection_risks(self, file_path: Path, sql: str) -> List[OutputIssue]:
        """
        Check for potential SQL injection vulnerabilities.

        Args:
            file_path: Path to the file being validated
            sql: SQL content to check

        Returns:
            List of security issues found
        """
        issues: List[OutputIssue] = []

        for pattern, message in self.SQL_INJECTION_PATTERNS:
            matches = re.finditer(pattern, sql)
            for match in matches:
                line_num = sql[:match.start()].count("\n") + 1
                issues.append(OutputIssue(
                    file_path=str(file_path),
                    line_number=line_num,
                    issue_type=IssueType.SQL_INJECTION_RISK,
                    message=message,
                    severity=IssueSeverity.WARNING,
                    suggestion="Use parameterized queries or dbt's ref()/source() macros"
                ))

        return issues

    def _parse_sql(self, sql: str) -> Any:
        """
        Parse SQL using sqlparse.

        Args:
            sql: SQL string to parse

        Returns:
            Parsed SQL statements
        """
        if not SQLPARSE_AVAILABLE:
            return None
        return sqlparse.parse(sql)

    def _strip_jinja(self, content: str) -> str:
        """Remove Jinja blocks from content for pure SQL validation."""
        # Replace Jinja blocks with placeholders
        result = content

        # Replace {{ ... }} with placeholder
        result = re.sub(r"\{\{.*?\}\}", "JINJA_EXPR", result, flags=re.DOTALL)

        # Replace {% ... %} with empty string (control flow)
        result = re.sub(r"\{%.*?%\}", "", result, flags=re.DOTALL)

        # Replace {# ... #} with empty string (comments)
        result = re.sub(r"\{#.*?#\}", "", result, flags=re.DOTALL)

        return result

    # =========================================================================
    # dbt Validation
    # =========================================================================

    def _validate_dbt_model(self, file_path: Path, content: str) -> List[OutputIssue]:
        """
        Validate a dbt model SQL file.

        Args:
            file_path: Path to the dbt model file
            content: File content

        Returns:
            List of issues found
        """
        issues: List[OutputIssue] = []

        # Validate Jinja syntax
        issues.extend(self._validate_jinja_syntax(file_path, content))

        # Validate ref() calls
        issues.extend(self._validate_ref_calls(file_path, content, self._available_models))

        # Check for config block
        if not self.CONFIG_PATTERN.search(content):
            issues.append(OutputIssue(
                file_path=str(file_path),
                line_number=1,
                issue_type=IssueType.BEST_PRACTICE,
                message="No config block found - consider adding materialization config",
                severity=IssueSeverity.INFO,
                suggestion="Add {{ config(materialized='...') }} at the top"
            ))

        # Check for source() calls without proper format
        source_matches = self.SOURCE_PATTERN.findall(content)
        for source_name in source_matches:
            if not re.search(rf"source\s*\(\s*['\"].*['\"]\s*,\s*['\"].*['\"]\s*\)", content):
                line_num = self._find_line_number(content, f"source.*{source_name}")
                issues.append(OutputIssue(
                    file_path=str(file_path),
                    line_number=line_num,
                    issue_type=IssueType.SYNTAX_ERROR,
                    message=f"Malformed source() call for '{source_name}'",
                    severity=IssueSeverity.ERROR,
                    suggestion="Use: {{ source('source_name', 'table_name') }}"
                ))

        return issues

    def _validate_jinja_syntax(self, file_path: Path, content: str) -> List[OutputIssue]:
        """Validate Jinja template syntax."""
        issues: List[OutputIssue] = []

        # Check for unbalanced Jinja delimiters
        open_expr = content.count("{{")
        close_expr = content.count("}}")
        open_stmt = content.count("{%")
        close_stmt = content.count("%}")
        open_comment = content.count("{#")
        close_comment = content.count("#}")

        if open_expr != close_expr:
            issues.append(OutputIssue(
                file_path=str(file_path),
                line_number=1,
                issue_type=IssueType.INVALID_JINJA,
                message=f"Unbalanced Jinja expression delimiters: {open_expr} '{{{{' vs {close_expr} '}}}}'",
                severity=IssueSeverity.ERROR
            ))

        if open_stmt != close_stmt:
            issues.append(OutputIssue(
                file_path=str(file_path),
                line_number=1,
                issue_type=IssueType.INVALID_JINJA,
                message=f"Unbalanced Jinja statement delimiters: {open_stmt} '{{% ' vs {close_stmt} ' %}}'",
                severity=IssueSeverity.ERROR
            ))

        if open_comment != close_comment:
            issues.append(OutputIssue(
                file_path=str(file_path),
                line_number=1,
                issue_type=IssueType.INVALID_JINJA,
                message=f"Unbalanced Jinja comment delimiters: {open_comment} '{{# ' vs {close_comment} ' #}}'",
                severity=IssueSeverity.ERROR
            ))

        return issues

    def _validate_ref_calls(
        self,
        file_path: Path,
        content: str,
        available_models: Set[str]
    ) -> List[OutputIssue]:
        """
        Validate that ref() calls reference existing models.

        Args:
            file_path: Path to the file being validated
            content: File content
            available_models: Set of available model names

        Returns:
            List of issues for missing references
        """
        issues: List[OutputIssue] = []

        if not available_models:
            return issues

        ref_matches = self.REF_PATTERN.findall(content)

        for ref_name in ref_matches:
            if ref_name not in available_models:
                line_num = self._find_line_number(content, f"ref.*{ref_name}")
                issues.append(OutputIssue(
                    file_path=str(file_path),
                    line_number=line_num,
                    issue_type=IssueType.MISSING_REF,
                    message=f"ref('{ref_name}') references non-existent model",
                    severity=IssueSeverity.ERROR,
                    suggestion=f"Available models: {', '.join(sorted(available_models)[:5])}..."
                ))

        return issues

    def _extract_jinja_blocks(self, content: str) -> List[str]:
        """
        Extract all Jinja blocks from content.

        Args:
            content: File content

        Returns:
            List of Jinja block strings
        """
        return self.JINJA_BLOCK_PATTERN.findall(content)

    def _validate_dbt_yaml(self, file_path: Path, content: str) -> List[OutputIssue]:
        """
        Validate a dbt YAML configuration file.

        Args:
            file_path: Path to the YAML file
            content: File content

        Returns:
            List of issues found
        """
        issues: List[OutputIssue] = []

        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            line = getattr(e, "problem_mark", None)
            line_num = line.line + 1 if line else 1
            issues.append(OutputIssue(
                file_path=str(file_path),
                line_number=line_num,
                issue_type=IssueType.YAML_ERROR,
                message=f"Invalid YAML syntax: {e}",
                severity=IssueSeverity.ERROR
            ))
            return issues

        if not isinstance(data, dict):
            issues.append(OutputIssue(
                file_path=str(file_path),
                line_number=1,
                issue_type=IssueType.YAML_ERROR,
                message="YAML root must be a dictionary",
                severity=IssueSeverity.ERROR
            ))
            return issues

        # Project-level files use a different structure from schema/sources files.
        # In dbt_project.yml, `models` is a dict of configs, not a list of model docs.
        if file_path.name in ("dbt_project.yml", "packages.yml", "profiles.yml", "selectors.yml"):
            return issues

        # Check for version field
        if "version" not in data:
            issues.append(OutputIssue(
                file_path=str(file_path),
                line_number=1,
                issue_type=IssueType.MISSING_FIELD,
                message="Missing 'version' field in dbt YAML",
                severity=IssueSeverity.WARNING,
                suggestion="Add 'version: 2' at the top of the file"
            ))

        # Validate models section
        if "models" in data:
            issues.extend(self._validate_dbt_models_yaml(file_path, data["models"]))

        # Validate sources section
        if "sources" in data:
            issues.extend(self._validate_dbt_sources_yaml(file_path, data["sources"]))

        return issues

    def _validate_dbt_models_yaml(
        self,
        file_path: Path,
        models: List[Dict[str, Any]]
    ) -> List[OutputIssue]:
        """Validate the models section of a dbt YAML file."""
        issues: List[OutputIssue] = []

        if not isinstance(models, list):
            issues.append(OutputIssue(
                file_path=str(file_path),
                line_number=1,
                issue_type=IssueType.YAML_ERROR,
                message="'models' must be a list",
                severity=IssueSeverity.ERROR
            ))
            return issues

        for idx, model in enumerate(models):
            if not isinstance(model, dict):
                issues.append(OutputIssue(
                    file_path=str(file_path),
                    line_number=1,
                    issue_type=IssueType.YAML_ERROR,
                    message=f"Model at index {idx} must be a dictionary",
                    severity=IssueSeverity.ERROR
                ))
                continue

            # Check required fields
            for field in self.DBT_MODEL_REQUIRED_FIELDS:
                if field not in model:
                    issues.append(OutputIssue(
                        file_path=str(file_path),
                        line_number=1,
                        issue_type=IssueType.MISSING_FIELD,
                        message=f"Model at index {idx} missing required field: '{field}'",
                        severity=IssueSeverity.ERROR
                    ))

            # Validate model name exists in project
            model_name = model.get("name")
            if model_name and self._available_models and model_name not in self._available_models:
                issues.append(OutputIssue(
                    file_path=str(file_path),
                    line_number=1,
                    issue_type=IssueType.MISSING_REF,
                    message=f"Model '{model_name}' defined in YAML but no corresponding .sql file found",
                    severity=IssueSeverity.WARNING
                ))

            # Validate columns
            if "columns" in model:
                issues.extend(self._validate_columns_yaml(file_path, model["columns"], model_name))

        return issues

    def _validate_dbt_sources_yaml(
        self,
        file_path: Path,
        sources: List[Dict[str, Any]]
    ) -> List[OutputIssue]:
        """Validate the sources section of a dbt YAML file."""
        issues: List[OutputIssue] = []

        if not isinstance(sources, list):
            issues.append(OutputIssue(
                file_path=str(file_path),
                line_number=1,
                issue_type=IssueType.YAML_ERROR,
                message="'sources' must be a list",
                severity=IssueSeverity.ERROR
            ))
            return issues

        for idx, source in enumerate(sources):
            if not isinstance(source, dict):
                issues.append(OutputIssue(
                    file_path=str(file_path),
                    line_number=1,
                    issue_type=IssueType.YAML_ERROR,
                    message=f"Source at index {idx} must be a dictionary",
                    severity=IssueSeverity.ERROR
                ))
                continue

            # Check required fields
            for field in self.DBT_SOURCE_REQUIRED_FIELDS:
                if field not in source:
                    issues.append(OutputIssue(
                        file_path=str(file_path),
                        line_number=1,
                        issue_type=IssueType.MISSING_FIELD,
                        message=f"Source at index {idx} missing required field: '{field}'",
                        severity=IssueSeverity.ERROR
                    ))

        return issues

    def _validate_columns_yaml(
        self,
        file_path: Path,
        columns: List[Dict[str, Any]],
        parent_name: Optional[str]
    ) -> List[OutputIssue]:
        """Validate columns section in YAML."""
        issues: List[OutputIssue] = []

        if not isinstance(columns, list):
            issues.append(OutputIssue(
                file_path=str(file_path),
                line_number=1,
                issue_type=IssueType.YAML_ERROR,
                message=f"'columns' in {parent_name or 'model'} must be a list",
                severity=IssueSeverity.ERROR
            ))
            return issues

        for idx, col in enumerate(columns):
            if not isinstance(col, dict):
                issues.append(OutputIssue(
                    file_path=str(file_path),
                    line_number=1,
                    issue_type=IssueType.YAML_ERROR,
                    message=f"Column at index {idx} in {parent_name or 'model'} must be a dictionary",
                    severity=IssueSeverity.ERROR
                ))
                continue

            for field in self.DBT_COLUMN_REQUIRED_FIELDS:
                if field not in col:
                    issues.append(OutputIssue(
                        file_path=str(file_path),
                        line_number=1,
                        issue_type=IssueType.MISSING_FIELD,
                        message=f"Column at index {idx} in {parent_name or 'model'} missing required field: '{field}'",
                        severity=IssueSeverity.ERROR
                    ))

        return issues

    def _run_dbt_compile(self, project_path: Path) -> Tuple[bool, str]:
        """
        Run dbt compile to verify the project compiles successfully.

        Args:
            project_path: Path to the dbt project root

        Returns:
            Tuple of (success, output_message)
        """
        if self.dry_run:
            return True, "Dry run - skipped dbt compile"

        # Check if dbt_project.yml exists
        if not (project_path / "dbt_project.yml").exists():
            return False, "No dbt_project.yml found in project root"

        try:
            result = subprocess.run(
                ["dbt", "compile"],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=120  # 2 minute timeout
            )

            if result.returncode == 0:
                return True, "dbt compile succeeded"
            else:
                # Extract relevant error message
                error_output = result.stderr or result.stdout
                return False, error_output[:500]  # Truncate long errors

        except FileNotFoundError:
            return False, "dbt command not found - ensure dbt is installed"
        except subprocess.TimeoutExpired:
            return False, "dbt compile timed out after 120 seconds"
        except Exception as e:
            return False, f"Failed to run dbt compile: {e}"

    # =========================================================================
    # YAML Validation
    # =========================================================================

    def _validate_yaml_file(self, file_path: Path, content: str) -> List[OutputIssue]:
        """Validate a YAML file."""
        issues: List[OutputIssue] = []

        # Basic YAML syntax validation
        try:
            data = yaml.safe_load(content)
            if data is None:
                issues.append(OutputIssue(
                    file_path=str(file_path),
                    line_number=1,
                    issue_type=IssueType.YAML_ERROR,
                    message="Empty YAML file",
                    severity=IssueSeverity.WARNING
                ))
                return issues
        except yaml.YAMLError as e:
            line = getattr(e, "problem_mark", None)
            line_num = line.line + 1 if line else 1
            issues.append(OutputIssue(
                file_path=str(file_path),
                line_number=line_num,
                issue_type=IssueType.YAML_ERROR,
                message=f"Invalid YAML syntax: {e}",
                severity=IssueSeverity.ERROR
            ))
            return issues

        # For dbt projects, run dbt-specific validation
        if self.output_type == "dbt":
            issues.extend(self._validate_dbt_yaml(file_path, content))

        return issues

    # =========================================================================
    # SQLAlchemy Validation
    # =========================================================================

    def _validate_sqlalchemy_file(self, file_path: Path, content: str) -> List[OutputIssue]:
        """Validate a SQLAlchemy model file."""
        issues: List[OutputIssue] = []

        # Check for basic Python syntax
        try:
            compile(content, str(file_path), "exec")
        except SyntaxError as e:
            issues.append(OutputIssue(
                file_path=str(file_path),
                line_number=e.lineno or 1,
                issue_type=IssueType.SYNTAX_ERROR,
                message=f"Python syntax error: {e.msg}",
                severity=IssueSeverity.ERROR
            ))
            return issues

        # Check for SQLAlchemy imports
        if "sqlalchemy" not in content.lower():
            issues.append(OutputIssue(
                file_path=str(file_path),
                line_number=1,
                issue_type=IssueType.BEST_PRACTICE,
                message="File does not appear to contain SQLAlchemy code",
                severity=IssueSeverity.INFO
            ))

        # Check for potential SQL injection in raw queries
        raw_sql_patterns = [
            (r"text\s*\(['\"].*%", "Potential SQL injection in text() - use bound parameters"),
            (r"execute\s*\(['\"].*\+", "Potential SQL injection in execute() - use bound parameters"),
        ]

        for pattern, message in raw_sql_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                line_num = content[:match.start()].count("\n") + 1
                issues.append(OutputIssue(
                    file_path=str(file_path),
                    line_number=line_num,
                    issue_type=IssueType.SQL_INJECTION_RISK,
                    message=message,
                    severity=IssueSeverity.WARNING
                ))

        return issues

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _find_line_number(self, content: str, pattern: str) -> int:
        """Find the line number where a pattern (regex, or literal text) first occurs."""
        try:
            match = re.search(pattern, content, re.IGNORECASE)
        except re.error:
            # Not a valid regex (e.g. a bare "("): fall back to a literal search
            index = content.lower().find(pattern.lower())
            return content[:index].count("\n") + 1 if index >= 0 else 1
        if match:
            return content[:match.start()].count("\n") + 1
        return 1
