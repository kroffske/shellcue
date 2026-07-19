---
schema: task.v3
id: T-109
title: "Train and select model-only checkpoint"
status: planning
review_required: qa
plan_review_profile: deep
plan_review_gate: required
type: research
priority: p1
owner: manager
created_at: "2026-07-19T14:15:25.489Z"
updated_at: "2026-07-19T14:15:25.489Z"
parent: null
depends_on: [T-108]
milestone: m1-model-only-history
gstack_refs: {}
spec_refs: ["docs/specs/model-only-history-prediction/README.md#REQ-003", "docs/specs/model-only-history-prediction/README.md#REQ-005", "docs/specs/model-only-history-prediction/README.md#REQ-007"]
---

# T-109: Train and select model-only checkpoint

## Outcome

Bounded, reproducible training experiments produce either one selected
history-conditioned model-only checkpoint that passes every frozen gate or an
explicit no-promotion verdict. The selected artifact is tied to exact
base/tokenizer/data/evaluator/runtime identities and is ready for independent
runtime promotion.

Direction: on-track; execution is dependency blocked until T-108 freezes data
and evaluation.

Spec source: `docs/specs/model-only-history-prediction/README.md#REQ-003`,
`#REQ-005`, and `#REQ-007`.

## Decisions

- **Method is empirical, not preselected.** Compare bounded LoRA, full
  fine-tuning, or continued-training lanes only when they fit the declared
  hardware and artifact contract.
- **Exact checkpoint identity is mandatory.** Every adapter/merge targets one
  pinned weight and tokenizer revision; upstream-family compatibility is not
  accepted as deployed-checkpoint compatibility.
- **Quality selection is multi-gate.** History gains cannot compensate for
  standard-command, privacy, safety, latency, or target-collapse failures.
- **No-promotion is valid.** Failed candidates do not reopen history/catalog
  fallbacks or weaken frozen thresholds.
- **Training and serving remain separate.** Training metadata and dependencies
  never enter the default ShellCue runtime artifact/profile.
- **Execution owner is `shellcue-training`.** Smart Bash is not an import,
  environment, dataset, evaluator, trainer, or exporter dependency.
- **Do not preselect LoRA as product policy.** The prompt/data repair must be
  proven with bounded same-lineage causal canaries; the final training method is
  frozen before results and selected only under the artifact and compute
  contract.

Decision history: [planning.md](planning.md).

## Boundary

### Included

- **Training contract** — Exact target checkpoint, recipe matrix, seeds,
  hardware/resource envelope, data mixture, curriculum, checkpointing, and
  reproducibility, all executed from `shellcue-training`.
- **Selection gates** — Frozen T-104/T-108 evaluation,
  overfit/memorization checks, standard-command regression, target collapse,
  latency, and artifact consumability.
- **Promotion packet** — Candidate ranking, selected/no-promotion verdict, and
  immutable artifact identities.

### Excluded

- **Invalid experiment changes** — Frozen-data/threshold edits after results,
  private-history training, cloud upload, and fallback restoration.
- **Runtime activation** — Installation and serving belong to T-110.
- **Weak evidence** — Training loss, save/reload, or a qualitative demo alone
  cannot establish product improvement.

## Work items

- [ ] W1 (experiment contract): Pin target weights/tokenizer, candidate methods,
  dependency lock, data/eval hashes, seeds, hardware, time/memory/disk budgets,
  and stop rules.
  - Deliverable: reviewed experiment matrix and immutable run manifests.
- [ ] W2 (bounded canaries): Prove each viable lane can train, save, reload in a
  fresh process, and export or merge into a runtime-valid artifact shape.
  - Deliverable: canary evidence with resource measurements and failed-lane
    dispositions.
- [ ] W3 (candidate runs): Train the precommitted candidate matrix without
  modifying frozen panels or thresholds.
  - Deliverable: checkpoints, logs, manifests, hashes, and reproducible commands.
- [ ] W4 (frozen comparison): Run T-104 and T-108 gates plus safety, privacy,
  memorization, collapse, latency, and compatibility checks on base and every
  candidate.
  - Deliverable: comparable row-level results and summary verdicts.
- [ ] W5 (selection review): Select exactly one promotable checkpoint or record
  no promotion, with independent QA and a hash-bound rationale.
  - Deliverable: promotion packet consumed unchanged by T-110.

## Verification

- Fresh environment reproduces the selected run from locked dependencies,
  config, seed, data hashes, and target revision.
- Removing Smart Bash from `PYTHONPATH` does not change canary, training,
  evaluation, selection, or export behavior.
- Candidate artifact passes `shellcue model verify` or an explicitly accepted
  successor validator before it can be selected.
- Base and candidates use identical frozen rows, prompt packing, decode policy,
  metrics, denominators, and environment identity.
- Standard-command, history-conditioned, privacy/safety, target-collapse,
  latency, and resource gates all pass independently; aggregate score cannot
  mask a failed slice.
- Memorization/canary extraction and held-out identity substitution tests pass.
- Independent QA confirms the selected/no-promotion verdict from immutable
  evidence.

## Execution log

Pending T-108.

## Closure

Ship the immutable promotion packet or negative result without activating the
artifact. Runtime installation, daemon restart, rollback, and terminal proof
belong exclusively to T-110.
