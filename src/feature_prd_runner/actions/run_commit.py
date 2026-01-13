from __future__ import annotations

from typing import Optional

from ..git_utils import _git_commit, _git_has_changes, _git_push
from ..models import CommitResult


def run_commit_action(
    *,
    project_dir,
    branch: str,
    commit_message: str,
    run_id: str,
    commit_enabled: bool = True,
    push_enabled: bool = True,
) -> CommitResult:
    if not _git_has_changes(project_dir):
        return CommitResult(run_id=run_id, committed=False, pushed=False, error=None, repo_clean=True)

    if not commit_enabled:
        return CommitResult(
            run_id=run_id,
            committed=False,
            pushed=False,
            error=None,
            repo_clean=False,
            skipped=True,
        )

    if push_enabled and not str(branch or "").strip():
        return CommitResult(
            run_id=run_id,
            committed=False,
            pushed=False,
            error="Branch is required to push; set a phase branch or re-run with --no-push",
            repo_clean=False,
            skipped=False,
        )

    try:
        _git_commit(project_dir, commit_message)
        if push_enabled:
            _git_push(project_dir, branch)
        return CommitResult(
            run_id=run_id,
            committed=True,
            pushed=bool(push_enabled),
            error=None,
            repo_clean=False,
            skipped=False,
        )
    except Exception as exc:  # pragma: no cover - git errors are runtime
        return CommitResult(
            run_id=run_id,
            committed=False,
            pushed=False,
            error=str(exc),
            repo_clean=False,
            skipped=False,
        )
