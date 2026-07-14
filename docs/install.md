# Install ShellCue development alpha

ShellCue `0.1.0a1` requires Python 3.10 or newer. Neural inference requires
Transformers 5.0.0 or newer. The documented model download is explicit so normal runtime
execution never needs network access or Hugging Face credentials.

## Install runtime and pinned model

```bash
python -m pip install "shellcue[neural] @ https://github.com/kroffske/shellcue/archive/refs/tags/v0.1.0a1.tar.gz"
uvx --from huggingface_hub hf download \
  kroffske/shellcue-lfm2.5-230m-alpha \
  --revision ae5b48546645926a6839df554a46596a8a19498e \
  --local-dir ./shellcue-model
shellcue model verify ./shellcue-model
shellcue model install ./shellcue-model --name shellcue-alpha
shellcue doctor --strict
```

Use a Hugging Face commit OID, not a moving branch or tag, as the trust anchor.

## Shell integration

Print a hook without changing files:

```bash
shellcue shell-init zsh
shellcue shell-init bash
```

Install or remove one managed block idempotently:

```bash
shellcue install-shell zsh
shellcue uninstall-shell zsh
shellcue install-shell bash
shellcue uninstall-shell bash
```

The hook binds ShellCue to `Ctrl-]`. Tab remains owned by the shell's normal completion.
If ShellCue has no candidate, it leaves the command line unchanged. The hook does not
record commands, emit telemetry, or upload context. It forwards at most eight prior
history entries through bounded NUL-delimited standard input, keeping raw commands out
of process arguments. The runtime masks them in memory before inference and does not
persist them.

## Local state and overrides

- Models and daemon state: `~/.cache/shellcue`.
- Configuration: `~/.config/shellcue`.
- Overrides: `SHELLCUE_CACHE_DIR`, `SHELLCUE_CONFIG_DIR`, `SHELLCUE_MODEL_DIR`,
  `SHELLCUE_DAEMON_DIR`, `SHELLCUE_DAEMON_SOCKET`, `SHELLCUE_NEURAL_DTYPE`.

Keep a custom `SHELLCUE_DAEMON_SOCKET` path short. Unix-domain socket paths have a
small OS-specific length limit; the default ShellCue path stays within it.

The runtime is offline. Download and installation are separate operations.

## Alpha status and licenses

This is a development alpha with `DEV_GRADE_SUPPORT`, not product acceptance. Runtime
code is MIT licensed. Model weights have a separate model license and attribution in the
Hugging Face repository; the runtime license does not cover those weights.
