---
schema: locus.spec.v1
id: model-only-history-prediction
title: "Model-only history-conditioned prediction"
status: active
trace_policy: required
owner: manager
created_at: "2026-07-19T14:20:00Z"
updated_at: "2026-07-19T14:20:00Z"
accepted: "2026-07-19"
source_commit: "78a5267"
milestone: "m1-model-only-history"
source_of_truth: "docs/specs/model-only-history-prediction/README.md"
related_tasks: [T-104, T-106, T-107, T-108, T-109, T-110]
---

# Model-only history-conditioned prediction

## Front Panel

- **Outcome:** ShellCue's local neural model generates and ranks every visible
  command continuation, including suggestions that depend on shell history.
- **Core decision:** History, standard-command knowledge, and other live state
  are model inputs; deterministic code may reject unsafe output but cannot
  create, rank, or substitute candidates.
- **Shape:** This README fixes the cross-cutting product contract; task-backed
  slices separately own rollback, context/privacy, evaluation, training, and
  checkpoint promotion.
- **Agent contract:** Run `locus spec context model-only-history-prediction --phase <phase>` before planning, implementation, review, or QA.
- **Task contract:** T-104, T-106, T-107, T-108, T-109, and T-110 carry
  `spec_refs` back to this README; `locus task state <id>` remains the source
  for execution status.
- **Risk / open question:** A 230M checkpoint may not reliably copy and rank
  several near-identical identity-bearing SSH targets within the interactive
  latency budget; failure blocks promotion rather than reopening a fallback.

## Scope

| Included | Excluded |
|---|---|
| Removal of candidate-generating runtime policies; variable-length history context; privacy and context-packing contract; synthetic and explicitly permitted data; frozen evaluation; bounded training; compatible artifact promotion; installed Zsh PTY proof. | Deterministic history lookup; command catalogs as answer sources; hard-coded aliases; hosted inference; silent history persistence or enrollment; private-history upload; unrelated IDE completion work. |

## Requirements and acceptance criteria

| ID | Requirement | Acceptance |
|---|---|---|
| REQ-001 | Every visible candidate is generated and ranked by the neural model. | Runtime and client accept only `source=model`; repository and installed-package scans contain no candidate-generating history/catalog path; a predictor spy proves every displayed candidate followed a model call. |
| REQ-002 | History is bounded model context, not a competing answer source. | Evaluated rows cover no history and useful history at varied recency/depth; tracing proves the selected context enters the model prompt and no history row is copied by non-model code. |
| REQ-003 | Training covers frequency and ambiguity rather than one exact replay. | Frozen data contains repeated, rare, deep, irrelevant, conflicting, and several near-identical SSH targets; QA checks top-1 ranking, top-k coverage, and collapse by target. |
| REQ-004 | Identity-bearing context stays local and secrets fail closed. | The accepted context/privacy contract distinguishes transient inference from persistence/training consent; adversarial fixtures cover credentials, tokens, shell control operators, paths, hosts, and deletion/retention boundaries. |
| REQ-005 | Model improvement is measured without rule-based repair. | Base and candidate checkpoints run through the same model-only evaluator with standard-command, history-conditioned, contamination, false-show, abstention, and regression gates frozen before results. |
| REQ-006 | Interactive behavior remains asynchronous and stale-safe. | Real Zsh PTY proof covers automatic ghost text, non-blocking typing, stale-result suppression, Tab one-word, Shift-Tab full, and no Apple Terminal session-save noise. |
| REQ-007 | A promoted checkpoint is consumable by the installed runtime. | `load_artifact`, registry installation, daemon restart, fresh-process inference, rollback, strict artifact checks, and installed-package source identity all pass for the selected checkpoint. |
| REQ-008 | The invalid bypasses are removed before model retraining is claimed. | `recent_history_exact_v1` is absent from the installed package; `standard_command_catalog_v1` is absent from source and installed runtime; any resulting alpha-model quality gap is reported as model debt. |

## Clarifications ledger

| ID | Question | Accepted answer | Consequence |
|---|---|---|---|
| Q-001 | Is exact history reuse an acceptable fast path? | No. The model must decide whether history matters on every request. | REQ-001, REQ-002, and T-106 remove the bypass rather than tune it. |
| Q-002 | May standard commands remain catalog-generated? | No. The model-only invariant is project-wide, not SSH-specific. | T-104 becomes an evaluation gate; T-106 removes `standard_command_catalog_v1`. |
| Q-003 | What should happen when history is absent or irrelevant? | The same model predicts from the remaining context and may abstain. | Training and evaluation require empty and irrelevant-history slices. |
| Q-004 | How should several similar SSH targets be handled? | The model must rank plausible alternatives without collapsing to one memorized target. | REQ-003 requires top-1, top-k, target-diversity, and frequency slices. |

## Decisions

