from __future__ import annotations

import hashlib
import json
import shutil
import threading
from pathlib import Path

import pytest

from shellcue.models import registry
from shellcue.models.registry import (
    active_model_dir,
    install_model,
    list_models,
    uninstall_model,
    use_model,
)


def test_registry_install_list_use_and_uninstall(
    model_dir: Path, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("SHELLCUE_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("SHELLCUE_CONFIG_DIR", str(tmp_path / "config"))

    installed = install_model(model_dir, name="alpha")

    assert installed.model_dir.name == "alpha"
    assert active_model_dir() == installed.model_dir
    assert list_models()[0].active
    assert use_model("alpha").active
    removed = uninstall_model("alpha")
    assert removed.name == "alpha"
    assert not removed.model_dir.exists()
    assert active_model_dir() is None


def test_registry_never_modifies_source(model_dir: Path, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SHELLCUE_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("SHELLCUE_CONFIG_DIR", str(tmp_path / "config"))
    before = sorted(path.name for path in model_dir.iterdir())

    install_model(model_dir, name="copy")

    assert sorted(path.name for path in model_dir.iterdir()) == before


def test_force_install_swap_failure_preserves_previous_model(
    model_dir: Path, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("SHELLCUE_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("SHELLCUE_CONFIG_DIR", str(tmp_path / "config"))
    installed = install_model(model_dir, name="alpha")
    old_weights = (installed.model_dir / "model.safetensors").read_bytes()
    replacement = tmp_path / "replacement"
    shutil.copytree(model_dir, replacement)
    new_weights = b"replacement-weights"
    (replacement / "model.safetensors").write_bytes(new_weights)
    manifest_path = replacement / "model.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["file_hashes"]["model.safetensors"] = hashlib.sha256(new_weights).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    original_replace = registry.os.replace

    def fail_new_target(source: Path, target: Path) -> None:
        if Path(source).name.startswith(".alpha.incoming"):
            raise OSError("simulated interrupted swap")
        original_replace(source, target)

    monkeypatch.setattr(registry.os, "replace", fail_new_target)

    with pytest.raises(OSError, match="interrupted swap"):
        install_model(replacement, name="alpha", force=True)

    assert (installed.model_dir / "model.safetensors").read_bytes() == old_weights
    assert not registry._replacement_backup(installed.model_dir).exists()


def test_active_model_recovers_interrupted_force_swap(
    model_dir: Path, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("SHELLCUE_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("SHELLCUE_CONFIG_DIR", str(tmp_path / "config"))
    installed = install_model(model_dir, name="alpha")
    backup = registry._replacement_backup(installed.model_dir)
    registry.os.replace(installed.model_dir, backup)

    recovered = active_model_dir()

    assert recovered == installed.model_dir
    assert recovered.is_dir()
    assert not backup.exists()


def test_active_resolution_waits_for_force_swap_transaction(
    model_dir: Path, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("SHELLCUE_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("SHELLCUE_CONFIG_DIR", str(tmp_path / "config"))
    installed = install_model(model_dir, name="alpha")
    replacement = _replacement_model(model_dir, tmp_path / "replacement-concurrent")
    backup = registry._replacement_backup(installed.model_dir)
    moved_old = threading.Event()
    release_swap = threading.Event()
    resolution_done = threading.Event()
    errors: list[Exception] = []
    resolved: list[Path | None] = []
    original_replace = registry.os.replace

    def pause_after_old_move(source: Path, target: Path) -> None:
        original_replace(source, target)
        if Path(source) == installed.model_dir and Path(target) == backup:
            moved_old.set()
            if not release_swap.wait(timeout=2):
                raise TimeoutError("test did not release model swap")

    def replace_model() -> None:
        try:
            install_model(replacement, name="alpha", force=True)
        except Exception as exc:  # test thread must return evidence to the main thread
            errors.append(exc)

    def resolve_model() -> None:
        try:
            resolved.append(active_model_dir())
        except Exception as exc:  # test thread must return evidence to the main thread
            errors.append(exc)
        finally:
            resolution_done.set()

    monkeypatch.setattr(registry.os, "replace", pause_after_old_move)
    installer = threading.Thread(target=replace_model)
    installer.start()
    assert moved_old.wait(timeout=2)
    resolver = threading.Thread(target=resolve_model)
    resolver.start()

    assert not resolution_done.wait(timeout=0.1)
    release_swap.set()
    installer.join(timeout=2)
    resolver.join(timeout=2)

    assert errors == []
    assert resolved == [installed.model_dir]
    assert (installed.model_dir / "model.safetensors").read_bytes() == b"replacement-weights"
    assert not backup.exists()


def test_configured_external_path_never_triggers_recovery(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("SHELLCUE_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("SHELLCUE_CONFIG_DIR", str(tmp_path / "config"))
    external = tmp_path / "external" / "alpha"
    backup = registry._replacement_backup(external)
    backup.mkdir(parents=True)
    registry._write_config(
        {
            "active_model": "alpha",
            "models": {"alpha": {"path": str(external)}},
        }
    )

    with pytest.raises(RuntimeError, match="outside the managed registry"):
        active_model_dir()

    assert backup.is_dir()
    assert not external.exists()


def test_explicit_external_model_path_has_no_recovery_side_effect(
    tmp_path: Path, monkeypatch
) -> None:
    external = tmp_path / "explicit" / "alpha"
    backup = registry._replacement_backup(external)
    backup.mkdir(parents=True)
    monkeypatch.setenv("SHELLCUE_MODEL_DIR", str(external))

    assert active_model_dir() == external
    assert backup.is_dir()
    assert not external.exists()


def _replacement_model(source: Path, target: Path) -> Path:
    shutil.copytree(source, target)
    weights = b"replacement-weights"
    (target / "model.safetensors").write_bytes(weights)
    manifest_path = target / "model.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["file_hashes"]["model.safetensors"] = hashlib.sha256(weights).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return target
