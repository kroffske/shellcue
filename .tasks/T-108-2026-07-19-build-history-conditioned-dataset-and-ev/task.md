---
schema: task.v3
id: T-108
title: "Build history-conditioned dataset and evaluator"
status: planning
review_required: qa
plan_review_profile: standard
plan_review_gate: required
type: feature
priority: p1
owner: manager
created_at: "2026-07-19T14:15:25.462Z"
updated_at: "2026-07-19T14:15:25.462Z"
parent: null
depends_on: [T-104, T-107, T-111]
milestone: m1-model-only-history
gstack_refs: {}
spec_refs: ["docs/specs/model-only-history-prediction/README.md#REQ-002", "docs/specs/model-only-history-prediction/README.md#REQ-003", "docs/specs/model-only-history-prediction/README.md#REQ-004", "docs/specs/model-only-history-prediction/README.md#REQ-005"]
---

# T-108: Build history-conditioned dataset and evaluator

## Outcome

A reproducible synthetic-first dataset builder and model-only evaluator freeze
the examples, provenance, splits, metrics, and promotion thresholds needed to
train history-conditioned ShellCue checkpoints without leaking runtime or
private-history assumptions.

Direction: on-track with the accepted feature spec; execution is dependency
blocked until T-104, T-107, and the `shellcue-training` extraction in T-111
close.

Spec source: `docs/specs/model-only-history-prediction/README.md#REQ-002`
through `#REQ-005`.

## Decisions

- **Rows use the accepted context grammar.** Any runtime/evaluator serialization
  mismatch makes a run incomparable.
- **Counterfactual context is mandatory.** Empty, useful, irrelevant,
  conflicting, reordered, and frequency-modified variants distinguish learned
  context use from prefix-only priors.
- **Plain history has weak labels.** Command lists never fabricate cwd,
  suggestion, selection, acceptance, or user-intent fields.
- **Ambiguity gets ranked metrics.** Top-1 utility, top-k coverage, target
  diversity, and collapse slices coexist; one metric cannot hide another.
- **Freeze before training.** Input manifests, split/dedup policy, metrics,
  thresholds, and evaluator code are immutable before T-109 results.
- **Training-repository ownership.** All builders, audits, frozen panels, and
  evaluator commands execute in `shellcue-training`; ShellCue supplies contract
  vectors and remains runtime-only.

Decision history: [planning.md](planning.md).

## Boundary

### Included

- **History corpus** — Synthetic SSH/SSH-add/SCP/SFTP/rsync histories with
  varied depth, frequency, similarity, conflicts, identities, and unsafe
  negatives.
- **Control rows** — Empty/irrelevant-history and standard-command cases.
- **Data contract** — Provenance, licensing, deduplication, split policy,
  contamination checks, and immutable manifests.
- **Evaluation contract** — Schema, latency/quality metrics, and composition
  with the T-104 standard-command result.

### Excluded

- **Other lifecycle slices** — Private-history enrollment, runtime collection,
  model training, artifact packaging, and shell integration.
- **Evaluator manipulation** — Heuristic candidate generation, answer repair,
  and post-result threshold changes.

## Work items

- [ ] W1 (row contract): Implement the accepted T-107 schema and provenance
  tiers in `shellcue-training` without importing training code into runtime or
  importing ShellCue internals into training.
  - Deliverable: typed row/schema validators and golden serialization fixtures.
- [ ] W2 (dataset generator): Generate balanced variable-history curricula and
  counterfactual pairs for recency, frequency, depth, relevance, conflict, and
  multiple near-identical targets.
  - Deliverable: deterministic generator, config, data card, and hashed train,
    validation, and untouched test manifests.
- [ ] W3 (privacy/contamination): Add secret/control-operator negatives,
  license/provenance checks, near-duplicate removal, and split leakage audits.
  - Deliverable: fail-closed audit report and adversarial fixture suite.
- [ ] W4 (model-only evaluator): Measure exact/top-k utility, coverage,
  abstention, target collapse, history reliance, standard-command regression,
  latency, and source identity on identical runtime-shaped rows.
  - Deliverable: versioned evaluator and machine-readable result envelope.
- [ ] W5 (freeze and QA): Bind hashes, thresholds, environment, model/runtime
  comparability rules, and independent QA before exposing the panel to T-109.
  - Deliverable: immutable evaluation contract and accepted baseline reports.

## Verification

- Dataset regeneration from the same config/seed produces identical manifests
  and deterministic row order.
- Tests cover history lengths and target positions from no history through the
  accepted deep bound, repeat counts, counterfactual swaps, similar hosts, and
  unsafe/private literals.
- Split audit finds no exact or near-duplicate train/eval targets under the
  frozen policy.
- Evaluator rejects non-`model` sources, missing identity, incompatible context
  serialization, changed panel hashes, and changed thresholds.
- Base checkpoint and later candidates run with the same tokenizer, prompt
  packing, decode contract, environment identity, and denominators.
- Independent QA reviews row semantics and reruns the frozen gate.

## Execution log

Pending T-104, T-107, and T-111.

## Closure

Ship the frozen dataset/evaluator and baseline evidence before any T-109
candidate training. Do not combine generated data, training outputs, and
runtime activation in one commit or artifact claim.
