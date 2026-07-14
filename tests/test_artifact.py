from __future__ import annotations

import json
from pathlib import Path

import pytest

from shellcue.models.artifact import ArtifactError, _version_key, load_artifact


def test_runtime_artifact_loads_from_inference_config_only(model_dir: Path) -> None:
    loaded = load_artifact(model_dir)

    assert loaded.inference.beams == 1
    assert loaded.inference.candidate_policy == "current_whitespace_heal_v1"
    assert loaded.inference.ctx_max == 128
    assert not (model_dir / "training_config.json").exists()


def test_missing_inference_config_fails_closed(model_dir: Path) -> None:
    (model_dir / "inference_config.json").unlink()

    with pytest.raises(ArtifactError, match="missing required files"):
        load_artifact(model_dir)


def test_unknown_inference_field_fails_closed(model_dir: Path) -> None:
    path = model_dir / "inference_config.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["decode"]["learning_rate"] = 0.1
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ArtifactError, match="unsupported fields: learning_rate"):
        load_artifact(model_dir)


def test_unknown_candidate_policy_fails_closed(model_dir: Path) -> None:
    path = model_dir / "inference_config.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["decode"]["candidate_policy"] = "future_policy_v2"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ArtifactError, match="candidate_policy"):
        load_artifact(model_dir)


def test_training_config_is_rejected_not_loaded(model_dir: Path) -> None:
    (model_dir / "training_config.json").write_text("{}", encoding="utf-8")

    with pytest.raises(ArtifactError, match="forbidden"):
        load_artifact(model_dir)


def test_hash_mismatch_fails_closed(model_dir: Path) -> None:
    (model_dir / "model.safetensors").write_bytes(b"changed")

    with pytest.raises(ArtifactError, match="SHA-256 mismatch"):
        load_artifact(model_dir)


def test_model_manifest_rejects_path_traversal(model_dir: Path) -> None:
    path = model_dir / "model.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["weights_path"] = "../model.safetensors"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ArtifactError, match="normalized relative path"):
        load_artifact(model_dir)


def test_runtime_version_order_is_prerelease_aware() -> None:
    assert _version_key("0.1.0a1") < _version_key("0.1.0rc1") < _version_key("0.1.0")
    assert _version_key("0.1.0a2") < _version_key("0.1.0b1")


def test_model_requiring_release_candidate_is_rejected_by_alpha_runtime(
    model_dir: Path,
) -> None:
    path = model_dir / "model.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["runtime_min_version"] = "0.1.0rc1"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ArtifactError, match=r"requires shellcue>=0\.1\.0rc1"):
        load_artifact(model_dir)


def test_hash_validation_streams_files(model_dir: Path, monkeypatch) -> None:
    def forbidden_read_bytes(_path: Path) -> bytes:
        raise AssertionError("hash validation must not load a full file into memory")

    monkeypatch.setattr(Path, "read_bytes", forbidden_read_bytes)

    assert load_artifact(model_dir).model_dir == model_dir
