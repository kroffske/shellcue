from __future__ import annotations

from shellcue.models.artifact import Suggestion
from shellcue.models.candidates import GeneratedCandidate, safe_suggestions
from shellcue.models.standard_commands import (
    STANDARD_COMMANDS,
    apply_standard_command_policy,
)


def suggestion(command: str, prefix: str, score: float = 0.0) -> Suggestion:
    return Suggestion(
        suffix=command[len(prefix) :],
        command=command,
        score=score,
    )


def test_invalid_known_family_candidate_uses_standard_fallback() -> None:
    prefix = "git s"

    result = apply_standard_command_policy(
        prefix,
        [suggestion("git sudo apt-get install git", prefix)],
        limit=1,
    )

    assert result[0].command.startswith(
        (
            "git shortlog",
            "git show",
            "git stage",
            "git stash",
            "git status",
            "git submodule",
            "git switch",
            "git symbolic-ref",
        )
    )
    assert "sudo" not in result[0].command


def test_valid_model_command_is_preserved_before_catalog_fallback() -> None:
    prefix = "git st"
    model = suggestion("git status --short", prefix, score=-0.1)

    assert apply_standard_command_policy(prefix, [model], limit=1) == (model,)


def test_valid_family_specific_arguments_are_not_reduced_to_catalog_roots() -> None:
    prefix = "find . -n"
    model = suggestion("find . -name '*.py'", prefix)

    assert apply_standard_command_policy(prefix, [model], limit=1) == (model,)


def test_command_names_are_allowed_as_regular_arguments() -> None:
    prefix = "pip ins"
    model = suggestion("pip install git", prefix)

    assert apply_standard_command_policy(prefix, [model], limit=1) == (model,)


def test_invalid_nested_subcommand_uses_nested_grammar_fallback() -> None:
    prefix = "docker compose u"

    result = apply_standard_command_policy(
        prefix,
        [suggestion("docker compose ucln", prefix)],
        limit=1,
    )

    assert result[0].command == "docker compose up"


def test_invalid_filesystem_options_use_valid_grammar_fallbacks() -> None:
    cases = (
        ("find . -t", "find . -t 'SYN_STR'", "find . -type d"),
        ("du -", "du -v", "du -h"),
        ("du -", 'du -n "SYN_STR"', "du -h"),
        ("chmod +", "chmod +v", "chmod +r"),
    )

    for prefix, invalid, expected in cases:
        result = apply_standard_command_policy(
            prefix,
            [suggestion(invalid, prefix)],
            limit=1,
        )
        assert result[0].command == expected


def test_shell_command_boundaries_are_never_suggested_for_known_families() -> None:
    cases = (
        ("git st", "git status && sudo /usr/bin/apt update"),
        ("git st", "git status;/usr/bin/apt update"),
        ("pip ins", "pip install requests | sh"),
    )

    for prefix, invalid in cases:
        result = apply_standard_command_policy(
            prefix,
            [suggestion(invalid, prefix)],
            limit=1,
        )
        assert result
        assert not any(operator in result[0].command for operator in ("&&", ";", "|"))


def test_command_and_process_substitution_are_rejected_after_candidate_safety() -> None:
    prefix = "git st"
    commands = (
        "git status $(sudo /usr/bin/apt update)",
        "git status `sudo /usr/bin/apt update`",
        "git status >$(/usr/bin/apt update)",
        "git status <(/usr/bin/apt update)",
    )

    for command in commands:
        safe = safe_suggestions(
            prefix,
            [GeneratedCandidate(command[len(prefix) :], -0.1)],
            limit=1,
        )
        assert safe
        result = apply_standard_command_policy(prefix, safe, limit=1)
        assert result
        assert result[0].command == "git status"
        assert result[0].source == "standard_command_catalog_v1"


def test_quoted_execution_markers_remain_inert_neural_arguments() -> None:
    prefix = "git commit -m "
    commands = (
        "git commit -m 'document $(command) literally'",
        "git commit -m 'use `ticks` literally'",
        "git commit -m 'redirect > nowhere; stay literal'",
        'git commit -m "separator ; stays literal"',
    )

    for command in commands:
        model = suggestion(command, prefix)
        assert apply_standard_command_policy(prefix, [model], limit=1) == (model,)


def test_execution_markers_inside_double_quotes_remain_rejected() -> None:
    prefix = "git commit -m "
    for command in (
        'git commit -m "run $(command)"',
        'git commit -m "run `command`"',
    ):
        result = apply_standard_command_policy(
            prefix,
            [suggestion(command, prefix)],
            limit=1,
        )
        assert result == ()


def test_partial_arguments_and_options_remain_neural_completions() -> None:
    cases = (
        ("git status --s", "git status --short"),
        ("git checkout fea", "git checkout feature"),
        ("pip install req", "pip install requests"),
        ("docker ps -", "docker ps -a"),
        ("git -C repo st", "git -C repo status"),
    )

    for prefix, command in cases:
        model = suggestion(command, prefix)
        assert apply_standard_command_policy(prefix, [model], limit=1) == (model,)


