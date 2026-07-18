"""Bash/Zsh hooks with one managed block and no event sinks."""

from __future__ import annotations

import os
from pathlib import Path

BLOCK_START = "# >>> shellcue managed block >>>"
BLOCK_END = "# <<< shellcue managed block <<<"
LEGACY_BLOCK_START = "# >>> smart-bash autocomplete >>>"
LEGACY_BLOCK_END = "# <<< smart-bash autocomplete <<<"


def render_shell_init(shell: str) -> str:
    """Render local suggestion integration for one supported shell."""

    if shell == "zsh":
        body = _render_zsh_init()
    elif shell == "bash":
        body = r'''_shellcue_suggest() {
  local -a shellcue_args
  local -a shellcue_recent
  local line
  local count=0
  local suffix
  local shellcue_ok=0
  shellcue_args=(suggest --plain --prefix "$READLINE_LINE" --cwd "$PWD")
  while IFS= read -r line && (( count < 8 )); do
    if [[ "$line" =~ ^[[:space:]]*[0-9]+[[:space:]]+(.*)$ ]]; then
      line="${BASH_REMATCH[1]}"
    fi
    if [[ -n "${line//[[:space:]]/}" ]]; then
      shellcue_recent+=("$line")
      (( count += 1 ))
    fi
  done < <(HISTTIMEFORMAT= builtin history 8 2>/dev/null)
  if (( ${#shellcue_recent[@]} > 0 )); then
    if suffix="$(
      printf '%s\0' "${shellcue_recent[@]}" |
        command shellcue "${shellcue_args[@]}" --recent-stdin0 2>/dev/null
    )"; then
      shellcue_ok=1
    fi
  else
    if suffix="$(command shellcue "${shellcue_args[@]}" 2>/dev/null)"; then
      shellcue_ok=1
    fi
  fi
  if (( ! shellcue_ok )); then
    printf '\nShellCue unavailable; run shellcue doctor\n' >&2
  elif [[ -n "$suffix" ]]; then
    READLINE_LINE="${READLINE_LINE}${suffix}"
    READLINE_POINT=${#READLINE_LINE}
  else
    printf '\nShellCue: no suggestion\n' >&2
  fi
}
bind -x '"\C-]":_shellcue_suggest' '''.rstrip()
    else:
        raise ValueError("shell must be 'bash' or 'zsh'")
    return f"{BLOCK_START}\n{body}\n{BLOCK_END}\n"


