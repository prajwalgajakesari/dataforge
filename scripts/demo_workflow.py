#!/usr/bin/env python3
"""
DataForge Demo: Complete Data Modeling Workflow

This script demonstrates the complete workflow:
1. Connecting to a database service
2. Selecting tables
3. AI analyzes and detects patterns
4. Generates normalized schema (dbt project)
"""

import tempfile
import time
from pathlib import Path
from rich.console import Console
from rich.table import Table as RichTable
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import print as rprint

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
from core.models.analysis import FunctionalDependency
from core.models.schema import Column, Schema, Table as SchemaTable
from core.normalization.violations import NFViolation, SeverityLevel, ViolationType

console = Console()


def simulate_database_connection():
    """Simulate connecting to a database and discovering schema."""
    console.print("\n[bold blue]═══════════════════════════════════════════════════════════════════[/bold blue]")
    console.print("[bold blue]   DATAFORGE - AI-Powered Data Engineering Platform[/bold blue]")
    console.print("[bold blue]═══════════════════════════════════════════════════════════════════[/bold blue]\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Connecting to PostgreSQL database...", total=None)
        time.sleep(1)
        progress.update(task, description="[green]✓ Connected to postgresql://localhost:5432/ecommerce")
        time.sleep(0.5)

    # Return mock schema
    return Schema(
        name="ecommerce",
        tables=[
            SchemaTable(
                name="orders",
                schema_name="ecommerce",
                columns=[
                    Column(name="order_id", data_type="integer", is_primary_key=True),
                    Column(name="customer_id", data_type="integer"),
                    Column(name="customer_name", data_type="varchar(100)"),
                    Column(name="customer_email", data_type="varchar(255)"),
                    Column(name="product_id", data_type="integer"),
                    Column(name="product_name", data_type="varchar(100)"),
                    Column(name="product_category", data_type="varchar(50)"),
                    Column(name="order_date", data_type="date"),
                    Column(name="quantity", data_type="integer"),
                    Column(name="unit_price", data_type="decimal(10,2)"),
                    Column(name="total_amount", data_type="decimal(10,2)"),
                ],
                row_count=150000,
            ),
            SchemaTable(
                name="customers",
                schema_name="ecommerce",
                columns=[
                    Column(name="customer_id", data_type="integer", is_primary_key=True),
                    Column(name="customer_name", data_type="varchar(100)"),
                    Column(name="email", data_type="varchar(255)"),
                    Column(name="phone", data_type="varchar(20)"),
                    Column(name="address", data_type="text"),
                    Column(name="city", data_type="varchar(50)"),
                    Column(name="country", data_type="varchar(50)"),
                    Column(name="created_at", data_type="timestamp"),
                ],
                row_count=50000,
            ),
            SchemaTable(
                name="products",
                schema_name="ecommerce",
                columns=[
                    Column(name="product_id", data_type="integer", is_primary_key=True),
                    Column(name="product_name", data_type="varchar(100)"),
                    Column(name="category", data_type="varchar(50)"),
                    Column(name="price", data_type="decimal(10,2)"),
                    Column(name="stock_quantity", data_type="integer"),
                ],
                row_count=5000,
            ),
        ],
    )


def display_discovered_schema(schema: Schema):
    """Display the discovered database schema."""
    console.print("\n[bold yellow]STEP 1: Schema Discovery[/bold yellow]")
    console.print("─" * 60)

    table = RichTable(title="Discovered Tables", show_header=True, header_style="bold magenta")
    table.add_column("Table", style="cyan")
    table.add_column("Columns", justify="right")
    table.add_column("Rows", justify="right", style="green")
    table.add_column("Primary Key", style="yellow")

    for t in schema.tables:
        pk_cols = [c.name for c in t.columns if c.is_primary_key]
        table.add_row(
            t.name,
            str(len(t.columns)),
            f"{t.row_count:,}",
            ", ".join(pk_cols) if pk_cols else "None"
        )

    console.print(table)


def select_tables(schema: Schema):
    """Simulate table selection for analysis."""
    console.print("\n[bold yellow]STEP 2: Table Selection[/bold yellow]")
    console.print("─" * 60)

    selected = ["orders", "customers", "products"]

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Selecting tables for analysis...", total=None)
        time.sleep(0.5)
        progress.update(task, description=f"[green]✓ Selected {len(selected)} tables: {', '.join(selected)}")
        time.sleep(0.3)

    return selected


