"""Per-user service definitions and lifecycle adapters."""

from __future__ import annotations

import os
import plistlib
import shutil
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from shellcue.runtime import daemon

Backend = Literal["launchd", "systemd", "session"]
LAUNCHD_LABEL = "com.shellcue.daemon"
SYSTEMD_UNIT = "shellcue.service"


@dataclass(frozen=True)
class ServicePlan:
    backend: Backend
    definition_path: Path | None
    executable: Path
    home: Path
    supervised: bool


@dataclass(frozen=True)
class ServiceState:
    backend: Backend
    installed: bool
    running: bool
    supervised: bool
    detail: str


def detect_service_plan(
    *,
    platform_name: str | None = None,
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
    executable: Path | None = None,
    systemd_available: bool | None = None,
) -> ServicePlan:
    platform_value = platform_name or sys.platform
    environment = dict(os.environ if environ is None else environ)
    home_value = (home or Path.home()).expanduser().resolve()
    executable_value = (executable or Path(sys.executable)).expanduser()
    if not executable_value.is_absolute():
        executable_value = Path.cwd() / executable_value
    if not executable_value.is_absolute():
        raise RuntimeError("service executable must be an absolute path")
    if platform_value == "darwin":
        return ServicePlan(
            backend="launchd",
            definition_path=home_value / "Library/LaunchAgents" / f"{LAUNCHD_LABEL}.plist",
            executable=executable_value,
            home=home_value,
            supervised=True,
        )
    if platform_value.startswith("linux"):
        available = _systemd_available() if systemd_available is None else systemd_available
        if _is_wsl(environment) and not available:
            return ServicePlan(
                backend="session",
                definition_path=None,
                executable=executable_value,
                home=home_value,
                supervised=False,
            )
        if not available:
            raise RuntimeError(
                "systemd user services are unavailable; ShellCue supports Ubuntu with "
                "systemd, or WSL session mode when WSL has no systemd"
            )
        return ServicePlan(
            backend="systemd",
            definition_path=home_value / ".config/systemd/user" / SYSTEMD_UNIT,
            executable=executable_value,
            home=home_value,
            supervised=True,
        )
    raise RuntimeError(f"unsupported service platform: {platform_value}")


def render_definition(plan: ServicePlan) -> str:
    environment = _service_environment(plan)
    command = (str(plan.executable), "-m", "shellcue.runtime.daemon")
    if plan.backend == "launchd":
        payload = {
            "Label": LAUNCHD_LABEL,
            "ProgramArguments": list(command),
            "EnvironmentVariables": environment,
            "RunAtLoad": True,
            "KeepAlive": True,
            "ProcessType": "Interactive",
            "StandardOutPath": str(daemon.log_path()),
            "StandardErrorPath": str(daemon.log_path()),
        }
        return plistlib.dumps(payload, sort_keys=True).decode("utf-8")
    if plan.backend == "systemd":
        env_lines = "\n".join(
            f"Environment={_systemd_quote(name + '=' + value)}"
            for name, value in sorted(environment.items())
        )
        command_text = " ".join(_systemd_quote(part) for part in command)
        return (
            "[Unit]\n"
            "Description=ShellCue local inference daemon\n"
            "After=default.target\n\n"
            "[Service]\n"
            "Type=simple\n"
            f"{env_lines}\n"
            f"ExecStart={command_text}\n"
            "Restart=always\n"
            "RestartSec=2\n\n"
            "[Install]\n"
            "WantedBy=default.target\n"
        )
    raise RuntimeError("session mode has no persistent service definition")


def install(plan: ServicePlan | None = None) -> ServiceState:
    selected = plan or detect_service_plan()
    if selected.backend == "session":
        daemon.start()
        return status(selected)
    assert selected.definition_path is not None
    selected.definition_path.parent.mkdir(parents=True, exist_ok=True)
    if selected.backend == "launchd":
        _stop_launchd()
    else:
        _stop_systemd()
    _write_atomic(selected.definition_path, render_definition(selected))
    daemon.log_path().parent.mkdir(parents=True, exist_ok=True)
    if selected.backend == "launchd":
        _bootstrap_launchd(selected.definition_path)
        _run(("launchctl", "enable", _launchd_target()))
        _run(("launchctl", "kickstart", "-k", _launchd_target()))
    else:
        _run(("systemctl", "--user", "daemon-reload"))
        _run(("systemctl", "--user", "enable", "--now", SYSTEMD_UNIT))
    return status(selected)


def uninstall(plan: ServicePlan | None = None) -> ServiceState:
    selected = plan or detect_service_plan()
    if selected.backend == "session":
        if daemon.status().running:
            daemon.stop()
        return status(selected)
    if selected.backend == "launchd":
        _stop_launchd()
    else:
        _stop_systemd()
        assert selected.definition_path is not None
        if selected.definition_path.exists():
            result = _run(("systemctl", "--user", "disable", SYSTEMD_UNIT), allow_failure=True)
            if result.returncode != 0:
                raise RuntimeError(
                    "systemd service could not be disabled; definition was preserved"
                )
    assert selected.definition_path is not None
    selected.definition_path.unlink(missing_ok=True)
    if selected.backend == "systemd":
        _run(("systemctl", "--user", "daemon-reload"))
    return status(selected)


