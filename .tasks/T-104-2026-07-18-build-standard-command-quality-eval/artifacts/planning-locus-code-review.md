# Pre-code shape review

Verdict: SHAPE-READY

The evaluator belongs in Smart Bash's existing
`smart_bash.eval.standard_commands` owner and
`scripts/evaluate_shellcue_standard_commands.py` entrypoint. ShellCue remains
the installed production runner and must not gain training/evaluation modules.

Deletion-first target:

- remove `apply_runtime_policy`, `runtime_policy_identity`, catalog imports,
  and any source-envelope adapter;
- keep the frozen public/synthetic panel and its metric owner;
- make production and mirror lanes consume unmodified model candidates;
- fail the run on non-model source or production/mirror divergence.

No new evaluator framework, policy registry, ShellCue wrapper, or answer-healing
layer is justified. The result envelope may be versioned because later
checkpoint selection has a real cross-task consumer.
