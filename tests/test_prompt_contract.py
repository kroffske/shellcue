from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from shellcue.models.prompt_contract import (
    PROMPT_CONTRACT,
    VECTOR_SCHEMA,
    PromptContractError,
    PromptInput,
    completion_suffix,
    render_prompt,
)

ROOT = Path(__file__).parents[1]
VECTORS = ROOT / "contracts" / "autocomplete-v2-vectors.json"


def byte_encoder(value: str) -> tuple[int, ...]:
    return tuple(value.encode("utf-8"))


def test_prompt_keeps_complete_prefix_and_orders_newest_history_near_it() -> None:
    rendered = render_prompt(
        PromptInput(
            source_kind="live_shell",
            cwd_hint="repo:shellcue",
            recent_commands=("git status", "ls -la"),
            typed_prefix="git st",
        ),
        encode=byte_encoder,
        max_tokens=1_024,
    )

    assert f'prompt_contract: "{PROMPT_CONTRACT}"' in rendered.text
    assert 'recent_2: "ls -la"' in rendered.text
    assert 'recent_1: "git status"' in rendered.text
    assert rendered.text.endswith('typed_prefix: "git st"\ncompletion_suffix:')
    assert completion_suffix("git st", "git status") == "atus"


def test_prompt_drops_oldest_whole_fields_without_truncating_prefix() -> None:
    value = PromptInput(
        source_kind="live_shell",
        recent_commands=("git status", "x" * 200),
        typed_prefix="git st",
    )
    one_history = render_prompt(value, encode=byte_encoder, max_tokens=10_000)
    max_tokens = len(byte_encoder(one_history.text)) - 200
    rendered = render_prompt(value, encode=byte_encoder, max_tokens=max_tokens)

    assert 'recent_1: "git status"' in rendered.text
    assert "x" * 10 not in rendered.text
    assert rendered.omitted_history_count == 1
    assert 'typed_prefix: "git st"' in rendered.text


def test_over_budget_prefix_fails_instead_of_truncating() -> None:
    with pytest.raises(PromptContractError, match="prefix_over_budget"):
        render_prompt(
            PromptInput(source_kind="live_shell", typed_prefix="git " + "x" * 500),
            encode=byte_encoder,
            max_tokens=20,
        )


def test_completion_suffix_rejects_unrelated_command() -> None:
    with pytest.raises(PromptContractError, match="must start"):
        completion_suffix("git st", "sudo apt-get install git")


def test_committed_vectors_match_canonical_prompt_bytes() -> None:
    payload = json.loads(VECTORS.read_text(encoding="utf-8"))

    assert payload["schema"] == VECTOR_SCHEMA
    for vector in payload["vectors"]:
        rendered = render_prompt(
            PromptInput(
                source_kind=vector["input"]["source_kind"],
                cwd_hint=vector["input"]["cwd_hint"],
                recent_commands=tuple(vector["input"]["recent_commands"]),
                typed_prefix=vector["input"]["typed_prefix"],
            ),
            encode=byte_encoder,
            max_tokens=vector["byte_budget"],
        )
        assert rendered.text == vector["prompt_text"]
        assert hashlib.sha256(rendered.text.encode()).hexdigest() == vector["prompt_utf8_sha256"]
        assert rendered.retained_fields == tuple(vector["retained_fields"])
        assert rendered.omitted_history_count == vector["omitted_history_count"]
        assert completion_suffix(
            vector["input"]["typed_prefix"], vector["expected_command"]
        ) == vector["target_suffix"]
