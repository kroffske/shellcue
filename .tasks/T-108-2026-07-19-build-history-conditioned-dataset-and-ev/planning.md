## Q0: Goal alignment
Question: What evidence can prove a checkpoint learned to use history rather
than merely memorizing the most frequent continuation?
Source check: Accepted spec REQ-002/REQ-003/REQ-005, `.locus/soul.md` traps, and
the user's required empty, rare, repeated, deep, conflicting, and multi-host
cases.
Answer: Freeze a synthetic-first history-conditioned corpus and evaluator with
counterfactual context variants, multiple valid targets, source identity, and
standard-command composition.
Status: accepted-by-user
Direction: on-track
Consequence: Training cannot begin until dataset/evaluator manifests and
thresholds are immutable.

## Q1: Labels from plain history
Question: Can a history list provide acceptance or next-command labels by
itself?
Source check: T-102 distinguishes command-only imports from richer contextual
events and forbids fabricated `cwd`, shown, selected, or accepted fields.
Answer: No. Synthetic rows may define known targets; real command lists provide
commands/order only unless separately consented events prove more.
Status: source-proven
Consequence: Dataset provenance and label strength are explicit per row.

## Q2: Ambiguous SSH targets
Question: How should evaluation score several plausible hosts that share almost
the same prefix?
Answer: Freeze both ranked top-1 utility and top-k target coverage, group by
history composition/frequency, and detect collapse to one target.
Status: accepted-by-user
Consequence: A candidate cannot pass by always emitting the most frequent host.
