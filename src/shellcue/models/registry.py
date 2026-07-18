"""Atomic local model installation and active-model selection."""

from __future__ import annotations

import fcntl
import json
import os
import re
import shutil
import threading
from collections.abc import Iterator, Mapping
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from shellcue.models.artifact import LoadedArtifact, load_artifact

_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_LOCAL_LOCKS: dict[Path, threading.Lock] = {}
_LOCAL_LOCKS_GUARD = threading.Lock()


@dataclass(frozen=True)
class InstalledModel:
    name: str
    model_dir: Path
    active: bool


def cache_dir() -> Path:
    override = os.environ.get("SHELLCUE_CACHE_DIR")
    if override:
        return Path(override).expanduser()
    root = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")).expanduser()
    return root / "shellcue"


def config_dir() -> Path:
    override = os.environ.get("SHELLCUE_CONFIG_DIR")
    if override:
        return Path(override).expanduser()
    root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")).expanduser()
    return root / "shellcue"


def models_dir() -> Path:
    return cache_dir() / "models"


def active_model_dir() -> Path | None:
    explicit = os.environ.get("SHELLCUE_MODEL_DIR")
    if explicit:
        return Path(explicit).expanduser()
    config = _read_config()
    active = config.get("active_model")
    if not isinstance(active, str):
        return None
    entry = config.get("models", {}).get(active) if isinstance(config.get("models"), dict) else None
    if isinstance(entry, dict) and isinstance(entry.get("path"), str):
        path = Path(entry["path"]).expanduser()
    else:
        path = models_dir() / active
    expected = models_dir() / normalize_name(active)
    if Path(os.path.abspath(path)) != Path(os.path.abspath(expected)):
        raise RuntimeError(f"configured model path is outside the managed registry: {path}")
    with _model_transaction(path):
        _recover_interrupted_replacement_locked(path)
    return path


def install_model(source: Path, *, name: str | None = None, force: bool = False) -> LoadedArtifact:
    source = source.expanduser().resolve()
    load_artifact(source)
    model_name = normalize_name(name or source.name)
    target = models_dir() / model_name
    target.parent.mkdir(parents=True, exist_ok=True)
    with _model_transaction(target):
        _recover_interrupted_replacement_locked(target)
        if target.exists() and not force:
            raise FileExistsError(f"model already installed: {model_name}")
    staging = target.parent / f".{model_name}.incoming-{os.getpid()}-{uuid4().hex}"
    backup = _replacement_backup(target)
    replacement_committed = False
    try:
        shutil.copytree(source, staging)
        load_artifact(staging)
        with _model_transaction(target):
            _recover_interrupted_replacement_locked(target)
            if target.exists() and not force:
                raise FileExistsError(f"model already installed: {model_name}")
            shutil.rmtree(backup, ignore_errors=True)
            if target.exists():
                os.replace(target, backup)
            try:
                os.replace(staging, target)
                installed = load_artifact(target)
                replacement_committed = True
            finally:
                if backup.exists():
                    if replacement_committed:
                        shutil.rmtree(backup)
                    else:
                        shutil.rmtree(target, ignore_errors=True)
                        os.replace(backup, target)
                elif target.exists() and not replacement_committed:
                    shutil.rmtree(target)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    config = _read_config()
    models = config.setdefault("models", {})
    if not isinstance(models, dict):
        models = {}
        config["models"] = models
    models[model_name] = {"path": str(target)}
    config["active_model"] = model_name
    _write_config(config)
    return installed


def list_models() -> tuple[InstalledModel, ...]:
    config = _read_config()
    active = config.get("active_model")
    found: dict[str, Path] = {}
    entries = config.get("models")
    if isinstance(entries, dict):
        for name, entry in entries.items():
            if (
                isinstance(name, str)
                and isinstance(entry, dict)
                and isinstance(entry.get("path"), str)
            ):
                found[name] = Path(entry["path"])
    root = models_dir()
    if root.exists():
        for child in root.iterdir():
            if child.is_dir() and not child.name.startswith("."):
                found.setdefault(child.name, child)
    return tuple(
        InstalledModel(name, path, name == active) for name, path in sorted(found.items())
    )


def use_model(name: str) -> InstalledModel:
    model_name = normalize_name(name)
    match = next((item for item in list_models() if item.name == model_name), None)
    if match is None or not match.model_dir.is_dir():
        raise FileNotFoundError(f"installed model not found: {model_name}")
    config = _read_config()
    config["active_model"] = model_name
    _write_config(config)
    return InstalledModel(model_name, match.model_dir, True)


