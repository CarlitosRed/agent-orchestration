# Review-history observations

This tool describes signed verdict events in GitHub issue comments. It does not
measure actual review rounds, class reopens, avoided rounds or framework savings.
Those measures still need the structured class ledger and a prospective trial.

## Commands

```powershell
python tools/benchmark/round_history.py fetch --repo OWNER/REPO --pr 35 --out history.json
python tools/benchmark/round_history.py analyze --comments history.json --reviewer "Independent Reviewer · Example"
```

Repeat `--reviewer` for additional eligible signatures. Use the project's actual
reviewer identities, including legacy signatures when applicable. Do not include
owner or builder signatures. This selection is supplied by the operator; it is
not identity authentication or the merge gate's independence check.

`fetch` retrieves issue-comment pages with `gh api --paginate --slurp`, decodes
UTF-8 explicitly, and checks the response before writing the snapshot. A failed
request, including a later page failure, returns exit 2 without replacing an
existing snapshot. Formal review bodies, inline review comments and minimized
status are outside this collection surface. Paging a changing thread is not an
atomic snapshot; retain the fetch time and treat it as a dated observation.

The snapshot contains schema version 1, repo, PR, fetch time, collection coverage,
pagination status and comments. Legacy fixture lists remain readable, with
coverage and pagination marked unknown. Comment bodies are strings; `created`
contains a timezone-aware ISO 8601 timestamp. Analysis orders comments by time.

## Report contract

| Field | Meaning |
| --- | --- |
| `verdict_events` | Leading signed verdicts matching the supplied reviewer signatures |
| `first_approval_event_index` | First matching approval event, or null |
| `has_approval_event` | Historical presence of an approval event, not current approval |
| `distinct_reviewed_sha_tokens` | Distinct case-normalized SHA strings; abbreviated/full aliases remain unresolved |
| `review_rounds`, `rounds_to_approval`, `class_reopens` | Null: structured round/class-lifecycle evidence is absent |
| `comment_text_overlap` | Whole-comment Jaccard overlap; shared boilerplate can trigger it |
| `literal_reopen_phrase_events` | Literal matches, including negated phrases such as 'no class remains open' |
| `collection` | Stated collection scope and pagination provenance |
| `reviewer_signatures` | Case/whitespace-normalized caller selection used for the report |

Refreshed approvals remain events; no additional round is inferred. SHA tokens
use 7-40 hex characters with an optional matched backtick pair. Eligibility and
syntax are narrower than an arbitrary quoted or buried verdict. Text observations
do not establish class identity, prior closure, approval validity or merge readiness.

The original PR #35/#38 fixtures are dated input snapshots retained unchanged.
They contain three and five matching verdict events respectively for the legacy
reviewer signature. A later approval refresh in #38 yields six live events while
still referring to round five. The fixture comparison does not measure the class
ledger's false-negative rate or prove that a ledger would prevent those rounds.

Run offline checks with:
`python -B -m unittest discover -s tools/benchmark -p test_round_history.py`.
Exit 0 means analysis/fetch completed; exit 2 reports a usage, collection, format
or file error. This unmerged tool's original inferred-round JSON contract is
replaced by the observation fields above.
