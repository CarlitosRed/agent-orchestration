# Handoff: Framework Orchestrator, 2026-10-15 (third checkpoint, same day)

## 1. Read this, then...
README.md, AGENTS.md, docs/roles-and-names.md, docs/change-proposals.md, docs/multi-orchestrator-model.md, docs/framework-map.md, docs/vendor-count-modes.md, skills/handoff/SKILL.md, rules/README.md (R1-R28), this file's FINAL UPDATE section if one exists below. The prior handoff (`handoff-framework-orchestrator-2026-10-15-2.md`) is superseded by this one - still useful for session-start context (rules learned, usage pattern) but every PR/state line below is newer.

## 2. PRs and head commits
| PR | Repo | State | What |
| --- | --- | --- | --- |
| #47 | agent-orchestration | MERGED | vendors/codex.md: named the danger-full-access preflight exception (handoff #46) |
| #49 | agent-orchestration | MERGED | templates/gate-audit.yml, required in adapters/README.md; rules/README.md R9/R23 point at it |
| #50 | agent-orchestration | MERGED | gate.py: config load now refuses a same-vendor review tier without 2+ distinct reviewers and owner_approval (handoff #48, a real self-approval loophole Codex found and I reproduced independently) |
| #51 | agent-orchestration | MERGED | docs/decisions.md: logged the v0.5.0 tag |
| - | agent-orchestration | tag pushed | `v0.5.0` at `b933f81`, verified on the remote before logging it |
| #51 | advance-po-reader | OPEN, MERGEABLE | Retrofit PR. Codex review approved (`Approved at 7aee81d`). Still needs plan `go` + Carlos's own owner-approval comment - delegated to a fresh PO Reader Orchestrator session (`local_2e3760b7...`, started this turn) rather than done from here. Stacked `claude/gate-cutover` branch is the next step once this merges. |
| #1 | career-agent-hq | MERGED | unchanged since the last handoff |
| #1 | charlieredondo/SmarterCommerce | OPEN | Unchanged - still pinned at v0.4.0's commit. Handoff #52 (below) tells them v0.5.0 is ready; no reply seen yet. |
| #2 | charlieredondo/SmarterCommerce | OPEN | New since last handoff - a documentation-only knowledge handoff for the Management Console app, explicitly independent of #1. Not framework-relevant; not acted on. |

## 3. Handoffs this session
| # | Direction | State | What |
| --- | --- | --- | --- |
| #46 | SmarterForge -> framework | CLOSED | Doctor-preflight gap; replied pointing at #47 |
| #48 | SmarterForge -> framework | CLOSED | Reproduced and fixed the same-vendor validation gap; replied pointing at #50 |
| #52 | framework -> SmarterForge | OPEN | Told them v0.5.0 is live, tagged and pushed; asked them to re-pin and retry `codex review --commit`. No reply yet - check first thing next sweep. |

## 4. What it waits for, and from whom
- Carlos: plan `go` + owner-approval comment on `advance-po-reader#51` - now the PO Reader Orchestrator session's job to prompt him for, not mine.
- SmarterForge's Codex orchestrator: reply to handoff #52 (re-pinned? reviewer dispatch actually unblocked?).
- Carlos: whether/when to share the dad-and-friends walkthrough artifact (`https://claude.ai/artifact/AnDaYr3uQ2g4Y7m8P96jdV` - a click-through explainer: install, start a project, how a merge works, the honest limits today, current status). Private by default; needs sharing turned on from the page's own Share menu before it's useful to anyone but Carlos. Built this session, fixed one real bug (a literal newline inside a single-quoted JS string broke the whole script - republished, confirmed fixed).
- Carlos said he wants this re-done or extended once the framework is proven end-to-end on a real trial, not before (saved as memory `project_install_walkthrough_video`).

