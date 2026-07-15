"""Bash/Zsh hooks with one managed block and no event sinks."""

from __future__ import annotations

import os
from pathlib import Path

BLOCK_START = "# >>> shellcue managed block >>>"
BLOCK_END = "# <<< shellcue managed block <<<"
LEGACY_BLOCK_START = "# >>> smart-bash autocomplete >>>"
LEGACY_BLOCK_END = "# <<< smart-bash autocomplete <<<"


def render_shell_init(shell: str) -> str:
    """Render a hook on a separate key so normal Tab completion remains untouched."""

    if shell == "zsh":
        body = r'''_shellcue_suggest() {
  local -a shellcue_args
  local -a shellcue_recent
  local line
  local count=0
  local suffix
  shellcue_args=(suggest --plain --prefix "$BUFFER" --cwd "$PWD")
  while IFS= read -r line && (( count < 8 )); do
    if [[ -n "${line//[[:space:]]/}" ]]; then
      shellcue_recent+=("$line")
      (( count += 1 ))
    fi
  done < <(fc -ln -8 2>/dev/null)
  if (( ${#shellcue_recent[@]} > 0 )); then
    suffix="$(
      printf '%s\0' "${shellcue_recent[@]}" |
        command shellcue "${shellcue_args[@]}" --recent-stdin0 2>/dev/null
    )"
  else
    suffix="$(command shellcue "${shellcue_args[@]}" 2>/dev/null)"
  fi
  if [[ -n "$suffix" ]]; then
    BUFFER="${BUFFER}${suffix}"
    CURSOR=${#BUFFER}
  fi
}
zle -N _shellcue_suggest
bindkey '^]' _shellcue_suggest'''
    elif shell == "bash":
        body = r'''_shellcue_suggest() {
  local -a shellcue_args
  local -a shellcue_recent
  local line
  local count=0
  local suffix
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
    suffix="$(
      printf '%s\0' "${shellcue_recent[@]}" |
        command shellcue "${shellcue_args[@]}" --recent-stdin0 2>/dev/null
    )"
  else
    suffix="$(command shellcue "${shellcue_args[@]}" 2>/dev/null)"
  fi
  if [[ -n "$suffix" ]]; then
    READLINE_LINE="${READLINE_LINE}${suffix}"
    READLINE_POINT=${#READLINE_LINE}
  fi
}
bind -x '"\C-]":_shellcue_suggest' '''.rstrip()
    else:
        raise ValueError("shell must be 'bash' or 'zsh'")
    return f"{BLOCK_START}\n{body}\n{BLOCK_END}\n"


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
