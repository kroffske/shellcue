"""Mask genuine credentials before local inference — and nothing else.

The model runs locally and its context never leaves the machine, so a URL, a
path, or a host in recent history is not a disclosure — it is signal. ShellCue
is *supposed* to reuse those exact values: complete an `scp` to the path that
was just listed, an `ssh` to the host from two commands ago, a `curl` to the URL
in the last request. Masking them starves the completion of the one thing that
makes context-aware autocomplete worth having.

What must never reach the model, even locally, is a live credential: a secret
assignment, a bearer token, or a bare high-entropy token. Re-emitting one into a
suggestion could surface it on screen or in a log, and unlike a path it has no
completion value. So this masks exactly those and passes everything else through
untouched.

This is the input policy. It is deliberately different from the publication
policy in the training repository, which masks paths and hosts too — because
publishing sends bytes to a public dataset, where a path *is* a disclosure.
Local inference and public upload are different threats, so they get different
rules rather than a single conservative one that would cripple prediction.
"""

from __future__ import annotations

import re

SECRET_ASSIGN_RE = re.compile(
    r"(?i)\b([A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD|PASSWD|API[_-]?KEY|AUTH|COOKIE|SESSION)"
    r"[A-Z0-9_-]*)(=|:)([^\s]+)"
)
BEARER_RE = re.compile(r"(?i)\b(Bearer|Basic)\s+[A-Za-z0-9._~+/=-]+")
LONG_TOKEN_RE = re.compile(r"\b[A-Za-z0-9_=-]{32,}\b")
_HEX_RE = re.compile(r"(?i)\A[0-9a-f]+\Z")


def mask_command(command: str) -> str:
    """Return a bounded command shape with live credentials removed.

    Paths, URLs, hosts, and quoted strings are preserved on purpose: locally
    they are the context the model exists to use.
    """

    masked = " ".join(command.strip().split())
    masked = SECRET_ASSIGN_RE.sub(lambda match: f"{match.group(1)}{match.group(2)}<SECRET>", masked)
    masked = BEARER_RE.sub(lambda match: f"{match.group(1)} <SECRET>", masked)
    return LONG_TOKEN_RE.sub(_mask_long_token, masked)


def _mask_long_token(match: re.Match[str]) -> str:
    """Mask a long opaque token, but keep a long hexadecimal one.

    A 40-character git object id and a 40-character API key are both long, but
    only one is a secret and only one is worth completing. Hashes are pure hex;
    real credentials almost never are, so a pure-hex run is left intact and
    everything else is treated as a token to hide.
    """
    token = match.group(0)
    return token if _HEX_RE.match(token) else "<SECRET>"
