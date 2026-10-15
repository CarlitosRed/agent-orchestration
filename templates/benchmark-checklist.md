# Benchmark checklist
Before you trust, report, or act on a number you measured (a speedup, a regression, a test count, a token cost, anything from `tools/usage-ledger` or a vendor's own usage output) - check all five. From idea I-014 (`ideas/README.md`), adapted from pstack's `benchmark-checklist`.

1. **Limiter.** What actually bounded this number - CPU, network, a cache that was warm (or cold) only this once, a rate limit, disk I/O? If you don't know, you don't know what the number measures.
2. **Tuning.** Was the configuration the one that matters (production-shaped, not a debug build; the real model, not a cheaper stand-in; real data shape, not a toy fixture)?
3. **Errors.** Did anything fail silently inside the run - a retried request, a skipped case, a partial result counted as complete? A number from a run with a swallowed error is not the number you think it is.
4. **Repeat runs.** Is this one sample or several? A single run cannot separate a real effect from noise; report a range or a repeat count, not one number dressed as certain.
5. **End-to-end relevance.** Does the measured thing reflect the real path a user or reviewer takes, or a proxy that's easier to measure but means something else (a unit benchmark standing in for the real request path; "tests pass" standing in for "the feature works")?

A number that fails any of these five gets labeled honestly (e.g. "one run, not repeated" or "measured a proxy, not the real path") rather than reported as settled fact. This applies to this framework's own claims about itself - a test count or a round-reduction number is a number like any other.
