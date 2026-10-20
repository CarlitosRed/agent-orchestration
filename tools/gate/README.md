# The merge gate (generic)

`gate.py` makes a project's merge rules checkable on a repository whose plan cannot enforce branch protection, and leaves a record on every merge. Every project rule lives in one JSON config (`gate.schema.md`); nothing about tiers, vendors, branch names, protected paths or checks is in the code.

Plain Python 3, standard library only. It calls `git` and the GitHub CLI `gh` (signed in to the project's account). No other network access, no key. Works on Windows, macOS and Linux: paths are forward-slash repository paths, `gh` output is read as UTF-8, git output as bytes, and console output never crashes on characters the terminal cannot show.

## Commands
Run from any checkout or worktree of the project. The config is found at `<repo top>/.orchestration/gate.json` unless `--config` says otherwise.

```
python gate.py check 12
python gate.py merge 12 --as "Release Manager · Beta" --dry-run
python gate.py merge 12 --as "Release Manager · Beta"
python gate.py scan --rev HEAD          # or --staged, --range A..B, --outgoing REV
python gate.py paths
python gate.py audit --range <old>..<new>
```

| Command | What it does | Changes anything? |
| --- | --- | --- |
| `check <PR>` | Prints every rule as PASS or FAIL for the PR's current head. Exit 0 only if all pass. | No |
| `merge <PR> --as "<signature>"` | Runs `check`; if all pass, squash-merges exactly that head (`--match-head-commit`) with a `Gate-Record:` body. `--dry-run` prints the command only. | Yes |
| `scan` | Forbidden files and secrets, by name and by content (a PDF renamed `.txt` is still a PDF; UTF-16 text, which Windows tools write by default, is read as text, other NUL-containing files are treated as binary). `--range`/`--outgoing` read every commit, so a file added then removed is still caught. | No |
| `paths` | How many tracked files each protected glob matches, to catch typos. | No |
| `audit --range A..B` | Flags first-parent commits with no valid `Gate-Record:` line, or an owner-tier record without `owner=yes`. | No |

Exit codes: 0 passed, 1 a rule failed, 2 the tool could not run (config error, `gh`/`git` error, a PR that moved while being read).

## Rules `check` applies
| Rule | Passes when |
| --- | --- |
| `state` | PR open, not draft, into `base`. |
| `hold` | No active `hold` comment (the owner's `unhold` lifts it) and no `hold_label`. |
| `signals` | No comment looks like a signal but fails to count: verdict for the head buried after other text, unsigned verdict for the head, commit id shorter than `verdict_sha_min_length`, invisible character before the signature. |
| `branch` | (only if `forbidden_head_prefixes` is set) the head branch is allowed as a PR head. |
| `tier` | Exactly one tier label; raised (never lowered) by protected paths and `allowed_paths`; non-mergeable tiers never pass. |
| `files` | The complete changed-file list (paginated, proven against GitHub's own count, pinned to the same base, head and count before and after reading; the second, full read is the one judged, so a hold, label or check posted meanwhile counts) has no forbidden file under its new or old name; fewer than 3000 files. Every name, branch, id and count is validated as exact text or a real integer first. |
| `comments` | Fewer than 100 comments, so the conversation is read in full. |
| `check:<name>` | Each `required_checks` entry succeeded on the head, in every run. |
| `evidence:<heading>` | Tiers with `body_headings`: each heading is in the PR body. |
| `author` | The head branch starts with a vendor's prefix (when the tier needs a go or approvals). |
| `plan` | Tiers with `plan_go`: a signed `go` from an independent reviewer or the owner. |
| `review` | `approvals` independent `Approved at <sha>` matching the head; any `Not approved` at the head blocks; a signer's later verdict replaces its earlier one. |
| `owner` | Tiers with `owner_approval`: the owner's `Approved at <sha>` matching the head. |

## Config: a worked example
An invented project, `recipe-box`, with two agent vendors, Alpha and Beta, one human owner, and one older signer name per vendor kept while old PRs close.

```json
{
  "_about": "Gate config for recipe-box. Changing this file is a protected-path change.",
  "schema_version": 1,
  "repo": "",
  "base": "main",
  "tiers": [
    {"label": "tier-1", "level": 1, "name": "docs only", "allowed_paths": ["docs/*", "README.md"]},
    {"label": "tier-2", "level": 2, "name": "code", "approvals": 1, "plan_go": true, "body_headings": true},
    {"label": "tier-3", "level": 3, "name": "money and trust", "approvals": 1, "plan_go": true,
     "body_headings": true, "owner_approval": true},
    {"label": "tier-4", "level": 4, "name": "humans only", "mergeable": false}
  ],
  "vendors": {
    "alpha": {"names": ["Alpha"], "branch_prefixes": ["alpha/"]},
    "beta":  {"names": ["Beta"],  "branch_prefixes": ["beta/"]}
  },
  "legacy_signers": {"Scout": "alpha", "Tinker": "beta"},
  "owner_signers": ["Program Owner"],
  "forbidden_head_prefixes": ["integration/"],
  "protected_paths": ["AGENTS.md", ".github/*", ".githooks/*", ".orchestration/*", "tools/gate/*",
                      "app/billing/*", "migrations/*", "*/migrations/*"],
  "protected_tier": 3,
  "required_checks": ["tests", "gate-tests", "scan"],
  "body_headings": ["Plan", "Evidence", "Cost"],
  "verdict_sha_min_length": 40,
  "forbidden_globs": ["*.pdf", "*.png", "*.jpg", "*.sqlite3", "*.pem", "*.key", ".env", ".env.*",
                      "data/*", "output/*"],
  "scan_allow": [".env.example", "tests/fixtures/fictional/*"],
  "max_file_mb": 5,
  "shared_account": true,
  "audit_exempt": []
}
```

What it means: a Beta PR (`beta/add-tags`) labelled `tier-2` needs `**Independent Reviewer · Alpha:** go`, then `**Independent Reviewer · Alpha:** Approved at <40-char head>`, green `tests`, `gate-tests` and `scan`, and `## Plan`, `## Evidence`, `## Cost` in its body; then `python gate.py merge <n> --as "Release Manager · Beta"`. If it touches `app/billing/`, it becomes `tier-3` and also needs `**Program Owner:** Approved at <head>`. An old-style `**Scout · PR review:** Approved at <head>` counts as Alpha.

Full field reference: `gate.schema.md`.

## Signals, exactly
- Sign: `**<Role> · <Vendor>:**` (agents) or `**Program Owner:**` (owner). Older projects may keep `**<Name> · <job>:**` via `legacy_signers`.
- The signal is the first words after the signature: `go`, `Approved at <sha>`, `Not approved at <sha>`, `hold`, `unhold`.
- Write comment files without a byte-order mark. A faulty signal fails the `signals` rule; post it again correctly and hide the faulty comment.
- Run `check` after every approval before saying it counts.

## What the gate cannot do
- Stop a manual merge by anyone holding the account's credentials. `audit` (run from CI on every push to the base) reports it afterwards.
- Prove who wrote a comment on a shared account. The owner's `hold` and the audit are the backstop.
- Check base and head atomically: it pins the head, not the base (one merge at a time, rule R13).
- Judge the code. Reviewers and CI do that.

## Migrating a project that has its own gate
This tool does not migrate anyone by itself. For a project that already runs its own gate with open PRs (the first one is the reference project the tool was extracted from):

1. **Write the config** in `.orchestration/gate.json` on a branch, without touching the old gate. Map the old settings: tiers and their approvals, plan-go, owner and evidence tiers become tier objects; old vendor first names become `legacy_signers`; old owner names go in `owner_signers`; branch prefixes move under `vendors`; protected, forbidden and allow lists copy over. If old approvals used short commit ids, set `verdict_sha_min_length` to what the old gate accepted (otherwise open PRs lose their approvals). Old tier numbers stay as `record` values so `audit` keeps reading old merge commits.
2. **Dry-run both gates side by side** on every open PR and a sample of merged ones: `old-gate check <n>` and `python gate.py --config .orchestration/gate.json check <n>`, plus `audit` over the full base history and `scan --rev HEAD`. Nothing merges.
3. **Compare** rule by rule. Every difference must be explained: expected ones are the new `signals` rule (buried verdicts and byte-order marks now fail loudly instead of silently not counting) and stricter owner matching. Anything else is a config error or a bug; fix before going on.
4. **Cut over** in one protected-path PR, when no merge is in progress: point CI, hooks and docs at the new tool, keep the old gate file until the next PR removes it. New comments use `Role · Vendor`; remove `legacy_signers` once no open PR depends on them.

## Tests
```
python -m unittest discover -s tools/gate -p "test_gate.py" -v
```
They use a pretend `gh` and throw-away local git repositories; they never contact GitHub.
