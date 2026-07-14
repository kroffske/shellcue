# ShellCue

ShellCue is a local-first neural suggestion runtime for Bash and Zsh. This release is
`0.1.0a1`, a development alpha with `DEV_GRADE_SUPPORT`. It is not product-accepted,
trusted, final, or a replacement for prospective validation on real shell use.

ShellCue performs inference on the local machine. It has no telemetry, hosted inference,
or implicit model download. Recent command context is masked before it enters the model.

## Install

```bash
python -m pip install "shellcue[neural] @ https://github.com/kroffske/shellcue/archive/refs/tags/v0.1.0a1.tar.gz"
uvx --from huggingface_hub hf download \
  kroffske/shellcue-lfm2.5-230m-alpha \
  --revision <immutable-hf-commit-oid> \
  --local-dir ./shellcue-model
shellcue model verify ./shellcue-model
shellcue model install ./shellcue-model --name shellcue-alpha
shellcue doctor --strict
shellcue suggest --prefix "git s"
shellcue install-shell zsh
```

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
shellcue model install|list|current|use|uninstall|verify
shellcue shell-init
shellcue install-shell
shellcue uninstall-shell
shellcue doctor
```

No history import, recording, collection, training, evaluation, or upload command exists.

## Development

```bash
python -m pip install -e ".[dev]"
ruff check .
pytest
python -m build
```
