# Handoff: Framework Orchestrator, 2026-10-15 (fourth checkpoint, same day)

## 1. Read this, then...
README.md, AGENTS.md, docs/roles-and-names.md, docs/change-proposals.md, docs/multi-orchestrator-model.md, docs/framework-map.md, docs/vendor-count-modes.md, skills/handoff/SKILL.md, rules/README.md (R1-R28), this file's FINAL UPDATE section if any. The prior handoff (`handoff-framework-orchestrator-2026-10-15-3.md`) is superseded - still useful for session-start context but every PR/state line below is newer.

## 2. PRs and head commits
| PR | Repo | State | What |
| --- | --- | --- | --- |
| #53, #55 | agent-orchestration | MERGED | checkpoint + tag-decision logging (v0.5.0, v0.6.0) |
| #54 | agent-orchestration | MERGED | `templates/gate-pre-review.yml` and `templates/gate-audit.yml` now authenticate the pin clone via a `FRAMEWORK_PIN_TOKEN` repo secret - the framework repo is private, a plain `git clone` from CI never worked. Found live on `advance-po-reader#52`, its own leak L58. `adapters/README.md` has a new "Private framework repo access" section naming the exact secret. |
| - | agent-orchestration | tag pushed | `v0.6.0` at `757c8e2`, verified on the remote |
| #51 | advance-po-reader | MERGED | Retrofit onto the adapter spec - the first real half of the end-to-end trial Carlos asked for |
| #52 | advance-po-reader | OPEN, blocked | The actual gate-cutover PR (switches the live merge gate from `po_gate.py` to the pinned `gate.py`). CI fails cold on the clone-auth bug just fixed in #54. Needs: Carlos creates a `FRAMEWORK_PIN_TOKEN` secret (fine-grained PAT, contents:read, scoped to `agent-orchestration` only) in `advance-po-reader`'s repo settings, and the PO Reader Orchestrator session re-pins to `v0.6.0` (not v0.5.0 - that tag predates the fix) and wires the workflows to the secret. Steps already written for Carlos in `project-notes\NEXT-FOR-CARLOS.md` box 0a-0d. |
| #1, #2 | charlieredondo/SmarterCommerce | OPEN | Unchanged. Handoff #52 (framework->SmarterForge, open) told them v0.5.0 is ready; no reply seen yet - worth a fresh check next sweep, and note v0.6.0 now exists too though it's unrelated to what they're blocked on. |

## 3. Sessions running alongside this one
- **PO Reader Orchestrator** (`local_2e3760b7-e676-4ab6-89d5-ed653f0b35fc`, named `po-reader-orchestrator`, cwd `project-notes`): started this session to handle `advance-po-reader#51`/`#52` without this chat reaching into that repo directly. Got #51 merged, opened #52, correctly diagnosed the clone-auth bug independently (leak L58) before I'd even looked, wrote Carlos's exact next steps into `NEXT-FOR-CARLOS.md`. I sent it a follow-up message (not yet confirmed read) correcting two details: the secret name is now fixed by the template (`FRAMEWORK_PIN_TOKEN`, not "pick any"), and the pin needs to go to `v0.6.0` specifically, not `v0.5.0` (which predates the fix). **Check whether it's read that message and adjusted before assuming its plan is still accurate as last reported.**

## 4. What it waits for, and from whom
- Carlos: create the `FRAMEWORK_PIN_TOKEN` PAT/secret in `advance-po-reader` (steps in `NEXT-FOR-CARLOS.md` box 0a-0b) - this is the actual remaining blocker on the end-to-end proof. Nothing else in the framework blocks it now.
- SmarterForge: reply to handoff #52 (framework repo issue, not to be confused with `advance-po-reader#52` the PR - unfortunate number collision across repos, worth remembering when re-reading old handoff text).
- Carlos: sharing the dad/friends walkthrough artifact (`https://claude.ai/artifact/AnDaYr3uQ2g4Y7m8P96jdV`) once he's ready to show it; he said to revisit/extend it once the end-to-end trial actually lands, not before (memory: `project_install_walkthrough_video`).

## 5. What it did not check
- Whether the PO Reader Orchestrator session has read and acted on the correction message sent this turn.
- Whether SmarterForge has replied to handoff #52.
- Whether `v0.6.0`'s fix actually works end to end in real CI (not yet proven - the secret doesn't exist in `advance-po-reader` yet, so the authenticated clone path has only been checked locally with a fake token, not against a live GitHub Actions run).

## 6. Decisions not yet written elsewhere
All written: `docs/decisions.md` has both `v0.5.0` and `v0.6.0` rows. Nothing pending beyond those.

## 7. Rules learned this session that must not be rediscovered
(Carried forward from handoff -3, still true: audit findings from another vendor can be real bugs, verify by reproducing; a self-merge policy must be restated in-conversation, doesn't carry over from settings alone; Claude Code cannot edit its own permission settings even via a skill; a literal newline inside a JS string literal is a silent total script failure; cross-repo work is a new session, never a tool call from here.)

New this checkpoint:
- **A framework fix proven "locally" (fake token, a string-substitution test) is not proven end to end until a real project's real CI actually exercises it.** `v0.6.0`'s clone-auth fix was checked by simulating the shell logic with a fake token - correct, but still short of the actual proof, which needs `advance-po-reader#52`'s CI to go green after Carlos creates the real secret. Don't describe this as "fixed and done" until that happens; describe it as "fixed, awaiting the real test."
- **A tag number is not interchangeable with "the latest tag that has the fix."** The PO Reader Orchestrator's own plan (written before this session's #54 existed) was about to re-pin to `v0.5.0`, which does NOT contain the clone-auth fix (that landed in `v0.6.0`, tagged after `v0.5.0`). A peer session's plan can be stale the moment a new tag lands after it was written - said as a correction, not assumed caught on its own.
- **The same PR number can exist in two different repos and mean completely unrelated things.** Framework issue `#52` (a handoff to SmarterForge) and `advance-po-reader` PR `#52` (the gate-cutover PR) are unrelated, coincidentally numbered the same. Always say which repo when citing a number past this point in the conversation.

## 8. Usage, this session (at this checkpoint)
- 5-hour window: 46% used, resets in ~3h.
- Weekly window: 69% used, resets in ~3d22h.
- Context: 428,950 / 1,000,000 tokens (43%), auto-compacts at 97%. Carlos's own checkpoint threshold this session is 300k, not the usual ~60% - crossed again; this is the second checkpoint for that same reason (the first was handoff -3 at 366k). At this rate, checkpoint proactively rather than waiting to be told again.

## 9. Next three actions
1. Check whether the PO Reader Orchestrator session read the correction message (secret name, v0.6.0 not v0.5.0) and check `advance-po-reader#52`'s real CI state once Carlos says he's created the secret.
2. Re-check handoff #52 (framework -> SmarterForge) for a reply.
3. Once `advance-po-reader#52` actually goes green end to end, that is the real completed proof Carlos asked for this session - worth its own short, clear status update to Carlos (and the moment to revisit the walkthrough artifact per his own stated preference).

## FINAL UPDATE
None - current as of the moment this was written.
