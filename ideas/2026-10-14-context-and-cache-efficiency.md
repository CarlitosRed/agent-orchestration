# Keep skill bodies lazy and prompt prefixes stable (Orchestrator, 2026-10-14)
Source: Carlos watched a video (no link given) saying it's cheaper to keep a skill or tool as a name only, loaded in full only when it fires, rather than keep every skill's full body resident. No primary source to check (no link, no transcript). What I can verify instead, against mechanisms already running in this session rather than the video: this session's own deferred-tool list works exactly this way (a bare name until `ToolSearch` loads its schema), and Anthropic's documented prompt caching requires an identical prefix up to a cache breakpoint to hit the cache at all - a changed or reordered "stable" block anywhere before the breakpoint misses the cache for every token after it. The general principle is sound and independently confirmable; the video's specific framing is unverified.

## Take
1. **Skill frontmatter is the only part that should stay cheap to keep resident.** This repo's own `skills/*/SKILL.md` already split `name` + `description` from the body, matching how the skill gets indexed versus loaded. Make it an explicit rule so authors don't let the description balloon into the body's job (R26 below).
2. **A prompt or template re-sent across a loop should keep a stable, byte-identical prefix.** A reviewer round, a task card, a Terms block shared between two skills (already required to "keep identical" between `create-verification-skill` and `maintain-verification-skill`) should put round-specific or variable content at the end, never inserted before or between the stable parts, so a provider's prompt cache can match the prefix across calls (R27 below).

## Leave
Nothing else from the video to act on; there is no other specific claim to check without a source.

## Proposed order
Both as prose rules now (R26, R27); a CI or lint enforcer is a later promotion once a real template shows the cost of getting this wrong (same "rule for rules" pattern as every other ADVICE row).
