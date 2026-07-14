from __future__ import annotations

import pytest

from shellcue.models.neural import _pack_context
from shellcue.runtime.context import RuntimeContext


def test_live_context_masks_secrets_paths_and_identity() -> None:
    context = RuntimeContext.capture(
        cwd="/Users/private-name/projects/secret-repo",
        recent_commands=[
            "curl https://secret.example/a",
            "export API_TOKEN=abcdefghijklmnopqrstuvwxyz0123456789",
            "cat /Users/private-name/.ssh/id_rsa",
        ],
    ).render()

    assert "private-name" not in context
    assert "secret.example" not in context
    assert "abcdefghijklmnopqrstuvwxyz" not in context
    assert "<URL>" in context
    assert "<SECRET>" in context
    assert "<PATH>" in context
    assert "cwd_hint: repo:secret-repo" in context


def test_live_context_accepts_exactly_eight_commands() -> None:
    context = RuntimeContext.capture(
        cwd=None, recent_commands=[f"echo {index}" for index in range(8)]
    )

    assert len(context.recent_commands) == 8
    assert context.recent_commands[0] == "echo 0"


def test_packed_context_places_newest_command_nearest_generation_cursor() -> None:
    rendered = RuntimeContext.capture(
        cwd="/work/repo", recent_commands=["echo oldest", "git status", "echo newest"]
    ).render()

    packed = _pack_context(rendered, per_command_chars=160)

    assert packed.splitlines()[-1] == "recent_1: echo newest"
    assert packed.index("recent_3: echo oldest") < packed.index("recent_1: echo newest")


@pytest.mark.parametrize(
    "recent",
    [[""], ["   "], [f"echo {index}" for index in range(9)]],
)
def test_runtime_context_rejects_invalid_entries_without_filtering(recent: list[str]) -> None:
    with pytest.raises(ValueError, match="recent context"):
        RuntimeContext.capture(cwd=None, recent_commands=recent)
