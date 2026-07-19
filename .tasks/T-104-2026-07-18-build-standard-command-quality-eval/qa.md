# QA — Build standard-command quality eval

Verdict: ACCEPTED

Reviewer topology: fresh self-verification after the implementation commits.
This is not independent-agent QA.

## Acceptance evidence

### W1 — Frozen model-only panel

Result: PASS.

- Contract `shellcue-standard-command-quality-v1` is frozen at version 6 and
  validates as `locus.ml.eval.v1`.
- Panel identity is unchanged:
  `513c3c91699453e47227e5c88d8fab6fe876a3b1227811d9ce51b97942e2d4d6`.
- The panel contains 60 cases: 48 positive, 12 negative, 40 set-valued cases,
  and 154 accepted commands across six balanced families.
- The evaluator requires top-level and per-candidate `source=model`, exact
  `command=prefix+suffix`, finite scores, unique candidates, and the requested
  limit.
- Source sweep finds no `apply_runtime_policy`,
  `models.standard_commands`, or `apply_standard_command_policy` in the
  evaluator.

### W2 — Fresh installed alpha baseline

Result: PASS.

- Installed ShellCue: `0.1.0a4`, daemon PID `96180`.
- Active checkpoint:
  `shellcue-lfm2.5-230m-alpha`.
- Weights SHA-256:
  `c4f7973c48eb04fa2e8013f0d03171fcfb4ee27c157dea31e96020b12b84fb53`.
- Production and same-config mirror mismatch count: `0`.
- Production verdict: `REJECT / BLOCK_RELEASE`.
- Useful rank-1: `20/48 = 0.4167`.
- Family-valid: `0.5833`; severe contamination: `0.0833`.
- False show: `0.0833`; correct abstention: `0.9167`.
- Exact result/report hashes and paths are recorded in
  `artifacts/model-only-alpha-v6-baseline.md`.

The failed quality gates are accepted as honest model evidence. They do not
invalidate the evaluator implementation.

### W3 — Promotion and incomparable-run contract

Result: PASS.

- Rank 1 is the release metric because ShellCue paints one leading suggestion.
- `useful@3`, `MRR@3`, and `coverage@3` are diagnostics and cannot promote a
  model.
- A production/mirror mismatch produces top-level `INCOMPARABLE /
  KEEP_BASELINE`; it is not repaired or promoted.
- The finalizer consumes explicit rank-1 metrics, model-only runtime identity,
  evaluator identity, and the top-level comparable decision.

### W4 — Regression and localization proof

Result: PASS.

- Production, beam-3, no-heal, and token-tail lanes ran.
- Beam-3 reached useful rank-1 `0.5000`, useful-at-3 `0.5208`, and
  coverage-at-3 `0.1250`.
- Only one positive case had an accepted answer below rank 1. The evidence
  routes the next work to data/SFT generation repair before ranking-only work.
- Tests cover set-valued targets, shell-token continuation, token splices,
  `git sudo apt-get install git`, `git ssh init`, malformed subcommands,
  empty abstention, positive-abstention denominators, non-model sources,
  rewritten payloads, and incomparable parity.

## Verification

- Focused tests: `22 passed`.
- Ruff: passed.
- Python compile check: passed.
- Contract validation: passed.
- Full repository suite with temporary test-only `jsonschema`: `906 passed`,
  `2 skipped`, `47 failed`. The failures depend on ignored historical
  datasets, run outputs, or archived task artifacts absent from this linked
  worktree; none involve the T-104 evaluator tests.
- `locus task analyze T-104 --write`: `READY`, no deterministic findings.
- `locus task lint --task T-104 --strict --json` failed inside the Locus
  diagnostic-envelope builder with duplicate finding IDs before it could emit a
  task verdict. Task state reports no consistency warnings and both plan-review
  and closure gates satisfied.
- Smart Bash worktree is clean at commits `2a76aa0` and `869ab4a`.
- ShellCue main worktree retains only the user's three pre-existing untracked
  report surfaces.

## Retraining-plan review

Result: PASS.

The owning ML docs require:

- a shadow holdout frozen before new rows;
- error taxonomy and hard-negative diagnostics;
- standard-command augmentation v2 without copying frozen prefix/context rows;
- suffix-only causal SFT as the primary objective;
- ranking work only if future top-3 evidence supports it;
- a `5k-20k` formatting smoke and bounded LoRA/adaptation canary before larger
  compute;
- no history-conditioned SSH claim until its separate context/privacy and
  variable-host evaluation gates exist.

## Findings

None for the bounded T-104 outcome.

## Residual risk

The current alpha checkpoint is not releasable on the standard-command gate.
The public/synthetic panel proves only engineering quality; it does not prove
generalization, private-history behavior, or product acceptance. Those
boundaries are explicitly preserved.
