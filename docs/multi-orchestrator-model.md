# One Orchestrator chat per repo (Carlos, 2026-10-13)
The framework and each project run in SEPARATE chats, each with its own Orchestrator, rooted in its own repo. One chat does not drive two repos at once; that was a scope overreach in the chat that first built this framework (it built F0-F4 while also running PO Reader work side by side) and is being split out from here on.

## The three chats
| Chat | Rooted in | Job | May edit |
| --- | --- | --- | --- |
| Framework Orchestrator | `agent-orchestration` | Runs the F-milestones, turns leaks from any project into change proposals, tags framework versions | only this repo |
| PO Reader Orchestrator | `project-notes` (its existing working directory) / `advance-po-reader` | Runs that project on a pinned framework version: builders, reviewers, the gate, its own leak log | that project's own repo and notes |
| Career Agent HQ Orchestrator | `career-agent-hq` | Same, for that project (role already existed there as "Career PM"; same job, framework-pinned) | that project's own repo and notes |

A project Orchestrator never edits the framework repo. It logs a leak or a wish in its OWN leak log; the Framework Orchestrator reads project leak logs (read-only) when deciding what to extract or fix next, and only the Program Owner approves the resulting change (`docs/change-proposals.md`).

## How they talk
- **Framework down to projects:** a tagged framework version (`framework.pin` in the project's `.orchestration/` folder, see `adapters/README.md`). A project upgrades by its own PR, on its own schedule.
- **Projects up to framework:** leaks and friction, written in the project's own leak log, with evidence. The Framework Orchestrator reads them, not the other way around; it does not reach into a project to fix product code.
- **Program Owner across chats:** carries context between chats by eye (reading one chat's state file before opening another) or by pasting a short status. No chat auto-reads another's transcript.

## Starting a chat
Each repo keeps its own resume prompt at its root (or in `project-notes` for the PO Reader chat, matching its existing pattern) so a fresh chat picks up instantly: `RESUME-framework-orchestrator.md` here, and each project's own resume file in its own tree.

## Today's handoff (2026-10-13)
The chat that built F0-F4 keeps finishing the PO Reader work already in flight (two helpers running) because abandoning running work mid-flight is worse than the scope mix-up. Once that in-flight work lands, that chat continues ONLY as the PO Reader Orchestrator. A fresh chat, rooted in `agent-orchestration` with `RESUME-framework-orchestrator.md`, becomes the Framework Orchestrator from F5 onward.
