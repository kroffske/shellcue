from __future__ import annotations

import json
import logging
import sys
from dataclasses import replace
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from shellcue.models import neural
from shellcue.models.artifact import (
    DecodeBudget,
    InferenceConfig,
    SuggestionRequest,
)
from shellcue.models.candidates import GeneratedCandidate
from shellcue.models.prompt_contract import PromptInput, render_prompt
from shellcue.runtime.context import RuntimeContext


class _FakeTorch:
    float16 = "float16"
    bfloat16 = "bfloat16"
    float32 = "float32"

    @staticmethod
    def device(name: str) -> str:
        return name


def inference_config(*, beams: int = 1) -> InferenceConfig:
    return InferenceConfig(
        beams=beams,
        candidate_policy="current_whitespace_heal_v1",
        max_decode_steps=8,
        newline_stop_id=708,
        token_healing=True,
        empty_heal_fallback="no_heal_parse_valid",
        ctx_max=128,
        cmd_max=96,
        per_cmd_chars=160,
        separator="newline",
        healing=True,
    )


@pytest.mark.parametrize(
    "budget",
    [
        {"beams": 0},
        {"beams": -1},
        {"beams": True},
        {"max_decode_steps": 0},
        {"max_decode_steps": False},
    ],
)
def test_decode_budget_rejects_invalid_explicit_values(budget: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        DecodeBudget(**budget)


def test_decode_budget_rejects_unbounded_beam_count() -> None:
    with pytest.raises(ValueError, match="beams must be from 1 to 5"):
        DecodeBudget(beams=6)


@pytest.mark.parametrize("value", ["int8", "", "garbage"])
def test_invalid_neural_dtype_fails_closed(monkeypatch, value: str) -> None:
    monkeypatch.setenv(neural.DTYPE_ENV, value)

    with pytest.raises(ValueError, match="SHELLCUE_NEURAL_DTYPE"):
        neural._resolve_dtype(_FakeTorch)


def test_device_fallback_logs_warning(caplog) -> None:
    class _Model:
        def __init__(self) -> None:
            self.devices: list[str] = []

        def to(self, device: str) -> None:
            self.devices.append(device)
            if device != "cpu":
                raise RuntimeError("backend unavailable")

    model = _Model()
    with caplog.at_level(logging.WARNING, logger="shellcue.models.neural"):
        selected = neural._place_model(model, _FakeTorch, "mps")

    assert selected == "cpu"
    assert model.devices == ["mps", "cpu"]
    assert "using CPU" in caplog.text


def test_generation_uses_artifact_beams_independently_of_display_limit(
    monkeypatch,
) -> None:
    class _NoGrad:
        def __enter__(self) -> None:
            return None

        def __exit__(self, *_args: object) -> None:
            return None

    class _Tensor:
        shape = (1, 1)

    fake_torch = ModuleType("torch")
    fake_torch.long = "long"
    fake_torch.tensor = lambda *_args, **_kwargs: _Tensor()
    fake_torch.ones_like = lambda value: value
    fake_torch.no_grad = _NoGrad
    monkeypatch.setitem(sys.modules, "torch", fake_torch)

    class _Model:
        def __init__(self) -> None:
            self.kwargs: dict[str, object] = {}

        def generate(self, **kwargs: object) -> SimpleNamespace:
            self.kwargs = kwargs
            count = int(kwargs["num_return_sequences"])
            return SimpleNamespace(
                sequences=[[10, index] for index in range(count)],
                sequences_scores=None,
            )

    class _Tokenizer:
        pad_token_id = 0

        @staticmethod
        def decode(tokens: list[int], *, skip_special_tokens: bool) -> str:
            assert skip_special_tokens
            return str(tokens[0])

    model = _Model()
    predictor = neural.NeuralPredictor(
        model,
        _Tokenizer(),
        inference_config(beams=4),
        "cpu",
    )

    generated = predictor._generate([10], inference_config(beams=4))

    assert len(generated) == 4
    assert model.kwargs["num_beams"] == 4
    assert model.kwargs["num_return_sequences"] == 4


def test_predictor_uses_valid_later_model_beam(monkeypatch) -> None:
    predictor = neural.NeuralPredictor(
        object(),
        object(),
        inference_config(beams=2),
        "cpu",
    )
    monkeypatch.setattr(predictor, "_prompt", lambda *_args: ([], " s"))
    monkeypatch.setattr(
        predictor,
        "_generate",
        lambda *_args: (
            GeneratedCandidate(" s; rm -rf /tmp/shellcue-test", -0.1),
            GeneratedCandidate(" status --short", -0.2),
        ),
    )

    result = predictor.suggest(
        SuggestionRequest(source_kind="live_shell", typed_prefix="git s"),
        limit=1,
    )

    assert result[0].command == "git status --short"
    assert result[0].source == "model"


def test_predictor_abstains_when_both_model_passes_are_unsafe(monkeypatch) -> None:
    predictor = neural.NeuralPredictor(
        object(),
        object(),
        inference_config(beams=2),
        "cpu",
    )
    generated_calls = 0
    monkeypatch.setattr(predictor, "_prompt", lambda *_args: ([], " s"))

    def generate(*_args) -> tuple[GeneratedCandidate, ...]:
        nonlocal generated_calls
        generated_calls += 1
        return (GeneratedCandidate(" s; rm -rf /tmp/shellcue-test", -0.1),)

    monkeypatch.setattr(predictor, "_generate", generate)

    result = predictor.suggest(
        SuggestionRequest(source_kind="live_shell", typed_prefix="git s"),
        limit=1,
    )

    assert result == ()
    assert generated_calls == 2


class _CodepointTokenizer:
    """Invertible tokenizer so prompt token ids can be compared as exact bytes."""

    pad_token_id = 0

    def __call__(self, text: str, *, add_special_tokens: bool = True) -> dict[str, list[int]]:
        assert not add_special_tokens
        return {"input_ids": [ord(character) for character in text]}

    @staticmethod
    def decode(ids: list[int], *, skip_special_tokens: bool = True) -> str:
        return "".join(chr(value) for value in ids)


def _served_prompt_text(request: SuggestionRequest, config: InferenceConfig) -> str:
    predictor = neural.NeuralPredictor(object(), _CodepointTokenizer(), config, "cpu")
    prompt_ids, fragment = predictor._prompt(request, config)
    assert fragment == ""
    return "".join(chr(value) for value in prompt_ids)


def test_served_prompt_is_byte_identical_to_the_contract_render() -> None:
    """The whole point of T-112: what we serve must equal what training renders.

    History has three distinguishable entries so a reversal cannot pass, and the
    typed prefix carries a quoted string and a path so any residual masking
    would change the bytes.
    """

    request = SuggestionRequest(
        source_kind="live_shell",
        typed_prefix="git commit -m 'fix /etc/hosts",
        cwd_hint="repo:tooling",
        recent_commands=("git add -A", "git status", "ls -la"),
    )
    config = replace(inference_config(), ctx_max=4096)

    expected = render_prompt(
        PromptInput(
            source_kind=request.source_kind,
            typed_prefix=request.typed_prefix,
            cwd_hint=request.cwd_hint,
            recent_commands=request.recent_commands,
        ),
        encode=lambda text: [ord(character) for character in text],
        max_tokens=config.ctx_max,
    ).text

    assert _served_prompt_text(request, config) == expected
    assert _served_prompt_text(request, config).endswith(
        'typed_prefix: "git commit -m \'fix /etc/hosts"\ncompletion_suffix:'
    )


def test_served_prompt_matches_the_committed_vector_ledger() -> None:
    """Anchor the runtime to the same authority `shellcue-training` verifies."""

    payload = json.loads(
        (Path(__file__).parents[1] / "contracts" / "autocomplete-v2-vectors.json").read_text(
            encoding="utf-8"
        )
    )
    checked = 0
    for vector in payload["vectors"]:
        source = vector["input"]
        budget = int(vector["byte_budget"])
        # The ledger budgets in bytes; only exercise vectors that fit whole.
        if vector["omitted_history_count"]:
            continue
        config = replace(inference_config(), ctx_max=budget)
        request = SuggestionRequest(
            source_kind=source["source_kind"],
            typed_prefix=source["typed_prefix"],
            cwd_hint=source["cwd_hint"],
            recent_commands=tuple(source["recent_commands"]),
        )

        assert _served_prompt_text(request, config) == vector["prompt_text"]
        checked += 1

    assert checked >= 2


def test_served_prompt_preserves_a_trailing_space_in_the_typed_prefix() -> None:
    """`mask_command` collapsed whitespace, so `git ` used to reach the model as `git`."""

    request = SuggestionRequest(source_kind="live_shell", typed_prefix="git ")

    assert _served_prompt_text(request, replace(inference_config(), ctx_max=4096)).endswith(
        'typed_prefix: "git "\ncompletion_suffix:'
    )


def test_predictor_abstains_when_mandatory_fields_exceed_the_budget() -> None:
    """Contract: return `prefix_over_budget`; no alternative predictor is invoked."""

    tiny = replace(inference_config(), ctx_max=8, cmd_max=8)
    predictor = neural.NeuralPredictor(object(), _CodepointTokenizer(), tiny, "cpu")

    result = predictor.suggest(
        SuggestionRequest(source_kind="live_shell", typed_prefix="git " + "x" * 500),
        limit=1,
    )

    assert result == ()


def test_prompt_budget_is_ctx_max_alone_not_the_summed_capacity() -> None:
    """Offline materialization budgets the whole prompt at `prompt_max_tokens`.

    `min(prompt_max_tokens, sequence_max_tokens - generation_reserve)` is 512 at
    the shipped training defaults, which equals the shipped artifact's
    `ctx_max`. Summing in `cmd_max` would retain history here that training
    would have dropped -- the skew this renderer exists to remove.
    """

    config = replace(inference_config(), ctx_max=200, cmd_max=1_000)
    request = SuggestionRequest(
        source_kind="live_shell",
        typed_prefix="git s",
        recent_commands=tuple(f"command-number-{index}" for index in range(8)),
    )

    served = _served_prompt_text(request, config)

    assert len(served) <= 200
    # Proves the budget actually bit: history was dropped, not merely rendered.
    assert "command-number-7" not in served


def test_runtime_has_exactly_one_prompt_serializer() -> None:
    """No second serialization anywhere in the runtime -- the core requirement."""

    source_root = Path(__file__).parents[1] / "src" / "shellcue"
    # Match emission sites (f-string/literal), not prose in docstrings.
    markers = ("prompt_contract: {", "typed_prefix: {", '"completion_suffix:"')
    offenders = sorted(
        path.relative_to(source_root).as_posix()
        for path in source_root.rglob("*.py")
        if path.name != "prompt_contract.py"
        and any(marker in path.read_text(encoding="utf-8") for marker in markers)
    )

    assert offenders == []


def test_captured_context_renders_the_contract_prompt_end_to_end() -> None:
    """Exercise the real RuntimeContext -> SuggestionRequest -> prompt seam.

    Hand-building an already-newest-first request would not prove the runtime
    reverses history exactly once.
    """

    request = RuntimeContext.capture(
        cwd="/Users/someone/projects/tooling",
        recent_commands=["ls -la", "git status", "git add -A"],
    ).request("git commit -m 'fix")

    expected = render_prompt(
        PromptInput(
            source_kind="live_shell",
            typed_prefix="git commit -m 'fix",
            cwd_hint="repo:tooling",
            recent_commands=("git add -A", "git status", "ls -la"),
        ),
        encode=lambda text: [ord(character) for character in text],
        max_tokens=4096,
    ).text

    assert _served_prompt_text(request, replace(inference_config(), ctx_max=4096)) == expected
