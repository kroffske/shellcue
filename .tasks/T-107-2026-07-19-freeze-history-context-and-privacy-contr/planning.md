## Q0: Goal alignment
Question: What contract must exist before ShellCue can train on and infer from
history without becoming history search or silent personal-data collection?
Source check: `.locus/soul.md`, accepted spec REQ-002/REQ-004, current
`RuntimeContext.capture` limit of eight masked commands, and the user's examples
of rare depth-60 commands, repeated commands, and near-identical SSH hosts.
Answer: Freeze one shared context grammar and privacy lifecycle used by row
generation, model prompts, evaluation, and runtime. The model receives context;
no context owner may generate a candidate.
Status: accepted-by-user
Direction: on-track
Consequence: The task closes on an accepted design contract, not code or a
training demo.

## Q1: Identity-bearing values
Question: How can a local model reproduce a real hostname or username when the
current masker replaces it?
Source check: `src/shellcue/core/redaction.py` masks email, URLs, paths, quoted
strings, and long tokens before inference; exact-history reuse bypassed that
loss but violated the model-only rule.
Options:
- A: pass every raw history line to the model;
- B: mask all identity values and accept generic output;
- C: define a local transient copy vocabulary/entity table that preserves safe
  identity-bearing values while excluding secret classes.
Recommended: C.
Rationale: `local-private-context` requires real local utility without turning
raw history into persistent training data.
Status: assumption
Consequence: The design must prove copy fidelity, secret exclusion, tokenizer
behavior, and no persistence before implementation.

## Q2: History depth and frequency
Question: Should runtime always send the last N commands?
Source check: The user requires a rare command around depth 60, repetitions,
irrelevant context, and several similar targets; a fixed last-eight window
cannot represent all cases.
Answer: The contract must define a bounded selector whose output records
recency, frequency, and source position without letting the selector choose the
answer. Exact bounds are decided against token budget and latency evidence.
Status: accepted-by-user
Consequence: Data and runtime use the same versioned selector and serialization.

## Q3: Enrollment boundaries
Question: Does local shell history automatically become training data?
Source check: ShellCue currently promises no history import, recording,
collection, training, or upload command; `.locus/soul.md` forbids silent
private-history training.
Answer: No. Request-time inference, optional persistence, evaluation capture,
and training enrollment are separate consent and deletion surfaces.
Status: accepted-by-user
Consequence: The SDD must specify local-only defaults, inspection, retention,
export, revocation, and derived-artifact deletion before any personal data path.