| ID | Decision | Why | Consequence | Status |
|---|---|---|---|---|
| D-001 | Model output is the only candidate source. | Product quality must measure learned prediction, not a retrieval or catalog proxy. | REQ-001, REQ-002, REQ-005, REQ-008: runtime accepts only `source=model`; a model miss becomes abstention. | accepted |
| D-002 | Deterministic safety remains rejection-only. | Removing safety would trade one proxy bug for a command-execution risk. | REQ-001, REQ-004, REQ-008: validators may drop candidates but cannot replace or reorder them with preferred commands. | accepted |
| D-003 | Roll back bypasses before a replacement checkpoint exists. | Keeping an invalid path would continue presenting false model quality. | REQ-008: temporary alpha-model regressions are recorded honestly and owned by the milestone. | accepted |
| D-004 | Train generic history use before personal adaptation. | The checkpoint must first learn the context grammar and copy/selection behavior on controlled data. | REQ-002, REQ-003, REQ-004: T-102 remains outside m1; private LoRA personalization is deliberately deferred. | accepted |
| D-005 | Freeze data and evaluation before training. | Post-hoc examples and thresholds make model selection unfalsifiable. | REQ-003, REQ-005: T-108 produces immutable manifests and gates before T-109 reads candidate results. | accepted |
| D-006 | Keep training outside the runtime package. | Runtime privacy, install size, and dependency boundaries must not depend on training machinery. | REQ-004, REQ-007: training/eval code lives in its owning project/profile and exports only verified artifacts/evidence. | accepted |
| D-007 | Promote only through the real installed surface. | Offline generation does not prove daemon, shell-hook, latency, or artifact compatibility. | REQ-001, REQ-005, REQ-006, REQ-007: T-110 owns install, rollback, PTY, and installed-source evidence. | accepted |

## Design

| Surface | Role |
|---|---|
| `src/shellcue/models/neural.py` | Owns model decode and returns only model-originated candidates. |
| `src/shellcue/models/candidates.py` | Rejects unsafe or structurally invalid model output without synthesizing replacements. |
| `src/shellcue/runtime/context.py` | Owns bounded request-time context rendering; its successor contract is fixed by T-107. |
| `src/shellcue/runtime/shell_integration.py` | Collects live context and renders asynchronous suggestions; it does not predict. |
| `/Users/ravius/projects/smart_bash` | Owns training and offline evaluation experiments; exported artifacts must satisfy ShellCue's runtime contract. |

No additional SDD is accepted yet. T-107 must either publish the context/privacy
design as a linked SDD or record why the compact contract belongs in this
README before context implementation begins.

## Tasks

| Task | Role | Status |
|---|---|---|
| T-106 — Enforce model-only candidate generation | Removes and installs out current candidate-generating bypasses; proves model-only source identity. | `locus task state T-106` |
| T-104 — Build standard-command quality eval | Preserves generalized standard-command quality as a checkpoint gate, not a runtime answer source. | `locus task state T-104` |
| T-107 — Freeze history-context and privacy contract | Fixes context selection, identity copying, consent, masking, and runtime/training boundaries. | `locus task state T-107` |
| T-108 — Build history-conditioned dataset and evaluator | Materializes frozen variable-history data and comparable model-only evaluation. | `locus task state T-108` |
| T-109 — Train and select model-only checkpoint | Runs bounded candidates and promotes only a checkpoint that beats the frozen baseline. | `locus task state T-109` |
| T-110 — Promote checkpoint and verify terminal runtime | Packages the selected artifact and proves the installed daemon and PTY behavior. | `locus task state T-110` |

## Verification and evidence

| Requirement | Evidence | Result |
|---|---|---|
| REQ-001, REQ-008 | T-106 repository tests, installed-package scan, direct suggestion source trace, and PTY transcript. | pending T-106 |
| REQ-005 | T-104 standard-command panel plus T-108 history-conditioned evaluator manifests and reviewed reports. | pending T-104/T-108 |
| REQ-002, REQ-003, REQ-004 | T-107 accepted contract and T-108 frozen fixtures/adversarial privacy gates. | pending T-107/T-108 |
| REQ-005, REQ-007 | T-109 checkpoint comparison and T-110 artifact/install/rollback evidence. | pending T-109/T-110 |
| REQ-006 | T-110 real Zsh PTY transcript on the installed candidate. | pending T-110 |

## Change history

| Date | Change | Reason |
|---|---|---|
| 2026-07-19 | Initial accepted specification. | The owner rejected deterministic history and catalog completions as invalid product behavior and requested a model-training milestone. |

## Source of truth

This README wins over generated indexes and remembered task outcomes for the
feature contract. `locus task state <id>` wins for task lifecycle. Current code
plus accepted QA evidence wins when it proves this README stale; update the
README before further implementation rather than preserving a contradicted
requirement.
