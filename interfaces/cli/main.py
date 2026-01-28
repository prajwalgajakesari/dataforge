"""
DataForge CLI - Command-line interface for DataForge.

This is the main entry point for the DataForge CLI application.
Provides commands for data modeling workflows including:
- analyze: Analyze database schema and data quality
- normalize: Normalize schema to target normal form
- design: Generate data model design from requirements
- generate: Generate code from data model design
- validate: Validate schema, design, or generated output
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import typer
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from rich.text import Text

app = typer.Typer(
    name="dataforge",
    help="AI-powered data engineering platform",
    add_completion=False,
)

console = Console()


# =============================================================================
# Utility Functions
# =============================================================================


def _load_json_or_yaml(file_path: str) -> Dict[str, Any]:
    """Load data from JSON or YAML file."""
    path = Path(file_path)
    if not path.exists():
        raise typer.BadParameter(f"File not found: {file_path}")

    content = path.read_text()

    if path.suffix.lower() in [".yaml", ".yml"]:
        return yaml.safe_load(content)
    elif path.suffix.lower() == ".json":
        return json.loads(content)
    else:
        # Try JSON first, then YAML
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return yaml.safe_load(content)


def _save_output(data: Dict[str, Any], output_path: Optional[str], fmt: str = "json") -> None:
    """Save data to file in specified format."""
    if fmt == "yaml":
        content = yaml.dump(data, default_flow_style=False, sort_keys=False)
    else:
        content = json.dumps(data, indent=2, default=str)

    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        console.print(f"[green]Output saved to:[/green] {output_path}")
    else:
        console.print(content)


def _format_output(data: Dict[str, Any], fmt: str) -> None:
    """Format and display output based on format type."""
    if fmt == "table":
        _display_as_table(data)
    elif fmt == "yaml":
        console.print(yaml.dump(data, default_flow_style=False, sort_keys=False))
    else:
        console.print(json.dumps(data, indent=2, default=str))


def _display_as_table(data: Dict[str, Any]) -> None:
    """Display data as rich tables."""
    if "tables" in data:
        table = Table(title="Tables Analysis")
        table.add_column("Table", style="cyan")
        table.add_column("Columns", style="green")
        table.add_column("Rows", style="blue")
        table.add_column("Quality Score", style="magenta")

        for tbl in data.get("tables", []):
            table.add_row(
                tbl.get("name", ""),
                str(tbl.get("column_count", len(tbl.get("columns", [])))),
                str(tbl.get("row_count", "")),
                f"{tbl.get('quality_score', 0):.1f}%"
            )
        console.print(table)

    if "violations" in data:
        violations = data.get("violations", {})
        if any(violations.values()):
            table = Table(title="Normalization Violations")
            table.add_column("Table", style="cyan")
            table.add_column("Level", style="red")
            table.add_column("Type", style="yellow")
            table.add_column("Description", style="white")

            for level, level_violations in violations.items():
                for v in level_violations:
                    table.add_row(
                        v.get("table", ""),
                        level.upper(),
                        str(v.get("type", "")),
                        str(v.get("description", ""))[:50]
                    )
            console.print(table)


# =============================================================================
# Existing Commands
# =============================================================================


@app.command()
def version():
    """Show DataForge version."""
    console.print("[bold blue]DataForge[/bold blue] version [green]0.1.0[/green]")
    console.print("AI-powered data engineering platform")


@app.command()
def init(
    name: str = typer.Argument(..., help="Name of the workspace"),
    project_type: str = typer.Option("dbt", "--type", "-t", help="Project type (dbt, airflow, terraform, multi)"),
    template: str = typer.Option(None, "--template", help="Template to use"),
):
    """Initialize a new DataForge workspace."""
    from core.workspace.manager import WorkspaceManager

    console.print(f"\n[bold]Creating workspace:[/bold] {name}")
    console.print(f"[dim]Type: {project_type}[/dim]\n")

    try:
        manager = WorkspaceManager()
        workspace = manager.create_workspace(
            name=name,
            project_type=project_type,
            template=template
        )

        console.print(Panel(
            f"[green]Workspace created successfully![/green]\n\n"
            f"[bold]Path:[/bold] {workspace.path}\n"
            f"[bold]Type:[/bold] {workspace.project_type}\n"
            f"[bold]ID:[/bold] {workspace.workspace_id}",
            title="Success",
            border_style="green"
        ))

        console.print(f"\n[dim]Next steps:[/dim]")
        console.print(f"  1. cd {workspace.path}")
        console.print(f"  2. dataforge chat")

    except Exception as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        raise typer.Exit(1)


@app.command("list")
def list_workspaces():
    """List all DataForge workspaces."""
    from core.workspace.manager import WorkspaceManager

    manager = WorkspaceManager()
    workspaces = manager.list_workspaces()

    if not workspaces:
        console.print("[yellow]No workspaces found.[/yellow]")
        console.print("\nCreate one with: [bold]dataforge init my-workspace[/bold]")
        return

    table = Table(title="DataForge Workspaces")
    table.add_column("Name", style="cyan")
    table.add_column("Type", style="magenta")
    table.add_column("Path", style="green")
    table.add_column("Created", style="blue")

    for ws in workspaces:
        table.add_row(
            ws.name,
            ws.project_type,
            str(ws.path),
            ws.created_at.strftime("%Y-%m-%d %H:%M")
        )

    console.print(table)


@app.command()
def chat(
    workspace: str = typer.Option(
        None,
        "--workspace",
        "-w",
        help="Path to workspace directory (uses current directory if not specified)",
    ),
):
    """Start an interactive chat session with DataForge.

    The chat interface provides a conversational way to:
    - Explore and analyze database schemas
    - Design data models (Star Schema, 3NF, Data Vault)
    - Generate DDL, dbt models, and documentation

    Use /help within the chat for available commands.
    """
    from interfaces.cli.chat import start_chat

    start_chat(workspace_path=workspace)


@app.command()
def status():
    """Show status of DataForge and connected services."""
    from core.utils.config import settings

    console.print("\n[bold]DataForge Status[/bold]\n")

    # Configuration
    table = Table(title="Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Environment", settings.dataforge_env)
    table.add_row("Log Level", settings.dataforge_log_level)
    table.add_row("Workspace Dir", settings.dataforge_workspace_dir)
    table.add_row("Default Model", settings.default_model)
    table.add_row("API Key", "[green]Set[/green]" if settings.anthropic_api_key else "[red]Not set[/red]")

    console.print(table)

    # MCP Servers
    console.print("\n[dim]MCP servers status coming soon...[/dim]\n")


# =============================================================================
# New Modeling Commands
# =============================================================================


@app.command()
def analyze(
    connection: str = typer.Argument(..., help="Database connection string or MCP server name"),
    schema: Optional[str] = typer.Option(None, "--schema", "-s", help="Schema to analyze"),
    tables: Optional[List[str]] = typer.Option(None, "--table", "-t", help="Specific tables to analyze"),
    output: str = typer.Option("json", "--output", "-o", help="Output format (json, yaml, table)"),
    output_file: Optional[str] = typer.Option(None, "--output-file", "-f", help="Output file path"),
    sample_size: int = typer.Option(10000, "--sample-size", help="Sample size for profiling"),
):
    """
    Analyze database schema and data quality.

    Performs comprehensive analysis including:
    - Schema discovery (tables, columns, constraints)
    - Data profiling (statistics, patterns, quality scores)
    - Functional dependency detection
    - Candidate key discovery

    Examples:
        dataforge analyze postgresql://user:pass@localhost/db
        dataforge analyze postgresql://localhost/db --schema public --table orders customers
        dataforge analyze my-mcp-server --output table
    """
    async def _run_analysis():
        from core.analysis.profiler import EnhancedProfiler
        from core.analysis.fd_detector import FunctionalDependencyDetector
        from core.analysis.key_finder import CandidateKeyFinder

        results: Dict[str, Any] = {
            "connection": connection,
            "schema": schema or "public",
            "tables": [],
            "functional_dependencies": {},
            "candidate_keys": {},
            "quality_summary": {},
        }

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            # Check if connection is MCP server or direct connection
            if connection.startswith(("postgresql://", "postgres://", "mysql://", "sqlite://")):
                # Direct database connection
                task = progress.add_task("[cyan]Connecting to database...", total=None)

                try:
                    # Try to use asyncpg for PostgreSQL
                    import asyncpg

                    # Parse connection string and connect
                    conn = await asyncpg.connect(connection)

                    # Create a simple connector wrapper
                    class AsyncPGConnector:
                        """Async PostgreSQL connector wrapper."""

                        def __init__(self, pg_conn):
                            self.conn = pg_conn

                        async def execute_query(self, query: str) -> List[Dict[str, Any]]:
                            """Execute query and return list of dictionaries."""
                            rows = await self.conn.fetch(query)
                            return [dict(row) for row in rows]

                        async def get_sample(self, tbl: str, schema_nm: str, limit: int) -> List[Dict[str, Any]]:
                            """Get sample data from table."""
                            query = f'SELECT * FROM "{schema_nm}"."{tbl}" LIMIT {limit}'
                            return await self.execute_query(query)

                    db = AsyncPGConnector(conn)

                    # Get schema info
                    schema_name = schema or "public"
                    tables_query = f"""
                        SELECT table_name
                        FROM information_schema.tables
                        WHERE table_schema = '{schema_name}'
                        AND table_type = 'BASE TABLE'
                    """
                    table_rows = await db.execute_query(tables_query)
                    table_names = [r["table_name"] for r in table_rows]

                    if tables:
                        table_names = [t for t in table_names if t in tables]

                    progress.update(task, completed=True)

                    # Initialize analyzers
                    profiler = EnhancedProfiler(db, sample_size=sample_size)
                    fd_detector = FunctionalDependencyDetector(db)
                    key_finder = CandidateKeyFinder(db)

                    analyze_task = progress.add_task(
                        "[green]Analyzing tables...",
                        total=len(table_names)
                    )

                    for table_name in table_names:
                        progress.update(analyze_task, description=f"[green]Profiling {table_name}...")

                        # Profile table
                        profile = await profiler.profile_table(schema_name, table_name)

                        table_info = {
                            "name": table_name,
                            "schema": schema_name,
                            "row_count": profile.row_count,
                            "column_count": profile.column_count,
                            "quality_score": profile.overall_quality_score,
                            "completeness_score": profile.completeness_score,
                            "columns": [
                                {
                                    "name": col.column_name,
                                    "data_type": col.statistics.data_type,
                                    "null_percentage": col.statistics.null_percentage,
                                    "distinct_count": col.statistics.distinct_count,
                                    "is_unique": col.statistics.is_unique,
                                    "semantic_type": col.inferred_semantic_type,
                                }
                                for col in profile.columns
                            ],
                        }
                        results["tables"].append(table_info)

                        # Detect FDs
                        progress.update(analyze_task, description=f"[green]Detecting FDs in {table_name}...")
                        fds = await fd_detector.discover_fds(schema_name, table_name)
                        results["functional_dependencies"][table_name] = [
                            {
                                "determinant": fd.determinant,
                                "dependent": fd.dependent,
                                "confidence": fd.confidence,
                                "is_partial": fd.is_partial,
                                "is_transitive": fd.is_transitive,
                            }
                            for fd in fds
                        ]

                        # Find candidate keys
                        progress.update(analyze_task, description=f"[green]Finding keys in {table_name}...")
                        key_analysis = await key_finder.analyze_keys(schema_name, table_name)
                        results["candidate_keys"][table_name] = {
                            "primary_key": key_analysis.primary_key,
                            "recommended_pk": key_analysis.recommended_primary_key,
                            "recommendation_reason": key_analysis.key_recommendation_reason,
                            "candidates": [
                                {
                                    "columns": ck.columns,
                                    "uniqueness": ck.uniqueness,
                                    "recommended": ck.recommended_as_primary,
                                }
                                for ck in key_analysis.candidate_keys
                            ],
                        }

                        progress.advance(analyze_task)

                    await conn.close()

                except ImportError:
                    console.print("[red]Error:[/red] asyncpg not installed. Run: pip install asyncpg")
                    raise typer.Exit(1)
                except Exception as e:
                    console.print(f"[red]Error connecting to database:[/red] {str(e)}")
                    raise typer.Exit(1)

            else:
                # MCP server connection
                console.print(f"[yellow]MCP server connections not yet implemented.[/yellow]")
                console.print(f"[dim]Use a direct database connection string instead.[/dim]")
                raise typer.Exit(1)

        # Calculate quality summary
        if results["tables"]:
            results["quality_summary"] = {
                "total_tables": len(results["tables"]),
                "total_columns": sum(t["column_count"] for t in results["tables"]),
                "total_rows": sum(t["row_count"] for t in results["tables"]),
                "avg_quality_score": sum(t["quality_score"] for t in results["tables"]) / len(results["tables"]),
                "total_fds": sum(len(fds) for fds in results["functional_dependencies"].values()),
            }

        return results

    try:
        results = asyncio.run(_run_analysis())

        if output_file:
            _save_output(results, output_file, fmt=output if output != "table" else "json")

        _format_output(results, output)

        # Summary panel
        console.print(Panel(
            f"[green]Analysis complete![/green]\n\n"
            f"[bold]Tables analyzed:[/bold] {results['quality_summary'].get('total_tables', 0)}\n"
            f"[bold]Total columns:[/bold] {results['quality_summary'].get('total_columns', 0)}\n"
            f"[bold]FDs discovered:[/bold] {results['quality_summary'].get('total_fds', 0)}\n"
            f"[bold]Avg quality score:[/bold] {results['quality_summary'].get('avg_quality_score', 0):.1f}%",
            title="Analysis Summary",
            border_style="green"
        ))

    except Exception as e:
        console.print(f"[red]Analysis failed:[/red] {str(e)}")
        raise typer.Exit(1)


@app.command()
def normalize(
    input_file: str = typer.Argument(..., help="Path to schema/analysis file"),
    target: str = typer.Option("3NF", "--target", "-t", help="Target normal form (1NF, 2NF, 3NF, BCNF)"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed violation info"),
):
    """
    Normalize schema to target normal form.

    Analyzes the input schema for normalization violations and
    applies decomposition to achieve the target normal form.

    Examples:
        dataforge normalize schema.json --target 3NF
        dataforge normalize analysis.yaml --target BCNF --output normalized.json
    """
    from core.normalization import ViolationDetector
    from core.models.schema import Table, Column
    from core.models.analysis import FunctionalDependency, CandidateKey

    console.print(f"\n[bold]Normalizing to {target}[/bold]\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Loading schema...", total=None)

        try:
            data = _load_json_or_yaml(input_file)
        except Exception as e:
            console.print(f"[red]Error loading file:[/red] {str(e)}")
            raise typer.Exit(1)

        # Parse tables from input
        parsed_tables: List[Table] = []
        fds_by_table: Dict[str, List[FunctionalDependency]] = {}
        keys_by_table: Dict[str, List[CandidateKey]] = {}

        progress.update(task, description="[cyan]Parsing schema...")

        if "tables" in data:
            for tbl_data in data["tables"]:
                columns = []
                for col_data in tbl_data.get("columns", []):
                    columns.append(Column(
                        name=col_data.get("name"),
                        data_type=col_data.get("data_type", "varchar"),
                        is_nullable=col_data.get("is_nullable", True),
                        is_primary_key=col_data.get("is_primary_key", False),
                        is_foreign_key=col_data.get("is_foreign_key", False),
                    ))

                tbl = Table(
                    name=tbl_data.get("name"),
                    schema_name=tbl_data.get("schema", "public"),
                    columns=columns,
                )
                parsed_tables.append(tbl)

        # Parse FDs if available
        if "functional_dependencies" in data:
            for table_name, fds in data["functional_dependencies"].items():
                fds_by_table[table_name] = [
                    FunctionalDependency(
                        determinant=fd.get("determinant", []),
                        dependent=fd.get("dependent", ""),
                        confidence=fd.get("confidence", 1.0),
                        is_partial=fd.get("is_partial", False),
                        is_transitive=fd.get("is_transitive", False),
                    )
                    for fd in fds
                ]

        # Parse candidate keys if available
        if "candidate_keys" in data:
            for table_name, key_data in data["candidate_keys"].items():
                if isinstance(key_data, dict) and "candidates" in key_data:
                    keys_by_table[table_name] = [
                        CandidateKey(
                            columns=k.get("columns", []),
                            uniqueness=k.get("uniqueness", 1.0),
                        )
                        for k in key_data.get("candidates", [])
                    ]

        if not parsed_tables:
            console.print("[red]Error:[/red] No tables found in input file.")
            raise typer.Exit(1)

        progress.update(task, description="[cyan]Detecting violations...")

        # Detect violations
        detector = ViolationDetector()
        all_violations: Dict[str, List[Dict[str, Any]]] = {"1nf": [], "2nf": [], "3nf": [], "bcnf": []}

        for tbl in parsed_tables:
            table_fds = fds_by_table.get(tbl.name, [])
            table_keys = keys_by_table.get(tbl.name, [])

            violations = detector.detect_all_violations(
                table=tbl,
                fds=table_fds,
                candidate_keys=[k.columns for k in table_keys] if table_keys else None,
            )

            for level, viols in violations.items():
                for v in viols:
                    all_violations[level].append({
                        "table": tbl.name,
                        "type": getattr(v, "violation_type", type(v).__name__),
                        "description": str(v),
                        "columns": list(getattr(v, "columns", [])) if hasattr(v, "columns") else [],
                    })

        progress.update(task, description="[cyan]Applying normalization...")

        # Determine current normal form
        current_nf = "BCNF"
        if all_violations["1nf"]:
            current_nf = "UNNORMALIZED"
        elif all_violations["2nf"]:
            current_nf = "1NF"
        elif all_violations["3nf"]:
            current_nf = "2NF"
        elif all_violations["bcnf"]:
            current_nf = "3NF"

        # Build result
        result: Dict[str, Any] = {
            "current_normal_form": current_nf,
            "target_normal_form": target,
            "violations": all_violations,
            "original_tables": [t.name for t in parsed_tables],
            "normalization_steps": [],
            "normalized_tables": [],
        }

        # Apply normalization based on target
        target_levels = {"1NF": 1, "2NF": 2, "3NF": 3, "BCNF": 4}
        target_level = target_levels.get(target, 3)

        if target_level >= 1 and all_violations["1nf"]:
            result["normalization_steps"].append({
                "step": "1NF",
                "action": "Remove non-atomic values and repeating groups",
                "violations_addressed": len(all_violations["1nf"]),
            })

        if target_level >= 2 and all_violations["2nf"]:
            result["normalization_steps"].append({
                "step": "2NF",
                "action": "Remove partial dependencies",
                "violations_addressed": len(all_violations["2nf"]),
            })

        if target_level >= 3 and all_violations["3nf"]:
            result["normalization_steps"].append({
                "step": "3NF",
                "action": "Remove transitive dependencies",
                "violations_addressed": len(all_violations["3nf"]),
            })

        if target_level >= 4 and all_violations["bcnf"]:
            result["normalization_steps"].append({
                "step": "BCNF",
                "action": "Ensure all determinants are superkeys",
                "violations_addressed": len(all_violations["bcnf"]),
            })

        # Add normalized table info
        for tbl in parsed_tables:
            result["normalized_tables"].append({
                "name": tbl.name,
                "columns": [c.name for c in tbl.columns],
                "primary_key": tbl.primary_key_columns,
            })

    # Display results
    console.print(Panel(
        f"[bold]Current Normal Form:[/bold] {current_nf}\n"
        f"[bold]Target Normal Form:[/bold] {target}\n"
        f"[bold]Violations Found:[/bold]\n"
        f"  - 1NF: {len(all_violations['1nf'])}\n"
        f"  - 2NF: {len(all_violations['2nf'])}\n"
        f"  - 3NF: {len(all_violations['3nf'])}\n"
        f"  - BCNF: {len(all_violations['bcnf'])}",
        title="Normalization Analysis",
        border_style="blue"
    ))

    if verbose:
        for level, violations in all_violations.items():
            if violations:
                viol_table = Table(title=f"{level.upper()} Violations")
                viol_table.add_column("Table", style="cyan")
                viol_table.add_column("Type", style="red")
                viol_table.add_column("Description", style="white")

                for v in violations:
                    viol_table.add_row(v["table"], str(v["type"]), str(v["description"])[:60])

                console.print(viol_table)

    if output:
        _save_output(result, output)
    else:
        console.print("\n[dim]Use --output to save normalized schema to file.[/dim]")


@app.command()
def design(
    requirements: str = typer.Argument(..., help="Business requirements or path to requirements file"),
    strategy: str = typer.Option("STAR_SCHEMA", "--strategy", "-s", help="Modeling strategy (STAR_SCHEMA, NORMALIZED_3NF, DATA_VAULT)"),
    input_schema: Optional[str] = typer.Option(None, "--input", "-i", help="Input schema file"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output design file"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="LLM model to use"),
):
    """
    Generate data model design from requirements.

    Uses LLM to generate a data model design based on business
    requirements and optionally an input schema analysis.

    Examples:
        dataforge design "Build a star schema for e-commerce analytics"
        dataforge design requirements.txt --strategy DATA_VAULT --input analysis.json
        dataforge design "Customer 360 view" --strategy NORMALIZED_3NF --output design.json
    """
    from core.utils.llm_client import LLMClient
    from core.prompts.modeling import (
        STAR_SCHEMA_DESIGN_PROMPT,
        NORMALIZED_3NF_DESIGN_PROMPT,
        DATA_VAULT_DESIGN_PROMPT,
        format_table_context,
        format_profile_context,
        format_analysis_context,
    )

    async def _run_design():
        console.print(f"\n[bold]Generating {strategy} Design[/bold]\n")

        # Load requirements
        req_path = Path(requirements)
        if req_path.exists():
            req_text = req_path.read_text()
        else:
            req_text = requirements

        # Load input schema if provided
        tables_context = ""
        profile_context = ""
        analysis_context = ""

        if input_schema:
            try:
                data = _load_json_or_yaml(input_schema)

                if "tables" in data:
                    tables_context = format_table_context(data["tables"])

                if "profiles" in data or "data_profiles" in data:
                    profiles = data.get("profiles") or data.get("data_profiles", {})
                    profile_context = format_profile_context(profiles)

                if "functional_dependencies" in data or "candidate_keys" in data:
                    analysis_context = format_analysis_context(
                        fds=data.get("functional_dependencies"),
                        keys=data.get("candidate_keys"),
                        relationships=data.get("relationships"),
                    )
            except Exception as e:
                console.print(f"[yellow]Warning:[/yellow] Could not load input schema: {e}")

        # Select prompt based on strategy
        strategy_upper = strategy.upper()
        if strategy_upper in ["STAR_SCHEMA", "STAR", "DIMENSIONAL"]:
            prompt_template = STAR_SCHEMA_DESIGN_PROMPT
            strategy_name = "Star Schema"
        elif strategy_upper in ["NORMALIZED_3NF", "3NF", "NORMALIZED"]:
            prompt_template = NORMALIZED_3NF_DESIGN_PROMPT
            strategy_name = "Normalized 3NF"
        elif strategy_upper in ["DATA_VAULT", "VAULT", "DV"]:
            prompt_template = DATA_VAULT_DESIGN_PROMPT
            strategy_name = "Data Vault 2.0"
        else:
            console.print(f"[red]Unknown strategy:[/red] {strategy}")
            console.print("Valid strategies: STAR_SCHEMA, NORMALIZED_3NF, DATA_VAULT")
            raise typer.Exit(1)

        # Format prompt
        prompt = prompt_template.format(
            requirements=req_text,
            tables_context=tables_context or "No input tables provided - design from requirements only.",
            profile_context=profile_context or "No profiling data available.",
            analysis_context=analysis_context or "No analysis data available.",
        )

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(f"[cyan]Generating {strategy_name} design with LLM...", total=None)

            try:
                client = LLMClient(model=model)
                response = await client.generate(
                    prompt=prompt,
                    system="You are an expert data architect. Generate data model designs as JSON.",
                    temperature=0.3,
                )

                # Parse JSON response
                content = response.content.strip()
                if content.startswith("```json"):
                    content = content[7:]
                if content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]

                design_data = json.loads(content.strip())

                progress.update(task, description="[green]Design generated successfully!")

                return design_data, response.usage

            except json.JSONDecodeError as e:
                console.print(f"[red]Error parsing LLM response:[/red] {e}")
                console.print(f"[dim]Raw response:[/dim]\n{response.content[:500]}...")
                raise typer.Exit(1)
            except Exception as e:
                console.print(f"[red]Error generating design:[/red] {str(e)}")
                raise typer.Exit(1)

    try:
        design_data, usage = asyncio.run(_run_design())

        # Count tables
        table_count = (
            len(design_data.get("dimensions", [])) +
            len(design_data.get("facts", [])) +
            len(design_data.get("entities", [])) +
            len(design_data.get("hubs", [])) +
            len(design_data.get("links", [])) +
            len(design_data.get("satellites", []))
        )

        # Display summary
        console.print(Panel(
            f"[green]Design generated successfully![/green]\n\n"
            f"[bold]Model Name:[/bold] {design_data.get('model_name', 'Unnamed')}\n"
            f"[bold]Strategy:[/bold] {design_data.get('strategy', strategy)}\n"
            f"[bold]Tables:[/bold] {table_count}\n"
            f"[bold]Tokens used:[/bold] {usage.total_tokens}\n"
            f"[bold]Cost:[/bold] ${usage.cost_usd:.4f}",
            title="Design Summary",
            border_style="green"
        ))

        # Show tables
        result_table = Table(title="Generated Tables")
        result_table.add_column("Name", style="cyan")
        result_table.add_column("Role", style="magenta")
        result_table.add_column("Columns", style="green")

        for dim in design_data.get("dimensions", []):
            result_table.add_row(dim.get("name", ""), "Dimension", str(len(dim.get("columns", []))))

        for fact in design_data.get("facts", []):
            result_table.add_row(fact.get("name", ""), "Fact", str(len(fact.get("columns", []))))

        for entity in design_data.get("entities", []):
            result_table.add_row(entity.get("name", ""), "Entity", str(len(entity.get("columns", []))))

        for hub in design_data.get("hubs", []):
            result_table.add_row(hub.get("name", ""), "Hub", str(len(hub.get("columns", []))))

        for link in design_data.get("links", []):
            result_table.add_row(link.get("name", ""), "Link", str(len(link.get("columns", []))))

        for sat in design_data.get("satellites", []):
            sat_cols = len(sat.get("columns", [])) + len(sat.get("attributes", []))
            result_table.add_row(sat.get("name", ""), "Satellite", str(sat_cols))

        console.print(result_table)

        if output:
            _save_output(design_data, output)

    except Exception as e:
        console.print(f"[red]Design generation failed:[/red] {str(e)}")
        raise typer.Exit(1)


@app.command()
def generate(
    design_file: str = typer.Argument(..., help="Path to design file"),
    output_dir: str = typer.Option("./output", "--output", "-o", help="Output directory"),
    fmt: str = typer.Option("dbt", "--format", "-f", help="Output format (sql, dbt, sqlalchemy)"),
    overwrite: bool = typer.Option(False, "--overwrite", help="Overwrite existing files"),
):
    """
    Generate code from data model design.

    Generates SQL DDL, dbt models, or SQLAlchemy models from
    a data model design file.

    Examples:
        dataforge generate design.json --format dbt --output ./dbt_project
        dataforge generate design.yaml --format sql --output ./sql
    """
    from core.generators.dbt_generator import DBTGenerator, ModelDesign as DBTModelDesign

    console.print(f"\n[bold]Generating {fmt} code[/bold]\n")

    output_path = Path(output_dir)
    if output_path.exists() and not overwrite:
        if list(output_path.iterdir()):
            console.print(f"[yellow]Warning:[/yellow] Output directory is not empty: {output_dir}")
            console.print("Use --overwrite to overwrite existing files.")
            if not typer.confirm("Continue anyway?"):
                raise typer.Exit(0)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Loading design...", total=None)

        try:
            design_data = _load_json_or_yaml(design_file)
        except Exception as e:
            console.print(f"[red]Error loading design file:[/red] {str(e)}")
            raise typer.Exit(1)

        progress.update(task, description=f"[cyan]Generating {fmt} code...")

        if fmt.lower() == "dbt":
            try:
                # Convert design to DBT format
                from core.generators.dbt_generator import (
                    SourceDefinition, TableDefinition, ColumnDefinition,
                    StagingModelDefinition, DimensionModelDefinition, FactModelDefinition,
                )

                project_name = design_data.get("model_name", "dataforge_project").replace(" ", "_").lower()

                # Build source definitions
                sources: List[Any] = []
                staging_models: List[StagingModelDefinition] = []
                dimension_models: List[DimensionModelDefinition] = []
                fact_models: List[FactModelDefinition] = []

                # Process staging models
                for stg in design_data.get("staging_models", []):
                    columns = [
                        ColumnDefinition(
                            name=col.get("name"),
                            data_type=col.get("data_type", "varchar"),
                            description=col.get("description"),
                            is_primary_key=col.get("role") == "surrogate_key" or col.get("is_primary_key", False),
                        )
                        for col in stg.get("columns", [])
                    ]

                    source_table = TableDefinition(
                        name=stg.get("name", "").replace("stg_", ""),
                        schema="source",
                        columns=columns,
                        description=stg.get("description", ""),
                    )

                    staging_models.append(StagingModelDefinition(
                        name=stg.get("name", "").replace("stg_", ""),
                        source_table=source_table,
                        columns=columns,
                        description=stg.get("description", ""),
                    ))

                # Process dimensions
                for dim in design_data.get("dimensions", []):
                    columns = [
                        ColumnDefinition(
                            name=col.get("name"),
                            data_type=col.get("data_type", "varchar"),
                            description=col.get("description"),
                            is_primary_key=col.get("role") == "surrogate_key" or col.get("is_primary_key", False),
                            is_foreign_key=col.get("role") == "foreign_key",
                            foreign_key_table=col.get("references_table"),
                            foreign_key_column=col.get("references_column"),
                        )
                        for col in dim.get("columns", [])
                    ]

                    dimension_models.append(DimensionModelDefinition(
                        name=dim.get("name", "").replace("dim_", ""),
                        source_models=dim.get("source_tables", []),
                        columns=columns,
                        description=dim.get("description", ""),
                        slowly_changing_type=dim.get("scd_type", 1),
                    ))

                # Process facts
                for fact in design_data.get("facts", []):
                    columns = [
                        ColumnDefinition(
                            name=col.get("name"),
                            data_type=col.get("data_type", "varchar"),
                            description=col.get("description"),
                            is_primary_key=col.get("role") == "surrogate_key" or col.get("is_primary_key", False),
                            is_foreign_key=col.get("role") == "foreign_key",
                            foreign_key_table=col.get("references_table"),
                            foreign_key_column=col.get("references_column"),
                        )
                        for col in fact.get("columns", [])
                    ]

                    measures = [m.get("name") for m in fact.get("measures", [])]

                    fact_models.append(FactModelDefinition(
                        name=fact.get("name", "").replace("fact_", ""),
                        source_models=fact.get("source_tables", []),
                        grain=fact.get("grain", "one row per event"),
                        columns=columns,
                        measures=measures,
                        dimensions=fact.get("dimension_keys", []),
                        description=fact.get("description", ""),
                    ))

                # Create model design
                dbt_design = DBTModelDesign(
                    project_name=project_name,
                    sources=sources,
                    staging_models=staging_models,
                    dimension_models=dimension_models,
                    fact_models=fact_models,
                    target_database=design_data.get("target_database", "analytics"),
                    target_schema=design_data.get("target_schema", "analytics"),
                )

                # Generate
                generator = DBTGenerator(project_name, target_dir=output_path)
                generator.generate_project(dbt_design)
                generator.write_to_disk()

                progress.update(task, description="[green]Generation complete!")

            except Exception as e:
                console.print(f"[red]Error generating dbt project:[/red] {str(e)}")
                import traceback
                traceback.print_exc()
                raise typer.Exit(1)

        elif fmt.lower() == "sql":
            # Generate raw SQL DDL
            progress.update(task, description="[cyan]Generating SQL DDL...")

            sql_files: Dict[str, str] = {}

            # Generate DDL for each table
            for table_type in ["dimensions", "facts", "entities", "hubs", "links", "satellites"]:
                for tbl in design_data.get(table_type, []):
                    table_name = tbl.get("name", "")
                    columns = tbl.get("columns", [])

                    col_defs = []
                    for col in columns:
                        col_def = f"    {col.get('name')} {col.get('data_type', 'VARCHAR')}"
                        if not col.get("is_nullable", True):
                            col_def += " NOT NULL"
                        if col.get("is_primary_key"):
                            col_def += " PRIMARY KEY"
                        col_defs.append(col_def)

                    ddl = f"CREATE TABLE {table_name} (\n"
                    ddl += ",\n".join(col_defs)
                    ddl += "\n);\n"

                    sql_files[f"{table_name}.sql"] = ddl

            # Write files
            output_path.mkdir(parents=True, exist_ok=True)
            for filename, content in sql_files.items():
                (output_path / filename).write_text(content)

            progress.update(task, description="[green]Generation complete!")

        else:
            console.print(f"[red]Unsupported format:[/red] {fmt}")
            console.print("Supported formats: dbt, sql")
            raise typer.Exit(1)

    # Summary
    file_count = len(list(output_path.rglob("*"))) if output_path.exists() else 0
    console.print(Panel(
        f"[green]Code generation complete![/green]\n\n"
        f"[bold]Format:[/bold] {fmt}\n"
        f"[bold]Output directory:[/bold] {output_path.absolute()}\n"
        f"[bold]Files generated:[/bold] {file_count}",
        title="Generation Summary",
        border_style="green"
    ))


@app.command()
def validate(
    path: str = typer.Argument(..., help="Path to validate (schema, design, or generated output)"),
    type: Optional[str] = typer.Option(None, "--type", "-t", help="Validation type (schema, design, output)"),
    strict: bool = typer.Option(False, "--strict", help="Fail on warnings"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output report file"),
):
    """
    Validate schema, design, or generated output.

    Performs validation checks appropriate to the content type:
    - schema: Validates table structure, keys, data types
    - design: Validates model design completeness and best practices
    - output: Validates generated code syntax and conventions

    Examples:
        dataforge validate schema.json --type schema
        dataforge validate design.yaml --type design --strict
        dataforge validate ./dbt_project --type output
    """
    from core.validators import (
        SchemaValidator,
        DesignValidator,
        OutputValidator,
    )

    console.print(f"\n[bold]Validating:[/bold] {path}\n")

    file_path = Path(path)
    validation_type = type

    # Auto-detect type if not provided
    if not validation_type:
        if file_path.is_dir():
            validation_type = "output"
        elif file_path.suffix.lower() in [".json", ".yaml", ".yml"]:
            try:
                data = _load_json_or_yaml(path)
                if any(key in data for key in ["dimensions", "facts", "entities", "hubs"]):
                    validation_type = "design"
                else:
                    validation_type = "schema"
            except Exception:
                validation_type = "schema"
        else:
            validation_type = "output"

    console.print(f"[dim]Validation type: {validation_type}[/dim]\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(f"[cyan]Running {validation_type} validation...", total=None)

        result: Dict[str, Any] = {
            "path": str(path),
            "type": validation_type,
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "info": [],
        }

        if validation_type == "schema":
            try:
                data = _load_json_or_yaml(path)
                validator = SchemaValidator()

                for tbl_data in data.get("tables", []):
                    from core.models.schema import Table, Column
                    columns = [
                        Column(
                            name=col.get("name"),
                            data_type=col.get("data_type", "varchar"),
                            is_nullable=col.get("is_nullable", True),
                            is_primary_key=col.get("is_primary_key", False),
                        )
                        for col in tbl_data.get("columns", [])
                    ]
                    tbl = Table(
                        name=tbl_data.get("name"),
                        schema_name=tbl_data.get("schema", "public"),
                        columns=columns,
                    )
                    report = validator.validate_table(tbl)

                    result["errors"].extend(report.errors)
                    result["warnings"].extend(report.warnings)

            except Exception as e:
                result["errors"].append(f"Failed to load schema: {str(e)}")

        elif validation_type == "design":
            try:
                data = _load_json_or_yaml(path)
                validator = DesignValidator()

                from core.models.design import ModelDesign, ModelingStrategy

                # Parse design
                strategy_map = {
                    "star_schema": ModelingStrategy.STAR_SCHEMA,
                    "normalized_3nf": ModelingStrategy.NORMALIZED_3NF,
                    "data_vault": ModelingStrategy.DATA_VAULT,
                }

                design_strategy = strategy_map.get(
                    data.get("strategy", "star_schema").lower(),
                    ModelingStrategy.STAR_SCHEMA
                )

                model_design = ModelDesign(
                    name=data.get("model_name", "Design"),
                    strategy=design_strategy,
                    tables=[],
                    relationships=[],
                )

                report = validator.validate(model_design)

                result["is_valid"] = report.is_valid
                result["errors"].extend([str(i) for i in report.critical_issues])
                result["warnings"].extend([str(i) for i in report.issues])
                result["info"].append(f"Score: {report.score}/100")

            except Exception as e:
                result["errors"].append(f"Failed to validate design: {str(e)}")

        elif validation_type == "output":
            try:
                validator = OutputValidator()

                if file_path.is_dir():
                    # Validate directory of files
                    for sql_file in file_path.rglob("*.sql"):
                        content = sql_file.read_text()
                        report = validator.validate_sql(content)
                        for issue in report.issues:
                            target = result["errors"] if issue.severity == "error" else result["warnings"]
                            target.append(f"{sql_file.name}: {issue.message}")
                else:
                    # Single file
                    content = file_path.read_text()
                    report = validator.validate_sql(content)
                    for issue in report.issues:
                        target = result["errors"] if issue.severity == "error" else result["warnings"]
                        target.append(issue.message)

            except Exception as e:
                result["errors"].append(f"Failed to validate output: {str(e)}")

        result["is_valid"] = len(result["errors"]) == 0
        if strict and result["warnings"]:
            result["is_valid"] = False

        progress.update(task, description="[green]Validation complete!")

    # Display results
    if result["is_valid"]:
        status = "[green]VALID[/green]"
        border = "green"
    else:
        status = "[red]INVALID[/red]"
        border = "red"

    console.print(Panel(
        f"[bold]Status:[/bold] {status}\n"
        f"[bold]Errors:[/bold] {len(result['errors'])}\n"
        f"[bold]Warnings:[/bold] {len(result['warnings'])}",
        title=f"{validation_type.title()} Validation Results",
        border_style=border
    ))

    if result["errors"]:
        console.print("\n[red]Errors:[/red]")
        for err in result["errors"]:
            console.print(f"  [red]x[/red] {err}")

    if result["warnings"]:
        console.print("\n[yellow]Warnings:[/yellow]")
        for warn in result["warnings"]:
            console.print(f"  [yellow]![/yellow] {warn}")

    if result["info"]:
        console.print("\n[blue]Info:[/blue]")
        for info in result["info"]:
            console.print(f"  [blue]i[/blue] {info}")

    if output:
        _save_output(result, output)

    if not result["is_valid"]:
        raise typer.Exit(1)


def main():
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
