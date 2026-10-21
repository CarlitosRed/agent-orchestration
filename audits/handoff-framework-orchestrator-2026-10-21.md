# Handoff: Framework Orchestrator, 2026-10-21
Newest by date; it supersedes `handoff-framework-orchestrator-2026-10-20-2.md` and its FINAL UPDATE. Read `STATE.md` first, then `docs/vendor-accounts.md`.

## State (read from the repo and GitHub, not relayed)
- Newest tag `v0.9.2` on `d5c7e85` (annotated, pushed). Open PRs: only the one carrying this file. Open issues: none (#52 closed 2026-10-21, its ask was done on 2026-10-16). Handoff inbox for `to:framework`: empty.
- One GitHub account per vendor is ON for this repo (#87): `carlitosred-claude`, `carlitosred-codex`, owner `CarlitosRed`. Leaks L1 and L13 are fixed (#88).

## How a PR runs now (proven on #87 to #95)
1. Claude session opens the PR (Claude account), labelled by tier.
2. `codex --no-daemon review --base origin/main < /dev/null` from the PR head; then `relay.py post <PR> ... --as-account carlitosred-codex` with `RELAY_TOKEN_CONFIG_DIR` set to the default gh config folder (the Claude session has its own folder, `GH_CONFIG_DIR`).
3. The Program Owner posts `go` (tier-2 and 3) and `Approved at <full sha>` from `CarlitosRed`; check `gh api user --jq .login` first. An agent never writes these lines.
4. From a worktree detached at `origin/main`: `python tools/gate/gate.py merge <PR> --as "Release Manager · Claude"`. The user's settings allow exactly that command, so no prompt.

## Merged this session
#87 gate opt-in (tier 3) · #88 L1/L13 fixed · #89 and #95 account how-to · #90 nine decisions rows shortened · #91 `doc-refs` hygiene check · #92 relay `--as-account` · #93 gate owner-line failure says what it saw · #94 first real Codex build run, L29. Codex reviewed #87, #88, #91, #92, #93 and #94 and found no defects in any; it did not exercise real posting or accounts itself (it said so). Later the same day: #100 (Codex-authored test, first full run of that direction) and #101 (merge account check, tier 3).

## Not done, and why
- Adopting `v0.9.2`: offered on 2026-10-21 by issues #97 (po-reader, pin v0.6.0), #98 (career-hq, v0.3.0) and #99 (smarter-forge, v0.7.0); each project answers by its own PR. Nobody has replied yet (not re-checked after posting).
- The Codex-authored direction is proven once (#100: Codex builds, Codex account opens the PR, Claude reviews, owner lines, merge). The merge ran from the Claude login, which exposed that `--as` was only a label; #101 now refuses a merge unless the signed-in account belongs to the `--as` name. A Codex-branch merge therefore needs the Codex token for that command; that refusal has not been seen live yet.
- Codex cannot run Python inside its `workspace-write` sandbox; the Orchestrator or CI runs the tests of any Codex build.
- Worktrees not ours or not removed: the shared folder on `checkpoint-2026-10-19`, `workflow-templates`, `framework-orchestrator-662617`, and one under `advance-po-reader`. Re-run `git worktree list` before trusting this (L6).
- Merged remote branches are not deleted.

## Next three actions
1. Sweep (`STATE.md`), then ask the Program Owner what is next; nothing is queued behind an approval.
2. Watch #97, #98 and #99 for replies; answer each project's questions by comment and close each issue when its PR lands or it declines.
3. When the Program Owner says so: offer `v0.9.2` to each project by its own PR.

## Rules learned (each cites its leak row)
- Close stdin when launching `codex exec` from a tool shell (L29).
- Files with backslash escapes go through the Write or Edit tool, not a shell heredoc (L18; hit again today in a test file).
- A gate "needs the owner's comment" failure now says what it saw (#93); if it still says nothing useful, list the PR's comments with their authors first.
- Usage: not measured this session.

## FINAL UPDATE (checkpoint at the Program Owner's request, later on 2026-10-21)
- Main is `de5cf77` plus this PR. Merged since the sections above: #101 (gate merge account check), #102 (this handoff). The remote branch `codex/relay-whitespace-note-test` is deleted. Open issues: #97, #98, #99 (the `v0.9.2` offers); open PRs: only the one carrying this update.
- Career HQ (`career-agent-hq`, private; this account cannot read it): its `master` has no `.orchestration/` folder, and a one-commit retrofit branch pinned at `v0.3.0` was never merged (read from the local checkout only, not the remote). The Program Owner was given a paste-ready prompt for a session rooted in that repo: pin `v0.9.2`, add the R29 line to its `AGENTS.md`, keep the gate documents-only, no vendor accounts and no CI workflows (both recorded as deliberate choices), one PR, not merged by the session. Whether he has run it is not known.
- Next action unchanged: watch #97 to #99; answer by comment; close each when its PR lands or it declines.
