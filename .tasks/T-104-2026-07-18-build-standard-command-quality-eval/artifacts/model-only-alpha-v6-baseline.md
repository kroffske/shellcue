# T-104 model-only alpha v6 baseline

## Decision

The installed `shellcue-lfm2.5-230m-alpha` checkpoint is `REJECT /
BLOCK_RELEASE` on the frozen standard-command engineering gate. This is an
honest model-quality result, not a failure of the evaluation task.

No candidate was rewritten. The production response and every candidate
required `source=model`; history/catalog fallback was disabled.

## Identity

- Smart Bash branch: `codex/standard-command-adaptation`.
- Evaluator implementation commit: `2a76aa0`.
- Contract metadata commit: `869ab4a`.
- Contract: `shellcue-standard-command-quality-v1`, version `6`, frozen.
- Panel: `standard-command-quality-v1`, 60 cases, 48 positive, 12 negative.
- Set-valued cases: 40; accepted targets: 154.
- Model weights SHA-256:
  `c4f7973c48eb04fa2e8013f0d03171fcfb4ee27c157dea31e96020b12b84fb53`.
- Installed ShellCue: `0.1.0a4`.
- Evaluator SHA-256:
  `d931c37e6adfe0b94b137c48c787a9d8630f50a0c9a33a847aca968c891fdfb0`.
- Result SHA-256:
  `e770d2261defb3a7062522b927a0fa350ffdd15b58080d37bea4d856f3f79f74`.
- Report SHA-256:
  `f77d9cbef24a3e6e942b9f60c1178f9cfab9ba8a211e50c13cd53a24c840dd27`.
- Local evidence:
  `/Users/ravius/projects/_worktrees/smart_bash-t104/runs/evaluation/t104-model-only-alpha-v6-20260719/`.

## Production result

| Metric | Value | Gate |
| --- | ---: | --- |
| Useful acceptance at rank 1 | 0.4167 | FAIL, required >= 0.80 |
| Parse-valid shown | 1.0000 | PASS, required = 1.00 |
| Family-valid shown | 0.5833 | FAIL, required = 1.00 |
| Severe contamination | 0.0833 | FAIL, required = 0.00 |
| False show | 0.0833 | FAIL, required <= 0.05 |
| Correct abstention | 0.9167 | FAIL, required >= 0.95 |
| Wall-clock p95 | 225.2 ms | Report-only in this gate |

Useful acceptance means that the first shown command matches any accepted
set-valued target. Higher is better. Parse-valid and family-valid must be 1.
Severe contamination and false show are lower-is-better. Correct abstention is
higher-is-better.

Observed owner examples:

- `git s` without family context -> `git ssh init`;
- `git s` with family context -> `git sudo apt-get install git`;
- `git st` without family context -> `git stale`;
- `git st` with family context -> `git stash`, accepted.

## Localization

The same-config production/mirror comparison had 0 mismatches. Production used
one beam, so `coverage@3=0`.

The diagnostic `beams=3` lane reached:

- useful at rank 1: `0.5000`;
- useful within ranks 1-3: `0.5208`;
- coverage with three candidates: `0.1250`.

Only one positive case had an accepted answer below rank 1. The main repair
route is therefore data/SFT generation quality. Ranking-only work is not the
first lever.

## Verification

- Focused evaluator/data tests: `22 passed`.
- Ruff: passed.
- Python compile check: passed.
- `locus.ml.eval.v1` contract validation: passed.
- Full repository suite with temporary `jsonschema`: `906 passed`, `2 skipped`,
  `47 failed`; failures require ignored historical datasets, run artifacts, or
  archived task evidence absent from this linked worktree. None touched the
  T-104 focused tests.

## Next training contract

The bounded corrective plan is recorded in:

- `docs/ml-system-design.md`, “Следующий corrective cycle для standard
  commands”;
- `docs/ml-experiment-contract.md`, “Standard-command gate с несколькими
  правильными ответами”.

It requires a shadow holdout before new data, error taxonomy, augmentation v2,
suffix-only causal SFT, a small formatting smoke, then a bounded LoRA/adaptation
canary. History-conditioned SSH remains a separate task after context/privacy
freeze.
