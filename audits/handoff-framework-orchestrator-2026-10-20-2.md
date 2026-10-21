# Handoff: Framework Orchestrator, 2026-10-20 (second checkpoint of the day, at the Program Owner's request)
One screen of facts, no prose. Newer than `handoff-framework-orchestrator-2026-10-20.md`, which it supersedes.

## 1. Read this, then...
`STATE.md` first, then README.md, AGENTS.md, docs/roles-and-names.md, docs/change-proposals.md, docs/multi-orchestrator-model.md, skills/handoff/SKILL.md, rules/README.md, `.orchestration/leaks.md`. Resume list: `RESUME-framework-orchestrator.md`. Work in a worktree of your own on a `claude/` or `codex/` branch; `git switch -c` a new branch per PR inside it.

## 2. State at checkpoint (read from the repo, not relayed)
Main `e4714e4` before this checkpoint's own PR. Newest tag `v0.9.1` on `69041fc` (annotated, pushed; precedent: a tag sits on the last functional merge, not on a log-only one). Handoff inbox for `to:framework`: empty. One open issue: #52 (`to:smarter-forge`, no reply since 2026-10-16). Required check `tests` now also runs the content scan first; `pre-review` and `gate-audit` unchanged. Merge: `python tools/gate/gate.py merge <PR> --as "Release Manager · Claude"` from a worktree of `origin/main`.

## 3. Merged this session (all through the gate; owner lines typed by the Program Owner)
| PR | Tier | What | Codex rounds |
| --- | --- | --- | --- |
| #77 | 2 | `ready-for-review` fixes, retrofit/onboard need both workflows run, `tools/review-relay` (L16, L19, L25) | 2: round 1 two P2 in the relay tool, fixed |
| #78 | 3 | workflow templates read pin and config from the base commit, rerun on label edits (L20) | 1: no findings |
| #79 | 3 | gate judges its fresh read, UTF-16 scan, content scan in `tests`, strict hygiene config, R13 wording (L21 to L24) | 2: round 1 one P2 (scan ran after PR code), fixed |
| #80 | 1 | leak rows L18 to L25, L16 fixed, deferrals recorded | none needed (tier-1) |

## 4. What it waits for, and from whom
- Program Owner, when ready: one GitHub account per vendor (only he can create them; steps in `docs/vendor-accounts.md`). Then a tier-3 PR setting `logins`, `owner_logins`, `distinct_accounts: true`, `shared_account: false` (L1, L13). Turning it on earlier refuses every approval.
- Deferred by the Program Owner (his words: wait "once we have a more solid architecture"): checking the project orchestrators and offering them `v0.9.1` by their own PR. Do not chase before he says so. Issue #52 stays open.

