# Orchestrator portability: Codex failover and a local-model Operations Clerk (2026-10-16)
Not an external source this time - two ideas the Program Owner raised directly in chat. Checked against this session's own evidence rather than a primary document to verify, so marked accordingly.

## I-017: Codex failover for the Framework Orchestrator role
What: if Claude credits run dry, start the next Framework Orchestrator chat on Codex instead, using the same `RESUME-framework-orchestrator.md` prompt.

What we can take: `RESUME-framework-orchestrator.md` is already vendor-neutral prose (file reads, `gh`, `git` - nothing Claude-Code-specific). The Orchestrator role has already been proven live on Codex today, just not on this repo: SmarterForge's own session (Codex, single-vendor) is running the Project Orchestrator role for `charlieredondo/SmarterCommerce` right now, signing comments `**Project Orchestrator · Codex:**` (`agent-orchestration#52`, the handoff issue, 2026-10-16).

What we leave: nothing decided - no test has been run on this repo's own resume file specifically.

What was NOT verified: whether Codex, given this exact resume prompt, actually reads the handoff file and sweeps correctly the same way this session does. That is the open question a real test answers, not something to assume from the SmarterForge evidence alone (different project, different adapter, different task shape).

## I-018: a local model for the Operations Clerk role
What: explore whether a local model (no per-call API cost, runs on the Program Owner's own machine) can fill the Operations Clerk role.

What we can take: `rules/README.md`'s R20 already names this exact fit - "chores without judgement (status table, closing listed PRs) go to an Operations Clerk on a cheap model or to a script." A local model is a cheap-model option R20 already anticipated, just never tried.

What we leave: don't start with the Orchestrator role for a local model - that needs the most judgment of any role (plans, verifies reports, proposes changes), the furthest fit from what local models are reliably good at today.

What was NOT verified: no local model has been tried on any role in this framework yet. Unproven in both directions - whether a given local model is capable enough for even Operations Clerk's mechanical work, and the mechanics of wiring one in as a vendor profile (`vendors/`) at all.
