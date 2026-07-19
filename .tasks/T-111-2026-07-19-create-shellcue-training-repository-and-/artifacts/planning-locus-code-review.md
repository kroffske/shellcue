# Improve codebase: ShellCue runtime/training repository split

## Target

Move reusable ML engineering out of Smart Bash into a focused
`shellcue-training` repository while keeping ShellCue's installed runtime small,
offline, and independently releasable.

## Evidence

- `README.md:60-87` says only runtime/inference code ships in ShellCue and no
  training/evaluation command exists.
- `tests/test_public_boundary.py:10-32` mechanically rejects Smart Bash, data,
  evaluation, training, scripts, Kaggle, and integration ownership.
- `pyproject.toml:44-45` packages only `src/shellcue`.
- Smart Bash mixes data/eval/training logic with runtime/model imports,
  task-numbered experiments, generated artifacts, and historical product code.
- Smart Bash Work3 T-299 contains the useful eight-stage repair plan but places
  ongoing training ownership in the legacy repository.

## Owner and interface map

| Owner | Responsibility | Interface | Failure behavior |
| --- | --- | --- | --- |
| ShellCue contract | Prompt/context/artifact consumption | Versioned spec, vectors, hashes | Reject unknown/drifted contract |
| ShellCue runtime | Live masked context, decode, safety, daemon, PTY | Artifact plus request context -> model candidate | Abstain; never fallback |
| `shellcue-training` data | Rows, splits, synthetics, manifests | Contract-shaped immutable datasets | Fail closed on audit/hash/privacy |
| `shellcue-training` eval | Frozen panels and metrics | Artifact + frozen rows -> result envelope | Reject source/contract mismatch |
| `shellcue-training` trainer | Canaries/full run/checkpoint selection | Frozen data/config/base -> candidate | Stop or no-promotion |
| `shellcue-training` exporter | Runtime artifact and promotion packet | Candidate identities -> immutable package | Reject incomplete provenance |

## Reuse, rewrite, reject

- Reuse algorithms for event materialization, frozen standard-command
  evaluation, causal training, best-checkpoint selection, manifests, and
  artifact hashing.
- Rewrite Smart Bash imports, runtime coupling, script-first orchestration, and
  duplicate prompt rendering behind package-owned APIs.
- Reject runtime/daemon/history/retrieval ownership, wholesale history copy,
  private/generated artifacts, broad historical experiments, and semantic
  fallbacks.

## Selected shape

One new package owns ML workflows. ShellCue owns the public contract; the new
repository verifies an exact vendored fixture ledger. Installed evaluation uses
the executable or immutable artifact boundaries, not cross-repository Python
imports.

## Independently reviewable slices

1. ShellCue contract, vectors, schema support, and canonical task graph; no
   model cutover.
2. New repository bootstrap, donor manifest, core migration, and independence
   proof.
3. Dataset/evaluation freeze.
4. Training and artifact selection.
5. ShellCue installed promotion and PTY proof.

## Growth trigger

Replan if the migration needs a third package, imports Smart Bash at execution
time, requires a breaking ShellCue runtime change, expands beyond the frozen
donor manifest, includes private/uncertain-license content, or introduces a new
trainer/model family.

## Planner summary

- Decision: separate repositories are required because training ownership and
  dependencies are incompatible with ShellCue's installed runtime contract.
- Simplicity: fresh selective extraction is smaller and safer than forking the
  Smart Bash working tree or preserving its mixed Git history.
- Verification: golden-vector parity plus Smart-Bash deletion is the key proof;
  successful imports in the donor checkout would be a false green.
