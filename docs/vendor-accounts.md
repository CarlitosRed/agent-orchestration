# One GitHub account per vendor (what turns a signature into proof)
Before 2026-10-21 every agent and the Program Owner posted from one GitHub account, so `**Independent Reviewer · Codex:**` was text anyone could type (leaks L1 and L13 in `.orchestration/leaks.md`). Since #87 this repo's `gate.json` opts in: the gate checks the account that posted each signed comment. Other projects stay on the old behaviour until their own `gate.json` opts in.

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

## How it runs day to day (no switching, no extra terminals)
Which account posts is set per command, not per terminal.
| Who | Account | How the account is chosen |
| --- | --- | --- |
| Claude session | the Claude account | the session's own `gh` config folder (`GH_CONFIG_DIR`) holds only this login |
| Codex review, relayed | the Codex account | the Claude session runs `python tools/review-relay/relay.py post <PR> ... --as-account <codex account>`; GitHub then shows the Codex login as author |
| Owner lines (`go`, `Approved at <sha>`) | the owner account | typed by the Program Owner in their own terminal or the web page; an agent never writes them (R23) |

- The relay reads the Codex token with `gh auth token --user <codex account>` from the gh config folder named by `--token-config-dir` (or env `RELAY_TOKEN_CONFIG_DIR`) when the login is not in the session's own folder, and keeps it in the environment of that run only, never in a file or the repo. It refuses a token that belongs to another login, a pull request authored by that same login, and a posted comment whose author is not that login (#92).
- Merge: `python tools/gate/gate.py merge <PR> --as "Release Manager · <Vendor>"`, run from a worktree on `origin/main` (detached). Allow that exact command in the session's permission settings (`Bash(python tools/gate/gate.py merge *)`), or each merge needs an explicit "merge" in chat. The gate, not the permission, is what demands the owner lines.
- Check the signed-in account before posting owner lines: `gh api user --jq .login` must print the owner login. A gate failure "tier-N needs the owner's comment" with the comment missing on GitHub usually means the comment went out under another account or never posted; list the comments with `gh pr view <PR> --json comments --jq '.comments[]|[.author.login,.body[0:60]]|@tsv'`.
- Proven on #87 (config) and #88 (first relayed review under the Codex token, owner line from the owner account, merged by the Claude account).

## What it does not fix
- It proves which account wrote a comment, not which model sat behind that account. A vendor's account is only as trustworthy as whoever holds its token.
- The Claude session can read the Codex token on this desk (same machine, same user). Separation here is accountability in the record, not a security boundary between the two vendors.
- `gate.py merge` still runs with the operator's own `gh` login.
