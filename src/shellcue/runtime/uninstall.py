"""Fail-closed coordination for removing ShellCue runtime state."""

from __future__ import annotations

import errno
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from shellcue.models.registry import cache_dir, config_dir
from shellcue.runtime import daemon, service
from shellcue.runtime.shell_integration import uninstall_shell


@dataclass(frozen=True)
class UninstallResult:
    service_state: service.ServiceState
    shell_paths: tuple[Path, ...]
    purged_paths: tuple[Path, ...]
    preserved_paths: tuple[Path, ...] = ()


@dataclass(frozen=True)
class _PurgeTarget:
    path: Path
    kind: Literal["root", "tree", "file"]


def uninstall(*, purge: bool = False) -> UninstallResult:
    """Remove runtime integration, then optionally remove ShellCue-owned state."""

    purge_targets, cleanup_roots, purge_socket = (
        _validated_purge_targets() if purge else ((), (), None)
    )
    service_state = service.uninstall()
    daemon.stop()
    shell_paths = tuple(uninstall_shell(shell) for shell in ("zsh", "bash"))
    purged_paths: list[Path] = []
    preserved_paths: list[Path] = []
    for target in purge_targets:
        if not target.path.exists():
            continue
        try:
            if target.kind in {"root", "tree"}:
                shutil.rmtree(target.path)
            else:
                target.path.unlink()
        except OSError as exc:
            raise RuntimeError(
                f"failed to purge ShellCue state at {target.path}: {exc}"
            ) from exc
        purged_paths.append(target.path)
    if purge_socket is not None and purge_socket.exists():
        if not purge_socket.is_socket():
            raise RuntimeError(f"refusing to purge non-socket daemon state: {purge_socket}")
        purge_socket.unlink()
        purged_paths.append(purge_socket)
    for root in sorted(cleanup_roots, key=lambda path: len(path.parts), reverse=True):
        if not root.exists():
            continue
        try:
            root.rmdir()
        except OSError as exc:
            if exc.errno in {errno.EEXIST, errno.ENOTEMPTY}:
                preserved_paths.append(root)
                continue
            raise RuntimeError(f"failed to finish purging ShellCue state at {root}: {exc}") from exc
        purged_paths.append(root)
    return UninstallResult(
        service_state,
        shell_paths,
        tuple(purged_paths),
        tuple(preserved_paths),
    )


def _validated_purge_targets() -> tuple[
    tuple[_PurgeTarget, ...], tuple[Path, ...], Path | None
]:
    roots = (
        (_validated_purge_root(cache_dir()), (("models", "tree"), (".locks", "tree"))),
        (
            _validated_purge_root(config_dir()),
            (("config.json", "file"), ("config.tmp", "file")),
        ),
        (
            _validated_purge_root(daemon.daemon_dir()),
            (
                ("shellcue.pid", "file"),
                ("shellcue.log", "file"),
                ("shellcue.lock", "file"),
            ),
        ),
    )
    targets: dict[Path, _PurgeTarget] = {}
    cleanup_roots: set[Path] = set()
    for root, owned_entries in roots:
        if root.name == "shellcue":
            targets[root] = _PurgeTarget(root, "root")
            continue
        cleanup_roots.add(root)
        for name, kind in owned_entries:
            target = _validated_owned_target(root, name, kind)
            targets[target.path] = target
    recursive_targets = tuple(
        target.path for target in targets.values() if target.kind in {"root", "tree"}
    )
    targets = {
        path: target
        for path, target in targets.items()
        if not any(
            path != recursive and path.is_relative_to(recursive)
            for recursive in recursive_targets
        )
    }
    cleanup_roots = {
        root
        for root in cleanup_roots
        if not any(
            root == recursive or root.is_relative_to(recursive)
            for recursive in recursive_targets
        )
    }
    socket = _validated_purge_socket(daemon.socket_path())
    if any(
        socket == target.path
        or (
            target.kind in {"root", "tree"}
            and socket.is_relative_to(target.path)
        )
        for target in targets.values()
    ):
        socket = None
    return tuple(targets.values()), tuple(cleanup_roots), socket


def _validated_owned_target(
    root: Path, name: str, kind: Literal["tree", "file"]
) -> _PurgeTarget:
    candidate = root / name
    if candidate.is_symlink():
        raise ValueError(f"refusing to purge symlinked ShellCue state: {candidate}")
    path = candidate.resolve(strict=False)
    if not path.is_relative_to(root):
        raise ValueError(f"refusing to purge ShellCue state outside {root}: {path}")
    if path.exists() and kind == "tree" and not path.is_dir():
        raise ValueError(f"refusing to purge non-directory ShellCue state: {path}")
    if path.exists() and kind == "file" and not path.is_file():
        raise ValueError(f"refusing to purge non-file ShellCue state: {path}")
    return _PurgeTarget(path, kind)


def _validated_purge_root(candidate: Path) -> Path:
    expanded = candidate.expanduser()
    if not expanded.is_absolute():
        raise ValueError(f"refusing to purge non-absolute ShellCue state root: {candidate}")
    if expanded.is_symlink():
        raise ValueError(f"refusing to purge symlinked ShellCue state root: {expanded}")
    root = expanded.resolve(strict=False)
    home = Path.home().resolve()
    protected = {
        Path(root.anchor),
        home,
        home / ".cache",
        home / ".config",
        Path("/tmp").resolve(),
        Path("/var/tmp").resolve(),
    }
    if len(root.parts) < 3 or root in protected or (root.exists() and root.is_mount()):
        raise ValueError(f"refusing to purge unsafe ShellCue state root: {root}")
    if root.exists() and not root.is_dir():
        raise ValueError(f"refusing to purge non-directory ShellCue state root: {root}")
    return root


def _validated_purge_socket(candidate: Path) -> Path:
    expanded = candidate.expanduser()
    if not expanded.is_absolute():
        raise ValueError(f"refusing to purge non-absolute daemon socket: {candidate}")
    if expanded.is_symlink():
        raise ValueError(f"refusing to purge symlinked daemon socket: {expanded}")
    socket = expanded.resolve(strict=False)
    if socket.exists() and not socket.is_socket():
        raise ValueError(f"refusing to purge non-socket daemon state: {socket}")
    return socket
