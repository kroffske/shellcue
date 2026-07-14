from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest


@pytest.fixture
def model_dir(tmp_path: Path) -> Path:
    root = tmp_path / "alpha-model"
    root.mkdir()
    files: dict[str, bytes] = {
        "model.safetensors": b"weights",
        "config.json": b"{}\n",
        "generation_config.json": b"{}\n",
        "tokenizer.json": b"{}\n",
        "tokenizer_config.json": b"{}\n",
    }
    for name, data in files.items():
        (root / name).write_bytes(data)
    hashes = {
        name: hashlib.sha256(data).hexdigest()
        for name, data in files.items()
    }
    manifest = {
        "schema_version": "shellcue.model.v1",
        "artifact_kind": "neural_causal_lm",
        "runtime_min_version": "0.1.0a1",
        "weights_path": "model.safetensors",
        "weights_format": "safetensors",
        "tokenizer_path": "tokenizer.json",
        "tokenizer_config_path": "tokenizer_config.json",
        "input_fields": ["context_text", "typed_prefix_masked"],
        "file_hashes": hashes,
    }
    inference = {
        "schema_version": "shellcue.inference.v1",
        "decode": {
            "beams": 1,
            "candidate_policy": "current_whitespace_heal_v1",
            "max_decode_steps": 8,
            "newline_stop_id": 708,
            "token_healing": True,
            "empty_heal_fallback": "no_heal_parse_valid",
        },
        "tokenization": {
            "ctx_max": 128,
            "cmd_max": 96,
            "per_cmd_chars": 160,
            "separator": "newline",
            "healing": True,
        },
    }
    (root / "model.json").write_text(json.dumps(manifest), encoding="utf-8")
    (root / "inference_config.json").write_text(json.dumps(inference), encoding="utf-8")
    return root
