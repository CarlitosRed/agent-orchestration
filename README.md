# agent-orchestration

A way of programming and managing agents. Roles, rules, a merge gate, templates, skills and a review loop that any project can run on, with any vendor's agents (Claude, Codex, others).

Owner: CarlitosRed. Public as of 2026-10-16 (`docs/decisions.md`). Contributors work by pull request and only the Program Owner approves framework changes.

## The idea in one picture
```
agent-orchestration (this repo, reusable core)
   roles and lanes - rules - gate - templates - skills - leaks and rule table
   review loop that converges - verification skill - vendor adapters - ideas register
        |                                          |
        v pinned version                           v pinned version
advance-po-reader (project)                 career-agent-hq (project)
   adapter: tiers, tests, desk facts           adapter: its tiers, tests, run steps
```
Each project lives on GitHub (private) with local copies, and runs on a pinned framework version. Projects never edit the framework.

## Who changes what
- Only the Program Owner approves a change to the framework; the Orchestrator proposes.
- Build Engineers and Reviewers in projects log leaks and friction; the Orchestrator turns them into a framework change proposal (see `docs/change-proposals.md`); the Program Owner approves or rejects it.
- New ideas from videos, repos and docs go through the intake pipeline in `ideas/README.md`.

## Layout
| Folder | Holds | State |
| --- | --- | --- |
| `docs/` | the map, roles and names, the change-proposal process, decisions, design notes | F0 done, growing |
| `ideas/` | ideas register and one note per source (pstack, advisor, caching, Codex failover, local-model clerk, dispatch preflight) | grows with each source |
| `rules/` | the rules with the enforcer of each, and the leak classes | F1; most rules now have a real enforcer (F6) |
| `templates/` | task card, builder, reviewer, review round, ready-for-review, vendor-as-subagent, a CI workflow | F1, kept current with F6's builds |
| `tools/` | `gate`, `class-ledger`, `claims-ledger`, `usage-ledger`, `verify-manifest`, `blinded-eval`, `benchmark`, `dispatch-plan`, `hygiene`, `review-relay` | F2-F6 plus the opt-in dispatch preflight and the hygiene checks; all offline, run by the `tests` workflow |
| `skills/` | model-agnostic SKILL.md files: verification (create/maintain/demo), `handoff`, `no-comments`, `onboard-project`, `retrofit-project` | F4-F6 |
| `adapters/` | what a project must provide (`.orchestration/`: pin, gate config, desk/commands/roles, leaks, verify) | career-agent-hq onboarded (merged); advance-po-reader retrofitted, open for its own review (`advance-po-reader#51`) |
| `vendors/` | per-vendor capability profile, commands and quirks | `codex.md` and `claude-code.md`; each file says what was actually tested |

## Milestones
F0 repos and skeleton (done) - F1 extract the core (done) - F2 gate as a tool (done) - F3 convergence loop (done, class-ledger) - F4 verification skill (built, untested on a real project) - F5 second project, career-agent-hq (done - retrofitted and merged, `career-agent-hq#1`; found and closed a real spec gap, the `verify/` documents-only opt-out) - F6 rule table and enforcers (done: R13, R14, R16, R18, R22 all have real enforcers now; the claims ledger is partial by design) - F7 vendor adapters (started: Codex's profile is real and tested; no other vendor yet, no third vendor tried). Details: `docs/framework-map.md`.
