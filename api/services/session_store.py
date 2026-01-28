"""Session store for modeling workflow sessions.

This module provides abstract and concrete implementations of session storage
for the data modeling workflow. It supports both in-memory storage for development
and Redis-based storage for production environments.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import uuid
import copy


class SessionStatus(str, Enum):
    """Enumeration of possible session statuses."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class WorkflowStep(str, Enum):
    """Enumeration of workflow steps."""
    INITIALIZED = "initialized"
    REQUIREMENTS_ANALYSIS = "requirements_analysis"
    SCHEMA_DISCOVERY = "schema_discovery"
    MODEL_DESIGN = "model_design"
    VALIDATION = "validation"
    GENERATION = "generation"
    COMPLETED = "completed"


@dataclass
class SessionData:
    """Data class for session information.

    Attributes:
        session_id: Unique identifier for the session.
        project_name: Name of the modeling project.
        requirements: User requirements for the data model.
        data_source: Type of data source (e.g., "postgres", "mysql").
        modeling_strategy: Strategy for modeling (e.g., "STAR_SCHEMA", "SNOWFLAKE").
        created_at: Timestamp when session was created.
        updated_at: Timestamp of last update.
        current_step: Current workflow step.
        status: Current session status.
        progress: Progress percentage (0.0 to 1.0).
        state: Full workflow state dictionary.
        error_message: Optional error message if status is FAILED.
    """
    session_id: str
    project_name: str
    requirements: str
    data_source: str
    modeling_strategy: str
    created_at: datetime
    updated_at: datetime
    current_step: str = WorkflowStep.INITIALIZED.value
    status: str = SessionStatus.PENDING.value
    progress: float = 0.0
    state: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert session data to dictionary.

        Returns:
            Dictionary representation with datetime objects converted to ISO format.
        """
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        data["updated_at"] = self.updated_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionData":
        """Create SessionData from dictionary.

        Args:
            data: Dictionary containing session data.

        Returns:
            SessionData instance.
        """
        data = data.copy()
        if isinstance(data.get("created_at"), str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if isinstance(data.get("updated_at"), str):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        return cls(**data)


class SessionStore(ABC):
    """Abstract base class for session storage.

    This defines the interface that all session store implementations must follow.
    Concrete implementations can use different backends (in-memory, Redis, database, etc.).
    """

    @abstractmethod
    async def create(
        self,
        project_name: str,
        requirements: str,
        data_source: str,
        modeling_strategy: str,
    ) -> SessionData:
        """Create a new session.

        Args:
            project_name: Name of the modeling project.
            requirements: User requirements for the data model.
            data_source: Type of data source.
            modeling_strategy: Strategy for data modeling.

        Returns:
            Newly created SessionData instance.
        """
        pass

    @abstractmethod
    async def get(self, session_id: str) -> Optional[SessionData]:
        """Get session by ID.

        Args:
            session_id: Unique session identifier.

        Returns:
            SessionData if found, None otherwise.
        """
        pass

    @abstractmethod
    async def update(self, session_id: str, **kwargs: Any) -> Optional[SessionData]:
        """Update session fields.

        Args:
            session_id: Unique session identifier.
            **kwargs: Fields to update with their new values.

        Returns:
            Updated SessionData if found, None otherwise.
        """
        pass

    @abstractmethod
    async def delete(self, session_id: str) -> bool:
        """Delete a session.

        Args:
            session_id: Unique session identifier.

        Returns:
            True if session was deleted, False if not found.
        """
        pass

    @abstractmethod
    async def list_sessions(self, limit: int = 100) -> List[SessionData]:
        """List all sessions.

        Args:
            limit: Maximum number of sessions to return.

        Returns:
            List of SessionData instances, ordered by creation time (newest first).
        """
        pass

    @abstractmethod
    async def cleanup_expired(self) -> int:
        """Remove expired sessions.

        Returns:
            Number of sessions removed.
        """
        pass


class InMemorySessionStore(SessionStore):
    """In-memory session store for development.

    This implementation stores sessions in a dictionary with thread-safe access
    using asyncio locks. Sessions are automatically expired based on TTL.

    Attributes:
        _sessions: Dictionary mapping session IDs to SessionData.
        _ttl: Time-to-live for sessions.
        _lock: Asyncio lock for thread-safe access.
    """

    def __init__(self, ttl_hours: int = 24):
        """Initialize the in-memory session store.

        Args:
            ttl_hours: Hours until a session expires. Defaults to 24.
        """
        self._sessions: Dict[str, SessionData] = {}
        self._ttl = timedelta(hours=ttl_hours)
        self._lock = asyncio.Lock()

    async def create(
        self,
        project_name: str,
        requirements: str,
        data_source: str,
        modeling_strategy: str,
    ) -> SessionData:
        """Create a new session.

        Args:
            project_name: Name of the modeling project.
            requirements: User requirements for the data model.
            data_source: Type of data source.
            modeling_strategy: Strategy for data modeling.

        Returns:
            Newly created SessionData instance.
        """
        session_id = str(uuid.uuid4())
        now = datetime.utcnow()

        session = SessionData(
            session_id=session_id,
            project_name=project_name,
            requirements=requirements,
            data_source=data_source,
            modeling_strategy=modeling_strategy,
            created_at=now,
            updated_at=now,
            current_step=WorkflowStep.INITIALIZED.value,
            status=SessionStatus.PENDING.value,
            progress=0.0,
            state={},
        )

        async with self._lock:
            self._sessions[session_id] = session

        return session

    async def get(self, session_id: str) -> Optional[SessionData]:
        """Get session by ID.

        Args:
            session_id: Unique session identifier.

        Returns:
            SessionData if found and not expired, None otherwise.
        """
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None

            # Check if session has expired
            if self._is_expired(session):
                del self._sessions[session_id]
                return None

            # Return a deep copy to prevent external modification
            return copy.deepcopy(session)

    async def update(self, session_id: str, **kwargs: Any) -> Optional[SessionData]:
        """Update session fields.

        Args:
            session_id: Unique session identifier.
            **kwargs: Fields to update. Valid fields are: project_name, requirements,
                     data_source, modeling_strategy, current_step, status, progress,
                     state, error_message.

        Returns:
            Updated SessionData if found, None otherwise.

        Raises:
            ValueError: If attempting to update immutable fields (session_id, created_at).
        """
        # Validate that we're not trying to update immutable fields
        immutable_fields = {"session_id", "created_at"}
        invalid_fields = immutable_fields.intersection(kwargs.keys())
        if invalid_fields:
            raise ValueError(f"Cannot update immutable fields: {invalid_fields}")

        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None

            # Check if session has expired
            if self._is_expired(session):
                del self._sessions[session_id]
                return None

            # Update allowed fields
            valid_fields = {
                "project_name",
                "requirements",
                "data_source",
                "modeling_strategy",
                "current_step",
                "status",
                "progress",
                "state",
                "error_message",
            }

            for key, value in kwargs.items():
                if key in valid_fields:
                    setattr(session, key, value)

            # Always update the updated_at timestamp
            session.updated_at = datetime.utcnow()

            return copy.deepcopy(session)

    async def delete(self, session_id: str) -> bool:
        """Delete a session.

        Args:
            session_id: Unique session identifier.

        Returns:
            True if session was deleted, False if not found.
        """
        async with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                return True
            return False

    async def list_sessions(self, limit: int = 100) -> List[SessionData]:
        """List all sessions.

        Args:
            limit: Maximum number of sessions to return. Defaults to 100.

        Returns:
            List of SessionData instances, ordered by creation time (newest first).
            Expired sessions are excluded.
        """
        async with self._lock:
            # Filter out expired sessions and sort by creation time
            valid_sessions = [
                copy.deepcopy(session)
                for session in self._sessions.values()
                if not self._is_expired(session)
            ]

            # Sort by created_at descending (newest first)
            valid_sessions.sort(key=lambda s: s.created_at, reverse=True)

            return valid_sessions[:limit]

    async def cleanup_expired(self) -> int:
        """Remove expired sessions.

        Returns:
            Number of sessions removed.
        """
        async with self._lock:
            expired_ids = [
                session_id
                for session_id, session in self._sessions.items()
                if self._is_expired(session)
            ]

            for session_id in expired_ids:
                del self._sessions[session_id]

            return len(expired_ids)

    def _is_expired(self, session: SessionData) -> bool:
        """Check if a session has expired.

        Args:
            session: Session to check.

        Returns:
            True if session has expired, False otherwise.
        """
        return datetime.utcnow() - session.updated_at > self._ttl

    async def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the session store.

        Returns:
            Dictionary containing session count, status breakdown, etc.
        """
        async with self._lock:
            sessions = list(self._sessions.values())

            status_counts: Dict[str, int] = {}
            for session in sessions:
                status = session.status
                status_counts[status] = status_counts.get(status, 0) + 1

            return {
                "total_sessions": len(sessions),
                "status_breakdown": status_counts,
                "ttl_hours": self._ttl.total_seconds() / 3600,
            }


