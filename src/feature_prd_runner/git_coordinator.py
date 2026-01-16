"""Thread-safe git operations coordinator for parallel execution.

This module provides a global lock for git operations to ensure they
don't conflict when running phases in parallel.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar

from loguru import logger

T = TypeVar("T")


class GitCoordinator:
    """Coordinate git operations across parallel phases.

    Git is not designed for concurrent operations on the same repository.
    This class ensures that only one thread can perform git operations
    at a time by using a global lock.
    """

    _instance: Optional[GitCoordinator] = None
    _lock = threading.Lock()

    def __new__(cls) -> GitCoordinator:
        """Singleton pattern to ensure one coordinator per process."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._git_lock = threading.RLock()
        return cls._instance

    def __init__(self) -> None:
        """Initialize git coordinator."""
        if not hasattr(self, "_initialized"):
            self._git_lock = threading.RLock()
            self._initialized = True

    def execute_git_operation(
        self,
        operation: Callable[[], T],
        operation_name: str = "git operation",
    ) -> T:
        """Execute a git operation with global lock.

        Args:
            operation: Function that performs git operation.
            operation_name: Name of operation for logging.

        Returns:
            Result of the operation.

        Raises:
            Any exception raised by the operation.
        """
        thread_id = threading.current_thread().name
        logger.debug("Thread {} waiting for git lock ({})", thread_id, operation_name)

        with self._git_lock:
            logger.debug("Thread {} acquired git lock ({})", thread_id, operation_name)
            try:
                result = operation()
                logger.debug("Thread {} completed git operation ({})", thread_id, operation_name)
                return result
            except Exception as e:
                logger.error("Thread {} git operation failed ({}): {}", thread_id, operation_name, e)
                raise
            finally:
                logger.debug("Thread {} releasing git lock ({})", thread_id, operation_name)

    def with_git_lock(self, operation: Callable[[], T]) -> T:
        """Context-free version of execute_git_operation.

        Args:
            operation: Function to execute under git lock.

        Returns:
            Result of operation.
        """
        return self.execute_git_operation(operation, operation_name="unlabeled")


# Global instance
_git_coordinator = GitCoordinator()


def get_git_coordinator() -> GitCoordinator:
    """Get the global git coordinator instance.

    Returns:
        GitCoordinator singleton.
    """
    return _git_coordinator


def with_git_lock(func: Callable[..., T]) -> Callable[..., T]:
    """Decorator to run a function with git lock.

    Usage:
        @with_git_lock
        def my_git_operation():
            # This will be serialized across threads
            subprocess.run(["git", "status"])

    Args:
        func: Function to wrap.

    Returns:
        Wrapped function.
    """
    def wrapper(*args: Any, **kwargs: Any) -> T:
        coordinator = get_git_coordinator()
        return coordinator.execute_git_operation(
            lambda: func(*args, **kwargs),
            operation_name=func.__name__,
        )
    return wrapper
