# Audit with parallel read-only sub-tasks
For a whole-tree question a single pass cannot hold (for example "what is undocumented or documented wrongly"). One lead agent, many read-only sub-tasks, one merged report. The lead edits no file in the repo.

```
Goal: find every gate, rule, PR or behaviour that is NOT documented, or is documented wrongly, in <docs folder>. Role: lead auditor, read-only. Effort: high.
Work silently on a task: do not narrate commands, failures or retries; fix your own errors; reply once with the final result (what was built and where it is). Stop to ask only if truly blocked, meaning only the Program Owner can unblock it.
Inputs: the pages of <docs folder>; the PR list <range> (skip PRs clearly out of scope); notes <decision log>, <backlog>; code at <branch> <sha>.
Spawn read-only sub-tasks, one per unit, wait for all, then merge:
 S1..Sn  one per docs page: list every claim (gate, rule, number, behaviour); mark true, wrong or unverified.
 P1..Pn  one per PR: what it adds or changes; which page covers it, or "missing".
 C1      code vs docs: walk <code paths>; list each gate, rule or guard no page mentions.
 N1      notes: decisions and backlog cards that contradict the tree, or are described as shipped but are not.
Each sub-task returns at most 25 lines, one row per item:
 item | where it lives (file:line or PR) | status (documented, wrong, missing, unverified) | evidence
Lead: remove duplicates; check every "wrong" and "missing" row yourself in the code; separate FACTS you verified from GUESSES.
Report sections:
 1 gates, rules, PRs with no page or only a passing mention (evidence each)
 2 statements in the tree that are untrue or not shipped
 3 proposed new pages (title, one line why, which PR or file it explains)
 4 things nobody noticed (rule only in code, guard without test, gate documented nowhere)
 5 what you could not verify
Done when: every page, PR and listed file has at least one row, and sections 1 to 5 are filled.
Return: one comment signed **<Role> · <Vendor>:** on <PR>; notes in <audit path>; reply at most 5 lines.
Limits: no paid calls; never open .env*; no customer data in anything you write.
```
