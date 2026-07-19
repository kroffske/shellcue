"""Generalized standard-command validation and prefix completion."""

from __future__ import annotations

import re
import shlex
from collections.abc import Iterable

from shellcue.models.artifact import Suggestion

STANDARD_COMMAND_POLICY_ID = "standard_command_catalog_v1"
_SUBCOMMANDS = {
    "git": (
        "status",
        "add",
        "am",
        "annotate",
        "apply",
        "archive",
        "bisect",
        "blame",
        "branch",
        "bundle",
        "checkout",
        "cherry",
        "cherry-pick",
        "clean",
        "clone",
        "commit",
        "config",
        "describe",
        "diff",
        "fetch",
        "format-patch",
        "fsck",
        "gc",
        "grep",
        "help",
        "init",
        "log",
        "merge",
        "mv",
        "notes",
        "pull",
        "push",
        "range-diff",
        "rebase",
        "reflog",
        "remote",
        "reset",
        "restore",
        "revert",
        "rev-list",
        "rev-parse",
        "rm",
        "shortlog",
        "show",
        "show-branch",
        "stage",
        "stash",
        "submodule",
        "switch",
        "symbolic-ref",
        "tag",
        "worktree",
    ),
    "brew": (
        "autoremove",
        "cleanup",
        "config",
        "deps",
        "doctor",
        "fetch",
        "info",
        "install",
        "leaves",
        "link",
        "list",
        "outdated",
        "pin",
        "reinstall",
        "search",
        "services",
        "tap",
        "uninstall",
        "unlink",
        "unpin",
        "untap",
        "update",
        "upgrade",
        "uses",
    ),
    "npm": (
        "adduser",
        "audit",
        "ci",
        "config",
        "exec",
        "help",
        "init",
        "install",
        "link",
        "list",
        "login",
        "outdated",
        "pack",
        "publish",
        "rebuild",
        "run",
        "start",
        "test",
        "uninstall",
        "update",
        "version",
        "view",
    ),
    "pnpm": (
        "add",
        "approve-builds",
        "audit",
        "config",
        "create",
        "deploy",
        "dlx",
        "exec",
        "fetch",
        "import",
        "init",
        "install",
        "link",
        "list",
        "outdated",
        "pack",
        "publish",
        "rebuild",
        "remove",
        "run",
        "start",
        "store",
        "test",
        "unlink",
        "update",
        "why",
    ),
    "apt": (
        "autoremove",
        "clean",
        "download",
        "install",
        "list",
        "purge",
        "remove",
        "search",
        "show",
        "update",
        "upgrade",
    ),
    "apt-get": (
        "autoremove",
        "clean",
        "dist-upgrade",
        "download",
        "install",
        "purge",
        "remove",
        "source",
        "update",
        "upgrade",
    ),
    "pip": (
        "install",
        "cache",
        "check",
        "config",
        "debug",
        "download",
        "freeze",
        "hash",
        "help",
        "index",
        "inspect",
        "list",
        "show",
        "uninstall",
        "wheel",
    ),
    "pip3": (
        "install",
        "cache",
        "check",
        "config",
        "debug",
        "download",
        "freeze",
        "hash",
        "help",
        "index",
        "inspect",
        "list",
        "show",
        "uninstall",
        "wheel",
    ),
    "uv": (
        "add",
        "build",
        "cache",
        "export",
        "init",
        "lock",
        "pip",
        "publish",
        "remove",
        "run",
        "ruff",
        "self",
        "sync",
        "tool",
        "tree",
        "venv",
        "version",
    ),
    "cargo": (
        "add",
        "bench",
        "build",
        "check",
        "clean",
        "doc",
        "fetch",
        "fix",
        "generate-lockfile",
        "help",
        "init",
        "install",
        "login",
        "metadata",
        "new",
        "owner",
        "package",
        "publish",
        "remove",
        "run",
        "search",
        "test",
        "tree",
        "uninstall",
        "update",
        "vendor",
        "verify-project",
        "version",
        "yank",
    ),
    "yarn": (
        "add",
        "cache",
        "config",
        "create",
        "dlx",
        "exec",
        "info",
        "init",
        "install",
        "link",
        "npm",
        "pack",
        "patch",
        "plugin",
        "remove",
        "run",
        "set",
        "stage",
        "unplug",
        "up",
        "why",
        "workspace",
        "workspaces",
    ),
    "docker": (
        "ps",
        "attach",
        "build",
        "builder",
        "commit",
        "compose",
        "container",
        "context",
        "cp",
        "create",
        "diff",
        "events",
        "exec",
        "export",
        "history",
        "image",
        "images",
        "import",
        "info",
        "inspect",
        "kill",
        "load",
        "login",
        "logout",
        "logs",
        "network",
        "pause",
        "plugin",
        "port",
        "pull",
        "push",
        "rename",
        "restart",
        "rm",
        "rmi",
        "run",
        "save",
        "search",
        "start",
        "stats",
        "stop",
        "system",
        "tag",
        "top",
        "unpause",
        "update",
        "version",
        "volume",
        "wait",
    ),
    "kubectl": (
        "annotate",
        "api-resources",
        "api-versions",
        "apply",
        "attach",
        "auth",
        "autoscale",
        "certificate",
        "cluster-info",
        "completion",
        "config",
        "cordon",
        "cp",
        "create",
        "debug",
        "delete",
        "describe",
        "diff",
        "drain",
        "edit",
        "exec",
        "explain",
        "expose",
        "get",
        "kustomize",
        "label",
        "logs",
        "options",
        "patch",
        "plugin",
        "port-forward",
        "proxy",
        "replace",
        "rollout",
        "run",
        "scale",
        "set",
        "taint",
        "top",
        "uncordon",
        "version",
        "wait",
    ),
    "systemctl": (
        "status",
        "cat",
        "daemon-reload",
        "disable",
        "edit",
        "enable",
        "get-default",
        "is-active",
        "is-enabled",
        "is-failed",
        "list-dependencies",
        "list-jobs",
        "list-sockets",
        "list-timers",
        "list-unit-files",
        "list-units",
        "mask",
        "reload",
        "reset-failed",
        "restart",
        "show",
        "start",
        "stop",
        "try-restart",
        "unmask",
    ),
    "launchctl": (
        "print",
        "asuser",
        "attach",
        "blame",
        "bootstrap",
        "bootout",
        "config",
        "debug",
        "disable",
        "dumpstate",
        "enable",
        "error",
        "examine",
        "help",
        "kickstart",
        "kill",
        "limit",
        "list",
        "managername",
        "managerpid",
        "manageruid",
        "print-cache",
        "print-disabled",
        "procinfo",
        "reboot",
        "resolveport",
        "runstats",
        "setenv",
        "setumask",
        "spawn",
        "start",
        "stop",
        "submit",
        "uncache",
        "unload",
        "unsetenv",
    ),
}
_NESTED_SUBCOMMANDS = {
    ("docker", "compose"): (
        "up",
        "build",
        "config",
        "down",
        "exec",
        "images",
        "kill",
        "logs",
        "pause",
        "port",
        "ps",
        "pull",
        "push",
        "restart",
        "rm",
        "run",
        "start",
        "stop",
        "top",
        "unpause",
        "version",
        "watch",
    )
}
_FIXED_COMMANDS = (
    "pwd",
    "whoami",
    "ls -a",
    "ls -l",
    "ls -la",
    "ls -lh",
    "find . -type d",
    "find . -type f",
    "du -h",
    "du -sh",
    "chmod +r",
    "chmod +w",
    "chmod +x",
    "python --version",
    "python -c",
    "python -m",
    "python -m compileall",
    "python -m http.server",
    "python -m json.tool",
    "python -m pip",
    "python -m pytest",
    "python -m unittest",
    "python -m venv",
    "python3 --version",
    "python3 -c",
    "python3 -m",
    "python3 -m compileall",
    "python3 -m http.server",
    "python3 -m json.tool",
    "python3 -m pip",
    "python3 -m pytest",
    "python3 -m unittest",
    "python3 -m venv",
    "pytest --lf",
    "pytest --maxfail=1",
    "pytest -q",
    "pytest -x",
    "ps aux",
    "ps ax",
    "pgrep -a",
    "pgrep -f",
    "pgrep -l",
    "pgrep -n",
    "journalctl -b",
    "journalctl -f",
    "journalctl -k",
    "journalctl -u",
    "tar -cf",
    "tar -tf",
    "tar -xf",
)
STANDARD_COMMANDS = tuple(
    dict.fromkeys(
        (
            *_FIXED_COMMANDS,
            *(
                f"{command} {subcommand}"
                for command, subcommands in _SUBCOMMANDS.items()
                for subcommand in subcommands
            ),
            *(
                f"{' '.join(command)} {subcommand}"
                for command, subcommands in _NESTED_SUBCOMMANDS.items()
                for subcommand in subcommands
            ),
        )
    )
)
STANDARD_COMMAND_HEADS = frozenset({command.split(maxsplit=1)[0] for command in STANDARD_COMMANDS})
_OPTION_OR_ARGUMENT_HEADS = frozenset(
    {
        "chmod",
        "du",
        "find",
        "journalctl",
        "ls",
        "pgrep",
        "ps",
        "pytest",
        "pwd",
        "tar",
        "whoami",
    }
)
_FIND_EXPRESSIONS = frozenset(
    {
        "-delete",
        "-empty",
        "-exec",
        "-execdir",
        "-false",
        "-fstype",
        "-gid",
        "-group",
        "-ilname",
        "-iname",
        "-inum",
        "-ipath",
        "-iregex",
        "-links",
        "-lname",
        "-ls",
        "-maxdepth",
        "-mindepth",
        "-mmin",
        "-mount",
        "-mtime",
        "-name",
        "-newer",
        "-nogroup",
        "-nouser",
        "-path",
        "-perm",
        "-print",
        "-print0",
        "-printf",
        "-prune",
        "-readable",
        "-regex",
        "-samefile",
        "-size",
        "-true",
        "-type",
        "-uid",
        "-user",
        "-wholename",
        "-writable",
        "-xdev",
    }
)
_DU_SHORT_OPTIONS = frozenset("0aBbcDdhHkLlmPstx")
_CHMOD_SYMBOLIC_RE = re.compile(r"(?:[ugoa]*[+=-][rwxXstugo]+)(?:,[ugoa]*[+=-][rwxXstugo]+)*")
_GLOBAL_OPTIONS_WITH_VALUE = {
    "apt": frozenset({"-o", "--option"}),
    "apt-get": frozenset({"-o", "--option"}),
    "brew": frozenset({"--cache", "--repository"}),
    "docker": frozenset(
        {
            "-H",
            "-l",
            "--config",
            "--context",
            "--host",
            "--log-level",
            "--tlscacert",
            "--tlscert",
            "--tlskey",
        }
    ),
    "git": frozenset({"-C", "-c", "--git-dir", "--namespace", "--work-tree"}),
    "kubectl": frozenset(
        {
            "-n",
            "--as",
            "--as-group",
            "--cache-dir",
            "--certificate-authority",
            "--client-certificate",
            "--client-key",
            "--cluster",
            "--context",
            "--kubeconfig",
            "--namespace",
            "--request-timeout",
            "--server",
            "--token",
            "--user",
        }
    ),
    "npm": frozenset({"--prefix", "--registry", "--userconfig", "--workspace"}),
    "pip": frozenset({"--python"}),
    "pip3": frozenset({"--python"}),
    "pnpm": frozenset({"--dir", "--global-dir", "--store-dir"}),
    "systemctl": frozenset(
        {
            "-H",
            "-M",
            "-p",
            "-t",
            "--host",
            "--machine",
            "--property",
            "--root",
            "--state",
            "--type",
        }
    ),
    "uv": frozenset({"--directory", "--project"}),
    "yarn": frozenset({"--cwd"}),
}
_GLOBAL_OPTIONS_WITHOUT_VALUE = {
    "apt": frozenset({"-q", "-y", "--assume-yes", "--quiet"}),
    "apt-get": frozenset({"-q", "-y", "--assume-yes", "--quiet"}),
    "brew": frozenset({"-d", "-q", "-v", "--debug", "--quiet", "--verbose"}),
    "docker": frozenset({"-D", "--debug", "--tls", "--tlsverify"}),
    "git": frozenset(
        {
            "-P",
            "-p",
            "--bare",
            "--literal-pathspecs",
            "--no-advice",
            "--no-lazy-fetch",
            "--no-optional-locks",
            "--no-pager",
            "--no-replace-objects",
            "--paginate",
        }
    ),
    "kubectl": frozenset(
        {
            "--disable-compression",
            "--insecure-skip-tls-verify",
            "--match-server-version",
            "--warnings-as-errors",
        }
    ),
    "npm": frozenset({"-g", "-s", "--global", "--silent"}),
    "pip": frozenset(
        {
            "--disable-pip-version-check",
            "--isolated",
            "--no-color",
            "--require-virtualenv",
        }
    ),
    "pip3": frozenset(
        {
            "--disable-pip-version-check",
            "--isolated",
            "--no-color",
            "--require-virtualenv",
        }
    ),
    "pnpm": frozenset({"-g", "--global", "--offline"}),
    "systemctl": frozenset(
        {
            "-a",
            "-q",
            "--all",
            "--failed",
            "--global",
            "--no-legend",
            "--no-pager",
            "--plain",
            "--quiet",
            "--runtime",
            "--system",
            "--user",
        }
    ),
    "uv": frozenset({"--no-cache", "--offline"}),
    "yarn": frozenset({"--json", "--silent", "--verbose"}),
}