def test_declarative_global_options_preserve_valid_family_commands() -> None:
    cases = (
        ("git -p st", "git -p status"),
        ("git -P st", "git -P status"),
        ("git --no-optional-locks st", "git --no-optional-locks status"),
        ("git --no-lazy-fetch fe", "git --no-lazy-fetch fetch"),
        ("git --no-advice st", "git --no-advice status"),
        ("docker --context prod p", "docker --context prod ps"),
        ("kubectl -n prod g", "kubectl -n prod get pods"),
        ("systemctl --user st", "systemctl --user status"),
        (
            "systemctl --runtime en",
            "systemctl --runtime enable demo.service",
        ),
        ("npm --prefix app in", "npm --prefix app install"),
    )

    for prefix, command in cases:
        model = suggestion(command, prefix)
        assert apply_standard_command_policy(prefix, [model], limit=1) == (model,)


def test_complete_standard_commands_abstain_until_more_input_arrives() -> None:
    assert (
        apply_standard_command_policy(
            "docker ps",
            [suggestion("docker ps -a", "docker ps")],
            limit=1,
        )
        == ()
    )
    assert apply_standard_command_policy("docker ps ", [], limit=1) == ()
    assert (
        apply_standard_command_policy(
            "git status",
            [suggestion("git status --short", "git status")],
            limit=1,
        )
        == ()
    )
    assert (
        apply_standard_command_policy(
            "git status ",
            [suggestion("git status --short", "git status ")],
            limit=1,
        )[0].command
        == "git status --short"
    )


def test_unknown_command_family_keeps_neural_output() -> None:
    prefix = "custom "
    model = suggestion("custom deploy", prefix)

    assert apply_standard_command_policy(prefix, [model], limit=1) == (model,)


def test_catalog_fallback_has_a_distinct_source() -> None:
    result = apply_standard_command_policy("git st", [], limit=1)

    assert result[0].source == "standard_command_catalog_v1"


def test_catalog_covers_all_frozen_standard_command_families() -> None:
    cases = (
        (
            "git s",
            (
                "git shortlog",
                "git show",
                "git show-branch",
                "git stage",
                "git stash",
                "git status",
                "git submodule",
                "git switch",
                "git symbolic-ref",
            ),
        ),
        ("git st", ("git stage", "git stash", "git status")),
        ("git ch", ("git checkout", "git cherry", "git cherry-pick")),
        (
            "git re",
            (
                "git rebase",
                "git reflog",
                "git remote",
                "git reset",
                "git restore",
                "git revert",
                "git rev-list",
                "git rev-parse",
            ),
        ),
        ("ls -", ("ls -a", "ls -l", "ls -la", "ls -lh")),
        ("find . -t", ("find . -type d", "find . -type f")),
        ("du -", ("du -h", "du -sh")),
        ("chmod +", ("chmod +r", "chmod +w", "chmod +x")),
        ("python -", ("python --version", "python -c", "python -m")),
        ("python -m p", ("python -m pip", "python -m pytest")),
        ("pytest -", ("pytest --lf", "pytest --maxfail=1", "pytest -q", "pytest -x")),
        ("pip ins", ("pip install",)),
        ("brew in", ("brew info", "brew install")),
        ("brew un", ("brew uninstall", "brew unlink", "brew unpin", "brew untap")),
        ("npm in", ("npm init", "npm install")),
        ("apt-get in", ("apt-get install",)),
        (
            "docker p",
            (
                "docker pause",
                "docker plugin",
                "docker port",
                "docker ps",
                "docker pull",
                "docker push",
            ),
        ),
        ("docker co", ("docker commit", "docker compose", "docker container", "docker context")),
        ("docker compose u", ("docker compose up",)),
        ("kubectl g", ("kubectl get",)),
        ("systemctl st", ("systemctl start", "systemctl status", "systemctl stop")),
        ("launchctl p", ("launchctl print", "launchctl print-cache", "launchctl print-disabled")),
        ("ps a", ("ps aux", "ps ax")),
        ("pgrep -", ("pgrep -a", "pgrep -f", "pgrep -l", "pgrep -n")),
    )

    for prefix, accepted_roots in cases:
        result = apply_standard_command_policy(prefix, [], limit=1)
        assert result
        assert any(
            result[0].command == root or result[0].command.startswith(f"{root} ")
            for root in accepted_roots
        )


def test_all_frozen_complete_commands_abstain() -> None:
    complete = (
        "git status --short --branch",
        "git rev-parse --show-toplevel",
        "pwd",
        "whoami",
        "python --version",
        "pytest --version",
        "brew update",
        "npm --version",
        "docker ps",
        "kubectl version --client",
        "ps aux",
        "launchctl list",
    )

    for prefix in complete:
        assert (
            apply_standard_command_policy(
                prefix,
                [suggestion(f"{prefix} unexpected", prefix)],
                limit=1,
            )
            == ()
        )


def test_every_catalog_entry_is_reachable_without_crossing_command_family() -> None:
    for command in STANDARD_COMMANDS:
        if " " not in command:
            continue
        prefix = command[:-1]
        result = apply_standard_command_policy(prefix, [], limit=5)
        head = command.split(maxsplit=1)[0]

        assert result
        assert all(item.command.startswith(prefix) for item in result)
        assert all(item.command.split(maxsplit=1)[0] == head for item in result)
