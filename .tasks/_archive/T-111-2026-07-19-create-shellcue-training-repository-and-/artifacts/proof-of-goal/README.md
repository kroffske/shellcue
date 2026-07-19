# T-111 proof of goal

Date: 2026-07-19

## Result

ShellCue remains the runtime/inference repository. The new private repository
[`kroffske/shellcue-training`](https://github.com/kroffske/shellcue-training)
owns offline data construction, token materialization, evaluation, causal-LM
training, checkpoint selection, and artifact export.

The new repository is private and its `main` branch is at
`9f82e9a` (`fix: require immutable training receipts`). The audited root commit
is `2033ea7` (`feat: establish ShellCue training workspace`).

## Contract boundary

- ShellCue base after merged PRs #5 and #6:
  `be07ea15e0a9bda2f6fae697c797f3679a032bbd`.
- Prompt contract: `shellcue.autocomplete.v2`.
- Target contract: `shellcue.completion_suffix.v1`.
- Vendored vector ledger SHA-256:
  `e673f34cd18d308b0c50fcaa01e5597dc3d0d62cea466c97291619bb3e968716`.
- Alpha tokenizer SHA-256:
  `df1d8d5ec5d091b460562ffd545e4a5e91d17d4a0db7ebe733be34ed374377bd`.
- All three golden prompts matched exact bytes and alpha tokenizer ids.
- Neither repository imports the other at runtime.
- Recent history is model context only. No lookup, retrieval, deterministic
  command expansion, or history fallback exists in the training design.

## Migration proof

- Smart Bash donor commit:
  `3bf021025813b93500890f0abe23333c2e6e3758`.
- Machine-readable manifest verified 19 donor-source mappings and 20 target
  mappings by SHA-256.
- Smart Bash runtime, daemon, shell integration, retrieval/history stores,
  private data, runs, checkpoints, reports, caches, tasks, and Git history were
  not copied.
- The donor declared MIT in `pyproject.toml` but contained no license file.
  Target code is a focused rewrite under ShellCue's MIT license.

## Executable evidence

ShellCue Training:

- Ruff passed.
- 29 tests passed.
- Source distribution and wheel built.
- Fresh wheel installation with `PYTHONPATH` removed passed contract
  verification, deterministic dataset construction, publishable-data audit,
  and package import.
- Synthetic curriculum produced 262 rows with SHA-256
  `4e185c1f4e04efb6d54b4b20acdddf4aa84a07f4e156f7576c5e5b9d65468fd3`.
- Real alpha-tokenizer materialization produced 262 rows with SHA-256
  `b0775b8ee8bf3949fdaed4c3ac52178541f6bb5687dfb5904fe88bed35c03e82`.
- A one-step local causal-LM canary completed at global step 1 and evaluated
  the validation split through a required receipt binding config, dataset,
  token rows, and prompt vectors.
- The canary artifact passed the sibling command `shellcue model verify`.
- GitHub Actions run
  `https://github.com/kroffske/shellcue-training/actions/runs/29701487561`
  passed on exact HEAD `9f82e9a`.

ShellCue:

- Ruff passed.
- 138 tests passed after temporarily moving and then restoring the user's
  untracked `src/shellcue/.DS_Store`, which otherwise violates the strict
  public-tree inventory test.
- Source distribution and wheel built.

## Privacy and publication audit

The private repository tracks no histories, raw/private datasets, runs,
checkpoints, artifacts, or model weights. Ignore rules cover those local
surfaces, the committed history contains one audited initial commit, and GitHub
reports visibility `PRIVATE`.

## Honest remaining boundary

No corrected production checkpoint was trained or promoted. T-108 must freeze
the full history-conditioned dataset and evaluator; T-109 must train and select
the real checkpoint; T-110 must promote it and prove installed ShellCue
behavior.
