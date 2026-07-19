"""Versioned prompt contract shared with offline ShellCue training."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass

PROMPT_CONTRACT = "shellcue.autocomplete.v2"
TARGET_CONTRACT = "shellcue.completion_suffix.v1"
VECTOR_SCHEMA = "shellcue.prompt_vectors.v1"

TokenEncoder = Callable[[str], Sequence[int]]


class PromptContractError(ValueError):
    """Structured prompt input cannot satisfy the public contract."""


@dataclass(frozen=True)
class PromptInput:
    source_kind: str
    typed_prefix: str
    cwd_hint: str = ""
    recent_commands: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.source_kind:
            raise PromptContractError("source_kind must not be empty")
        if "\x00" in self.typed_prefix:
            raise PromptContractError("typed_prefix must not contain NUL")
        if any("\x00" in value for value in (self.cwd_hint, *self.recent_commands)):
            raise PromptContractError("context fields must not contain NUL")


@dataclass(frozen=True)
class RenderedPrompt:
    text: str
    token_ids: tuple[int, ...]
    retained_fields: tuple[str, ...]
    omitted_history_count: int

    @property
    def utf8_sha256(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()


def completion_suffix(typed_prefix: str, command: str) -> str:
    """Return only the visible continuation after ``typed_prefix``."""

    if not command.startswith(typed_prefix):
        raise PromptContractError("command must start with typed_prefix")
    return command[len(typed_prefix) :]


def render_prompt(
    value: PromptInput,
    *,
    encode: TokenEncoder,
    max_tokens: int,
) -> RenderedPrompt:
    """Render complete prefix plus the newest whole history fields that fit."""

    if max_tokens < 1:
        raise PromptContractError("max_tokens must be positive")
    selected: list[str] = []
    mandatory = _render(value, selected)
    mandatory_ids = tuple(int(item) for item in encode(mandatory))
    if len(mandatory_ids) > max_tokens:
        raise PromptContractError("prefix_over_budget")

    for command in value.recent_commands:
        candidate = [*selected, command]
        if len(tuple(encode(_render(value, candidate)))) > max_tokens:
            break
        selected = candidate

    text = _render(value, selected)
    token_ids = tuple(int(item) for item in encode(text))
    retained = ["prompt_contract", "source_kind"]
    if value.cwd_hint:
        retained.append("cwd_hint")
    retained.extend(f"recent_{index}" for index in range(len(selected), 0, -1))
    retained.extend(("typed_prefix", "completion_suffix"))
    return RenderedPrompt(
        text=text,
        token_ids=token_ids,
        retained_fields=tuple(retained),
        omitted_history_count=len(value.recent_commands) - len(selected),
    )


def _render(value: PromptInput, selected_newest_first: Sequence[str]) -> str:
    lines = [
        f"prompt_contract: {_json_string(PROMPT_CONTRACT)}",
        f"source_kind: {_json_string(value.source_kind)}",
    ]
    if value.cwd_hint:
        lines.append(f"cwd_hint: {_json_string(value.cwd_hint)}")
    count = len(selected_newest_first)
    lines.extend(
        f"recent_{count - offset}: {_json_string(command)}"
        for offset, command in enumerate(reversed(selected_newest_first))
    )
    lines.extend(
        (
            f"typed_prefix: {_json_string(value.typed_prefix)}",
            "completion_suffix:",
        )
    )
    return "\n".join(lines)


def _json_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
