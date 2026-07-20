"""Versioned, runtime-only model artifact contract."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from shellcue import __version__

MANIFEST_SCHEMA = "shellcue.model.v1"
INFERENCE_SCHEMA = "shellcue.inference.v1"
MODEL_JSON = "model.json"
INFERENCE_CONFIG_JSON = "inference_config.json"
REQUIRED_HF_FILES = (
    "config.json",
    "generation_config.json",
    "tokenizer.json",
    "tokenizer_config.json",
)
_MANIFEST_FIELDS = {
    "schema_version",
    "artifact_kind",
    "runtime_min_version",
    "weights_path",
    "weights_format",
    "tokenizer_path",
    "tokenizer_config_path",
    "input_fields",
    "file_hashes",
}
_INFERENCE_FIELDS = {"schema_version", "decode", "tokenization"}
_DECODE_FIELDS = {
    "beams",
    "candidate_policy",
    "max_decode_steps",
    "newline_stop_id",
    "token_healing",
    "empty_heal_fallback",
}
_TOKENIZATION_FIELDS = {"ctx_max", "cmd_max", "per_cmd_chars", "separator", "healing"}
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
MAX_GENERATION_BEAMS = 5
# The v2 prompt contract's input vocabulary (docs/contracts/autocomplete-v2.md).
CONTRACT_INPUT_FIELDS = ("source_kind", "cwd_hint", "recent_commands", "typed_prefix")
# Pre-v2 artifacts declare this literal. It never described a trained shape: the
# exporter emitted it verbatim because this verifier demanded it, so it carries
# no information and is accepted only so existing artifacts keep loading.
LEGACY_INPUT_FIELDS = ("context_text", "typed_prefix_masked")


class ArtifactError(ValueError):
    """A model directory violates the public inference contract."""


@dataclass(frozen=True)
class ModelManifest:
    runtime_min_version: str
    weights_path: str
    weights_format: str
    tokenizer_path: str
    tokenizer_config_path: str
    input_fields: tuple[str, ...]
    file_hashes: Mapping[str, str]

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> ModelManifest:
        _reject_unknown(payload, _MANIFEST_FIELDS, MODEL_JSON)
        if payload.get("schema_version") != MANIFEST_SCHEMA:
            raise ArtifactError(f"model.json schema_version must be {MANIFEST_SCHEMA!r}")
        if payload.get("artifact_kind") != "neural_causal_lm":
            raise ArtifactError("model.json artifact_kind must be 'neural_causal_lm'")
        weights_format = _required_str(payload, "weights_format")
        if weights_format not in {"safetensors", "torch_state_dict"}:
            raise ArtifactError("weights_format must be safetensors or torch_state_dict")
        input_fields = payload.get("input_fields")
        if input_fields not in (list(CONTRACT_INPUT_FIELDS), list(LEGACY_INPUT_FIELDS)):
            raise ArtifactError(
                f"input_fields must be {list(CONTRACT_INPUT_FIELDS)}"
                f" or the legacy {list(LEGACY_INPUT_FIELDS)}"
            )
        hashes = payload.get("file_hashes")
        if not isinstance(hashes, dict) or not hashes:
            raise ArtifactError("file_hashes must be a non-empty object")
        validated_hashes: dict[str, str] = {}
        for raw_path, digest in hashes.items():
            path = _relative_path(raw_path, "file_hashes key")
            if not isinstance(digest, str) or not _SHA256_RE.fullmatch(digest):
                raise ArtifactError(f"file_hashes[{path!r}] must be a lowercase SHA-256")
            validated_hashes[path] = digest
        manifest = cls(
            runtime_min_version=_required_str(payload, "runtime_min_version"),
            weights_path=_relative_path(payload.get("weights_path"), "weights_path"),
            weights_format=weights_format,
            tokenizer_path=_relative_path(payload.get("tokenizer_path"), "tokenizer_path"),
            tokenizer_config_path=_relative_path(
                payload.get("tokenizer_config_path"), "tokenizer_config_path"
            ),
            input_fields=tuple(input_fields),
            file_hashes=validated_hashes,
        )
        if _version_key(manifest.runtime_min_version) > _version_key(__version__):
            raise ArtifactError(
                f"model requires shellcue>={manifest.runtime_min_version}; current {__version__}"
            )
        if manifest.weights_path not in manifest.file_hashes:
            raise ArtifactError("file_hashes must include weights_path")
        return manifest

    @property
    def required_files(self) -> tuple[str, ...]:
        return (
            MODEL_JSON,
            INFERENCE_CONFIG_JSON,
            self.weights_path,
            self.tokenizer_path,
            self.tokenizer_config_path,
            *REQUIRED_HF_FILES,
        )


@dataclass(frozen=True)
class InferenceConfig:
    beams: int
    candidate_policy: str
    max_decode_steps: int
    newline_stop_id: int | None
    token_healing: bool
    empty_heal_fallback: str
    ctx_max: int
    cmd_max: int
    per_cmd_chars: int
    separator: str
    healing: bool

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> InferenceConfig:
        _reject_unknown(payload, _INFERENCE_FIELDS, INFERENCE_CONFIG_JSON)
        if payload.get("schema_version") != INFERENCE_SCHEMA:
            raise ArtifactError(
                f"inference_config.json schema_version must be {INFERENCE_SCHEMA!r}"
            )
        decode = _required_object(payload, "decode")
        tokenization = _required_object(payload, "tokenization")
        _reject_unknown(decode, _DECODE_FIELDS, "inference_config.json decode")
        _reject_unknown(tokenization, _TOKENIZATION_FIELDS, "inference_config.json tokenization")
        newline_stop_id = decode.get("newline_stop_id")
        if newline_stop_id is not None and not _is_int(newline_stop_id):
            raise ArtifactError("decode.newline_stop_id must be an integer or null")
        fallback = _required_str(decode, "empty_heal_fallback")
        if fallback not in {"none", "no_heal_parse_valid"}:
            raise ArtifactError("decode.empty_heal_fallback is unsupported")
        candidate_policy = _required_str(decode, "candidate_policy")
        if candidate_policy != "current_whitespace_heal_v1":
            raise ArtifactError("decode.candidate_policy must be 'current_whitespace_heal_v1'")
        separator = _required_str(tokenization, "separator")
        if separator != "newline":
            raise ArtifactError("tokenization.separator must be 'newline'")
        config = cls(
            beams=_positive_int(decode, "beams"),
            candidate_policy=candidate_policy,
            max_decode_steps=_positive_int(decode, "max_decode_steps"),
            newline_stop_id=newline_stop_id,
            token_healing=_required_bool(decode, "token_healing"),
            empty_heal_fallback=fallback,
            ctx_max=_positive_int(tokenization, "ctx_max"),
            cmd_max=_positive_int(tokenization, "cmd_max"),
            per_cmd_chars=_positive_int(tokenization, "per_cmd_chars"),
            separator=separator,
            healing=_required_bool(tokenization, "healing"),
        )
        if config.healing != config.token_healing:
            raise ArtifactError("decode.token_healing and tokenization.healing must match")
        if config.beams > MAX_GENERATION_BEAMS:
            raise ArtifactError(f"decode.beams must be from 1 to {MAX_GENERATION_BEAMS}")
        return config


@dataclass(frozen=True)
class LoadedArtifact:
    model_dir: Path
    manifest: ModelManifest
    inference: InferenceConfig


@dataclass(frozen=True)
class SuggestionRequest:
    """Structured v2 prompt-contract input, never a pre-rendered prompt.

    Fields mirror ``docs/contracts/autocomplete-v2.md``. ``cwd_hint`` and
    ``recent_commands`` arrive already masked from ``RuntimeContext``;
    ``typed_prefix`` is the complete text visible at the shell prompt and is
    never masked or truncated. ``recent_commands`` is ordered newest first.
    """

    source_kind: str
    typed_prefix: str
    cwd_hint: str = ""
    recent_commands: tuple[str, ...] = ()


@dataclass(frozen=True)
class DecodeBudget:
    beams: int | None = None
    max_decode_steps: int | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("beams", self.beams),
            ("max_decode_steps", self.max_decode_steps),
        ):
            if value is not None and (not _is_int(value) or value < 1):
                raise ValueError(f"DecodeBudget.{name} must be a positive integer or None")
        if self.beams is not None and self.beams > MAX_GENERATION_BEAMS:
            raise ValueError(f"DecodeBudget.beams must be from 1 to {MAX_GENERATION_BEAMS}")


@dataclass(frozen=True)
class Suggestion:
    suffix: str
    command: str
    score: float
    source: str = "model"


def load_artifact(model_dir: Path) -> LoadedArtifact:
    """Validate every required local file and return typed runtime metadata."""

    root = model_dir.expanduser().resolve()
    if not root.is_dir():
        raise ArtifactError(f"model directory not found: {root}")
    if (root / "training_config.json").exists():
        raise ArtifactError("training_config.json is forbidden in a ShellCue model")
    manifest = ModelManifest.from_mapping(_read_object(root / MODEL_JSON))
    missing = sorted(name for name in set(manifest.required_files) if not (root / name).is_file())
    if missing:
        raise ArtifactError(f"model is missing required files: {', '.join(missing)}")
    inference = InferenceConfig.from_mapping(_read_object(root / INFERENCE_CONFIG_JSON))
    _validate_hashes(root, manifest.file_hashes)
    return LoadedArtifact(model_dir=root, manifest=manifest, inference=inference)


def _validate_hashes(root: Path, hashes: Mapping[str, str]) -> None:
    for relative_path, expected in hashes.items():
        path = root / relative_path
        if not path.is_file():
            raise ArtifactError(f"file_hashes references missing file: {relative_path}")
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        actual = digest.hexdigest()
        if actual != expected:
            raise ArtifactError(f"SHA-256 mismatch: {relative_path}")


def _read_object(path: Path) -> Mapping[str, Any]:
    if not path.is_file():
        raise ArtifactError(f"required file is missing: {path.name}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ArtifactError(f"{path.name} must be readable valid JSON") from exc
    if not isinstance(payload, dict):
        raise ArtifactError(f"{path.name} must contain a JSON object")
    return payload


def _reject_unknown(payload: Mapping[str, Any], allowed: set[str], owner: str) -> None:
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise ArtifactError(f"{owner} contains unsupported fields: {', '.join(unknown)}")


def _required_object(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise ArtifactError(f"{key} must be an object")
    return value


def _required_str(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ArtifactError(f"{key} is required")
    return value


def _required_bool(payload: Mapping[str, Any], key: str) -> bool:
    value = payload.get(key)
    if not isinstance(value, bool):
        raise ArtifactError(f"{key} must be a boolean")
    return value


def _positive_int(payload: Mapping[str, Any], key: str) -> int:
    value = payload.get(key)
    if not _is_int(value) or value < 1:
        raise ArtifactError(f"{key} must be a positive integer")
    return value


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _relative_path(value: object, key: str) -> str:
    if not isinstance(value, str) or not value:
        raise ArtifactError(f"{key} is required")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or value != path.as_posix():
        raise ArtifactError(f"{key} must be a normalized relative path")
    return value


def _version_key(value: str) -> tuple[int, int, int, int, int]:
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)(?:(a|b|rc)(\d+))?", value.strip())
    if match is None:
        raise ArtifactError(f"unsupported runtime version: {value!r}")
    major, minor, patch = (int(match.group(index)) for index in range(1, 4))
    stage = match.group(4)
    stage_rank = {"a": 0, "b": 1, "rc": 2, None: 3}[stage]
    stage_number = int(match.group(5)) if stage is not None else 0
    return major, minor, patch, stage_rank, stage_number
