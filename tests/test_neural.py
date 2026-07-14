from __future__ import annotations

import logging

import pytest

from shellcue.models import neural
from shellcue.models.artifact import DecodeBudget


class _FakeTorch:
    float16 = "float16"
    bfloat16 = "bfloat16"
    float32 = "float32"

    @staticmethod
    def device(name: str) -> str:
        return name


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
