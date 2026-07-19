## Q0: Goal alignment
Question: What training result advances the product rather than merely proving a
LoRA job can run?
Source check: `.locus/soul.md` requires model-owned prediction and
evidence-before-promotion; accepted spec REQ-003/REQ-005/REQ-007; T-102
separates feasibility from relevance.
Answer: A candidate advances only if it runs on the exact declared checkpoint,
is runtime-consumable, and beats the frozen model-only baseline without losing
standard-command, safety, latency, or multi-target behavior.
Status: accepted-by-user
Direction: on-track
Consequence: Training success, low loss, or one SSH demo cannot select a
checkpoint.

## Q1: Training method
Question: Should the task preselect LoRA, full fine-tuning, or continued
pretraining?
Source check: No history-conditioned candidate has been compared under T-108's
future frozen contract; current runtime artifact compatibility with dynamic
adapters is unproven.
Answer: Keep method as an experiment variable with a bounded matrix. Every lane
must target the exact declared weights/tokenizer and export a runtime-compatible
artifact or fail.
Status: source-proven
Consequence: The task selects on quality/resource/runtime evidence, not method
preference.

## Q2: Failure outcome
Question: What happens if every bounded candidate fails?
Answer: Preserve the model-only runtime, publish the negative result, and stop
without promoting a checkpoint or restoring a fallback.
Status: accepted-by-user
Consequence: A no-promotion outcome is valid and keeps the evaluation honest.
