# Tiers and approvals
Generalised from the first project's roles file. A project declares the paths and names in its `gate.json` (`adapters/README.md`); the rules below are what the gate enforces with them.

## Tiers
Every PR carries exactly one tier label. The gate raises a label that is too low (by path) and never lowers one.

| Tier | Covers | Plan go | Approval | Program Owner line | Process |
| --- | --- | --- | --- | --- | --- |
| 1 | Only docs folders and the readme | no | none | no | one PR, light check by the Orchestrator, merge on green CI; docs that state safety, spend or key behaviour get one cross-vendor round |
| 2 | Code, tests, configuration | yes, signed, on the PR | one, from the other vendor, at the exact head | no | full review protocol |
| 3 | Money and trust: the protected paths (instruction and roles files, CI and hooks, the gate, paid-call code, migrations, scripts) | yes, signed, on the PR | one, from the other vendor | yes, `Approved at <full sha>`, typed by the owner; no agent ever writes it | full protocol, even for "just docs" |
| 4 | Billing, spend limits, credentials, production, deleting data | not a PR | not a PR | humans only | outside the agents |

**Single-vendor projects:** "from the other vendor" above assumes two or more vendors, today's default. A project running exactly one vendor also needs the Program Owner's line at Tier 2, not only Tier 3 - see `adapters/README.md`'s "How many vendors".

## How a change moves
Card → draft PR with `## Plan` only → signed `go` on this PR → build → `## Evidence` and `## Cost`, ready-for-review → reviewer's `Approved at <full sha>` → owner's line on Tier 3 → merge by the author's vendor through the gate → handoff note; the Orchestrator updates the state file and decision log.

## Signals the gate reads
Each comment starts with `**<Role> · <Vendor>:**`; the first words after it are the signal: `go`, `Approved at <full sha>`, `Not approved at <full sha>`, `hold` (anyone), `unhold` (owner only). No other comment starts with these words. Write comment files without a byte-order mark.

## Merge rules
- **The author's vendor merges** its own PRs; the vendor comes from the branch prefix (declared per vendor). An integration branch cannot be a PR head.
- **The gate is the single merge path**: never the host's merge button, the host CLI's merge command, or a push to main. The gate merges only the head it checked and writes a record line into the merge commit; a CI workflow opens an issue for any commit on main without that line.
- **One merge at a time** (R13): announce, merge, confirm, wait for main CI. Pull the checkout that runs the gate first, so it runs the current gate.
- **Known limits**: the gate pins the head, not the base, so base and head are not checked atomically; on a shared account it cannot prove who wrote a comment. The owner's `hold`, the record line and the audit are the backstop; branch protection, where the plan allows it, is a second check.

## What a project's gate.json must declare
1. Tier by path: the docs-only paths (Tier 1) and the protected paths (Tier 3).
2. Approvals required per tier, and that they must come from a vendor other than the author's.
3. Vendors and their branch prefixes; which prefixes may not be PR heads.
4. Signature names the gate accepts, per role and vendor, and the owner's signature (during migration: a map from old signatures to `Role · Vendor`, F2).
5. Who may merge: the author's vendor.
6. Required checks (CI jobs, secret scan) and the required PR body headings (`## Plan`, `## Evidence`, `## Cost`).
7. Hold and unhold rules.
The schema and its tests ship with the gate tool (F2); this list is the requirement, not the schema.
