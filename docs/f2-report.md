# F2 report: the gate as a generic tool (Platform Engineer, 2026-10-13)
Milestone F2: turn the first project's merge gate into a vendor- and project-agnostic tool. The source project was only read (one probe ran its gate script against a scratch repository with `python -B`, so nothing was written into the source tree; `git status` there is unchanged). Nothing committed; the Orchestrator commits.

## Built
| File | What |
| --- | --- |
| `tools/gate/gate.py` | The tool. Same CLI as the source gate: `check`, `merge --as [--dry-run]`, `audit --range`, `scan [--staged / --rev / --range / --outgoing]`, `paths`. Standard library only; `gh` and `git` as before. Renamed from the source file name because that name carried the project's initials. |
| `tools/gate/gate.schema.md` | The config schema (version 1): required and optional fields, tier object, signature classification, signals, Gate-Record trailer. |
| `tools/gate/test_gate.py` | 224 offline tests (fake `gh`, throw-away local git repositories). |
| `tools/gate/README.md` | What it does, the rules, a worked example config for an invented project, commands, migration steps. |
| `adapters/README.md` | `gate.json` line replaced with the real field names. |

## Test results
Command, run from the framework repo root on Windows 11, Python 3.12.10, git 2.55.0.windows.5:
`python -m unittest discover -s tools/gate -p "test_gate.py" -v`
Result: **224 run, 224 passed, 0 failed, 0 errors, 0 skipped** (about 36 seconds). Two git-grammar tests skip only if `git` is missing; it was present. The first run had 1 failure and 2 errors: one test setup slip, one too-narrow detector (6-character ids were not reported), and one real bug inherited from the source gate (below). All three fixed, then the full suite re-run green.

The source test file is offline too (it uses a fake `gh` and temporary git repositories; the one exception, its pre-push hook tests, runs a local `sh`, no network).

## Bug found in the source gate (not fixed there)
`scan --rev`, `scan --staged` and `paths` read file names with `git ls-tree --name-only` / `git diff --name-only` / `git ls-files` without `-z`. Git quotes non-ASCII names (`"caf\303\251.txt"`), so `git show` cannot find them. Probe: the source gate on a scratch repository with one committed file `café.txt` exits 2 with `path '"caf\303\251.txt"' does not exist`. It fails closed (no bypass), but any non-ASCII file name blocks the scan job. The generic tool uses `-z`; three tests cover it. The source project should get the same one-line fix in its own PR.

## Leak-class fix: verdict first, made an enforcer (C4, L27, L37, L40)
The source gate already matched the verdict only at the start of the text after the signature, so a buried approval never counted; but it failed silently, which is how three approvals were believed and did not count. New rule **`signals`** FAILS `check` (and so `merge`) when a non-hidden comment or review body:
- has a verdict for the head commit that is not the first words after the signature (text before it, a later sentence or paragraph, bold or quote markup, odd spacing such as two spaces or a line break inside "Approved at");
- carries a verdict for the head with no signature;
- uses a commit id shorter than `verdict_sha_min_length`;
- has an invisible character (byte-order mark, zero-width space, any Unicode C* or Z* character) before the signature.
The fix for the author is to post the signal again correctly and hide the faulty comment. A buried `Not approved at <head>` therefore blocks instead of vanishing. Verdicts for older commits are ignored by this rule (they could not count anyway). Bypass-first tests: buried sentence, buried paragraph, five "extra text before" shapes, byte-order mark, zero-width space, byte-order mark on `go`, case variants (count), odd spacing (refused), short id, 41-character id, unsigned verdict, review-body verdict, hidden comment clears it, merge refuses while faulty. All of these pass the source gate's `review` silently or are not reported by it; the `signals` rule does not exist there.

## The two signature formats
| | Legacy | New |
| --- | --- | --- |
| Shape | `**<Name> · <job>:**` or `**<Name>:**` | `**<Role> · <Vendor>:**` |
| Example | `**Scout · PR review:** Approved at <sha>` | `**Independent Reviewer · Alpha:** Approved at <sha>` |
| What the first part is | a name listed in `legacy_signers` | a role listed in `roles` |
| Vendor comes from | `legacy_signers[Name]` | the second part, which must be a vendor `name` |
| Parts | any number (as the source read it) | exactly two |
| Role | none | the first part |
Owner: `**<owner signer>:**`, the whole signature equal to one of `owner_signers`.

Detection is unambiguous because only the first part (before the middle dot U+00B7) decides the format, and `roles`, `legacy_signers` and `owner_signers` must be disjoint, checked when the config loads (a config that breaks this is refused). A vendor name in first position (`**Alpha · PR review:**`) is unknown, never legacy. Both formats count side by side in one project (tested), so an existing project's open PRs keep working while new comments use roles. Comparison ignores case and repeated spaces.

