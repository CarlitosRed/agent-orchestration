# agent-orchestration

A way of programming and managing agents. Roles, rules, a merge gate, templates, skills and a review loop that any project can run on, with any vendor's agents (Claude, Codex, others).

Owner: Carlos (CarlitosRed). Private. Even with outside contributors it stays private; contributors work by pull request and only the PM approves framework changes.

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
- Only the PM (Carlos's voice in the chat) approves a change to the framework.
- Builders and reviewers in projects log leaks and friction; the PM turns them into a framework change proposal (see `docs/change-proposals.md`) and approves or rejects it.
- New ideas from videos, repos and docs go through the intake pipeline in `ideas/README.md`.

## Layout
| Folder | Holds | State |
| --- | --- | --- |
| `docs/` | the map, the change-proposal process, decisions | F0 done |
| `ideas/` | ideas register and one note per source | started (pstack, advisor) |
| `rules/` | the rules (from CONTEXT-RULES) with the enforcer of each | F1 |
| `templates/` | task card, builder, reviewer, review round, ready-for-review | F1 |
| `tools/` | generic gate, status script, review-loop controller | F2, F3 |
| `skills/` | model-agnostic SKILL.md files (verification, review, intake) | F3, F4 |
| `adapters/` | what a project must provide (gate config, tiers, test commands) | spec started |
| `vendors/` | per-vendor adapter and capability profile (Claude, Codex, ...) | F7 |

## Milestones
F0 repos and skeleton (done) - F1 extract the core - F2 gate as a tool - F3 convergence loop - F4 verification skill - F5 second project (career-agent-hq) - F6 rule table and enforcers - F7 vendor adapters. Details: `docs/framework-map.md`.
