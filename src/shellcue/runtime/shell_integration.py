"""Bash/Zsh hooks with one managed block and no event sinks."""

from __future__ import annotations

from pathlib import Path

BLOCK_START = "# >>> shellcue managed block >>>"
BLOCK_END = "# <<< shellcue managed block <<<"


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
    cleaned = _remove_block(current).rstrip()
    block = render_shell_init(shell).rstrip()
    updated = f"{cleaned}\n\n{block}\n" if cleaned else f"{block}\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(updated, encoding="utf-8")
    return path


def uninstall_shell(shell: str, *, rc_path: Path | None = None) -> Path:
    path = (rc_path or shell_rc_path(shell)).expanduser()
    if not path.exists():
        return path
    current = path.read_text(encoding="utf-8")
    cleaned = _remove_block(current).strip()
    path.write_text(f"{cleaned}\n" if cleaned else "", encoding="utf-8")
    return path


def _remove_block(text: str) -> str:
    while BLOCK_START in text:
        start = text.index(BLOCK_START)
        end = text.find(BLOCK_END, start)
        if end < 0:
            raise ValueError("found incomplete ShellCue managed block")
        text = text[:start] + text[end + len(BLOCK_END) :]
    return text
