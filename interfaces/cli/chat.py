"""
Interactive Chat Mode for DataForge.

Provides an interactive chat interface for data modeling conversations.
Users can have natural conversations about their data modeling needs,
load schemas, analyze tables, design data models, and generate artifacts.
"""

import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.spinner import Spinner
from rich.text import Text

from core.prompts.modeling import (
    DATA_PROFILING_SUMMARY_PROMPT,
    DESIGN_REVIEW_PROMPT,
    RELATIONSHIP_INFERENCE_PROMPT,
    STAR_SCHEMA_DESIGN_PROMPT,
    TABLE_RELEVANCE_PROMPT,
    format_analysis_context,
    format_profile_context,
    format_table_context,
)
from core.utils.llm_client import LLMClient


class ChatContext:
    """Maintains the current context for the chat session."""

    def __init__(self):
        """Initialize empty context."""
        self.schema: Optional[Dict[str, Any]] = None
        self.tables: List[Dict[str, Any]] = []
        self.profiles: Dict[str, Any] = {}
        self.analysis: Dict[str, Any] = {}
        self.design: Optional[Dict[str, Any]] = None
        self.requirements: Optional[str] = None
        self.current_step: str = "initial"

    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for serialization."""
        return {
            "schema": self.schema,
            "tables": self.tables,
            "profiles": self.profiles,
            "analysis": self.analysis,
            "design": self.design,
            "requirements": self.requirements,
            "current_step": self.current_step,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChatContext":
        """Create context from dictionary."""
        ctx = cls()
        ctx.schema = data.get("schema")
        ctx.tables = data.get("tables", [])
        ctx.profiles = data.get("profiles", {})
        ctx.analysis = data.get("analysis", {})
        ctx.design = data.get("design")
        ctx.requirements = data.get("requirements")
        ctx.current_step = data.get("current_step", "initial")
        return ctx

    def get_summary(self) -> str:
        """Get a summary of the current context."""
        parts = []

        if self.schema:
            parts.append(f"Schema: {self.schema.get('name', 'unnamed')}")

        if self.tables:
            parts.append(f"Tables: {len(self.tables)} loaded")

        if self.profiles:
            parts.append(f"Profiles: {len(self.profiles)} analyzed")

        if self.analysis:
            if self.analysis.get("relationships"):
                parts.append(f"Relationships: {len(self.analysis['relationships'])} found")
            if self.analysis.get("functional_dependencies"):
                parts.append(f"FDs: {len(self.analysis['functional_dependencies'])} identified")

        if self.design:
            parts.append(f"Design: {self.design.get('strategy', 'unknown')} model")

        if self.requirements:
            req_preview = (
                self.requirements[:50] + "..."
                if len(self.requirements) > 50
                else self.requirements
            )
            parts.append(f"Requirements: \"{req_preview}\"")

        parts.append(f"Step: {self.current_step}")

        return "\n".join(f"  - {p}" for p in parts) if parts else "  (empty)"


class ChatSession:
    """
    Interactive chat session for data modeling.

    Provides a conversational interface for users to describe their data
    modeling needs, explore schemas, design models, and generate artifacts.
    """

    # Available commands
    COMMANDS = {
        "/help": "Show available commands",
        "/clear": "Clear conversation history",
        "/context": "Show current context",
        "/schema": "Load or show schema",
        "/analyze": "Analyze specific table",
        "/design": "Start design process",
        "/generate": "Generate from current design",
        "/validate": "Validate current work",
        "/save": "Save session to file",
        "/load": "Load session from file",
        "/exit": "Exit chat (or /quit)",
        "/quit": "Exit chat (or /exit)",
    }

    def __init__(self, workspace_path: Optional[str] = None):
        """
        Initialize the chat session.

        Args:
            workspace_path: Optional path to a workspace directory
        """
        self.console = Console()
        self.workspace_path = Path(workspace_path) if workspace_path else Path.cwd()
        self.conversation_history: List[Dict[str, str]] = []
        self.context = ChatContext()
        self.llm_client: Optional[LLMClient] = None
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        # System prompt for the chat
        self.system_prompt = """You are DataForge, an expert data modeling assistant. You help users:

1. Understand their data and requirements
2. Analyze database schemas and table structures
3. Design optimal data models (Star Schema, 3NF, Data Vault)
4. Generate DDL, dbt models, and documentation

You have access to the user's context including:
- Loaded schema and table definitions
- Data profiles and statistics
- Analysis results (relationships, functional dependencies)
- Current design progress

