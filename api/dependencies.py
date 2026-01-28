"""
FastAPI dependencies for dependency injection.

This module provides centralized dependency management for the DataForge API.
Dependencies are initialized during app lifespan and injected into route handlers.

Thread Safety:
    Global instances are initialized once during startup and are read-only thereafter.
    The session store implementations must be thread-safe for concurrent access.

Usage:
    from api.dependencies import get_mcp_registry, get_session_store, get_session

    @router.get("/example")
    async def example_endpoint(
        registry: MCPRegistry = Depends(get_mcp_registry),
        store: SessionStore = Depends(get_session_store)
    ):
        ...
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock
from typing import Any, Dict, Optional, Protocol, runtime_checkable

from fastapi import Depends, HTTPException, status

from core.mcp.registry import MCPRegistry


# -----------------------------------------------------------------------------
# Session Data Model
# -----------------------------------------------------------------------------

@dataclass
class SessionData:
    """
    Represents a modeling session with its associated state.

    Attributes:
        session_id: Unique identifier for the session.
        project_name: Name of the modeling project.
        created_at: Timestamp when session was created.
        updated_at: Timestamp of last update.
        workflow: The ModelingWorkflow instance (if initialized).
        state: Current workflow state dictionary.
        metadata: Additional session metadata.
    """

    session_id: str
    project_name: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    workflow: Optional[Any] = None  # ModelingWorkflow instance
    state: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


# -----------------------------------------------------------------------------
# Session Store Protocol
# -----------------------------------------------------------------------------

@runtime_checkable
class SessionStore(Protocol):
    """
    Protocol for session storage implementations.

    Implementations must be thread-safe for concurrent access.
    All methods are async to support both sync and async backends.
    """

    async def get(self, session_id: str) -> Optional[SessionData]:
        """
        Retrieve a session by ID.

        Args:
            session_id: The unique session identifier.

        Returns:
            SessionData if found, None otherwise.
        """
        ...

    async def set(self, session_id: str, data: SessionData) -> None:
        """
        Store or update a session.

        Args:
            session_id: The unique session identifier.
            data: The session data to store.
        """
        ...

    async def delete(self, session_id: str) -> bool:
        """
        Delete a session.

        Args:
            session_id: The unique session identifier.

        Returns:
            True if session was deleted, False if not found.
        """
        ...

    async def exists(self, session_id: str) -> bool:
        """
        Check if a session exists.

        Args:
            session_id: The unique session identifier.

        Returns:
            True if session exists, False otherwise.
        """
        ...

    async def list_sessions(self) -> list[str]:
        """
        List all session IDs.

        Returns:
            List of session identifiers.
        """
        ...


# -----------------------------------------------------------------------------
# In-Memory Session Store Implementation
# -----------------------------------------------------------------------------

class InMemorySessionStore:
    """
    Thread-safe in-memory session store.

    Suitable for development and single-instance deployments.
    For production, consider Redis or database-backed implementations.

    Thread Safety:
        Uses a threading.Lock for safe concurrent access.
        All operations acquire the lock before modifying state.
    """

    def __init__(self) -> None:
        """Initialize an empty session store with a lock for thread safety."""
        self._sessions: Dict[str, SessionData] = {}
        self._lock: Lock = Lock()

    async def get(self, session_id: str) -> Optional[SessionData]:
        """
        Retrieve a session by ID.

        Args:
            session_id: The unique session identifier.

        Returns:
            SessionData if found, None otherwise.
        """
        with self._lock:
            return self._sessions.get(session_id)

    async def set(self, session_id: str, data: SessionData) -> None:
        """
        Store or update a session.

        Args:
            session_id: The unique session identifier.
            data: The session data to store.
        """
        with self._lock:
            data.updated_at = datetime.utcnow()
            self._sessions[session_id] = data

    async def delete(self, session_id: str) -> bool:
        """
        Delete a session.

        Args:
            session_id: The unique session identifier.

        Returns:
            True if session was deleted, False if not found.
        """
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                return True
            return False

    async def exists(self, session_id: str) -> bool:
        """
        Check if a session exists.

        Args:
            session_id: The unique session identifier.

        Returns:
            True if session exists, False otherwise.
        """
        with self._lock:
            return session_id in self._sessions

    async def list_sessions(self) -> list[str]:
        """
        List all session IDs.

        Returns:
            List of session identifiers.
        """
        with self._lock:
            return list(self._sessions.keys())


# -----------------------------------------------------------------------------
# Global Dependency Instances
# -----------------------------------------------------------------------------

# Global instances (initialized in lifespan, read-only thereafter)
_mcp_registry: Optional[MCPRegistry] = None
_session_store: Optional[SessionStore] = None
_init_lock: Lock = Lock()


def init_dependencies(
    mcp_registry: MCPRegistry,
    session_store: SessionStore
) -> None:
    """
    Initialize global dependencies.

    This function should be called once during application startup
    (typically in the FastAPI lifespan context manager).

    Thread Safety:
        Uses a lock to ensure atomic initialization.
        Safe to call from any thread, but should only be called once.

    Args:
        mcp_registry: The initialized MCP registry instance.
        session_store: The session store implementation to use.

    Raises:
        RuntimeError: If dependencies are already initialized.
    """
    global _mcp_registry, _session_store

    with _init_lock:
        if _mcp_registry is not None or _session_store is not None:
            raise RuntimeError(
                "Dependencies already initialized. "
                "Call reset_dependencies() first if re-initialization is needed."
            )
        _mcp_registry = mcp_registry
        _session_store = session_store


def reset_dependencies() -> None:
    """
    Reset global dependencies to uninitialized state.

    This is primarily useful for testing scenarios where you need
    to reinitialize dependencies between test cases.

    Thread Safety:
        Uses a lock to ensure atomic reset.
    """
    global _mcp_registry, _session_store

    with _init_lock:
        _mcp_registry = None
        _session_store = None


# -----------------------------------------------------------------------------
# FastAPI Dependency Functions
# -----------------------------------------------------------------------------

def get_mcp_registry() -> MCPRegistry:
    """
    FastAPI dependency to get the MCP registry.

    Returns:
        The initialized MCPRegistry instance.

    Raises:
        HTTPException: 503 Service Unavailable if registry not initialized.

    Example:
        @router.get("/servers")
        async def list_servers(registry: MCPRegistry = Depends(get_mcp_registry)):
            return registry.get_server_status()
    """
    if _mcp_registry is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MCP registry not initialized. The server may still be starting up."
        )
    return _mcp_registry


def get_session_store() -> SessionStore:
    """
    FastAPI dependency to get the session store.

    Returns:
        The initialized SessionStore instance.

    Raises:
        HTTPException: 503 Service Unavailable if store not initialized.

    Example:
        @router.post("/sessions")
        async def create_session(store: SessionStore = Depends(get_session_store)):
            ...
    """
    if _session_store is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Session store not initialized. The server may still be starting up."
        )
    return _session_store


async def get_session(
    session_id: str,
    store: SessionStore = Depends(get_session_store)
) -> SessionData:
    """
    FastAPI dependency to get and validate a session exists.

    This is a convenience dependency that combines session store access
    with session lookup and validation.

    Args:
        session_id: The session ID to look up (typically from path parameter).
        store: The session store (injected automatically).

    Returns:
        The SessionData for the requested session.

    Raises:
        HTTPException: 404 Not Found if session does not exist.
        HTTPException: 503 Service Unavailable if store not initialized.

    Example:
        @router.get("/sessions/{session_id}")
        async def get_session_state(session: SessionData = Depends(get_session)):
            return session.state
    """
    session = await store.get(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found. It may have expired or been deleted."
        )
    return session


# -----------------------------------------------------------------------------
# Convenience Functions for Testing
# -----------------------------------------------------------------------------

def is_initialized() -> bool:
    """
    Check if dependencies have been initialized.

    Returns:
        True if both MCP registry and session store are initialized.
    """
    return _mcp_registry is not None and _session_store is not None
