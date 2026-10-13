# Framework change proposals
Only the PM approves a change to the framework.

1. A project run produces a leak or friction (logged in the project, with evidence).
2. The PM decides to act and says what they dislike, in their own words.
3. A proposal PR is opened here. Body headings: `## Failure` (evidence), `## Class` (the generator of the whole class), `## Fix` (highest level that works), `## Proof` (how we will know it helped: rounds, cost or defects measured on a real PR), `## Affects` (projects), `## Rollback`.
4. The other vendor reviews the proposal; the PM approves.
5. Merge, tag a new framework version, record it in `docs/decisions.md`; projects upgrade by their own PR.

Rule for rules: every rule lists its enforcer (gate check, CI check, template field, or "advice" if only prose). A repeated mistake whose rule is only "advice" must be promoted to a higher level in the same change.