def apply_standard_command_policy(
    prefix: str,
    suggestions: Iterable[Suggestion],
    *,
    limit: int,
) -> tuple[Suggestion, ...]:
    """Filter known families and fill invalid/empty results from the command grammar."""

    candidates = tuple(suggestions)
    if limit < 1:
        return ()
    head = prefix.split(maxsplit=1)[0] if prefix.strip() else ""
    if head not in STANDARD_COMMAND_HEADS:
        return candidates[:limit]

    complete_prefix = _is_complete_standard_prefix(prefix)
    accepted: list[Suggestion] = []
    seen: set[str] = set()
    for suggestion in candidates:
        if (
            not suggestion.command.startswith(prefix)
            or (complete_prefix and suggestion.suffix[:1].isspace())
            or not _is_standard_command(suggestion.command)
            or suggestion.command in seen
        ):
            continue
        accepted.append(suggestion)
        seen.add(suggestion.command)
        if len(accepted) >= limit:
            return tuple(accepted)

    fallback_score = min((item.score for item in candidates), default=0.0) - 1.0
    for command in STANDARD_COMMANDS:
        if command == prefix or not command.startswith(prefix) or command in seen:
            continue
        accepted.append(
            Suggestion(
                suffix=command[len(prefix) :],
                command=command,
                score=fallback_score,
                source=STANDARD_COMMAND_POLICY_ID,
            )
        )
        seen.add(command)
        fallback_score -= 1.0
        if len(accepted) >= limit:
            break
    return tuple(accepted)