Be helpful, precise, and guide users through the data modeling process.
When suggesting next steps, reference the available commands they can use.

Available commands: /help, /context, /schema, /analyze, /design, /generate, /validate, /save, /load, /exit
"""

    def _init_llm_client(self) -> bool:
        """
        Initialize the LLM client.

        Returns:
            True if successful, False otherwise
        """
        try:
            self.llm_client = LLMClient()
            return True
        except ValueError as e:
            self.console.print(
                f"[red]Error:[/red] Could not initialize LLM client: {e}"
            )
            self.console.print(
                "[yellow]Hint:[/yellow] Make sure ANTHROPIC_API_KEY is set in your environment."
            )
            return False

    def _print_welcome(self) -> None:
        """Print welcome message and instructions."""
        welcome_text = """
Welcome to [bold blue]DataForge Chat[/bold blue]

I'm your AI-powered data modeling assistant. I can help you:
- Analyze database schemas and understand your data
- Design data models (Star Schema, 3NF, Data Vault)
- Generate DDL, dbt models, and documentation

[dim]Type your questions naturally, or use commands like /help for guidance.[/dim]
[dim]Type /exit or /quit to end the session.[/dim]
"""
        self.console.print(Panel(welcome_text, border_style="blue"))

    def _print_help(self) -> None:
        """Print available commands."""
        help_text = "[bold]Available Commands:[/bold]\n\n"
        for cmd, desc in self.COMMANDS.items():
            help_text += f"  [cyan]{cmd}[/cyan] - {desc}\n"

        help_text += "\n[bold]Workflow Tips:[/bold]\n\n"
        help_text += "  1. Start by describing your data modeling goals\n"
        help_text += "  2. Use /schema to load your database schema\n"
        help_text += "  3. Use /analyze [table] to explore specific tables\n"
        help_text += "  4. Use /design to start the model design process\n"
        help_text += "  5. Use /generate to create DDL or dbt models\n"
        help_text += "  6. Use /save to preserve your session\n"

        self.console.print(Panel(help_text, title="Help", border_style="green"))

    def _print_context(self) -> None:
        """Print current context information."""
        summary = self.context.get_summary()
        context_text = f"[bold]Current Context:[/bold]\n\n{summary}"

        if self.conversation_history:
            context_text += f"\n\nConversation: {len(self.conversation_history)} messages"

        self.console.print(Panel(context_text, title="Context", border_style="cyan"))

    async def _handle_command(self, user_input: str) -> bool:
        """
        Handle a slash command.

        Args:
            user_input: The command string (starts with /)

        Returns:
            True if should continue loop, False if should exit
        """
        parts = user_input.strip().split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if command in ("/exit", "/quit"):
            if self.conversation_history:
                if Confirm.ask("Save session before exiting?"):
                    await self._handle_save(args)
            self.console.print("\n[blue]Goodbye![/blue]\n")
            return False

        elif command == "/help":
            self._print_help()

        elif command == "/clear":
            self.conversation_history.clear()
            self.console.print("[green]Conversation history cleared.[/green]")

        elif command == "/context":
            self._print_context()

        elif command == "/schema":
            await self._handle_schema(args)

        elif command == "/analyze":
            await self._handle_analyze(args)

        elif command == "/design":
            await self._handle_design(args)

        elif command == "/generate":
            await self._handle_generate(args)

        elif command == "/validate":
            await self._handle_validate(args)

        elif command == "/save":
            await self._handle_save(args)

        elif command == "/load":
            await self._handle_load(args)

        else:
            self.console.print(
                f"[yellow]Unknown command:[/yellow] {command}\n"
                f"Type /help for available commands."
            )

        return True

    async def _handle_schema(self, args: str) -> None:
        """Handle /schema command."""
        if not args:
            if self.context.schema:
                self.console.print(
                    Panel(
                        f"[bold]Current Schema:[/bold] {self.context.schema.get('name', 'unnamed')}\n"
                        f"Tables: {len(self.context.tables)}",
                        title="Schema",
                        border_style="cyan",
                    )
                )
                if self.context.tables:
                    for table in self.context.tables[:10]:
                        self.console.print(f"  - {table.get('name', 'unknown')}")
                    if len(self.context.tables) > 10:
                        self.console.print(
                            f"  ... and {len(self.context.tables) - 10} more"
                        )
            else:
                self.console.print(
                    "[yellow]No schema loaded.[/yellow]\n"
                    "Usage: /schema [path_to_schema.json]\n"
                    "Or describe your schema in natural language."
                )
            return

        # Try to load schema from file
        schema_path = Path(args)
        if not schema_path.is_absolute():
            schema_path = self.workspace_path / args

        if schema_path.exists():
            try:
                with open(schema_path, "r") as f:
                    data = json.load(f)

                if "tables" in data:
                    self.context.schema = data.get("schema", {"name": schema_path.stem})
                    self.context.tables = data["tables"]
                elif isinstance(data, list):
                    self.context.schema = {"name": schema_path.stem}
                    self.context.tables = data
                else:
                    self.context.schema = {"name": schema_path.stem}
                    self.context.tables = [data]

                self.context.current_step = "schema_loaded"
                self.console.print(
                    f"[green]Loaded schema with {len(self.context.tables)} table(s).[/green]"
                )
            except json.JSONDecodeError as e:
                self.console.print(f"[red]Error parsing JSON:[/red] {e}")
            except Exception as e:
                self.console.print(f"[red]Error loading schema:[/red] {e}")
        else:
            self.console.print(f"[yellow]File not found:[/yellow] {schema_path}")

    async def _handle_analyze(self, args: str) -> None:
        """Handle /analyze command."""
        if not self.context.tables:
            self.console.print(
                "[yellow]No tables loaded.[/yellow] Use /schema first."
            )
            return

        if not self.llm_client:
            self.console.print("[red]LLM client not available.[/red]")
            return

        if args:
            # Analyze specific table
            table_name = args.strip().lower()
            matching_tables = [
                t for t in self.context.tables
                if t.get("name", "").lower() == table_name
            ]
            if not matching_tables:
                self.console.print(
                    f"[yellow]Table not found:[/yellow] {args}\n"
                    f"Available tables: {', '.join(t.get('name', '') for t in self.context.tables[:10])}"
                )
                return

            tables_to_analyze = matching_tables
        else:
            tables_to_analyze = self.context.tables

        self.console.print(
            f"\n[bold]Analyzing {len(tables_to_analyze)} table(s)...[/bold]\n"
        )

        # Build analysis prompt
        tables_context = format_table_context(tables_to_analyze)
        prompt = RELATIONSHIP_INFERENCE_PROMPT.format(
            requirements=self.context.requirements or "General data analysis",
            tables_context=tables_context,
            analysis_context="Initial analysis - no prior context",
        )

        # Stream the response
        await self._stream_response(prompt, "Analyzing tables")

        self.context.current_step = "analysis_complete"

    async def _handle_design(self, args: str) -> None:
        """Handle /design command."""
        if not self.context.tables and not self.context.requirements:
            self.console.print(
                "[yellow]No context available.[/yellow]\n"
                "Please load a schema with /schema or describe your requirements."
            )
            return

        if not self.llm_client:
            self.console.print("[red]LLM client not available.[/red]")
            return

        # Determine design strategy
        strategy = args.strip().lower() if args else "star"
        if strategy not in ("star", "3nf", "vault"):
            self.console.print(
                "[yellow]Available strategies:[/yellow] star, 3nf, vault\n"
                f"Using default: star"
            )
            strategy = "star"

        self.console.print(f"\n[bold]Designing {strategy.upper()} schema...[/bold]\n")

        # Build design prompt
        tables_context = format_table_context(self.context.tables)
        profile_context = format_profile_context(self.context.profiles)
        analysis_context = format_analysis_context(
            fds=self.context.analysis.get("functional_dependencies"),
            keys=self.context.analysis.get("candidate_keys"),
            relationships=self.context.analysis.get("relationships"),
        )

        prompt = STAR_SCHEMA_DESIGN_PROMPT.format(
            requirements=self.context.requirements or "Design a dimensional model",
            tables_context=tables_context,
            profile_context=profile_context,
            analysis_context=analysis_context,
        )

        # Stream the response
        await self._stream_response(prompt, f"Designing {strategy} schema")

        self.context.current_step = "design_complete"

    async def _handle_generate(self, args: str) -> None:
        """Handle /generate command."""
        if not self.context.design:
            self.console.print(
                "[yellow]No design available.[/yellow]\n"
                "Use /design first to create a data model design."
            )
            return

        output_type = args.strip().lower() if args else "ddl"
        if output_type not in ("ddl", "dbt", "docs"):
            self.console.print(
                "[yellow]Available output types:[/yellow] ddl, dbt, docs\n"
                f"Using default: ddl"
            )
            output_type = "ddl"

        self.console.print(
            f"\n[bold]Generating {output_type.upper()} from design...[/bold]\n"
        )

        # This would typically call the appropriate generation prompt
        # For now, show a placeholder
        self.console.print(
            f"[dim]Generation of {output_type} would occur here.[/dim]\n"
            "[dim]This feature requires the full generation pipeline.[/dim]"
        )

        self.context.current_step = "generation_complete"

    async def _handle_validate(self, args: str) -> None:
        """Handle /validate command."""
        if not self.context.design:
            self.console.print(
                "[yellow]No design to validate.[/yellow]\n"
                "Use /design first to create a data model design."
            )
            return

        if not self.llm_client:
            self.console.print("[red]LLM client not available.[/red]")
            return

        self.console.print("\n[bold]Validating design...[/bold]\n")

        prompt = DESIGN_REVIEW_PROMPT.format(
            requirements=self.context.requirements or "General data modeling",
            design_json=json.dumps(self.context.design, indent=2),
        )

        await self._stream_response(prompt, "Validating design")

        self.context.current_step = "validation_complete"

    async def _handle_save(self, args: str) -> None:
        """Handle /save command."""
        filename = args.strip() if args else f"chat_session_{self.session_id}.json"

        if not filename.endswith(".json"):
            filename += ".json"

        save_path = self.workspace_path / filename

        session_data = {
            "session_id": self.session_id,
            "timestamp": datetime.now().isoformat(),
            "workspace_path": str(self.workspace_path),
            "conversation_history": self.conversation_history,
            "context": self.context.to_dict(),
        }

        try:
            with open(save_path, "w") as f:
                json.dump(session_data, f, indent=2, default=str)
            self.console.print(f"[green]Session saved to:[/green] {save_path}")
        except Exception as e:
            self.console.print(f"[red]Error saving session:[/red] {e}")

    async def _handle_load(self, args: str) -> None:
        """Handle /load command."""
        if not args:
            # List available sessions
            sessions = list(self.workspace_path.glob("chat_session_*.json"))
            if sessions:
                self.console.print("[bold]Available sessions:[/bold]")
                for session_file in sorted(sessions, reverse=True)[:5]:
                    self.console.print(f"  - {session_file.name}")
                self.console.print("\nUsage: /load [filename]")
            else:
                self.console.print("[yellow]No saved sessions found.[/yellow]")
            return

        filename = args.strip()
        if not filename.endswith(".json"):
            filename += ".json"

        load_path = self.workspace_path / filename
        if not load_path.exists():
            self.console.print(f"[yellow]Session file not found:[/yellow] {load_path}")
            return

        try:
            with open(load_path, "r") as f:
                session_data = json.load(f)

            self.session_id = session_data.get("session_id", self.session_id)
            self.conversation_history = session_data.get("conversation_history", [])
            self.context = ChatContext.from_dict(session_data.get("context", {}))

            self.console.print(
                f"[green]Session loaded:[/green] {len(self.conversation_history)} messages restored"
            )
        except Exception as e:
            self.console.print(f"[red]Error loading session:[/red] {e}")

    async def _handle_message(self, user_input: str) -> None:
        """
        Handle a regular chat message (not a command).

        Args:
            user_input: The user's message
        """
        if not self.llm_client:
            self.console.print(
                "[yellow]LLM client not available.[/yellow]\n"
                "API-based responses are disabled. Use commands like /help for guidance."
            )
            return

        # Add user message to history
        self.conversation_history.append({"role": "user", "content": user_input})

        # Build context for the prompt
        context_parts = []

        if self.context.requirements:
            context_parts.append(f"User Requirements: {self.context.requirements}")

        if self.context.tables:
            context_parts.append(
                f"Loaded Tables ({len(self.context.tables)}): "
                + ", ".join(t.get("name", "unknown") for t in self.context.tables[:5])
            )

        if self.context.design:
            context_parts.append(
                f"Current Design: {self.context.design.get('strategy', 'unknown')} schema"
            )

        context_parts.append(f"Current Step: {self.context.current_step}")

        context_str = "\n".join(context_parts) if context_parts else "No context loaded."

        # Build the full prompt
        prompt = f"""## Current Context
{context_str}

