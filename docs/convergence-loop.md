# The convergence loop
How a PR's review rounds converge instead of chasing one instance per round. Generalises `docs/framework-map.md` section 4; the tool is `tools/class-ledger/ledger.py`. Each part is marked **TODAY** (a template or the gate already does it), **LEDGER** (the ledger tool refuses the wrong action) or **PROPOSED** (a design choice not yet measured on a real PR; what to measure is at the end).

## Why
On the worst PRs each round found one more instance of the same class (`rules/leak-classes.md`, C1). The builder fixed the reported instance, not the rule that produced it, so the next round found the next member. The loop below makes the unit of work the class, makes "closed" mean "a script enumerated the whole class", and makes a late instance visible as a failed sweep instead of a fresh finding.

## Terms
- **Class.** A defect named by its **generator**: one line that enumerates the whole defect space, not one member. Good: "any unit spelling the parser accepts that is not a row of the canonical table". Bad: "`tbsp.` is accepted" (an instance), "input validation is weak" (no space to enumerate).
- **Instance.** One member of a class: file:line, a counterexample, and a command that reproduces it.
- **Sweep.** A script that enumerates the generator's space and reports every member still present. A sweep that only re-checks the reported instances is not a sweep.
- **Slug.** The class's short id in the ledger (`unit-alias`). The generator, not the slug, defines the class.

## The finding record
Every finding goes into the ledger (`add-finding`) with these fields; the reviewer's notes give them in this order.

| Field | Meaning |
| --- | --- |
| class | slug of an existing class, or a new slug |
| generator | one line, required for a new class |
| by | signature `<Role> · <Vendor>`; the vendor is read from it |
| severity | P1, P2, P3 (`templates/reviewer-prompt.md`) |
| file | `path:line` |
| counterexample | the input or text that shows the defect |
| repro | one command that reproduces it |
| new-reason | from round 2 on, for a new class: why this is not an instance of a known class |
| distinct-from | known classes the reviewer says this is NOT (only needed when the ledger flags a lookalike) |

The ledger adds round, kind (new-class, instance, duplicate, reopen) and an id.

## Sorting before each round (lead judgment, from ideas I-003)
After a reviewer returns and before the builder starts, the Orchestrator sorts every open class into one bucket (`sort`):

| Bucket | Means | Blocks approval |
| --- | --- | --- |
| Act on | the builder fixes the whole class this round | yes, if P1 or P2 |
| Consider | needs a decision; must become another bucket before the round starts | yes, if P1 or P2 |
| Noted | real but out of scope or P3; recorded, not fixed now | no |
| Dismissed | wrong, or allowed by the spec; needs a reason | no |

**LEDGER.** `new-round` refuses while any open class is unsorted or in Consider. Dismissing needs a reason. A later finding on a dismissed class is recorded and shown, never silently dropped. **PROPOSED:** a class raised by both vendors goes to Act on unless the Orchestrator writes why not.

## Round 1: exhaustive
- **TODAY.** One reviewer from the vendor that did not author the PR runs `templates/reviewer-prompt.md`: every class, every instance, in one pass.
- **PROPOSED: dual-vendor parallel round 1.** Two reviewers from different vendors start on the same head at the same time (`templates/reviewer-prompt-round1-parallel.md`) and do not see each other's work. The Orchestrator merges their lists (`templates/findings-merge.md`): a class both raised is top priority; a class one raised is normal priority; an explicit contradiction is a disagreement the Orchestrator resolves before sorting. The approval still comes only from the vendor that did not author the PR; the author's vendor is an extra opinion.
- **LEDGER.** The same instance raised by both in the same round counts once and records both vendors (`both_vendor_classes`). Two reviewer slugs for one class are joined with `merge-classes` (with a reason).

## Closing a class
A class is closed only by a script-provable sweep, never by "fixed" in a comment. The closer posts:
1. the sweep command, which enumerates the generator's whole space (not the reported instances);
2. its output: members checked, members still present (must be 0), and a test that is red on the old head and green on the new one;
3. an evidence pointer (comment id, file:line, or test name and both shas).

**LEDGER.** `close-class` needs the evidence pointer and the sweep command, and hashes the sweep output file into the record so a later re-run can be compared. It cannot run the sweep or judge whether the sweep really covers the generator; the reviewer checks that in the next round.