## 5. What it did not check
- Whether the PO Reader Orchestrator session (just started, background) has made any progress yet - do not assume either way, check `list_sessions` / its own report.
- Whether SmarterForge has read handoff #52.
- Whether `codex review` under `danger-full-access` behaves any differently now that `vendors/codex.md` names the exception explicitly - the doc changed, the tool's own behavior (`codex doctor`, `codex review`) did not; still only confirmed on Carlos's desk per the existing vendor profile's own caveats.

## 6. Decisions not yet written elsewhere
All written: `docs/decisions.md`'s `v0.5.0` row covers #47/#49/#50. Nothing pending beyond that.

## 7. Rules learned this session that must not be rediscovered
- **An audit finding from another vendor can be a real tool bug, not just a documentation gap - verify by reproducing it, not by trusting the report.** Codex (SmarterForge's orchestrator) reported two gate.py gaps in handoffs #46/#48. Both were real: reproduced directly against this repo's own `gate.py` before writing any fix (not taken on report alone), and re-verified the fix against SmarterCommerce's actual deployed config, not just synthetic test fixtures. This is the same discipline as the prior session's "verify the technical action actually happened" lesson, extended to a peer's audit claims.
- **A self-merge policy must be restated in chat, in the current conversation, to actually unblock `gh pr merge`.** The permission rule already existed in `~/.claude/settings.json` (`permissions.autoMode.allow`) from a prior session, but `gh pr merge` was still denied twice (once by the local classifier, once by a server-side one with no reason given) until Carlos typed the standing-policy sentence explicitly in this chat. The existing rule's own wording requires it be set "in this conversation" - a policy from a past session's settings file does not carry the weight of a fresh verbal statement. Expect to ask for this again in the next fresh chat; do not assume it persists.
- **Claude Code cannot modify its own permission settings, even via a dedicated skill, even when the user asked for it.** `update-config` was denied by a "Self-Modification" classifier. Don't retry this path; the only ways through are the user editing `~/.claude/settings.json` themselves, or (what actually worked) the user stating the policy sentence directly in chat.
- **A JS string with a literal (unescaped) line break inside quotes is a silent, total failure, not a partial one.** It throws a SyntaxError on the whole inline `<script>` block, so EVERY handler on the page fails to attach - symptom was "I can not click it or do anything," not "this one button is broken." Multi-line text going into an HTML attribute from a JS string literal needs `\n`, never a raw newline in the source.
- **Cross-repo work is a new session, not a tool call from here.** Carlos asked to "set up the test end to end using the PO... and SmarterForge." The SmarterForge half is a GitHub handoff issue (already the right channel). The advance-po-reader half is NOT something to do via `gh` commands from this chat, even read-only checks are fine but writing an approval or a plan `go` is not - that boundary is `docs/multi-orchestrator-model.md`'s whole reason for existing, and the original scope-overreach mistake it was written to prevent. Started a fresh `PO Reader Orchestrator` session (`start_session`, cwd `project-notes`, fresh context) instead of reaching into that repo directly.

## 8. Usage, this session (at checkpoint)
- 5-hour window: 27% used, resets in 3h16m.
- Weekly window: 67% used, resets in 3d23h.
- Context: 366,243 / 1,000,000 tokens (37%), auto-compacts at 97%. Carlos set a tighter personal checkpoint threshold this session - 300k, not the usual ~60% - and this handoff is that checkpoint, written right after crossing it.

## 9. Next three actions
1. Check on the PO Reader Orchestrator session (`local_2e3760b7-e676-4ab6-89d5-ed653f0b35fc` / `po-reader-orchestrator`) - did Carlos post the plan `go` and owner approval, did #51 merge, did the `claude/gate-cutover` branch open as its own PR.
2. Check handoff #52 for SmarterForge's reply - re-pinned to v0.5.0? reviewer dispatch actually unblocked, or did something else surface?
3. Once advance-po-reader#51's trial actually completes (merged, gate cutover done), that is the real end-to-end proof Carlos asked for - revisit the dad/friends walkthrough artifact then, per his own stated preference (saved in memory), rather than before.

## FINAL UPDATE
None - this handoff is current as of the moment it was written.