def rename_model(name: str, new_name: str) -> InstalledModel:
    """Rename one managed model in place without copying its weights."""

    model_name = normalize_name(name)
    replacement_name = normalize_name(new_name)
    if replacement_name == model_name:
        raise ValueError("new model name must differ from the current name")
    match = next((item for item in list_models() if item.name == model_name), None)
    if match is None:
        raise FileNotFoundError(f"installed model not found: {model_name}")
    source = models_dir() / model_name
    target = models_dir() / replacement_name
    if Path(os.path.abspath(match.model_dir)) != Path(os.path.abspath(source)):
        raise ValueError(f"refusing to rename model outside {models_dir().resolve()}")
    with _model_transactions(source, target):
        _recover_interrupted_replacement_locked(source)
        _recover_interrupted_replacement_locked(target)
        if not source.is_dir():
            raise FileNotFoundError(f"installed model not found: {model_name}")
        if target.exists():
            raise FileExistsError(f"model already installed: {replacement_name}")
        load_artifact(source)
        config = _read_config()
        entries = config.setdefault("models", {})
        if not isinstance(entries, dict):
            entries = {}
            config["models"] = entries
        if replacement_name in entries:
            raise FileExistsError(f"model already registered: {replacement_name}")
        was_active = config.get("active_model") == model_name
        previous_entry = entries.pop(model_name, None)
        entries[replacement_name] = {"path": str(target)}
        if was_active:
            config["active_model"] = replacement_name
        os.replace(source, target)
        try:
            _write_config(config)
        except BaseException:
            os.replace(target, source)
            if previous_entry is not None:
                entries[model_name] = previous_entry
            entries.pop(replacement_name, None)
            if was_active:
                config["active_model"] = model_name
            raise
    return InstalledModel(replacement_name, target, was_active)


def uninstall_model(name: str) -> InstalledModel:
    model_name = normalize_name(name)
    match = next((item for item in list_models() if item.name == model_name), None)
    if match is None:
        raise FileNotFoundError(f"installed model not found: {model_name}")
    managed = models_dir().resolve()
    target = match.model_dir.expanduser().resolve()
    try:
        target.relative_to(managed)
    except ValueError as exc:
        raise ValueError(f"refusing to remove model outside {managed}") from exc
    shutil.rmtree(target, ignore_errors=False)
    config = _read_config()
    entries = config.get("models")
    if isinstance(entries, dict):
        entries.pop(model_name, None)
    if config.get("active_model") == model_name:
        config.pop("active_model", None)
    _write_config(config)
    return InstalledModel(model_name, target, False)


def normalize_name(name: str) -> str:
    value = name.strip()
    if not _NAME_RE.fullmatch(value):
        raise ValueError("model name may contain letters, digits, '.', '_' and '-'")
    return value


def _config_path() -> Path:
    return config_dir() / "config.json"


def _replacement_backup(target: Path) -> Path:
    return target.parent / f".{target.name}.previous"


def _recover_interrupted_replacement_locked(target: Path) -> None:
    backup = _replacement_backup(target)
    if not backup.exists():
        return
    if not target.exists():
        os.replace(backup, target)
        return
    try:
        load_artifact(target)
    except (OSError, ValueError):
        shutil.rmtree(target, ignore_errors=True)
        os.replace(backup, target)
    else:
        shutil.rmtree(backup)


@contextmanager
def _model_transaction(target: Path) -> Iterator[None]:
    lock_path = target.parent / ".locks" / f"{target.name}.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    key = Path(os.path.abspath(lock_path))
    with _LOCAL_LOCKS_GUARD:
        local_lock = _LOCAL_LOCKS.setdefault(key, threading.Lock())
    with local_lock, lock_path.open("a+") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


@contextmanager
def _model_transactions(*targets: Path) -> Iterator[None]:
    with ExitStack() as stack:
        for target in sorted(set(targets), key=lambda item: str(item)):
            stack.enter_context(_model_transaction(target))
        yield


def _read_config() -> dict[str, Any]:
    path = _config_path()
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"invalid ShellCue config: {path}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"invalid ShellCue config: {path}")
    return payload


def _write_config(payload: Mapping[str, Any]) -> None:
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)
