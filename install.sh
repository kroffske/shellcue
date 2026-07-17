#!/usr/bin/env bash

set -euo pipefail

UV_VERSION="0.11.28"
PYTHON_VERSION="3.12"
EXPECTED_VERSION="0.1.0a4"
MODEL_REPO="kroffske/shellcue-lfm2.5-230m-alpha"
MODEL_REVISION="ae5b48546645926a6839df554a46596a8a19498e"
MODEL_NAME="shellcue-alpha"
MODEL_WEIGHTS_SHA256="c4f7973c48eb04fa2e8013f0d03171fcfb4ee27c157dea31e96020b12b84fb53"
MODEL_CHECKSUMS_SHA256="d781bffab68c5c667eb28f9a1591a7bb2347c16a63f39893f45d118eae5f4025"
HF_TOOL="huggingface_hub==0.35.0"

SOURCE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_URL="${SHELLCUE_PACKAGE_URL:-}"
PACKAGE_SHA256="${SHELLCUE_PACKAGE_SHA256:-}"
TARGET_SHELL="${SHELLCUE_SHELL:-${SHELL##*/}}"
SERVICE_READY_TIMEOUT="${SHELLCUE_SERVICE_READY_TIMEOUT:-120}"
STAGING_DIR=""

say() {
  printf 'shellcue-install: %s\n' "$*"
}

fail() {
  printf 'shellcue-install: %s\n' "$*" >&2
  exit 2
}

cleanup() {
  if [[ -n "$STAGING_DIR" && -d "$STAGING_DIR" ]]; then
    rm -rf "$STAGING_DIR"
  fi
}
trap cleanup EXIT INT TERM

sha256_file() {
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | awk '{print $1}'
  elif command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    fail "neither shasum nor sha256sum is available"
  fi
}

validate_install_source() {
  if [[ -z "$PACKAGE_URL" ]]; then
    [[ -z "$PACKAGE_SHA256" ]] || fail \
      "SHELLCUE_PACKAGE_SHA256 requires SHELLCUE_PACKAGE_URL"
    [[ -f "$SOURCE_DIR/pyproject.toml" && -d "$SOURCE_DIR/src/shellcue" ]] || fail \
      "source checkout is incomplete; clone the ShellCue repository before running install.sh"
    return
  fi
  [[ "$PACKAGE_SHA256" =~ ^[0-9a-f]{64}$ ]] || fail \
    "set SHELLCUE_PACKAGE_SHA256 to the exact 64-character lowercase SHA-256"
}

install_uv() {
  if command -v uv >/dev/null 2>&1; then
    return
  fi
  command -v curl >/dev/null 2>&1 || fail "curl is required to install uv"
  say "installing uv ${UV_VERSION}"
  curl -LsSf "https://astral.sh/uv/${UV_VERSION}/install.sh" | sh
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
  command -v uv >/dev/null 2>&1 || fail "uv installed but is not on PATH"
}

install_tool() {
  local install_source="$SOURCE_DIR"
  if [[ -n "$PACKAGE_URL" ]]; then
    install_source="$STAGING_DIR/shellcue.tar.gz"
    say "downloading digest-bound ShellCue package"
    curl -fL "$PACKAGE_URL" -o "$install_source"
    local actual
    actual="$(sha256_file "$install_source")"
    [[ "$actual" == "$PACKAGE_SHA256" ]] || fail \
      "package SHA-256 mismatch: expected ${PACKAGE_SHA256}, got ${actual}"
  else
    say "installing ShellCue from source checkout at $SOURCE_DIR"
  fi
  stop_current_shellcue
  uv tool install --force --python "$PYTHON_VERSION" --torch-backend cpu "$install_source"
  local tool_bin
  tool_bin="$(uv tool dir --bin)"
  export PATH="$tool_bin:$PATH"
  command -v shellcue >/dev/null 2>&1 || fail "uv installed ShellCue but its bin dir is not on PATH"
  [[ "$(shellcue --version)" == "shellcue ${EXPECTED_VERSION}" ]] || fail \
    "unexpected ShellCue version"
}

stop_current_shellcue() {
  if ! command -v shellcue >/dev/null 2>&1; then
    return
  fi
  shellcue service stop >/dev/null 2>&1 || shellcue daemon stop >/dev/null 2>&1 || true
}

current_model_path() {
  local current
  current="$(shellcue model current 2>/dev/null || true)"
  [[ "$current" == *$'\t'* ]] || return 1
  printf '%s\n' "${current#*$'\t'}"
}