## PO-specific rules turned into configuration
| Source (hardcoded or project default) | Generic |
| --- | --- |
| `TIER_LABELS` tier-1..tier-4, trailer `tier=[123]` | `tiers[]` with `label`, `level`, `record`, `mergeable` |
| `approvals_required`, `plan_go_tiers`, `owner_approval_tiers`, `evidence_tiers`, `same_vendor_ok_tiers` | per-tier `approvals`, `plan_go`, `owner_approval`, `body_headings`, `cross_vendor` |
| `tier1_paths` and "tier 1 raised to 2" | per-tier `allowed_paths`, raise to the next level |
| protected paths raise "to 3" | `protected_tier` |
| `vendors` (first word -> vendor), `branch_vendors` | `vendors{id: names, branch_prefixes}` plus `legacy_signers` |
| `owner_names` | `owner_signers` |
| `reviewer_chats` | `same_vendor_reviewers` |
| `MAGIC`, `SECRETS` tables | `magic`, `secrets` (defaults are the source tables) |
| `evidence_headings` | `body_headings` |
| hold label `hold` | `hold_label` |
| VERDICT accepts 7 to 40 hex | `verdict_sha_min_length`, default 40 (docs say full sha); set 7 to match the source |
| config next to the script, PO defaults if missing | `<repo top>/.orchestration/gate.json`; missing file is an error |
New from the docs, not in the source gate: `forbidden_head_prefixes` (tiers doc: an integration branch cannot be a PR head), optional `approver_roles` and `merger_roles` (roles doc: the role drives who may do what; off by default, so source behaviour holds).

## Deliberately not ported, or changed
1. **The pre-push hook tests** (`HookHistoryTests`): they run the project's own `.githooks/pre-push`, which the framework does not ship. The history-scan logic they exercise is ported and tested directly.
2. **Built-in policy defaults**: the source fell back to its own project's names, paths and vendors when `gate.json` was missing. The generic tool refuses to run without a config, and refuses unknown fields (a typo cannot silently drop protection).
3. **Owner matching narrowed**: the source treated any signature whose first word was an owner name (`Owner · anything`) as the owner. Now the whole signature must equal an owner signer. An agent writing `**Program Owner · Alpha:**` is unknown.
4. **Signer identity is case-insensitive**: a later `Not approved` from the same signer in different case now cancels its approval (source keyed by exact string).
5. **A hold behind a byte-order mark now holds** (source silently ignored it); an `unhold` behind one does not lift.
6. **41+ hex characters** after "Approved at" no longer match as a 40-character prefix.
7. **`scan` folds case for forbidden names** like `check` already did (source `scan` was case-exact while `check` folded); `paths` counts with the same folding the tier rule uses.
8. **`audit` owner check** looks for ` owner=yes by=` instead of the substring `owner=yes` anywhere after the head (a reviewer name containing `owner=yes` no longer satisfies it).
9. **`scan --range`** with anything but `A..B` is a clear error instead of a Python traceback.
10. All user-facing messages name roles and the configured owner, not people or vendors.
Unchanged on purpose: the whole file-list proof (pagination, count proof, before/after pinning, strict ids, names, statuses, Git branch grammar, rename old names), required-check reading, the 100-comment and 3000-file caps, `--match-head-commit` squash merge, the Gate-Record format, first-parent audit with the new-branch case, history scan of every commit, secrets never printed.

## F1 inconsistencies resolved here
- Old reviewer template without "first words" (F1 contradiction 4): now enforced by the `signals` rule regardless of template.
- Owner's signature in a generic gate (F1 unsure 3): `owner_signers`, project-declared.
- Seven-character sha rule (left in the project by F1): a config value; framework default is the full id.
- Launch ceilings, cost-ledger writer, which vendor builds (contradictions 1 to 3): not gate rules, untouched.

## Unsure
1. The `signals` rule can block on an innocent comment that quotes a head verdict (for example the Orchestrator relaying "the reviewer wrote Approved at <head>"). Hiding the comment clears it. Fail-closed felt right for L37/L40, but it may be noisy; measure on the first project before relying on it.
2. Plan `go` uses the same "independent" test as approvals (other vendor, or owner), as the source did; F1 noted the docs disagree on who posts the Tier 2 go. `approver_roles` also restricts go.
3. Legacy signers carry no role, so `approver_roles` and `merger_roles` do not restrict them. Fine during migration; remove `legacy_signers` after cut over.
4. Default `verdict_sha_min_length` 40 is stricter than the source's 7. A migrating project must set 7 at first or its open approvals stop counting.
5. Verdicts are detected for reporting from 4 hex characters up; shorter ones are not reported (they cannot count either).
6. Only tested on Windows with Python 3.12; the cleanup helper has a fallback for older Pythons, not run here.
7. The rename from `po_gate.py` to `gate.py` changes the CLI program name; commands and flags are the same.
