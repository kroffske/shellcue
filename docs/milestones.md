---
title: "Milestones"
updated_at: "2026-07-19"
---

# Milestones

Registry for the `milestone:` frontmatter field on tasks and temporal decision
docs. Exactly one milestone is active. Closing marks a row `done`; archival is a
separate evidence-preserving step.

| ID | Status | Period | Criterion | Note |
|---|---|---|---|---|
| m1-model-only-history | active | 2026-07-19 - | Done when all candidate-generating bypasses are absent, a history-conditioned model-only checkpoint passes frozen standard/history/privacy/compatibility gates, and the installed Zsh PTY proves automatic stale-safe suggestions from that checkpoint. | Immediate rollback first; data/eval freeze precedes training; no fallback may reopen. |

## m1-model-only-history

| Task | Role |
|---|---|
| T-106 — Enforce model-only candidate generation | Required to stop false model-quality claims and restore the installed source contract immediately. |
| T-104 — Build standard-command quality eval | Required to keep Git and other standard command families as a generalized model gate. |
| T-107 — Freeze history-context and privacy contract | Required before data or runtime work can choose history depth, identity handling, or consent semantics. |
| T-108 — Build history-conditioned dataset and evaluator | Required to freeze variable-history examples and promotion metrics before training. |
| T-109 — Train and select model-only checkpoint | Required to produce and compare the actual learned replacement for removed bypasses. |
| T-110 — Promote checkpoint and verify terminal runtime | Required to close artifact, install, daemon, rollback, latency, and PTY evidence. |

T-102 — Research local LoRA personalization architecture is deliberately not
in `m1-model-only-history`, because it owns opt-in personal adapter
architecture, until generic model-only history use and its privacy contract are
proven.
