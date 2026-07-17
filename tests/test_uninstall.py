from __future__ import annotations

import socket
import tempfile
from pathlib import Path

import pytest

from shellcue.runtime import service
from shellcue.runtime import uninstall as runtime_uninstall


def _service_state() -> service.ServiceState:
    return service.ServiceState("launchd", False, False, True, "service definition not installed")


def _record_runtime_removal(monkeypatch, events: list[str]) -> None:
    monkeypatch.setattr(
        runtime_uninstall.service,
        "uninstall",
        lambda: events.append("service") or _service_state(),
    )
    monkeypatch.setattr(
        runtime_uninstall.daemon,
        "stop",
        lambda: events.append("daemon") or False,
    )
    monkeypatch.setattr(
        runtime_uninstall,
        "uninstall_shell",
        lambda shell: events.append(f"shell:{shell}") or Path(f"/{shell}rc"),
    )


def test_uninstall_preserves_state_without_purge(tmp_path: Path, monkeypatch) -> None:
    cache = tmp_path / "cache"
    config = tmp_path / "config"
    cache.mkdir()
    config.mkdir()
    events: list[str] = []
    _record_runtime_removal(monkeypatch, events)
    monkeypatch.setenv("SHELLCUE_CACHE_DIR", str(cache))
    monkeypatch.setenv("SHELLCUE_CONFIG_DIR", str(config))

    result = runtime_uninstall.uninstall()

    assert events == ["service", "daemon", "shell:zsh", "shell:bash"]
    assert result.purged_paths == ()
    assert cache.is_dir()
    assert config.is_dir()


def test_purge_removes_owned_state_but_preserves_external_data(
    tmp_path: Path, monkeypatch
) -> None:
    cache = tmp_path / "cache/shellcue"
    config = tmp_path / "config/shellcue"
    daemon = tmp_path / "runtime/shellcue"
    external_model = tmp_path / "external-model"
    huggingface_cache = tmp_path / "huggingface/hub"
    for root in (cache, config, daemon, external_model, huggingface_cache):
        root.mkdir(parents=True)
        (root / "sentinel").write_text("keep or remove", encoding="utf-8")
    events: list[str] = []
    _record_runtime_removal(monkeypatch, events)
    monkeypatch.setenv("SHELLCUE_CACHE_DIR", str(cache))
    monkeypatch.setenv("SHELLCUE_CONFIG_DIR", str(config))
    monkeypatch.setenv("SHELLCUE_DAEMON_DIR", str(daemon))
    monkeypatch.setenv("SHELLCUE_MODEL_DIR", str(external_model))

    with tempfile.TemporaryDirectory(prefix="sc-", dir="/tmp") as socket_root:
        daemon_socket = Path(socket_root) / "shellcue.sock"
        monkeypatch.setenv("SHELLCUE_DAEMON_SOCKET", str(daemon_socket))
        with socket.socket(socket.AF_UNIX) as server:
            server.bind(str(daemon_socket))
            first = runtime_uninstall.uninstall(purge=True)
            second = runtime_uninstall.uninstall(purge=True)
        assert set(first.purged_paths) == {
            cache,
            config,
            daemon,
            daemon_socket.resolve(),
        }
        assert not daemon_socket.exists()

    assert events == [
        "service",
        "daemon",
        "shell:zsh",
        "shell:bash",
        "service",
        "daemon",
        "shell:zsh",
        "shell:bash",
    ]
    assert second.purged_paths == ()
    assert not cache.exists()
    assert not config.exists()
    assert not daemon.exists()
    assert external_model.is_dir()
    assert huggingface_cache.is_dir()


def test_purge_removes_only_owned_entries_from_shared_overrides(
    tmp_path: Path, monkeypatch
) -> None:
    cache = tmp_path / "shared-cache"
    config = tmp_path / "shared-config"
    daemon = tmp_path / "shared-runtime"
    owned_paths = (
        cache / "models",
        cache / ".locks",
    )
    for path in owned_paths:
        path.mkdir(parents=True)
        (path / "owned").write_text("remove", encoding="utf-8")
    config.mkdir()
    (config / "config.json").write_text("{}", encoding="utf-8")
    daemon.mkdir()
    (daemon / "shellcue.log").write_text("remove", encoding="utf-8")
    for root in (cache, config, daemon):
        (root / "unrelated").write_text("keep", encoding="utf-8")
    events: list[str] = []
    _record_runtime_removal(monkeypatch, events)
    monkeypatch.setenv("SHELLCUE_CACHE_DIR", str(cache))
    monkeypatch.setenv("SHELLCUE_CONFIG_DIR", str(config))
    monkeypatch.setenv("SHELLCUE_DAEMON_DIR", str(daemon))

    result = runtime_uninstall.uninstall(purge=True)

    assert set(result.purged_paths) == {
        cache / "models",
        cache / ".locks",
        config / "config.json",
        daemon / "shellcue.log",
    }
    assert set(result.preserved_paths) == {cache, config, daemon}
    for root in (cache, config, daemon):
        assert (root / "unrelated").read_text(encoding="utf-8") == "keep"


def test_purge_rejects_symlinked_owned_entry_before_service_changes(
    tmp_path: Path, monkeypatch
) -> None:
    cache = tmp_path / "shared-cache"
    cache.mkdir()
    external = tmp_path / "external-models"
    external.mkdir()
    (cache / "models").symlink_to(external, target_is_directory=True)
    events: list[str] = []
    _record_runtime_removal(monkeypatch, events)
    monkeypatch.setenv("SHELLCUE_CACHE_DIR", str(cache))
    monkeypatch.setenv("SHELLCUE_CONFIG_DIR", str(tmp_path / "config/shellcue"))

    with pytest.raises(ValueError, match="symlinked"):
        runtime_uninstall.uninstall(purge=True)

    assert events == []
    assert external.is_dir()


