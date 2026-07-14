"""ShellCue runtime-only command line."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import BinaryIO

from shellcue import __version__
from shellcue.core.redaction import mask_command
from shellcue.models.artifact import ArtifactError, SuggestionRequest, load_artifact
from shellcue.models.neural import NeuralPredictor
from shellcue.models.registry import (
    active_model_dir,
    install_model,
    list_models,
    uninstall_model,
    use_model,
)
from shellcue.runtime import daemon
from shellcue.runtime.context import MAX_HISTORY, MAX_INPUT_COMMAND_CHARS, RuntimeContext
from shellcue.runtime.doctor import checks
from shellcue.runtime.shell_integration import (
    install_shell,
    render_shell_init,
    uninstall_shell,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="shellcue", description="Local neural shell suggestions")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    suggest = commands.add_parser("suggest", help="return local neural suggestions")
    suggest.add_argument("--prefix", required=True)
    suggest.add_argument("--cwd")
    suggest.add_argument("--recent", action="append", default=[])
    suggest.add_argument("--recent-stdin0", action="store_true", help=argparse.SUPPRESS)
    suggest.add_argument("--limit", type=int, default=5)
    suggest.add_argument("--plain", action="store_true")
    suggest.set_defaults(handler=_cmd_suggest)

    daemon_parser = commands.add_parser("daemon", help="manage resident inference")
    daemon_commands = daemon_parser.add_subparsers(dest="daemon_command", required=True)
    for name, handler in (
        ("start", _cmd_daemon_start),
        ("stop", _cmd_daemon_stop),
        ("status", _cmd_daemon_status),
    ):
        item = daemon_commands.add_parser(name)
        item.set_defaults(handler=handler)

    model = commands.add_parser("model", help="manage local model snapshots")
    model_commands = model.add_subparsers(dest="model_command", required=True)
    install = model_commands.add_parser("install")
    install.add_argument("path", type=Path)
    install.add_argument("--name")
    install.add_argument("--force", action="store_true")
    install.set_defaults(handler=_cmd_model_install)
    listing = model_commands.add_parser("list")
    listing.set_defaults(handler=_cmd_model_list)
    current = model_commands.add_parser("current")
    current.set_defaults(handler=_cmd_model_current)
    select = model_commands.add_parser("use")
    select.add_argument("name")
    select.set_defaults(handler=_cmd_model_use)
    remove = model_commands.add_parser("uninstall")
    remove.add_argument("name")
    remove.set_defaults(handler=_cmd_model_uninstall)
    verify = model_commands.add_parser("verify")
    verify.add_argument("path", type=Path)
    verify.set_defaults(handler=_cmd_model_verify)

    shell_init = commands.add_parser("shell-init", help="print Bash/Zsh integration")
    shell_init.add_argument("shell", nargs="?", choices=("bash", "zsh"), default=_default_shell())
    shell_init.set_defaults(handler=_cmd_shell_init)
    shell_install = commands.add_parser("install-shell", help="install one managed hook")
    shell_install.add_argument(
        "shell", choices=("bash", "zsh"), nargs="?", default=_default_shell()
    )
    shell_install.add_argument("--rc-file", type=Path)
    shell_install.set_defaults(handler=_cmd_install_shell)
    shell_remove = commands.add_parser("uninstall-shell", help="remove the managed hook")
    shell_remove.add_argument("shell", choices=("bash", "zsh"), nargs="?", default=_default_shell())
    shell_remove.add_argument("--rc-file", type=Path)
    shell_remove.set_defaults(handler=_cmd_uninstall_shell)

    doctor = commands.add_parser("doctor", help="check local inference readiness")
    doctor.add_argument("--strict", action="store_true")
    doctor.set_defaults(handler=_cmd_doctor)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except (ArtifactError, FileExistsError, FileNotFoundError, RuntimeError, ValueError) as exc:
        print(f"shellcue: {exc}", file=sys.stderr)
        return 2


def _cmd_suggest(args: argparse.Namespace) -> int:
    if not 1 <= args.limit <= 10:
        raise ValueError("--limit must be from 1 to 10")
    recent_commands = _recent_commands(args)
    candidates: tuple[dict[str, object], ...]
    if daemon.status().running:
        candidates = daemon.suggest(
            prefix=args.prefix,
            cwd=args.cwd,
            recent_commands=recent_commands,
            limit=args.limit,
        )
    else:
        model_dir = active_model_dir()
        if model_dir is None:
            raise RuntimeError("no active model; run 'shellcue model install' first")
        context = RuntimeContext.capture(cwd=args.cwd, recent_commands=recent_commands)
        predictor = NeuralPredictor.from_artifact(load_artifact(model_dir))
        suggestions = predictor.suggest(
            SuggestionRequest(
                context_text=context.render(),
                typed_prefix_masked=mask_command(args.prefix),
            ),
            limit=args.limit,
        )
        candidates = tuple(
            {
                "suffix": item.suffix,
                "command": item.command,
                "score": item.score,
                "source": item.source,
            }
            for item in suggestions
        )
    if args.plain:
        if candidates:
            print(candidates[0]["suffix"])
    else:
        print(json.dumps({"source": "model", "candidates": candidates}, ensure_ascii=False))
    return 0


def _cmd_daemon_start(_args: argparse.Namespace) -> int:
    state = daemon.start()
    print(f"running pid={state.pid} socket={state.socket_path}")
    return 0


def _cmd_daemon_stop(_args: argparse.Namespace) -> int:
    print("stopped" if daemon.stop() else "not running")
    return 0


def _cmd_daemon_status(_args: argparse.Namespace) -> int:
    state = daemon.status()
    print(f"running pid={state.pid} socket={state.socket_path}" if state.running else "not running")
    return 0 if state.running else 1


def _cmd_model_verify(args: argparse.Namespace) -> int:
    loaded = load_artifact(args.path)
    print(f"valid {loaded.model_dir}")
    return 0


def _cmd_model_install(args: argparse.Namespace) -> int:
    loaded = install_model(args.path, name=args.name, force=args.force)
    print(f"installed {loaded.model_dir.name} at {loaded.model_dir}")
    return 0


def _cmd_model_list(_args: argparse.Namespace) -> int:
    for item in list_models():
        marker = "*" if item.active else " "
        print(f"{marker} {item.name}\t{item.model_dir}")
    return 0


def _cmd_model_current(_args: argparse.Namespace) -> int:
    current = next((item for item in list_models() if item.active), None)
    if current is None:
        print("none")
        return 1
    print(f"{current.name}\t{current.model_dir}")
    return 0


def _cmd_model_use(args: argparse.Namespace) -> int:
    selected = use_model(args.name)
    print(f"active {selected.name}")
    return 0


def _cmd_model_uninstall(args: argparse.Namespace) -> int:
    removed = uninstall_model(args.name)
    print(f"uninstalled {removed.name}")
    return 0


def _cmd_shell_init(args: argparse.Namespace) -> int:
    print(render_shell_init(args.shell), end="")
    return 0


def _cmd_install_shell(args: argparse.Namespace) -> int:
    print(install_shell(args.shell, rc_path=args.rc_file))
    return 0


def _cmd_uninstall_shell(args: argparse.Namespace) -> int:
    print(uninstall_shell(args.shell, rc_path=args.rc_file))
    return 0


def _cmd_doctor(args: argparse.Namespace) -> int:
    results = checks()
    for item in results:
        print(f"{'ok' if item.ok else 'fail'}\t{item.name}\t{item.detail}")
    failed_required = any(not item.ok and item.required for item in results)
    return 1 if args.strict and failed_required else 0


def _default_shell() -> str:
    return "bash" if Path(os.environ.get("SHELL", "")).name == "bash" else "zsh"


def _recent_commands(args: argparse.Namespace) -> list[str]:
    if not args.recent_stdin0:
        return list(args.recent)
    if args.recent:
        raise ValueError("--recent and --recent-stdin0 cannot be combined")
    return _read_recent_stdin0(sys.stdin.buffer)


def _read_recent_stdin0(stream: BinaryIO) -> list[str]:
    maximum_bytes = MAX_HISTORY * (MAX_INPUT_COMMAND_CHARS + 1)
    payload = stream.read(maximum_bytes + 1)
    if len(payload) > maximum_bytes:
        raise ValueError("NUL-delimited recent context exceeds the byte limit")
    if not payload:
        return []
    if not payload.endswith(b"\0"):
        raise ValueError("NUL-delimited recent context must end with NUL")
    entries = payload[:-1].split(b"\0")
    if len(entries) > MAX_HISTORY:
        raise ValueError(f"recent context may contain at most {MAX_HISTORY} entries")
    try:
        return [entry.decode("utf-8") for entry in entries]
    except UnicodeDecodeError as exc:
        raise ValueError("NUL-delimited recent context must be UTF-8") from exc


if __name__ == "__main__":
    raise SystemExit(main())
