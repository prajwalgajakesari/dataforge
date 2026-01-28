"""
MCP Client for DataForge.

Universal client for interacting with MCP (Model Context Protocol) servers.
Handles protocol specifics, retries, error handling, and connection management.
"""

import asyncio
from typing import Any, AsyncIterator, Dict, Optional

from pydantic import BaseModel

from core.mcp.registry import MCPServerConfig


class MCPRequest(BaseModel):
    """Request to an MCP server."""

    operation: str
    params: Dict[str, Any]
    timeout: Optional[int] = None


class MCPResponse(BaseModel):
    """Response from an MCP server."""

    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = {}


class MCPClient:
    """
    Universal client for interacting with MCP servers.

    This client:
    - Establishes and maintains connections to MCP servers
    - Handles protocol-specific communication
    - Implements retry logic with exponential backoff
    - Supports streaming responses
    - Manages timeouts and circuit breaking
    """

    def __init__(self, config: MCPServerConfig):
        """
        Initialize the MCP client.

        Args:
            config: Server configuration
        """
        self.config = config
        self.connection: Optional[Any] = None
        self._connected = False
        self._connection_lock = asyncio.Lock()
        self._retry_count = 0
        self._circuit_open = False

    async def connect(self) -> bool:
        """
        Establish connection to MCP server.

        Returns:
            True if connection successful

        Raises:
            ConnectionError: If connection fails
        """
        async with self._connection_lock:
            if self._connected:
                return True

            try:
                # Connection logic depends on server type
                if self.config.type == "database":
                    await self._connect_database()
                elif self.config.type == "api":
                    await self._connect_api()
                elif self.config.type == "tool":
                    await self._connect_tool()
                elif self.config.type == "file":
                    await self._connect_file_system()
                else:
                    raise ValueError(f"Unknown server type: {self.config.type}")

                self._connected = True
                self._retry_count = 0
                return True

            except Exception as e:
                self._retry_count += 1
                max_retries = self.config.retry_policy.get("max_retries", 3)

                if self._retry_count >= max_retries:
                    self._circuit_open = True
                    raise ConnectionError(
                        f"Failed to connect to {self.config.name} after {max_retries} attempts: {e}"
                    )
                raise

    async def _connect_database(self) -> None:
        """Connect to a database MCP server."""
        # TODO: Implement database-specific connection
        # This would use sqlalchemy or database-specific drivers
        # based on connection_config
        pass

    async def _connect_api(self) -> None:
        """Connect to an API MCP server."""
        # TODO: Implement API connection (HTTP/REST)
        # This would set up httpx client with appropriate auth
        pass

    async def _connect_tool(self) -> None:
        """Connect to a tool MCP server."""
        # TODO: Implement tool connection
        # This might be local process communication
        pass

    async def _connect_file_system(self) -> None:
        """Connect to a file system MCP server."""
        # TODO: Implement file system connection
        # This might be S3, GCS, Azure Blob, or local filesystem
        pass

    async def execute(
        self,
        operation: str,
        params: Dict[str, Any]
    ) -> MCPResponse:
        """
        Execute an operation on the MCP server.

        This method:
        1. Ensures connection is established
        2. Validates the operation
        3. Executes with retry logic
        4. Returns structured response

        Args:
            operation: Operation to execute (e.g., "query", "execute", "read")
            params: Operation parameters

        Returns:
            MCPResponse with results

        Raises:
            ConnectionError: If not connected and cannot connect
            TimeoutError: If operation times out
            Exception: For other errors
        """
        if self._circuit_open:
            return MCPResponse(
                success=False,
                error="Circuit breaker is open, server unavailable"
            )

        if not self._connected:
            await self.connect()

        request = MCPRequest(
            operation=operation,
            params=params,
            timeout=self.config.timeout
        )

        try:
            # Execute with retry logic
            response = await self._execute_with_retry(request)
            return response

        except asyncio.TimeoutError:
            return MCPResponse(
                success=False,
                error=f"Operation timed out after {self.config.timeout}s"
            )
        except Exception as e:
            return MCPResponse(
                success=False,
                error=str(e)
            )

    async def _execute_with_retry(self, request: MCPRequest) -> MCPResponse:
        """
        Execute request with exponential backoff retry.

        Args:
            request: MCP request to execute

        Returns:
            MCPResponse

        Raises:
            Exception: If all retries exhausted
        """
        max_retries = self.config.retry_policy.get("max_retries", 3)
        backoff_factor = self.config.retry_policy.get("backoff_factor", 2)

        last_error = None

        for attempt in range(max_retries):
            try:
                response = await self._execute_operation(request)
                return response

            except Exception as e:
                last_error = e

                if attempt < max_retries - 1:
                    # Calculate backoff delay
                    delay = backoff_factor ** attempt
                    await asyncio.sleep(delay)
                    continue
                else:
                    # Last attempt failed
                    break

        # All retries exhausted
        return MCPResponse(
            success=False,
            error=f"Operation failed after {max_retries} attempts: {last_error}"
        )

    async def _execute_operation(self, request: MCPRequest) -> MCPResponse:
        """
        Execute the actual operation against the MCP server.

        Args:
            request: MCP request

        Returns:
            MCPResponse

        Raises:
            Exception: If execution fails
        """
        # Operation execution depends on server type and operation
        operation = request.operation
        params = request.params

        if self.config.type == "database":
            return await self._execute_database_operation(operation, params)
        elif self.config.type == "api":
            return await self._execute_api_operation(operation, params)
        elif self.config.type == "tool":
            return await self._execute_tool_operation(operation, params)
        elif self.config.type == "file":
            return await self._execute_file_operation(operation, params)
        else:
            return MCPResponse(
                success=False,
                error=f"Unknown operation type for {self.config.type}"
            )

    async def _execute_database_operation(
        self,
        operation: str,
        params: Dict[str, Any]
    ) -> MCPResponse:
        """Execute a database operation."""
        # TODO: Implement database operations
        # - query: Execute SELECT query
        # - execute: Execute INSERT/UPDATE/DELETE
        # - schema: Get schema information
        return MCPResponse(success=True, data={"rows": [], "columns": []})

    async def _execute_api_operation(
        self,
        operation: str,
        params: Dict[str, Any]
    ) -> MCPResponse:
        """Execute an API operation."""
        # TODO: Implement API operations
        # - get: HTTP GET request
        # - post: HTTP POST request
        # - put: HTTP PUT request
        # - delete: HTTP DELETE request
        return MCPResponse(success=True, data={})

    async def _execute_tool_operation(
        self,
        operation: str,
        params: Dict[str, Any]
    ) -> MCPResponse:
        """Execute a tool operation."""
        # TODO: Implement tool operations
        # Specific to each tool (dbt, airflow, git, etc.)
        return MCPResponse(success=True, data={})

    async def _execute_file_operation(
        self,
        operation: str,
        params: Dict[str, Any]
    ) -> MCPResponse:
        """Execute a file system operation."""
        # TODO: Implement file operations
        # - read: Read file
        # - write: Write file
        # - list: List files
        # - delete: Delete file
        return MCPResponse(success=True, data={})

    async def stream(
        self,
        operation: str,
        params: Dict[str, Any]
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream results from MCP server.

        This is useful for large result sets that should be processed
        incrementally rather than loaded entirely into memory.

        Args:
            operation: Operation to execute
            params: Operation parameters

        Yields:
            Chunks of data from the server

        Raises:
            ConnectionError: If not connected
            Exception: For other errors
        """
        if not self._connected:
            await self.connect()

        # TODO: Implement streaming based on server capabilities
        # For now, yield empty results
        yield {"data": []}

    async def disconnect(self) -> None:
        """Close connection to MCP server."""
        async with self._connection_lock:
            if not self._connected:
                return

            try:
                # Close connection based on type
                if self.connection:
                    # TODO: Implement proper cleanup based on connection type
                    pass

                self._connected = False
                self.connection = None

            except Exception as e:
                # Log error but don't raise
                print(f"Error disconnecting from {self.config.name}: {e}")

    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self._connected

    def reset_circuit_breaker(self) -> None:
        """Reset the circuit breaker to allow reconnection attempts."""
        self._circuit_open = False
        self._retry_count = 0

    async def health_check(self) -> bool:
        """
        Perform health check on the MCP server.

        Returns:
            True if server is healthy
        """
        try:
            if not self._connected:
                await self.connect()

            # Execute a lightweight health check operation
            response = await self.execute("health", {})
            return response.success

        except Exception:
            return False
