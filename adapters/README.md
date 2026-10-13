# Project adapter spec (what a project provides to run on the framework)
Each project keeps a folder `.orchestration/` with:
- `framework.pin`: the framework version (git tag) the project runs on.
- `gate.json`: the config of `tools/gate/gate.py`, schema in `tools/gate/gate.schema.md`. Required: `schema_version`, `tiers` (label, level, approvals, plan_go, owner_approval, cross_vendor, body_headings, allowed_paths, mergeable, record), `vendors` (names, branch_prefixes), `owner_signers`, `protected_paths`, `protected_tier`, `required_checks`. Optional: `legacy_signers` (old signature names during migration), `forbidden_head_prefixes`, `body_headings`, `verdict_sha_min_length`, forbidden-file and secret lists. Who merges is fixed: the author's vendor (by branch prefix) or the owner.
- `desk.md`: facts about the machine and environment (interpreters, services, ports, known flakes).
- `commands.md`: the exact commands for tests, scan, the app launcher and the verification drive.
- `roles.md`: which vendor and model fills each role in this project and the launch limits (usage ceilings).
- `leaks.md`: the project's leak log (what went wrong, evidence, root cause, fix).
A project is "on the framework" when its gate runs from the pinned tool with this config. Status: advance-po-reader has these facts spread across `tools/gate`, `desk-environment.md`, `ROLES.md`; career-agent-hq has its own early copies of the rules. F2 and F5 move both onto this spec.
