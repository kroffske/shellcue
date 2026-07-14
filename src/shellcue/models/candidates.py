"""Deterministic filtering for raw neural continuations."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from shellcue.core.safety import candidate_is_safe
from shellcue.models.artifact import Suggestion


@dataclass(frozen=True)
class GeneratedCandidate:
    text: str
    score: float


def safe_suggestions(
    prefix: str,
    generated: Iterable[GeneratedCandidate],
    *,
    typed_fragment: str = "",
    limit: int = 5,
) -> tuple[Suggestion, ...]:
    """Keep ordered, unique, fragment-compatible, safe suffixes."""

    if limit < 1:
        return ()
    suggestions: list[Suggestion] = []
    seen: set[str] = set()
    for candidate in generated:
        if typed_fragment and not candidate.text.startswith(typed_fragment):
            continue
        suffix = candidate.text[len(typed_fragment) :]
        if suffix in seen or not candidate_is_safe(prefix, suffix):
            continue
        seen.add(suffix)
        suggestions.append(
            Suggestion(suffix=suffix, command=prefix + suffix, score=float(candidate.score))
        )
        if len(suggestions) >= limit:
            break
    return tuple(suggestions)
