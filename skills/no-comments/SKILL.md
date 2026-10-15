---
name: no-comments
description: Prune comments that don't earn their place out of a diff or file set, before a PR goes up for review. Spawns a fresh, read-only subagent to do the hunting so the pruning lens isn't softened by whoever wrote the code. Use before opening a PR, or whenever asked to clean up comments.
---

# No comments

Adapted from pstack's `no-comments` and `comment-sicko` (`ideas/2026-10-14-pstack-no-comments-and-swarm.md`, I-009). This sharpens the same thing this repo's own authoring style already asks for (default to no comments; a comment survives only for a non-obvious why) into an enforced pass instead of a prose reminder.

## Ground rules
- **The hunter is read-only and fresh.** Spawn a new subagent for the hunt every time (R25); never reuse one that has already seen this diff, and never let the Build Engineer's own session hunt its own code. Same blind spot this repo already distrusts in a same-vendor review (R21).
- **Only comments and dead code are in scope.** The hunter may read application code to judge a comment's claim. It may not propose a behaviour change.
- **Five exceptions survive, nothing else.** (1) Legal or license headers. (2) A comment forced by something outside this repo's control (an external API's undocumented quirk, a platform bug) and not a surprise in our own code. (3) A formatter or lint suppression whose rule is itself wrong for this line. (4) A doc comment that defines a public API's contract. (5) An issue or RFC link that explains a constraint the code itself cannot express. A comment that is none of these is a kill, however confident it sounds ("IMPORTANT", "do not remove", "temporary", "fine for now").
- **A kill of our own code's surprise gets a reshape flag, not silence.** Mark the exact symbol for a rename, extract, or type that would make the behaviour obvious without the comment. Do not restore the comment as a stand-in for that fix; the fix is reported, not made here, unless it is the smallest possible deletion (see step 4).
- **One re-hunt, then stop.** Reject and re-run once if the report: edits application logic rather than a comment, escapes the stated scope, claims an exception without the file:line evidence this file requires, or kills a comment that turns out to satisfy one of the five exceptions. A second rejected report ends `/no-comments` as `blocked`, named in the PR body, not silently merged either way.

## Steps
1. **Scope.** The caller's named files, or the current diff against the base branch (default `main`), including the working tree, if none is named.
2. **Hunt.** Spawn a subagent with exactly the scope and the five-exception list above, nothing else from this file. It returns, per comment: `kill` or `keep`, the file:line, and for a kill of our own code's surprise, the reshape flag; for a keep, which exception number and the evidence that it applies.
3. **Check the report.** Reject and re-hunt (once, per Ground rules) on any of the four rejection conditions above.
4. **Act.** Delete every accepted kill. Fix a trivial accepted case directly only when it is a straight deletion (a dead branch the comment was justifying, an unused parameter, a suppression whose rule no longer fires) with no shape decision involved. Anything needing a real design change is reported as open work, not fixed here.
5. **Report.** Deletions (count and file:line), reshape flags, kept exceptions with their evidence, anything the hunter and the check disagreed on, and the outcome: `clean` (nothing to kill), `pruned` (deletions made, listed), or `blocked` (second rejection, named).
