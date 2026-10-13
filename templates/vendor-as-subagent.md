# Another vendor's agent as a build or review subagent
Use when the Orchestrator cannot launch the other vendor's agent itself. The Program Owner is the relay: they paste a one-line launcher into that vendor's session and tell the Orchestrator "done" when it stops. Typical reason: spread work across allowances so the Orchestrator's session never runs out.

## Handover
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
- The Orchestrator's own helpers obey the usage ceilings in the adapter (R14).
