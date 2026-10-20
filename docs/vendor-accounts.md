# One GitHub account per vendor (what turns a signature into proof)
Today every agent and the Program Owner post from one GitHub account, so `**Independent Reviewer · Codex:**` is text anyone can type (leaks L1 and L13 in `.orchestration/leaks.md`). The gate can check accounts as well as signatures once they exist. Nothing here changes behaviour until `gate.json` opts in.

## What the Program Owner does (agents never create accounts or enter credentials)
1. Create one GitHub account for each vendor that works on this repo (for example one for Claude sessions, one for Codex sessions). Check GitHub's current terms for automation accounts first.
2. Add each as a collaborator with write access, and keep the Program Owner's own account for the owner lines.
3. Sign each vendor's tooling in with its own account (`gh auth login` in that vendor's environment), so its PRs and comments are posted by that account.

## What changes in `.orchestration/gate.json` (a tier-3 PR, after the accounts exist)
```
"vendors": {"claude": {"names": ["Claude"], "branch_prefixes": ["claude/"], "logins": ["<claude account>"]},
            "codex":  {"names": ["Codex"],  "branch_prefixes": ["codex/"],  "logins": ["<codex account>"]}},
"owner_logins": ["<the Program Owner's account>"],
"distinct_accounts": true,
"shared_account": false
```

## What the gate then refuses (`tools/gate/gate.schema.md`)
- A verdict or `go` signed as a vendor but posted from another account: it counts for nothing and the `signals` rule fails.
- An owner `Approved`, `go` or `unhold` posted from an account that is not in `owner_logins`: same.
- With `distinct_accounts`, a `go` or approval posted from the pull request author's own account, or from an unknown one: not independent. This is what stops an author approving its own work, including a conflict fix it pushed.

## What it does not fix
- It proves which account wrote a comment, not which model sat behind that account. A vendor's account is only as trustworthy as whoever holds its token.
- `gate.py merge` still runs with the operator's own `gh` login.
- Until the config opts in, nothing changes and the shared-account note stays in every gate report.
