# Codex capability profile
Confirmed on Carlos's desk, 2026-10-14 (Windows, `@openai/codex` npm package, codex-cli 0.162.1), by a live smoke test, not from `--help` text alone. F7 pulled forward because it unblocks the automated handoff design (`templates/vendor-as-subagent.md`).

## Install and auth
- CLI: `npm install -g @openai/codex`. Verify the real package first (`npm view @openai/codex description homepage`) before trusting a name from memory; there are similarly-named decoys.
- Auth on this desk: shared with the Codex desktop app (`~/.codex/auth.json`, `stored ChatGPT tokens: true`). No separate API key was needed here; a different desk may need its own `codex login`.

## Preflight, every time, before dispatching
`codex doctor --summary` must report `0 fail`. Confirmed failure mode on this desk: `CODEX_HOME` and the worktree need real headroom (warn under 5 GiB free, fail under 1 GiB) - a near-full system drive fails this outright. Do not dispatch on a failing doctor result; surface it instead (same rule as a failing doctor in `skills/create-verification-skill`).

## Non-interactive build dispatch
```
codex exec [PROMPT] -C <working dir> -s <read-only|workspace-write|danger-full-access> --output-last-message <file> --json --skip-git-repo-check
```
- `-s workspace-write` scoped to the task's own worktree is the default for a Build Engineer task; never `danger-full-access` from an automated dispatch.
- `--json` streams JSONL events; the final `turn.completed` event carries real per-call usage: `{input_tokens, cached_input_tokens, output_tokens, reasoning_output_tokens}`. This is a real data source for R14 (usage-ceiling tracking) - not wired into a ledger yet, but no longer just advice-shaped; the numbers exist and are cheap to capture (append one line per dispatch).
- `--output-last-message <file>` is the simplest way to capture the agent's final reply without parsing the full JSONL stream.

## Non-interactive review (R21, the other vendor reviews)
```
codex review --base <branch>
codex review --commit <sha>
```
Runs a code review directly against the repo, no human relay needed. Confirmed to exist and documented in `--help`; not yet smoke-tested the way `exec` was - trial this before relying on its output shape for a real gate decision.

## Smoke test, 2026-10-14
`codex exec --skip-git-repo-check --sandbox read-only --output-last-message last.txt --json "Reply with exactly the single word OK and nothing else."` returned `OK` in both the JSONL stream and `last.txt`, with a real usage block. Proves: non-interactive execution works, auth works without extra setup, `--output-last-message` writes correctly, `--json` reports real token counts.

## Known failure on this desk, confirmed reproducible (2026-10-14)
Direct shell command execution fails 100% of the time (2/2 attempts, a trivial file write and a bare `git --version`), both with the same error: `Failed to create unified exec process: helper_unknown_error: setup refresh had errors`. The file-write task still completed because Codex had an MCP server (`node_repl`) available as a fallback and routed around the shell entirely; `git --version` had no such fallback and returned empty stdout. **Any real task needing an actual shell command (tests, git, a build step, a package manager) will hit this wall with no workaround.** `codex doctor` already named a likely cause: Microsoft Defender exclusions for Codex are unverified on this desk (signed Codex app, `codex.exe`, `codex-windows-sandbox-setup.exe`, `codex-command-runner.exe`, `codex-code-mode-host.exe`); the sandbox backend is also reported as `elevated`. Not yet fixed or root-caused - do not treat the automated dispatch path as ready for a real coding task until this clears.

## Not yet confirmed
- Whether `codex review`'s output is structured enough to feed directly into this framework's finding format (`docs/convergence-loop.md`'s finding record) or needs a parsing step.
- Behavior on a desk without an existing desktop-app login (whether `codex login` is interactive-only or scriptable).
- Multi-desk or CI use (this was confirmed on one interactive desktop session only).
