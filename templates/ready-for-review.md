# Ready for review
The Orchestrator sends a PR to the other vendor only when every line holds, checked from the repo host and files, not from the builder's report. A missing line goes back to the builder. Why: when the first review is a PR's first real test, each round finds one more instance of a class (7 to 9 rounds on the worst PRs).

1. **Scope fence.** Only the files and rules the card names; extras listed under "suggestions". A fix to a finding fixes its class and nothing wider.
2. **Class list with sweeps.** The defect classes reviewers should probe (code: every input, its governing grammar, the platform; docs: every claim with a condition, pin, label or number), each with its generator, the sweep command and its output (instances fixed, or "none"). PROPOSED: alias-type classes carry one probe per alias kind.
3. **Bypass-first tests** for every safety rule: fail on the old code, pass on the new, including missing, partial, malformed, near-valid, renamed and wrong-platform inputs.
4. **Claims ledger** for text that states behaviour: claim / exact condition / exception / pinned line / state-ledger row.
5. **Mechanical checks run and pasted:** the repo's tests, the secret scan, link and diagram checks for docs, the app's free demo start when the change can affect it.
6. **Process gates at opening:** branch name carries the author's vendor prefix (an integration branch cannot be a PR head); body has `## Plan`, `## Evidence`, `## Cost`; Tier 2 and 3 have a signed plan `go` ON THIS PR; the plan names who runs the merge (the author's vendor); `<gate> merge <PR> --as "<Role · Vendor>" --dry-run` output where only the review and owner rules may still fail; CI green or the failing job is a recorded flake.
7. **After a squash landing on the base (PROPOSED):** diff the head against the new base and list every base line the PR removes.
8. **Description:** plan style (what, why, risk), the evidence above, the plain-language summary section.
