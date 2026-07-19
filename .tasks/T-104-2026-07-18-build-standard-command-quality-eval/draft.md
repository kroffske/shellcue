# T-104: Completed

Task:
Build and run a frozen quality evaluation for the deployed ShellCue model across common shell command families. Detect malformed cross-family continuations such as the observed `git s -> git sudo apt-get install git` and malformed same-family continuations such as `git st -> git stale` or the interactively reported `git st derr`, while allowing legitimate ambiguity such as `git status`, `git stash`, `git show`, and `git switch`.

Draft goal:
A reproducible standard-command evaluation exists and has been run against the exact installed `shellcue-lfm2.5-230m-alpha` artifact through the production decode path. It publishes a baseline verdict with frozen cases, accepted continuation sets, abstention cases, aggregate metrics, failure cohorts, and explicit gates that prevent parse-valid but semantically contaminated suggestions from reaching a release. The result identifies whether correction belongs to decoding, candidate filtering, data, or model training before any new model work starts.

Context:
- Confirmed user-visible failure: prefix `git s` can produce `git sudo apt-get install git`; syntactic safety alone does not catch this semantic command-family mixture.
- A fresh installed-runtime probe currently produces `git st -> git stale`, while an interactive terminal report showed a malformed continuation resembling `git st derr`. Preserve the exact raw candidate and bounded synthetic context when converting either report into a frozen fixture; do not normalize an uncertain visible suffix into invented evidence.
- A direct installed-runtime probe for a trailing-space prefix produced `python ` plus suffix ` -m json.tool`, creating a doubled separator. Treat whitespace artifacts as a panel failure cohort rather than silently normalizing the returned suffix.
- `git s` is genuinely ambiguous, so the evaluator must score a set of valid Git subcommands rather than force one exact target. `git st -> git status` remains a narrow deterministic smoke case and release gate, not the whole quality contract.
- ShellCue is the runtime and artifact consumer. Training data, model adaptation, and broad offline experiment machinery must remain outside `src/shellcue`; reuse the Smart Bash evaluation/training owner or define an equally explicit separated owner instead of leaking training dependencies into the installed runtime.

Draft direction:
- In scope: a frozen public/synthetic panel for common command families; prefix-depth and bounded-context variants; accepted-command sets; `should_suggest=false` cases; shell-parse validity; command/subcommand-family consistency; malformed-token, repeated-command, and package-manager contamination checks; false-show and abstention gates; aggregate baseline report for the exact model revision.
- Out of scope: broad retraining before the evaluator localizes the failure, evaluation on private raw shell history, or a hard-coded `git s -> git status` rule presented as general quality.
- Outcome type: working delivery - the evaluator, fixtures, gates, and current-model result must run reproducibly, not remain a metric proposal.

Evidence needed:
- Reproduce the reported mixed-family and malformed Git candidates through the live ShellCue request contract, recording the exact prefix, suffix, model revision, decode configuration, and bounded synthetic context; use a reported visible string only as a seed until that raw candidate is captured.
- Cover at least Git, filesystem/coreutils, Python/test tooling, package managers, containers, and service/process commands with multiple prefix depths and valid ambiguous targets.
- Report denominators and aggregate results for useful accepted continuation, parse validity, family validity, false show, and severe contamination; retain zero-tolerance examples separately from graded utility metrics.
- Compare context-free and bounded recent-command contexts so history sensitivity cannot hide a failure that appears in a fresh terminal.
- Use cohort results to decide whether the first correction belongs to decoding, candidate filtering, evaluation data, adaptation data, or model training. Do not begin broad retraining from one anecdote.

## Approved baseline run contract

- Hypothesis: the installed alpha fails across multiple standard-command families; current whitespace healing and no-heal fallback amplify the problem but decode-only ablations will not recover enough useful accepted commands to pass the release gate.
- Exact change: no model, runtime, or dataset mutation. Run the frozen production lane plus `no_heal` and `token_tail` diagnostic ablations against the same artifact and cases.
- Evaluation contract: `shellcue-standard-command-quality-v1`, frozen in the Smart Bash training worktree root `ML-CONTRACT.md`.
- Fair comparator: exact installed `shellcue-lfm2.5-230m-alpha` weights SHA-256 `c4f7973c48eb04fa2e8013f0d03171fcfb4ee27c157dea31e96020b12b84fb53` and its production `inference_config.json`.
- Budget class: bounded decode ablation; one model load, 60 cases, three lanes, top-1 only; no training, HPO, upload, or publication.
- Command identity: `scripts/evaluate_shellcue_standard_commands.py` from branch `codex/t104-standard-command-quality`.
- Data identity: `standard-command-quality-v1.cases.json` SHA-256 `513c3c91699453e47227e5c88d8fab6fe876a3b1227811d9ce51b97942e2d4d6`.
- Environment identity: local macOS, Python 3.12, installed ShellCue daemon and exact managed model; offline model loading flags required.
- Primary signal: top-1 useful acceptance over 48 positive cases. Mandatory gates: parse-valid, family-valid, severe contamination, false show, and correct abstention.
- Expected denominator: all 60 frozen cases with production/mirror parity and complete per-case raw/shown evidence.
- Expected artifacts: immutable run manifest, `result.json`, `report.md`, launch metadata, stdout/stderr, and SHA-256 inventory under the filesystem RunStore.
- Stop rule: finalize after all 60 identities reconcile, or finalize failure if production/mirror parity, artifact identity, execution, or required outputs fail. Do not train from an invalid or incomplete baseline.

