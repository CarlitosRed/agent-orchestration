# F1 extraction report (Platform Engineer, 2026-10-13)
Milestone F1: copy the reusable core out of the first project's working notes. Sources were read only; nothing in them was changed. Not committed (the Orchestrator commits).

## Extracted
| Framework file | From |
| --- | --- |
| `rules/README.md` (24 rules with enforcer and status, "promote next") | the 21 context rules, plus four rules from the project's roles file |
| `rules/leak-classes.md` (11 classes, all 41 leaks assigned) | the process-leaks log |
| `templates/` (11 files) | the project's 11 templates, generalised to roles and placeholders |
| `docs/review-protocol.md` | rule 19, ready-for-review, the two review templates, framework map section 4 |
| `docs/tiers-and-approvals.md` | the project's roles file, rule 17, rule 20 |
| `docs/leak-log-format.md`, `docs/cost-ledger-format.md`, `docs/decision-log-format.md` | the leak log, the cost ledger, the decision log, ideas register I-004 |
| `docs/checkpoint-and-handoff.md` | rules 9 and 10, the handoff and resume files |
| `docs/orchestrator-playbook.md` | rules 7, 11, 17, 18; handoff "merge rules learned"; desk gotchas on writes |

## Left in the project on purpose
- Desk facts: interpreter launcher, database binaries and ports, browser-test gap, the known socket flake, the reception checkout, network retries (adapter `desk.md`).
- The protected-path list, gate file names and commands, the gate's seven-character sha rule, branch prefixes per vendor (adapter `gate.json`).
- Product rules from the project's instruction file; customer-data and test-data locations; spend facts and plan prices.
- All PR, task and leak specifics (heads, rounds per PR, named accounts, artifact links, the people outside the team).
- Usage ceiling numbers and the temporary one-day exception (adapter `roles.md`).
- Per-vendor prompting details: tag style, effort scales, model names, the model-swap bug, rejected-prompt issues (go to `vendors/` in F7).
- The owner's personal style file path; only the pattern is in the playbook.

## Unsure
1. "Enforced" status means the reference project's gate, not a framework tool; nothing is framework-enforced until F2 ships and a project pins it.
2. Who posts the Tier 2 plan go: the roles file says the reviewer; later prompts and leak L31 say the owner. Templates leave it as a placeholder.
3. The owner's signature in a generic gate (`**Program Owner:**` or a project-declared name) is left to F2.
4. Whether the visuals rule (R6) is a framework rule or an owner preference; kept as advice pointing to the owner's style file.
5. Leak L41 has no status and L30 is a meta row; both were classed by their content.
6. Dual-vendor round 1, class records, the controller and patch-id approvals are marked PROPOSED; the ready-for-review squash-landing line and the alias-probe line come from open leaks and are also marked PROPOSED.

## Contradictory or obsolete in the sources
1. **Launch ceilings.** Rule 18 says 80 percent five-hour and weekly (raised 2026-10-13), then a one-day 70 percent exception "returning to 40", weekly "stays 75"; the vendor-subagent template and the resume prompt say 40 and 75. Three numbers for one limit. The framework keeps only "declared in the adapter".
2. **Who may write the cost ledger.** Rule 7 says only the Orchestrator writes task files; the cost ledger says the Orchestrator or the clerk may append; the clerk template says the clerk writes only the status file. The playbook picks "Orchestrator or clerk, append only"; the project should settle it.
3. **Which vendor gets builds.** The subagent-vs-chat rules say one vendor's budget is "for reviews"; rule 18 moves builds to that same vendor because it has budget. Obsolete line; the framework makes it an adapter choice.
4. **Old reviewer template.** The single-vendor reviewer template asks for "Approved at <sha>" without saying it must be the first words (the cause of L37 and L40); the short-round template was fixed. The old template is superseded by `templates/reviewer-prompt.md`.
5. **Round budget.** Rule 19 allows a round 4 after the sweep; the framework map adds that the owner then decides a scope cut. Not contradictory, but rule 19 has no end; recorded as PROPOSED in the protocol.
6. **Leak log rows.** L5 and L6 share one physical line in the source table, and L41 has six cells instead of seven; the source log needs a format fix.
7. **Stale instruction line** (L16) about the project's active scope stays open in the source; it is project-only.
