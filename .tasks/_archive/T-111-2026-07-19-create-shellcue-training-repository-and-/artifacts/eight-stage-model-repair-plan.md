# Eight-stage ShellCue model-repair plan

## Accepted outcome

Repair model quality at the prompt, label, context-budget, dataset, evaluation,
training, artifact, and installed-runtime layers. Runtime code may reject unsafe
or contract-invalid model output, but it may not generate, retrieve, rewrite,
or substitute a better semantic answer.

Repository ownership:

- ShellCue owns the live runtime, prompt/artifact contract, model loading,
  decode, safety rejection, daemon, installer, and terminal acceptance.
- `shellcue-training` owns dataset construction, offline evaluation, training,
  selection, artifact export, and aggregate promotion evidence.
- Smart Bash is migration input and historical evidence only.

## Repair matrix

| Broken layer | Failure | Repair | Owner | Rejecting proof |
| --- | --- | --- | --- | --- |
| Typed prefix | Healing can make `git s`, `git sh`, and `git st` look identical to the model | Include complete canonical `typed_prefix` in the model prompt | ShellCue contract plus training parity | Prompt bytes and token ids differ before generation |
| Label boundary | Joint prefix/target tokenization can hide cursor-straddling suffixes | Mask labels through an explicit suffix sentinel; train only visible suffix | `shellcue-training` | Golden label span equals expected suffix, such as `atus` |
| Context serialization | Bare lines can collide with quotes, colons, newlines, and field-like text | Canonical JSON strings, stable field order, UTF-8, versioned contract | Both, via vectors | Round-trip and byte parity tests |
| Token budget | Character slicing or token tail truncation can cut fields, prefix, or labels | Reserve structural fields and full prefix; add whole recent fields; drop oldest; explicit overflow abstention | Both, via vectors | Boundary-fit and overflow vectors |
| Production context | Historical rows may not match live source/cwd/history shapes | Rebuild rows using the exact runtime contract and bounded history depths | `shellcue-training` | Coverage manifest and contract hashes |
| Dataset structure | Weak coverage and invalid adjacent command families teach nonsense | Controlled valid Git/SSH/history/operator synthetics; invalid transitions remain negatives only | `shellcue-training` | Zero known invalid positive transitions |
| Split and evaluation | Cursor expansion, duplicate events, or answer repair can create false quality | Split before expansion; frozen set-valued raw-model evaluation | `shellcue-training` | Leakage audit and immutable panel hashes |
| Training | Alpha learned the wrong product surface | Causal canary ladder, then at most one bounded full Liquid fine-tune | `shellcue-training` | Frozen multi-gate selection or no-promotion |
| Artifact | Runtime can silently select old prompt/decode behavior | Bind prompt/target/tokenizer/data/eval identities in the artifact | Both repositories | Unknown/drifted contract rejected |
| Installed path | Offline success can hide daemon, latency, stale, or keybinding failure | Install exact artifact; run PTY, rollback, and source-trace acceptance | ShellCue | Exact loaded hash and real-terminal evidence |

## Stage 1: freeze ShellCue prompt and artifact contract

### Actions

- Define a versioned autocomplete contract such as
  `shellcue.autocomplete.v2`.
- Serialize dynamic values as canonical JSON strings in deterministic field
  order and UTF-8.
- Include source kind, captured cwd when present, bounded recent commands,
  complete `typed_prefix`, and explicit `completion_suffix:` sentinel.
- Define suffix-only targets. For visible `git st` followed by `git status`, the
  training target is `atus`.
- Define artifact metadata for prompt contract, target contract, tokenizer
  revision, token/context budgets, vector-ledger hash, and minimum runtime.
- Keep current artifact compatibility until an accepted successor exists.

### Token-budget algorithm

1. Serialize and tokenize contract/version, source, complete typed prefix,
   suffix sentinel, and captured cwd.
2. If mandatory fields exceed the artifact budget, return
   `prefix_over_budget`; never truncate the prefix or invoke another predictor.
3. Consider bounded recent commands newest-first after runtime masking.
4. Include only whole serialized fields. Omit oldest non-fitting history first.
5. Preserve repetitions. Never slice escaped fields, labels, or sentinel.

### Exit gate

- `git s`, `git sh`, and `git st` have different prompt bytes/token ids.
- Golden vectors cover empty, Unicode, quotes, colons, newlines, field-like
  text, history depths, repeats, exact fit, and overflow.
