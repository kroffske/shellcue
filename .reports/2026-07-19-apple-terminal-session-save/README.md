# Apple Terminal session-save incident during ShellCue prediction

- Date: 2026-07-19
- Status: fixed and verified
- Fix branch: `codex/apple-terminal-session-save`, based on merged installer PR #2
- Affected surface: macOS Terminal.app + Zsh automatic suggestions

## 30-second summary

ShellCue does not implement a command-history store, but its former Zsh cancellation path accidentally invoked Apple Terminal's built-in session saver. When a delayed prediction became stale, `_shellcue_start_prediction` executed `exit 0` inside a process-substitution subshell. Apple Terminal had registered `shell_session_update` as a `zshexit` hook, so that explicit subshell exit printed:

```text
Saving session...
...copying shared history...
...saving history...truncating history files...
...completed.
```

The same path wrote Apple Terminal session and history files even though the user did not enable a ShellCue persistence flag. The fix makes a stale worker reach the natural end of the process-substitution body. ShellCue neither invokes the inherited exit hook nor changes the user's global Apple Terminal policy.

The correct product behavior is:

- Zsh automatic ghost suggestions remain enabled by default after the normal installer runs.
- `Tab` accepts one word, `Shift-Tab` accepts the full visible suffix, and `Ctrl-]` remains optional.
- Starting, replacing, or cancelling a prediction is silent and does not invoke Apple Terminal's session-save hook.
- ShellCue does not change the user's global Apple Terminal session-history policy.

## What is installed now

The current checkout has one unified installer path. `install.sh` installs the checkout package, verifies the pinned model, installs the shell integration, registers the user service, waits for inference readiness, and runs strict diagnostics. For Zsh, the managed hook enables automatic predictions after a 200 ms pause and installs the `Tab` and `Shift-Tab` acceptance widgets.

Live verification at report time found:

- Installed binary: `/Users/ravius/.local/bin/shellcue`, version `0.1.0a4`.
- Installed model: `shellcue-lfm2.5-230m-alpha`.
- Service: supervised LaunchAgent, installed and running, inference ready.
- Installed Zsh hook: byte-for-byte equal to the hook rendered by this checkout.
- Current fix branch: `codex/apple-terminal-session-save`.
- Current Git quality probe: failed with `git st -> git stale`; this is tracked in T-104 (Build standard-command quality eval).

This confirms that automatic suggestions are part of the installer-owned Zsh integration, not a separate manual hotkey-only installation.

## Who prints the save messages

The strings come from Apple's `/etc/zshrc_Apple_Terminal`, not from ShellCue:

- Lines 91-96 enable Apple Terminal's save/restore mechanism by default when `TERM_SESSION_ID` is present unless `SHELL_SESSIONS_DISABLE=1`.
- Lines 181-206 copy, append, and truncate history while printing the three history messages.
- Lines 213-228 save session state while printing `Saving session...` and `completed.`
- Lines 246-251 register `shell_session_update` as a `zshexit` hook.

ShellCue's relevant path is `src/shellcue/runtime/shell_integration.py`. `_shellcue_start_prediction` runs a delayed prediction in Zsh process substitution. Normal rapid typing invalidates earlier request ids, so the stale-request branch is expected during ordinary use. The corrected worker enters the inference body only while its request id is current; a stale worker reaches the end naturally.

The corrected cancellation flow is:

```text
new character
  -> previous delayed ShellCue request becomes stale
  -> stale ShellCue worker reaches the end naturally
  -> inherited Apple `zshexit` hook is not invoked
```

Before the correction, the final two steps were:

```text
stale ShellCue worker executes explicit `exit 0`
  -> inherited Apple `zshexit` hook runs
  -> Terminal.app saves session/history and prints the messages
```

## Reproduction and minimization

The incident was reproduced in a PTY with a synthetic `TERM_SESSION_ID` and an isolated temporary `ZDOTDIR`; no real user history was read or modified.

Typing `git st` with the installed ShellCue hook produced, before the parent shell exited:

- `Saving session`: 1 occurrence.
- `copying shared history`: 1 occurrence.
- `saving history`: 1 occurrence.
- `truncating history files`: 1 occurrence.
- A synthetic `.session` file, per-session `.history` file, and shared history file.

The minimized probe then changed one variable at a time:

- Process substitution ending naturally: zero save cycles.
- Process substitution executing `exit 0`: one save cycle and session/history writes.
- The same explicit exit after removing `shell_session_update` only inside the child: zero save cycles.

This rules out the model daemon, the ShellCue CLI, and process substitution by itself. The direct trigger is the explicit stale-worker exit combined with the inherited Apple `zshexit` hook.

## Persistence boundary

There are two different mechanisms:

1. ShellCue reads at most eight recent history entries from the current shell and sends them through local standard input for masked local inference. The ShellCue runtime does not provide a history import, recording, telemetry, or upload command.
2. Apple Terminal saves shell state under `${ZDOTDIR:-$HOME}/.zsh_sessions` and may merge commands into the file referenced by `$HISTFILE`. This Apple behavior is enabled by default unless the user disables it.

No explicit `SHELL_SESSIONS_DISABLE` or `SHELL_SESSION_HISTORY` setting was found in the user's `.zshenv`, `.zprofile`, or `.zshrc`. The user's `~/.zsh_sessions` directory exists with mode `0700`, and a `.historynew` file timestamp matches the reported `Last login` time. This is consistent with Apple Terminal's default policy, not a ShellCue opt-in.

`SHELL_SESSION_HISTORY=0` disables Apple's per-session history while retaining the broader session mechanism. `SHELL_SESSIONS_DISABLE=1`, typically set in `.zshenv`, disables the Apple save/restore mechanism as a whole. ShellCue must not set either globally because doing so would silently change Terminal.app behavior outside ShellCue.

## Applied correction and regression gate

The stale prediction path now terminates naturally instead of calling explicit `exit` inside the process-substitution worker. ShellCue does not remove Apple's hook or depend on its private function name.

The automated macOS regression test:

- uses a synthetic `TERM_SESSION_ID` and isolated `ZDOTDIR`;
- sources `/etc/zshrc_Apple_Terminal` when available;
- loads the rendered ShellCue Zsh hook;
- starts and invalidates an asynchronous prediction;
- asserts that no Apple save marker is printed;
- asserts that no `.session` or completed `.history` file is created.

The test failed before the production change with the exact Apple `Saving session...` sequence and passed after it. The full repository suite passes with 126 tests.

A separate live PTY verification installed the checkout and exercised the actual interactive Zsh hook. Rapid typing created stale requests without save output. The visible ghost suggestion appeared, `Tab` accepted one word, and `Shift-Tab` accepted the full suffix. Before removing the parent shell's normal Apple exit hook, the probe found zero save markers and zero `.session` or completed `.history` files. The installed hook matched the checkout renderer byte for byte.

After the fix, Apple Terminal may still print its normal save message when the real top-level terminal shell exits. ShellCue should neither relabel that operating-system message nor add a startup banner; it should only stop causing extra save cycles during prediction.

## Separate model-quality defect

The current installed model still fails the narrow Git smoke case. The deterministic diagnostic produced `git st -> git stale`, while the interactive report showed a malformed continuation resembling `git st derr`. Another observed failure is `git s -> git sudo apt-get install git`.

These examples belong to T-104 (Build standard-command quality eval). That draft now requires exact raw-candidate capture, malformed-token and cross-family cohorts, context-free and bounded-context cases, abstention gates, and a decision about whether correction belongs to decoding, filtering, data, adaptation, or model training. Broad retraining must not start from an anecdote before the evaluator localizes the failure.