def start(plan: ServicePlan | None = None) -> ServiceState:
    selected = plan or detect_service_plan()
    if selected.backend == "session":
        daemon.start()
    elif selected.backend == "launchd":
        if not status(selected).installed:
            raise RuntimeError("launchd service is not installed")
        if not _command_succeeds(("launchctl", "print", _launchd_target())):
            assert selected.definition_path is not None
            _bootstrap_launchd(selected.definition_path)
        _run(("launchctl", "kickstart", "-k", _launchd_target()))
    else:
        _run(("systemctl", "--user", "start", SYSTEMD_UNIT))
    return status(selected)


def stop(plan: ServicePlan | None = None) -> ServiceState:
    selected = plan or detect_service_plan()
    if selected.backend == "session":
        if daemon.status().running:
            daemon.stop()
    elif selected.backend == "launchd":
        _stop_launchd()
    else:
        _stop_systemd()
    return status(selected)


def status(plan: ServicePlan | None = None) -> ServiceState:
    selected = plan or detect_service_plan()
    if selected.backend == "session":
        running = daemon.status().running
        detail = (
            "unsupervised WSL session daemon; enable systemd in /etc/wsl.conf for restart support"
        )
        return ServiceState("session", False, running, False, detail)
    assert selected.definition_path is not None
    installed = selected.definition_path.is_file()
    if selected.backend == "launchd":
        manager_loaded = installed and _command_succeeds(
            ("launchctl", "print", _launchd_target())
        )
    else:
        manager_loaded = installed and _command_succeeds(
            ("systemctl", "--user", "is-active", "--quiet", SYSTEMD_UNIT)
        )
    running = manager_loaded and daemon.status().running
    if not installed:
        detail = "service definition not installed"
    elif running:
        detail = "supervised user service; inference ready"
    elif manager_loaded:
        detail = "supervised user service loaded; inference not ready"
    else:
        detail = "service definition installed; service manager not active"
    return ServiceState(selected.backend, installed, running, True, detail)


def _service_environment(plan: ServicePlan) -> dict[str, str]:
    cache = Path(os.environ.get("SHELLCUE_CACHE_DIR", plan.home / ".cache/shellcue"))
    config = Path(os.environ.get("SHELLCUE_CONFIG_DIR", plan.home / ".config/shellcue"))
    daemon_root = Path(os.environ.get("SHELLCUE_DAEMON_DIR", cache / "daemon"))
    return {
        "HOME": str(plan.home),
        "SHELLCUE_CACHE_DIR": str(cache.expanduser().resolve()),
        "SHELLCUE_CONFIG_DIR": str(config.expanduser().resolve()),
        "SHELLCUE_DAEMON_DIR": str(daemon_root.expanduser().resolve()),
    }


def _is_wsl(environ: Mapping[str, str]) -> bool:
    if environ.get("WSL_INTEROP") or environ.get("WSL_DISTRO_NAME"):
        return True
    try:
        version = Path("/proc/version").read_text(encoding="utf-8").lower()
    except OSError:
        return False
    return "microsoft" in version or "wsl" in version


def _systemd_available() -> bool:
    return Path("/run/systemd/system").is_dir() and shutil.which("systemctl") is not None


def _launchd_domain() -> str:
    return f"gui/{os.getuid()}"


def _launchd_target() -> str:
    return f"{_launchd_domain()}/{LAUNCHD_LABEL}"


def _systemd_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _write_atomic(path: Path, content: str) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(content, encoding="utf-8")
        os.chmod(temporary, 0o600)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _run(
    command: Sequence[str], *, allow_failure: bool = False
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        raise RuntimeError(f"service manager command not found: {command[0]}") from exc
    if result.returncode != 0 and not allow_failure:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise RuntimeError(f"service command failed: {' '.join(command)}: {detail}")
    return result


def _command_succeeds(command: Sequence[str]) -> bool:
    return _run(command, allow_failure=True).returncode == 0


def _bootstrap_launchd(definition_path: Path, *, attempts: int = 40) -> None:
    command = ("launchctl", "bootstrap", _launchd_domain(), str(definition_path))
    last: subprocess.CompletedProcess[str] | None = None
    for attempt in range(attempts):
        last = _run(command, allow_failure=True)
        if last.returncode == 0:
            return
        if attempt + 1 < attempts:
            time.sleep(0.25)
    assert last is not None
    detail = last.stderr.strip() or last.stdout.strip() or f"exit {last.returncode}"
    rendered = " ".join(command)
    raise RuntimeError(
        f"service command failed after {attempts} attempts: {rendered}: {detail}"
    )


def _wait_for_launchd_unloaded(*, attempts: int = 40) -> bool:
    command = ("launchctl", "print", _launchd_target())
    for attempt in range(attempts):
        if not _command_succeeds(command):
            return True
        if attempt + 1 < attempts:
            time.sleep(0.25)
    return False


def _stop_launchd() -> None:
    _run(("launchctl", "bootout", _launchd_target()), allow_failure=True)
    if not _wait_for_launchd_unloaded():
        raise RuntimeError("launchd service did not unload; definition was preserved")


def _stop_systemd() -> None:
    _run(("systemctl", "--user", "stop", SYSTEMD_UNIT), allow_failure=True)
    if _command_succeeds(("systemctl", "--user", "is-active", "--quiet", SYSTEMD_UNIT)):
        raise RuntimeError("systemd service is still active; definition was preserved")
