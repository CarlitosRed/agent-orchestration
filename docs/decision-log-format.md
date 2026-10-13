# Decision log format
A decision that exists only in chat does not exist (rule R4). Every project keeps one decision log; the framework's `docs/decisions.md` moves to this shape (its first rows have no "by" column). Adopted from the ideas register (I-004); the "by" column, the start row, the transcript audit and the other-vendor scan are new practice, first use pending.

| date | decision | by | evidence |
| --- | --- | --- | --- |
| <yyyy-mm-dd> | one to three lines: what was decided and the one-line why | Program Owner / Orchestrator / <Role · Vendor> | a pointer someone can open: sha, PR comment id, file:line, audit or draft file |
| <yyyy-mm-dd> | START <session name>: what this run sets out to do | Orchestrator | handoff or resume file |

Rules:
- **Append-only.** Never edit or delete a row; a reversal is a new row that names the row it reverses.
- **At most three lines per row.** Detail lives in the linked file.
- **Evidence column is required.** A row without a pointer is a draft, not a decision.
- **Start row per run.** Each Orchestrator session adds a START row, so the log can be cut by session.
- **Audit at the end of a milestone.** The Orchestrator compares the log with the session transcript and adds any decision that was made but not logged.
- **Other-vendor scan.** An agent from the other vendor reads the log for decisions without evidence or that contradict each other; it reports, it does not edit.
