## Q0: Goal alignment
Question: Does the existing standard-command evaluator still matter after the
catalog that made it pass is removed?
Source check: `.locus/soul.md` requires learned prediction;
`docs/specs/model-only-history-prediction/README.md` REQ-005 requires the same
gate without rule-based repair; the existing v5 evaluator is in
`/Users/ravius/projects/_worktrees/smart_bash-t104/scripts/evaluate_shellcue_standard_commands.py`.
Answer: Yes. The evaluator becomes more important because it measures checkpoint
quality instead of validating a runtime workaround.
Status: accepted-by-user
Direction: on-track
Consequence: Preserve the frozen families and metrics but require every
candidate source to be `model`.

## Q1: Baseline legality
Question: Can the prior 48/48 result remain the model baseline?
Source check: The accepted report was produced with
`standard_command_catalog_v1`, which generated answers absent from the alpha
checkpoint.
Answer: No. Re-run the exact checkpoint through the model-only runtime and label
the prior report policy-assisted historical evidence.
Status: source-proven
Consequence: The first deliverable is a fresh model-only baseline with immutable
runtime/model/evaluator identities.

## Q2: Scope of the evaluator
Question: Should T-104 absorb history-conditioned SSH evaluation?
Source check: The current evaluator owns standard command families and prefix
quality; the accepted spec gives variable-history data and evaluation to T-108.
Answer: Keep T-104 focused on standard commands and expose a composable result
contract consumed by T-108/T-109.
Status: source-proven
Consequence: Avoid one evaluator with mixed denominators and unclear ownership.
