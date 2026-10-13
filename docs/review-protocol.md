# Review protocol
How a PR goes from "ready" to "approved" in few rounds. The precise loop (class records, reopen and escalation triggers, buckets) and its tool are in `docs/convergence-loop.md` and `tools/class-ledger/`. Each part is marked **TODAY** (practised in the first project, by template or gate) or **PROPOSED** (framework map section 4, milestone F3; to be measured on a real PR before it becomes a rule).

## Why
On the worst PRs each round found a new instance of the same class (7 to 9 rounds). The loop was instance-chasing: the builder fixed the reported instance, the reviewer found the next (`rules/leak-classes.md`, C1).

## Before round 1
- **TODAY.** The Orchestrator checks every line of `templates/ready-for-review.md` from the repo host. A missing line goes back to the builder, not to the reviewer.
- **TODAY.** The reviewer is from the vendor that did not author the PR (gate-enforced in the first project).
- **PROPOSED.** For a gate or validator PR, ask the reviewer for the list of input dimensions before the build starts (threat model first).

## Round 1: exhaustive class audit
- **TODAY.** `templates/reviewer-prompt.md`: every class, every instance, parallel read-only sub-tasks per dimension for protected-path PRs and big diffs; P1 and P2 with a counterexample and a reachable scenario; at most five process findings.
- **PROPOSED.** Dual-vendor parallel round 1 on Tier 3: both vendors review the same head at once; findings are merged and sorted Act on / Consider / Noted / Dismissed, with the vendor that raised each. A class raised by both is top priority. Measure rounds and cost against a serial round 1 before adopting. The author's vendor reviewing is an extra opinion only; the approval still comes from the other vendor.

## The class ledger
- **TODAY (template fields).** The builder fixes the class, sweeps for every instance and posts the sweep (`templates/builder-prompt.md` `<fix_rounds>`).
- **PROPOSED.** Each finding is a record {class, generator, severity, file, counterexample, reproduction command}. A controller script tracks open, closed and reopened classes, rounds and cost. A fix without the sweep output is refused at ready-for-review.

## Rounds 2 and 3
- **TODAY.** `templates/review-round-short.md`: the reviewer reads only the delta and its previous findings, marks each fixed / open / not reproducible, re-sweeps the same classes, then reports new issues.
- **PROPOSED.** A later round may raise only (a) failures of closed classes, found by re-running the builder's sweep with a different vocabulary or generator, counted as a failed builder sweep, and (b) classes that are genuinely new. Instances of a known class found late are the builder's sweep failure, not a reason to reopen scope.
- **PROPOSED.** An approval survives a rebase or a merge of main when the PR's own patch id is unchanged (needs a gate change).

## Budget and escalation
- **TODAY (advice, R17).** Budget 3 rounds. At round 3 without approval the Orchestrator stops, lists the open classes and sends one whole-class sweep to a different agent, then one final round.
- **PROPOSED.** After that final round the Program Owner decides a scope cut; there is no open-ended next round.

## Approval and exit
- **TODAY (gate).** Approval is `Approved at <full sha>` as the first words after the signature, at the current head; any later push voids it. The Orchestrator runs the gate dry run after every approval before saying it counts.
- **Exit (PROPOSED as a rule, practised informally).** Approved when no P1 or P2 class is open and the last round found nothing new.

## Metrics (PROPOSED)
Rounds per PR, classes per PR, instances per class, tokens and money per PR, written to the decision log so the framework can show it improved.