- ShellCue accepts v1/v2 contracts additively without changing the installed
  model.

Canonical tasks: T-107 (freeze history context/privacy) and T-111 (create
ShellCue Training).

## Stage 2: bootstrap `shellcue-training` and prove contract parity

### Actions

- Create the new package and locked environment without Smart Bash imports.
- Vendor the exact ShellCue fixture ledger and verify its SHA-256.
- Implement one pure training-side renderer/budgeter against structured masked
  fields.
- Materialize full typed prefix, visible suffix, structured context,
  provenance, contract ids, tokenizer identity, and vector hash.
- Encode labels only after the suffix sentinel.
- Remove dependence on healed committed prefixes, hidden pending fragments,
  whitespace repair, or semantic no-heal fallback.

### Exit gate

For every golden fixture, ShellCue and `shellcue-training` agree on UTF-8 prompt
bytes, tokenizer ids, retained fields, overflow outcome, and suffix-label span.
Deleting Smart Bash from `PYTHONPATH` does not change the result.

Canonical task: T-111 (create ShellCue Training).

## Stage 3: rebuild the production-shaped dataset

### Base-data rules

- Ingest event-level permitted sources through the accepted privacy policy.
- Preserve source provenance in metadata; render the exact live product
  conditioning contract.
- Split by source sequence/session before cursor expansion.
- Create a new immutable dataset identity; never mutate alpha rows.
- Record input snapshots, recipe/config/code hash, tokenizer/vector hash, row
  identity hash, and output hashes.

### Required coverage

- cwd absent and `repo:<basename>` present;
- history depths from empty through the accepted bound;
- repeated, rare, irrelevant, conflicting, and frequency-modified history;
- two to four near-identical SSH targets whose final identity tokens differ;
- typed prefixes for verbs, subcommands, options, arguments, paths, operators,
  quoting, multiline text, and long input;
- command families including Git, SSH, filesystem, search, Python, packages,
  containers, and explicit shell continuations.

### Synthetic policy

- Generate valid event-level commands and pass them through the same masking,
  splitting, rendering, and expansion pipeline.
- Include controlled Git standard commands; `ssh`, `ssh-add`, `ssh-keygen`,
  identity/port options, multiple hosts; history choices; explicit `&&`, `||`,
  `;`, pipes, and redirects; paths, variables, and quoting.
- Cap synthetic share/weight and mark it `augmentation_only=true`.
- Exclude synthetic identities from chronological product acceptance.
- Keep `git sudo`, `git ssh`, `git stale`, and similar impossible transitions
  as negative evaluation cases only.

### Exit gate

The deterministic audit passes split/leakage, duplicates/conflicts, positive
shell structure, unsafe exclusions, privacy/redaction, coverage, overflow, and
hash checks.

Canonical task: T-108 (build history-conditioned dataset/evaluator).

## Stage 4: freeze validation and prove learnability

### Evaluation surfaces

1. Current standard-command panel with set-valued valid answers and raw-model
   source checks.
2. Structural collision panel for Git/SSH family contamination, malformed
   subcommands, explicit versus missing operators, history depth/repetition,
   rare commands, and competing similar hostnames.
3. Chronological natural holdout frozen before the final run.

### Metrics and policy

- Top-1 useful acceptance is the release metric; top-k coverage/ranking is
  diagnostic.
- Severe family contamination has zero tolerance on the release panel.
- Parse-valid nonsense does not satisfy family consistency.
- No suggestion remains a miss on positive cases, but is distinct from unsafe
  contamination.
- Natural, curated, and synthetic slices remain separate.
- Panel hashes, metrics, denominators, thresholds, comparator eligibility, and
  environment identity freeze before candidate results.

### Micro-overfit

Train a tiny deterministic fixture containing colliding prefixes and context
choices. It must learn distinct suffixes for `git s`, `git sh`, and `git st`.
Failure blocks canaries because it proves prompt/label/trainer wiring is still
wrong.

### Exit gate

Frozen evaluator rejects non-model sources, contract drift, changed panels,
changed thresholds, leakage, and incomparable environments. Micro-overfit
passes without answer repair.

Canonical tasks: T-104 (standard-command quality eval), T-108 (build
history-conditioned dataset/evaluator), and T-109 (train/select checkpoint).

## Stage 5: run a causal canary ladder

### Canary A: framing only

