from __future__ import annotations

import plistlib
import subprocess
from pathlib import Path

import pytest

from shellcue.runtime import service


def test_launchd_definition_uses_absolute_tool_python_and_state_paths(tmp_path: Path) -> None:
    executable = tmp_path / "uv-tools/shellcue/bin/python"
    plan = service.detect_service_plan(
        platform_name="darwin", home=tmp_path, executable=executable
    )

    payload = plistlib.loads(service.render_definition(plan).encode())

    assert payload["ProgramArguments"] == [
        str(executable),
        "-m",
        "shellcue.runtime.daemon",
    ]
    assert payload["EnvironmentVariables"] == {
        "HOME": str(tmp_path),
        "SHELLCUE_CACHE_DIR": str(tmp_path / ".cache/shellcue"),
        "SHELLCUE_CONFIG_DIR": str(tmp_path / ".config/shellcue"),
        "SHELLCUE_DAEMON_DIR": str(tmp_path / ".cache/shellcue/daemon"),
    }
    assert payload["KeepAlive"] is True
    assert "PATH" not in payload["EnvironmentVariables"]


def test_service_executable_keeps_uv_environment_symlink(tmp_path: Path) -> None:
    environment_python = tmp_path / "tools/shellcue/bin/python"
    base_python = tmp_path / "python-build/bin/python3.12"
    base_python.parent.mkdir(parents=True)
    base_python.write_text("", encoding="utf-8")
    environment_python.parent.mkdir(parents=True)
    environment_python.symlink_to(base_python)

    plan = service.detect_service_plan(
        platform_name="darwin", home=tmp_path, executable=environment_python
    )

    assert plan.executable == environment_python
    assert plan.executable.resolve() == base_python


def test_systemd_definition_and_wsl_backend_matrix(tmp_path: Path) -> None:
    executable = tmp_path / "uv-tools/shellcue/bin/python"
    systemd = service.detect_service_plan(
        platform_name="linux",
        environ={"WSL_DISTRO_NAME": "Ubuntu"},
        home=tmp_path,
        executable=executable,
        systemd_available=True,
    )
    session = service.detect_service_plan(
        platform_name="linux",
        environ={"WSL_DISTRO_NAME": "Ubuntu"},
        home=tmp_path,
        executable=executable,
        systemd_available=False,
    )

    unit = service.render_definition(systemd)
    assert systemd.backend == "systemd"
    assert f'ExecStart="{executable}" "-m" "shellcue.runtime.daemon"' in unit
    assert f'Environment="HOME={tmp_path}"' in unit
    assert "Environment=\"PATH=" not in unit
    assert "Restart=always" in unit
    assert session.backend == "session"
    assert session.supervised is False
    assert session.definition_path is None


def test_linux_without_systemd_fails_outside_wsl(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="systemd user services are unavailable"):
        service.detect_service_plan(
            platform_name="linux",
            environ={},
            home=tmp_path,
            executable=tmp_path / "python",
            systemd_available=False,
        )


def test_install_and_uninstall_launchd_definition_are_idempotent(
    tmp_path: Path, monkeypatch
) -> None:
    plan = service.detect_service_plan(
        platform_name="darwin",
        home=tmp_path,
        executable=tmp_path / "uv-tools/shellcue/bin/python",
    )
    commands: list[tuple[str, ...]] = []
    manager_loaded = False

    def fake_run(command, *, allow_failure=False):
        nonlocal manager_loaded
        commands.append(tuple(command))
        if command[:2] == ("launchctl", "bootstrap"):
            manager_loaded = True
        elif command[:2] == ("launchctl", "bootout"):
            manager_loaded = False
        code = 0
        if command[:2] == ("launchctl", "print") and not manager_loaded:
            code = 113
        return subprocess.CompletedProcess(command, code, "", "")

    monkeypatch.setattr(service, "_run", fake_run)
    monkeypatch.setattr(
        service.daemon,
        "status",
        lambda: service.daemon.DaemonStatus(False, None, tmp_path / "daemon.sock"),
    )

    installed = service.install(plan)
    removed = service.uninstall(plan)
    service.uninstall(plan)

    assert installed.installed is True
    assert installed.running is False
    assert "inference not ready" in installed.detail
    assert removed.installed is False
    assert plan.definition_path is not None
    assert not plan.definition_path.exists()
    assert any(command[:2] == ("launchctl", "bootstrap") for command in commands)
    kickstarts = [command for command in commands if command[:2] == ("launchctl", "kickstart")]
    assert kickstarts
    assert all(str(plan.executable) not in part for command in kickstarts for part in command)


def test_wsl_session_status_is_explicitly_unsupervised(tmp_path: Path, monkeypatch) -> None:
    plan = service.ServicePlan("session", None, tmp_path / "python", tmp_path, False)
    monkeypatch.setattr(
        service.daemon,
        "status",
        lambda: service.daemon.DaemonStatus(True, 88, tmp_path / "daemon.sock"),
    )

    state = service.status(plan)

    assert state.running is True
    assert state.installed is False
    assert state.supervised is False
    assert "unsupervised WSL session" in state.detail


def test_launchd_bootstrap_retries_transient_failure(tmp_path: Path, monkeypatch) -> None:
    results = iter((5, 0))
    sleeps: list[float] = []

    def fake_run(command, *, allow_failure=False):
        code = next(results)
        return subprocess.CompletedProcess(command, code, "", "transient")

    monkeypatch.setattr(service, "_run", fake_run)
    monkeypatch.setattr(service.time, "sleep", sleeps.append)

    service._bootstrap_launchd(tmp_path / "com.shellcue.daemon.plist", attempts=2)

    assert sleeps == [0.25]


def test_uninstall_preserves_definition_when_launchd_stays_loaded(
    tmp_path: Path, monkeypatch
) -> None:
    plan = service.detect_service_plan(
        platform_name="darwin", home=tmp_path, executable=tmp_path / "python"
    )
    assert plan.definition_path is not None
    plan.definition_path.parent.mkdir(parents=True)
    plan.definition_path.write_text("definition", encoding="utf-8")
    def still_loaded(command, **_kwargs):
        code = 5 if command[:2] == ("launchctl", "bootout") else 0
        return subprocess.CompletedProcess(command, code, "", "busy")

    monkeypatch.setattr(service, "_run", still_loaded)
    monkeypatch.setattr(service.time, "sleep", lambda _seconds: None)

    with pytest.raises(RuntimeError, match="definition was preserved"):
        service.uninstall(plan)

    assert plan.definition_path.read_text(encoding="utf-8") == "definition"
