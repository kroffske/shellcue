---
schema: task.v3
id: T-111
title: "Create ShellCue Training repository and migrate ML ownership"
status: done
review_required: qa
plan_review_profile: standard
plan_review_gate: required
type: feature
priority: p1
owner: manager
created_at: "2026-07-19T18:33:21.459Z"
updated_at: 2026-07-19T19:54:49.950Z
parent: null
depends_on: []
milestone: m1-model-only-history
gstack_refs: {}
spec_refs: ["docs/specs/model-only-history-prediction/README.md#REQ-002", "docs/specs/model-only-history-prediction/README.md#REQ-005", "docs/specs/model-only-history-prediction/README.md#REQ-007"]
---

# T-111: Create ShellCue Training repository and migrate ML ownership

## Outcome

A sibling `/Users/ravius/projects/shellcue-training` repository owns ShellCue
dataset construction, offline evaluation, model training, candidate selection,
and artifact export. It is independently installable and reproducible without
Smart Bash. ShellCue remains the runtime/inference product and consumes only a
versioned contract, golden fixtures, and promoted model artifacts.

The migration is selective and evidence-backed. Smart Bash remains a historical
donor, not an active dependency or second planning authority. The current
eight-stage prompt/data/training repair is represented once in ShellCue's
canonical task graph.

Spec source: `docs/specs/model-only-history-prediction/README.md#REQ-002`,
`#REQ-005`, and `#REQ-007`, introduced by prerequisite ShellCue PR #5.

## Decisions

- **Repository split:** `shellcue-training` is a new sibling repository with
  Python package `shellcue_training`; ShellCue remains runtime-only.
- **Contract authority:** ShellCue owns prompt/context and runtime artifact
  contracts. The training repository vendors exact golden vectors and verifies
  bytes, tokens, label spans, overflow behavior, and hashes.
- **No shared runtime package:** Neither repository imports the other at
  runtime. A third shared package is deferred unless fixture parity proves
  insufficient.
- **Selective migration:** Copy no Smart Bash Git history or working tree.
  Every donor file is classified `migrate`, `rewrite`, `reference`, or `reject`
  and recorded with source/target hashes and provenance.
- **Smart Bash retirement boundary:** After migration proof, Smart Bash is
  removable from `PYTHONPATH` and its T-299 plan is reference-only.
- **Publication boundary:** Create a local Git repository first. A GitHub remote
  or public release requires separate license, privacy, data, and history audit.
- **Base prerequisite:** ShellCue PR #5 must merge before implementation starts
  because it introduces the model-only spec and removes invalid deterministic
  candidate ownership.
- **Model work boundary:** This task creates the training surface and migration
  proof. Dataset freeze, model training, artifact selection, and installed
  cutover remain T-108 (build history-conditioned dataset/evaluator), T-109
  (train/select checkpoint), and T-110 (promote and verify runtime).

Decision history: [planning.md](planning.md).

## Boundary

### Included

- ShellCue contract/task-authority slice needed by the new repository.
- New repository scaffold, dependency lock, package/CLI layout, tests, and CI.
- Selective migration/rewrite of current data, evaluation, training, artifact,
  privacy, configuration, documentation, and supporting test logic.
- Donor manifest, license/provenance audit, golden-vector parity, fresh-env
  installation, Smart-Bash deletion test, and ShellCue boundary regression.
- Canonical mapping of the eight repair stages into T-107 (freeze context and
  privacy) through T-110 (promote and verify runtime).

### Excluded

- Training or promoting a production checkpoint.
- Copying Smart Bash runtime, daemon, shell integration, retrieval/history
  store, deterministic candidate generation, private data, runs, checkpoints,
  reports, caches, task history, or broad historical experiments.
- Changing ShellCue's installed model or automatic-suggestion behavior.
- Publishing a remote repository, uploading data, or starting external compute
  without its own explicit approval and audit.

## Work items

