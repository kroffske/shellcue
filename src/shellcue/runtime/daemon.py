"""Resident local inference process over a private Unix socket."""

from __future__ import annotations

import fcntl
import json
import math
import os
import signal
import socket
import socketserver
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shellcue.core.redaction import mask_command
from shellcue.core.safety import candidate_is_safe
from shellcue.models.artifact import ArtifactError, SuggestionRequest, load_artifact
from shellcue.models.neural import NeuralPredictor
from shellcue.models.registry import active_model_dir, cache_dir
from shellcue.models.standard_commands import STANDARD_COMMAND_POLICY_ID
from shellcue.runtime.context import RuntimeContext

DEFAULT_START_TIMEOUT = 60.0
SUGGESTION_SOURCES = frozenset({"model", STANDARD_COMMAND_POLICY_ID})


@dataclass(frozen=True)
class DaemonStatus:
    running: bool
    pid: int | None
    socket_path: Path


class _Server(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True

    def __init__(self, path: str, predictor: NeuralPredictor) -> None:
        self.predictor = predictor
        self.inference_lock = threading.Lock()
        super().__init__(path, _Handler)


class _Handler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        try:
            payload = json.loads(self.rfile.readline(1_048_576))
            response = _serve_serialized_suggestion(  # type: ignore[attr-defined]
                self.server.predictor,
                self.server.inference_lock,
                payload,
            )
        except (ArtifactError, RuntimeError, TypeError, ValueError, json.JSONDecodeError) as exc:
            response = {"ok": False, "error": str(exc)}
        try:
            self.wfile.write((json.dumps(response) + "\n").encode())
        except (BrokenPipeError, ConnectionResetError):
            return


def daemon_dir() -> Path:
    override = os.environ.get("SHELLCUE_DAEMON_DIR")
    return Path(override).expanduser() if override else cache_dir() / "daemon"


def socket_path() -> Path:
    override = os.environ.get("SHELLCUE_DAEMON_SOCKET")
    return Path(override).expanduser() if override else daemon_dir() / "shellcue.sock"


def pid_path() -> Path:
    return daemon_dir() / "shellcue.pid"


def log_path() -> Path:
    return daemon_dir() / "shellcue.log"


def lock_path() -> Path:
    return daemon_dir() / "shellcue.lock"


def status(timeout: float = 0.2) -> DaemonStatus:
    pid = _read_pid()
    running = pid is not None and _pid_alive(pid) and _probe_daemon_pid(timeout=timeout) == pid
    return DaemonStatus(running=running, pid=pid if running else None, socket_path=socket_path())


def start(timeout: float = DEFAULT_START_TIMEOUT) -> DaemonStatus:
    if timeout <= 0:
        raise ValueError("daemon startup timeout must be positive")
    current = status()
    if current.running:
        return current
    model_dir = active_model_dir()
    if model_dir is None:
        raise RuntimeError("no active model; run 'shellcue model install' first")
    load_artifact(model_dir)
    root = daemon_dir()
    root.mkdir(parents=True, exist_ok=True)
    if _lifetime_lock_held():
        return _wait_until_ready(timeout=timeout, process=None)
    log = log_path().open("ab")
    try:
        process = subprocess.Popen(
            [sys.executable, "-m", "shellcue.runtime.daemon"],
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            start_new_session=True,
            close_fds=True,
        )
    finally:
        log.close()
    return _wait_until_ready(timeout=timeout, process=process)


def _wait_until_ready(*, timeout: float, process: subprocess.Popen[bytes] | None) -> DaemonStatus:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        current = status()
        if current.running:
            return current
        if process is not None and process.poll() is not None and not _lifetime_lock_held():
            raise RuntimeError(f"daemon exited with code {process.returncode}; see {log_path()}")
        time.sleep(0.05)
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=3.0)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3.0)
    raise RuntimeError(f"daemon did not become ready; see {log_path()}")


def stop(timeout: float = 3.0) -> bool:
    pid = _read_pid()
    if pid is None:
        if pid_path().exists() or socket_path().exists():
            raise RuntimeError("daemon state exists but ownership cannot be confirmed")
        return False
    if not _pid_alive(pid) or _probe_daemon_pid(timeout=0.2) != pid:
        raise RuntimeError("refusing to signal an unconfirmed daemon PID")
    os.kill(pid, signal.SIGTERM)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _pid_alive(pid) and _probe_daemon_pid(timeout=0.05) is None:
            _cleanup_state(owner_pid=pid)
            return True
        time.sleep(0.05)
    raise RuntimeError("daemon termination was not confirmed before timeout")


def ping(timeout: float = 0.2) -> bool:
    return _probe_daemon_pid(timeout=timeout) is not None


def suggest(
    *, prefix: str, cwd: str | None, recent_commands: list[str], limit: int, timeout: float = 2.0
) -> tuple[dict[str, Any], ...]:
    response = request(
        {"op": "suggest", "prefix": prefix, "cwd": cwd, "recent": recent_commands, "limit": limit},
        timeout=timeout,
    )
    if response.get("ok") is not True:
        raise RuntimeError(str(response.get("error", "daemon request failed")))
    candidates = response.get("candidates")
    return _validate_response_candidates(candidates, prefix=prefix)


