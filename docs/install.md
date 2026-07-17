---
title: Install ShellCue development alpha
type: guide
status: active
owner: ShellCue contributors
tags: [install, model, uninstall]
updated: "2026-07-17T00:15:42Z"
source_commit: "cffde1fa2736"
update_event: "ship_refresh"
context: "release_candidate=0.1.0a4"
description: "Documents the reviewed checkout installer, CPU-only runtime, managed model, and safe purge boundary."
---

# Install ShellCue development alpha

ShellCue `0.1.0a4` requires Python 3.10 or newer. The bootstrap uses Python 3.12 in a
persistent isolated `uv tool` environment. PyTorch, Transformers, Tokenizers, and
Safetensors are mandatory package dependencies because ShellCue always performs local
neural inference. Network access occurs only during explicit installation; normal
runtime execution never needs network access or Hugging Face credentials.

## Install from a Git checkout

```bash
git clone https://github.com/kroffske/shellcue.git
cd shellcue
./install.sh
```

With no package variables, `install.sh` installs the checkout containing the script by
running `uv tool install` against that directory. It then downloads the model, installs
the shell integration, registers the user service, waits for inference readiness, and
runs strict diagnostics. The isolated tool uses uv's CPU-only PyTorch backend, so Ubuntu
and WSL installations do not pull CUDA libraries. Re-running the installer upgrades or
repairs the same tool.

## Model download and verification

The installer pins the model repository to Hugging Face commit
`ae5b48546645926a6839df554a46596a8a19498e` and requires `model.safetensors` SHA-256
`c4f7973c48eb04fa2e8013f0d03171fcfb4ee27c157dea31e96020b12b84fb53`.
It removes its temporary download directory after the model registry has made the
verified managed copy.

The explicit download and registry sequence is:

```bash
MODEL_DIR="$(mktemp -d)"
uvx --from huggingface_hub==0.35.0 hf download \
  kroffske/shellcue-lfm2.5-230m-alpha \
  --revision ae5b48546645926a6839df554a46596a8a19498e \
  --local-dir "$MODEL_DIR"
shellcue model verify "$MODEL_DIR"
rm -rf "$MODEL_DIR/.cache"
shellcue model install "$MODEL_DIR" --name shellcue-alpha --force
rm -rf "$MODEL_DIR"
```

The bootstrap performs these operations automatically and additionally anchors the
download to the accepted weights and checksum-manifest digests. A valid existing managed
copy is reused, so repeated installation does not download the model again.

## Optional digest-bound package source

Release testing can replace the checkout with an exact package while keeping the same
model and service flow:

```bash
uv build --sdist
export SHELLCUE_PACKAGE_URL="file://$PWD/dist/shellcue-0.1.0a4.tar.gz"
export SHELLCUE_PACKAGE_SHA256="$(shasum -a 256 dist/shellcue-0.1.0a4.tar.gz | awk '{print $1}')"
./install.sh
```

If `SHELLCUE_PACKAGE_URL` is set, its SHA-256 is mandatory. The checkout path remains the
default for GitHub users; the package override exists for an immutable release artifact.

## Platform and service behavior

| Platform | Backend | Support |
|---|---|---|
| macOS | per-user LaunchAgent | Full local lifecycle target. No root install. |
| Ubuntu Linux | per-user systemd unit | Supported when the user systemd manager is available. |
| WSL with systemd | per-user systemd unit | Same backend as Ubuntu. |
| WSL without systemd | session daemon | Explicitly unsupervised; it does not survive session/WSL restart. |

The service definition uses the absolute Python executable in the uv tool environment.
It also records `HOME`, ShellCue cache, config, and daemon directories, so it does not
depend on interactive-shell activation or `PATH`.

```bash
shellcue service status
shellcue service stop
shellcue service start
shellcue service uninstall
shellcue service install
```

On WSL without systemd, ShellCue labels the daemon `unsupervised` and tells the operator
to enable systemd in `/etc/wsl.conf`; it never claims that a restartable service exists.

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

Installation also removes the exact legacy `smart-bash autocomplete` managed block.
Before changing an rc file it retains the original once as `.zshrc.shellcue-backup` or
`.bashrc.shellcue-backup`. It asks a live legacy daemon to shut down over its Unix socket;
it never trusts a PID file, signals a legacy PID, uninstalls the legacy tool, or deletes
legacy databases, history, models, or other local data.

## Local state and overrides

- Models and daemon state: `~/.cache/shellcue`.
- Configuration: `~/.config/shellcue`.
- Overrides: `SHELLCUE_CACHE_DIR`, `SHELLCUE_CONFIG_DIR`, `SHELLCUE_MODEL_DIR`,
  `SHELLCUE_DAEMON_DIR`, `SHELLCUE_DAEMON_SOCKET`, `SHELLCUE_NEURAL_DTYPE`.

Keep a custom `SHELLCUE_DAEMON_SOCKET` path short. Unix-domain socket paths have a
small OS-specific length limit; the default ShellCue path stays within it.

The runtime is offline. The bootstrap performs the explicit network download before the
service starts.

## Removal

Remove the service and managed blocks from both Bash and Zsh while preserving local models
and configuration:

```bash
shellcue uninstall
uv tool uninstall shellcue
```

Use the explicit purge flag to remove all ShellCue-owned cache, models, configuration, and
daemon state before removing the program:

```bash
shellcue uninstall --purge
uv tool uninstall shellcue
```

Purge honors `SHELLCUE_CACHE_DIR`, `SHELLCUE_CONFIG_DIR`, and independently overridden
`SHELLCUE_DAEMON_DIR` or `SHELLCUE_DAEMON_SOCKET` paths. A root named `shellcue` is removed
as application-owned state. For any other overridden root, purge removes only recognized
ShellCue entries and preserves the root when unrelated entries remain. Symlinks, unsafe
broad roots, and unexpected entry types are rejected before deleting anything. It never removes
`~/.cache/huggingface`, an external `SHELLCUE_MODEL_DIR`, legacy Smart Bash data, or the
`uv` tool installation itself. Plain `shellcue uninstall` intentionally keeps the cache
and configuration for a later reinstall.

## Troubleshooting

- `SHELLCUE_PACKAGE_SHA256 requires SHELLCUE_PACKAGE_URL` means only half of the optional
  package override was provided. Unset both variables for checkout installation.
- `set SHELLCUE_PACKAGE_SHA256` means a package URL was supplied without a valid lowercase
  SHA-256. Supply the exact digest or unset both package variables.
- `systemd user services are unavailable` on Ubuntu means the user systemd manager is
  not running. On WSL, either enable systemd or accept the labeled session fallback.
- `daemon did not become ready` waits 60 seconds by default and terminates only the child
  spawned by that command. Increase it with `shellcue daemon start --timeout 120` on a
  slow cold load, then inspect `~/.cache/shellcue/daemon/shellcue.log`.
- The bootstrap waits up to 120 seconds for the inference socket after registering the
  service. Set `SHELLCUE_SERVICE_READY_TIMEOUT` to a larger integer on slower hardware.
- `shellcue service status` reports service-manager state. `shellcue doctor --strict`
  separately verifies Python, neural dependencies, and the active model.

## Alpha status and licenses

This is a development alpha with `DEV_GRADE_SUPPORT`, not product acceptance. Runtime
code is MIT licensed. Model weights use the separate LFM Open License v1.0, which includes
a commercial-use limitation, plus attribution in the Hugging Face repository. Review the
complete model terms before use or redistribution; the runtime license does not cover the
weights.
