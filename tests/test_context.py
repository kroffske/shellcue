from __future__ import annotations

import pytest

from shellcue.models.prompt_contract import PromptInput, render_prompt
from shellcue.runtime.context import RuntimeContext


def test_live_context_masks_secrets_paths_and_identity() -> None:
    request = RuntimeContext.capture(
        cwd="/Users/private-name/projects/secret-repo",
        recent_commands=[
            "curl https://secret.example/a",
            "export API_TOKEN=abcdefghijklmnopqrstuvwxyz0123456789",
            "cat /Users/private-name/.ssh/id_rsa",
        ],
    ).request("git s")
    context = "\n".join((request.cwd_hint, *request.recent_commands))

    assert "private-name" not in context
    assert "secret.example" not in context
    assert "abcdefghijklmnopqrstuvwxyz" not in context
    assert "<URL>" in context
    assert "<SECRET>" in context
    assert "<PATH>" in context
    assert request.cwd_hint == "repo:secret-repo"


def test_live_context_accepts_exactly_eight_commands() -> None:
    context = RuntimeContext.capture(
        cwd=None, recent_commands=[f"echo {index}" for index in range(8)]
    )

    assert len(context.recent_commands) == 8
    assert context.recent_commands[0] == "echo 0"


def test_context_places_newest_command_nearest_generation_cursor() -> None:
    """Same intent as the pre-v2 `_pack_context` test, now on the contract render.

    Shell hooks emit history oldest-first, so `recent_commands` is stored that
    way; the contract numbers `recent_1` as the newest and places it nearest the
    typed prefix. This pins that the runtime reverses exactly once.
    """

    request = RuntimeContext.capture(
        cwd="/work/repo", recent_commands=["echo oldest", "git status", "echo newest"]
    ).request("git s")

    assert request.recent_commands == ("echo newest", "git status", "echo oldest")

    rendered = render_prompt(
        PromptInput(
            source_kind=request.source_kind,
            typed_prefix=request.typed_prefix,
            cwd_hint=request.cwd_hint,
            recent_commands=request.recent_commands,
        ),
        encode=lambda text: list(text.encode("utf-8")),
        max_tokens=4096,
    ).text

    assert rendered.index('recent_3: "echo oldest"') < rendered.index('recent_1: "echo newest"')
    assert rendered.index('recent_1: "echo newest"') < rendered.index('typed_prefix: "git s"')


@pytest.mark.parametrize(
    "recent",
    [[""], ["   "], [f"echo {index}" for index in range(9)]],
)
def test_runtime_context_rejects_invalid_entries_without_filtering(recent: list[str]) -> None:
    with pytest.raises(ValueError, match="recent context"):
        RuntimeContext.capture(cwd=None, recent_commands=recent)
