# Handoff: Framework Orchestrator, 2026-10-19 (checkpoint, Program Owner's own call, 73% context)
One screen of facts, no prose.

## 1. Read this, then...
README.md, AGENTS.md, docs/roles-and-names.md, docs/change-proposals.md, docs/multi-orchestrator-model.md, docs/framework-map.md, docs/vendor-count-modes.md, skills/handoff/SKILL.md, rules/README.md, and the newest docs/f*-report.md files, in that order. The prior handoff (`handoff-framework-orchestrator-2026-10-16.md`, written by a Codex-based Orchestrator session, committed in this same checkpoint) is superseded - still useful for the full #65 build/review trail, worth a skim, but every PR/state line below is newer and independently re-verified today, not relayed.

## 2. Usage at checkpoint
Context: 731,748 / 1,000,000 tokens (73%), auto-compacts at 97%. 5-hour window: 10% used (resets in ~5h). Weekly (all models): 2% used (resets in ~7d). Plan: Pro.

## 3. PRs and head commits - fresh sweep, not relayed
Main: `9604c8a` (PR #64 merged). Newest tag: `v0.7.0` -> `98a77b7`; no v0.8.0. Handoff inbox (`handoff` + `to:framework`): empty. No GitHub Actions workflows run on this repo itself (confirmed: `checks: []` on every open PR) - all testing here is local/offline, by design.

| PR | State | What |
| --- | --- | --- |
| #59 | OPEN, CLEAN, not draft | PAT-fallback clone simplification. I resolved a real merge conflict with main via an Auto-fix event 2026-10-16 (explains the "unexplained drift" the 10-16 Codex handoff flagged on this PR's head - not a mystery, just two sessions touching the repo the same evening). Still just needs Program Owner review. |
| #60 | OPEN, CLEAN, not draft | Original benchmark-harness proposal. **Now an empty diff against main** - its real content shipped separately via #64 (Codex's own correction). Recommend closing, not merging. |
| #61 | OPEN, CLEAN, not draft | Privacy naming cleanup (Carlos -> Program Owner). Also conflict-resolved by me 2026-10-16 after an Auto-fix event; had to redo it carefully since a naive merge would have silently undone the cleanup on the older decisions.md rows. Verified clean afterward. |
| #62 | OPEN, CLEAN, not draft | I-017/I-018 ideas-register entries (Codex failover, local-model Operations Clerk). I-017 since confirmed live-tested in this same checkpoint window. |
| #63 | OPEN, CLEAN, not draft | vendors/codex.md desk-facts: the desktop-app's own Codex install path + `--no-daemon` requirement, found live getting the Program Owner's own interactive Codex session working. |
| #65 | OPEN, CLEAN, **draft** | Codex's own proposal (not mine, not the Program Owner's): `tools/dispatch-plan/`, an opt-in preflight checker for parallel-dispatch worker ID/dependency/write-ownership conflicts (R5/C11). Built and reviewed entirely by Codex sessions (same-vendor only). I independently re-verified 2026-10-19: re-ran all 427 offline tests myself in a clean worktree (pass), read the actual `dispatch_plan.py` (sound, careful, matches house style). **Still missing: a real cross-vendor review (R21) and Program Owner approval** - I offered to do the Independent Reviewer pass; Program Owner said hold off, not yet. |

## 4. The big arc this window: Codex as a second live Orchestrator, not just a reviewer
Program Owner asked whether the Framework Orchestrator role could fail over to Codex (I-017). Tested live via `codex exec`, confirmed working, then helped get a real interactive Codex CLI session running on the Program Owner's own desktop (found the real install path, `C:\Users\carlo\AppData\Local\OpenAI\Codex\bin\<hash>\codex.exe`, not on PATH by default, needs `--no-daemon` - documented in #63). That Codex session then ran for real as Framework Orchestrator: merged #64 (with Program Owner's explicit one-time same-provider-review exception), and independently proposed and built #65 on its own initiative. Also got a standalone `claude` CLI working the same way (npm global install, needed a PowerShell execution-policy fix the Program Owner ran himself - I never touch that setting). Program Owner's own stated goal: CLI fluency with both vendors, not desktop apps - saved as a standing preference in memory.

## 5. What it did NOT check
- Whether the Program Owner has looked at #59/#60/#61/#62/#63 since my sweep - no review activity visible on any of them as of this checkpoint.
- Whether `po-reader-orchestrator` or the SmarterForge Codex session are still alive - `ListAgents` shows no reachable peer sessions right now; the 10-16 Codex handoff warns not to infer liveness from session metadata either way. advance-po-reader#53 (that project's own name-cleanup PR) is still open, not merged.
- Whether SmarterForge (the Program Owner's dad, `charlieredondo/SmarterCommerce`) has moved since re-pinning to v0.7.0 and getting a clean review - handoff issue #52 still shows only the same 2 comments from 2026-10-16, no new activity.
- The exact state of the Codex-only "PO session" and "SmarterForge session" interactive terminals the 10-16 handoff describes (`orchestrator-sessions/2026-10-16/`) - not re-inspected this checkpoint, per that handoff's own "do not restart automatically" caution.

## 6. Rules learned or reinforced this window
- **A session's own handoff file can sit uncommitted on disk for days.** The 10-16 Codex handoff was never pushed - R7 says "write a handoff file," not "and commit it." Worth treating "commit and push the handoff" as part of the rule in practice, not just writing it locally, or the next session may never find it unless told the exact path.
- **"Head changed" isn't automatically suspicious.** The prior handoff correctly flagged drift on #59/#60/#61 as unexplained rather than guessing - the real explanation (Auto-fix-triggered merge-conflict resolutions from a parallel Claude session) was mundane. Flag drift, don't assume malice or corruption; a live sweep resolves it faster than speculating.
- **Same-vendor review is real evidence, just not R21-sufficient evidence.** #65's Codex-only review (427 tests, two independent audit slices, a scheduling oracle) is genuine technical rigor - it still isn't cross-vendor independence, and both the building Codex session and this session agree on that framing. Don't let thoroughness substitute for the actual rule.
- **CLI quirks are desk facts, not framework facts** - documented in `vendors/codex.md` (#63) rather than guessed at from memory each time: the desktop-app Codex binary needs `--no-daemon`; `codex queue` (used for the PO session) rejects that same flag - different subcommands, different requirements, confirmed by the prior session, not yet independently re-tested by this one.

## 7. Next three actions
1. Ask the Program Owner directly: review/merge-or-close #59, #60 (close - empty diff), #61, #62, #63; decide #65 (approve as-is, request the real cross-vendor review I'm available to run, or hold).
2. Re-sweep `po-reader-orchestrator` and SmarterForge liveness next session - both went quiet with no explanation, worth a direct check rather than assuming either finished or stalled.
3. If #65 gets a go-ahead for real cross-vendor review: run it properly (fresh read of the diff, not a relay of Codex's own self-review), post a signed `**Independent Reviewer · Claude:**` comment on the PR itself per R22, not just a chat summary.

## FINAL UPDATE
None - current as of the moment this was written.
