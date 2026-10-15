# Cost ledger format
Each project keeps a cost ledger to learn which work burns the most. One row per finished task; the Orchestrator or the Operations Clerk may append.

| date | task | who (Role · Vendor, model) | tokens (helper) | rounds / outcome | ref |
| --- | --- | --- | --- | --- | --- |
| <yyyy-mm-dd> | <short task name> | <e.g. Build Engineer · Vendor, model> | <number the tool reports when the helper ends, input plus output plus tool results; or "not visible"> | <rounds, findings by severity, tests added, approved or not> | <PR, or none> |

Rules:
- Record what the tool reported, not an estimate; write "not visible" where a vendor shows no usage to the Orchestrator, and let the Program Owner add those rows from the vendor's usage page.
- Note the usage window before and after (five-hour and weekly percent) when known; it feeds the launch ceilings (R14). `tools/usage-ledger/usage.py log` records the same fact in a form `check` can actually gate on before the next launch, rather than only after the task finished; this table stays the human-readable, per-task analysis view (what burns the most), not a replacement for it.
- A resumed helper is its own row.
- Add a short "what the rows say" section when a pattern shows. Lesson from the first project: one exhaustive audit cost about as much as two review rounds of a mid-size PR, and the Orchestrator's own session used more than any helper.
- PROPOSED (F3): per PR, total rounds, classes and money, for the review-protocol metrics.
