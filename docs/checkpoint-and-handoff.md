# Checkpoint and handoff
Long sessions get compacted and compaction drops detail. Files hold the truth, so a fresh session loses nothing.

## When to checkpoint
At about 60 percent of context, when the Program Owner says "checkpoint", or at a finished milestone. Builders write progress to their notes file at about 60 percent and stop.

## The handoff file
`<audits>/handoff-<session name>-<date>.md`, written by that session only. One screen of facts, no prose:
1. A "read this, then ..." line listing the files a successor reads, in order.
2. PRs and head commits (a table: PR, branch, head, state, next step).
3. What it waits for, and from whom.
4. What it did not check.
5. Decisions not yet written in a PR comment or the decision log.
6. Rules learned this session that must not be rediscovered.
7. Usage: the windows and when they reset.
8. Next three actions.
Later in the same session, add dated `UPDATE` sections; the last one is headed `FINAL UPDATE` and overrides everything above it.

Standard checkpoint prompt:
```
Checkpoint now. Write <audits>/handoff-<name>-<date>.md (new file; edit no other file). One screen of facts, no prose: PRs and head commits, what you wait for, what you did not check, decisions not yet written down, next three actions. Reply with the path only.
```

## The resume prompt
A small file `RESUME-<role>-<n>.md` holds one paste for the next session, in its own code block:
```
You are <Role> <n>, continuing <Role> <n-1>. Read <handoff path> (the FINAL UPDATE section overrides everything above it), then <owner's next file>, <work queue>, the last 30 rows of <decision log>, <rules>, <templates that matter now>, <desk facts>. Do a sweep first (startup sweep). Then continue: (1) <...>; (2) <...>; (3) <...>. Rules to keep: <the few learned rules that cost rounds>. Never open .env*.
```

## The owner's "what to do next" file
One file, written by the Orchestrator, read by the Program Owner on any device:
- the single next action at the top;
- below it, each paste-ready prompt in its own code block, headed by the session it goes to;
- updated in the same turn as any state change or handed prompt; every reply to the owner ends with that single next action.

## After the handoff
The finished session gets a closing note in the state file and is archived the same day (R1).
