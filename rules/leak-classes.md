# Leak classes: the core lesson
41 process leaks from the first project fall into 11 classes. A class is named by its **generator**: one line that enumerates every member, so a fix can cover the class instead of the instance someone happened to find. Fix levels, highest first: structure, gate or CI check, script, template field, prose rule. Each leak is listed under its main class; "also" marks a second class.

## C1. Instance chasing
- **Generator:** a finding is fixed as the one reported instance while the rule that produced it has more members.
- **Examples:** a review finds one more mislabelled word each round, five rounds running; a validator gains one bad character per round while the rest of its grammar stays open.
- **Fix:** class ledger. Every finding becomes a class with a generator; the builder enumerates the generator's whole space with a script, proves it with a test that is red on the old head, and posts the sweep output. Reviewers name the class and list every instance in one pass. (Template fields today; controller script PROPOSED, F3.)
- **From:** L13, L24, L30 (also L1, L14, L18, L22, L25).

## C2. Claims beyond the evidence
- **Generator:** any sentence with a condition, a quantifier (always, never, only, same, new) or a qualifier, written without the input that would make it false.
- **Examples:** docs say "a retry makes a new run" when it does so only if no earlier run exists; "blocked by the cap" when two independent caps exist and the sentence names one.
- **Fix:** claims ledger per behavioural sentence: exact condition from the code's operands (not a nearby comment), the exception, the pinned line, one state-ledger row through the whole flow with every admission condition as a second axis. Text that restates code facts is generated, not hand written.
- **From:** L1, L6, L8, L14, L15, L20, L23.

## C3. Tests that share the code's blind spots
- **Generator:** the input space of a check is drawn from the author's model of the problem instead of the governing spec, the real platform and every endpoint of the compared change.
- **Examples:** 100 green tests against a fake that always returns complete data, while three bypasses pass; path checks written for one operating system while the tool runs on another (drive roots, junctions, short names, streams).
- **Fix:** bypass-first tests (fail on the old code); fakes that return partial, empty, malformed and unexpected data; vary every input that defines the result independently; derive the matrix from the official grammar of each value and the platform it runs on; near-valid values; one probe per alias class before claiming "alias safe"; fix shared helpers once instead of per feature. Optional: ask the reviewer for the input dimensions before the build starts (threat model first, untested).
- **From:** L2, L11, L12, L18, L22, L25, L41.

## C4. Machine-read text produced by hand
- **Generator:** any text a parser decides on (signature, verdict, plan go) written from memory or by a tool that adds bytes.
- **Examples:** an approval whose first byte is an invisible byte-order mark; an approval that puts the verdict in its second paragraph. Both look right and count for nothing.
- **Fix:** gate or linter reports misplaced verdicts and leading marks (PROPOSED); templates give the exact first words; read the parser before telling the owner a phrase; run the gate dry run after every signal.
- **From:** L27, L37, L40.

## C5. Process gates found late
- **Generator:** any precondition the merge gate checks that nobody checks when the PR opens.
- **Examples:** a protected-path PR reaches the final dry run after eight rounds without the plan go the gate requires; the Orchestrator tries to merge PRs the gate reserves for the author's vendor.
- **Fix:** gate dry run when the PR opens (CI job PROPOSED), with only reviews and owner approval allowed to fail; the plan says where the go comes from and who runs the merge; branch prefix and body headings checked at opening.
- **From:** L26, L31, L34, L38.

## C6. Facts copied by hand instead of read from the source
- **Generator:** a fact restated from another source (code, CI log, repo host, an older note) without re-reading that source.
- **Examples:** notes say a test suite runs in CI because a job has that name, while it skips silently; the Orchestrator tells the owner a review never ran, judging from a missing file, while the comment had landed minutes later.
- **Fix:** read the source of truth (repo host, the log, the parser) at the moment of the claim; generate derived text (pin summaries, line labels) from parsed data and add a check comparing visible labels with their anchors; prune stale scope lines in instruction files.
- **From:** L16, L28, L29, L32, L35.

## C7. Rounds that mix or widen
- **Generator:** a round whose diff contains anything other than the fixes for the listed classes.
- **Examples:** a correction round also adds three new pages, so the review is half re-review and half fresh review and does not close; a prompt promises an absolute guarantee the mechanism cannot give, which invites scope growth every round.
- **Fix:** corrections and additions in separate commits and reviews; a fix widens nothing (extras go under "suggestions"); prompts state the guarantee and its residual risk.
- **From:** L7, L19.

## C8. Review loop overhead
- **Generator:** each round re-reads everything and is paid three times (builder resume, review round, Orchestrator bookkeeping).
- **Examples:** a weekly review allowance spent on late rounds that each find one sentence; a reviewer rereads truncated output and writes helper scripts with hard-coded paths.
- **Fix:** later rounds read only the delta plus the class ledger; a short round prompt pulls context from the repo host; the reviewer builds a compact claim inventory first and passes paths as arguments; every P2 carries a reachable scenario, not only a function-level counterexample; round budget 3.
- **From:** L4, L9, L10 (also L30).

## C9. Environment facts rediscovered
- **Generator:** a fact about the machine, a dependency or a flaky test that each agent finds again.
- **Examples:** a builder cannot run the browser checks because the dependency is missing in its worktree; a known socket flake costs a rerun and a relevance lookup in every round.
- **Fix:** desk facts in the project adapter (`desk.md`), read by every builder; missing checks moved into CI; a flake list with test, error signature and rerun result.
- **From:** L3, L17, L21 (also L35).

## C10. Unsafe writes by tools
- **Generator:** a write whose encoding, file set or order of operations is a default rather than a choice.
- **Examples:** a shell rewrite re-encodes a character in a notes file; a script opens a file for writing before reading its replacement and blanks it; a blanket "add all" sweeps another agent's evidence folder into a commit.
- **Fix:** use the edit tools; read first, write after, check the size before committing; UTF-8 without a byte-order mark; stage named paths only.
- **From:** L5, L36 (also L37).

## C11. Seams between parallel changes
- **Generator:** two changes that meet at a contract or a base, with no check across them.
- **Examples:** two PRs built in parallel disagree on reason codes, and a dry run followed by a live run on the same output silently reuses stale records; a merge resolved against a squash-landed base reads "absent in my old branch" as "deleted by this PR" and drops main's lines.
- **Fix:** a shared contract test with one owner for the glue; after any squash landing, diff the PR head against the new main and list the main lines it removes; one merge at a time (R13).
- **From:** L33, L39.
