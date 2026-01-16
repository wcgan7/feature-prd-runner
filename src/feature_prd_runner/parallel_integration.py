"""Integration layer for parallel phase execution in the orchestrator.

This module provides the bridge between the ParallelExecutor and the
main orchestrator loop, enabling actual parallel execution of phases.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from .parallel import ParallelExecutor, PhaseResult


@dataclass
class PhaseExecutionContext:
    """Context needed to execute a phase."""

    phase_id: str
    phase_data: dict[str, Any]
    tasks: list[dict[str, Any]]  # All tasks for this phase
    project_dir: Path
    paths: dict[str, Path]
    config: dict[str, Any]


def group_tasks_by_phase(tasks: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Group tasks by their phase_id.

    Args:
        tasks: List of all tasks.

    Returns:
        Dictionary mapping phase_id to list of tasks.
    """
    phase_tasks: dict[str, list[dict[str, Any]]] = {}

    for task in tasks:
        phase_id = task.get("phase_id")
        if not phase_id:
            # Tasks without phase_id (like 'plan' task) are not parallelizable
            continue

        if phase_id not in phase_tasks:
            phase_tasks[phase_id] = []

        phase_tasks[phase_id].append(task)

    return phase_tasks


def extract_phase_dependencies(
    phases: list[dict[str, Any]],
    phase_tasks: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Extract phase information with dependencies for parallel execution.

    Args:
        phases: List of phases from phase_plan.yaml.
        phase_tasks: Tasks grouped by phase_id.

    Returns:
        List of phase dicts suitable for ParallelExecutor.
    """
    parallel_phases: list[dict[str, Any]] = []

    for phase in phases:
        phase_id = phase.get("id")
        if not phase_id:
            continue

        # Check if this phase has ready tasks
        tasks = phase_tasks.get(phase_id, [])
        if not tasks:
            continue

        # Check if any task for this phase is ready or running
        has_ready_task = any(
            t.get("lifecycle") in ["ready", "running"]
            for t in tasks
        )

        if not has_ready_task:
            continue

        # Create phase object for parallel executor
        parallel_phase = {
            "id": phase_id,
            "description": phase.get("description", ""),
            "deps": phase.get("deps", []),
            "tasks": tasks,
        }

        parallel_phases.append(parallel_phase)

    return parallel_phases


def can_execute_in_parallel(
    tasks: list[dict[str, Any]],
    phases: list[dict[str, Any]],
) -> tuple[bool, Optional[str]]:
    """Check if parallel execution is possible.

    Args:
        tasks: List of all tasks.
        phases: List of all phases.

    Returns:
        Tuple of (can_execute, reason_if_not).
    """
    # Must have phases
    if not phases:
        return False, "No phases defined"

    # Check if any tasks are ready
    ready_tasks = [t for t in tasks if t.get("lifecycle") == "ready"]
    if not ready_tasks:
        return False, "No ready tasks"

    # Group tasks by phase
    phase_tasks = group_tasks_by_phase(tasks)
    if not phase_tasks:
        return False, "No tasks associated with phases"

    # Extract parallelizable phases
    parallel_phases = extract_phase_dependencies(phases, phase_tasks)
    if len(parallel_phases) < 2:
        return False, "Less than 2 phases ready for execution"

    return True, None


def should_use_parallel_execution(
    parallel_enabled: bool,
    tasks: list[dict[str, Any]],
    phases: list[dict[str, Any]],
) -> bool:
    """Determine if parallel execution should be used.

    Args:
        parallel_enabled: Whether --parallel flag is set.
        tasks: List of all tasks.
        phases: List of all phases.

    Returns:
        True if parallel execution should be used.
    """
    if not parallel_enabled:
        return False

    can_execute, reason = can_execute_in_parallel(tasks, phases)

    if not can_execute:
        logger.debug("Parallel execution not viable: {}", reason)
        return False

    return True


def create_phase_executor_fn(
    phase_id: str,
    phase_data: dict[str, Any],
    context: PhaseExecutionContext,
) -> PhaseResult:
    """Create an executor function for a single phase.

    This function would execute all tasks for a phase sequentially,
    but multiple phases can run in parallel.

    Args:
        phase_id: Phase identifier.
        phase_data: Phase configuration.
        context: Execution context.

    Returns:
        PhaseResult with success/failure info.
    """
    # TODO: This is a placeholder for the actual phase execution logic
    # In a full implementation, this would:
    # 1. Execute all tasks for the phase (plan_impl -> implement -> verify -> review)
    # 2. Update task states in task_queue
    # 3. Handle errors and blocking conditions
    # 4. Return PhaseResult

    logger.info("Phase {} execution placeholder - would execute {} tasks", phase_id, len(phase_data.get("tasks", [])))

    # For now, just return success
    # Real implementation would integrate with the existing task execution logic
    return PhaseResult(
        phase_id=phase_id,
        success=True,
        error=None,
        duration_seconds=0.0,
    )


def log_parallel_execution_intent(
    phases: list[dict[str, Any]],
    max_workers: int,
) -> None:
    """Log information about parallel execution plan.

    Args:
        phases: Phases that will be executed in parallel.
        max_workers: Maximum number of workers.
    """
    executor = ParallelExecutor(max_workers=max_workers)

    try:
        plan = executor.resolve_execution_order(phases)

        logger.info("=" * 70)
        logger.info("PARALLEL EXECUTION PLAN")
        logger.info("=" * 70)
        logger.info("Total phases: {}", plan.total_phases)
        logger.info("Execution batches: {}", len(plan.batches))
        logger.info("Max parallelism: {}", plan.max_parallelism)
        logger.info("Workers available: {}", max_workers)

        for batch_idx, batch in enumerate(plan.batches, 1):
            phase_ids = ", ".join(batch)
            logger.info("  Batch {}: {} phase(s) - {}", batch_idx, len(batch), phase_ids)

        logger.info("=" * 70)

    except ValueError as e:
        logger.error("Failed to create parallel execution plan: {}", e)


# NOTE: Full integration with orchestrator would require:
# 1. Extracting the task execution logic into a reusable function
# 2. Making it thread-safe (already uses FileLock in many places)
# 3. Creating a wrapper that executes all tasks for a phase
# 4. Using ParallelExecutor to run phases concurrently
# 5. Collecting results and updating task states
# 6. Handling failures and dependencies properly
#
# This is a complex integration that would require significant refactoring
# of the orchestrator's main loop. The current implementation provides
# the infrastructure and visualization, with full parallel execution
# to be implemented in a future iteration.
