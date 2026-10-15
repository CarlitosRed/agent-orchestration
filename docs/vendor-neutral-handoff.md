# Vendor-neutral orchestrator handoff (PROPOSED, not designed)
Carlos, 2026-10-14: copying prompts between chats by hand doesn't scale, and the framework is meant to be published - anyone, any vendor, downloads it and runs their own orchestrators. The fix used earlier today (a direct session-to-session message, `docs/multi-orchestrator-model.md`) only works because both chats happened to be Claude Code sessions on the same machine; it has no Codex equivalent and nothing a stranger's install could rely on.

## The actual requirement
A project Orchestrator (any vendor) needs to pick up: a new framework tag, a specific ask from the Framework Orchestrator, or a reply to one - without the Program Owner retyping it, and without depending on a product-specific session-messaging feature.

## A starting sketch, not a decision
A plain file drop, inside the receiving repo's own `.orchestration/` folder (so it travels with the adapter spec, not as a separate mechanism):
```
.orchestration/inbox/
  2026-10-14-1432-framework-v0.1.0.md   one message per file, UTC timestamp in the name
```
Any orchestrator, any vendor, checks this folder as the first step of its own sweep (same place `RESUME-*-orchestrator.md` files already say "sweep first"); a message is moved to `inbox/read/` once acted on, so the next sweep doesn't re-read it. Writing one is just writing a file - no vendor API, no shared process, works identically for Claude, Codex, or a human editing it by hand.

## What's unresolved
1. Does the framework repo need its own inbox too, for projects writing back (today that's the leak log; is a plain message ever better than a structured leak row)?
2. How does a session know new mail arrived without polling - or is "check at the start of every sweep" simply good enough, given these are long-lived conversational sessions, not a live service?
3. Whether this belongs in `adapters/README.md` (every project gets one) or stays framework-repo-only (only the Framework Orchestrator writes to projects' inboxes, not peer-to-peer between projects).

## Status
Not designed. Candidate to pull ahead of F7's normal vendor-adapter timing, since it directly blocks "publish this for anyone to run," which is the stated goal. Needs its own change proposal before anything here becomes a rule.