def _render_zsh_init() -> str:
    return r'''# ShellCue automatic suggestions.
# Prediction runs after a short typing pause and never from self-insert.
# Tab accepts one word while a suggestion is visible.
# Shift-Tab accepts the full suggestion.
# Ctrl-] requests a suggestion immediately.
if (( ! $+SHELLCUE_ZSH_ACCEPT_KEYS )); then
  typeset -ga SHELLCUE_ZSH_ACCEPT_KEYS
  SHELLCUE_ZSH_ACCEPT_KEYS=('^I' '^[[Z')
fi
: ${SHELLCUE_ZSH_HIGHLIGHT:='fg=244'}
: ${SHELLCUE_ZSH_AUTO_SUGGEST:=1}
: ${SHELLCUE_ZSH_DEBOUNCE_SECONDS:=0.20}
: ${SHELLCUE_ZSH_STATE_DIR:=${TMPDIR:-/tmp}/shellcue-zsh-${UID}}
typeset -g SHELLCUE_ZSH_PENDING_FD=""
typeset -g SHELLCUE_ZSH_PENDING_BUFFER=""
typeset -g SHELLCUE_ZSH_PENDING_REQUEST_ID=""
typeset -g SHELLCUE_ZSH_READY_BUFFER=""
typeset -g SHELLCUE_ZSH_READY_SUFFIX=""
typeset -g SHELLCUE_ZSH_READY_REQUEST_ID=""
typeset -g SHELLCUE_ZSH_ERROR_BUFFER=""
typeset -g SHELLCUE_ZSH_DISPLAY_BUFFER=""
typeset -g SHELLCUE_ZSH_DISPLAY_COMMAND=""
typeset -g SHELLCUE_ZSH_EMPTY_BUFFER=""
typeset -g SHELLCUE_ZSH_STATE_FILE="$SHELLCUE_ZSH_STATE_DIR/state-$$"
typeset -gi SHELLCUE_ZSH_REQUEST_ID=0
mkdir -p "$SHELLCUE_ZSH_STATE_DIR" 2>/dev/null || true
chmod 700 "$SHELLCUE_ZSH_STATE_DIR" 2>/dev/null || true

_shellcue_widget_for_key() {
  local desc widget
  desc="$(bindkey -- "$1" 2>/dev/null)"
  widget="${desc##* }"
  if [[ -z "$desc" || "$widget" == "undefined-key" || "$widget" == _shellcue_* ]]; then
    print -r -- "$2"
  else
    print -r -- "$widget"
  fi
}

_shellcue_clear_suggestion() {
  POSTDISPLAY=""
  SHELLCUE_ZSH_DISPLAY_BUFFER=""
  SHELLCUE_ZSH_DISPLAY_COMMAND=""
  region_highlight=("${region_highlight:#*memo=shellcue-suggestion}")
}

_shellcue_highlight_suggestion() {
  local start="${#BUFFER}"
  local end=$(( ${#BUFFER} + ${#POSTDISPLAY} ))
  region_highlight=("${region_highlight:#*memo=shellcue-suggestion}")
  if [[ -n "$POSTDISPLAY" ]]; then
    region_highlight+=("P$start $end $SHELLCUE_ZSH_HIGHLIGHT memo=shellcue-suggestion")
  fi
}

_shellcue_close_fd() {
  local close_fd="$1"
  if [[ -n "$close_fd" ]]; then
    exec {close_fd}<&- 2>/dev/null || true
  fi
}

_shellcue_close_pending() {
  local fd="${SHELLCUE_ZSH_PENDING_FD:-}"
  if [[ -n "$fd" ]]; then
    zle -F "$fd" 2>/dev/null || true
    _shellcue_close_fd "$fd"
  fi
  SHELLCUE_ZSH_PENDING_FD=""
  SHELLCUE_ZSH_PENDING_BUFFER=""
  SHELLCUE_ZSH_PENDING_REQUEST_ID=""
}

_shellcue_invalidate_pending() {
  (( SHELLCUE_ZSH_REQUEST_ID++ ))
  print -r -- "$SHELLCUE_ZSH_REQUEST_ID" >| "$SHELLCUE_ZSH_STATE_FILE" 2>/dev/null || true
}

_shellcue_clear_ready() {
  SHELLCUE_ZSH_READY_BUFFER=""
  SHELLCUE_ZSH_READY_SUFFIX=""
  SHELLCUE_ZSH_READY_REQUEST_ID=""
}

_shellcue_async_ready() {
  local fd="$1"
  local frame=""
  local suffix=""
  local expected="${SHELLCUE_ZSH_PENDING_BUFFER:-}"
  local request_id="${SHELLCUE_ZSH_PENDING_REQUEST_ID:-0}"
  if [[ "$fd" != "${SHELLCUE_ZSH_PENDING_FD:-}" ]]; then
    zle -F "$fd" 2>/dev/null || true
    _shellcue_close_fd "$fd"
    return 0
  fi
  IFS= read -r frame <&$fd || frame=""
  zle -F "$fd" 2>/dev/null || true
  _shellcue_close_fd "$fd"
  SHELLCUE_ZSH_PENDING_FD=""
  SHELLCUE_ZSH_PENDING_BUFFER=""
  SHELLCUE_ZSH_PENDING_REQUEST_ID=""
  if [[ "$frame" == "1" ]]; then
    _shellcue_clear_ready
    SHELLCUE_ZSH_ERROR_BUFFER="$expected"
    zle -M "ShellCue unavailable; run shellcue doctor"
    zle redisplay
    return 0
  fi
  if [[ "$frame" != 0* ]]; then
    return 0
  fi
  suffix="${frame[2,-1]}"
  SHELLCUE_ZSH_READY_BUFFER="$expected"
  SHELLCUE_ZSH_READY_SUFFIX="$suffix"
  SHELLCUE_ZSH_READY_REQUEST_ID="$request_id"
  zle _shellcue_apply_ready_widget 2>/dev/null || zle redisplay
}

_shellcue_apply_ready_suggestion() {
  local current="$1"
  local suffix="${SHELLCUE_ZSH_READY_SUFFIX:-}"
  local request_id="${SHELLCUE_ZSH_READY_REQUEST_ID:-0}"
  _shellcue_clear_ready
  if [[ "$request_id" != "$SHELLCUE_ZSH_REQUEST_ID" ]]; then
    return 0
  fi
  SHELLCUE_ZSH_ERROR_BUFFER=""
  if [[ -z "$suffix" ]]; then
    SHELLCUE_ZSH_EMPTY_BUFFER="$current"
    return 0
  fi
  POSTDISPLAY="$suffix"
  SHELLCUE_ZSH_DISPLAY_BUFFER="$current"
  SHELLCUE_ZSH_DISPLAY_COMMAND="${current}${suffix}"
  SHELLCUE_ZSH_EMPTY_BUFFER=""
  _shellcue_highlight_suggestion
}

_shellcue_start_prediction() {
  local current="$1"
  local delay="$2"
  local cwd="$PWD"
  local request_id
  local fd
  _shellcue_invalidate_pending
  request_id="$SHELLCUE_ZSH_REQUEST_ID"
  exec {fd}< <(
    if [[ "$delay" != "0" ]]; then
      sleep "$delay"
    fi
    if [[ "$(cat "$SHELLCUE_ZSH_STATE_FILE" 2>/dev/null)" == "$request_id" ]]; then
      local -a shellcue_args
      local -a shellcue_recent
      local line
      local count=0
      local suffix=""
      local shellcue_ok=0
      shellcue_args=(suggest --plain --prefix "$current" --cwd "$cwd")
      while IFS= read -r line && (( count < 8 )); do
        if [[ -n "${line//[[:space:]]/}" ]]; then
          shellcue_recent+=("$line")
          (( count += 1 ))
        fi
      done < <(fc -ln -8 2>/dev/null)
      if (( ${#shellcue_recent[@]} > 0 )); then
        if suffix="$(
          printf '%s\0' "${shellcue_recent[@]}" |
            command shellcue "${shellcue_args[@]}" --recent-stdin0 2>/dev/null
        )"; then
          shellcue_ok=1
        fi
      else
        if suffix="$(command shellcue "${shellcue_args[@]}" 2>/dev/null)"; then
          shellcue_ok=1
        fi
      fi
      if (( shellcue_ok )); then
        print -r -- "0${suffix}"
      else
        print -r -- "1"
      fi
    fi
  )
  SHELLCUE_ZSH_PENDING_FD="$fd"
  SHELLCUE_ZSH_PENDING_BUFFER="$current"
  SHELLCUE_ZSH_PENDING_REQUEST_ID="$request_id"
  zle -F "$fd" _shellcue_async_ready
}

_shellcue_schedule_suggestion() {
  local current="$BUFFER"
  if [[ "$SHELLCUE_ZSH_AUTO_SUGGEST" == "0" ]]; then
    return 0
  fi
  if [[ -z "$current" || "$CURSOR" -ne "${#BUFFER}" ]]; then
    _shellcue_clear_suggestion
    _shellcue_clear_ready
    SHELLCUE_ZSH_EMPTY_BUFFER=""
    SHELLCUE_ZSH_ERROR_BUFFER=""
    if [[ -n "${SHELLCUE_ZSH_PENDING_FD:-}" ]]; then
      _shellcue_close_pending
      _shellcue_invalidate_pending
    fi
    return 0
  fi
  if [[ -n "$SHELLCUE_ZSH_ERROR_BUFFER" ]]; then
    if [[ "$SHELLCUE_ZSH_ERROR_BUFFER" == "$current" ]]; then
      return 0
    fi
    SHELLCUE_ZSH_ERROR_BUFFER=""
  fi
  if [[ -n "${SHELLCUE_ZSH_READY_BUFFER:-}" ]]; then
    if [[ "$SHELLCUE_ZSH_READY_BUFFER" == "$current" ]]; then
      _shellcue_apply_ready_suggestion "$current"
      return 0
    fi
    _shellcue_clear_ready
  fi
  if [[ -n "$POSTDISPLAY" && -n "$SHELLCUE_ZSH_DISPLAY_COMMAND" ]]; then
    if [[ "$SHELLCUE_ZSH_DISPLAY_COMMAND" != "$current" \
      && "${SHELLCUE_ZSH_DISPLAY_COMMAND[1,${#current}]}" == "$current" ]]; then
      local suffix_start=$(( ${#current} + 1 ))
      POSTDISPLAY="${SHELLCUE_ZSH_DISPLAY_COMMAND[$suffix_start,-1]}"
      SHELLCUE_ZSH_DISPLAY_BUFFER="$current"
      _shellcue_highlight_suggestion
      if [[ -n "${SHELLCUE_ZSH_PENDING_FD:-}" \
        && "$SHELLCUE_ZSH_PENDING_BUFFER" != "$current" ]]; then
        _shellcue_close_pending
        _shellcue_invalidate_pending
      fi
      return 0
    fi
    _shellcue_clear_suggestion
  fi
  if [[ "$SHELLCUE_ZSH_EMPTY_BUFFER" == "$current" ]]; then
    return 0
  fi
  if [[ -n "${SHELLCUE_ZSH_PENDING_FD:-}" ]]; then
    if [[ "$SHELLCUE_ZSH_PENDING_BUFFER" == "$current" ]]; then
      return 0
    fi
    _shellcue_close_pending
    _shellcue_invalidate_pending
  fi
  _shellcue_clear_suggestion
  _shellcue_clear_ready
  _shellcue_start_prediction "$current" "$SHELLCUE_ZSH_DEBOUNCE_SECONDS"
}

_shellcue_zle_line_pre_redraw() {
  if [[ -n "${widgets[_shellcue_orig_zle_line_pre_redraw]:-}" ]]; then
    zle _shellcue_orig_zle_line_pre_redraw "$@"
  fi
  _shellcue_schedule_suggestion
}

_shellcue_apply_ready_widget() {
  _shellcue_schedule_suggestion
  zle redisplay
}

_shellcue_accept_full_suggestion() {
  if [[ -z "$POSTDISPLAY" ]]; then
    return 1
  fi
  BUFFER="${BUFFER}${POSTDISPLAY}"
  CURSOR="${#BUFFER}"
  _shellcue_clear_suggestion
  SHELLCUE_ZSH_EMPTY_BUFFER="$BUFFER"
  zle redisplay
  return 0
}

_shellcue_accept_next_word() {
  local accepted
  local remaining
  if [[ -z "$POSTDISPLAY" ]]; then
    return 1
  fi
  if [[ "$POSTDISPLAY" =~ '^([[:space:]]*[^[:space:]]+)(.*)$' ]]; then
    accepted="$match[1]"
    remaining="$match[2]"
  else
    accepted="$POSTDISPLAY"
    remaining=""
  fi
  BUFFER="${BUFFER}${accepted}"
  CURSOR="${#BUFFER}"
  POSTDISPLAY="$remaining"
  if [[ -n "$POSTDISPLAY" ]]; then
    SHELLCUE_ZSH_DISPLAY_BUFFER="$BUFFER"
    _shellcue_highlight_suggestion
  else
    _shellcue_clear_suggestion
    SHELLCUE_ZSH_EMPTY_BUFFER="$BUFFER"
  fi
  zle redisplay
  return 0
}

_shellcue_accept_suggestion() {
  if [[ -n "$POSTDISPLAY" ]]; then
    if [[ "$KEYS" == $'\t' ]]; then
      _shellcue_accept_next_word
    else
      _shellcue_accept_full_suggestion
    fi
    return
  fi
  if [[ "$KEYS" == $'\t' ]]; then
    zle _shellcue_orig_tab "$@"
    return
  fi
  if [[ "$KEYS" == $'\e[Z' ]]; then
    zle _shellcue_orig_shift_tab "$@"
  fi
}

_shellcue_force_suggestion() {
  local current="$BUFFER"
  if [[ -z "$current" || "$CURSOR" -ne "${#BUFFER}" ]]; then
    zle -M "ShellCue needs a non-empty prefix with the cursor at the end"
    return 0
  fi
  _shellcue_clear_suggestion
  _shellcue_clear_ready
  SHELLCUE_ZSH_EMPTY_BUFFER=""
  SHELLCUE_ZSH_ERROR_BUFFER=""
  if [[ -n "${SHELLCUE_ZSH_PENDING_FD:-}" ]]; then
    _shellcue_close_pending
  fi
  _shellcue_start_prediction "$current" "0"
}

_shellcue_accept_line() {
  _shellcue_clear_suggestion
  _shellcue_clear_ready
  if [[ -n "${SHELLCUE_ZSH_PENDING_FD:-}" ]]; then
    _shellcue_close_pending
  fi
  _shellcue_invalidate_pending
  zle _shellcue_orig_accept_line "$@"
}

zle -N _shellcue_accept_suggestion
zle -N _shellcue_force_suggestion
zle -N _shellcue_apply_ready_widget
for key in "${SHELLCUE_ZSH_ACCEPT_KEYS[@]}"; do
  bindkey "$key" _shellcue_accept_suggestion
done
bindkey '^]' _shellcue_force_suggestion

if [[ -z "${SHELLCUE_ZSH_WIDGETS_WRAPPED:-}" ]]; then
  zle -A "$(_shellcue_widget_for_key '^I' expand-or-complete)" _shellcue_orig_tab 2>/dev/null \
    || zle -A expand-or-complete _shellcue_orig_tab
  zle -A "$(_shellcue_widget_for_key '^[[Z' reverse-menu-complete)" \
    _shellcue_orig_shift_tab 2>/dev/null \
    || zle -A reverse-menu-complete _shellcue_orig_shift_tab
  zle -A accept-line _shellcue_orig_accept_line
  zle -N accept-line _shellcue_accept_line
  SHELLCUE_ZSH_WIDGETS_WRAPPED=1
fi
if [[ -z "${SHELLCUE_ZSH_PRE_REDRAW_WRAPPED:-}" ]]; then
  if [[ -n "${widgets[zle-line-pre-redraw]:-}" ]]; then
    zle -A zle-line-pre-redraw _shellcue_orig_zle_line_pre_redraw
  fi
  SHELLCUE_ZSH_PRE_REDRAW_WRAPPED=1
fi
zle -N zle-line-pre-redraw _shellcue_zle_line_pre_redraw'''


