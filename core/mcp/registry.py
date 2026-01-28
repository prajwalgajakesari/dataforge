"""
MCP Registry for DataForge.

This module provides the central registry for all MCP (Model Context Protocol) servers.
It handles server discovery, health monitoring, capability mapping, and request routing.
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field


class MCPServerConfig(BaseModel):
    """Configuration for an MCP server."""

    name: str
    type: str  # database, api, file, tool
    version: str = "1.0.0"
    capabilities: List[str] = Field(default_factory=list)
    connection_config: Dict[str, Any] = Field(default_factory=dict)
    health_check_interval: int = 60  # seconds
    timeout: int = 30
    retry_policy: Dict[str, int] = Field(
        default_factory=lambda: {"max_retries": 3, "backoff_factor": 2}
    )
    enabled: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MCPCapability(BaseModel):
    """What an MCP server can do."""

    capability_type: str  # query, execute, read, write, transform
    operations: List[str] = Field(default_factory=list)
    schema_support: bool = False
    streaming_support: bool = False
    batch_support: bool = False


class MCPHealthStatus(BaseModel):
    """Health status of an MCP server."""

    server_name: str
    healthy: bool
    last_check: datetime
    latency_ms: Optional[float] = None
    error: Optional[str] = None


class MCPRegistry:
    """
    Central registry for all MCP servers.

    This class:
    - Discovers MCP servers from configuration files
    - Manages server lifecycle (connect, disconnect, health checks)
    - Routes requests to appropriate servers
    - Provides capability discovery
    - Monitors server health
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the MCP registry.

        Args:
            config_path: Path to MCP servers configuration file
        """
        self.config_path = config_path or str(
            Path.home() / ".dataforge" / "mcp-servers.yml"
        )
        self.servers: Dict[str, MCPServerConfig] = {}
        self.clients: Dict[str, Any] = {}  # Will be MCPClient instances
        self.health_status: Dict[str, MCPHealthStatus] = {}
        self._health_check_task: Optional[asyncio.Task] = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the registry by discovering and connecting to servers."""
        if self._initialized:
            return

        # Load configuration
        await self._load_config()

        # Discover servers
        await self.discover_servers()

        # Connect to enabled servers
        await self._connect_all()

        # Start health monitoring
        self._health_check_task = asyncio.create_task(self._monitor_health())

        self._initialized = True

    async def _load_config(self) -> None:
        """Load MCP server configuration from file."""
        config_path = Path(self.config_path)

        if not config_path.exists():
            # Create default configuration
            await self._create_default_config(config_path)

        try:
            with open(config_path, "r") as f:
                config_data = yaml.safe_load(f)

            servers_config = config_data.get("servers", [])
            for server_data in servers_config:
                config = MCPServerConfig(**server_data)
                self.servers[config.name] = config

        except Exception as e:
            print(f"Error loading MCP config: {e}")
            # Continue with empty config

    async def _create_default_config(self, config_path: Path) -> None:
        """
        Create a default MCP server configuration file.

        Args:
            config_path: Path where config should be created
        """
        config_path.parent.mkdir(parents=True, exist_ok=True)

        default_config = {
            "version": "1.0",
            "servers": [
                {
                    "name": "postgres",
                    "type": "database",
                    "version": "1.0.0",
                    "capabilities": ["query", "execute", "schema"],
                    "connection_config": {
                        "host": "${POSTGRES_HOST}",
                        "port": "${POSTGRES_PORT}",
                        "database": "${POSTGRES_DATABASE}",
                        "user": "${POSTGRES_USER}",
                        "password": "${POSTGRES_PASSWORD}",
                    },
                    "enabled": False,
                },
                {
                    "name": "mysql",
                    "type": "database",
                    "version": "1.0.0",
                    "capabilities": ["query", "execute", "schema"],
                    "connection_config": {
                        "host": "${MYSQL_HOST}",
                        "port": "${MYSQL_PORT}",
                        "database": "${MYSQL_DATABASE}",
                        "user": "${MYSQL_USER}",
                        "password": "${MYSQL_PASSWORD}",
                    },
                    "enabled": False,
                },
                {
                    "name": "snowflake",
                    "type": "database",
                    "version": "1.0.0",
                    "capabilities": ["query", "execute", "schema"],
                    "connection_config": {
                        "account": "${SNOWFLAKE_ACCOUNT}",
                        "user": "${SNOWFLAKE_USER}",
                        "password": "${SNOWFLAKE_PASSWORD}",
                        "warehouse": "${SNOWFLAKE_WAREHOUSE}",
                        "database": "${SNOWFLAKE_DATABASE}",
                        "schema": "${SNOWFLAKE_SCHEMA}",
                    },
                    "enabled": False,
                },
            ],
        }

        with open(config_path, "w") as f:
            yaml.dump(default_config, f, default_flow_style=False)

    async def discover_servers(self) -> List[str]:
        """
        Auto-discover MCP servers from multiple sources:
        1. User config (~/.dataforge/mcp-servers.yml)
        2. Project config (.dataforge/mcp-servers.yml)
        3. Environment variables
        4. System-wide registry

        Returns:
            List of discovered server names
        """
        discovered = list(self.servers.keys())

        # Check for project-local config
        project_config = Path(".dataforge") / "mcp-servers.yml"
        if project_config.exists():
            try:
                with open(project_config, "r") as f:
                    config_data = yaml.safe_load(f)
                    for server_data in config_data.get("servers", []):
                        config = MCPServerConfig(**server_data)
                        if config.name not in self.servers:
                            self.servers[config.name] = config
                            discovered.append(config.name)
            except Exception as e:
                print(f"Error loading project MCP config: {e}")

        return discovered

    async def register_server(self, config: MCPServerConfig) -> bool:
        """
        Register a new MCP server.

        Args:
            config: Server configuration

        Returns:
            True if registration successful
        """
        try:
            self.servers[config.name] = config
            # TODO: Create and connect client
            return True
        except Exception as e:
            print(f"Error registering server {config.name}: {e}")
            return False

    async def get_capabilities(self) -> Dict[str, List[str]]:
        """
        Get map of available capabilities.

        Returns:
            Dictionary mapping capability types to available servers:
            {
                "data_sources": ["postgres", "mysql", "snowflake"],
                "tools": ["dbt", "git"],
                "platforms": ["aws", "gcp"]
            }
        """
        capabilities = {
            "data_sources": [],
            "tools": [],
            "platforms": [],
            "apis": [],
        }

        for name, config in self.servers.items():
            if not config.enabled:
                continue

            if config.type == "database":
                capabilities["data_sources"].append(name)
            elif config.type == "tool":
                capabilities["tools"].append(name)
            elif config.type == "platform":
                capabilities["platforms"].append(name)
            elif config.type == "api":
                capabilities["apis"].append(name)

        return capabilities

    async def query_source(
        self,
        source_name: str,
        query: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a query against a data source MCP.

        Args:
            source_name: Name of the data source
            query: SQL query to execute
            params: Optional query parameters

        Returns:
            Query results

        Raises:
            ValueError: If source not found or not available
            Exception: If query execution fails
        """
        if source_name not in self.servers:
            raise ValueError(f"Data source '{source_name}' not found")

        config = self.servers[source_name]
        if not config.enabled:
            raise ValueError(f"Data source '{source_name}' is not enabled")

        # TODO: Use MCP client to execute query
        # client = self.clients.get(source_name)
        # return await client.execute("query", {"sql": query, "params": params})

        # Placeholder return
        return {"rows": [], "columns": []}

    async def execute_tool(
        self,
        tool_name: str,
        command: str,
        args: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a command via tool MCP.

        Args:
            tool_name: Name of the tool
            command: Command to execute
            args: Command arguments

        Returns:
            Command results
        """
        if tool_name not in self.servers:
            raise ValueError(f"Tool '{tool_name}' not found")

        config = self.servers[tool_name]
        if not config.enabled:
            raise ValueError(f"Tool '{tool_name}' is not enabled")

        # TODO: Use MCP client to execute tool
        return {"status": "success"}

    async def health_check(self, server_name: str) -> bool:
        """
        Check if an MCP server is healthy.

        Args:
            server_name: Name of the server to check

        Returns:
            True if server is healthy
        """
        if server_name not in self.servers:
            return False

        try:
            # TODO: Implement actual health check via MCP client
            # For now, just check if server is configured and enabled
            config = self.servers[server_name]
            is_healthy = config.enabled

            self.health_status[server_name] = MCPHealthStatus(
                server_name=server_name,
                healthy=is_healthy,
                last_check=datetime.now(),
            )

            return is_healthy

        except Exception as e:
            self.health_status[server_name] = MCPHealthStatus(
                server_name=server_name,
                healthy=False,
                last_check=datetime.now(),
                error=str(e),
            )
            return False

    async def _monitor_health(self) -> None:
        """Background task to monitor all server health."""
        while True:
            try:
                for server_name in self.servers:
                    await self.health_check(server_name)
                await asyncio.sleep(60)  # Check every minute
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in health monitoring: {e}")
                await asyncio.sleep(60)

    async def _connect_all(self) -> None:
        """Connect to all enabled MCP servers."""
        for name, config in self.servers.items():
            if config.enabled:
                try:
                    # TODO: Create and connect MCP client
                    pass
                except Exception as e:
                    print(f"Failed to connect to {name}: {e}")

    async def shutdown(self) -> None:
        """Shutdown the registry and disconnect all servers."""
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass

        # Disconnect all clients
        # TODO: Implement when MCPClient is ready
        for client in self.clients.values():
            try:
                # await client.disconnect()
                pass
            except Exception as e:
                print(f"Error disconnecting client: {e}")

        self._initialized = False

    def get_server_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Get status of all registered servers.

        Returns:
            Dictionary mapping server names to their status
        """
        status = {}
        for name, config in self.servers.items():
            health = self.health_status.get(name)
            status[name] = {
                "enabled": config.enabled,
                "type": config.type,
                "capabilities": config.capabilities,
                "healthy": health.healthy if health else None,
                "last_check": health.last_check if health else None,
            }
        return status