def test_purge_collapses_default_daemon_state_into_cache(tmp_path: Path, monkeypatch) -> None:
    cache = tmp_path / "cache/shellcue"
    config = tmp_path / "config/shellcue"
    daemon = cache / "daemon"
    daemon.mkdir(parents=True)
    config.mkdir(parents=True)
    events: list[str] = []
    _record_runtime_removal(monkeypatch, events)
    monkeypatch.setenv("SHELLCUE_CACHE_DIR", str(cache))
    monkeypatch.setenv("SHELLCUE_CONFIG_DIR", str(config))

    result = runtime_uninstall.uninstall(purge=True)

    assert set(result.purged_paths) == {cache, config}
    assert not cache.exists()
    assert not config.exists()


@pytest.mark.parametrize(
    "unsafe_root",
    [Path("/"), Path("relative-state"), Path.home() / ".cache", Path("/tmp")],
)
def test_purge_rejects_unsafe_root_before_service_or_data_changes(
    tmp_path: Path, monkeypatch, unsafe_root: Path
) -> None:
    config = tmp_path / "config/shellcue"
    config.mkdir(parents=True)
    events: list[str] = []
    _record_runtime_removal(monkeypatch, events)
    monkeypatch.setenv("SHELLCUE_CACHE_DIR", str(unsafe_root))
    monkeypatch.setenv("SHELLCUE_CONFIG_DIR", str(config))

    with pytest.raises(ValueError, match="refusing to purge"):
        runtime_uninstall.uninstall(purge=True)

    assert events == []
    assert config.is_dir()


def test_purge_rejects_symlinked_root_before_service_or_data_changes(
    tmp_path: Path, monkeypatch
) -> None:
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "shellcue-link"
    link.symlink_to(target, target_is_directory=True)
    events: list[str] = []
    _record_runtime_removal(monkeypatch, events)
    monkeypatch.setenv("SHELLCUE_CACHE_DIR", str(link))
    monkeypatch.setenv("SHELLCUE_CONFIG_DIR", str(tmp_path / "config/shellcue"))

    with pytest.raises(ValueError, match="symlinked"):
        runtime_uninstall.uninstall(purge=True)

    assert events == []
    assert link.is_symlink()
    assert target.is_dir()


def test_purge_rejects_external_non_socket_before_service_or_data_changes(
    tmp_path: Path, monkeypatch
) -> None:
    daemon_socket = tmp_path / "shellcue.sock"
    daemon_socket.write_text("not a socket", encoding="utf-8")
    events: list[str] = []
    _record_runtime_removal(monkeypatch, events)
    monkeypatch.setenv("SHELLCUE_CACHE_DIR", str(tmp_path / "cache/shellcue"))
    monkeypatch.setenv("SHELLCUE_CONFIG_DIR", str(tmp_path / "config/shellcue"))
    monkeypatch.setenv("SHELLCUE_DAEMON_SOCKET", str(daemon_socket))

    with pytest.raises(ValueError, match="non-socket"):
        runtime_uninstall.uninstall(purge=True)

    assert events == []
    assert daemon_socket.is_file()


def test_service_failure_preserves_hooks_and_state(tmp_path: Path, monkeypatch) -> None:
    cache = tmp_path / "cache/shellcue"
    config = tmp_path / "config/shellcue"
    cache.mkdir(parents=True)
    config.mkdir(parents=True)
    shell_calls: list[str] = []
    monkeypatch.setenv("SHELLCUE_CACHE_DIR", str(cache))
    monkeypatch.setenv("SHELLCUE_CONFIG_DIR", str(config))

    def fail_service_uninstall() -> service.ServiceState:
        raise RuntimeError("service still loaded")

    monkeypatch.setattr(runtime_uninstall.service, "uninstall", fail_service_uninstall)
    monkeypatch.setattr(
        runtime_uninstall,
        "uninstall_shell",
        lambda shell: shell_calls.append(shell) or Path(f"/{shell}rc"),
    )

    with pytest.raises(RuntimeError, match="service still loaded"):
        runtime_uninstall.uninstall(purge=True)

    assert shell_calls == []
    assert cache.is_dir()
    assert config.is_dir()


def test_daemon_stop_failure_preserves_hooks_and_state(tmp_path: Path, monkeypatch) -> None:
    cache = tmp_path / "cache/shellcue"
    config = tmp_path / "config/shellcue"
    cache.mkdir(parents=True)
    config.mkdir(parents=True)
    shell_calls: list[str] = []
    monkeypatch.setenv("SHELLCUE_CACHE_DIR", str(cache))
    monkeypatch.setenv("SHELLCUE_CONFIG_DIR", str(config))
    monkeypatch.setattr(runtime_uninstall.service, "uninstall", _service_state)
    monkeypatch.setattr(
        runtime_uninstall.daemon,
        "stop",
        lambda: (_ for _ in ()).throw(RuntimeError("daemon still running")),
    )
    monkeypatch.setattr(
        runtime_uninstall,
        "uninstall_shell",
        lambda shell: shell_calls.append(shell) or Path(f"/{shell}rc"),
    )

    with pytest.raises(RuntimeError, match="daemon still running"):
        runtime_uninstall.uninstall(purge=True)

    assert shell_calls == []
    assert cache.is_dir()
    assert config.is_dir()
