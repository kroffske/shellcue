"""Typed live context capture with masking before inference."""

from __future__ import annotations

from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from shellcue.core.redaction import mask_command

MAX_HISTORY = 8
MAX_COMMAND_CHARS = 160
MAX_CWD_CHARS = 80
MAX_INPUT_COMMAND_CHARS = 4096


@dataclass(frozen=True)
class RuntimeContext:
    """Masked request-time context retained only in memory."""

    cwd_hint: str | None
    recent_commands: tuple[str, ...]

    @classmethod
    def capture(cls, *, cwd: str | None, recent_commands: Sequence[str]) -> RuntimeContext:
        if len(recent_commands) > MAX_HISTORY:
            raise ValueError(f"recent context may contain at most {MAX_HISTORY} entries")
        retained: deque[str] = deque(maxlen=MAX_HISTORY)
        for command in recent_commands:
            if (
                not isinstance(command, str)
                or not command.strip()
                or len(command) > MAX_INPUT_COMMAND_CHARS
            ):
                raise ValueError("each recent context entry must be a non-empty bounded string")
            retained.append(mask_command(command)[:MAX_COMMAND_CHARS])
        return cls(cwd_hint=_cwd_hint(cwd), recent_commands=tuple(retained))

    def render(self) -> str:
        lines = ["source_kind: live_shell"]
        if self.cwd_hint:
            lines.append(f"cwd_hint: {self.cwd_hint}")
        for index, command in enumerate(reversed(self.recent_commands), start=1):
            lines.append(f"recent_{index}: {command}")
        return "\n".join(lines)


def _cwd_hint(cwd: str | None) -> str | None:
    text = (cwd or "").strip()
    if not text:
        return None
    name = text.removeprefix("repo:").strip() if text.startswith("repo:") else Path(text).name
    masked = mask_command(name).replace("\n", " ")[:MAX_CWD_CHARS]
    return f"repo:{masked}" if masked else None
