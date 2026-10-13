# Roles and names
The framework names ROLES, not personas. Any vendor's agent can fill any role (see `vendors/`). Personal names like "Claudio" are retired here.

| Role (use this name) | What it does | Replaces (old chat names) |
| --- | --- | --- |
| Program Owner | The human. Sets goals, gives signed go and Approved lines, approves framework changes | Carlos |
| Orchestrator | Plans, routes work to roles, verifies reports from GitHub, runs the gate, keeps the state files; the only role that proposes framework changes to the Program Owner | Claudio · PM (and PM 1 to 5) |
| Platform Engineer | Machine, environment and tooling: installs, desk facts, scripts | Claudio · IT |
| Build Engineer | Implements one task card on one branch | builder helpers, Codex builders |
| Independent Reviewer | Reviews a PR it did not author, from the other vendor; read-only | Claudio · PR review, Codex · PR review |
| Release Manager | Runs the gate merge for a PR it is allowed to merge (the author's vendor) | Codex · integration, PM merges |
| Verification Engineer | Runs the app like a user and records evidence (screenshots, video, transcript) | new |
| Research Analyst | Reads sources (docs, repos, videos) and writes idea notes | Claudio · counselor, scouts |
| Operations Clerk | Mechanical chores: status tables, closing finished PRs | haiku clerk |
| Strategy Advisor | Optional stronger model consulted at plan lock, repeated failure and before done | advisor, counselor |

## Signature format (what the gate reads)
Comments are signed `**<Role> · <Vendor>:**`, for example `**Independent Reviewer · Codex:**` or `**Build Engineer · Claude:**`. The vendor in the signature drives the cross-vendor rules; the role drives who may do what. The verdict must be the first words after the signature: `Approved at <full sha>` or `Not approved at <full sha>`.

## Migration note (important)
The live PO Reader gate still matches the OLD signatures (`Claudio · PR review`, `Codex · PR review`, `Codex · integration`). Do not rename them in open PRs. The rename ships with F2 (gate as a tool with a config that maps old and new signatures), then projects switch by their own PR. Until then, new notes use the role names and mention the old signature in brackets when it matters.
