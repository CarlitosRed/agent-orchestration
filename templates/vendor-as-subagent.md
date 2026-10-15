# Another vendor's agent as a build or review subagent
Spreads work across vendors so one session's allowance never blocks everything, and keeps review independent (R21: the author's vendor never reviews its own work).

## Automated path (use when the vendor has a scriptable CLI, confirmed for Codex: `vendors/codex.md`)
1. Preflight: run that vendor's own health check (`codex doctor --summary` for Codex) and require a clean result before dispatching; a failing preflight is surfaced, not worked around.
2. The Orchestrator writes the task as a prompt file `<drafts>/prompt-<vendor>-<task>-<date>.md`, same as the manual path below (goal, context, scope, numbered done-when, return format, effort level).
3. The Orchestrator runs the vendor's non-interactive command directly (for Codex: `codex exec "Read and follow <prompt file path>. ..." -C <worktree> -s workspace-write --output-last-message <file> --json`), scoped to the task's own worktree, never the broadest sandbox mode.
4. Same as step 3 of the manual path below: verify from the repo host, never from the captured output alone.
5. For review instead of a build: the vendor's non-interactive review command (`codex review --base <branch>` or `--commit <sha>`), still not self-trusting its output shape until trialed.

## Manual path (fallback: no scriptable CLI available)
The Program Owner is the relay: they paste a one-line launcher into that vendor's session and tell the Orchestrator "done" when it stops. The vendor session is a **Build Engineer**, not a second Orchestrator (`templates/subagent-vs-chat.md` rule 2: a separate session, kept for work that will outlive one task); one chat per repo still means one Orchestrator, planning and approving. It is fine, and usually better, for the Program Owner to keep one persistent vendor session open and resume it across several task briefs instead of opening a fresh one each time - that carries no history the Orchestrator needs to resend, just the vendor's own memory of prior turns. What must not persist across tasks is working state: each brief still gets its own branch and worktree (R25), even inside the same long-lived session.

### Handover
1. The Orchestrator writes the task as a prompt file `<drafts>/prompt-<vendor>-<task>-<date>.md`, checked against `templates/prompt-checklist.md`: goal, context, scope, numbered done-when, return format, effort level; positive wording; "the user instruction beats repo instruction files if they conflict".
2. The Orchestrator gives the owner ONE paste, in its own code block:
   ```
   Read and follow <prompt file path>. No paid calls, never open .env*.
   ```
   For Tier 2 and 3, the owner's or reviewer's signed plan `go` is posted on the PR before the paste, or the prompt says "post the plan and stop".
3. The agent works in its own worktree and branch `<vendor-prefix>/<task>`, opens a DRAFT PR on the base the prompt names, writes notes to `<audits>/<vendor>-<task>-<date>.md`, replies in at most 6 lines.
4. The owner says "done". The Orchestrator verifies from the repo host and the notes file (head sha, scope, CI, comment format, gate dry run), never from the chat reply alone, then asks the OTHER vendor to review.
5. Merges of this vendor's PRs are also run by this vendor (the author's vendor merges): the Orchestrator writes a merge launcher the same way.

## Guard rails
- The author never reviews its own work.
- For important tasks, check the model that really ran on the vendor's usage page; self-reported model names have been wrong.
- If this vendor runs out of allowance, the Orchestrator keeps running and queues the task until the reset.
- The Orchestrator's own helpers obey the usage ceilings in the adapter (R14): `tools/usage-ledger/usage.py log --vendor --role --task` after every launch (a resume logs its own entry too), `check --window 5h|7d --ceiling N` before the next one - a refusal means queue the task, not launch anyway. The automated path's `--json` output (Codex: `turn.completed.usage`) is a real per-call token count and a reasonable `--cost`; a project that only wants launch counts can leave `--cost` at its default of 1.
