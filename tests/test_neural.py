from __future__ import annotations

import logging
import sys
from types import ModuleType, SimpleNamespace

import pytest

from shellcue.models import neural
from shellcue.models.artifact import (
    DecodeBudget,
    InferenceConfig,
    SuggestionRequest,
)
from shellcue.models.candidates import GeneratedCandidate


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


def test_policy_considers_valid_later_beam_before_catalog_fallback(monkeypatch) -> None:
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
            GeneratedCandidate(" sudo apt-get install git", -0.1),
            GeneratedCandidate(" status --short", -0.2),
        ),
    )

    result = predictor.suggest(
        SuggestionRequest(context_text="", typed_prefix_masked="git s"),
        limit=1,
    )

    assert result[0].command == "git status --short"
