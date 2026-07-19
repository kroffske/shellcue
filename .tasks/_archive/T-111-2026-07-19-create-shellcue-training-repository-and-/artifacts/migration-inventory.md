# ShellCue Training migration inventory

## Decision

Build a fresh sibling repository at
`/Users/ravius/projects/shellcue-training`. Do not fork or copy the complete
Smart Bash repository. Smart Bash is a donor whose selected algorithms are
ported under new ownership; it is not a package or execution dependency.

## Target ownership

| Surface | Owner after migration | Boundary |
| --- | --- | --- |
| Live context capture and masking | ShellCue | Request-scoped runtime only |
| Prompt and artifact contract | ShellCue | Versioned spec plus golden vectors |
| Dataset build and audit | `shellcue-training` | No raw private data in Git |
| Offline evaluation and freeze | `shellcue-training` | Raw model candidates only |
| Training and checkpoint selection | `shellcue-training` | Bounded, reproducible runs |
| Artifact export and promotion packet | `shellcue-training` | Aggregate evidence plus hashes |
| Artifact verify/install/daemon/PTY | ShellCue | Exact promoted artifact only |
| Historical experiments | Smart Bash | Read-only reference |

## Target repository

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

Required commands:

```text
shellcue-training dataset build|audit
shellcue-training eval run|freeze
shellcue-training train canary|run
shellcue-training artifact export|verify
```

## Donor classification

### Migrate or rewrite: core data/evaluation

| Smart Bash source | Target owner | Disposition |
| --- | --- | --- |
| `src/smart_bash/data/token_suffix_export.py` | `data/` | Rewrite imports, schema, and contract adapter |
| `src/smart_bash/eval/autocomplete.py` | `eval/` | Rewrite around explicit model-result envelope |
| `src/smart_bash/eval/benchmark_v2.py` | `eval/` | Migrate reusable benchmark types |
| `src/smart_bash/eval/context_pack.py` | `contracts/` or `eval/` | Replace duplicate contract logic with ShellCue vectors |
| `src/smart_bash/eval/standard_commands.py` | `eval/` | Migrate frozen set-valued quality contract |
| Current latency/path/quality helpers | `eval/` | Migrate only if named by a frozen gate |

### Migrate or rewrite: dataset/training

| Smart Bash source | Target owner | Disposition |
| --- | --- | --- |
| `training/kaggle/runners/train_causal_command_lm.py` | `training/` | Split reusable trainer from Kaggle adapter |
| `training/kaggle/runners/preflight_freeze.py` | `training/` | Migrate hash/freeze checks |
| `training/kaggle/utils/training_history.py` | `training/` | Migrate atomic aggregate history |
| `training/kaggle/datasets/build_token_suffix_dataset.py` | `data/` | Rewrite for new contract |
| `build_shell_family_coverage_dataset.py` | `data/` | Migrate controlled family coverage |
| `build_synthetic_filesystem_transcripts.py` | `data/` | Migrate safe synthetic generator |
| `build_standard_command_curriculum.py` | `data/` | Migrate as augmentation-only curriculum |
| Active generic Liquid recipes | `configs/` | Rename and remove task-number coupling |

### Migrate as package commands

- autocomplete benchmark construction and top-k evaluation;
- chronological evaluation identity export;
- dataset mixture materialization and freeze;
- training-only/evaluation upload preparation;
- preflight and existing-artifact matrix;
- candidate scoring;
- standard-command evaluation/finalization;
- ShellCue artifact export after privacy/license gate.

Standalone scripts remain only for external platforms that require file entry
points. New internal behavior belongs in importable package modules.

### Migrate: current contracts and documentation

- `ML-CONTRACT.md`;
- `docs/ml-experiment-contract.md`;
- `docs/models/alpha-prompt-framing-diagnosis.md`;
- `docs/models/token-suffix-artifact.md`;
- `docs/datasets/token-suffix-dataset.md`;
- `docs/experiments/next-autocomplete-quality-cycle.md`;
- tests that prove the selected modules and frozen gates.

### Reference only

- old experiment results required to explain the alpha diagnosis;
- historical task-specific recipes needed to reproduce a cited baseline;
- prior aggregate reports whose hashes are referenced by the active contract.

Reference content stays in Smart Bash unless licensing/privacy review approves a
small aggregate-only copy.

### Reject

- Smart Bash CLI, daemon, runtime models/decode, shell integration, retrieval,
  history database, collector, or deterministic candidate generation;
- `runs/**`, datasets, checkpoints, private histories, raw traces, `.local/**`,
  `.tasks/**`, `.reports/**`, caches, virtual environments, and generated files;
- broad task-numbered analysis scripts, configs, and notebooks not named by the
  active contract;
- legacy publication shims and historical Smart Bash product documentation;
- semantic fallback, history replay as prediction, command catalogs, answer
  repair, and whitelists.

## Per-file migration record

Before copying code, generate a machine-readable manifest with:

```json
{
  "source_repo": "smart_bash",
  "source_commit": "<sha>",
  "source_path": "<path>",
  "source_sha256": "<sha256>",
  "disposition": "migrate|rewrite|reference|reject",
  "target_path": "<path-or-null>",
  "target_sha256": "<sha256-or-null>",
  "license": "<decision>",
  "private_data_risk": "<decision>",
  "notes": "<rewrite and dependency rationale>"
}
```

The manifest is sorted deterministically and fails validation if a migrated
target has an unrecorded Smart Bash import.

## Eight-stage mapping

| Repair stage | Canonical ShellCue task | Execution repository |
| --- | --- | --- |
| 1. Context/privacy/prompt contract | T-107 (freeze context/privacy) plus T-111 (create training repo) | ShellCue |
| 2. Runtime contract support, no cutover | T-111 (create training repo) | ShellCue |
| 3. Training renderer/materializer parity | T-111 (create training repo) plus T-108 (build dataset/eval) | `shellcue-training` |
| 4. Dataset and synthetics | T-108 (build dataset/eval) | `shellcue-training` |
| 5. Eval freeze and micro-overfit | T-108 (build dataset/eval) plus T-109 (train/select) | `shellcue-training` |
| 6. Causal canaries and full training | T-109 (train/select) | `shellcue-training` |
| 7. Artifact export/selection | T-109 (train/select) | `shellcue-training` |
| 8. Install, PTY, rollback | T-110 (promote/verify runtime) | ShellCue |

T-299 (repair prompt framing and retrain Liquid) in Smart Bash is superseded as
a task authority after this plan lands. Its analysis remains donor evidence.

## Migration gates

1. ShellCue contract and golden-vector PR is accepted without model cutover.
2. New repository installs from a clean checkout and locked environment.
3. Smart Bash is absent from `PYTHONPATH`; all new commands/tests still pass.
4. Contract vectors match prompt bytes, token ids, retained fields, overflow,
   label spans, and hashes.
5. A fixture artifact passes the external `shellcue model verify` command.
6. Package/history scans find no raw data, checkpoints, runs, private histories,
   fallback code, or unapproved license.
7. ShellCue build/tests/public-boundary proof remains green.

## Publication boundary

Initialize local Git first. Before creating a GitHub remote or making it public:

- audit the complete staged history and large-file list;
- verify source and model/data licenses;
- verify no private command, hostname, username, path, token, checkpoint, or
  dataset payload is present;
- decide repository visibility and ownership explicitly;
- publish only from a clean, reviewed commit.
