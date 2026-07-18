from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from pathlib import Path

import pytest

from shellcue.runtime.shell_integration import (
    BLOCK_START,
    LEGACY_BLOCK_END,
    LEGACY_BLOCK_START,
    backup_path,
    install_shell,
    render_shell_init,
    uninstall_shell,
)


@pytest.mark.parametrize("shell", ["bash", "zsh"])
def test_shell_install_and_uninstall_are_idempotent(shell: str, tmp_path: Path) -> None:
    rc = tmp_path / f".{shell}rc"
    rc.write_text("# existing completion\n", encoding="utf-8")

    install_shell(shell, rc_path=rc)
    install_shell(shell, rc_path=rc)

    installed = rc.read_text(encoding="utf-8")
    assert installed.count(BLOCK_START) == 1
    assert "# existing completion" in installed
    uninstall_shell(shell, rc_path=rc)
    uninstall_shell(shell, rc_path=rc)
    assert rc.read_text(encoding="utf-8") == "# existing completion\n"


@pytest.mark.parametrize("shell", ["bash", "zsh"])
def test_shell_hook_has_no_capture_or_network_hooks(shell: str) -> None:
    snippet = render_shell_init(shell).lower()

    assert "command shellcue" in snippet
    assert "shellcue_args=(suggest" in snippet
    assert "--recent-stdin0" in snippet
    assert "count < 8" in snippet
    assert '"${shellcue_args[@]}"' in snippet
    assert "shellcue_recent+=(\"$line\")" in snippet
    assert "printf '%s\\0'" in snippet
    assert "shellcue_args+=(--recent" not in snippet
    assert '--recent "$line"' not in snippet
    assert "telemetry" not in snippet
    assert "collect" not in snippet
    assert "record" not in snippet
    assert "interaction" not in snippet
    assert "curl" not in snippet
    assert "wget" not in snippet
    assert "\t" not in snippet
    if shell == "bash":
        assert "ShellCue: no suggestion" in render_shell_init(shell)
        assert "ShellCue unavailable; run shellcue doctor" in render_shell_init(shell)