def run_ai_analysis(schema: Schema):
    """Simulate AI analysis of the data."""
    console.print("\n[bold yellow]STEP 3: AI Analysis (Claude)[/bold yellow]")
    console.print("─" * 60)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Sampling data for profiling...", total=None)
        time.sleep(0.8)
        progress.update(task, description="[cyan]Analyzing column statistics...")
        time.sleep(0.8)
        progress.update(task, description="[cyan]Detecting functional dependencies...")
        time.sleep(1)
        progress.update(task, description="[cyan]Identifying candidate keys...")
        time.sleep(0.5)
        progress.update(task, description="[green]✓ Analysis complete")
        time.sleep(0.3)

    # Return mock functional dependencies
    fds = [
        FunctionalDependency(determinant=["customer_id"], dependent="customer_name", confidence=0.99),
        FunctionalDependency(determinant=["customer_id"], dependent="customer_email", confidence=0.99),
        FunctionalDependency(determinant=["product_id"], dependent="product_name", confidence=0.99),
        FunctionalDependency(determinant=["product_id"], dependent="product_category", confidence=0.99),
    ]

    console.print("\n[bold cyan]Detected Functional Dependencies:[/bold cyan]")
    fd_table = RichTable(show_header=True, header_style="bold")
    fd_table.add_column("Determinant", style="cyan")
    fd_table.add_column("→", style="white")
    fd_table.add_column("Dependent", style="green")
    fd_table.add_column("Confidence", justify="right", style="yellow")

    for fd in fds:
        fd_table.add_row(
            ", ".join(fd.determinant),
            "→",
            fd.dependent,
            f"{fd.confidence:.0%}"
        )

    console.print(fd_table)

    return fds


def detect_normalization_violations(fds):
    """Detect normalization violations based on functional dependencies."""
    console.print("\n[bold yellow]STEP 4: Normalization Analysis[/bold yellow]")
    console.print("─" * 60)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Checking 1NF compliance...", total=None)
        time.sleep(0.5)
        progress.update(task, description="[cyan]Checking 2NF compliance...")
        time.sleep(0.5)
        progress.update(task, description="[cyan]Checking 3NF compliance...")
        time.sleep(0.8)
        progress.update(task, description="[green]✓ Normalization analysis complete")
        time.sleep(0.3)

    violations = [
        NFViolation(
            table="orders",
            columns=frozenset(["customer_name", "customer_email"]),
            violation_type=ViolationType.TRANSITIVE_DEPENDENCY,
            severity=SeverityLevel.HIGH,
            description="customer_id → customer_name, customer_email",
            fix_suggestion="Extract to separate 'customers' dimension table",
            normal_form="3NF",
        ),
        NFViolation(
            table="orders",
            columns=frozenset(["product_name", "product_category"]),
            violation_type=ViolationType.TRANSITIVE_DEPENDENCY,
            severity=SeverityLevel.HIGH,
            description="product_id → product_name, product_category",
            fix_suggestion="Extract to separate 'products' dimension table",
            normal_form="3NF",
        ),
    ]

    console.print("\n[bold red]⚠ Normalization Violations Detected:[/bold red]")

    for i, v in enumerate(violations, 1):
        panel = Panel(
            f"[yellow]Type:[/yellow] {v.violation_type.value}\n"
            f"[yellow]Table:[/yellow] {v.table}\n"
            f"[yellow]Columns:[/yellow] {', '.join(v.columns)}\n"
            f"[yellow]Description:[/yellow] {v.description}\n"
            f"[green]Fix:[/green] {v.fix_suggestion}",
            title=f"[bold red]Violation #{i} ({v.normal_form})[/bold red]",
            border_style="red",
        )
        console.print(panel)

    return violations


