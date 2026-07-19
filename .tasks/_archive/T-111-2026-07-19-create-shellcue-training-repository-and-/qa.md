# QA — Create ShellCue Training repository and migrate ML ownership

Verdict: ACCEPTED

Reviewer topology: fresh self-verification plus a successful GitHub-hosted CI
run. This is not an independent human or agent review.

## Acceptance evidence

### Repository and ownership boundary

- ShellCue PR #5 merged at
  `6347e45546262978901f21341cfa8c70d305b3b7`.
- ShellCue PR #6 merged at
  `be07ea15e0a9bda2f6fae697c797f3679a032bbd`.
- Private `kroffske/shellcue-training` exists with visibility `PRIVATE`,
  default branch `main`, audited initial commit
  `2033ea7a9ce0f40ab4815b307a478ed6ff87a067`, and current commit
  `9f82e9a2c48a62bcc52225a2931ecd094186607b`.
- ShellCue Training package code has no `smart_bash` or `shellcue` runtime
  import. The repositories communicate through vendored, hash-checked
  contracts and exported artifacts only.
- Smart Bash T-299 is archived as superseded/reference-only at local donor
  commit `1e93407`; its planning evidence remains preserved.

### Contract and data correctness

- Runtime and training vector files match byte-for-byte at SHA-256
  `e673f34cd18d308b0c50fcaa01e5597dc3d0d62cea466c97291619bb3e968716`.
- The installed alpha tokenizer matches SHA-256
  `df1d8d5ec5d091b460562ffd545e4a5e91d17d4a0db7ebe733be34ed374377bd`.
- All three golden prompt texts, retained fields, omission counts, suffix
  targets, prompt hashes, and alpha token-id vectors match.
- Training preserves the causal boundary as exact prompt ids followed by
  separately tokenized suffix ids; prompt labels are `-100`.
- Synthetic Git/SSH/history data varies prefix length, history length,
  repetitions, and similar hosts. The deterministic public curriculum contains
  262 rows.
- Set-valued evaluation accepts multiple valid completions and classifies
  `git sudo apt-get install git` as severe foreign-command insertion.

### Build, package, canary, and artifact gates

- ShellCue Training Ruff passed and 29 tests passed.
- Source and wheel distributions built.
- Fresh wheel install with `PYTHONPATH` removed passed package import, contract
  verification, deterministic dataset construction, and publishable-data
  audit.
- Real alpha-tokenizer materialization processed all 262 rows.
- A local one-step causal-LM canary completed at global step 1 and evaluated
  the validation split. The runner required a receipt binding config, dataset,
  token rows, and prompt vectors.
- Its exported runtime-only artifact passed `shellcue model verify`.
- GitHub Actions run
  `https://github.com/kroffske/shellcue-training/actions/runs/29701487561`
  completed successfully for exact HEAD `9f82e9a`.
- ShellCue Ruff passed, 138 tests passed, and source/wheel builds passed. The
  user's untracked `src/shellcue/.DS_Store` was temporarily moved and restored
  unchanged because the strict public-tree test intentionally rejects it.
- `locus task converge T-111 --base be07ea1 --write` reports `CONVERGED`.

### Provenance and privacy

- The donor manifest verifies 19 pinned source mappings and 20 target mappings
  by SHA-256 against Smart Bash commit
  `3bf021025813b93500890f0abe23333c2e6e3758`.
- The donor declared MIT in `pyproject.toml` but had no license file. Target
  code is a focused rewrite under ShellCue's MIT license.
- No donor Git history, private histories, raw/private datasets, runs,
  checkpoints, artifacts, reports, caches, tasks, or model weights were copied.
- Ignore rules and the migration audit reject tracked weight/checkpoint formats.

Primary readable evidence:
`artifacts/proof-of-goal/README.md`.

## Findings

None for the declared repository migration and contract-authority outcome.

## Residual boundary

No corrected production model was trained, selected, promoted, installed, or
accepted. T-108 owns the full history-conditioned dataset and evaluator; T-109
owns real Liquid training and checkpoint selection; T-110 owns promotion and
installed ShellCue verification.
