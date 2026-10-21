# Review round 2 and later (verify and re-sweep)
The Orchestrator fills six values; the reviewer pulls the rest from the repo host. A long context paragraph per round costs Orchestrator capacity and drifts from the PR. Same reviewer vendor as round 1.

```
Role: Independent Reviewer, read-only, of PR <N> at exact head <full sha>. Edit nothing, commit nothing, push nothing, merge nothing. Effort: <level>.
Work silently on a task: do not narrate commands, failures or retries; fix your own errors; reply once with the final result (what was built and where it is). Stop to ask only if truly blocked, meaning only the Program Owner can unblock it.
Read first: your previous review (comment <id>, notes <audit path>) and the builder's newest comment (<id>). Review only the diff <old sha>..<new sha>, plus any instance of the same defect classes anywhere in the tree.
Do: (1) mark each earlier finding fixed, open or not reproducible, with evidence; (2) re-run the class sweep over the whole tree or code path and list EVERY remaining instance with its class; (3) PROPOSED, F3: use a vocabulary or generator different from the builder's, count an instance of a closed class as a failed builder sweep, and raise only classes that are new; (4) check nothing else changed (scope, gate config, invariants), run the tests, recheck CI. P1 and P2 with counterexample and reachable scenario. Correctness only.
Return: one comment starting with **Independent Reviewer · <Vendor>:** whose FIRST WORDS are "Approved at <full sha>" (only if clean) or "Not approved at <full sha>"; no byte-order mark; notes in <audit path for this round>; at most 5 process findings in the notes; reply at most 5 lines. No paid calls; never open .env*; no customer data in comments.
```

After posting: the Orchestrator runs the gate dry run to confirm the signal counts before telling the Program Owner.