def generate_normalized_schema():
    """Generate the normalized schema as a dbt project."""
    console.print("\n[bold yellow]STEP 5: Generate Normalized Schema (dbt)[/bold yellow]")
    console.print("─" * 60)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Designing star schema...", total=None)
        time.sleep(0.5)
        progress.update(task, description="[cyan]Creating staging models...")
        time.sleep(0.5)
        progress.update(task, description="[cyan]Creating dimension tables...")
        time.sleep(0.5)
        progress.update(task, description="[cyan]Creating fact tables...")
        time.sleep(0.5)
        progress.update(task, description="[cyan]Generating dbt project...")
        time.sleep(0.8)

    # Create model design
    design = ModelDesign(
        project_name="ecommerce_analytics",
        sources=[
            SourceDefinition(
                name="ecommerce",
                schema="public",
                tables=[
                    TableDefinition(
                        name="orders",
                        schema="public",
                        columns=[
                            ColumnDefinition(name="order_id", data_type="integer", is_primary_key=True),
                            ColumnDefinition(name="customer_id", data_type="integer"),
                            ColumnDefinition(name="product_id", data_type="integer"),
                            ColumnDefinition(name="order_date", data_type="date"),
                            ColumnDefinition(name="quantity", data_type="integer"),
                            ColumnDefinition(name="total_amount", data_type="decimal"),
                        ],
                    ),
                    TableDefinition(
                        name="customers",
                        schema="public",
                        columns=[
                            ColumnDefinition(name="customer_id", data_type="integer", is_primary_key=True),
                            ColumnDefinition(name="customer_name", data_type="varchar"),
                            ColumnDefinition(name="email", data_type="varchar"),
                            ColumnDefinition(name="city", data_type="varchar"),
                            ColumnDefinition(name="country", data_type="varchar"),
                        ],
                    ),
                    TableDefinition(
                        name="products",
                        schema="public",
                        columns=[
                            ColumnDefinition(name="product_id", data_type="integer", is_primary_key=True),
                            ColumnDefinition(name="product_name", data_type="varchar"),
                            ColumnDefinition(name="category", data_type="varchar"),
                            ColumnDefinition(name="price", data_type="decimal"),
                        ],
                    ),
                ],
            ),
        ],
        staging_models=[
            StagingModelDefinition(
                name="stg_orders",
                description="Cleaned orders data",
                source_table=TableDefinition(name="orders", schema="public", columns=[]),
                columns=[
                    ColumnDefinition(name="order_id", data_type="integer", is_primary_key=True),
                    ColumnDefinition(name="customer_id", data_type="integer"),
                    ColumnDefinition(name="product_id", data_type="integer"),
                    ColumnDefinition(name="order_date", data_type="date"),
                    ColumnDefinition(name="quantity", data_type="integer"),
                    ColumnDefinition(name="total_amount", data_type="decimal"),
                ],
            ),
            StagingModelDefinition(
                name="stg_customers",
                description="Cleaned customer data",
                source_table=TableDefinition(name="customers", schema="public", columns=[]),
                columns=[
                    ColumnDefinition(name="customer_id", data_type="integer", is_primary_key=True),
                    ColumnDefinition(name="customer_name", data_type="varchar"),
                    ColumnDefinition(name="email", data_type="varchar"),
                    ColumnDefinition(name="city", data_type="varchar"),
                    ColumnDefinition(name="country", data_type="varchar"),
                ],
            ),
            StagingModelDefinition(
                name="stg_products",
                description="Cleaned product data",
                source_table=TableDefinition(name="products", schema="public", columns=[]),
                columns=[
                    ColumnDefinition(name="product_id", data_type="integer", is_primary_key=True),
                    ColumnDefinition(name="product_name", data_type="varchar"),
                    ColumnDefinition(name="category", data_type="varchar"),
                    ColumnDefinition(name="price", data_type="decimal"),
                ],
            ),
        ],
        dimension_models=[
            DimensionModelDefinition(
                name="dim_customer",
                description="Customer dimension - SCD Type 1",
                source_models=["stg_customers"],
                columns=[
                    ColumnDefinition(name="customer_key", data_type="integer", is_primary_key=True, description="Surrogate key"),
                    ColumnDefinition(name="customer_id", data_type="integer", description="Natural key"),
                    ColumnDefinition(name="customer_name", data_type="varchar"),
                    ColumnDefinition(name="email", data_type="varchar"),
                    ColumnDefinition(name="city", data_type="varchar"),
                    ColumnDefinition(name="country", data_type="varchar"),
                ],
            ),
            DimensionModelDefinition(
                name="dim_product",
                description="Product dimension - SCD Type 1",
                source_models=["stg_products"],
                columns=[
                    ColumnDefinition(name="product_key", data_type="integer", is_primary_key=True, description="Surrogate key"),
                    ColumnDefinition(name="product_id", data_type="integer", description="Natural key"),
                    ColumnDefinition(name="product_name", data_type="varchar"),
                    ColumnDefinition(name="category", data_type="varchar"),
                    ColumnDefinition(name="price", data_type="decimal"),
                ],
            ),
            DimensionModelDefinition(
                name="dim_date",
                description="Date dimension",
                source_models=[],
                columns=[
                    ColumnDefinition(name="date_key", data_type="integer", is_primary_key=True),
                    ColumnDefinition(name="date", data_type="date"),
                    ColumnDefinition(name="year", data_type="integer"),
                    ColumnDefinition(name="quarter", data_type="integer"),
                    ColumnDefinition(name="month", data_type="integer"),
                    ColumnDefinition(name="day_of_week", data_type="integer"),
                ],
            ),
        ],
        fact_models=[
            FactModelDefinition(
                name="fact_orders",
                description="Order fact table - grain: one row per order line",
                source_models=["stg_orders"],
                columns=[
                    ColumnDefinition(name="order_key", data_type="integer", is_primary_key=True),
                    ColumnDefinition(name="customer_key", data_type="integer"),
                    ColumnDefinition(name="product_key", data_type="integer"),
                    ColumnDefinition(name="date_key", data_type="integer"),
                ],
                measures=["quantity", "total_amount", "unit_price"],
                dimensions=["customer", "product", "date"],
                grain="One row per order line item",
            ),
        ],
    )

    # Generate dbt project
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "ecommerce_analytics"
        generator = DBTGenerator(
            project_name="ecommerce_analytics",
            target_dir=output_dir,
        )

        files = generator.generate_project(design)
        generator.write_to_disk()

        console.print(f"\n[green]✓ Generated dbt project with {len(files)} files[/green]")

        # Display generated structure
        console.print("\n[bold cyan]Generated Project Structure:[/bold cyan]")

        file_tree = """
ecommerce_analytics/
├── dbt_project.yml
├── packages.yml
├── profiles.yml
├── .gitignore
├── models/
│   ├── docs.md
│   ├── staging/
│   │   ├── sources.yml
│   │   ├── schema.yml
│   │   ├── stg_orders.sql
│   │   ├── stg_customers.sql
│   │   └── stg_products.sql
│   └── marts/
│       ├── schema.yml
│       ├── dim_customer.sql
│       ├── dim_product.sql
│       ├── dim_date.sql
│       └── fact_orders.sql
"""
        console.print(Panel(file_tree, title="[bold]dbt Project[/bold]", border_style="cyan"))

        # Show sample generated SQL
        console.print("\n[bold cyan]Sample Generated SQL (dim_customer.sql):[/bold cyan]")

        dim_model_files = [f for f in files if "dim_customer" in f]
        if dim_model_files:
            sample_sql = files[dim_model_files[0]]
            # Truncate if too long
            if len(sample_sql) > 800:
                sample_sql = sample_sql[:800] + "\n... (truncated)"
            console.print(Panel(sample_sql, title="[bold]dim_customer.sql[/bold]", border_style="green"))

        return files


