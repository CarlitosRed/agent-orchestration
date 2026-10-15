# Claims ledger: scope (2026-10-15, updated same day with --since)
C2's own definition (`rules/leak-classes.md`) is more concrete than the one-line Promote-next row suggested. Scoping it split the ask into one genuinely tractable half and one that is not a framework-level problem at all.

## The original ask, split in two
1. **Detection**: flag every behavioural sentence in a doc (a condition, a quantifier - "always, never, only, same, new" - or a qualifier) that has no matching ledger row. Mechanical: a fixed word list and a line scan. **Tractable, built below** (`tools/claims-ledger`).
2. **Generation**: "text that restates code facts is generated from parsed triples, not hand written" - docs prose for a claim should be mechanically generated from a project's own source, not typed. **Not a framework-level problem.** Parsing arbitrary source into semantic triples is project- and language-specific; the framework cannot own a universal code-fact extractor. What the framework CAN own is the ledger's shape (condition / exception / pinned line / states) so that IF a project builds its own generator later, it has a stable schema to target. Scoped out of this build; `condition_pointer` (a file:line, not generated prose) is the compromise that gets most of the safety (a reviewer can always check the real line) without the generator.

## What was built
`tools/claims-ledger/claims.py`, mirroring `tools/class-ledger`'s conventions (stdlib only, one JSON file, offline-testable):
- `init FILE` - empty ledger.
- `add FILE --slug --doc --line --claim --condition --condition-pointer --exception [--states a,b] --by` - one claim row. Refuses an empty condition or exception (a claim ledger row restating "it does X" with no condition is the exact bug this exists to catch) and a duplicate slug.
- `scan FILE --doc PATH` - lists every quantifier sentence in PATH with no matching row (human-readable, exit 0 regardless, for looking before committing to `add`).
- `check FILE --doc PATH` - exit 0 if every quantifier sentence in PATH has a row, else refuses (exit 1) naming each one. Slots into `templates/ready-for-review.md` item 4 the same way `tools/class-ledger`'s `check` slotted into item 5.

A claim is matched to its doc by **sentence text** (whitespace-normalized), not line number - line numbers drift every time something is edited above a claim; text is what the claim is actually about. `line` is stored as a pointer for a human to find it, never used for matching.

## What's deliberately out of scope, and why
1. ~~Whole file, not a diff~~ - built 2026-10-15: `--since REF` scopes `scan`/`check` to lines changed since a git ref (`changed_lines()`, parsed from `git diff --unified=0`'s hunk headers), so a pre-existing unclaimed sentence elsewhere in the file is left alone and only what the PR actually touches is checked. 6 new tests, real git repos, no mocking. No non-git fallback - `--since` fails outright if `doc` isn't in a git working tree with `REF` reachable. Adopting this on an existing doc still means a one-time choice the first time: run without `--since` once to see the real backlog, or start clean with `--since` from day one and accept pre-existing unclaimed prose as untouched debt.
2. **The quantifier word list (`always, never, only, same, new, every, any, guaranteed, must, cannot`) is a first cut from C2's own text plus close synonyms**, not a closed, tested-correct set - same status as class-ledger's `SIMILARITY_THRESHOLD`: PROPOSED, tune after it runs on a real doc change and either over- or under-flags.
3. **Whether a claim should ever expire or get re-verified automatically** (the code at `condition_pointer` changed since the claim was added) - not tracked; a stale pointer is currently a silent risk, same as a stale comment would be.

## Status
Built and tested (see PR). Scan/check are real and usable today on a whole file; the changed-lines-only CI integration and the pointer-staleness check are the next two increments if this proves useful on a real doc PR.
