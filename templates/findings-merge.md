# Merging two reviewers' class lists (PROPOSED, with dual-vendor round 1)
The Orchestrator does this after both parallel round-1 reviewers (`templates/reviewer-prompt-round1-parallel.md`) have returned, and before the builder starts. Output: every class in the ledger, sorted into buckets, with a short merge note on the PR. Protocol: `docs/convergence-loop.md`.

## Steps
1. **Read both class lists from the notes**, not from the replies. Check each verdict comment against the gate dry run (only the other vendor's verdict counts).
2. **Match classes by generator, not by slug.** Two classes match when their generators enumerate the same space, or one's space contains the other's. Test: would the smallest fix of one also remove every instance of the other? If yes, they are one class.
   - Same space: one class; keep the clearer generator; list both reviewers.
   - One contains the other: one class with the WIDER generator; note it.
   - Overlapping, neither contains the other: two classes; note the overlap so the builder's sweep covers both.
3. **Enter them in the ledger** (`tools/class-ledger/ledger.py`). The first reviewer's classes with `add-finding --generator`; the second reviewer's instances of a matched class under the SAME slug (an identical instance counts once and records the second vendor). If two slugs were entered for one class by mistake: `merge-classes <src> --into <dst> --reason`.
4. **Priority.**

   | Raised by | Priority | Default bucket |
   | --- | --- | --- |
   | both vendors | top | Act on (write why if not) |
   | one vendor, P1 or P2 | normal | Act on or Consider |
   | one vendor, P3 | low | Noted, unless one line fixes it |

   `report` lists `both_vendor_classes`.
5. **Disagreements.** A disagreement is one reviewer raising a class and the other explicitly saying the opposite (in its findings or its "Explicitly not defects" list). Silence is not disagreement. For each, record the class, what each reviewer said with a pointer, and the decision. Decide from the spec, the code or a run, not from which vendor is usually right. If a run cannot settle it, the class goes to Consider and the Program Owner decides before the round starts.
6. **Sort** every open class (`sort`): Act on / Consider / Noted / Dismissed (dismissed needs a reason). Consider must be resolved before `new-round`; the ledger refuses otherwise.
7. **Post one merge note on the PR**, signed `**Orchestrator · <Vendor>:**`, with no verdict words: the class table from `ledger.py status`, the both-vendor classes, the disagreements and their decisions, the bucket of each class. The builder works from this note.

## Record for the trial
For the PROPOSED measurement, add to the decision log row: classes found by vendor A only, by B only, by both; disagreements; Orchestrator time for the merge; review tokens and money of both reviewers.