- same permitted source events;
- prompt/target contract v2;
- no new command synthetics;
- only serialization and necessary context normalization changes.

### Canary B: production context

- same v2 code;
- corrected live source, cwd, and history coverage;
- no new command synthetics.

### Canary C: controlled augmentation

- same v2 code and production context;
- controlled valid Git/SSH/history/operator synthetic packs.

### Controlled variables

Use the same Liquid base checkpoint/tokenizer, training method, optimizer,
schedule, max steps/tokens, selector, early stopping, seed policy, decode
config, and frozen evaluator. Each adjacent canary changes one declared data
lever.

### Exit gate

One arm passes the precommitted structural, quality, safety, privacy, collapse,
latency, and resource gates, or the task records an evidence-backed causal stop.
More data cannot substitute for a failed framing canary.

Canonical task: T-109 (train/select checkpoint).

## Stage 6: authorize and run one bounded full Liquid fine-tune

### Approval packet

Before upload or external compute, bind:

- clean code commit and diff scope;
- dataset, recipe, source, redaction, contract, and evaluation hashes;
- Liquid base checkpoint and tokenizer revision;
- hyperparameters, selector, early stopping, seeds, time/memory/disk/cost caps;
- upload destination and private-data boundary;
- aggregate-only output boundary;
- explicit owner approval.

### Training

- run at most one full fine-tune from the passing canary arm;
- select on validation only and restore the best validation checkpoint;
- never use final holdout during selection;
- save logs, checkpoints, manifests, and hashes atomically;
- reproduce or verify outputs locally.

### Exit gate

Training completion or lower loss is not acceptance. The restored candidate
must pass every frozen engineering gate. Failure yields no promotion and one
next causal experiment.

Canonical task: T-109 (train/select checkpoint).

## Stage 7: export and select the runtime artifact

### Actions

- Export weights, tokenizer, inference config, prompt/target contracts, budgets,
  base/data/eval/config/code identities, licensing, and provenance.
- Verify save/reload in a fresh process.
- Run frozen standard-command, history-conditioned, severe-contamination,
  malformed-family, parse, unsafe, memorization, target-collapse, latency, and
  privacy gates.
- Produce one immutable aggregate promotion packet or explicit no-promotion
  verdict.
- Validate the package through the external `shellcue model verify` command.

### Exit gate

The artifact hash in the promotion packet equals the file that ShellCue
verifies. No evaluator, threshold, prompt, decode, or data identity changed
after results.

Canonical task: T-109 (train/select checkpoint).

## Stage 8: install, verify terminal behavior, and prove rollback

### Actions

- Install/register the exact promoted artifact.
- Restart the managed daemon and verify the fresh-process package, model,
  tokenizer, contract, and config identities.
- Run unchanged frozen gates against the installed runtime.
- Trace every displayed candidate to a model invocation and `source=model`.
- Exercise automatic asynchronous ghost text, continued/divergent typing,
  stale cancellation, Tab one-word acceptance, and Shift-Tab full acceptance.
- Verify no Apple Terminal session-save noise and no runtime network access.
- Roll back to the previous artifact, verify it, then reactivate the candidate.

### Exit gate

Automated PTY and independent QA accept the exact installed hash. Remaining
subjective usefulness is stated separately. Failed installation, stale
behavior, latency, privacy, or rollback returns to the previous artifact.

Canonical task: T-110 (promote checkpoint and verify terminal runtime).

## Stop and replan triggers

Stop before further work if:

- ShellCue and `shellcue-training` golden vectors diverge;
- Smart Bash remains an import or execution dependency;
- the donor manifest expands without review;
- private or uncertain-license data/code is proposed for Git history or upload;
- a deterministic history/catalog/rewrite path is proposed as quality repair;
- the prompt/label micro-overfit fails;
- frozen evaluation or thresholds change after candidate results;
- a new model family or trainer is introduced as an unplanned confound;
- the exported artifact differs from the installed artifact.

## Delivery order

1. Merge ShellCue PR #5, the verified model-only runtime cleanup.
2. Land the ShellCue contract/task-authority slice without model cutover.
3. Create and independently verify local `shellcue-training`.
4. Freeze data/evaluation.
5. Run canaries and, if authorized, one full training.
6. Export/select an artifact or stop.
7. Promote through ShellCue installation, PTY, rollback, review, and QA.

Public repository creation, private-data upload, external compute, model
cutover, and release are separate explicit ship decisions.