## Round 2 and later: what a reviewer may do
Reads only the delta since the last reviewed head plus the ledger (`templates/review-round-short.md`). Exactly three things:
1. **Verify closed classes with a DIFFERENT generator.** Re-sweep each class closed since the last round with a vocabulary or enumeration the builder did not use (another word list, the spec's own table, mutations of the reported inputs). Clean: `verify-class`. **LEDGER** refuses a generator identical to the one the class was closed with.
2. **Report instances of known classes under that class.** An instance of a CLOSED class is a **reopen**: it counts against the builder's sweep, not as new scope. **LEDGER** marks it, counts it, and never lets it become a new class by default.
3. **Raise genuinely new classes**, each with a new-reason. **LEDGER** refuses a new class whose generator looks like a known class's generator or whose location already holds a known instance, unless the reviewer names that class in `distinct-from`; every class opened after round 1 is listed in the report for the Orchestrator to confirm.

Nothing else: no re-review of unchanged code for fresh opinions, no widening (R18).

## Reopen, budget and escalation (rule R17)
R17 (the first project's source rule 19): budget 3 rounds; at round 3 without approval, stop, send one whole-class sweep to a different agent, then one final round. Made precise here:
- **Trigger 1, reopen (LEDGER).** A class becomes `reopened` the moment an instance is filed on it after it was closed. That is proof the closer's sweep did not cover the generator. From then on only a signature that has never closed that class may close it (a different agent's whole-class sweep). A second reopen needs a third agent. The trigger does not wait for round 3.
- **Trigger 2, budget (LEDGER).** Rounds 1 to `budget` (default 3) start freely. Round `budget + 1` is the final round and starts only with `--escalation-sweep <pointer>` (the different agent's sweep of every open class). Any round after that needs `--owner-decision <pointer>`: the Program Owner's scope cut, not another review round.

## Exit
**LEDGER** computes `exit_ready`: no open or reopened P1 or P2 class in Act on, Consider or unsorted, and the current round added no new class and no reopen. The approval itself is still the reviewer's signed `Approved at <full sha>`, checked by the gate; the ledger only says whether the loop has converged.

## Metrics
`report` gives, per PR: rounds, classes opened / closed / open / dismissed / merged, instances per class, per-round counts (new classes, instances, duplicates, reopens), reopen count and which classes, classes raised by both vendors, bucket counts, classes needing a different agent, classes opened after round 1. Cost (tokens, money) stays in the cost ledger (`docs/cost-ledger-format.md`); the Orchestrator copies the report's key numbers into the decision log row when the PR closes.

## What must be measured before the PROPOSED parts become rules
Run the loop on two or three PRs of the instance-chasing shape (the first project had two that cost 3 to 4 rounds each on one class: see `docs/framework-map.md` section 4) and compare with that history:
1. **Rounds to approval** per PR, before vs after. Target: at most 2 for a PR of that shape.
2. **Reopens per PR.** A reopen that still happens means the sweep requirement is not biting; zero reopens with many rounds means the problem was elsewhere.
3. **Dual-vendor round 1:** classes found in round 1 by each vendor alone and by both; classes first found in round 2 or later; total review tokens and money vs a serial round 1. Adopt only if later-round classes drop more than the extra round-1 cost.
4. **Lookalike check:** how often it refuses, and how often the Orchestrator overturns it (false positives) or catches a renamed class it let through (false negatives). Tune `SIMILARITY_THRESHOLD` from that.
5. **Escalation:** rounds after a different-agent sweep; whether the final round ever needed an owner decision.

## Commands
```
python tools/class-ledger/ledger.py init       pr-12.json --pr 12 --budget 3 --head <sha>
python tools/class-ledger/ledger.py add-finding pr-12.json --class <slug> --by "<Role> · <Vendor>" --severity P2 \
       --file <path:line> --counterexample "<text>" --repro "<cmd>" [--generator "<one line>"] [--new-reason "<why>"]
python tools/class-ledger/ledger.py sort        pr-12.json <slug> --bucket act|consider|noted|dismissed --by "<sig>" [--reason "<why>"]
python tools/class-ledger/ledger.py close-class pr-12.json <slug> --by "<sig>" --evidence "<pointer>" --sweep-cmd "<cmd>" [--sweep-output <file>]
python tools/class-ledger/ledger.py new-round   pr-12.json --head <sha> [--escalation-sweep <pointer>] [--owner-decision <pointer>]
python tools/class-ledger/ledger.py verify-class pr-12.json <slug> --by "<sig>" --generator-used "<different line>" --evidence "<pointer>"
python tools/class-ledger/ledger.py merge-classes pr-12.json <src> --into <dst> --by "<sig>" --reason "<why>"
python tools/class-ledger/ledger.py status|report pr-12.json [--json]
```
Exit 0 done, 1 refused by a rule (nothing written), 2 usage or file error. One JSON file per PR, sorted keys, LF endings: commit it in the project if you want the audit trail. Who writes it: the Orchestrator (R5, one writer per file); reviewers and builders give the fields in their notes. Worked example: `docs/convergence-loop-worked-example.md`. Tests: `python -m unittest discover -s tools/class-ledger -p "test_ledger.py" -v`.
