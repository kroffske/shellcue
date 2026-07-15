from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path

import pytest

from shellcue import __version__
from shellcue.cli import _read_recent_stdin0, build_parser, main
from shellcue.runtime.context import MAX_HISTORY, MAX_INPUT_COMMAND_CHARS, RuntimeContext


def _choices(parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
    action = next(
        item for item in parser._actions if isinstance(item, argparse._SubParsersAction)
    )
    return action.choices


def test_public_cli_surface_is_exact() -> None:
    commands = _choices(build_parser())

    assert set(commands) == {
        "suggest",
        "daemon",
        "service",
        "model",
        "shell-init",
        "install-shell",
        "uninstall-shell",
        "doctor",
    }
    assert set(_choices(commands["daemon"])) == {"start", "stop", "status", "run"}
    assert set(_choices(commands["service"])) == {
        "install",
        "uninstall",
        "start",
        "stop",
        "status",
    }
    assert set(_choices(commands["model"])) == {
        "install",
        "list",
        "current",
        "use",
        "uninstall",
        "verify",
    }


def test_version_and_shell_init(capsys) -> None:
    assert __version__ == "0.1.0a3"
    assert main(["shell-init", "zsh"]) == 0
    output = capsys.readouterr().out
    assert "command shellcue" in output
    assert "shellcue_args=(suggest" in output


def test_verify_command(model_dir: Path, capsys) -> None:
    assert main(["model", "verify", str(model_dir)]) == 0
    assert "valid" in capsys.readouterr().out


def test_nul_stdin_history_is_bounded_then_masked_by_runtime() -> None:
    raw_secret = "export API_TOKEN=abcdefghijklmnopqrstuvwxyz0123456789"
    entries = _read_recent_stdin0(BytesIO(f"git status\0{raw_secret}\0".encode()))

    context = RuntimeContext.capture(cwd=None, recent_commands=entries).render()

    assert entries == ["git status", raw_secret]
    assert raw_secret not in context
    assert "<SECRET>" in context


@pytest.mark.parametrize(
    "payload",
    [
        b"unterminated",
        b"\xff\0",
        b"x\0" * (MAX_HISTORY + 1),
        b"x" * (MAX_HISTORY * (MAX_INPUT_COMMAND_CHARS + 1) + 1),
    ],
)
def test_nul_stdin_history_rejects_invalid_or_oversized_input(payload: bytes) -> None:
    with pytest.raises(ValueError):
        _read_recent_stdin0(BytesIO(payload))