class RedisSessionStore(SessionStore):
    """Redis-based session store for production.

    This implementation uses Redis for distributed session storage,
    enabling horizontal scaling and persistence across server restarts.

    Note: This is a placeholder implementation. Full Redis integration
    will be implemented in a future phase.
    """

    def __init__(self, redis_url: str, ttl_hours: int = 24):
        """Initialize the Redis session store.

        Args:
            redis_url: Redis connection URL (e.g., "redis://localhost:6379/0").
            ttl_hours: Hours until a session expires. Defaults to 24.

        Raises:
            NotImplementedError: Redis store is not yet implemented.
        """
        self._redis_url = redis_url
        self._ttl_hours = ttl_hours
        raise NotImplementedError(
            "Redis store not yet implemented. Use InMemorySessionStore for development."
        )

    async def create(
        self,
        project_name: str,
        requirements: str,
        data_source: str,
        modeling_strategy: str,
    ) -> SessionData:
        """Create a new session in Redis."""
        raise NotImplementedError("Redis store not yet implemented")

    async def get(self, session_id: str) -> Optional[SessionData]:
        """Get session by ID from Redis."""
        raise NotImplementedError("Redis store not yet implemented")

    async def update(self, session_id: str, **kwargs: Any) -> Optional[SessionData]:
        """Update session fields in Redis."""
        raise NotImplementedError("Redis store not yet implemented")

    async def delete(self, session_id: str) -> bool:
        """Delete a session from Redis."""
        raise NotImplementedError("Redis store not yet implemented")

    async def list_sessions(self, limit: int = 100) -> List[SessionData]:
        """List all sessions from Redis."""
        raise NotImplementedError("Redis store not yet implemented")

    async def cleanup_expired(self) -> int:
        """Remove expired sessions from Redis."""
        raise NotImplementedError("Redis store not yet implemented")


def get_session_store(backend: str = "memory", **kwargs: Any) -> SessionStore:
    """Factory function to get a session store instance.

    Args:
        backend: Storage backend to use ("memory" or "redis").
        **kwargs: Additional arguments passed to the store constructor.
            For "memory": ttl_hours (int)
            For "redis": redis_url (str), ttl_hours (int)

    Returns:
        SessionStore instance.

    Raises:
        ValueError: If an unknown backend is specified.
    """
    if backend == "memory":
        return InMemorySessionStore(**kwargs)
    elif backend == "redis":
        return RedisSessionStore(**kwargs)
    else:
        raise ValueError(f"Unknown session store backend: {backend}")
