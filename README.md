# ShellCue

ShellCue is a local-first neural suggestion runtime for Bash and Zsh. This branch prepares
`0.1.0a4`, a development alpha with `DEV_GRADE_SUPPORT`. It is not product-accepted,
trusted, final, or a replacement for prospective validation on real shell use.

ShellCue performs inference on the local machine. It has no telemetry, hosted inference,
or runtime network access. `install.sh` explicitly downloads the pinned model once; recent
command context is masked before it enters the model.

## Install from GitHub

Run the installer from a Git checkout on macOS, Ubuntu, or WSL:

```bash
git clone https://github.com/kroffske/shellcue.git
cd shellcue
./install.sh
```

No package URL or manual model pre-download is required. The bootstrap installs `uv` when
absent, installs the current checkout as an isolated `uv tool`, downloads and verifies the
pinned Hugging Face model, installs the Bash/Zsh hook, and starts a per-user service.

The model download performed by the installer is equivalent to:

```bash
MODEL_DIR="$(mktemp -d)"
uvx --from huggingface_hub==0.35.0 hf download \
  kroffske/shellcue-lfm2.5-230m-alpha \
  --revision ae5b48546645926a6839df554a46596a8a19498e \
  --local-dir "$MODEL_DIR"
shellcue model verify "$MODEL_DIR"
shellcue model install "$MODEL_DIR" --name shellcue-alpha --force
rm -rf "$MODEL_DIR"
```

`install.sh` additionally checks the accepted weights and checksum-manifest SHA-256 before
registering the model. Confirm the completed installation with:

```bash
shellcue --version
shellcue model current
shellcue service status
shellcue doctor --strict
```

See [docs/install.md](docs/install.md) for Bash/Zsh setup, removal, offline behavior,
the optional digest-bound release-package path, and troubleshooting.

## Runtime contract

Only runtime and inference code ships here: artifact validation/loading, neural decode,
candidate safety, model registry, daemon, masked live context, shell integration, and
diagnostics. Model files must include a versioned `inference_config.json`; runtime never
reads or requires training metadata. Hugging Face download is an explicit external step.

Code in this repository is MIT licensed. Model weights are distributed separately under
their model repository's license. The alpha model is derived from
`LiquidAI/LFM2.5-230M-Base`; do not infer that the runtime MIT license applies to weights.

## Commands

```text
shellcue suggest
shellcue daemon start|stop|status
shellcue daemon run
shellcue service install|uninstall|start|stop|status
shellcue model install|list|current|use|uninstall|verify
shellcue shell-init
shellcue install-shell
shellcue uninstall-shell
shellcue doctor
```

No history import, recording, collection, training, evaluation, or upload command exists.

## Development

```bash
uv sync --extra dev
ruff check .
pytest
python -m build
```