model_is_accepted() {
  local model_dir="$1"
  [[ -f "$model_dir/model.safetensors" && -f "$model_dir/checksums.sha256" ]] || return 1
  [[ "$(sha256_file "$model_dir/model.safetensors")" == "$MODEL_WEIGHTS_SHA256" ]] || return 1
  [[ "$(sha256_file "$model_dir/checksums.sha256")" == "$MODEL_CHECKSUMS_SHA256" ]] || return 1
  if command -v shasum >/dev/null 2>&1; then
    (cd "$model_dir" && shasum -a 256 -c checksums.sha256 >/dev/null) || return 1
  else
    (cd "$model_dir" && sha256sum -c checksums.sha256 >/dev/null) || return 1
  fi
  shellcue model verify "$model_dir" >/dev/null
}

install_model() {
  local current=""
  current="$(current_model_path || true)"
  if [[ -n "$current" ]] && model_is_accepted "$current"; then
    say "reusing exact verified model snapshot at $current"
    return
  fi
  local model_dir="$STAGING_DIR/model"
  say "downloading ${MODEL_REPO} at immutable revision ${MODEL_REVISION}"
  uvx --from "$HF_TOOL" hf download "$MODEL_REPO" \
    --revision "$MODEL_REVISION" --local-dir "$model_dir"
  model_is_accepted "$model_dir" || fail \
    "downloaded model does not match the accepted checksum manifest"
  rm -rf -- "$model_dir/.cache"
  shellcue model install "$model_dir" --name "$MODEL_NAME" --force
}

stop_legacy_daemon_safely() {
  local socket_path="${SMART_BASH_DAEMON_SOCKET:-${TMPDIR:-/tmp}/smart-bash-$(id -u)/daemon.sock}"
  LEGACY_SOCKET_PATH="$socket_path" uv run --no-project --python "$PYTHON_VERSION" python - <<'PY'
import json
import os
import socket
import time
from pathlib import Path

path = Path(os.environ["LEGACY_SOCKET_PATH"])
if not path.exists():
    print("shellcue-install: legacy daemon socket absent; no PID signal attempted")
    raise SystemExit(0)
def request(payload: bytes) -> dict:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(1.0)
        client.connect(str(path))
        client.sendall(payload + b"\n")
        return json.loads(client.recv(65536).split(b"\n", 1)[0])

try:
    ping = request(b'{"op":"ping"}')
except (OSError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
    print(f"shellcue-install: legacy daemon not safely stopped over live socket: {exc}")
    raise SystemExit(0)
if (
    set(ping) != {"ok", "status", "model_status"}
    or ping.get("ok") is not True
    or ping.get("status") != "ready"
    or not isinstance(ping.get("model_status"), str)
):
    print("shellcue-install: socket does not match the legacy daemon protocol; no shutdown sent")
    raise SystemExit(0)
try:
    response = request(b'{"op":"shutdown"}')
except (OSError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
    print(f"shellcue-install: verified legacy daemon did not accept shutdown: {exc}")
    raise SystemExit(0)
if response.get("ok") is not True:
    print("shellcue-install: legacy daemon rejected socket shutdown; no PID signal attempted")
    raise SystemExit(0)
deadline = time.monotonic() + 3.0
while path.exists() and time.monotonic() < deadline:
    time.sleep(0.05)
print("shellcue-install: legacy daemon shutdown requested over confirmed live socket")
PY
}

install_runtime() {
  [[ "$TARGET_SHELL" == "bash" || "$TARGET_SHELL" == "zsh" ]] || fail \
    "unsupported shell '$TARGET_SHELL'; set SHELLCUE_SHELL=bash or zsh"
  stop_legacy_daemon_safely
  shellcue install-shell "$TARGET_SHELL"
  shellcue daemon stop >/dev/null 2>&1 || true
  shellcue service install
  wait_for_service_ready
  shellcue doctor --strict
  say "installed ShellCue; open a fresh ${TARGET_SHELL} and press Ctrl-] for a suggestion"
}

wait_for_service_ready() {
  [[ "$SERVICE_READY_TIMEOUT" =~ ^[0-9]+$ && "$SERVICE_READY_TIMEOUT" -gt 0 ]] || fail \
    "SHELLCUE_SERVICE_READY_TIMEOUT must be a positive integer"
  local deadline=$((SECONDS + SERVICE_READY_TIMEOUT))
  while (( SECONDS < deadline )); do
    if shellcue daemon status >/dev/null 2>&1; then
      say "inference service is ready"
      return
    fi
    sleep 1
  done
  shellcue service status || true
  fail "service manager started ShellCue, but inference was not ready after ${SERVICE_READY_TIMEOUT}s"
}

main() {
  validate_install_source
  command -v curl >/dev/null 2>&1 || fail "curl is required"
  STAGING_DIR="$(mktemp -d "${TMPDIR:-/tmp}/shellcue-install.XXXXXX")"
  install_uv
  install_tool
  install_model
  install_runtime
}

main "$@"
