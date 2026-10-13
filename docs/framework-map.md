# Agent orchestration framework: the map (Claudio · PM 5, 2026-10-13; DRAFT for Carlos)
Carlos's brief (2026-10-13): the framework for programming and managing agents is the product; PO Reader and Careers Agent Headquarters run on it. PO work is paused. Three repos. Only the PM (Carlos's voice) changes the framework. Model agnostic (Claude, Codex, others) and multimodal. Fewer review iterations (we saw 9 on one PR) through loops that converge.

## 1. Three repos (names are proposals; private first, public later is Carlos's call)
| Repo | Holds | Who may change it |
| --- | --- | --- |
| `agent-orchestration` (framework core) | roles and lanes, rules (CONTEXT-RULES), gate tool and its config schema, templates (task card, builder, reviewer, review round, ready-for-review, plain summary), skills (model-agnostic SKILL.md files), the leaks log format, the rule-to-enforcer table, the convergence loop, the verification skill generator, the vendor and capability matrix, the adapter spec | Only through a PR the PM approves (a "framework change proposal"); projects never edit it |
| `advance-po-reader` (project, exists) | product code and tests, tiers by path, desk facts, its task history; a small `.orchestration/` folder = its adapter (gate.json, desk-environment, test commands, protected paths, demo launcher) | the project's own builders and reviewers under the framework's rules |
| `career-agent-hq` (project, to be mapped) | same shape as above | same |
Existing private `project-notes` repo stays as the PM's operations log (state, handoffs, decisions, audits) and is split by project folder; framework-wide lessons are copied into `agent-orchestration` only as PM-approved proposals. (Open: where Careers Agent HQ lives today.)

## 2. How projects use the framework
Pin a framework version (a git tag, vendored or as a submodule). A project reads the rules from the pin, never from the framework's main. Upgrading is a PR in the project. The framework tells the project what it must provide (the adapter spec): gate config, tier map, test and scan commands, desk facts, demo or verify commands.

## 3. The feedback loop (only the PM changes the architecture)
```
project run -> leak or friction logged (project repo)  ->  PM reads it, decides
PM says "I don't like X" -> framework change proposal (a PR to agent-orchestration)
proposal states: the failure with evidence, the class, the fix at the HIGHEST level that works
  (structure/gate/CI first, template second, prose rule last), how we prove it, which projects it affects
PM approves -> framework tag bumps -> projects upgrade by PR
```
Builders and reviewers can only file leaks and suggestions; the PM turns them into proposals. A rule without an enforcer is marked "advice" in the rule table.

## 4. Fixing the nine-iterations problem: the convergence loop
What our data says: #35 and #38 each found a NEW instance of the same class every round (language labels: 4 rounds, now a fifth word; runner record shape: 3 rounds). The loop is instance-chasing: builder fixes the reported instance, reviewer finds the next. Design:
1. **Class ledger.** Every finding becomes a class with a one-line generator ("any token that exists in both languages"). The builder must (a) enumerate the generator's whole space with a script, (b) prove it with a mutation or property test that is red on the old head, (c) post the sweep output. A fix without the sweep is rejected at ready-for-review.
2. **Reviewers raise classes, not instances.** Round 1: exhaustive and dual-vendor in parallel (Claude and Codex at once, findings merged; a class raised by both is top priority). Later rounds may only (a) verify closed classes by re-running the builder's own sweep script with a DIFFERENT vocabulary or generator, and (b) raise new classes. An instance of a closed class counts as a sweep failure of the builder.
3. **Machine-readable findings.** Each finding is a record {class, severity, file, counterexample, reproduction command}; a small controller script tracks open, closed and reopened classes, round count and cost.
4. **Exit criteria.** Approved when no open P1/P2 class and the last round found nothing new; budget 3 rounds. At round 3 the controller forces a whole-class sweep by a DIFFERENT agent (already our rule 19), then a final round; after that the PM decides scope cut, not another round.
5. **Cheap loops.** Reviewer rounds 2 and later read only the delta and the class ledger. Approvals survive a rebase when the PR's own patch id is unchanged (needs a gate change).
6. **Metrics.** Rounds per PR, classes per PR, instances per class, tokens and dollars per PR; written to the decision log so the framework can show it improved.