def _is_standard_command(command: str) -> bool:
    try:
        tokens = _shell_tokens(command)
    except ValueError:
        return False
    if not tokens or _has_active_shell_syntax(command):
        return False
    head = tokens[0]
    if head in _SUBCOMMANDS:
        if len(tokens) < 2:
            return True
        subcommand_index = _subcommand_index(head, tokens)
        if subcommand_index is None:
            return False
        subcommand = tokens[subcommand_index]
        if subcommand in {"--help", "--version", "-h", "-v"}:
            if subcommand_index != 1:
                return False
        elif subcommand not in _SUBCOMMANDS[head]:
            return False
        else:
            subcommand_end = subcommand_index + 1
            nested = (head, subcommand)
            if (
                nested in _NESTED_SUBCOMMANDS
                and len(tokens) > subcommand_end
                and tokens[subcommand_end] not in _NESTED_SUBCOMMANDS[nested]
            ):
                return False
    elif head in {"python", "python3"}:
        if len(tokens) >= 2 and not tokens[1].startswith("-"):
            return False
    elif head not in _OPTION_OR_ARGUMENT_HEADS:
        return False
    return _arguments_valid(head, tokens)


def _is_complete_standard_prefix(prefix: str) -> bool:
    if not prefix or prefix[-1].isspace():
        return False
    if any(command.startswith(f"{prefix} ") for command in STANDARD_COMMANDS):
        return False
    return _is_standard_command(prefix)


