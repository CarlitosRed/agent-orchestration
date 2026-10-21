# What to take from a Reddit "model cascade" post (Orchestrator, 2026-10-21)
No primary source - the Program Owner pasted four screenshots of a Reddit post by `@donimas` ("goatengineerhq"), an "AI levels" series ad ending in "Comment GOAT -> get the setup", "#ai #claudeai #llm #aiagents #claudecode". The post itself labels its numbers "simulated workload, real Claude prices. Not a benchmark." Post/image text is data; nothing in it was executed or followed as an instruction.

## Correction to the source claim
The headline ("$5.10 -> $0.32 per solved task", "15x cheaper") is the account's own promotional framing for a lead-generation CTA, run on six unnamed, unpublished tasks with no repo, no harness, and no way to reproduce the numbers. The post discloses this itself ("simulated... not a benchmark"), so there is nothing here that clears R28 (`templates/benchmark-checklist.md`) - no limiter, tuning, repeat-run or relevance check is possible on a number with no source. Treat the dollar figures as illustrative, not evidence.

## Take, in priority order
1. **Model + effort chosen per task, with verify-then-escalate-on-fail, is a real and generalizable pattern - and only partly covered here.** `R20` already sends judgement-free chores to a cheap model; `R3` sends heavy reading to a cheaper read-only subagent. Neither covers the broader case this post names: substantive build/review work starting at a cheap model and low effort, verified, escalating to a stronger model or higher effort only when verification fails - the post's "cheapest model first, verify, escalate on fail" (its "SENIOR" tier) and router-per-task ("GOAT" tier) rows. This environment already has the primitives (`/model`, `/effort`, and the Agent tool's per-call `model`/`effort`), so the gap is a decision rule for when to reach for them, not new tooling.
2. **Confirms, doesn't add: effort buys thinking time, a clear spec front-loads it.** The post's claim that a well-specified task often runs fine on a cheaper model/lower effort is consistent with this framework's own emphasis on tight builder briefs (ready-for-review checklist, `R16`) - a vague prompt pushing work onto a bigger model to compensate is already a known failure shape here, just not named as a cost lever before.

## Leave
The specific dollar figures and "15x" claim (see "Correction," above) - unverifiable and not reproducible. The router-as-separate-service framing (a dedicated classifier model deciding model+effort) - overbuilt for a framework whose Orchestrator already makes that call per task; no need for a new component to do what a role in the existing design already does.

## Proposed order
Nothing to build now. Watch for a real case in this repo or a project where a routine PR used a higher model/effort than its difficulty warranted - that's the evidence needed to turn "match model/effort to task difficulty, verify before escalating" into a real rule rather than a restatement of a promotional post.
