from __future__ import annotations

import shlex
from pathlib import Path
from typing import Optional

from loguru import logger

from ..git_utils import _path_is_allowed
from ..config import get_verify_config, load_runner_config
from ..io_utils import _save_data
from ..logging_utils import summarize_pytest_failures
from ..models import VerificationResult
from ..signals import (
    build_allowed_files,
    extract_paths_from_log,
    extract_ruff_repo_paths,
    extract_failed_test_files,
    extract_failures_section,
    extract_traceback_repo_paths,
    extract_mypy_repo_paths,
    filter_repo_file_paths,
    infer_suspect_source_files,
)
from ..tasks import _format_log_path, _lint_log_path, _resolve_test_command, _tests_log_path, _typecheck_log_path
from ..utils import _now_iso
from ..worker import _capture_test_result_snapshot, _run_command
from ..io_utils import _read_text_window


def _is_pytest_command(command: str) -> bool:
    cmd = (command or "").strip()
    if not cmd:
        return False

    # Fast-path common prefixes.
    if cmd.startswith("pytest"):
        return True
    if cmd.startswith("python") and " -m pytest" in cmd:
        return True

    # Tokenize and look for pytest invocation behind common wrappers
    # (poetry/uv/pipenv/hatch) or other prefixes.
    try:
        tokens = shlex.split(cmd)
    except ValueError:
        tokens = cmd.split()
    tokens = [t for t in tokens if t]
    if not tokens:
        return False

    if "pytest" in tokens:
        return True

    # python -m pytest ...
    if "python" in tokens:
        for i, tok in enumerate(tokens[:-1]):
            if tok == "-m" and tokens[i + 1] == "pytest":
                return True

    return False



