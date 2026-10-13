# Task card: <short-name>
Written by the Orchestrator. One card, one branch, one Build Engineer.

Project: <project>   Builder: <Build Engineer · Vendor>   Branch: <vendor-prefix>/<topic>   Date: <date>
Tier: <1 | 2 | 3>   Reviewer: <Independent Reviewer · other vendor>   Desk: <worktree folder>   Merge by: <author's vendor>

## Goal
One or two sentences: what exists when this is done.

## Read first
- <at most three files this task needs>

## Allowed to change
- <folders or files>. Anything outside needs a new card. A path on the project's protected list makes the tier 3, whatever the label says.

## Done when
- [ ] <a check someone can run>
- [ ] <a check someone can run>

## Leave alone
- <files, folders or decisions that must not change>

## Stop and ask the Program Owner if
- the change needs a paid call, a new key, a spend limit, production access, a deletion, or a decision this card does not make.

## How it is reviewed
Draft PR with `## Plan` first; wait for a signed plan `go` on this PR (Tier 2 and 3; say who gives it); then build; then `## Evidence` and `## Cost`; check `templates/ready-for-review.md`; then the reviewer's `Approved at <full sha>` (and the owner's line on Tier 3). The author's vendor merges with `<gate> merge <PR> --as "<Role · Vendor>"`. Sign every comment `**<Role> · <Vendor>:**`.

## When finished
Add a short handoff note in the project's handoff file. Say what changed and what was only documented, not built.

## Check with the Program Owner first
Does this card match what was meant? A one-line yes, or the correction.
