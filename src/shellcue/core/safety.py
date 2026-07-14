"""Fail-closed shell candidate safety policy."""

from __future__ import annotations

import re
import shlex

UNSAFE_RE = re.compile(
    r"(?i)(?:^|[\s;&|(`/])(?:rm\s+-(?:[a-z]*r[a-z]*f|[a-z]*f[a-z]*r)|sudo\s+rm|"
    r"mkfs|dd\s+if=|chmod\s+(?:777|-R)|chown\s+-R|kill\s+-9|"
    r"curl\s+[^|;]+[|]\s*(?:sh|bash))"
)
DANGEROUS_PREFIX_RE = re.compile(
    r"(?i)^\s*(?:rm\s+-|sudo\s+rm\b|chmod\s+-R\b|chown\s+-R\b|dd\s+if=|"
    r"mkfs\b|kill\s+-9\b)"
)


def candidate_is_safe(prefix: str, suffix: str) -> bool:
    """Return true only for a non-empty, parseable, non-destructive command."""

    if not suffix or DANGEROUS_PREFIX_RE.match(prefix):
        return False
    command = prefix + suffix
    try:
        shlex.split(command)
    except ValueError:
        return False
    return not UNSAFE_RE.search(command)
