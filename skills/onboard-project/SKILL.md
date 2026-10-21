---
name: onboard-project
description: Scaffold a brand-new project onto the framework when the Program Owner says "launch a new project" - create its .orchestration/ adapter skeleton pinned to the current framework tag, plus a resume prompt for its own Project Orchestrator chat. Does not fill in the project's brief, tests, or product code; that handoff happens in the new chat, not here. Use only when starting a project that does not exist yet.
---

# Onboard a new project

The Framework Orchestrator's end of a new-project request (`docs/multi-orchestrator-model.md`). Builds the empty building; the Program Owner moves in and tells the new Project Orchestrator what to build.

## Ground rules
- **Creates a new repo only.** Never edits `agent-orchestration` beyond reading its own templates and tag, and never touches an existing project's repo.
- **Ask only what cannot be derived**: the project's name/slug and where it lives locally. Never ask for the project's brief, goals, or tech stack - those are explicitly out of scope here; they belong to the new chat's own intake conversation with the Program Owner.
- **Creating a remote (GitHub, private or public) is an outward-facing action.** Ask the Program Owner whether to create it now or leave the repo local-only until they're ready to push.
- **Everything product-specific in the generated adapter files is `TODO` or `UNKNOWN`**, with a pointer to `adapters/README.md` for what's needed and who fills it in (the new Project Orchestrator and its own Build Engineers, once there is real code to describe).
- **Pin the current framework tag at creation time**; never guess a future one.

## Steps
1. **Confirm slug and path.** Ask for the project's short slug (lowercase, hyphens) and the local directory it should live in (default: a sibling of this repo's own parent directory). Ask about the remote per the ground rule above.
2. **Initialize.** `git init` the new directory. Write `README.md`: one paragraph naming the project, that it runs on the `agent-orchestration` framework pinned at `<tag>`, and a link to the framework repo.
3. **Write `.orchestration/`** (shape from `adapters/README.md`):
   - `framework.pin`: two lines, `repo: <framework repo URL>` then `tag: <current tag>` (`adapters/README.md`). This repo URL is also the handoff bus's address (`skills/handoff`); do not shorten it to the tag alone.
   - `gate.json`: a comment-only stub pointing at `tools/gate/gate.schema.md`; no real config until there is a codebase and tiers to set.
   - `desk.md`, `commands.md`, `roles.md`: each a one-line `TODO` naming who fills it in and when (a Platform Engineer sets up the desk; commands exist once there's code; roles are picked at setup).
   - `leaks.md`: the leak log's header row only, empty, same shape the Framework Orchestrator already reads from other projects.
4. **Write the project's own `AGENTS.md`**, adapted from this repo's: branch-and-PR discipline, who approves what, framework-pinned, pointing at its own `.orchestration/` for specifics. Keep the "Work silently on a task" line from this repo's `AGENTS.md` word for word (R29).
5. **Write the resume prompt** at the new repo's root, `RESUME-<slug>-orchestrator.md`, modeled on `RESUME-framework-orchestrator.md` but for the Project Orchestrator role: read `README.md`, `AGENTS.md`, every `.orchestration/` file, and the framework repo's `skills/handoff/SKILL.md`, in that order; declare itself the Project Orchestrator for `<slug>`, framework-pinned at `<tag>`; sweep (check the handoff inbox - `gh issue list --repo <framework repo> --label handoff --label "to:<slug>" --state open` - then `git log`, `git status`, expecting nothing yet on a brand-new repo); then **stop and ask the Program Owner for the project's brief** before doing anything else, since nothing about the project's purpose is known yet.
6. **One commit**, directly on this new repo's own default branch. There is no reviewer or gate to route through yet; this is the repo's first commit, the same shape as F0 was for the first two projects.
7. **Report**: the path, the resume-prompt filename, and that the next step is a fresh chat rooted there, opened with that resume prompt, where the Program Owner hands over the actual brief. Also list what must happen before the project's first governed PR, since this skill stops short of it: replace the `gate.json` stub with a real config, copy `templates/gate-pre-review.yml` and `templates/gate-audit.yml` from the pinned tag into `.github/workflows/`, and see each run once (`adapters/README.md`).