- [x] W1 (freeze ownership and donor manifest): Record repository commits,
  selected donor paths, dispositions, source hashes, license/provenance, import
  dependencies, and explicit rejected classes.
  - Deliverable: reviewed migration manifest and no-copy/private-data policy.
- [x] W2 (land ShellCue contract authority): Add/version the prompt/artifact
  contract and golden fixtures required by training, preserve runtime-only
  packaging, and update the canonical milestone/task dependency graph.
  - Deliverable: isolated ShellCue PR with contract tests and no model cutover.
- [x] W3 (bootstrap sibling repository): Create local
  `/Users/ravius/projects/shellcue-training`, package `shellcue_training`,
  locked dependencies, package-first module layout, thin CLI, tests, and CI.
  - Deliverable: clean local Git repository that installs in a fresh env.
- [x] W4 (migrate data/evaluation core): Rewrite selected materialization,
  context packing, benchmark, standard-command, privacy, split, and manifest
  logic against the ShellCue contract.
  - Deliverable: deterministic dataset/eval commands and golden-vector parity.
- [x] W5 (migrate training/artifact core): Rewrite the current Liquid causal
  trainer, preflight, canary, checkpoint-selection, provenance, and artifact
  exporter without Smart Bash runtime imports.
  - Deliverable: bounded canary/export path plus a fixture artifact accepted by
    `shellcue model verify`.
- [x] W6 (migrate active docs/config/tests): Port only current contracts,
  generic Liquid configs, data cards, experiment docs, and load-bearing tests;
  record historical or rejected files instead of copying them.
  - Deliverable: self-contained operator documentation and test coverage.
- [x] W7 (prove independence and privacy): Run fresh-env, Smart-Bash deletion,
  import/package scans, donor-manifest audit, ShellCue build/public-boundary
  regression, and cross-repository contract tests.
  - Deliverable: QA evidence sufficient to declare ownership migrated.
- [x] W8 (retire old authority and prepare delivery): Mark Smart Bash T-299
  (repair prompt framing and retrain Liquid) superseded/reference-only, record
  downstream task owners/dependencies, and prepare separate PR/audit boundaries
  for ShellCue and the new repository.
  - Deliverable: one canonical ShellCue task graph and reviewed handoff to
    T-108.

## Verification

- Fresh `uv sync` and full tests succeed in `shellcue-training`.
- Removing Smart Bash from `PYTHONPATH` does not break any new package import,
  test, CLI command, evaluator, trainer canary, or artifact export.
- A machine-readable donor manifest binds original commit/path/SHA-256,
  disposition, target path/SHA-256, license, and rewrite rationale.
- Repository and package scans find no Smart Bash runtime imports, private
  histories, datasets, checkpoints, `runs/**`, caches, or fallback code.
- ShellCue and `shellcue-training` produce identical canonical prompt bytes,
  tokenizer ids, retained fields, overflow results, suffix label spans, and
  contract/vector hashes for every golden fixture.
- The standard-command panel and prompt-framing collision cases run from the
  new repository with raw model candidates only.
- A fixture export passes `shellcue model verify`; the new repository does not
  import ShellCue internals to make it pass.
- ShellCue's `uv build`, full tests, and `tests/test_public_boundary.py` pass;
  its wheel/default dependencies contain no training code or dependencies.
- Independent QA reruns the critical parity and deletion tests from clean
  environments.

## Execution log

Planning complete; implementation not started.

## Closure

Close only after both independently reviewable delivery slices exist:

1. ShellCue contract/task authority with runtime boundary preserved and no
   installed model cutover.
2. A runnable `shellcue-training` repository with selective migration,
   parity/deletion/privacy proof, and no Smart Bash execution dependency.

GitHub publication remains a separate explicit ship decision after repository
history, licensing, and data-privacy audit. T-108 (build history-conditioned
dataset/evaluator) may begin only from the accepted contract/vector hash and
migrated training surface.
