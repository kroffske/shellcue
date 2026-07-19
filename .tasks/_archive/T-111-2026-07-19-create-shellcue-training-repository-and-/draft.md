# T-111: Draft

$locus-plan + auto grill
$locus-pm

Task:
Create a sibling `shellcue-training` repository and move the reusable
dataset, evaluation, training, and artifact-export ownership out of Smart Bash.
Keep ShellCue as the inference/runtime product and move the current eight-stage
model-repair plan into ShellCue's canonical task graph.

Draft goal:
A clean, independently installable `shellcue-training` repository can build
datasets, freeze evaluations, run bounded Liquid-model experiments, and export
a ShellCue-verifiable artifact without importing Smart Bash or leaking training
dependencies into ShellCue. ShellCue contains the canonical task and contract
references; Smart Bash remains historical donor evidence only.

Context:
- ShellCue's README, wheel configuration, and public-boundary test already
  define a runtime-only package.
- Smart Bash contains the existing training/evaluation implementation plus
  large historical runs, data, runtime code, and one-off experiments that must
  not be copied wholesale.
- The eight-stage prompt/data/training repair plan currently lives only in
  Smart Bash Work3 as T-299 and therefore has the wrong ownership and delivery
  boundary.

Draft direction:
- In scope: bootstrap the new repository, selectively migrate and rewrite the
  current ML core, prove cross-repository contract parity, and rebind ShellCue's
  downstream tasks to the new owner.
- Out of scope: copying Smart Bash history or private data, training a new
  checkpoint in this extraction task, cutting over the installed model, or
  creating deterministic history/catalog fallbacks.
- Outcome type: working delivery — a runnable repository boundary and
  independently verified migration, not a design document alone.

Evidence needed:
- A donor manifest classifies each selected Smart Bash path as
  `migrate`, `rewrite`, `reference`, or `reject`, with source hashes.
- Fresh-environment tests prove the new repository works after Smart Bash is
  removed from `PYTHONPATH`.
- Golden prompt bytes, token ids, label spans, and artifact metadata match
  ShellCue's public contract.
- ShellCue's build and public-boundary tests prove no training package or
  dependency leaked into runtime.

Execution notes:
- Land separate reviewable changes: ShellCue contract/task authority first,
  new-repository bootstrap and migration second, experiments later.
- Create the local sibling repository before any public remote. GitHub
  visibility and publication require a separate license/privacy/history audit.
- T-299 in Smart Bash is reference-only after this plan lands; do not merge it
  as the canonical product task.
