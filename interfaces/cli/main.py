"""
DataForge CLI - Command-line interface for DataForge.

This is the main entry point for the DataForge CLI application.
"""

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

app = typer.Typer(
    name="dataforge",
    help="AI-powered data engineering platform",
    add_completion=False,
)

console = Console()


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
            f"[green]✓[/green] Workspace created successfully!\n\n"
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


@app.command()
def list():
    """List all DataForge workspaces."""
    from core.workspace.manager import WorkspaceManager
    from rich.table import Table

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
def chat():
    """Start an interactive chat session with DataForge."""
    console.print("\n[bold blue]DataForge Chat[/bold blue]")
    console.print("[dim]Type 'exit' or 'quit' to end the session[/dim]\n")

    console.print("[yellow]Chat interface coming soon![/yellow]")
    console.print("[dim]This will provide an interactive conversation with the AI agent.[/dim]\n")

    # TODO: Implement interactive chat
    # This will use the DataModelingAgent to have conversations


@app.command()
def status():
    """Show status of DataForge and connected services."""
    from core.utils.config import settings
    from rich.table import Table

    console.print("\n[bold]DataForge Status[/bold]\n")

    # Configuration
    table = Table(title="Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Environment", settings.dataforge_env)
    table.add_row("Log Level", settings.dataforge_log_level)
    table.add_row("Workspace Dir", settings.dataforge_workspace_dir)
    table.add_row("Default Model", settings.default_model)
    table.add_row("API Key", "✓ Set" if settings.anthropic_api_key else "✗ Not set")

    console.print(table)

    # MCP Servers
    console.print("\n[dim]MCP servers status coming soon...[/dim]\n")


def main():
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
