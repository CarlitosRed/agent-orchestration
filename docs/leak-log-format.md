# Leak log format
Each project keeps `.orchestration/leaks.md`. A leak is any place the process lost time, money or safety. Reviewers report them (at most five per review, rule R11); the Orchestrator logs them; the Program Owner decides which become framework change proposals.

| id | date | leak | evidence | root cause | class | fix (level) | status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| L<n> | <yyyy-mm-dd> | one line: what went wrong and what it cost (rounds, money, a near miss) | a pointer: PR and comment id, sha, file:line, command output | why it happened, one line | C<n> from `rules/leak-classes.md`, or "new" | the fix and its level: structure, gate, CI, script, template, prose | open / fixed in <where> / not doing (reason) / measure on <next PR> |

Rules:
- One row per leak, at most three lines; detail goes to the evidence file.
- Every row needs evidence a reader can open; "I remember" is not evidence.
- A class seen twice is fixed before the next PR starts, at the highest level that works; a prose-only fix for a repeated class is not accepted.
- PROPOSED: "fixed in template" is not done until a later PR shows the leak did not recur; then write "verified on <PR>".
- A meta row may summarise several leaks (root causes, rounds per PR); it cites the rows it covers.
- The class column is new in the framework (the first project's log had no class column; classes were assigned during extraction).
