# Gate config schema (version 1)

One JSON file per project, by default at `<repo top>/.orchestration/gate.json` (or pass `--config`). Plain JSON, UTF-8 (a byte-order mark is tolerated in this file only). The gate refuses to run on a missing file, invalid JSON, a missing required field, a wrong type, or an **unknown field** (a typo such as `protected_path` must never silently drop protection). Fields starting with `_` are comments and are ignored.

There are no hidden policy defaults: tiers, vendors, owner, protected paths and required checks must be written down. Only non-policy knobs have defaults.

## Required fields
| Field | Type | Meaning |
| --- | --- | --- |
| `schema_version` | `1` | The schema this file follows. |
| `tiers` | list of tier objects (below) | Every tier a PR can carry. At least one. |
| `vendors` | object: vendor id -> `{names, branch_prefixes}` | `names`: how the vendor is written after the dot in a new-format signature (`Independent Reviewer · <name>`). `branch_prefixes`: head-branch prefixes that mark a PR as authored by this vendor. Names are unique across vendors (case-insensitive); prefixes may not overlap (no prefix may start another vendor's prefix). Optional `logins`: the GitHub logins that may sign as this vendor (case ignored, one login per vendor). When set, a verdict or `go` signed as this vendor counts only if its comment was posted by one of them; otherwise it counts for nothing and the `signals` rule fails. |
| `owner_signers` | non-empty list of strings | The Program Owner's signatures, written alone: `**Program Owner:**`. The whole signature must equal one of these (case and spacing ignored). Owner lines: Tier approval, `unhold`, plan `go`. |
| `protected_paths` | list of globs | A change to any of these (new or old name of a rename; case ignored) raises the PR to `protected_tier`. |
| `protected_tier` | integer | The `level` of the tier protected paths raise to. |
| `required_checks` | list of strings | CI check or status names that must succeed, in every run, on the head commit. May be `[]`. |

## Tier object
| Field | Type | Default | Meaning |
| --- | --- | --- | --- |
| `label` | string | required | The PR label, e.g. `tier-2`. Exactly one tier label per PR. |
| `level` | integer | required | Ordering. Raises always go to a higher level; the gate never lowers. |
| `name` | string | `label` | Display name only. |
| `record` | string `[A-Za-z0-9_.-]+` | `str(level)` | The value written as `tier=<record>` in the Gate-Record trailer and read back by `audit`. |
| `approvals` | integer >= 0 | `0` | Independent approvals required at the head commit. |
| `plan_go` | bool | `false` | Needs a signed `go` from an independent reviewer or the owner. |
| `owner_approval` | bool | `false` | Needs `**<owner>:** Approved at <sha>` at the head. `audit` flags a record of this tier without `owner=yes`. |
| `cross_vendor` | bool | `true` | Approvals must come from a vendor other than the author's. `false` additionally admits signers listed in `same_vendor_reviewers`. |
| `body_headings` | bool | `false` | The PR body must contain every heading in `body_headings`. |
| `allowed_paths` | list of globs or `null` | `null` | If set, a PR labelled with this tier that changes any file outside these globs (case-exact) is raised to the next higher tier. |
| `mergeable` | bool | `true` | `false` = human only: the gate never passes it, and its `record` is never accepted by `audit`. |

Raise order: protected paths first (to `protected_tier` if lower), then `allowed_paths` repeatedly to the next level. Landing on a non-mergeable tier, or needing a raise when no higher tier exists, fails the `tier` rule.

## Optional fields (defaults)
| Field | Default | Meaning |
| --- | --- | --- |
| `repo` | `""` | `owner/name`; empty = ask `gh` from the current folder. |
| `base` | `"main"` | The only base branch the gate merges into. |
| `roles` | the nine agent roles of `docs/roles-and-names.md` (not Program Owner) | Role names accepted before the dot in a new-format signature. |
| `legacy_signers` | `{}` | Old-format first names -> vendor id, e.g. `{"Scout": "alpha"}` reads `**Scout · PR review:**` as vendor `alpha`. A project mid-migration removes these once it has cut over; a project that never adopts `<Role> · <Vendor>` signatures at all keeps them indefinitely - "legacy" names the signature format, not a required transition (found 2026-10-15: advance-po-reader has used only this format since before the framework existed, and has no plan to change it). |
| `approver_roles` | `null` (any role) | If a list, only new-format signers with these roles count as approvals and plan go. Legacy signers carry no role and are not restricted. |
| `merger_roles` | `null` (any role) | If a list, `merge --as` accepts only these roles (owner always allowed). |
| `same_vendor_reviewers` | `[]` | Full signatures that may approve their own vendor's work on tiers with `cross_vendor: false`. |
| `forbidden_head_prefixes` | `[]` | Branch prefixes that may never be a PR head (e.g. an integration branch). Adds a `branch` rule. |
| `hold_label` | `"hold"` | A PR label that blocks like a hold comment. |
| `body_headings` | `[]` | Headings required by tiers with `body_headings: true` (must be non-empty if any tier asks). |
| `signature_pattern` | see below | Regular expression with named groups `name` and `rest`, anchored with `^`. |
| `verdict_sha_min_length` | `40` | Shortest commit id a verdict may use (7 to 40). The framework's rule is the full id. |
| `forbidden_globs` | `.env`, `.env.*`, `*.pem`, `*.key` | File names a PR or `scan` may not add (case ignored). Replaces the default list. |
| `scan_allow` | `.env.example`, `.env.*.example` | Exempt from name, content-type and size checks (case-exact). Secrets are still looked for. |
| `magic` | PDF, PNG, JPEG, GIF, TIFF, GGUF | Content signatures: `[{"hex": "25504446 2d", "kind": "PDF"}]`. Spaces in `hex` are ignored. Replaces the default list. |
| `secrets` | `sk-` keys, private key headers, AWS access keys, GitHub tokens | `[{"pattern": "<regex>", "label": "..."}]`. Matches are reported by label, never printed. Replaces the default list. |
| `max_file_mb` | `5` | Larger files fail `scan`. |
| `shared_account` | `true` | Adds the note that signatures cannot prove authorship on one shared account. Set `false` once `logins`, `owner_logins` and `distinct_accounts` are in use. |
| `owner_logins` | `[]` | GitHub logins that may sign as the owner. When set, an owner `Approved`, `go` or `unhold` posted from any other account counts for nothing. A login may not also be a vendor login. |
| `distinct_accounts` | `false` | When `true`, a `go` or an approval counts as independent only if it was posted from a known account other than the pull request author's. With one shared account this refuses everything, so turn it on only together with separate accounts. |
| `audit_exempt` | `[]` | Full commit ids `audit` skips (for example the commit that adopted the gate). |

## Signatures and signals
Default `signature_pattern`: `^\s*\*\*\s*(?P<name>[^*\n]+?)\s*:?\s*\*\*\s*:?\s*(?P<rest>.*)\Z`, which accepts `**Name:** text` and `**Name**: text`. Only ordinary whitespace may precede the `**`; a byte-order mark or zero-width character makes the comment unsigned.

The `name` group is classified by its first part (before the middle dot `·`, U+00B7):

| Format | Shape | Classified when | Vendor from |
| --- | --- | --- | --- |
| owner | `**Program Owner:**` | whole name is in `owner_signers` | none |
| new | `**<Role> · <Vendor>:**` | first part is in `roles` AND there are exactly two parts AND the second is a vendor `name` | the second part |
| legacy | `**<Name> · <job>:**` or `**<Name>:**` | first part is in `legacy_signers` | `legacy_signers[Name]` |
| unknown | anything else | | never an approval or a go |

`roles`, `legacy_signers` keys and `owner_signers` must be disjoint (checked at load), so one signature can only mean one thing.

The signal is the text right after the signature, matched from its first character: `go`, `Approved at <sha>`, `Not approved at <sha>` (verdict words in any case), `hold` (anyone, even unsigned), `unhold` (owner only). The `signals` rule FAILS the check when a comment looks like a signal but does not count: a verdict for the head commit that is not the first words, an unsigned verdict for the head, a too-short commit id, or an invisible character before the signature. Fix: post the signal again correctly and hide (minimize) the faulty comment.

## Gate-Record trailer
`merge` writes, as the squash commit body:
`Gate-Record: pass tier=<record> head=<40 hex> reviewers=<names; or none> owner=<yes|no> by=<--as>`
`audit` accepts only `record` values of mergeable tiers and a full 40-character lowercase head, and requires ` owner=yes by=` for tiers with `owner_approval`.