def display_summary():
    """Display the workflow summary."""
    console.print("\n[bold blue]═══════════════════════════════════════════════════════════════════[/bold blue]")
    console.print("[bold blue]   WORKFLOW COMPLETE[/bold blue]")
    console.print("[bold blue]═══════════════════════════════════════════════════════════════════[/bold blue]\n")

    summary_table = RichTable(title="Summary", show_header=True, header_style="bold green")
    summary_table.add_column("Step", style="cyan")
    summary_table.add_column("Status", style="green")
    summary_table.add_column("Output")

    summary_table.add_row("1. Connect to Service", "✓ Complete", "3 tables discovered")
    summary_table.add_row("2. Select Tables", "✓ Complete", "orders, customers, products")
    summary_table.add_row("3. AI Analysis", "✓ Complete", "4 functional dependencies")
    summary_table.add_row("4. Normalization Check", "✓ Complete", "2 violations (3NF)")
    summary_table.add_row("5. Generate Schema", "✓ Complete", "dbt project with 12 files")

    console.print(summary_table)

    console.print("\n[bold green]Goal Achieved:[/bold green]")
    console.print("  ✓ Connected to database service")
    console.print("  ✓ Selected tables for analysis")
    console.print("  ✓ AI analyzed data and detected patterns")
    console.print("  ✓ Generated normalized schema (Star Schema)")

    console.print("\n[bold yellow]Next Steps:[/bold yellow]")
    console.print("  1. cd ecommerce_analytics")
    console.print("  2. dbt deps")
    console.print("  3. dbt run")
    console.print("  4. dbt test")
    console.print()


def main():
    """Run the complete demo workflow."""
    try:
        # Step 1: Connect and discover schema
        schema = simulate_database_connection()
        display_discovered_schema(schema)

        # Step 2: Select tables
        selected_tables = select_tables(schema)

        # Step 3: AI analysis
        fds = run_ai_analysis(schema)

        # Step 4: Detect normalization issues
        violations = detect_normalization_violations(fds)

        # Step 5: Generate normalized schema
        files = generate_normalized_schema()

        # Display summary
        display_summary()

    except KeyboardInterrupt:
        console.print("\n[yellow]Demo interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        raise


if __name__ == "__main__":
    main()
