"""
Base classes and interfaces for DataForge agents.

This module defines the core abstractions for all specialized agents
in the DataForge platform.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, AsyncIterator, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class AgentType(str, Enum):
    """Types of agents in the DataForge system."""

    MODELING = "modeling"
    PIPELINE = "pipeline"
    INFRASTRUCTURE = "infrastructure"
    ORCHESTRATOR = "orchestrator"


class TaskStatus(str, Enum):
    """Status of an agent task."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentCapability(BaseModel):
    """Describes what an agent can do."""

    name: str
    description: str
    required_mcps: List[str] = Field(default_factory=list)
    output_types: List[str] = Field(default_factory=list)  # dbt, airflow, terraform, etc.
    parameters: Dict[str, Any] = Field(default_factory=dict)


class AgentEvent(BaseModel):
    """Event emitted during agent execution for streaming updates."""

    event_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=datetime.now)
    type: str  # step_start, step_complete, thinking, tool_use, error, warning
    step_name: str
    message: str
    data: Optional[Dict[str, Any]] = None
    level: str = "info"  # debug, info, warning, error


class AgentState(BaseModel):
    """Shared state across agent execution."""

    # Identity
    conversation_id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    agent_type: AgentType

    # Workspace
    workspace_path: str
    workspace_id: Optional[str] = None

    # Request
    requirements: str
    parameters: Dict[str, Any] = Field(default_factory=dict)

    # Conversation
    conversation_history: List[Dict[str, str]] = Field(default_factory=list)

    # Discovery & Context
    discovered_context: Dict[str, Any] = Field(default_factory=dict)
    data_sources: List[Dict[str, Any]] = Field(default_factory=list)
    schemas: Dict[str, Any] = Field(default_factory=dict)
    profiles: Dict[str, Any] = Field(default_factory=dict)

    # Generated Artifacts
    generated_artifacts: Dict[str, str] = Field(default_factory=dict)
    artifact_metadata: Dict[str, Any] = Field(default_factory=dict)

    # Execution
    current_step: str = "initialized"
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0  # 0.0 to 1.0

    # Errors & Issues
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    def add_error(self, error: str) -> None:
        """Add an error message."""
        self.errors.append(error)
        self.updated_at = datetime.now()

    def add_warning(self, warning: str) -> None:
        """Add a warning message."""
        self.warnings.append(warning)
        self.updated_at = datetime.now()

    def update_progress(self, step: str, progress: float) -> None:
        """Update execution progress."""
        self.current_step = step
        self.progress = min(1.0, max(0.0, progress))
        self.updated_at = datetime.now()


class BaseDataEngineeringAgent(ABC):
    """
    Base class for all specialized agents in DataForge.

    This abstract class defines the contract that all agents must implement.
    Each agent is responsible for a specific domain (modeling, pipelines, infrastructure)
    and can execute complex multi-step workflows.
    """

    def __init__(
        self,
        mcp_registry: Any,  # Type will be 'MCPRegistry' when implemented
        workspace_manager: Any,  # Type will be 'WorkspaceManager' when implemented
        llm_client: Any,  # Type will be 'LLMClient' when implemented
    ):
        """
        Initialize the agent with required dependencies.

        Args:
            mcp_registry: Registry for MCP server discovery and routing
            workspace_manager: Manager for file system and git operations
            llm_client: Client for LLM API calls
        """
        self.mcp_registry = mcp_registry
        self.workspace = workspace_manager
        self.llm = llm_client
        self.capabilities = self._define_capabilities()
        self.agent_type = self._get_agent_type()

    @abstractmethod
    def _get_agent_type(self) -> AgentType:
        """Return the type of this agent."""
        pass

    @abstractmethod
    def _define_capabilities(self) -> List[AgentCapability]:
        """
        Define what this agent can do.

        Returns:
            List of capabilities this agent provides
        """
        pass

    @abstractmethod
    async def can_handle(self, task: Dict[str, Any]) -> bool:
        """
        Determine if this agent can handle the given task.

        Args:
            task: Task description with requirements and parameters

        Returns:
            True if this agent can handle the task, False otherwise
        """
        pass

    @abstractmethod
    async def execute(self, state: AgentState) -> AgentState:
        """
        Execute the agent's workflow.

        This is the main entry point for agent execution. The agent should:
        1. Discover context from workspace and MCPs
        2. Plan the work based on requirements
        3. Generate code artifacts
        4. Validate the generated artifacts
        5. Document the artifacts
        6. Update the state with results

        Args:
            state: Current agent state

        Returns:
            Updated agent state with results
        """
        pass

    async def execute_with_streaming(
        self,
        state: AgentState
    ) -> AsyncIterator[AgentEvent]:
        """
        Execute the agent's workflow with streaming updates.

        This method wraps the execute() method and emits events
        for real-time progress tracking.

        Args:
            state: Current agent state

        Yields:
            AgentEvent objects for each significant step
        """
        try:
            yield AgentEvent(
                type="step_start",
                step_name="execution",
                message=f"Starting {self.agent_type.value} agent execution",
            )

            # Execute the agent
            result_state = await self.execute(state)

            yield AgentEvent(
                type="step_complete",
                step_name="execution",
                message=f"{self.agent_type.value} agent completed successfully",
                data={"status": result_state.status.value},
            )

        except Exception as e:
            yield AgentEvent(
                type="error",
                step_name="execution",
                message=f"Error during execution: {str(e)}",
                level="error",
            )
            raise

    async def discover_context(self, state: AgentState) -> Dict[str, Any]:
        """
        Discover relevant context from workspace and MCPs.

        This method should:
        - Query available MCP servers for data sources
        - Read existing workspace files
        - Gather metadata about available resources

        Args:
            state: Current agent state

        Returns:
            Dictionary of discovered context
        """
        context = {
            "available_mcps": await self.mcp_registry.get_capabilities(),
            "workspace_files": self.workspace.list_files() if self.workspace else [],
        }
        return context

    async def generate_code(self, spec: Dict[str, Any]) -> Dict[str, str]:
        """
        Generate code artifacts based on specification.

        Args:
            spec: Specification for code generation

        Returns:
            Dictionary mapping file paths to file contents
        """
        # To be implemented by specialized agents
        return {}

    async def validate(self, artifacts: Dict[str, str]) -> List[str]:
        """
        Validate generated artifacts.

        Args:
            artifacts: Generated code artifacts

        Returns:
            List of validation errors (empty if valid)
        """
        # To be implemented by specialized agents
        return []

    async def document(self, artifacts: Dict[str, str]) -> str:
        """
        Generate documentation for artifacts.

        Args:
            artifacts: Generated code artifacts

        Returns:
            Documentation markdown
        """
        # To be implemented by specialized agents
        return "# Documentation\n\nNo documentation generated."

    def get_capabilities(self) -> List[AgentCapability]:
        """Get list of agent capabilities."""
        return self.capabilities

    def get_agent_info(self) -> Dict[str, Any]:
        """Get agent information."""
        return {
            "type": self.agent_type.value,
            "capabilities": [cap.dict() for cap in self.capabilities],
        }