def shell_rc_path(shell: str) -> Path:
    if shell == "zsh":
        return Path.home() / ".zshrc"
    if shell == "bash":
        return Path.home() / ".bashrc"
    raise ValueError("shell must be 'bash' or 'zsh'")


def install_shell(shell: str, *, rc_path: Path | None = None) -> Path:
    path = (rc_path or shell_rc_path(shell)).expanduser()
    current = path.read_text(encoding="utf-8") if path.exists() else ""
    legacy_present = _find_exact_marker_line(current, LEGACY_BLOCK_START) >= 0
    cleaned = _remove_block(current, LEGACY_BLOCK_START, LEGACY_BLOCK_END)
    cleaned = _remove_block(cleaned, BLOCK_START, BLOCK_END)
    updated = _append_block(cleaned, render_shell_init(shell))
    path.parent.mkdir(parents=True, exist_ok=True)
    if updated != current:
        if legacy_present:
            _write_backup_once(path, current)
        _write_atomic(path, updated)
    return path


def uninstall_shell(shell: str, *, rc_path: Path | None = None) -> Path:
    path = (rc_path or shell_rc_path(shell)).expanduser()
    if not path.exists():
        return path
    current = path.read_text(encoding="utf-8")
    cleaned = _remove_block(current, BLOCK_START, BLOCK_END)
    if cleaned != current:
        _write_atomic(path, cleaned)
    return path


