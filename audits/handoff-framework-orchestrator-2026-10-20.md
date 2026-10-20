# Handoff: Framework Orchestrator, 2026-10-20 (written the evening of 2026-10-19 local; checkpoint at the Program Owner's request)
One screen of facts, no prose. Newer than `handoff-framework-orchestrator-2026-10-19.md`, which it supersedes.

## 1. Read this, then...
`STATE.md` first (how a change lands now), then README.md, AGENTS.md, docs/roles-and-names.md, docs/change-proposals.md, docs/multi-orchestrator-model.md, skills/handoff/SKILL.md, rules/README.md, `.orchestration/leaks.md`. The resume list is `RESUME-framework-orchestrator.md` (9 files). Self-review evidence: `audits/framework-self-review-2026-10-19.md`.

## 2. State at checkpoint (read from the repo, not relayed)
Main `66202db`. Newest tag `v0.9.0` on `d5955b4`. Open PRs: none. Handoff inbox for `to:framework`: empty. One open issue: #52 (`to:smarter-forge`, from this repo, no reply since 2026-10-16). Checks on this repo: `tests` (required, includes the hygiene checks), `pre-review`, `gate-audit`; merges go through `python tools/gate/gate.py merge <PR> --as "Release Manager · Claude"` run from a worktree of `origin/main`.

## 3. Merged this session, all through the gate with a Codex review where tier 2 or 3
#59 clone fallback, #61 name cleanup, #62/#63 notes and desk facts, #64, #65 dispatch-plan, #66, #67 v0.8.0 log, #68 gate.json plus `tests`, #69 pre-review plus audit workflows, #70 leak log plus STATE.md, #71 vendor text and handoff rule, #72 hygiene tool, #73 account-aware gate (off by default), #74 leak statuses, #75 v0.9.0 log. Closed unmerged: #60.

## 4. What it waits for, and from whom
- Program Owner, 2026-10-20: create one GitHub account per vendor (`docs/vendor-accounts.md`). Then: sign Claude's and Codex's `gh` in with their own accounts, give the logins to the Orchestrator, and open a tier-3 PR setting `logins`, `owner_logins`, `distinct_accounts: true`, `shared_account: false` (L1, L13). Turning on `distinct_accounts` before the accounts exist refuses every approval.
- Nothing else is blocked.

## 5. What it did not check
- Whether `po-reader-orchestrator` or the SmarterForge session is alive; whether any project upgraded past `v0.7.0`. No project has adopted the #59 clone fallback (L14) or v0.9.0.
- The audit workflow's issue creation (needs a real bypass of `main`); `distinct_accounts` against a real PR with separate accounts.
- Review depth: Codex's rounds 2 and 3 on small PRs were one short paragraph each, and its later texts did not name the earlier findings.
- Token and usage numbers: not measured this session.

## 6. Decisions not written elsewhere
Tier-1 (docs, leak log, STATE.md) needs the Program Owner's `Approved at` line; tier-2 needs a signed `go`, a cross-vendor approval and that line; tier-3 is the same, reached by protected path. The first name stays in 10 frozen dated files (`exempt_files` in `.orchestration/hygiene.json`) and in git history; history is not rewritten because it would break every pinned tag. Branch prefixes `claude/` and `codex/` are required for the gate's author rule.

## 7. Rules learned this session (each cites its leak row)
- A flag that cannot fail a run is not a gate: `python -W error::ResourceWarning` exits 0 (L12). Grep stderr instead.
- Gate `body_headings` are bare names, the gate adds the `#` itself (L11).
- The author never signs a review of its own commit, including a conflict fix it pushed (L13).
- Never switch branches in the shared folder; work in your own worktree (L6).
- A relayed review is built by one script that refuses an empty finding, then checked after posting (L16).
- `codex review` takes no custom prompt with `--base`; its output has no verdict line and is UTF-16 through PowerShell 5.1 `Tee-Object` (L15, now in `vendors/codex.md`).
- L? new: in this harness, files containing backslash escapes are written with the Write tool, never shell heredocs or inline Python (three failures: mangled `\n`, a broken regex, a broken `sed`).

## 8. Usage
Not measured this session.

## 9. Next three actions
1. Sweep (`STATE.md`), then ask the Program Owner whether the accounts exist; if yes, open the tier-3 PR for L1 and L13 and relay a Codex review.
2. Re-check liveness of the project orchestrators and issue #52; offer each project the `v0.9.0` upgrade by its own PR.
3. Commit the relay builder as a small tool (L16) and add the harness rule from section 7 to the leak log as a new row.

## FINAL UPDATE
Superseded the same day by `handoff-framework-orchestrator-2026-10-20-2.md`, which you must read instead. (A name sort puts `-2026-10-20-2.md` before `-2026-10-20.md`, so "newest by name" picks this file; pick by git log date.)
