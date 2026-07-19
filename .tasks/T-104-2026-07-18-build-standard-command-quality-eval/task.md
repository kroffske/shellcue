---
schema: task.v3
id: T-104
title: "Build standard-command quality eval"
status: review
review_required: qa
plan_review_profile: standard
plan_review_gate: required
type: feature
priority: p1
owner: manager
created_at: "2026-07-18T22:37:52.047Z"
updated_at: 2026-07-19T15:42:17.484Z
parent: null
depends_on: []
milestone: m1-model-only-history
gstack_refs: {}
spec_refs: ["docs/specs/model-only-history-prediction/README.md#REQ-005"]
---

# T-104: Build standard-command quality eval

## Outcome

The frozen standard-command quality gate measures only neural-model output
across command families and prefix depths. It produces an immutable baseline
for the installed alpha checkpoint and a reusable promotion verdict for later
history-conditioned candidates.

Direction: on-track with model-only prediction; the prior catalog-assisted
48/48 result is historical policy evidence, not a checkpoint-quality claim.

Spec source: `docs/specs/model-only-history-prediction/README.md#REQ-005`.

## Decisions

- **Model source is mandatory.** A row with any candidate source other than
  `model` fails the run instead of being adapted or relabelled.
- **Keep standard and history gates separate.** This task owns standard command
  families; T-108 owns variable-history behavior and later composes both
  verdicts.
- **Freeze before candidate comparison.** Panel, prefix lanes, metrics,
  thresholds, evaluator code hash, model identity, runtime identity, and
  environment are bound before T-109 results are read.
- **Abstention remains explicit.** Missing suggestions are not contamination,
  but useful-acceptance and coverage gates may still fail.

Decision history: [planning.md](planning.md).

## Boundary

### Included

- **Standard-command panel** — Git, package-manager, container, orchestration,
  service, and other frozen families at multiple prefix depths.
- **Quality metrics** — Parse validity, family consistency, severe
  contamination, false-show, abstention, useful acceptance, latency, and
  source identity.
- **Baseline contract** — Fresh model-only baseline and a machine-readable
  comparison envelope.

### Excluded

- **Answer synthesis** — Candidate catalogs, aliases, prompt rewrites that
  inject target answers, or evaluator-side healing.
- **Other lifecycle slices** — Variable-history SSH ranking, private data,
  model training, and runtime checkpoint activation.

## Work items

- [x] W1 (freeze model-only panel): Preserve the accepted v5 standard-command
  cases and add a hard `source=model` invariant plus immutable input identities.
  - Deliverable: versioned evaluator policy and panel manifests in Smart Bash.
- [x] W2 (fresh alpha baseline): Run the exact installed alpha checkpoint
  through the model-only ShellCue runtime and preserve row-level outputs,
  environment, timing, and verdict.
  - Deliverable: immutable baseline result/report with no adapter.
- [x] W3 (promotion contract): Define the machine-readable result consumed by
  T-109, with metric directions, denominators, thresholds, and incomparable-run
  behavior.
  - Deliverable: versioned standard-command evaluation envelope and tests.
- [x] W4 (regression proof): Exercise production, no-heal, token-tail, empty,
  and invalid-output lanes without candidate synthesis.
  - Deliverable: focused evaluator tests and reviewed quality report.

## Verification

- Run the existing evaluator from
  `/Users/ravius/projects/_worktrees/smart_bash-t104/scripts/evaluate_shellcue_standard_commands.py`
  against the installed model-only ShellCue binary.
- Every returned candidate has `source=model`; any other source produces a
  non-zero evaluator exit.
- Result records exact checkpoint, model weights, inference config, ShellCue
  commit/package hashes, evaluator hash, panel hash, environment, and latency.
- Unit tests prove metric denominators, thresholds, source rejection,
  abstention accounting, contamination, and deterministic row order.
- Independent QA re-runs the frozen gate before a result becomes promotable.

## Execution log

Planning refreshed after the owner rejected catalog-generated answers.

## Closure

Ship evaluator changes and the fresh model-only alpha baseline independently of
training candidates. T-109 consumes the frozen contract without modifying its
panel or thresholds.
