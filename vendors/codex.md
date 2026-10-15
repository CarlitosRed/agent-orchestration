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

## Known failure on this desk, root-caused (2026-10-14)
Direct shell command execution fails 100% of the time (5/5 attempts across this session), always the same error: `Failed to create unified exec process: helper_unknown_error: setup refresh had errors`. **This is an open upstream Codex bug on Windows, not a local misconfiguration** - `codex doctor` reports it precisely: `elevated Windows sandbox provisioning recorded a structured failure`, `sandbox backend: elevated`, `sandbox provisioning: failed`. Public, open, currently-unresolved issues on `openai/codex` describe the identical failure (checked 2026-10-14): #46380, #51811, #52041, #52735 - the common root cause across them is the sandbox setup step trying to apply ACLs to runtime binaries Codex itself is currently executing, which Windows refuses. #51006 is an open feature *request* for a supported execution-only mode that skips this provisioning entirely; it does not exist yet.

Ruled out, in order, each a real attempt not a guess: Microsoft Defender exclusions (path + 5 named processes + Controlled Folder Access, added and verified present - no change). Reinstalling the CLI (`npm install -g @openai/codex` - no change). The `code_mode_only` feature flag, hoping to force the same code-execution path that incidentally worked around this for a file-write task - no change, Codex still attempted the native shell path and failed the same way.

**Any task needing an actual shell command (tests, git, a build step, a package manager) will hit this wall with no reliable workaround**, until OpenAI ships a fix or the execution-only mode requested in #51006. A pure file-edit task may still complete if Codex happens to route it through an MCP tool instead (as the file-write smoke test did) - that is incidental agent behavior, not something to depend on. **Do not point a real coding task at this desk's Codex dispatch until this clears upstream; re-run `codex doctor` after any Codex update and look for `sandbox provisioning: failed` before trying again.**

## Not yet confirmed
- Whether `codex review`'s output is structured enough to feed directly into this framework's finding format (`docs/convergence-loop.md`'s finding record) or needs a parsing step.
- Behavior on a desk without an existing desktop-app login (whether `codex login` is interactive-only or scriptable).
- Multi-desk or CI use (this was confirmed on one interactive desktop session only).
