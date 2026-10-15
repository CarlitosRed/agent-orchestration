# Handoff: Framework Orchestrator, 2026-10-15

## 1. Read this, then...
README.md, AGENTS.md, docs/roles-and-names.md, docs/change-proposals.md, docs/multi-orchestrator-model.md, docs/framework-map.md, skills/handoff/SKILL.md, rules/README.md (R1-R28), the newest docs/*-report.md, this file's FINAL UPDATE section if one exists below.

## 2. PRs and head commits
All 33 PRs opened today are merged; `main` is clean, nothing open on `agent-orchestration`.
| Tag | Commit | What it covers |
| --- | --- | --- |
| `v0.1.0` | `56472fe` | PRs #1-7: F4-trial hardening, pstack ideas intake, no-comments skill, R25-R27 |
| `v0.2.0` | `f9d6662` | PRs #8-26: handoff bus, onboard/retrofit-project, F6 closed (R13/R14/R16/R18/R22 real enforcers), claims-ledger, multi-kind-class, usage-ledger, Codex vendor profile |
| `v0.3.0` | `77c0921` (HEAD) | PRs #27-33: Claude Code vendor profile, README/playbook/cost-ledger refresh, two adapter-spec gaps from PO Reader's retrofit, legacy_signers schema fix, claims-ledger `--since`, I-014 benchmark-checklist (R28), I-012 blinded-eval |

Elsewhere (not mine, read-only):
| Repo | PR | State | Next step |
| --- | --- | --- | --- |
| `advance-po-reader` | #51 "Retrofit onto the framework's adapter spec" | OPEN, mergeable | PO Reader Orchestrator's own tier-3 review; not mine to approve |

## 3. What it waits for, and from whom
- `advance-po-reader#51` waits on PO Reader's own tier-3 review/merge - theirs, not mine.
- Career HQ onboarding waits on Carlos starting that chat with the paste-ready prompt already given (below, still unused as of this handoff).
- `vendors/claude-code.md`'s live smoke test waits on Carlos running `claude auth login` on this desk (an OAuth flow; deliberately not done by me - see "Rules learned").

## 4. What it did not check
- Whether the Career HQ Orchestrator chat was ever started - last checked 2026-10-15 morning, it had not been.
- Whether `advance-po-reader#51` has had any review activity since it was opened - checked once (OPEN, mergeable), not polled since.
- I-005 (pstack `autopilot-full`: "approval survives a rebase when the patch id is unchanged") was discussed in reasoning but never written to a design doc or built. Scoping notes below, under "Next three actions" - this is real unfinished work, not forgotten, just not started.

## 5. Decisions not yet written elsewhere
None pending beyond what's in `docs/decisions.md` - it was kept current through this handoff (v0.1.0, v0.2.0, v0.3.0 entries all present).

## 6. Rules learned this session that must not be rediscovered
- **`gh issue list --label "a,b"` silently returns empty.** Needs the flag repeated: `--label a --label b`. (`gh issue create --label a,b,c` DOES accept the comma form - the two subcommands differ. Fixed in `skills/handoff/SKILL.md` and `docs/vendor-neutral-handoff.md`.)
- **Never name a file `claude.md` anywhere in this repo, any case.** Collides with `CLAUDE.md` on a case-insensitive filesystem (Windows, default macOS), which Claude Code auto-loads as project instructions. Confirmed live - a system reminder surfaced an uncommitted draft back as instructions before it was ever committed. `vendors/README.md` documents this now.
- **Tag at every real checkpoint, not just session starts.** `v0.1.0` was 20 commits stale by the time the first real trial (`retrofit-project` on PO Reader) needed it. This handoff practices the lesson immediately (`v0.3.0`, same day as `v0.2.0`).
- **A persistent vendor session (Codex or Claude, resumed across tasks) is a Build Engineer, not a second Orchestrator.** "One chat per repo" still means one Orchestrator; the persistent session is convenience, not a role change (`templates/vendor-as-subagent.md`).
- **Codex's automated shell-exec is broken on Windows by an open, unresolved upstream bug** (`helper_unknown_error: setup refresh had errors` - sandbox provisioning tries to ACL its own running binaries). Ruled out Defender exclusions, reinstall, and the `code_mode_only` feature flag, in that order, before concluding it's upstream (`vendors/codex.md`). Do not re-attempt these three fixes blind.
- **Claude Code's own standalone CLI (`@anthropic-ai/claude-code`) does not inherit the desktop app's login** on this desk - needs its own `claude auth login`, not done (Carlos's own action, an OAuth flow).
- **Program Owner's standing instruction (saved to global memory, `feedback_autonomy_over_questions.md`):** act and report, don't interview; ask only on a real fork. Merge policy evolved during this session from "ask every PR" to "self-merge everything in this repo, flag anything genuinely novel or risky" - 33 PRs merged today under that policy with zero objections.
- **Always verify the real package name before installing** (`npm view <pkg> description homepage`) - caught nothing bad this session, but it's the standing discipline that made both vendor installs (Codex, Claude Code) trustworthy evidence rather than guesses.

## 7. Usage, this session
- 5-hour window: 25% used, resets in 4h 39m (as of this handoff).
- Weekly window: 53% used, resets in 4d 5h.
- Context: 879,337 / 1,000,000 tokens (88%), auto-compacts at 97%. Messages (the conversation itself) is 79% of the window - the dominant cost, same finding as the mid-session check earlier today; nothing new to add beyond what's already in that exchange.

## 8. Next three actions
1. Check `advance-po-reader#51`'s review status; if merged, confirm `.orchestration/verify/` is still correctly deferred (it was deliberately not created, pending the open fold-into-#43 decision from the F4 trials - do not create it without checking that decision first).
2. If Carlos wants Career HQ onboarded: confirm whether that chat has been started; if not, the paste-ready prompt is already written (see the Framework Orchestrator's prior reply in this transcript, or regenerate from `skills/retrofit-project/SKILL.md` + `adapters/README.md` the same way).
3. Scope I-005 before building it: "approval survives a rebase when the patch id is unchanged" needs real git tree access (not just GitHub API metadata, which is all `tools/gate/gate.py` uses today) to compute `git patch-id` across a rebase. Recommend building `patch_id_of()` as a small, pure, separately-tested helper first (same pattern `changed_lines()` used for claims-ledger) - do NOT modify `cmd_merge`'s existing refuse-on-any-base-move logic in the same pass; that logic has 227 tests riding on its current conservative behavior and deserves its own careful, dedicated review before anything about it changes.