## Conversation History
{self._format_history()}

## User Message
{user_input}

Please respond helpfully. If the user is asking about data modeling, provide specific guidance.
If they seem to be describing requirements, acknowledge and suggest next steps.
If they need to perform an action, suggest the appropriate command."""

        # Stream the response
        response = await self._stream_response(prompt, "Thinking")

        # Add assistant response to history
        if response:
            self.conversation_history.append({"role": "assistant", "content": response})

            # Check if this looks like requirements
            if self._looks_like_requirements(user_input):
                self.context.requirements = user_input
                self.context.current_step = "requirements_captured"

    def _format_history(self) -> str:
        """Format conversation history for the prompt."""
        if not self.conversation_history:
            return "(No prior conversation)"

        # Only include last 6 messages to avoid token limits
        recent = self.conversation_history[-6:]
        formatted = []

        for msg in recent:
            role = msg["role"].capitalize()
            content = msg["content"][:500]  # Truncate long messages
            formatted.append(f"{role}: {content}")

        return "\n".join(formatted)

    def _looks_like_requirements(self, text: str) -> bool:
        """Check if text looks like requirements."""
        requirement_patterns = [
            r"\bwant\b",
            r"\bneed\b",
            r"\bbuild\b",
            r"\bcreate\b",
            r"\banalyze\b",
            r"\bmodel\b",
            r"\btrack\b",
            r"\breport\b",
            r"\bdashboard\b",
            r"\bmetric\b",
        ]

        text_lower = text.lower()
        matches = sum(1 for pattern in requirement_patterns if re.search(pattern, text_lower))
        return matches >= 2

    async def _stream_response(
        self, prompt: str, status_message: str = "Processing"
    ) -> Optional[str]:
        """
        Stream a response from the LLM with real-time display.

        Args:
            prompt: The prompt to send
            status_message: Message to show while processing

        Returns:
            The complete response text, or None on error
        """
        if not self.llm_client:
            return None

        full_response = ""

        try:
            # Show typing indicator while waiting for first chunk
            with self.console.status(f"[bold blue]{status_message}...[/bold blue]"):
                # Get the first chunk to confirm connection
                stream = self.llm_client.stream(prompt, system=self.system_prompt)

                # Start building response
                first_chunk = True
                async for chunk in stream:
                    if first_chunk:
                        first_chunk = False
                        self.console.print()  # Start new line for response

                    full_response += chunk
                    # Print chunks as they arrive
                    self.console.print(chunk, end="", markup=False)

            # Print final newline
            self.console.print("\n")

            return full_response

        except Exception as e:
            self.console.print(f"\n[red]Error:[/red] {e}")
            self._print_error_help(e)
            return None

    def _print_error_help(self, error: Exception) -> None:
        """Print helpful error messages."""
        error_str = str(error).lower()

        if "api" in error_str or "key" in error_str or "auth" in error_str:
            self.console.print(
                "[yellow]Tip:[/yellow] Check your ANTHROPIC_API_KEY environment variable."
            )
        elif "rate" in error_str or "limit" in error_str:
            self.console.print(
                "[yellow]Tip:[/yellow] Rate limit reached. Wait a moment and try again."
            )
        elif "timeout" in error_str:
            self.console.print(
                "[yellow]Tip:[/yellow] Request timed out. Try a simpler request."
            )
        else:
            self.console.print(
                "[yellow]Tip:[/yellow] Try /help for available commands."
            )

    async def run(self) -> None:
        """Run the interactive chat session."""
        self._print_welcome()

        # Initialize LLM client
        if not self._init_llm_client():
            self.console.print(
                "\n[yellow]Running in limited mode without LLM.[/yellow]\n"
                "You can still use commands like /help, /schema, /save, /load.\n"
            )

        # Main chat loop
        while True:
            try:
                user_input = Prompt.ask("\n[bold green]You[/bold green]")

                if not user_input.strip():
                    continue

                if user_input.startswith("/"):
                    should_continue = await self._handle_command(user_input)
                    if not should_continue:
                        break
                else:
                    await self._handle_message(user_input)

            except KeyboardInterrupt:
                self.console.print("\n\n[yellow]Interrupted.[/yellow]")
                if Confirm.ask("Exit chat?"):
                    break
            except EOFError:
                break


def start_chat(workspace_path: Optional[str] = None) -> None:
    """
    Entry point for the chat command.

    This function starts an interactive chat session. It can be called
    from the CLI or programmatically.

    Args:
        workspace_path: Optional path to a workspace directory.
            If not provided, uses the current working directory.

    Example:
        >>> start_chat()  # Start chat in current directory
        >>> start_chat("/path/to/workspace")  # Start chat in specific workspace
    """
    session = ChatSession(workspace_path=workspace_path)
    asyncio.run(session.run())


if __name__ == "__main__":
    start_chat()
