# Vendor-neutral orchestrator handoff (designed 2026-10-14, not yet used for real)
Replaces the earlier sketch in this file. Carlos: use GitHub itself as the channel, not a product-specific session feature, and keep token cost near zero on both ends.

## The mechanism: GitHub issues on the framework repo, as the shared bus
Not a pull request - a PR means a code change under review; a handoff is a note, and an issue is the right weight for that. Every project already needs the framework repo's URL to read its pinned tag, so there is no new discovery problem: the framework repo's Issues tab is the one place every orchestrator, of any vendor, already knows to look.

**Labels** (on issues in the framework repo):
- `handoff` - marks it as a cross-orchestrator message, not a bug or an idea.
- `to:<slug>` - required on every handoff issue, the one exact recipient (a project's slug, or `framework` for the Framework Orchestrator itself). `gh issue list --label` matches exact labels, not patterns, so this is what every sweep filters on; there is exactly one per issue.
- `from:<slug>` - optional, the sender, for anyone reading the list to see who sent what. Never used for filtering by itself.
- `handled` - applied, and the issue closed, once the recipient has acted on it. A closed, handled issue is never re-read.

**Body**: the same signature line this framework already uses everywhere else (`**<Role> · <Vendor>:**`, `docs/roles-and-names.md`), then one short, self-contained message - a pointer (a tag, a file, a PR number), not a restatement of context the reader can look up itself. This is R3 (context economy) applied to the channel itself.

## Protocol
**Writing** (either direction):
```
gh issue create --repo <framework-repo> --title "<short title>" --label handoff,to:<recipient-slug>,from:<sender-slug> --body "**<Role> · <Vendor>:** <one short, pointer-shaped message>"
```
**Checking** (step 0 of every orchestrator's own sweep, before anything else). Note: `gh issue list --label` needs the flag repeated per label, not comma-joined - comma-joined silently returns empty (confirmed by running it, 2026-10-14):
```
gh issue list --repo <framework-repo> --label handoff --label "to:<my-slug>" --state open --json number,title,url
```
One small call. Empty result, near-zero tokens, move on. A non-empty result is opened (`gh issue view <number>`), acted on, then closed with the `handled` label so it never resurfaces:
```
gh issue edit <number> --add-label handled && gh issue comment <number> --body "**<Role> · <Vendor>:** done, see <pointer>" && gh issue close <number> --reason completed
```
A reply that needs its own follow-up stays on the same thread (`gh issue comment`); an unprompted status update going the other direction is a new issue with its own `to:<recipient-slug>`, not a reply.

## Why this instead of the file-inbox sketch
A committed file needs a push on one side and a pull on the other before it is visible; an issue is visible the instant it is created, from any machine, with no commit to make or merge to resolve. Closed-vs-open is a free "handled" flag GitHub already tracks; the file sketch had to invent an `inbox/read/` folder to get the same property. Nothing here depends on a specific product's session or messaging feature - `gh` is the only dependency, and it is already how this framework does everything else (PRs, the gate, the decisions log).

## Token efficiency, by design
- Listing costs a small JSON response, no issue bodies fetched unless one is actually opened.
- Closing immediately after handling keeps the open list - and therefore every future sweep's read - small.
- Each message is a pointer, never a re-explanation; a reader who needs more follows the pointer into the repo itself, the same discipline R3 already asks of subagent prompts.
- No transcript sharing, no re-stating what changed - the decisions log, the leak log, and the tag itself stay the source of truth; the issue only says "look there."

## What's formalized elsewhere
- `adapters/README.md`: `framework.pin` now carries the framework repo's URL alongside the tag, so a project's own orchestrator has what it needs to check the bus without being told again.
- `skills/handoff/SKILL.md`: the concrete commands above, as a skill any vendor's orchestrator can read once.
- `RESUME-framework-orchestrator.md` and the resume prompt `skills/onboard-project` generates: sweep now includes checking the inbox.

## What's unresolved
1. Whether the framework repo is the only bus, or whether two projects ever need to talk to each other directly without routing through the framework - not needed yet; today's traffic is framework-to-project and back.
2. Rate - nothing here assumes real-time delivery; a sweep happens when a session starts or when a milestone finishes, which matches how these chats actually run (long-lived conversations, not a live service).
3. Whether `gh` itself is a safe assumption for every future vendor, or whether the protocol needs a non-`gh` fallback (the raw GitHub REST API, same labels and states) for an agent with git but no `gh` CLI.

## Status
Designed. Not yet exercised on a real cross-vendor handoff - the next real test is whichever project first checks its inbox for real, the same way the F4 trial was the first real test of the verification skill.
