"""Typed live context capture with masking before inference."""

from __future__ import annotations

from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from shellcue.core.redaction import mask_command
from shellcue.models.artifact import SuggestionRequest

SOURCE_KIND = "live_shell"
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

    def request(self, typed_prefix: str) -> SuggestionRequest:
        """Bind masked context to the complete typed prefix for the model.

        The prefix is passed through unmasked on purpose. Per
        ``docs/contracts/autocomplete-v2.md`` the contract masks ``cwd_hint``
        and ``recent_commands`` but defines ``typed_prefix`` as the complete
        text visible at the shell prompt.
        """

        return SuggestionRequest(
            source_kind=SOURCE_KIND,
            typed_prefix=typed_prefix,
            cwd_hint=self.cwd_hint or "",
            recent_commands=self.newest_first,
        )

    @property
    def newest_first(self) -> tuple[str, ...]:
        """Masked history ordered newest first, as the prompt contract expects.

        ``recent_commands`` is stored oldest first because both shell hooks
        emit history that way (``builtin history 8`` in Bash, ``fc -ln -8`` in
        Zsh). The contract numbers ``recent_1`` as the newest entry, nearest the
        typed prefix, so the runtime must reverse before rendering.
        """

        return tuple(reversed(self.recent_commands))


def _cwd_hint(cwd: str | None) -> str | None:
    text = (cwd or "").strip()
    if not text:
        return None
    name = text.removeprefix("repo:").strip() if text.startswith("repo:") else Path(text).name
    masked = mask_command(name).replace("\n", " ")[:MAX_CWD_CHARS]
    return f"repo:{masked}" if masked else None