@pytest.mark.parametrize("shell", ["bash", "zsh"])
def test_shell_hook_is_valid_shell_syntax(shell: str) -> None:
    executable = shutil.which(shell)
    if executable is None:
        pytest.skip(f"{shell} is not installed")

    result = subprocess.run(
        [executable, "-n"],
        input=render_shell_init(shell),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_zsh_hook_owns_automatic_nonblocking_ghost_suggestions() -> None:
    snippet = render_shell_init("zsh")

    assert ": ${SHELLCUE_ZSH_AUTO_SUGGEST:=1}" in snippet
    assert ": ${SHELLCUE_ZSH_DEBOUNCE_SECONDS:=0.20}" in snippet
    assert "POSTDISPLAY" in snippet
    assert "region_highlight" in snippet
    assert "zle -F \"$fd\" _shellcue_async_ready" in snippet
    assert "zle -N zle-line-pre-redraw _shellcue_zle_line_pre_redraw" in snippet
    assert "zle -N self-insert" not in snippet
    assert "zle -N backward-delete-char" not in snippet
    assert "zle -N delete-char" not in snippet
    assert 'print -r -- "0${suffix}"' in snippet
    assert 'print -r -- "1"' in snippet
    assert 'zle -M "ShellCue unavailable; run shellcue doctor"' in snippet


def test_zsh_hook_preserves_tab_fallback_and_accepts_visible_suggestion() -> None:
    snippet = render_shell_init("zsh")

    assert "SHELLCUE_ZSH_ACCEPT_KEYS=('^I' '^[[Z')" in snippet
    assert "_shellcue_accept_next_word()" in snippet
    assert "_shellcue_accept_full_suggestion()" in snippet
    assert "_shellcue_widget_for_key '^I' expand-or-complete" in snippet
    assert "bindkey '^]' _shellcue_force_suggestion" in snippet


def test_zsh_accept_widgets_apply_one_word_or_full_suffix() -> None:
    executable = shutil.which("zsh")
    if executable is None:
        pytest.skip("zsh is not installed")
    snippet = render_shell_init("zsh")
    script = "\n".join(
        [
            "zle() { return 0; }",
            "bindkey() { return 0; }",
            snippet,
            "BUFFER='git st'",
            "CURSOR=${#BUFFER}",
            "POSTDISPLAY='atus --short --branch'",
            "SHELLCUE_ZSH_DISPLAY_COMMAND=\"${BUFFER}${POSTDISPLAY}\"",
            "KEYS=$'\\t'",
            "_shellcue_accept_suggestion",
            "print -r -- \"word:${BUFFER}|${POSTDISPLAY}\"",
            "BUFFER='git st'",
            "CURSOR=${#BUFFER}",
            "POSTDISPLAY='atus --short --branch'",
            "SHELLCUE_ZSH_DISPLAY_COMMAND=\"${BUFFER}${POSTDISPLAY}\"",
            "KEYS=$'\\e[Z'",
            "_shellcue_accept_suggestion",
            "print -r -- \"full:${BUFFER}|${POSTDISPLAY}\"",
        ]
    )

    result = subprocess.run(
        [executable, "-f", "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "word:git status| --short --branch" in result.stdout
    assert "full:git status --short --branch|" in result.stdout


def test_zsh_schedule_consumes_matching_ghost_and_drops_divergence() -> None:
    executable = shutil.which("zsh")
    if executable is None:
        pytest.skip("zsh is not installed")
    snippet = render_shell_init("zsh")
    script = "\n".join(
        [
            "zle() { return 0; }",
            "bindkey() { return 0; }",
            snippet,
            "BUFFER='git sta'",
            "CURSOR=${#BUFFER}",
            "POSTDISPLAY='atus --short'",
            "SHELLCUE_ZSH_DISPLAY_COMMAND='git status --short'",
            "_shellcue_schedule_suggestion",
            "print -r -- \"match:${POSTDISPLAY}\"",
            "BUFFER='git diff'",
            "CURSOR=${#BUFFER}",
            "SHELLCUE_ZSH_EMPTY_BUFFER='git diff'",
            "_shellcue_schedule_suggestion",
            "print -r -- \"diverged:${POSTDISPLAY}\"",
        ]
    )

    result = subprocess.run(
        [executable, "-f", "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "match:tus --short" in result.stdout
    assert "diverged:" in result.stdout
    assert "diverged:tus" not in result.stdout


def test_zsh_async_worker_frames_transport_failure(tmp_path: Path) -> None:
    executable = shutil.which("zsh")
    if executable is None:
        pytest.skip("zsh is not installed")
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_shellcue = fake_bin / "shellcue"
    fake_shellcue.write_text("#!/bin/sh\nexit 7\n", encoding="utf-8")
    fake_shellcue.chmod(0o755)
    snippet = render_shell_init("zsh")
    script = "\n".join(
        [
            "zle() { return 0; }",
            "bindkey() { return 0; }",
            f"PATH={fake_bin!s}:$PATH",
            snippet,
            "_shellcue_start_prediction 'git st' '0'",
            "IFS= read -r frame <&$SHELLCUE_ZSH_PENDING_FD || true",
            "print -r -- \"frame:${frame}\"",
        ]
    )

    result = subprocess.run(
        [executable, "-f", "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "frame:1" in result.stdout


def test_zsh_stale_worker_does_not_trigger_apple_terminal_session_save(
    tmp_path: Path,
) -> None:
    executable = shutil.which("zsh")
    apple_terminal_init = Path("/etc/zshrc_Apple_Terminal")
    if executable is None or not apple_terminal_init.is_file():
        pytest.skip("Apple Terminal Zsh integration is unavailable")
    history = tmp_path / "history"
    snippet = render_shell_init("zsh")
    script = "\n".join(
        [
            "zle() { return 0; }",
            "bindkey() { return 0; }",
            f"HISTFILE={shlex.quote(str(history))}",
            "SAVEHIST=100",
            "HISTSIZE=100",
            "/usr/bin/touch \"$HISTFILE\"",
            f"source {shlex.quote(str(apple_terminal_init))}",
            snippet,
            "_shellcue_start_prediction 'git st' '0.01'",
            "_shellcue_invalidate_pending",
            "IFS= read -r frame <&$SHELLCUE_ZSH_PENDING_FD || true",
            "autoload -Uz add-zsh-hook",
            "add-zsh-hook -d zshexit shell_session_update",
        ]
    )
    env = os.environ.copy()
    env.update(
        {
            "TERM_SESSION_ID": "SHELLCUE-STALE-WORKER-REGRESSION",
            "ZDOTDIR": str(tmp_path),
            "SHELL_SESSIONS_DISABLE": "0",
            "SHELL_SESSION_DID_INIT": "0",
        }
    )

    result = subprocess.run(
        [executable, "-d", "-f", "-c", script],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Saving session" not in result.stderr
    session_dir = tmp_path / ".zsh_sessions"
    assert not tuple(session_dir.glob("*.session"))
    assert not tuple(session_dir.glob("*.history"))


@pytest.mark.parametrize("shell", ["bash", "zsh"])
def test_install_migrates_legacy_block_with_one_backup(shell: str, tmp_path: Path) -> None:
    rc = tmp_path / f".{shell}rc"
    original = (
        "# before\n"
        f"{LEGACY_BLOCK_START}\nlegacy command hook\n{LEGACY_BLOCK_END}\n"
        "# after\n"
    )
    rc.write_text(original, encoding="utf-8")

    install_shell(shell, rc_path=rc)
    first = rc.read_text(encoding="utf-8")
    install_shell(shell, rc_path=rc)

    assert LEGACY_BLOCK_START not in first
    assert "legacy command hook" not in first
    assert "# before\n# after\n" in first
    assert first.count(BLOCK_START) == 1
    assert rc.read_text(encoding="utf-8") == first
    assert backup_path(rc).read_text(encoding="utf-8") == original


def test_incomplete_legacy_block_does_not_mutate_rc(tmp_path: Path) -> None:
    rc = tmp_path / ".zshrc"
    original = f"# keep\n{LEGACY_BLOCK_START}\nbroken\n"
    rc.write_text(original, encoding="utf-8")

    with pytest.raises(ValueError, match="incomplete managed block"):
        install_shell("zsh", rc_path=rc)

    assert rc.read_text(encoding="utf-8") == original
    assert not backup_path(rc).exists()


@pytest.mark.parametrize(
    "line",
    [
        f"{LEGACY_BLOCK_START} keep this",
        f"prefix {LEGACY_BLOCK_START}",
        f"{LEGACY_BLOCK_END} keep this",
        f"prefix {LEGACY_BLOCK_END}",
    ],
)
def test_marker_substrings_do_not_delete_user_lines(line: str, tmp_path: Path) -> None:
    rc = tmp_path / ".zshrc"
    original = f"# before\n{line}\n# after\n"
    rc.write_text(original, encoding="utf-8")

    install_shell("zsh", rc_path=rc)

    installed = rc.read_text(encoding="utf-8")
    assert original in installed
    assert not backup_path(rc).exists()
