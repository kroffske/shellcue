# ShellCue autocomplete prompt contract v2

ShellCue owns the runtime prompt contract. Training repositories may implement
the same pure renderer, but must verify the committed vector ledger before
building data, training, evaluating, or exporting an artifact.

## Input

- `source_kind`: required request surface, currently `live_shell`.
- `cwd_hint`: optional masked repository hint.
- `recent_commands`: bounded, already-masked commands ordered newest first.
- `typed_prefix`: complete text visible at the shell prompt.

## Serialization

Dynamic values are canonical JSON strings encoded as UTF-8. Field order is
contract id, source, optional cwd, retained recent commands from oldest to
newest, complete typed prefix, then `completion_suffix:`.

`recent_1` is the newest command and therefore appears nearest to
`typed_prefix`. Repetitions remain visible.

## Token budget

Contract id, source, cwd when captured, complete typed prefix, and suffix
sentinel are mandatory. The renderer adds whole recent-command fields
newest-first. It omits older fields when the next whole field does not fit. It
never slices an escaped value or truncates the typed prefix.

If mandatory fields exceed the artifact budget, the renderer returns
`prefix_over_budget`; no alternative semantic predictor is invoked.

## Target

The target is only the remaining visible suffix. For `git st -> git status`,
the target is `atus`. A command that does not start with the exact typed prefix
is invalid training data.

Offline causal training tokenizes the complete prompt and generated suffix as
separate segments, concatenates their token ids, and masks every prompt label.
Retokenizing prompt text plus suffix as one string is invalid because a BPE
token can cross the already-committed inference boundary.

## Evidence

`contracts/autocomplete-v2-vectors.json` binds canonical prompt bytes, retained
fields, suffix targets, the alpha tokenizer SHA-256, and tokenizer ids. The
vector ledger is copied unchanged into `shellcue-training` and hash-checked
there; the runtime package does not import the training package.
