## Q0: Goal alignment
Question: What evidence closes the gap between an offline winning checkpoint and
the actual ShellCue product?
Source check: Accepted spec REQ-006/REQ-007, `.locus/soul.md` real-PTY
principle, installer/service contracts, and prior incidents where daemon health
did not prove interactive suggestions.
Answer: Package and install the exact selected artifact, verify source/model
identity and rollback, then test the automatic Zsh interaction through a real
PTY under latency and stale-result pressure.
Status: accepted-by-user
Direction: on-track
Consequence: Offline evaluation is necessary but cannot close the milestone.

## Q1: Activation failure
Question: May T-110 patch runtime policy to make a candidate pass after
selection?
Answer: Only compatibility fixes already covered by the accepted artifact
contract are allowed and require rerunning frozen evaluation. Candidate
synthesis, answer catalogs, or unreviewed prompt changes are prohibited.
Status: accepted-by-user
Consequence: Runtime evidence remains attributable to the selected model.

## Q2: Rollback
Question: What must rollback restore?
Source check: ShellCue registry and daemon activation are separate from the
installed Python package; stale clients and hooks can continue speaking an old
contract after model changes.
Answer: Preserve the prior model registration, inference config, daemon and
shell-client compatibility, and prove a fresh process returns to the prior
identity and behavior.
Status: source-proven
Consequence: Rollback is exercised, not described.
