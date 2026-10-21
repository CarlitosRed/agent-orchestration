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
#87 gate opt-in (tier 3) · #88 L1/L13 fixed · #89 and #95 account how-to · #90 nine decisions rows shortened · #91 `doc-refs` hygiene check · #92 relay `--as-account` · #93 gate owner-line failure says what it saw · #94 first real Codex build run, L29. Codex reviewed #87, #88, #91, #92, #93 and #94 and found no defects in any; it did not exercise real posting or accounts itself (it said so).

## Not done, and why
- Offering `v0.9.2` to the projects: the Program Owner deferred it until the architecture is solid. No project has adopted `v0.8.0` or later (not re-checked).
- A `codex/` branch PR has not been tried. It must be opened by the Codex account or the Claude review counts as not independent (`distinct_accounts`).
- Codex cannot run Python inside its `workspace-write` sandbox; the Orchestrator or CI runs the tests of any Codex build.
- Worktrees not ours or not removed: the shared folder on `checkpoint-2026-10-19`, `workflow-templates`, `framework-orchestrator-662617`, and one under `advance-po-reader`. Re-run `git worktree list` before trusting this (L6).
- Merged remote branches are not deleted.

## Next three actions
1. Sweep (`STATE.md`), then ask the Program Owner what is next; nothing is queued behind an approval.
2. Try one Codex-authored PR end to end (Codex account opens it, Claude reviews, same gate) to prove the other direction.
3. When the Program Owner says so: offer `v0.9.2` to each project by its own PR.

## Rules learned (each cites its leak row)
- Close stdin when launching `codex exec` from a tool shell (L29).
- Files with backslash escapes go through the Write or Edit tool, not a shell heredoc (L18; hit again today in a test file).
- A gate "needs the owner's comment" failure now says what it saw (#93); if it still says nothing useful, list the PR's comments with their authors first.
- Usage: not measured this session.
