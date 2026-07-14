from __future__ import annotations

from pathlib import Path

import pytest

from shellcue.models.artifact import Suggestion
from shellcue.runtime import daemon


class _FakePredictor:
    def suggest(self, request, *, limit: int):
        assert "<SECRET>" in request.context_text
        assert request.typed_prefix_masked == "git s"
        return (Suggestion(suffix="tatus", command="git status", score=-0.1),)


def test_daemon_request_masks_context_before_predictor() -> None:
    response = daemon._serve_request(
        _FakePredictor(),
        {
            "op": "suggest",
            "prefix": "git s",
            "cwd": "/Users/name/project",
            "recent": ["export API_TOKEN=abcdefghijklmnopqrstuvwxyz0123456789"],
            "limit": 1,
        },
    )

    assert response["ok"] is True
    assert response["candidates"][0]["source"] == "model"


def test_daemon_paths_use_shellcue_environment(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SHELLCUE_DAEMON_DIR", str(tmp_path))

    assert daemon.socket_path() == tmp_path / "shellcue.sock"
    assert daemon.pid_path() == tmp_path / "shellcue.pid"
    assert daemon.lock_path() == tmp_path / "shellcue.lock"


@pytest.mark.parametrize(
    "recent",
    [
        ["git status", 123],
        ["git status", ""],
        [f"echo {index}" for index in range(9)],
    ],
)
def test_daemon_rejects_every_invalid_recent_entry(recent: list[object]) -> None:
    with pytest.raises(ValueError, match="recent context"):
        daemon._serve_request(
            _FakePredictor(),
            {"op": "suggest", "prefix": "git s", "cwd": None, "recent": recent},
        )


def test_stop_refuses_stale_reused_pid_without_cleanup(monkeypatch) -> None:
    killed: list[tuple[int, int]] = []
    cleaned: list[bool] = []
    monkeypatch.setattr(daemon, "_read_pid", lambda: 8123)
    monkeypatch.setattr(daemon, "_pid_alive", lambda _pid: True)
    monkeypatch.setattr(daemon, "_probe_daemon_pid", lambda **_kwargs: None)
    monkeypatch.setattr(daemon.os, "kill", lambda pid, sig: killed.append((pid, sig)))
    monkeypatch.setattr(daemon, "_cleanup_state", lambda: cleaned.append(True))

    with pytest.raises(RuntimeError, match="unconfirmed daemon PID"):
        daemon.stop()

    assert killed == []
    assert cleaned == []


def test_stop_timeout_fails_without_cleanup(monkeypatch) -> None:
    killed: list[tuple[int, int]] = []
    cleaned: list[bool] = []
    times = iter((0.0, 1.0))
    monkeypatch.setattr(daemon, "_read_pid", lambda: 8123)
    monkeypatch.setattr(daemon, "_pid_alive", lambda _pid: True)
    monkeypatch.setattr(daemon, "_probe_daemon_pid", lambda **_kwargs: 8123)
    monkeypatch.setattr(daemon.os, "kill", lambda pid, sig: killed.append((pid, sig)))
    monkeypatch.setattr(daemon.time, "monotonic", lambda: next(times))
    monkeypatch.setattr(daemon, "_cleanup_state", lambda: cleaned.append(True))

    with pytest.raises(RuntimeError, match="termination was not confirmed"):
        daemon.stop(timeout=0.1)

    assert killed == [(8123, daemon.signal.SIGTERM)]
    assert cleaned == []


@pytest.mark.parametrize(
    "candidate",
    [
        "not-an-object",
        {"suffix": "tatus", "command": "git status", "score": -0.1},
        {"suffix": "tatus", "command": "wrong", "score": -0.1, "source": "model"},
        {
            "suffix": "; rm -rf /tmp/x",
            "command": "git s; rm -rf /tmp/x",
            "score": -0.1,
            "source": "model",
        },
        {"suffix": "tatus", "command": "git status", "score": float("nan"), "source": "model"},
    ],
)
def test_client_rejects_every_invalid_daemon_candidate(candidate: object, monkeypatch) -> None:
    monkeypatch.setattr(
        daemon,
        "request",
        lambda *_args, **_kwargs: {"ok": True, "candidates": [candidate]},
    )

    with pytest.raises(RuntimeError, match="daemon candidate"):
        daemon.suggest(
            prefix="git s", cwd=None, recent_commands=[], limit=1
        )