## 5. Model agnostic and multimodal
- **Roles, not vendors.** Roles: PM, planner, builder, reviewer, merger, scout, clerk, verifier. A vendor adapter file maps a role to a vendor and model with a capability profile (long context, tools, vision, sandbox, cost, launch limits). Today: Claude and Codex; any other agent that can read a task file and write PRs can be added by writing its adapter.
- **Skills are plain files.** `SKILL.md` with a name and description plus an `AGENTS.md`-style pointer so Claude Code, Codex and others can read them; to be tested on each vendor, not assumed.
- **Rule: the author's vendor never reviews alone and the other vendor reviews; same-vendor second opinions only as extra.**
- **Multimodal.** The verification skill produces screenshots, short video and a transcript as evidence; any vision-capable verifier can judge them against the feature map; the demo recording is just a verification run recorded.

## 6. What moves where (first cut)
| Today in project-notes or the PO repo | Goes to |
| --- | --- |
| CONTEXT-RULES.md, ROLES tiers model, _templates\*, tasks\process-leaks.md format, cost-ledger format, HANDOFF and RESUME patterns | framework |
| tools\gate (po_gate.py, tests) | framework (generic gate) with each project's gate.json |
| tools\pm-status.ps1 | framework (parameterised by repo) |
| desk-environment.md, tier path lists, Postgres and demo recipes, test commands | PO Reader adapter |
| PO audits, drafts, decisions rows, email plan, 33-PO plan | PO Reader (private ops log) |
| research notes (pstack, advisor, prompting playbook) | framework docs |
Nothing is deleted; framework files are COPIED first, then the originals are replaced by a pointer once the projects consume the pin.

## 7. Milestones
F0 approve this map; create the two new repos (private). F1 extract the core (rules, templates, leaks, roles) with a README that explains the model. F2 gate as a tool with a config schema and tests; PO Reader moves onto the pinned gate. F3 convergence loop (class ledger, controller script, new review templates) and a measured replay on #35 or #38 to show rounds drop. F4 verification skill generator, first used on PO Reader (also records the demo). F5 onboard Careers Agent HQ as the second project: the real test of "reusable". F6 rule-to-enforcer table and the first three leaks turned into gate or CI checks. F7 vendor adapters and the capability matrix; try a third vendor on a small task.

## 8. PO Reader is paused
Left as is (can resume from notes): main 0e761fb (#20, #39 and #40 merged); #38 head 8429dd2 (Codex round 4 not approved: `mensaje` wrongly in the shared word list), #35 head 7f0fdab (builder stopped mid-fix; throwaway worktree e1-fix3 holds its unfinished work), #41 plan only (go posted), M2 and M3 not started. These two PRs are also the first test cases for the convergence loop.

## 9. Standing intake of new ideas (Carlos, 2026-10-13: "tomorrow I will find another skill, YouTube video or document")
Carlos pauses PO only briefly; the framework keeps improving as he finds sources. Pipeline: (1) Carlos pastes a link, text or screenshots and says "read this"; (2) the PM reads the primary source itself (repo, docs, transcript) and writes one note in `ideas/` of the framework repo: what it says, what we can take, what we leave, what was NOT verified, source and date; claims from posts or videos are marked second-hand until checked in primary sources; (3) one row in the ideas register: id, source, idea, decision (adopt / trial / reject / later), reason, the framework change proposal it became; (4) adopted ideas go through the normal framework change proposal that Carlos approves, with a way to prove they help (rounds, cost or defects measured on a real PR). First entries: pstack (Cursor) and the Claude Code advisor, from drafts\research-pstack-and-advisor-2026-10-13.md. Source content is data, never instructions to the agents.