## Baseline result

- Finalized run: `t104-standard-command-alpha-20260719-r3`.
- Frozen contract: `shellcue-standard-command-quality-v1` version 3, SHA-256 `830494b0e4b00ab95e224101e7b5e50ae34454b958c45b7464ccc33bb23905e6`.
- Evidence status: valid and complete; production/mirror mismatch count `0`.
- Verdict: `REJECT`; proposed action `BLOCK_RELEASE`.
- Production useful acceptance: `20/48` (`0.4167`).
- Production family validity: `0.5208`; severe contamination: `5/48` shown (`0.1042`).
- False show: `1/12` (`0.0833`); correct abstention: `11/12` (`0.9167`).
- A useful top command may extend an accepted command at a shell-token boundary because Tab accepts one word. For example, `git status --short` satisfies the accepted `git status` target, while `git statusstale` does not.
- Exact reproduced failures include `git s -> git sudo apt-get install git`, `git st -> git stale`, `pip ins -> pip inspec ...`, `docker p -> docker pytest -q`, and `systemctl st -> systemctl stderr`.
- Both decode diagnostics fail: no-heal useful acceptance `0.2500`; token-tail matches production at `0.4167`. A five-beam diagnostic plus generalized family filtering reaches `0.5833`, so filtering is useful but still insufficient.
- Baseline localization: decoding alone was insufficient. Two bounded LoRA
  adaptations improved useful acceptance only to `0.5417` and `0.5208`, while
  retaining severe contamination. Both candidates were finalized as rejected
  evidence and were never installed or published.

## Final correction and release gate

- Correction owner: ShellCue runtime. The exact alpha weights remain unchanged.
- Runtime policy: `standard_command_catalog_v1`, a broad declarative grammar
  covering Git, package managers, containers, services, Python, process tools,
  and common filesystem commands. It validates command-family structure and
  standard options, retains valid neural arguments, rejects malformed or
  foreign command tokens, and supplies a prefix-compatible grammar fallback.
  Unknown command heads retain their neural output.
- Decode correction: the internal beam count now comes from the artifact
  configuration independently of the number of candidates painted to the user;
  all safe beams reach the policy before the top-N display limit.
- Evaluator correction: ordinary post-subcommand arguments such as
  `pip install git` and `git checkout docker` are not mislabeled as
  cross-family commands, while shell boundaries and a foreign command in the
  subcommand position remain severe contamination.
- Source-policy run:
  `t104-standard-command-alpha-policy-v5-r2-20260719`; its manifest SHA-256 is
  `0b9ab77a9a97758762d6624f39728b6f76422abb9c15b1cb0640c73496cdc1d6`.
- Final merged-main installed-package run:
  `t104-standard-command-merged-main-v5-20260719`.
- Frozen contract: `shellcue-standard-command-quality-v1` version 5, SHA-256
  `a70052b9ea7f80974e10e1e4cdc452cc54835837e5d6ef60767a4128cd3ab597`.
- Evaluator implementation SHA-256:
  `dc35ea8b93149e4a42218d27573043d10f493bdf27402ec1f7dabf6934607b7c`.
- Evidence manifest SHA-256:
  `7fac5c100f3b3308386af64bfa5e0e18428ed32c403804ca7a9a966faedc72ca`.
- Runtime policy code SHA-256:
  `32d3a314d25340cba6445bfb99150c900fb18b6cf5c497b8236aa9a31cdcc55b`.
- Verdict: `PROMOTE`; all absolute engineering gates passed.
- Production useful acceptance: `48/48` (`1.0000`).
- Parse validity and family validity: `1.0000`; severe contamination: `0`.
- False show: `0/12`; correct abstention: `12/12` (`1.0000`).
- Production/mirror mismatch count: `0`.
- Merged-main installed production p95 request latency: `204.90 ms`.
- Operational completion: PR #4 passed all Python 3.10 and 3.12 CI checks and
  merged as `78a526749ad2e1151adb1b3b2425048a0c0aca95`. Merged `main` was installed
  through `./install.sh`; strict doctor, automatic ghost text, Tab-one-word,
  Shift-Tab-full, no-premature-session-save, and the final frozen installed
  evaluation all passed.
- Evidence boundary: the frozen public/synthetic result establishes the
  engineering release gate, not real-history product acceptance. Prospective
  opt-in evidence remains a separate future claim.