def run_verify_action(
    *,
    project_dir: Path,
    artifacts_dir: Path,
    run_dir: Path,
    phase: Optional[dict],
    task: dict,
    run_id: str,
    plan_data: dict,
    default_test_command: Optional[str],
    default_format_command: Optional[str] = None,
    default_lint_command: Optional[str] = None,
    default_typecheck_command: Optional[str] = None,
    verify_profile: str = "none",
    ensure_ruff: str = "off",
    timeout_seconds: int,
) -> VerificationResult:
    phase_id = str(phase.get("id") if phase else task.get("phase_id") or task.get("id"))
    allowed_files = build_allowed_files(plan_data)

    config, config_err = load_runner_config(project_dir)
    verify_cfg = get_verify_config(config)
    cfg_test_command = verify_cfg.get("test_command") if isinstance(verify_cfg.get("test_command"), str) else None
    cfg_format_command = verify_cfg.get("format_command") if isinstance(verify_cfg.get("format_command"), str) else None
    cfg_lint_command = verify_cfg.get("lint_command") if isinstance(verify_cfg.get("lint_command"), str) else None
    cfg_typecheck_command = verify_cfg.get("typecheck_command") if isinstance(verify_cfg.get("typecheck_command"), str) else None

    test_command = _resolve_test_command(phase, task, default_test_command or cfg_test_command)
    format_command = default_format_command or cfg_format_command
    lint_command = default_lint_command or cfg_lint_command
    typecheck_command = default_typecheck_command or cfg_typecheck_command

    warnings: list[str] = []
    if config_err:
        warnings.append(f"config.yaml parse error: {config_err}")

    logger.info(
        "Running verification: command={} phase={}",
        test_command,
        phase_id,
    )

    def _tool_exists(name: str) -> bool:
        from shutil import which
        return bool(which(name))

    def _maybe_add_ruff_config(cmd: str) -> str:
        if ensure_ruff != "add-config":
            return cmd
        if "--config" in cmd.split():
            return cmd
        cfg_path = project_dir / ".prd_runner" / "ruff.toml"
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        if not cfg_path.exists():
            cfg_path.write_text('line-length = 100\n')
        return f"{cmd} --config {cfg_path}"

    def _run_stage(stage: str, command: str, log_path: Path) -> dict:
        result = _run_command(command, project_dir, log_path, timeout_seconds=timeout_seconds)
        snapshot = _capture_test_result_snapshot(
            command=command,
            exit_code=result["exit_code"],
            log_path=Path(result["log_path"]),
        )
        excerpt_text, excerpt_truncated = _read_text_window(Path(result["log_path"]), max_chars=120_000)
        excerpt_path = run_dir / f"{stage}_output.txt"
        excerpt_path.write_text(excerpt_text)
        return {
            "stage": stage,
            "command": command,
            "exit_code": int(result["exit_code"]),
            "timed_out": bool(result.get("timed_out")),
            "log_path": str(result["log_path"]),
            "log_tail": snapshot.get("log_tail", ""),
            "excerpt_path": str(excerpt_path),
            "excerpt_truncated": bool(excerpt_truncated),
            "captured_at": snapshot.get("captured_at", _now_iso()),
        }

    # Apply python profile defaults (opt-in).
    if verify_profile == "python":
        if not lint_command and _tool_exists("ruff"):
            lint_command = "ruff check ."
        if not format_command and _tool_exists("ruff"):
            format_command = "ruff format --check ."
        if not test_command and _tool_exists("pytest"):
            test_command = "pytest"
        if not typecheck_command and _tool_exists("mypy"):
            # Only enable if there appears to be a mypy config.
            candidates = [project_dir / "mypy.ini", project_dir / "setup.cfg", project_dir / "pyproject.toml"]
            if any(p.exists() and p.read_text(errors="replace").find("mypy") != -1 for p in candidates):
                typecheck_command = "mypy ."

    # Ruff helper modes.
    ruff_needed = any(
        isinstance(cmd, str) and cmd.strip().startswith("ruff")
        for cmd in [format_command, lint_command]
    )
    if ruff_needed and not _tool_exists("ruff"):
        if ensure_ruff == "warn":
            warnings.append("ruff not found; ruff-based format/lint will be skipped")
            if isinstance(format_command, str) and format_command.strip().startswith("ruff"):
                format_command = None
            if isinstance(lint_command, str) and lint_command.strip().startswith("ruff"):
                lint_command = None
        elif ensure_ruff == "install":
            # Best-effort install into current environment (may require network).
            install = _run_stage("ensure_ruff", "python -m pip install ruff", _lint_log_path(artifacts_dir, phase_id))
            if install["exit_code"] != 0:
                warnings.append("ruff install failed; ruff-based format/lint will fail")
            # re-check
            if not _tool_exists("ruff"):
                warnings.append("ruff still not available after install attempt")
        # add-config does not install; it only affects config when ruff exists.

    stages: list[dict] = []
    failing_stage: dict | None = None

    if isinstance(format_command, str) and format_command.strip():
        cmd = _maybe_add_ruff_config(format_command.strip())
        if cmd.startswith("ruff") and not _tool_exists("ruff"):
            failing_stage = {
                "stage": "format",
                "command": cmd,
                "exit_code": 127,
                "timed_out": False,
                "log_path": None,
                "log_tail": "ruff not found",
                "excerpt_path": None,
                "excerpt_truncated": False,
                "captured_at": _now_iso(),
            }
        else:
            res = _run_stage("format", cmd, _format_log_path(artifacts_dir, phase_id))
            stages.append(res)
            if res["exit_code"] != 0 or res["timed_out"]:
                failing_stage = res

    if not failing_stage and isinstance(lint_command, str) and lint_command.strip():
        cmd = _maybe_add_ruff_config(lint_command.strip())
        if cmd.startswith("ruff") and not _tool_exists("ruff"):
            failing_stage = {
                "stage": "lint",
                "command": cmd,
                "exit_code": 127,
                "timed_out": False,
                "log_path": None,
                "log_tail": "ruff not found",
                "excerpt_path": None,
                "excerpt_truncated": False,
                "captured_at": _now_iso(),
            }
        else:
            res = _run_stage("lint", cmd, _lint_log_path(artifacts_dir, phase_id))
            stages.append(res)
            if res["exit_code"] != 0 or res["timed_out"]:
                failing_stage = res

    if not failing_stage and isinstance(typecheck_command, str) and typecheck_command.strip():
        cmd = typecheck_command.strip()
        if cmd.split()[0] in {"mypy", "pyright"} and not _tool_exists(cmd.split()[0]):
            failing_stage = {
                "stage": "typecheck",
                "command": cmd,
                "exit_code": 127,
                "timed_out": False,
                "log_path": None,
                "log_tail": f"{cmd.split()[0]} not found",
                "excerpt_path": None,
                "excerpt_truncated": False,
                "captured_at": _now_iso(),
            }
        else:
            res = _run_stage("typecheck", cmd, _typecheck_log_path(artifacts_dir, phase_id))
            stages.append(res)
            if res["exit_code"] != 0 or res["timed_out"]:
                failing_stage = res

    if not failing_stage and isinstance(test_command, str) and test_command.strip():
        cmd = test_command.strip()
        if _is_pytest_command(cmd):
            if "--tb=" not in cmd:
                cmd += " --tb=long"
            if "--disable-warnings" not in cmd:
                cmd += " --disable-warnings"
            if "-q" not in cmd.split():
                cmd += " -q"
        res = _run_stage("tests", cmd, _tests_log_path(artifacts_dir, phase_id))
        # for pytest, overwrite excerpt file with failures section for better parsing
        if _is_pytest_command(cmd):
            excerpt_text, excerpt_truncated = _read_text_window(Path(res["log_path"]), max_chars=120_000)
            fail_text = extract_failures_section(excerpt_text)
            fail_path = run_dir / "pytest_failures.txt"
            fail_path.write_text(fail_text)
            res["excerpt_path"] = str(fail_path)
            res["excerpt_truncated"] = bool(excerpt_truncated)
        stages.append(res)
        if res["exit_code"] != 0 or res["timed_out"]:
            failing_stage = res

    if not stages and not failing_stage:
        # No verification configured; treat as pass.
        event = VerificationResult(
            run_id=run_id,
            passed=True,
            command=None,
            exit_code=0,
            log_path=None,
            log_tail="No verification commands configured",
            captured_at=_now_iso(),
            failing_paths=[],
            needs_allowlist_expansion=False,
            error_type=None,
        )
        _save_data(
            run_dir / "verify_manifest.json",
            {
                "run_id": run_id,
                "phase_id": phase_id,
                "passed": True,
                "warnings": warnings,
                "config_error": config_err,
                "stages": [],
            },
        )
        return event

    failing_repo_paths: list[str] = []
    expansion_paths: list[str] = []
    needs_expansion = False
    error_type = None
    stage_for_event = failing_stage or (stages[-1] if stages else None)
    if stage_for_event:
        stage_name = str(stage_for_event.get("stage") or "")
        timed_out = bool(stage_for_event.get("timed_out"))
        if timed_out:
            error_type = "verify_timeout"
        elif int(stage_for_event.get("exit_code") or 0) == 127:
            error_type = "tool_missing"
        else:
            error_type = f"{stage_name}_failed"

        excerpt_text = ""
        excerpt_path = stage_for_event.get("excerpt_path")
        if isinstance(excerpt_path, str) and excerpt_path:
            try:
                excerpt_text = Path(excerpt_path).read_text(errors="replace")
            except OSError:
                excerpt_text = stage_for_event.get("log_tail") or ""

        if stage_name in {"format", "lint"} and str(stage_for_event.get("command") or "").strip().startswith("ruff"):
            failing_repo_paths = extract_ruff_repo_paths(excerpt_text, project_dir)
        elif stage_name == "typecheck" and str(stage_for_event.get("command") or "").strip().startswith("mypy"):
            failing_repo_paths = extract_mypy_repo_paths(excerpt_text, project_dir)
        elif stage_name == "tests" and _is_pytest_command(str(stage_for_event.get("command") or "")):
            fail_text = excerpt_text
            failed_test_files = extract_failed_test_files(fail_text, project_dir)
            trace_files = extract_traceback_repo_paths(fail_text, project_dir)
            src_in_traces = [p for p in trace_files if p.startswith("src/")]
            suspect_source_files = infer_suspect_source_files(failed_test_files, project_dir) if (not src_in_traces and failed_test_files) else []
            failing_repo_paths = sorted(set(failed_test_files) | set(trace_files) | set(suspect_source_files))
        else:
            candidate_paths = filter_repo_file_paths(extract_paths_from_log(excerpt_text, project_dir), project_dir)
            failing_repo_paths = [
                p for p in candidate_paths if (p.startswith("src/") or p.startswith("tests/"))
            ]

        meaningful_allowlist = [p for p in allowed_files if p and p != "README.md"]
        if meaningful_allowlist:
            outside = [p for p in failing_repo_paths if not _path_is_allowed(project_dir, p, allowed_files)]
            needs_expansion = bool(outside)
            expansion_paths = outside if needs_expansion else []

    passed = failing_stage is None
    if needs_expansion:
        logger.info("Verification failed; switching to PLAN_IMPL (expand allowlist)")
        logger.info("Expansion paths: {}", expansion_paths)
    elif not passed:
        logger.info("Verification failed; retrying IMPLEMENT (fix verification)")
    else:
        logger.info("Verification passed")

    event = VerificationResult(
        run_id=run_id,
        passed=bool(passed),
        command=str(stage_for_event.get("command") or "") if stage_for_event else None,
        exit_code=int(stage_for_event.get("exit_code") or (0 if passed else 1)) if stage_for_event else 0,
        log_path=str(stage_for_event.get("log_path") or "") if stage_for_event else None,
        log_tail=str(stage_for_event.get("log_tail") or ""),
        captured_at=str(stage_for_event.get("captured_at") or _now_iso()),
        failing_paths=expansion_paths,
        needs_allowlist_expansion=bool(needs_expansion),
        error_type=error_type,
    )

    _save_data(
        run_dir / "verify_manifest.json",
        {
            "run_id": run_id,
            "task_id": str(task.get("id")),
            "phase_id": str(task.get("phase_id") or task.get("id") or ""),
            "step": "verify",
            "passed": bool(passed),
            "error_type": error_type,
            "needs_allowlist_expansion": bool(needs_expansion),
            "failing_paths": list(expansion_paths),
            "allowlist_used": allowed_files,
            "verify_profile": verify_profile,
            "ensure_ruff": ensure_ruff,
            "warnings": warnings,
            "config_error": config_err,
            "stages": stages,
            "failing_stage": failing_stage,
            "failing_repo_paths": failing_repo_paths,
        },
    )
    return event
