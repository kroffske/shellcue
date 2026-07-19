---
schema: task.v3
id: T-107
title: "Freeze history-context and privacy contract"
status: planning
review_required: human
plan_review_profile: deep
plan_review_gate: required
type: research
priority: p1
owner: manager
created_at: "2026-07-19T14:15:25.431Z"
updated_at: "2026-07-19T14:15:25.431Z"
parent: null
depends_on: []
milestone: m1-model-only-history
gstack_refs: {}
spec_refs: ["docs/specs/model-only-history-prediction/README.md#REQ-002", "docs/specs/model-only-history-prediction/README.md#REQ-003", "docs/specs/model-only-history-prediction/README.md#REQ-004"]
---

# T-107: Freeze history-context and privacy contract

## Outcome

An accepted context/privacy SDD fixes how variable-length shell history becomes
model input and offline rows without becoming a candidate source or an implicit
personal-data lifecycle. It resolves history selection, serialization,
identity copying, masking, consent, retention, deletion, latency, and
runtime/training ownership.

Direction: on-track with the model-only strategic outcome.

Spec source: `docs/specs/model-only-history-prediction/README.md#REQ-002`
through `#REQ-004`.

## Decisions

- **One versioned grammar across runtime and training.** Row builders,
  evaluators, and the runtime must serialize the same typed context or declare
  themselves incomparable.
- **ShellCue owns the public contract.** ShellCue commits the versioned prompt,
  typed-prefix, field-aware token-budget, suffix-label, and artifact vectors.
  `shellcue-training` verifies an exact vendored vector ledger and must not
  become a runtime dependency.
- **Selection is not prediction.** The history selector may bound and annotate
  recency/frequency/source position, but only the model may create and rank a
  continuation.
- **Safe identity copying is an explicit design problem.** Generic masking that
  destroys the hostname is insufficient; raw unbounded history is also
  insufficiently safe.
- **Consent surfaces stay separate.** Request-time local inference implies
  neither persistence, evaluation recording, training enrollment, export, nor
  upload.
- **Synthetic-first generic training.** Private history is unnecessary for
  teaching the context grammar and copy/selection behavior; any later personal
  adaptation remains outside m1.

Decision history: [planning.md](planning.md).

## Boundary

### Included

- **History grammar** — Zsh/Bash availability, depth/selection policy, repeats,
  ordering, session boundaries, truncation, token budget, and serialization.
- **Identity and privacy** — Safe local hostname/username/path copying, secret
  classes, shell operators, masking, logging, crash files, permissions,
  retention, inspection, export, revocation, deletion, and uninstall/purge.
- **Ownership map** — ShellCue runtime/contract and `shellcue-training`
  dataset/evaluator/trainer/export boundaries, including fixture versioning and
  compatibility failure behavior.
- **Resource envelope** — One bounded latency and resource contract for the
  first supported local profile.

### Excluded

- **Implementation** — Runtime code, dataset materialization, training, and
  checkpoint activation.
- **Unconsented data lifecycle** — Silent persistence, private-history upload,
  cloud inference, and acceptance labels that plain history cannot contain.
- **Personal adaptation** — LoRA architecture beyond the generic
  history-conditioned milestone.

## Work items

- [ ] W1 (current contract map): Trace shell history collection, masking,
  `RuntimeContext`, prompt packing, artifact inputs, logs, install/uninstall,
  and public-boundary tests.
  - Deliverable: SDD evidence table with exact source/test references.
- [ ] W2 (context grammar): Select and specify bounded history sampling,
  recency/frequency/depth annotations, order, deduplication semantics, empty
  state, truncation, tokenizer budget, and stable serialization.
  - Deliverable: versioned request/row schema with examples at zero, shallow,
    and deep history.
- [ ] W3 (identity and privacy): Specify safe transient copy handling for hosts,
  users, and paths plus fail-closed secret/control-operator policy and separate
  inference/persistence/eval/training lifecycles.
  - Deliverable: privacy threat model, adversarial fixtures, consent matrix,
    retention/export/revocation/deletion contract.
- [ ] W4 (runtime and data ownership): Fix package/profile boundaries,
  selector owner, schema versioning, errors, stale clients, compatibility,
  resource budget, and migration/rollback behavior.
  - Deliverable: `docs/sdd/history-context-privacy/history-context-privacy.md`
    linked from the feature spec plus the ShellCue-owned golden-vector contract
    consumed by `shellcue-training`.
- [ ] W5 (review and freeze): Reconcile independent technical/privacy review
  and obtain explicit human acceptance before T-108 starts.
  - Deliverable: hash-bound review evidence and accepted SDD status.

## Verification

- Every SDD requirement maps to accepted spec REQ-002, REQ-003, or REQ-004 and
  to a downstream task/evidence owner.
- Golden serialization fixtures cover empty history, repeated commands, rare
  deep commands, irrelevant/conflicting context, multiple near-identical SSH
  targets, multiline/control syntax, identities, and secret classes.
- Token-budget and latency estimates are measured on the declared alpha
  tokenizer/runtime rather than guessed.
- Privacy review proves request-only inference creates no ShellCue history
  file, log, telemetry, crash payload, or training row.
- Human acceptance is required because identity fidelity versus masking is a
  product/privacy trade-off.

## Execution log

Pending contract research and human acceptance.

## Closure

Ship the accepted SDD and spec decision update independently. T-108 may start
only from the accepted schema/hash; T-102 personal LoRA research remains
deferred.
