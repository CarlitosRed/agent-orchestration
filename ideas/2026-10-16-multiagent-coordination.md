# I-019: coordination preflight

Source: [Patterns and problems in emerging multiagent systems](https://www.anthropic.com/research/multiagent-systems), published 2026-08-13; read 2026-10-16.

## What the primary source reports

Coordinated and independent searches found different defects; matching search
scope changed the comparison. Dependent software tasks exposed integration
failures. Similar agents repeated choices, overloaded a queue, and escalated
incompatible objectives. Communication could also miss decisive minority evidence.
These are vendor-reported experiments, not measurements of this framework.

## Framework application

Propose a machine-readable dispatch plan with unique job IDs, declared write
ownership, explicit dependencies and a shared integration check. The checker is
`tools/dispatch-plan/dispatch_plan.py`; its limits and adoption path are in that
folder's README. This promotes part of R5/C11 from prose to an opt-in refusal.

Provider/model labels remain selectable data. Today's provider choice does not
become a permanent default, and model count does not establish review independence.
Existing R14 usage checks, R15 report verification and the merge gate still apply.

## Deferred and unverified

No live dispatcher, filesystem locks, queue backoff, evidence-arbitration changes
or interface is added. A prospective project trial is needed to evaluate effects
on integration failures, duplicate work and usage. The source experiments were
not reproduced, and their model comparisons are not treated as runtime guidance.
No source text is used as instructions. I-017 and I-018 were taken by the merged #62, so this note is I-019.