def backup_path(path: Path) -> Path:
    return path.with_name(f"{path.name}.shellcue-backup")


def _remove_block(text: str, block_start: str, block_end: str) -> str:
    while True:
        start = _find_exact_marker_line(text, block_start)
        if start < 0:
            return text
        end = _find_exact_marker_line(text, block_end, start=start + len(block_start))
        if end < 0:
            raise ValueError(f"found incomplete managed block: {block_start}")
        after = end + len(block_end)
        if after < len(text) and text[after] == "\n":
            after += 1
        prefix = text[:start]
        suffix = text[after:]
        if not suffix and prefix.endswith("\n\n"):
            prefix = prefix[:-1]
        text = prefix + suffix


def _find_exact_marker_line(text: str, marker: str, *, start: int = 0) -> int:
    position = text.find(marker, start)
    while position >= 0:
        line_start = text.rfind("\n", 0, position) + 1
        line_end = text.find("\n", position)
        if line_end < 0:
            line_end = len(text)
        if text[line_start:line_end].removesuffix("\r") == marker:
            return line_start
        position = text.find(marker, position + len(marker))
    return -1


def _append_block(text: str, block: str) -> str:
    block = block.rstrip("\n") + "\n"
    if not text:
        return block
    if text.endswith("\n\n"):
        return text + block
    if text.endswith("\n"):
        return text + "\n" + block
    return text + "\n\n" + block


def _write_backup_once(path: Path, content: str) -> None:
    target = backup_path(path)
    try:
        with target.open("x", encoding="utf-8") as backup:
            backup.write(content)
    except FileExistsError:
        return
    if path.exists():
        os.chmod(target, path.stat().st_mode & 0o777)


def _write_atomic(path: Path, content: str) -> None:
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o600
    temporary = path.with_name(f".{path.name}.shellcue-{os.getpid()}.tmp")
    try:
        temporary.write_text(content, encoding="utf-8")
        os.chmod(temporary, mode)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
