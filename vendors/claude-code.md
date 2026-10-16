# Claude Code capability profile
Confirmed on the Program Owner's desk, 2026-10-15 (Windows, `@anthropic-ai/claude-code` npm package, CLI v2.1.300). Install and CLI surface confirmed directly; live dispatch NOT confirmed - this desk's standalone CLI has no auth configured (below), unlike `vendors/codex.md`'s Codex install which shared the desktop app's login automatically.

**Naming note**: this file is deliberately not `vendors/claude.md`. On a case-insensitive filesystem (Windows, default macOS) that collides with `CLAUDE.md`, which Claude Code auto-loads as project instructions - a vendor capability profile would silently become an instructions file for every session touching this repo. Caught while writing this very file (a system reminder surfaced it back as `vendors/CLAUDE.md`). Never name a file in `vendors/` (or anywhere else in this repo) `claude.md`, any case.

## Install and auth
- CLI: `npm install -g @anthropic-ai/claude-code`. Verify the real package first (`npm view @anthropic-ai/claude-code description homepage`) before trusting a name from memory, same discipline as any other install.
- `claude doctor` confirms a clean install ("No installation issues found") but reports **not signed in to claude.ai** on this desk - unlike Codex, this CLI did not inherit credentials from anything already logged in. Signing in (`claude auth login`, an interactive OAuth flow, or an `ANTHROPIC_API_KEY`) is the Program Owner's own action; not done here, same boundary as not touching Windows Defender settings earlier - this is a real account login, not a local test app.

## Preflight, every time, before dispatching
`claude doctor` - confirm "No installation issues found" and that auth is actually configured (this desk fails that second part today). Not yet smoke-tested end to end because of the auth gap; do not treat the automated path as proven on this desk until a real dispatch succeeds.

## Non-interactive dispatch
```
claude -p "<prompt>" --output-format json --permission-mode <acceptEdits|bypassPermissions|dontAsk|...> [--session-id <uuid>] [--add-dir <dir>]
```
- `--output-format json` (single result) or `stream-json` (realtime) for structured capture, mirroring Codex's `--json`; plain `text` is the default.
- `--permission-mode` controls how the session handles tool-use approval without a human watching - choices are `acceptEdits`, `auto`, `bypassPermissions`, `manual`, `dontAsk`, `plan`. For an automated Build Engineer dispatch, the narrowest mode that still lets the task finish is the right default, not `bypassPermissions`, mirroring the same caution `vendors/codex.md` gives for Codex's sandbox modes.
- `--resume <session-id>` / `--session-id <uuid>`: the same persistent-session pattern `templates/vendor-as-subagent.md` already describes for Codex (a Build Engineer role kept open across tasks, not a second Orchestrator) is directly supported here too.
- `--agents <json-or-file>`: defines custom named subagents for one invocation - a way to hand this CLI a role definition (Build Engineer, Reviewer) directly as structured input, rather than only as prose in the prompt.

## Review
No equivalent of Codex's dedicated `review` subcommand was found in `--help`; a review dispatch would be a normal `-p` prompt asking for one. Not confirmed either way beyond reading the help text.

## Not yet confirmed
- Nothing has actually run end to end: no live smoke test, because this desk's CLI has no auth. Everything above is read from `--help` and `doctor`, not proven by a real call - weaker evidence than `vendors/codex.md`'s claims, which include one successful live dispatch.
- Whether this desk's Claude Code **desktop app** session (the one running right now, doing this work) and this freshly-installed standalone CLI can ever share credentials the way Codex's CLI and desktop app did - not checked.
- The exact JSON shape of `--output-format json`/`stream-json` - not seen for real.
- Whether `--permission-mode bypassPermissions` or similar has any of the sandboxing caveats Codex's `danger-full-access` carries - not investigated.

## Next step, for the Program Owner specifically
Run `claude auth login` (or set `ANTHROPIC_API_KEY`) on this desk if real Claude-to-Claude automated dispatch (not just Claude-to-Codex) is wanted; then the same kind of one-line smoke test `vendors/codex.md` describes can confirm this profile for real.
