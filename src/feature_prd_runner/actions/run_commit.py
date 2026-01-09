from __future__ import annotations

from typing import Optional

from ..git_utils import _git_commit_and_push, _git_has_changes
from ..models import CommitResult


def run_commit_action(
    *,
    project_dir,
    branch: str,
    commit_message: str,
    run_id: str,
) -> CommitResult:
    if not _git_has_changes(project_dir):
        return CommitResult(run_id=run_id, pushed=False, error=None, repo_clean=True)

    try:
        _git_commit_and_push(project_dir, branch, commit_message)
        return CommitResult(run_id=run_id, pushed=True, error=None, repo_clean=False)
    except Exception as exc:  # pragma: no cover - git errors are runtime
        return CommitResult(run_id=run_id, pushed=False, error=str(exc), repo_clean=False)
