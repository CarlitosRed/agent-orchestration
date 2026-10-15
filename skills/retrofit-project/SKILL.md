---
name: retrofit-project
description: Bring an EXISTING project (one with real code, PRs and history already) onto the framework's adapter spec, consolidating its scattered facts into .orchestration/. Use for a project that predates the framework, or that grew its own ad hoc rules before pinning one. Different from onboard-project, which is for a project that doesn't exist yet.
---

# Retrofit an existing project onto the framework

Run BY that project's own Orchestrator, in that project's own repo - never by the Framework Orchestrator, which only ever edits its own repo (`docs/multi-orchestrator-model.md`). This closes the gap `adapters/README.md` already names: a project's facts spread across its own ad hoc files instead of the adapter shape.

## Ground rules
- **This project's own facts are the source of truth.** This skill consolidates and relocates them; it does not invent new policy or override an existing decision just to fit the spec's shape more neatly.
- **Keep substance, change location.** Where an existing fact conflicts with the adapter spec's shape, preserve the existing fact and change only where it lives; a genuinely undecided point is written `UNKNOWN: <what you found instead>`, not guessed.
- **Don't break what already reads the old location.** Before moving a file (a leak log, a gate config) that something else (CI, a script, a habit) already reads from its old path, check for that dependency; a pointer file at the old location beats a silent move.
- **This is itself a real change**, same tier as any other: goes through this project's own normal PR process, at whatever tier its gate says a rule or protected-path change needs.

## Steps
1. **Inventory.** Find every place this project currently keeps adapter-shaped facts: an existing gate config and the schema it was built against, a desk or environment doc, a roles or ownership doc, a leak or incident log, any verification or demo scripts already in use. List each with a pointer (file, or folder if it's spread across several).
2. **Map to the spec**, one `.orchestration/` file at a time (shape in `adapters/README.md`):
   - `framework.pin`: two lines, `repo:` (the framework's URL) and `tag:` (the version to pin at - normally the latest tag, unless there's a specific reason to pin an older one).
   - `gate.json`: translate the existing gate config to `tools/gate/gate.schema.md`. Where a concept doesn't map cleanly, leave the old config file in place untouched and write the gap down rather than guessing at a schema field.
   - `desk.md`, `commands.md`, `roles.md`: migrated from wherever they currently live, kept in substance, not rewritten from scratch.
   - `leaks.md`: either the existing leak log moved here directly, or a one-line pointer to where it already lives, if moving it would break history or a tool that reads it from the old path.
3. **Resume prompt.** Write or update this project's own `RESUME-<slug>-orchestrator.md` (same shape `skills/onboard-project` generates for a new project): read order, declare the Project Orchestrator role for this project, pinned at the tag from step 2; sweep now checks the handoff inbox first (`skills/handoff` in the framework repo named in `framework.pin`), then the project's own usual sweep.
4. **Report.** What moved, what stayed as a pointer, what's flagged `UNKNOWN`; any existing automation that reads one of the old scattered locations, and whether it was updated to the new path or the old path was kept as a pointer for it. Outcome is `migrated` (every `.orchestration/` file exists, even if some entries are `UNKNOWN`) or `blocked` (named: what's missing and why).