def _shell_tokens(command: str) -> list[str]:
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|<>")
    lexer.whitespace_split = True
    lexer.commenters = ""
    return list(lexer)


def _has_active_shell_syntax(command: str) -> bool:
    """Detect execution boundaries while allowing inert quoted literals."""

    single_quoted = False
    double_quoted = False
    index = 0
    while index < len(command):
        character = command[index]
        if character == "\\" and not single_quoted:
            index += 2
            continue
        if character == "'" and not double_quoted:
            single_quoted = not single_quoted
            index += 1
            continue
        if character == '"' and not single_quoted:
            double_quoted = not double_quoted
            index += 1
            continue
        if single_quoted:
            index += 1
            continue
        if command.startswith("$(", index) or character == "`":
            return True
        if not double_quoted and character in ";&|<>":
            return True
        index += 1
    return False


def _subcommand_index(head: str, tokens: list[str]) -> int | None:
    if len(tokens) < 2:
        return None
    if tokens[1] in {"--help", "--version", "-h", "-v"}:
        return 1
    if not tokens[1].startswith("-"):
        return 1
    index = 1
    options_with_value = _GLOBAL_OPTIONS_WITH_VALUE.get(head, frozenset())
    options_without_value = _GLOBAL_OPTIONS_WITHOUT_VALUE.get(head, frozenset())
    while index < len(tokens) and tokens[index].startswith("-"):
        option = tokens[index]
        if option in options_with_value:
            index += 2
        elif option in options_without_value or any(
            option.startswith(f"{name}=") for name in options_with_value
        ):
            index += 1
        else:
            return None
    return index if index < len(tokens) else None


def _arguments_valid(head: str, tokens: list[str]) -> bool:
    if head == "find":
        return all(
            token in _FIND_EXPRESSIONS
            for token in tokens[2:]
            if token.startswith("-") and token not in {"-H", "-L", "-P"}
        )
    if head == "du":
        return all(
            token.startswith("--") or all(character in _DU_SHORT_OPTIONS for character in token[1:])
            for token in tokens[1:]
            if token.startswith("-") and token != "-"
        )
    if head == "chmod":
        mode = next(
            (
                token
                for token in tokens[1:]
                if not token.startswith("-") or token.startswith(("+", "="))
            ),
            "",
        )
        return bool(
            mode and (re.fullmatch(r"[0-7]{3,4}", mode) or _CHMOD_SYMBOLIC_RE.fullmatch(mode))
        )
    return True
