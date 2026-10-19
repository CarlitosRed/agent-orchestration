# Dispatch-plan preflight (opt-in proposal)

Check declared worker identities, ownership and dependencies before a dispatch.
This is an offline checker, not an agent launcher or approval gate.

```powershell
python tools/dispatch-plan/dispatch_plan.py check tools/dispatch-plan/example.json
python -B -m unittest discover -s tools/dispatch-plan -p test_dispatch_plan.py
```

The fictional example proposes two disjoint builders, followed by a read-only
review. Its SHA, providers and models are placeholders, not available runtimes.

## Contract

A plan has schema version 1, a full lowercase base SHA, a shared goal, a named
integration check, positive integer `max_parallel`, and a non-empty `jobs` list.
Each job declares its role, provider/model labels, workspace ID, access, output,
proof, dependencies, branch ID and write scopes. Keys are exact; missing/unknown
fields, duplicate JSON keys and wrong types are input errors. Read-only jobs use
empty write scopes and null branch IDs. Writers declare a branch and write scopes.

IDs are lowercase ASCII labels of up to 64 letters/digits/underscores/hyphens,
starting with a letter or digit. Scope labels are slash-separated lowercase ASCII
segments with that character set; they describe logical resources, not real paths.
Declare a shared resource consistently across jobs. `code` overlaps `code/parser`;
`code/parser` and `code/parser_extra` are separate scopes. Scope labels have no
filesystem alias resolution, length cap or translation into sandbox permissions.

The checker refuses duplicate job IDs, unresolved/cyclic dependencies and pairs
without a dependency ordering when a writer shares a workspace, two writers share
a branch ID, or their declared write scopes overlap. A transitive dependency is
enough to order reuse. An incidental batch ordering or `max_parallel: 1` is not an
ownership dependency; specify the intended order explicitly.

Output proposes deterministic, capacity-bounded batches and lists declared model
and provider labels. Multiple models from one provider and multiple providers
use the ownership checks above. Labels do not prove actual runtime identity,
availability, independent review, owner approval or compliance with `gate.json`.

## Enforcer and limits

Exit 0 means the declared plan passed. Exit 1 refuses a coordination conflict.
Exit 2 reports file/format/decoder errors. The CLI reads the input and prints a
report; it does not change the plan, launch workers, acquire locks or contact a
provider. A valid plan is not proof that the actual environment matches it.

Proposed batches assume predecessors succeed; task completion and output heads
must be verified separately before downstream work. The base SHA is a declared
starting point, not a verified result-head receipt. Output/proof/integration
strings are required fields, not executed checks. Approval rules, usage ceilings,
preflight health, write containment and the human brief still apply separately.

Adoption is opt-in. No project config, dispatch process or framework pin changes
automatically. A project trial must record actual jobs/resources, refusals, result
heads, integration checks and usage before claiming a delivery improvement.
