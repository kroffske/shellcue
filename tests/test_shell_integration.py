from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from shellcue.runtime.shell_integration import (
    BLOCK_START,
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