def request(payload: dict[str, Any], *, timeout: float) -> dict[str, Any]:
    data = (json.dumps(payload) + "\n").encode()
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(timeout)
            client.connect(str(socket_path()))
            client.sendall(data)
            received = bytearray()
            while not received.endswith(b"\n"):
                chunk = client.recv(65_536)
                if not chunk:
                    break
                received.extend(chunk)
    except TimeoutError as exc:
        raise RuntimeError(f"daemon request timed out after {timeout:g}s") from exc
    except OSError as exc:
        raise RuntimeError(f"daemon request failed: {exc}") from exc
    try:
        response = json.loads(received)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError("daemon returned invalid JSON") from exc
    if not isinstance(response, dict):
        raise RuntimeError("daemon returned a non-object response")
    return response


def serve_forever() -> int:
    root = daemon_dir()
    root.mkdir(parents=True, exist_ok=True)
    lock = lock_path().open("a+")
    try:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        lock.close()
        raise RuntimeError("another ShellCue daemon owns the runtime lock") from exc
    try:
        model_dir = active_model_dir()
        if model_dir is None:
            raise RuntimeError("no active model")
        predictor = NeuralPredictor.from_artifact(load_artifact(model_dir))
        _warm_predictor(predictor)
        sock = socket_path()
        sock.unlink(missing_ok=True)
        owner_pid = os.getpid()
        pid_path().write_text(f"{owner_pid}\n", encoding="utf-8")
        os.chmod(pid_path(), 0o600)
        server = _Server(str(sock), predictor)
        os.chmod(sock, 0o600)

        def shutdown(_signum: int, _frame: object) -> None:
            threading.Thread(target=server.shutdown, daemon=True).start()

        signal.signal(signal.SIGTERM, shutdown)
        try:
            server.serve_forever(poll_interval=0.1)
        finally:
            server.server_close()
            _cleanup_state(owner_pid=owner_pid)
    finally:
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        lock.close()
    return 0


def _serve_request(predictor: NeuralPredictor, payload: object) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("request must be an object")
    if payload.get("op") == "ping":
        return {"ok": True, "pid": os.getpid()}
    if payload.get("op") != "suggest":
        raise ValueError("unsupported daemon operation")
    prefix = payload.get("prefix")
    recent = payload.get("recent", [])
    cwd = payload.get("cwd")
    limit = payload.get("limit", 5)
    if not isinstance(prefix, str) or not isinstance(recent, list):
        raise ValueError("prefix and recent context have invalid types")
    if cwd is not None and not isinstance(cwd, str):
        raise ValueError("cwd must be a string or null")
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 10:
        raise ValueError("limit must be an integer from 1 to 10")
    context = RuntimeContext.capture(
        cwd=cwd,
        recent_commands=recent,
    )
    request_value = SuggestionRequest(
        context_text=context.render(), typed_prefix_masked=mask_command(prefix)
    )
    suggestions = predictor.suggest(request_value, limit=limit)
    return {
        "ok": True,
        "candidates": [
            {
                "suffix": item.suffix,
                "command": item.command,
                "score": item.score,
                "source": item.source,
            }
            for item in suggestions
        ],
    }


def _serve_serialized_suggestion(
    predictor: NeuralPredictor,
    inference_lock: threading.Lock,
    payload: object,
) -> dict[str, Any]:
    if isinstance(payload, dict) and payload.get("op") == "suggest":
        with inference_lock:
            return _serve_request(predictor, payload)
    return _serve_request(predictor, payload)


def _warm_predictor(predictor: NeuralPredictor) -> None:
    context = RuntimeContext.capture(cwd=None, recent_commands=()).render()
    predictor.suggest(
        SuggestionRequest(context_text=context, typed_prefix_masked="pytest -"),
        limit=1,
    )


def _read_pid() -> int | None:
    try:
        return int(pid_path().read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def _probe_daemon_pid(*, timeout: float) -> int | None:
    try:
        response = request({"op": "ping"}, timeout=timeout)
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError):
        return None
    pid = response.get("pid")
    if response.get("ok") is not True or not isinstance(pid, int) or isinstance(pid, bool):
        return None
    return pid if pid > 0 else None


def _validate_response_candidates(candidates: object, *, prefix: str) -> tuple[dict[str, Any], ...]:
    if not isinstance(candidates, list):
        raise RuntimeError("daemon candidates must be a list")
    masked_prefix = mask_command(prefix)
    validated: list[dict[str, Any]] = []
    expected_fields = {"suffix", "command", "score", "source"}
    for index, item in enumerate(candidates):
        if not isinstance(item, dict) or set(item) != expected_fields:
            raise RuntimeError(f"daemon candidate {index} has invalid fields")
        suffix = item["suffix"]
        command = item["command"]
        score = item["score"]
        source = item["source"]
        if (
            not isinstance(suffix, str)
            or not isinstance(command, str)
            or not isinstance(score, (int, float))
            or isinstance(score, bool)
            or not math.isfinite(float(score))
            or source not in SUGGESTION_SOURCES
            or command != masked_prefix + suffix
            or not candidate_is_safe(masked_prefix, suffix)
        ):
            raise RuntimeError(f"daemon candidate {index} violates the suggestion contract")
        validated.append(item)
    return tuple(validated)


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _lifetime_lock_held() -> bool:
    root = daemon_dir()
    root.mkdir(parents=True, exist_ok=True)
    with lock_path().open("a+") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
    return False


def _cleanup_state(*, owner_pid: int) -> None:
    if _read_pid() != owner_pid:
        return
    socket_path().unlink(missing_ok=True)
    pid_path().unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(serve_forever())