## 5. What it did not check
- Whether any project adopted `v0.8.0`, `v0.9.0` or `v0.9.1`; whether the project orchestrators are alive.
- The new workflow templates in a real project run (the live copies and the scan step ran green in this repo's own CI on #79; the templates themselves were proven only by extracting their shell steps into throwaway repos).
- Worktrees: the Program Owner pruned four old ones, but `git worktree list` still showed `coordination-preflight`, `pr59-adoption-guidance`, `pr60-benchmark-corrections`, `review-pr60-13cbb678`, my extra `workflow-templates`, and the shared folder on `checkpoint-2026-10-19`. Re-run `git worktree list` before trusting any of this (L6).
- Review depth: Codex's reviews of #78 and the second rounds were one short paragraph each. Token and usage numbers were not measured.

## 6. Decisions not written elsewhere
Tag `v0.9.1` was approved by the Program Owner in chat ("tag it"); its decisions row is in the PR carrying this file. The improvement list (A1 to F2) lived in a notes folder outside the repo; what is left of it is in section 9, item 3.

## 7. Rules learned this session (each cites its leak row)
- Files containing backslash escapes go through the Write or Edit tool, never a shell heredoc or inline Python (L18; hit twice more today).
- Post relayed reviews with `python tools/review-relay/relay.py post <PR> ...`: it refuses an empty finding and reads the comment back by URL (L16, fixed #77). Shorten local absolute paths in Codex's text before relaying (they contain a first name).
- A relayed verdict names the exact head; a later push needs a fresh review and fresh owner lines. The author's `go` and `Approved` lines are typed by the Program Owner with `gh pr comment`; an agent never writes them (R23).
- A hook refuses writes into any worktree other than the session's own, and the permission classifier refused `git worktree remove` and a `sleep N; ...` chain. Run slow commands with `run_in_background` (L? new, harness behaviour).
- Codex's own report said it ran shell commands and tests under `exec -s read-only` on 2026-10-20 (codex-cli 0.163.0), which contradicts `vendors/codex.md`'s "Known failure" section; not re-tested by me (L? new, a stale desk fact).
- "Newest handoff file" by name is ambiguous: `-2026-10-20-2.md` sorts before `-2026-10-20.md`. Pick the newest by commit date (`git log -1 --format=%cI -- <file>`), or name the next one with a later date (L? new).
- Cross-vendor review found a real defect in two of the three PRs it reviewed this session (L17 pattern; keep it mandatory at tier 2 and 3).

## 8. Usage
Not measured this session.

## 9. Next three actions
1. Sweep (`STATE.md`), then ask the Program Owner whether the vendor accounts exist; if yes, open the tier-3 PR for L1 and L13 and relay a Codex review.
2. Re-test whether Codex shell commands work under `exec -s read-only` on this desk, then update `vendors/codex.md` (tier-2) and add the leak row for the stale fact.
3. Remaining backlog, lowest first: trim `adapters/README.md` (stale "has neither workflow" text and mixed ideas, tier-3); a hygiene check for broken file references in docs (needs a tighter filter than the first draft, which gave mostly false hits); shorten the nine old `docs/decisions.md` rows over 600 characters; later, when the Program Owner says the architecture is solid, offer `v0.9.1` to each project by its own PR.

## FINAL UPDATE
Later on 2026-10-20 (read from the repo and run logs, not relayed):
- Main moved to `8dfcbad` with #82 (adapter spec trimmed to requirements; token text in `docs/private-framework-access.md`, dated history in `docs/adapter-history.md`). Section 9 item 3's `adapters/README.md` trim is done. Newest tag still `v0.9.1` on `69041fc`; no open PRs; inbox empty; issue #52 open.
- The four old Codex worktrees were removed by the Program Owner. Still listed: the shared folder on `checkpoint-2026-10-19`, one extra Orchestrator worktree `workflow-templates`, and one under `advance-po-reader` (not ours).
- Section 9 item 2 is done in the PR carrying this update: a probe under `-s read-only` and `-s workspace-write` ran shell commands (git ran; the file write was refused read-only and worked in workspace-write; `python` was not on Codex's PATH); `vendors/codex.md` now carries that dated status and leak row L26. A real build dispatch has still not been tried.
- Remaining: the vendor accounts (Program Owner, when ready), then the tier-3 PR for L1 and L13; a hygiene check for broken doc references; shorten nine old `docs/decisions.md` rows; offering `v0.9.1` to the projects waits for the Program Owner.

Still later on 2026-10-20 (read from the repo):
- Main is `6e9d2da` before the PR carrying this update. Merged since: #83 (`vendors/codex.md` shell status, L26), #84 (gate test fake key body, L27), #85 (rule R29: work silently on a task, carried by `AGENTS.md` and seven prompt templates, checked by `hygiene.py` `required_text`). Newest tag is still `v0.9.1`; R29 is not in a tag, so a `v0.9.2` would carry it.
- Two PRs appending to the end of `.orchestration/leaks.md` at once conflicted and voided an approval (L28): keep one open PR editing that file at a time.
- The Program Owner's standing rule (also in his global instructions): no narration while working, one final result, ask only if truly blocked. Approval lines remain his to type; stop and ask for them.
- Section 9 item 3 now reads: the vendor accounts (his), then a hygiene check for broken doc references, shortening nine old `docs/decisions.md` rows, and offering the projects the next tag by their own PRs when he says so.
