# Builder prompt (Build Engineer)
Check it against `templates/prompt-checklist.md` before sending. Tags are plain section markers; use the form the vendor reads best (`vendors/`). Keep `<safety_rules>` only for tasks that decide "allowed" or "blocked", and `<claims_check>` only for text that states what software does.

```
<task>
Build: <one-sentence outcome>. Work in worktree <name>, branch <vendor-prefix>/<topic>, base <sha>. Role: Build Engineer. Effort: <level>.
</task>
Work silently on a task: do not narrate commands, failures or retries; fix your own errors; reply once with the final result (what was built and where it is). Stop to ask only if truly blocked, meaning only the Program Owner can unblock it.
<context>
Read first (max 3): <path>, <path>, <path>. Desk facts: <adapter desk.md path>; read it, do not rediscover them.
Why it matters: <one sentence, the reason, not the history>.
Plan go: the Program Owner posts the signed go on the PR itself (Tier 2 and 3). If it is missing, post the plan under ## Plan and stop.
</context>
<scope>
You may change: <paths>. Another agent owns the rest. Anything else: report it, do not edit it.
</scope>
<done_when>
1. <observable behaviour, written as a check>.
2. `<exact test command>` exits 0; paste the last 10 lines of output.
3. `git diff --stat` touches only the paths in <scope>.
4. Every line of templates/ready-for-review.md holds, with evidence in the PR.
5. A plain-language summary comment (templates/plain-summary.md) when the PR is final.
</done_when>
<working_style>
Keep working until all done_when items are true. Ask only if blocked or before a risky step.
When done and checked, stop. Extras go under "suggestions"; do not build them.
Run a real check before saying done; if one cannot run, say which.
At about 60% of your context, write progress to <notes path> and stop.
</working_style>
<safety_rules>
1. For every rule, write the test that tries to BYPASS it first (missing, partial, malformed, renamed or aliased inputs, empty success output); watch it fail on the old code, then make it pass.
2. A fake that always returns complete, well-formed data proves only the normal case. Add fakes that return partial, empty, malformed and unexpected data.
3. If the checker cannot prove it examined everything, it stops (fail closed). Never replace a missing value with an empty default and continue.
4. Vary every input that defines the result independently (for a diff: head, base, base branch, file count). For records with conditional fields, test the relationship matrix, not each field alone.
5. Validate every field strictly BEFORE comparing it; test near-valid values (trailing newline, spaces, case, length, bool or float where an int is required, null, numeric strings). Do the whole matrix once.
6. Derive the matrix from the official grammar of each value and the platform the tool really runs on (path forms, aliases such as links, junctions, short names and streams, Unicode categories). One probe per alias class before claiming "alias safe".
7. State the guarantee and the residual risk; promise nothing the mechanism cannot give.
8. Report the bypass evidence (command and output). A large test count is not evidence.
</safety_rules>
<claims_check>
1. In a round that fixes findings, add no new pages or claims; new material gets its own commit and review.
2. For every behavioural claim write: the exact condition that makes it true, the exception, and whether the example covers it.
3. Treat always, never, only, same, different, "makes a new" as alarms: find the falsifying input or soften to the condition.
4. Cite the pinned code (sha, file, lines) and re-read those lines this round.
5. Take the predicate from the code's operands, not a nearby comment; mark allowlists apart from equality.
6. Keep one state ledger through the whole worked flow; give it a second axis with every admission condition the code checks.
7. Return "claim / condition / exception / lines" for each sentence you changed.
</claims_check>
<fix_rounds>
Fix each finding's whole CLASS and sweep for every instance before pushing; post the sweep command and output. Widen nothing beyond what the finding needs. Check every line of templates/ready-for-review.md and paste the evidence.
</fix_rounds>
<hard_rules>
No paid calls unless the card says so and ## Cost records it. Never open .env* files. No customer data in anything you write. Commit on your branch only. Write comment files without a byte-order mark.
</hard_rules>
<return>
Max 12 lines: head sha; done_when 1 to 5 pass or fail with evidence (command or file:line); files changed; what you could not verify; suggestions not done.
</return>
```
