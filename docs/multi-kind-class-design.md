# Multi-kind class probes (designed 2026-10-15, not built)
The historical leak (C1, part of L1/L13/L24/L25/L30) was specific: a class generalized as "any alias" (symlink, junction, short name, stream) was closed after a sweep that only checked ONE kind, so later rounds kept finding "new" instances that were really just unchecked kinds of the same class. The original fix idea named those exact kinds - but `symlink`/`junction`/`short name`/`stream` are one project's filesystem concepts, not a framework one. This generalizes the mechanism instead of hardcoding that project's vocabulary into the framework (`AGENTS.md`: write roles and mechanisms, not project specifics).

## The generic version
Some classes are really a family: the generator's own wording implies more than one distinct kind (not just more instances of the same kind), and a sweep that only checks one kind is not a real sweep of the class. The ledger already refuses a close without `--sweep-cmd`; it does not yet know whether that one sweep actually covered every kind the class's own generator implies.

## Proposed mechanism
1. **Declaring kinds is the reviewer's or builder's job, not the ledger's.** Nothing in `tools/class-ledger` should contain a hardcoded list of "kinds" for any domain. Instead, `add-finding` gains an optional `--kinds k1,k2,...` (comma-separated, free text, project-defined) on the finding that first raises a class as multi-kind. Most findings never set this; it only applies when a reviewer explicitly recognizes "this generator covers more than one kind."
2. **Closing a multi-kind class needs one probe per declared kind.** `close-class` already takes one `--sweep-cmd`; for a class with declared kinds, it should instead take `--sweep-cmd` once per kind (repeatable, e.g. `--kind-sweep symlink:"python sweep.py --symlink" --kind-sweep junction:"python sweep.py --junction"`), and refuse if any declared kind has no matching sweep.
3. **A later finding naming a kind not yet swept is a real gap, not a false new class**, even if the generator text looks similar to an already-closed class - this is exactly the leak class being fixed, so it needs to stay easy to report, not get refused as a lookalike.
4. **Reporting:** `status`/`report` should list, per multi-kind class, which kinds have a recorded sweep and which don't; `exit_ready` (already used by `check`, PR #19/#21's work) should treat an unswept declared kind the same as an unswept class.

## What's unresolved
1. Whether kinds should be free text (simple, but a reviewer could typo a kind name and silently open a new one instead of matching the existing one) or a closed, per-class enum set at the moment the class is first declared multi-kind (safer, more ceremony). Leaning free text with a `status` warning for a kind name that's a near-miss of an existing one (same fuzzy-match idea `SIMILARITY_THRESHOLD` already uses for class generators).
2. Whether this needs a new finding/class field in the stored JSON schema (`schema_version` bump) or can reuse the existing `distinct-from`-style mechanism some other way.
3. Whether a non-multi-kind class should ever be upgraded to multi-kind mid-review (a reviewer realizes only in round 2 that "oh, this is actually a family") without losing the round-1 history.

## Status
Designed, not built. A real implementation should start with (1) above as a pure, offline-testable function (`kinds_for(class) -> set`, `missing_kinds(class, swept) -> set`) before touching the CLI, same approach `passed_ignoring` took for R16.
