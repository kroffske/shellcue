"""The input mask hides live credentials and keeps everything else.

These pin the product decision that ShellCue reuses exact local paths, URLs, and
hosts, and mask only genuine credentials — the opposite of the training
repository's publication policy, which is stricter because it sends bytes to a
public dataset.
"""

from __future__ import annotations

import pytest

from shellcue.core.redaction import mask_command


@pytest.mark.parametrize(
    "command",
    [
        "curl -fsSL https://get.example.test/install.sh -o install.sh",
        "ssh deploy@build.example.test",
        "scp dist.tar.gz deploy@build.example.test:/srv/releases",
        "cat ~/.ssh/id_ed25519.pub",
        "cd /Users/me/projects/app",
        "git checkout 9f8e7d6c5b4a3928170615243342516070819abc",
        "psql 'postgres://reader@db.example.test/analytics'",
    ],
)
def test_context_values_are_preserved(command: str) -> None:
    """A path, URL, host, or hash is signal a local completion should reuse."""
    assert mask_command(command) == command


@pytest.mark.parametrize(
    "command, kept",
    [
        ("export API_TOKEN=abcdefghijklmnopqrstuvwxyz0123456789", "API_TOKEN=<SECRET>"),
        (
            "AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMIabcdefGHIJKLMNOpqrs",
            "AWS_SECRET_ACCESS_KEY=<SECRET>",
        ),
        ("curl -H 'Authorization: Bearer sk-abcdEFGH1234abcdEFGH'", "Bearer <SECRET>"),
        ("gh auth login --with-token ghp_abcdefghijklmnopqrstuvwxyz0123", "<SECRET>"),
    ],
)
def test_credentials_are_masked(command: str, kept: str) -> None:
    masked = mask_command(command)
    assert kept in masked
    # The raw secret body never survives.
    assert "abcdefghijklmnopqrstuvwxyz" not in masked
    assert "wJalrXUtnFEMI" not in masked
    assert "ghp_abcdefghijklmnop" not in masked


def test_a_git_sha_is_not_mistaken_for_a_secret() -> None:
    """A 40-char object id is long but pure hex, and it is worth completing."""
    assert mask_command("git show 9f8e7d6c5b4a3928170615243342516070819abc") == (
        "git show 9f8e7d6c5b4a3928170615243342516070819abc"
    )
