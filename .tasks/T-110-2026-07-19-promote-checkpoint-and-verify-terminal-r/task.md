---
schema: task.v3
id: T-110
title: "Promote checkpoint and verify terminal runtime"
status: planning
review_required: qa
plan_review_profile: deep
plan_review_gate: required
type: feature
priority: p1
owner: manager
created_at: "2026-07-19T14:15:25.513Z"
updated_at: "2026-07-19T14:15:25.513Z"
parent: null
depends_on: [T-109]
milestone: m1-model-only-history
gstack_refs: {}
spec_refs: ["docs/specs/model-only-history-prediction/README.md#REQ-001", "docs/specs/model-only-history-prediction/README.md#REQ-005", "docs/specs/model-only-history-prediction/README.md#REQ-006", "docs/specs/model-only-history-prediction/README.md#REQ-007", "docs/specs/model-only-history-prediction/README.md#REQ-008"]
---

# T-110: Promote checkpoint and verify terminal runtime

## Outcome

The selected model-only history-conditioned checkpoint is packaged, installed,
activated, and independently verified on the real ShellCue daemon and automatic
Zsh surface. Artifact identity, model-only source tracing, latency, stale
suppression, acceptance keys, privacy boundaries, and rollback all have
reproducible evidence sufficient to close the milestone.

Direction: on-track; execution is dependency blocked until checkpoint selection
closes and the model-only ShellCue base is merged.

Spec source: `docs/specs/model-only-history-prediction/README.md#REQ-001`,
`#REQ-005` through `#REQ-008`.

## Decisions

- **Promotion packet is immutable input.** Runtime work consumes T-109's exact
  `shellcue-training` artifact and aggregate evidence; material
  model/prompt/decode changes force reevaluation.
- **Model-only runtime is a merged prerequisite.** ShellCue PR #5 must already
  be in the promotion base; this task does not recreate or track the completed
  rollback task as an open dependency.
- **Installed behavior is the acceptance surface.** Package verification and
  offline generation cannot substitute for daemon and PTY evidence.
- **Rollback is a tested operation.** Prior model identity and service behavior
  are restored in a fresh process before final reactivation.
- **Model-only tracing remains mandatory.** Every visible candidate is
  attributable to a model call and `source=model`; safety may abstain only.
- **Human terminal observation is residual, not hidden.** Automated PTY proves
  mechanics; any remaining subjective ghost-text usefulness is stated
  separately.

Decision history: [planning.md](planning.md).

## Boundary

### Included

- **Artifact lifecycle** — Cross-repository promotion packet, manifest, hashes,
  license, registry install/use,
  daemon restart/reload, stale-client compatibility, activation, rollback, and
  purge ownership.
- **Installed acceptance** — Frozen standard/history gates, source tracing,
  automatic Zsh PTY, Tab/Shift-Tab, stale cancellation, latency, Apple Terminal
  noise, offline/no-network behavior, and independent QA.
- **Closure evidence** — Spec and milestone evidence updates.

### Excluded

- **Model and policy changes** — No further training, threshold changes, or
  fallback addition.
- **Adjacent runtime work** — No unrelated installer refactor or Bash automatic
  suggestions beyond its current contract.
- **Publication** — No public release, push, PR, or merge without explicit
  authorization.

## Work items

- [ ] W1 (artifact package): Validate runtime schema, file hashes, weights,
  tokenizer, inference config, licensing, provenance, version compatibility,
  and reproducible package identity.
  - Deliverable: digest-bound ShellCue model artifact and promotion manifest.
- [ ] W2 (install and activation): Install/register the candidate, restart the
  managed daemon, verify fresh-process identity, and reject stale package/model
  combinations.
  - Deliverable: installed-source/model/service evidence.
- [ ] W3 (rollback drill): Switch to the previous model and service state,
  verify it, then reactivate the candidate without stale clients or hooks.
  - Deliverable: raw rollback/reactivation transcript and identity hashes.
- [ ] W4 (installed evaluation): Re-run frozen T-104/T-108 gates, privacy,
  safety, no-network, latency, and source-identity checks against the installed
  candidate.
  - Deliverable: installed-runtime comparison report.
- [ ] W5 (terminal acceptance): Run isolated real Zsh PTY scenarios for
  automatic ghost text, continued typing, divergence/stale clearing, Tab one
  word, Shift-Tab full, and no Apple Terminal session-save output.
  - Deliverable: raw PTY transcript plus readable proof report.
- [ ] W6 (independent QA and closure): Review immutable identities and rerun
  critical installed paths before recording spec/milestone evidence.
  - Deliverable: accepted QA verdict or explicit rollback/block.

## Verification

- `shellcue model verify <candidate>` and registry install/use commands pass
  against the exact promotion manifest.
- Installed package, daemon, model, tokenizer, inference config, evaluator,
  panel, and PTY harness hashes are recorded.
- Every displayed candidate has a corresponding model invocation and
  `source=model`; repository and site-packages scans contain no history/catalog
  candidate source.
- Frozen standard/history gates and all mandatory privacy, safety,
  target-collapse, latency, and regression slices pass unchanged.
- A fresh-process rollback restores prior identity and behavior; reactivation
  restores the candidate without stale clients.
- Real isolated Zsh PTY proves automatic non-blocking display, stale clearing,
  acceptance keys, and no session-save noise.
- Independent QA accepts the installed evidence before the milestone criterion
  can be claimed.

## Execution log

Pending T-109 and the merged model-only ShellCue base.

## Closure

After accepted QA, update the feature spec evidence, close
`m1-model-only-history` only when every member task is done or explicitly
deferred, and keep public push/PR/merge/release as a separate authorized ship
action.
