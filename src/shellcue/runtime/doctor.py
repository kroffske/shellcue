"""Actionable local runtime diagnostics."""

from __future__ import annotations

import importlib.metadata
import sys
from dataclasses import dataclass
from pathlib import Path

from shellcue.models.artifact import ArtifactError, load_artifact
from shellcue.models.registry import active_model_dir
from shellcue.runtime.daemon import status


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
    daemon_state = status()
    results.append(
        Check(
            "daemon",
            daemon_state.running,
            f"running pid={daemon_state.pid}" if daemon_state.running else "not running",
            required=False,
        )
    )
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
