from __future__ import annotations

from pathlib import Path

from shellcue.runtime import doctor
from shellcue.runtime.daemon import DaemonStatus
from shellcue.runtime.shell_integration import install_shell


def test_shell_check_reports_trigger_for_current_hook(tmp_path: Path) -> None:
    rc = tmp_path / ".zshrc"
    install_shell("zsh", rc_path=rc)

    result = doctor._shell_check("zsh", rc_path=rc)

    assert result.ok
    assert result.required
    assert "automatic hook" in result.detail
    assert "Tab accepts one word" in result.detail


def test_shell_check_reports_missing_hook_as_strict_runtime_failure(
    tmp_path: Path,
) -> None:
    result = doctor._shell_check("zsh", rc_path=tmp_path / ".zshrc")

    assert not result.ok
    assert result.required
    assert "install-shell zsh" in result.detail


def test_suggestion_checks_separate_runtime_smoke_from_git_quality(monkeypatch) -> None:
    def fake_suggest(*, prefix, cwd, recent_commands, limit, timeout):
        command = {"pytest -": "pytest -q", "git st": "git stale"}[prefix]
        return (
            {
                "suffix": command[len(prefix) :],
                "command": command,
                "score": 0.0,
                "source": "model",
            },
        )

    monkeypatch.setattr(doctor.daemon, "suggest", fake_suggest)
    state = DaemonStatus(True, 123, Path("/tmp/shellcue.sock"))

    runtime, quality = doctor._suggestion_checks(state)

    assert runtime.ok
    assert runtime.required
    assert "pytest -q" in runtime.detail
    assert not quality.ok
    assert quality.required is False
    assert "git stale" in quality.detail
    assert "git status" in quality.detail


def test_suggestion_check_requires_running_daemon() -> None:
    runtime, quality = doctor._suggestion_checks(
        DaemonStatus(False, None, Path("/tmp/shellcue.sock"))
    )

    assert not runtime.ok
    assert runtime.required
    assert not quality.ok
    assert quality.required is False
