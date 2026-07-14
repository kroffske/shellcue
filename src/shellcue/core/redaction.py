"""Mask secrets and identity-bearing paths before local inference."""

from __future__ import annotations

import re

URL_RE = re.compile(r"\b[a-zA-Z][a-zA-Z0-9+.-]*://[^\s'\"<>]+")
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
SECRET_ASSIGN_RE = re.compile(
    r"(?i)\b([A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD|PASSWD|API[_-]?KEY|AUTH|COOKIE|SESSION)"
    r"[A-Z0-9_-]*)(=|:)([^\s]+)"
)
BEARER_RE = re.compile(r"(?i)\b(Bearer|Basic)\s+[A-Za-z0-9._~+/=-]+")
LONG_TOKEN_RE = re.compile(r"\b[A-Za-z0-9_=-]{32,}\b")
ABS_PATH_RE = re.compile(r"(?<![\w])(?:~[A-Za-z0-9_.-]*(?:/[^\s'\";|&<>]*)?|/[\w.-][^\s'\";|&<>]*)")
REL_PATH_RE = re.compile(r"(?<![\w</~])(?:\.{1,2}/|[A-Za-z0-9_.-]+/)[^\s'\";|&<>]*")
SINGLE_QUOTED_RE = re.compile(r"'(?:[^'\\]|\\.)*'")
DOUBLE_QUOTED_RE = re.compile(r'"(?:[^"\\]|\\.)*"')


def mask_command(command: str) -> str:
    """Return a bounded command shape with sensitive literals removed."""

    masked = " ".join(command.strip().split())
    masked = URL_RE.sub("<URL>", masked)
    masked = EMAIL_RE.sub("<EMAIL>", masked)
    masked = SECRET_ASSIGN_RE.sub(lambda match: f"{match.group(1)}{match.group(2)}<SECRET>", masked)
    masked = BEARER_RE.sub(lambda match: f"{match.group(1)} <SECRET>", masked)
    masked = SINGLE_QUOTED_RE.sub("'<STR>'", masked)
    masked = DOUBLE_QUOTED_RE.sub('"<STR>"', masked)
    masked = ABS_PATH_RE.sub("<PATH>", masked)
    masked = REL_PATH_RE.sub("<PATH>", masked)
    return LONG_TOKEN_RE.sub("<SECRET>", masked)
