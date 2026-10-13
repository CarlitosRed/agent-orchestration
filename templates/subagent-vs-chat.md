# Subagent or separate session? Five rules
1. **Subagent** when the work is read-heavy, independent and its detail will not be needed again (one docs page, one PR, one file group); only the summary comes back.
2. **Separate session** when you need an independent opinion (review of code another agent wrote) or the work will outlive this session. A fresh context is not biased to its own code.
3. **Do not split** work that shares context or writes the same files; one builder, one worktree.
4. A subagent sees no history: the brief carries objective, output format, tool guidance and boundaries, and caps the reply (12 to 25 lines). Longer detail goes to a named file.
5. Do not spawn for what takes a few tool calls, and never to check your own work; spawn only when you will wait for the results and merge them yourself. Subagents cost several times more tokens.

Framework rules on top: the author never reviews its own work; protected paths need the other vendor as reviewer; every helper returns a capped, signed report; check usage against the project's ceilings before spawning (R14); which vendor gets builds and which gets reviews is a project choice in the adapter's `roles.md`, set by allowance.
