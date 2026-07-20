from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from shellcue.models.artifact import Suggestion
from shellcue.runtime import daemon


class _FakePredictor:
    def suggest(self, request, *, limit: int):
        # Context stays masked; the typed prefix reaches the model complete.
        # docs/contracts/autocomplete-v2.md:11-12 — `recent_commands` are
        # "already-masked", `typed_prefix` is "complete text visible at the
        # shell prompt".
        assert "<SECRET>" in "\n".join(request.recent_commands)
        assert request.typed_prefix == "git s"
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


def test_request_normalizes_socket_timeout(monkeypatch) -> None:
    class _TimedOutSocket:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def settimeout(self, _timeout):
            return None

        def connect(self, _path):
            return None

        def sendall(self, _data):
            return None

        def recv(self, _size):
            raise TimeoutError("timed out")

    monkeypatch.setattr(daemon.socket, "socket", lambda *_args, **_kwargs: _TimedOutSocket())

    with pytest.raises(RuntimeError, match="timed out"):
        daemon.request({"op": "suggest"}, timeout=0.1)


def test_suggestion_requests_are_serialized() -> None:
    active = 0
    overlap = False
    barrier = threading.Barrier(2)
    lock = threading.Lock()

    class _SlowPredictor:
        def suggest(self, _request, *, limit):
            nonlocal active, overlap
            with lock:
                active += 1
                overlap = overlap or active > 1
            time.sleep(0.02)
            with lock:
                active -= 1
            return ()

    predictor = _SlowPredictor()
    inference_lock = threading.Lock()

    def invoke() -> None:
        barrier.wait()
        daemon._serve_serialized_suggestion(
            predictor,
            inference_lock,
            {"op": "suggest", "prefix": "git s", "cwd": None, "recent": []},
        )

    threads = [threading.Thread(target=invoke) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=1)

    assert not overlap


def test_warmup_runs_real_predictor_path() -> None:
    seen: list[tuple[str, int]] = []

    class _Predictor:
        def suggest(self, request, *, limit):
            seen.append((request.typed_prefix, limit))
            return ()

    daemon._warm_predictor(_Predictor())

    assert seen == [("pytest -", 1)]


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
        daemon.suggest(prefix="git s", cwd=None, recent_commands=[], limit=1)


def test_client_rejects_non_model_candidate_source(monkeypatch) -> None:
    monkeypatch.setattr(
        daemon,
        "request",
        lambda *_args, **_kwargs: {
            "ok": True,
            "candidates": [
                {
                    "suffix": "tatus",
                    "command": "git status",
                    "score": -1.0,
                    "source": "standard_command_catalog_v1",
                }
            ],
        },
    )

    with pytest.raises(RuntimeError, match="daemon candidate"):
        daemon.suggest(
            prefix="git s",
            cwd=None,
            recent_commands=[],
            limit=1,
        )


class _FakeProcess:
    returncode: int | None = None

    def __init__(self) -> None:
        self.terminated = False
        self.killed = False
        self.waits: list[float] = []

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.killed = True

    def wait(self, timeout: float) -> int:
        self.waits.append(timeout)
        self.returncode = -15 if not self.killed else -9
        return self.returncode


def test_start_timeout_terminates_only_retained_child(monkeypatch) -> None:
    process = _FakeProcess()
    stopped = daemon.DaemonStatus(False, None, Path("/tmp/not-ready.sock"))
    times = iter((0.0, 1.0))
    monkeypatch.setattr(daemon, "status", lambda: stopped)
    monkeypatch.setattr(daemon.time, "monotonic", lambda: next(times))

    with pytest.raises(RuntimeError, match="did not become ready"):
        daemon._wait_until_ready(timeout=0.1, process=process)  # type: ignore[arg-type]

    assert process.terminated is True
    assert process.killed is False
    assert process.waits == [3.0]


def test_cleanup_does_not_remove_replacement_state(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SHELLCUE_DAEMON_DIR", str(tmp_path))
    daemon.pid_path().write_text("9002\n", encoding="utf-8")
    daemon.socket_path().write_text("replacement", encoding="utf-8")

    daemon._cleanup_state(owner_pid=9001)

    assert daemon.pid_path().read_text(encoding="utf-8") == "9002\n"
    assert daemon.socket_path().read_text(encoding="utf-8") == "replacement"


def test_start_waits_for_lock_owner_without_spawning(tmp_path: Path, monkeypatch) -> None:
    model = tmp_path / "model"
    model.mkdir()
    stopped = daemon.DaemonStatus(False, None, tmp_path / "daemon.sock")
    running = daemon.DaemonStatus(True, 8123, tmp_path / "daemon.sock")
    statuses = iter((stopped, running))
    monkeypatch.setattr(daemon, "status", lambda: next(statuses))
    monkeypatch.setattr(daemon, "active_model_dir", lambda: model)
    monkeypatch.setattr(daemon, "load_artifact", lambda _path: object())
    monkeypatch.setattr(daemon, "_lifetime_lock_held", lambda: True)
    monkeypatch.setattr(
        daemon.subprocess,
        "Popen",
        lambda *_args, **_kwargs: pytest.fail("must not spawn while lifetime lock is held"),
    )

    assert daemon.start(timeout=1.0) == running
