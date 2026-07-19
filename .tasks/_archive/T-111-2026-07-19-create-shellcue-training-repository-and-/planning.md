# Planning: create ShellCue Training and migrate ML ownership

## Q0: Product and repository boundary

Question: Where should model training live?

Source check:

- `README.md:60-87` defines ShellCue as runtime/inference only and explicitly
  excludes training and evaluation commands.
- `tests/test_public_boundary.py:10-32` rejects Smart Bash, Kaggle, data,
  evaluation, training, and script ownership inside the runtime tree.
- `pyproject.toml:44-45` builds only `src/shellcue`.
- `.locus/soul.md` requires model-only prediction and separates runtime from
  training/data/evaluation.

Answer: create `/Users/ravius/projects/shellcue-training` with package
`shellcue_training`. ShellCue remains the installed runtime. Smart Bash becomes
a read-only donor and historical evidence source.

Status: accepted-by-user

Consequence: no trainer, dataset builder, notebook, experiment dependency, or
raw training data enters the ShellCue wheel or default dependency set.

## Q1: New repository ownership

Question: What belongs in `shellcue-training`?

Answer:

- dataset ingestion, normalization, masking audits, synthetic generation,
  split/materialization, manifests, and data cards;
- offline quality evaluation, frozen panels, metrics, comparability checks,
  and candidate selection;
- bounded training canaries and full training runs;
- training checkpoints, run metadata, artifact export, and aggregate-only
  promotion packets;
- training-specific privacy, licensing, provenance, and publication gates.

ShellCue retains:

- the public prompt/context and artifact-consumption contract;
- request-time context capture and masking;
- local model loading, decoding, candidate rejection, daemon, installer,
  shell integration, and PTY acceptance;
- final `shellcue model verify` and installed-artifact proof.

Status: accepted-by-user

Consequence: installed evaluation invokes a ShellCue executable/daemon or
consumes immutable artifacts. It does not import runtime internals as a library.

## Q2: Cross-repository contract

Question: How do both repositories stay byte-equivalent without coupling their
release cycles?

Options:

1. Make ShellCue import `shellcue-training`.
2. Publish a third shared package.
3. Let ShellCue own a versioned contract and golden vectors; vendor the exact
   vectors into `shellcue-training` and verify hashes and rendered outputs.

Decision: option 3.

Rationale: option 1 violates the runtime boundary. Option 2 adds a third release
stream before the contract is stable. Golden vectors make drift fail visibly
without runtime dependency coupling.

Required parity fields:

- canonical UTF-8 prompt bytes;
- tokenizer revision and token ids;
- retained context fields and overflow outcome;
- complete typed-prefix visibility;
- suffix-only label span;
- prompt/target/artifact contract ids and vector-ledger SHA-256.

Status: source-proven

Consequence: a contract change lands in ShellCue first. Training/data work is
blocked until the new repository passes the updated vectors.

## Q3: Repository shape and command surface

Decision:

```text
shellcue-training/
  pyproject.toml
  uv.lock
  src/shellcue_training/
    contracts/
    data/
    eval/
    training/
    artifacts/
    privacy/
  configs/
  tests/
  docs/
  tools/
```

Stable operator surface:

```text
shellcue-training dataset build|audit
shellcue-training eval run|freeze
shellcue-training train canary|run
shellcue-training artifact export|verify
```

The repository has no daemon, shell hook, suggestion renderer, installation, or
history-recording command.

Status: accepted-by-user

Consequence: library modules own reusable logic; command entry points are thin
adapters. One-off historical scripts are not recreated as the primary API.

## Q4: Smart Bash migration policy

Question: Should Smart Bash be copied, forked, or selectively extracted?

Decision: selective extraction with rewrite. Start a fresh repository; do not
copy Smart Bash Git history or working tree wholesale.

Why:

- Smart Bash contains both runtime and training surfaces.
- local artifacts and historical data make the checkout tens of gigabytes;
- many scripts import `smart_bash.*` runtime/model modules;
- task folders, experiment reports, checkpoints, and private histories are not
  distributable source.

Each donor path receives one disposition:

- `migrate`: reusable logic already matches the new owner;
- `rewrite`: useful algorithm, wrong dependencies or interface;
- `reference`: historical evidence only;
- `reject`: runtime, fallback, private, generated, or obsolete content.

Every migrated/rewritten source records origin commit, source path, source
SHA-256, target path, license/provenance decision, and rewrite notes.

Status: source-proven

Consequence: Smart Bash can later be absent without breaking new commands or
tests. It remains an audit trail, not a runtime dependency.

## Q5: What moves

### Core data and evaluation

- `src/smart_bash/data/token_suffix_export.py`;
- `src/smart_bash/eval/autocomplete.py`;
- `src/smart_bash/eval/benchmark_v2.py`;
- `src/smart_bash/eval/context_pack.py`;
- `src/smart_bash/eval/standard_commands.py`;
- only latency/path/quality helpers referenced by the frozen current gates.

These move mostly as rewrites because current imports and product naming bind
them to Smart Bash.

### Dataset and training

- `training/kaggle/runners/train_causal_command_lm.py`;
- `training/kaggle/runners/preflight_freeze.py`;
- `training/kaggle/utils/training_history.py`;
- `training/kaggle/datasets/build_token_suffix_dataset.py`;
- `build_shell_family_coverage_dataset.py`;
- `build_synthetic_filesystem_transcripts.py`;
- `build_standard_command_curriculum.py`;
- active generic Liquid recipes required by the selected experiment contract.

