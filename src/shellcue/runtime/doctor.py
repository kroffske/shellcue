"""Actionable local runtime diagnostics."""

from __future__ import annotations

import importlib.metadata
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from shellcue.models.artifact import ArtifactError, load_artifact
from shellcue.models.registry import active_model_dir
from shellcue.runtime import daemon
from shellcue.runtime.shell_integration import render_shell_init, shell_rc_path


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str
    required: bool = True


def checks() -> tuple[Check, ...]:
    results = [
        Check(
            "python",
            sys.version_info >= (3, 10),
            f"{sys.version_info.major}.{sys.version_info.minor}",
        ),
        _dependency_check("transformers", minimum=(5, 0, 0)),
        _model_check(active_model_dir()),
    ]
    daemon_state = daemon.status()
    results.append(
        Check(
            "daemon",
            daemon_state.running,
            f"running pid={daemon_state.pid}" if daemon_state.running else "not running",
        )
    )
    results.extend(_suggestion_checks(daemon_state))
    results.append(_shell_check(_default_shell()))
    return tuple(results)


def _dependency_check(name: str, *, minimum: tuple[int, ...]) -> Check:
    try:
        version = importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return Check(name, False, "not installed; reinstall shellcue")
    numbers = tuple(int(part) for part in version.split(".")[:3] if part.isdigit())
    return Check(name, numbers >= minimum, version)


def _model_check(path: Path | None) -> Check:
    if path is None:
        return Check("model", False, "no active model")
    try:
        loaded = load_artifact(path)
    except ArtifactError as exc:
        return Check("model", False, str(exc))
    return Check("model", True, str(loaded.model_dir))


def _suggestion_checks(
    daemon_state: daemon.DaemonStatus,
) -> tuple[Check, Check]:
    if not daemon_state.running:
        detail = "daemon is not running; start the service before the functional probe"
        return (
            Check("suggestion", False, detail),
            Check("git-quality", False, detail, required=False),
        )
    try:
        runtime_candidates = daemon.suggest(
            prefix="pytest -",
            cwd=None,
            recent_commands=[],
            limit=1,
            timeout=2.0,
        )
    except RuntimeError as exc:
        return (
            Check("suggestion", False, str(exc)),
            Check("git-quality", False, "not run because suggestion transport failed", False),
        )
    runtime_command = _top_command(runtime_candidates)
    runtime_ok = bool(runtime_command)
    runtime = Check(
        "suggestion",
        runtime_ok,
        (
            f"pytest - -> {runtime_command}"
            if runtime_ok
            else "pytest - -> <none>; functional probe returned no suggestion"
        ),
    )
    try:
        git_candidates = daemon.suggest(
            prefix="git st",
            cwd=None,
            recent_commands=[],
            limit=1,
            timeout=2.0,
        )
        git_command = _top_command(git_candidates)
        quality_ok = git_command in {
            "git status",
            "git status --short",
            "git status --short --branch",
        }
        quality_detail = (
            f"git st -> {git_command}"
            if quality_ok
            else f"git st -> {git_command or '<none>'}; expected git status"
        )
    except RuntimeError as exc:
        quality_ok = False
        quality_detail = str(exc)
    return runtime, Check("git-quality", quality_ok, quality_detail, required=False)


def _shell_check(shell: str, *, rc_path: Path | None = None) -> Check:
    path = (rc_path or shell_rc_path(shell)).expanduser()
    expected = render_shell_init(shell).rstrip("\n")
    try:
        current = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        current = ""
    except OSError as exc:
        return Check("shell", False, f"cannot read {path}: {exc}")
    if expected not in current:
        return Check(
            "shell",
            False,
            f"{shell} hook missing or stale at {path}; run 'shellcue install-shell {shell}'",
        )
    detail = (
        f"zsh automatic hook installed at {path}; Tab accepts one word and "
        "Shift-Tab accepts the full suggestion"
        if shell == "zsh"
        else f"bash hook installed at {path}; press Ctrl-] to request a suggestion"
    )
    return Check("shell", True, detail)


def _default_shell() -> str:
    return "bash" if Path(os.environ.get("SHELL", "")).name == "bash" else "zsh"


def _top_command(candidates: tuple[dict[str, object], ...]) -> str:
    if not candidates:
        return ""
    command = candidates[0].get("command")
    return command if isinstance(command, str) else ""
