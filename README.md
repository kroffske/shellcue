# ShellCue

ShellCue is a local-first neural suggestion runtime for Bash and Zsh. This branch prepares
`0.1.0a2`, a development alpha with `DEV_GRADE_SUPPORT`. It is not product-accepted,
trusted, final, or a replacement for prospective validation on real shell use.

ShellCue performs inference on the local machine. It has no telemetry, hosted inference,
or implicit model download. Recent command context is masked before it enters the model.

## Install

The supported bootstrap installs a persistent isolated `uv tool`, the pinned public
model, the Bash/Zsh hook, and a per-user service. This draft intentionally fails closed
until the release artifact URL and SHA-256 are finalized. Maintainers can test an exact
local sdist now:

```bash
uv build --sdist
export SHELLCUE_PACKAGE_URL="file://$PWD/dist/shellcue-0.1.0a2.tar.gz"
export SHELLCUE_PACKAGE_SHA256="$(shasum -a 256 dist/shellcue-0.1.0a2.tar.gz | awk '{print $1}')"
./install.sh
```

`install.sh` installs `uv` if absent, installs `shellcue[neural]` with `uv tool install`,
downloads the Hugging Face snapshot at its immutable commit OID, verifies the accepted
weights SHA-256, migrates the legacy shell hook, and installs the user service.

See [docs/install.md](docs/install.md) for Bash/Zsh setup, removal, offline behavior,
and troubleshooting.

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
