"""Parallel phase execution with dependency resolution.

This module provides parallel execution of independent phases with
topological ordering and circular dependency detection.
"""

from __future__ import annotations

import concurrent.futures
import threading
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any, Callable, Optional

from loguru import logger
from rich.console import Console
from rich.table import Table
from rich.tree import Tree


@dataclass
class PhaseResult:
    """Result of phase execution."""

    phase_id: str
    success: bool
    error: Optional[str] = None
    duration_seconds: float = 0.0


@dataclass
class ExecutionPlan:
    """Execution plan with batches."""

    batches: list[list[str]]  # List of batches, each batch can run in parallel
    total_phases: int
    max_parallelism: int  # Maximum phases in any single batch


class ParallelExecutor:
    """Execute phases in parallel with topological ordering."""

    def __init__(self, max_workers: int = 3):
        """Initialize parallel executor.

        Args:
            max_workers: Maximum number of concurrent workers.
        """
        self.max_workers = max_workers
        self.console = Console()
        self._lock = threading.Lock()
        self._phase_status: dict[str, str] = {}  # phase_id -> status
        self._phase_errors: dict[str, str] = {}  # phase_id -> error

    def check_circular_deps(self, phases: list[dict[str, Any]]) -> Optional[list[str]]:
        """Detect circular dependencies in phases.

        Args:
            phases: List of phase dictionaries with 'id' and 'deps' fields.

        Returns:
            List representing the cycle if found, None otherwise.
        """
        # Build adjacency list
        graph: dict[str, list[str]] = defaultdict(list)
        for phase in phases:
            phase_id = phase.get("id", "")
            deps = phase.get("deps", [])
            for dep in deps:
                graph[dep].append(phase_id)

        # Track visit state: 0 = unvisited, 1 = visiting, 2 = visited
        state: dict[str, int] = {phase.get("id", ""): 0 for phase in phases}
        parent: dict[str, Optional[str]] = {phase.get("id", ""): None for phase in phases}

        def dfs(node: str, path: list[str]) -> Optional[list[str]]:
            """DFS to detect cycles."""
            if state[node] == 1:
                # Found a cycle - reconstruct it
                cycle_start = path.index(node)
                return path[cycle_start:] + [node]
            if state[node] == 2:
                return None

            state[node] = 1
            path.append(node)

            for neighbor in graph.get(node, []):
                cycle = dfs(neighbor, path.copy())
                if cycle:
                    return cycle

            state[node] = 2
            return None

        # Check for cycles starting from each unvisited node
        for phase in phases:
            phase_id = phase.get("id", "")
            if state[phase_id] == 0:
                cycle = dfs(phase_id, [])
                if cycle:
                    return cycle

        return None

    def resolve_execution_order(self, phases: list[dict[str, Any]]) -> ExecutionPlan:
        """Return batches of phase IDs that can run in parallel using topological sort.

        Args:
            phases: List of phase dictionaries with 'id' and 'deps' fields.

        Returns:
            ExecutionPlan with batches of phase IDs.

        Raises:
            ValueError: If circular dependency detected.
        """
        # Check for circular dependencies first
        cycle = self.check_circular_deps(phases)
        if cycle:
            raise ValueError(f"Circular dependency detected: {' -> '.join(cycle)}")

        # Build phase lookup
        phase_by_id = {phase.get("id", ""): phase for phase in phases}

        # Build dependency graph
        in_degree: dict[str, int] = {}
        graph: dict[str, list[str]] = defaultdict(list)

        for phase in phases:
            phase_id = phase.get("id", "")
            deps = phase.get("deps", [])
            in_degree[phase_id] = len(deps)

            for dep in deps:
                graph[dep].append(phase_id)

        # Kahn's algorithm for topological sort with batching
        batches: list[list[str]] = []
        queue = deque([pid for pid in in_degree if in_degree[pid] == 0])

        while queue:
            # Current batch: all phases with no remaining dependencies
            batch = list(queue)
            batches.append(batch)
            queue.clear()

            # Process current batch
            for phase_id in batch:
                # Reduce in-degree for all dependents
                for dependent in graph.get(phase_id, []):
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)

        # Verify all phases were included (sanity check)
        total_in_batches = sum(len(batch) for batch in batches)
        if total_in_batches != len(phases):
            missing = [p.get("id") for p in phases if p.get("id") not in [pid for batch in batches for pid in batch]]
            raise ValueError(f"Failed to schedule all phases. Missing: {missing}")

        max_parallelism = max(len(batch) for batch in batches) if batches else 0

        return ExecutionPlan(
            batches=batches,
            total_phases=len(phases),
            max_parallelism=max_parallelism,
        )

    def visualize_execution_plan(self, phases: list[dict[str, Any]], plan: ExecutionPlan) -> str:
        """Visualize execution plan as tree.

        Args:
            phases: List of phases.
            plan: Execution plan.

        Returns:
            Formatted tree representation.
        """
        console = Console(record=True, width=100)

        console.print("\n[bold]Parallel Execution Plan[/bold]")
        console.print(f"Total phases: {plan.total_phases}")
        console.print(f"Batches: {len(plan.batches)}")
        console.print(f"Max parallelism: {plan.max_parallelism}")
        console.print()

        phase_by_id = {p.get("id", ""): p for p in phases}

        for batch_idx, batch in enumerate(plan.batches, 1):
            console.print(f"[bold cyan]Batch {batch_idx}:[/bold cyan] ({len(batch)} phase(s) in parallel)")

            for phase_id in batch:
                phase = phase_by_id.get(phase_id, {})
                deps = phase.get("deps", [])
                desc = phase.get("description", "No description")

                if deps:
                    console.print(f"  • {phase_id} [dim](depends on: {', '.join(deps)})[/dim]")
                else:
                    console.print(f"  • {phase_id}")
                console.print(f"    {desc[:80]}")

            console.print()

        return console.export_text()

    def visualize_as_tree(self, phases: list[dict[str, Any]]) -> str:
        """Visualize dependencies as tree.

        Args:
            phases: List of phases.

        Returns:
            Formatted tree.
        """
        console = Console(record=True, width=100)

        phase_by_id = {p.get("id", ""): p for p in phases}

        # Find root phases (no dependencies)
        roots = [p for p in phases if not p.get("deps", [])]

        tree = Tree("[bold]Phase Dependency Tree[/bold]")

        def add_dependents(parent_node: Tree, phase_id: str, visited: set[str]) -> None:
            """Recursively add dependent phases."""
            if phase_id in visited:
                return
            visited.add(phase_id)

            # Find phases that depend on this one
            dependents = [p for p in phases if phase_id in p.get("deps", [])]

            for dep_phase in dependents:
                dep_id = dep_phase.get("id", "")
                branch = parent_node.add(f"[cyan]{dep_id}[/cyan]")
                add_dependents(branch, dep_id, visited)

        visited: set[str] = set()
        for root in roots:
            root_id = root.get("id", "")
            branch = tree.add(f"[green]{root_id}[/green]")
            add_dependents(branch, root_id, visited)

        console.print(tree)
        return console.export_text()

    def execute_parallel(
        self,
        phases: list[dict[str, Any]],
        executor_fn: Callable[[str, dict[str, Any]], PhaseResult],
        max_workers: Optional[int] = None,
    ) -> list[PhaseResult]:
        """Execute phases in parallel batches.

        Args:
            phases: List of phase dictionaries.
            executor_fn: Function to execute a single phase.
                         Takes (phase_id, phase_dict) and returns PhaseResult.
            max_workers: Override max workers for this execution.

        Returns:
            List of PhaseResult for all phases.

        Raises:
            ValueError: If circular dependency detected.
        """
        workers = max_workers or self.max_workers
        plan = self.resolve_execution_order(phases)

        logger.info("Parallel execution plan: {} batches, max parallelism: {}", len(plan.batches), plan.max_parallelism)

        results: list[PhaseResult] = []
        phase_by_id = {p.get("id", ""): p for p in phases}

        for batch_idx, batch in enumerate(plan.batches, 1):
            logger.info("Executing batch {}/{} with {} phase(s)", batch_idx, len(plan.batches), len(batch))

            # Execute current batch in parallel
            batch_results = self._execute_batch(batch, phase_by_id, executor_fn, workers)
            results.extend(batch_results)

            # Check for failures in batch
            failures = [r for r in batch_results if not r.success]
            if failures:
                logger.warning("Batch {} had {} failure(s)", batch_idx, len(failures))
                for failure in failures:
                    logger.warning("  - Phase {} failed: {}", failure.phase_id, failure.error)

                # Optionally stop on first failure
                # For now, continue with remaining batches
                # TODO: Add configuration for fail-fast behavior

        return results

    def _execute_batch(
        self,
        batch: list[str],
        phase_by_id: dict[str, dict[str, Any]],
        executor_fn: Callable[[str, dict[str, Any]], PhaseResult],
        max_workers: int,
    ) -> list[PhaseResult]:
        """Execute a single batch of phases in parallel.

        Args:
            batch: List of phase IDs to execute.
            phase_by_id: Phase lookup dictionary.
            executor_fn: Executor function.
            max_workers: Maximum workers.

        Returns:
            List of results for this batch.
        """
        if len(batch) == 1:
            # Single phase - execute directly without thread pool overhead
            phase_id = batch[0]
            phase = phase_by_id[phase_id]
            with self._lock:
                self._phase_status[phase_id] = "running"

            result = executor_fn(phase_id, phase)

            with self._lock:
                self._phase_status[phase_id] = "completed" if result.success else "failed"
                if not result.success:
                    self._phase_errors[phase_id] = result.error or "Unknown error"

            return [result]

        # Multiple phases - use thread pool
        results: list[PhaseResult] = []

        def execute_phase_wrapper(phase_id: str) -> PhaseResult:
            """Wrapper to track status."""
            phase = phase_by_id[phase_id]

            with self._lock:
                self._phase_status[phase_id] = "running"

            try:
                result = executor_fn(phase_id, phase)
            except Exception as e:
                logger.exception("Unexpected error executing phase {}: {}", phase_id, e)
                result = PhaseResult(
                    phase_id=phase_id,
                    success=False,
                    error=f"Unexpected error: {e}",
                )

            with self._lock:
                self._phase_status[phase_id] = "completed" if result.success else "failed"
                if not result.success:
                    self._phase_errors[phase_id] = result.error or "Unknown error"

            return result

        # Execute in parallel with thread pool
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(execute_phase_wrapper, pid): pid for pid in batch}

            for future in concurrent.futures.as_completed(futures):
                phase_id = futures[future]
                try:
                    result = future.result()
                    results.append(result)
                    logger.info("Phase {} completed: success={}", phase_id, result.success)
                except Exception as e:
                    logger.exception("Failed to get result for phase {}: {}", phase_id, e)
                    results.append(
                        PhaseResult(
                            phase_id=phase_id,
                            success=False,
                            error=f"Execution error: {e}",
                        )
                    )

        return results

    def get_status(self) -> dict[str, str]:
        """Get current status of all phases.

        Returns:
            Dictionary mapping phase_id to status.
        """
        with self._lock:
            return dict(self._phase_status)

    def get_errors(self) -> dict[str, str]:
        """Get errors for failed phases.

        Returns:
            Dictionary mapping phase_id to error message.
        """
        with self._lock:
            return dict(self._phase_errors)

    def print_progress(self) -> None:
        """Print current progress to console."""
        status = self.get_status()
        errors = self.get_errors()

        if not status:
            return

        table = Table(title="Parallel Execution Progress", show_header=True)
        table.add_column("Phase ID", style="cyan")
        table.add_column("Status", style="bold")
        table.add_column("Error", style="red")

        for phase_id, state in status.items():
            error_msg = errors.get(phase_id, "")
            if state == "running":
                status_str = "[yellow]Running[/yellow]"
            elif state == "completed":
                status_str = "[green]✓ Completed[/green]"
            elif state == "failed":
                status_str = "[red]✗ Failed[/red]"
            else:
                status_str = state

            table.add_row(phase_id, status_str, error_msg[:50] if error_msg else "")

        self.console.print(table)