Kaggle is one execution adapter, not the new package architecture.

### Operator workflows

Migrate the behavior behind current benchmark, materialization, preflight,
candidate-scoring, standard-command evaluation, and artifact-export scripts
into package commands. Preserve wrapper scripts only where an external platform
requires a file entry point.

### Contracts and documentation

- `ML-CONTRACT.md`;
- `docs/ml-experiment-contract.md`;
- `docs/models/alpha-prompt-framing-diagnosis.md`;
- `docs/models/token-suffix-artifact.md`;
- `docs/datasets/token-suffix-dataset.md`;
- `docs/experiments/next-autocomplete-quality-cycle.md`;
- current tests supporting the selected modules.

Status: source-proven

Consequence: migration follows the detailed inventory artifact; file presence
alone never proves a successful move.

## Q6: What does not move

Reject:

- Smart Bash CLI, daemon, runtime decode, shell integration, retrieval,
  history database, collector, or deterministic candidate sources;
- `runs/**`, datasets, checkpoints, local histories, `.local/**`, `.tasks/**`,
  reports, raw traces, caches, and private data;
- broad `t###` experiment configs/scripts/notebooks unless a current frozen
  contract directly names them;
- legacy publication shims and Smart Bash product documentation;
- any history/catalog fallback or answer-repair path.

Status: accepted-by-user

Consequence: migration size remains reviewable, licensing/privacy review has a
bounded surface, and the new project does not inherit dead experiments.

## Q7: Reconcile the current eight-stage repair plan

The Smart Bash Work3 task T-299 (repair prompt framing and retrain Liquid) is
not copied as a second authority. Its useful content maps into ShellCue's
existing milestone:

1. Contract and privacy freeze -> T-107 (freeze history-context and privacy
   contract).
2. ShellCue prompt/artifact support without cutover -> T-111 (create
   ShellCue Training) contract slice.
3. Training materializer and parity -> T-111 (create ShellCue Training)
   bootstrap plus T-108
   (history-conditioned dataset/evaluator).
4. Dataset successor and synthetic curriculum -> T-108 (build
   history-conditioned dataset/evaluator).
5. Frozen evaluation and micro-overfit -> T-108 (build history-conditioned
   dataset/evaluator) and T-109 (train/select checkpoint).
6. Bounded causal canaries and full training -> T-109 (train/select
   checkpoint).
7. Artifact export and validation -> T-109 (train/select checkpoint).
8. Installation, PTY proof, and rollback -> T-110 (promote and verify runtime).

T-108 (build history-conditioned dataset/evaluator) gains a dependency on T-111
(create ShellCue Training). T-108 and T-109 (train/select checkpoint) execute
in `shellcue-training`; T-110 (promote and verify runtime) executes in ShellCue.

Status: accepted-by-user

Consequence: one canonical task graph owns the product outcome. Smart Bash
T-299 (repair prompt framing and retrain Liquid) becomes
`superseded/reference-only` after the ShellCue plan lands.

## Q8: Delivery sequence

1. Merge the already verified model-only ShellCue cleanup.
2. Land a ShellCue contract/task-authority PR: task graph, versioned contract
   specification, golden vectors, artifact schema support, and tests; no model
   cutover.
3. Create local `shellcue-training`, then migrate the selected core and prove
   independence; create its remote only after license/privacy/history audit.
4. Execute T-108 (build history-conditioned dataset/evaluator) in the new
   repository.
5. Execute T-109 (train/select checkpoint) in the new repository.
6. Hand an immutable promotion packet to T-110 (promote and verify runtime) for
   ShellCue installation and real-terminal verification.

Separate PRs are mandatory for the ShellCue contract slice and the new
repository bootstrap. External compute/upload remains approval-gated.

Status: accepted-by-user

Consequence: repository extraction cannot silently become a model cutover or
private-data publication.

## Q9: Verification and deletion tests

The extraction closes only when:

- `shellcue-training` installs and tests in a fresh environment;
- all selected commands work with Smart Bash absent from `PYTHONPATH`;
- repository scans find no Smart Bash runtime imports or private/generated
  payloads;
- donor and target manifests bind hashes and dispositions;
- cross-repository golden prompt and artifact vectors match;
- the standard-command and prompt-framing gates run from the new repository;
- one exported fixture artifact passes `shellcue model verify`;
- ShellCue still builds unchanged and its public-boundary test rejects training
  ownership/dependency leakage.

Status: source-proven

Consequence: “files copied” cannot be mistaken for “ownership migrated.”

## Q10: Pressure pass

Deleted complexity:

- no third shared package;
- no full-history fork of Smart Bash;
- no second evaluator framework;
- no training API in ShellCue;
- no duplicate canonical eight-stage plan;
- no remote/publication before audit.

Growth triggers requiring replan:

- contract parity cannot be expressed with fixtures and hashes;
- migration needs Smart Bash runtime at execution time;
- selected donor surface expands beyond the reviewed manifest;
- artifact compatibility requires a breaking ShellCue runtime change;
- private data or uncertain licensing enters the proposed repository history;
- a new model family/trainer is introduced during extraction.

Final direction: ready for formal plan review.
